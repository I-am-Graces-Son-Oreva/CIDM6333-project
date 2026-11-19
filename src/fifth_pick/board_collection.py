"""Receipt-bound, event-scoped M4/M5 board collection. Offline verification only."""

import hashlib
import json
import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from zoneinfo import ZoneInfo

from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.errors import FifthPickError
from fifth_pick.identity import IdentityResolver
from fifth_pick.personal_readiness import LiveEventScope, authorized_projection_filter
from fifth_pick.receipts import Receipt, redact_text
from fifth_pick.registry import Registry
from fifth_pick.slate_manifest import SLATE_TIMEZONE, read_slate_run_context
from fifth_pick.snapshots import (
    SnapshotEvidence,
    SnapshotWorkflow,
    read_receipted_snapshot_ledger,
    snapshot_2_target,
)
from fifth_pick.sources.base import (
    BudgetExceededError,
    EvidenceMode,
    LiveAuthorizationError,
    MalformedPayloadError,
    SourceBoard,
    SourceError,
    SourceEvent,
    SourceProjection,
)
from fifth_pick.sources.odds_api import (
    API_KEY_ENV_VAR,
    APPROVED_BOOKMAKERS,
    APPROVED_MARKETS,
    SOURCE_ID,
    OddsApiClient,
    OddsApiSourceConfig,
    events_url,
    odds_url,
    validate_event_id,
)
from fifth_pick.sources.quota import QuotaBudget
from fifth_pick.sources.transport import HttpResponse, Transport, UrllibTransport
from fifth_pick.storage import RunStore, application_run_store, collection_lock

_EVENT_COST = len(APPROVED_MARKETS)
_POLICY = "dfs-board-policy"
_RESERVED = "DFS_BOARD_RESERVED"
_COLLECTED = "DFS_BOARD_COLLECTED"


def _json(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _reported_market_coverage(body: bytes) -> list[tuple[str, str]] | None:
    """Summarize approved response keys without inspecting player outcomes."""
    try:
        payload = json.loads(body)
    except (ValueError, RecursionError):
        return None
    books = payload.get("bookmakers") if isinstance(payload, dict) else None
    if not isinstance(books, list):
        return None
    return sorted(
        {
            (book["key"], market["key"])
            for book in books
            if isinstance(book, dict)
            and book.get("key") in APPROVED_BOOKMAKERS
            and isinstance(book.get("markets"), list)
            for market in book["markets"]
            if isinstance(market, dict) and market.get("key") in APPROVED_MARKETS
        }
    )


@dataclass(frozen=True, slots=True)
class BoardPolicy:
    """An explicit caller-supplied board scope and reference to Joseph's alias review."""

    credit_limit: int
    event_ids: tuple[str, ...]
    max_projection_age: timedelta
    aliases: Mapping[str, tuple[str, ...]]
    alias_review_reference: str

    def __post_init__(self) -> None:
        QuotaBudget(self.credit_limit)
        if not isinstance(self.event_ids, tuple) or not self.event_ids:
            raise SourceError("authorize one or more provider event IDs")
        for event in self.event_ids:
            validate_event_id(event)
        if len(set(self.event_ids)) != len(self.event_ids):
            raise SourceError("provider event IDs must be unique")
        if not isinstance(self.max_projection_age, timedelta) or (
            self.max_projection_age <= timedelta()
        ):
            raise SourceError("an explicit positive projection freshness bound is required")
        if (
            not isinstance(self.alias_review_reference, str)
            or not self.alias_review_reference.strip()
        ):
            raise SourceError("the reviewed aliases require an approval reference")
        for name, ids in self.aliases.items():
            if not isinstance(name, str) or not isinstance(ids, tuple):
                raise SourceError("provider aliases require exact names and canonical ID tuples")
        object.__setattr__(self, "aliases", MappingProxyType(dict(self.aliases)))

    def fingerprint(self) -> str:
        return _digest(
            {
                "credit_limit": self.credit_limit,
                "event_ids": sorted(self.event_ids),
                "projection_age_seconds": self.max_projection_age.total_seconds(),
                "aliases": dict(self.aliases),
                "alias_review_reference": self.alias_review_reference,
                "mode": EvidenceMode.FIXTURE,
            }
        )


@dataclass(frozen=True, slots=True)
class LiveBoardGrant:
    """Owner approval for a policy, run, collection slots and verified event scope."""

    run_id: str
    approval_reference: str
    billing_reference: str
    expires_at: datetime
    policy_sha256: str
    events: tuple[LiveEventScope, ...]
    slate_event_ids: tuple[str, ...]
    slots: tuple[int, ...] = (1,)


def _application_clock() -> datetime:
    return datetime.now(UTC)


class BoardCollector:
    """Fixture collection and explicitly granted application-owned LIVE collection."""

    def __init__(
        self,
        store: RunStore,
        policy: BoardPolicy,
        *,
        transport: Transport,
        environ: Mapping[str, str] | None = None,
        clock: Callable[[], datetime] | None = None,
        live_grant: LiveBoardGrant | None = None,
    ) -> None:
        self._store = store
        self._policy = policy
        self._grant = live_grant
        self._clock_injected = clock is not None
        self._clock = _application_clock if clock is None else clock
        environment = (
            dict(os.environ if environ is None else environ)
            if type(transport) is UrllibTransport
            else dict(environ or {})
        )
        self._credential = environment.get(API_KEY_ENV_VAR, "")
        self._client = OddsApiClient(
            transport=transport,
            environ=environment,
            clock=self._now,
        )
        self._mode = self._client.evidence_mode
        self._scope = {row.event_id: row for row in live_grant.events} if live_grant else {}
        if self._mode is EvidenceMode.LIVE and live_grant is not None:
            if len(self._scope) != len(live_grant.events):
                raise SourceError("LIVE event scope contains duplicates")
            for event in live_grant.events:
                event.validate()
            for event_id in live_grant.slate_event_ids:
                validate_event_id(event_id)
            if len(set(live_grant.slate_event_ids)) != len(
                live_grant.slate_event_ids
            ) or not self._scope.keys() <= set(live_grant.slate_event_ids):
                raise SourceError("LIVE event scope must belong to the approved complete slate")
        self._filter = None
        self._resolver = IdentityResolver(
            Registry.from_universe(load_configs().approved_universe), policy.aliases
        )
        if self._mode is EvidenceMode.LIVE:
            self._filter = authorized_projection_filter(
                self._resolver, {key: item.player_ids for key, item in self._scope.items()}
            )

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise SourceError("board collection clock must be timezone-aware")
        return now

    def _receipt(
        self,
        run_id: str,
        key: str,
        event: str,
        result: str,
        subject: str,
        reason: str,
        at: datetime,
    ) -> Receipt:
        return Receipt(at.isoformat(), event, result, subject, SOURCE_ID, reason, run_id, key)

    def collect(
        self, run_id: str, snapshot: int, event_id: str, *, request_authorized: bool = False
    ) -> tuple[SnapshotEvidence, ...]:
        """Collect one explicit event/slot or return its verified completed replay."""

        if request_authorized is not True:
            raise LiveAuthorizationError("board collection requires explicit request authorization")
        if self._mode is EvidenceMode.LIVE:
            grant = self._grant
            if (
                grant is None
                or self._clock_injected
                or grant.run_id != run_id
                or grant.policy_sha256 != self._policy.fingerprint()
                or self._store.root != application_run_store().root
                or not grant.approval_reference.strip()
                or not grant.billing_reference.strip()
                or grant.expires_at.utcoffset() is None
                or self._now() >= grant.expires_at
                or self._scope.keys() != set(self._policy.event_ids)
                or snapshot not in grant.slots
            ):
                raise LiveAuthorizationError(
                    "LIVE collection requires matching owner approval and scope"
                )
        elif self._mode is not EvidenceMode.FIXTURE or self._grant is not None:
            raise LiveAuthorizationError("unrecognized board transport")
        if type(snapshot) is not int or snapshot not in (1, 2, 3):
            raise SourceError("invalid snapshot number")
        validate_event_id(event_id)
        if event_id not in self._policy.event_ids:
            raise LiveAuthorizationError("event is outside the authorized request scope")
        with collection_lock(self._store, run_id):
            return self._collect_locked(run_id, snapshot, event_id)

    def _collect_locked(
        self, run_id: str, snapshot: int, event_id: str
    ) -> tuple[SnapshotEvidence, ...]:
        directory = self._store.run_directory(run_id)
        receipts = self._store.read_receipts(run_id)
        by_key = {row.get("event_key"): row for row in receipts}
        if None in by_key or len(by_key) != len(receipts):
            raise SourceError("duplicate or missing board run receipt identity")
        now = self._now()
        policy = self._receipt(
            run_id,
            _POLICY,
            "DFS_BOARD_POLICY",
            self._mode.name,
            self._policy.fingerprint()
            if self._grant is None
            else _digest(
                {
                    "policy": self._policy.fingerprint(),
                    "approval": self._grant.approval_reference,
                    "billing": self._grant.billing_reference,
                    "expires_at": self._grant.expires_at.isoformat(),
                    "slots": self._grant.slots,
                    "slate_event_ids": self._grant.slate_event_ids,
                    "events": [event.to_dict() for event in self._grant.events],
                }
            ),
            f"credit_limit={self._policy.credit_limit}",
            now,
        )
        if previous := by_key.get(_POLICY):
            if previous != replace(policy, timestamp=previous["timestamp"] or "").to_dict():
                raise SourceError("board run conflicts with its pinned policy or evidence mode")
        elif receipts or directory.exists():
            raise SourceError("board collection requires a fresh run or an existing board policy")

        reservations = {
            key.removesuffix("-reserved"): row
            for key, row in by_key.items()
            if isinstance(key, str) and key.startswith("dfs-board-") and key.endswith("-reserved")
        }
        completions = {
            key.removesuffix("-collected"): row
            for key, row in by_key.items()
            if isinstance(key, str) and key.startswith("dfs-board-") and key.endswith("-collected")
        }
        if reservations.keys() != completions.keys():
            raise SourceError("board run has an unfinished collection; preserve its reservation")
        if len(reservations) * _EVENT_COST > self._policy.credit_limit:
            raise SourceError("stored reservations exceed the pinned board run budget")
        stage_key = f"dfs-board-{snapshot}-{event_id}"
        replay = None
        for key, row in reservations.items():
            subject = row.get("subject")
            slot, _, event = subject.partition(":") if isinstance(subject, str) else ("", "", "")
            completion = completions[key]
            if (
                slot not in ("1", "2", "3")
                or event not in self._policy.event_ids
                or key != f"dfs-board-{slot}-{event}"
                or row.get("event") != _RESERVED
                or row.get("result") != "RESERVED"
                or row.get("reason") != f"credits={_EVENT_COST}"
                or row.get("run_id") != run_id
                or row.get("source") != SOURCE_ID
                or completion.get("event") != _COLLECTED
                or completion.get("result") != self._mode.name
                or completion.get("subject") != subject
                or completion.get("run_id") != run_id
                or completion.get("source") != SOURCE_ID
            ):
                raise SourceError("board run contains an invalid reservation or completion")
            if self._mode is EvidenceMode.LIVE and any(
                (attempt := by_key.get(f"{key}-attempt-{index}")) is None
                or attempt.get("event") != "DFS_HTTP_REQUEST"
                or attempt.get("subject") != subject
                or attempt.get("run_id") != run_id
                or attempt.get("source") != SOURCE_ID
                for index in (1, 2)
            ):
                raise SourceError("LIVE board collection has missing or invalid request receipts")
            responses = tuple(by_key.get(f"{key}-{kind}") for kind in ("events", "odds"))
            entries = self._verify_replay(run_id, int(slot), event, completion, responses)
            if key == stage_key:
                replay = entries
        if replay is not None:
            return replay
        if snapshot != 1 and f"dfs-board-1-{event_id}" not in completions:
            raise SourceError("collect Snapshot 1 for this event first")
        if any(f"dfs-board-{later}-{event_id}" in completions for later in range(snapshot + 1, 4)):
            raise SourceError("a later observation is already recorded for this event")
        if (len(reservations) + 1) * _EVENT_COST > self._policy.credit_limit:
            raise BudgetExceededError("persistent board run budget is exhausted")

        if self._mode is EvidenceMode.LIVE:
            self._check_live_window(run_id, snapshot, event_id, now)
        self._client.require_credentials()
        if previous is None:
            self._store.append_receipt(policy)
        subject = f"{snapshot}:{event_id}"
        self._store.append_receipt(
            self._receipt(
                run_id,
                f"{stage_key}-reserved",
                _RESERVED,
                "RESERVED",
                subject,
                f"credits={_EVENT_COST}",
                now,
            )
        )
        return self._fetch_reserved(
            run_id, snapshot, event_id, stage_key, subject, first=not reservations
        )

    def _fetch_reserved(
        self,
        run_id: str,
        snapshot: int,
        event_id: str,
        stage_key: str,
        subject: str,
        *,
        first: bool,
    ) -> tuple[SnapshotEvidence, ...]:
        recorded_responses = []
        requested_urls = set()
        event_quota: tuple[int, int] | None = None

        def authorize_request(url: str, at: datetime) -> None:
            if self._mode is not EvidenceMode.LIVE:
                return
            assert self._grant is not None
            if (
                at >= self._grant.expires_at
                or url in requested_urls
                or url not in (events_url(), odds_url(event_id, OddsApiSourceConfig()))
            ):
                raise LiveAuthorizationError("live request exceeds its approved sequence or time")
            if url != events_url():
                self._check_live_window(run_id, snapshot, event_id, at)
            requested_urls.add(url)
            self._store.append_receipt(
                self._receipt(
                    run_id,
                    f"{stage_key}-attempt-{len(requested_urls)}",
                    "DFS_HTTP_REQUEST",
                    "ATTEMPTED",
                    subject,
                    redact_text(url, (self._credential,)),
                    at,
                )
            )

        def select_events(events: tuple[SourceEvent, ...]) -> str:
            scope = self._scope[event_id]
            assert self._grant is not None
            self._check_public_text(
                text
                for event in events
                for text in (event.event_id, event.away_team, event.home_team)
            )
            chicago = ZoneInfo(SLATE_TIMEZONE)
            date = scope.tipoff.astimezone(chicago).date()
            current = {
                event.event_id
                for event in events
                if event.commence_time.astimezone(chicago).date() == date
            }
            approved = set(self._grant.slate_event_ids)
            if first:
                from fifth_pick.official_slate import load_official_slate, reconcile_coverage

                official = load_official_slate(date)
                if (
                    official is not None
                    and not reconcile_coverage(official, events, day=date)[
                        "provider_matches_official_slate"
                    ]
                ):
                    raise SourceError(
                        "provider schedule does not cover the verified official slate"
                    )
            if (first and current != approved) or not current <= approved:
                raise SourceError("provider schedule differs from the approved full slate")
            if not any(scope.matches(event) for event in events):
                raise SourceError("provider schedule differs from the approved event scope")
            return event_id

        def observe(url: str, requested: datetime, retrieved: datetime, response: HttpResponse):
            nonlocal event_quota
            request = "events" if url == events_url() else "odds"
            headers = {key.lower(): value for key, value in response.headers.items()}
            quota = {}
            for field in ("x-requests-remaining", "x-requests-used", "x-requests-last"):
                value = headers.get(field, "")
                quota[field] = (
                    int(value)
                    if value.isascii() and value.isdecimal() and (len(value) <= 12)
                    else None
                )
            status = response.status
            coverage = (
                {"provider_market_coverage": _reported_market_coverage(response.body)}
                if self._mode is EvidenceMode.LIVE and request == "odds" and status == 200
                else {}
            )
            recorded = self._store.append_receipt(
                self._receipt(
                    run_id,
                    f"{stage_key}-{request}",
                    "DFS_HTTP_RESPONSE",
                    str(status),
                    subject,
                    _json(
                        {
                            "url": redact_text(url, (self._credential,)),
                            "requested_at": requested.isoformat(),
                            "retrieved_at": retrieved.isoformat(),
                            "payload_sha256": hashlib.sha256(response.body).hexdigest(),
                            "quota": quota,
                            **coverage,
                        }
                    ),
                    retrieved,
                )
            )
            recorded_responses.append(recorded.receipt)
            if status == 200 and (
                retrieved < requested
                or quota["x-requests-remaining"] is None
                or (
                    self._mode is EvidenceMode.LIVE
                    and request == "events"
                    and quota["x-requests-last"] != 0
                )
                or (
                    request == "odds"
                    and (quota["x-requests-last"] is None or quota["x-requests-last"] > _EVENT_COST)
                )
            ):
                raise SourceError("missing or inconsistent request quota or timestamps")
            if status == 200 and self._mode is EvidenceMode.LIVE:
                used = quota["x-requests-used"]
                remaining = quota["x-requests-remaining"]
                last = quota["x-requests-last"]
                if used is None or remaining is None or last is None:
                    raise SourceError("LIVE quota counters are incomplete")
                if request == "events":
                    event_quota = used, remaining
                elif event_quota is None or (
                    used - event_quota[0] != last or event_quota[1] - remaining != last
                ):
                    raise SourceError("LIVE quota counters disagree with the odds charge")

        try:
            board = self._client.fetch_board(
                live_authorized=True,
                budget=QuotaBudget(_EVENT_COST),
                event_id=event_id if self._mode is EvidenceMode.FIXTURE else None,
                retain_schedule=first,
                select_event=select_events if self._mode is EvidenceMode.LIVE else None,
                observe_request=authorize_request if self._mode is EvidenceMode.LIVE else None,
                observe_response=observe,
                projection_allowed=self._filter,
            )
            if self._mode is EvidenceMode.LIVE:
                self._check_live_window(run_id, snapshot, event_id, self._now())
                self._check_public_text(row.provider_player_name for row in board.projections)
            board = self._validate_board(board, event_id, run_id, first=first)
            entries = SnapshotWorkflow(
                self._store, self._resolver, AuthorizationGate(), clock=self._now
            ).collect(
                run_id,
                snapshot,
                board,
                event_scope=event_id if self._mode is EvidenceMode.LIVE else None,
            )
        except (FifthPickError, ValueError, OSError) as exc:
            self._store.append_receipt(
                self._receipt(
                    run_id,
                    f"{stage_key}-stopped",
                    "DFS_BOARD_STOPPED",
                    "STOPPED",
                    subject,
                    type(exc).__name__,
                    self._now(),
                )
            )
            if self._mode is EvidenceMode.LIVE:
                raise SourceError("live board collection stopped; see source receipts") from None
            raise
        metadata = {
            "mode": board.provenance.evidence_mode.value,
            "event_id": event_id,
            "response_receipts_sha256": _digest(recorded_responses),
            "schedule_event_ids": [event.event_id for event in board.events],
            "payload_sha256": board.provenance.payload_sha256,
            "snapshots_sha256": _digest([entry.to_dict() for entry in entries]),
            "coverage": sorted(
                {(row.platform.value, row.category.value) for row in board.projections}
            ),
            "source_update_time": (
                board.provenance.source_update_time.isoformat()
                if board.provenance.source_update_time is not None
                else None
            ),
            "retrieved_at": board.provenance.retrieved_at.isoformat(),
        }
        self._store.append_receipt(
            self._receipt(
                run_id,
                f"{stage_key}-collected",
                _COLLECTED,
                self._mode.name,
                subject,
                _json(metadata),
                self._now(),
            )
        )
        return entries

    def _check_public_text(self, values: Iterable[str]) -> None:
        if any(
            (self._credential and self._credential in value) or not value.isprintable()
            for value in values
        ):
            raise SourceError("provider returned unsafe public text")

    def _check_live_window(self, run_id: str, snapshot: int, event_id: str, at: datetime) -> None:
        scope = self._scope[event_id]
        chicago = ZoneInfo(SLATE_TIMEZONE)
        tipoff = scope.tipoff
        if at >= tipoff or at.astimezone(chicago).date() != tipoff.astimezone(chicago).date():
            raise SourceError("live collection is outside its approved slate or after tipoff")
        if snapshot == 1:
            if snapshot_2_target(at, tipoff) is None:
                raise SourceError("no time remains for three legitimate observations")
            return
        from fifth_pick.schedule import schedule_view

        schedule = schedule_view(self._store, run_id, as_of=at)
        candidates = schedule["candidates"]
        if not isinstance(candidates, list):
            raise SourceError("live schedule is missing candidate observations")
        due = [
            row
            for row in candidates
            if isinstance(row, dict)
            and row.get("event_id") == event_id
            and row.get(f"snapshot_{snapshot}") == "DUE"
        ]
        if not due:
            raise SourceError("no authorized observations are due in this snapshot window")
        if (
            snapshot == 3
            and self._grant is not None
            and self._grant.slots == (1, 2, 3)
            and not any(row.get("snapshot_2") == "RECORDED" for row in due)
        ):
            raise SourceError("no recorded second observation remains in the complete series")

    def _validate_board(
        self, board: SourceBoard, event_id: str, run_id: str, *, first: bool
    ) -> SourceBoard:
        if board.provenance.evidence_mode is not self._mode:
            raise SourceError("board mode does not match the authorized run")
        event = next(event for event in board.events if event.event_id == event_id)
        if first:
            chicago = ZoneInfo(SLATE_TIMEZONE)
            if event.commence_time.astimezone(chicago).date() != (
                board.provenance.request_timestamp.astimezone(chicago).date()
            ):
                raise SourceError("selected event is outside the run's Chicago slate date")
        else:
            context = read_slate_run_context(self._store, run_id)
            start = context.event_boards[0]
            if start.evidence_mode is not self._mode or not any(
                item.event_id == event_id
                and item.commence_time == event.commence_time
                and item.home_team == event.home_team
                and item.away_team == event.away_team
                and item.commence_time.astimezone(ZoneInfo(SLATE_TIMEZONE)).date().isoformat()
                == context.metadata.slate_date
                for item in start.events
            ):
                raise SourceError("selected event does not match the pinned run schedule")
        return validate_projection_rows(
            board, event, self._resolver, self._policy.max_projection_age
        )

    def _verify_replay(
        self,
        run_id: str,
        snapshot: int,
        event_id: str,
        completion: dict[str, str | None],
        responses: tuple[dict[str, str | None] | None, ...],
    ) -> tuple[SnapshotEvidence, ...]:
        return _verify_completed_slot(
            self._store, self._mode, run_id, snapshot, event_id, completion, responses
        )


def _verify_completed_slot(
    store: RunStore,
    mode: EvidenceMode,
    run_id: str,
    snapshot: int,
    event_id: str,
    completion: dict[str, str | None],
    responses: tuple[dict[str, str | None] | None, ...],
) -> tuple[SnapshotEvidence, ...]:
    entries = tuple(
        row
        for row in read_receipted_snapshot_ledger(store, run_id)
        if isinstance(row, SnapshotEvidence)
        and row.event_id == event_id
        and row.snapshot.number == snapshot
    )
    try:
        metadata = json.loads(completion.get("reason") or "")
    except (ValueError, KeyError) as exc:
        raise SourceError("invalid stored board completion") from exc
    context = read_slate_run_context(store, run_id)
    if (
        not isinstance(metadata, dict)
        or metadata.get("mode") != mode
        or metadata.get("event_id") != event_id
        or metadata.get("response_receipts_sha256") != _digest(responses)
        or any(
            response is None
            or response.get("event") != "DFS_HTTP_RESPONSE"
            or response.get("result") != "200"
            or response.get("run_id") != run_id
            or response.get("subject") != f"{snapshot}:{event_id}"
            or response.get("source") != SOURCE_ID
            for response in responses
        )
        or any(item.evidence_mode is not mode for item in context.event_boards)
        or metadata.get("snapshots_sha256") != _digest([row.to_dict() for row in entries])
        or not any(
            board.snapshot_number == snapshot
            and board.evidence_mode is mode
            and board.payload_sha256 == metadata.get("payload_sha256")
            and [event.event_id for event in board.events] == metadata.get("schedule_event_ids")
            for board in context.event_boards
        )
    ):
        raise SourceError("stored board completion does not match its manifest or snapshots")
    return entries


def live_slot_has_bound_aliases(run_id: str, snapshot: int, event_id: str) -> bool:
    """Verify a complete LIVE collector receipt binds this event's exact snapshot bytes."""
    store = application_run_store()
    rows = store.read_receipts(run_id)
    receipts = {row["event_key"]: row for row in rows}
    if None in receipts or len(rows) != len(receipts):
        return False
    prefix = f"dfs-board-{snapshot}-{event_id}"
    subject = f"{snapshot}:{event_id}"
    required = (
        (_POLICY, "DFS_BOARD_POLICY", "LIVE", None, None),
        (f"{prefix}-reserved", _RESERVED, "RESERVED", subject, f"credits={_EVENT_COST}"),
        (f"{prefix}-attempt-1", "DFS_HTTP_REQUEST", "ATTEMPTED", subject, events_url()),
        (
            f"{prefix}-attempt-2",
            "DFS_HTTP_REQUEST",
            "ATTEMPTED",
            subject,
            odds_url(event_id, OddsApiSourceConfig()),
        ),
        (f"{prefix}-collected", _COLLECTED, "LIVE", subject, None),
    )
    if any(
        (row := receipts.get(key)) is None
        or row["run_id"] != run_id
        or row["event"] != event
        or row["result"] != result
        or row["source"] != SOURCE_ID
        or (expected_subject is not None and row["subject"] != expected_subject)
        or (reason is not None and row["reason"] != reason)
        for key, event, result, expected_subject, reason in required
    ):
        return False
    receipt = receipts[f"{prefix}-collected"]
    responses = tuple(receipts.get(f"{prefix}-{kind}") for kind in ("events", "odds"))
    try:
        return bool(
            _verify_completed_slot(
                store, EvidenceMode.LIVE, run_id, snapshot, event_id, receipt, responses
            )
        )
    except (FifthPickError, OSError, ValueError):
        return False


def validate_projection_rows(
    board: SourceBoard,
    event: SourceEvent,
    resolver: IdentityResolver,
    max_projection_age: timedelta,
) -> SourceBoard:
    """Reject stale or conflicting lines before recording any snapshot."""
    distinct: dict[tuple[object, ...], SourceProjection] = {}
    for row in event.projections:
        age = row.retrieved_at - row.source_update_time
        if not timedelta() <= age <= max_projection_age:
            raise SourceError("provider projection is stale or dated after retrieval")
        identity = resolver.resolve_provider(row.provider_player_name)
        player = row.provider_player_name if identity.player is None else identity.player.player_id
        key = (row.platform, player, row.category, row.direction)
        if key in distinct and distinct[key] != row:
            raise MalformedPayloadError("conflicting duplicate projection for the same candidate")
        distinct[key] = row
    updated = replace(event, projections=tuple(distinct.values()))
    return replace(
        board,
        events=tuple(
            updated if other.event_id == event.event_id else other for other in board.events
        ),
    )
