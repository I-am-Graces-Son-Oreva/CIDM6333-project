"""One-event, one-shot board discovery and collection. Provider access is opt-in."""

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fifth_pick.authorization import AuthorizationGate
from fifth_pick.board_collection import _digest, _json, validate_projection_rows
from fifth_pick.config import load_configs
from fifth_pick.errors import FifthPickError
from fifth_pick.identity import IdentityResolver
from fifth_pick.personal_readiness import LiveEventScope, authorized_projection_filter
from fifth_pick.receipts import Receipt, redact_text
from fifth_pick.registry import Registry
from fifth_pick.slate_manifest import SLATE_TIMEZONE, SlateEvent, read_slate_run_context
from fifth_pick.snapshots import SnapshotEvidence, SnapshotWorkflow, read_receipted_snapshot_ledger
from fifth_pick.sources.base import EvidenceMode, LiveAuthorizationError, SourceError, SourceEvent
from fifth_pick.sources.normalize import MARKET_TO_CATEGORY
from fifth_pick.sources.odds_api import (
    API_KEY_ENV_VAR,
    APPROVED_BOOKMAKERS,
    APPROVED_MARKETS,
    SOURCE_ID,
    OddsApiClient,
    OddsApiSourceConfig,
    events_url,
    odds_url,
)
from fifth_pick.sources.quota import QuotaBudget, QuotaSnapshot, parse_quota_headers
from fifth_pick.sources.transport import HttpResponse, Transport, UrllibTransport
from fifth_pick.storage import RunStore, application_run_store, collection_lock

_REQUEST_LIMIT = 2
_CREDIT_LIMIT = 5
_FRESHNESS = timedelta(minutes=30)
_PREFIX = "dfs-smoke-"
_RESERVATION = _PREFIX + "reserved"
_COMPLETION = _PREFIX + "completed"


@dataclass(frozen=True, slots=True)
class SmokeAuthorization:
    """Separate owner authorization for one named run, with current LIVE billing evidence."""

    run_id: str
    evidence_mode: EvidenceMode
    approval_reference: str
    expires_at: datetime
    billing_reference: str | None = None
    alias_review_sha256: str | None = None
    event_scope: LiveEventScope | None = None


@dataclass(frozen=True, slots=True)
class SmokeEvent:
    event_id: str
    home_team: str
    away_team: str
    tipoff: datetime
    slate_game_count: int
    slate_date: str
    slate: tuple[SlateEvent, ...]

    @property
    def slate_classification(self) -> str:
        return "FULL" if self.slate_game_count >= 5 else "HALF"


@dataclass(frozen=True, slots=True)
class UnresolvedIdentity:
    provider_label: str
    platforms: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class SmokeProjection:
    provider_label: str
    platform: str
    category: str
    direction: str
    projection: float
    updated_at: str
    retrieved_at: str


@dataclass(frozen=True, slots=True)
class SmokeResult:
    event: SmokeEvent
    evidence_mode: EvidenceMode
    coverage: tuple[tuple[str, str], ...]
    unresolved: tuple[UnresolvedIdentity, ...]
    accepted_snapshots: int
    projections: tuple[SmokeProjection, ...]
    payload_sha256: str
    credits_used: int

    @property
    def market_coverage(self) -> tuple[tuple[str, str], ...]:
        markets = {category.value: market for market, category in MARKET_TO_CATEGORY.items()}
        return tuple((platform, markets[category]) for platform, category in self.coverage)

    @property
    def missing_coverage(self) -> tuple[tuple[str, str], ...]:
        returned = set(self.market_coverage)
        return tuple(
            (platform, market)
            for platform in APPROVED_BOOKMAKERS
            for market in APPROVED_MARKETS
            if (platform, market) not in returned
        )


def _event_record(event: SmokeEvent) -> dict[str, object]:
    return {
        **asdict(event),
        "tipoff": event.tipoff.isoformat(),
        "slate": [
            {**asdict(row), "commence_time": row.commence_time.isoformat()} for row in event.slate
        ],
    }


def _receipt(
    run_id: str, suffix: str, event: str, result: str, subject: str, reason: object, at: datetime
) -> Receipt:
    return Receipt(
        at.isoformat(), event, result, subject, SOURCE_ID, _json(reason), run_id, _PREFIX + suffix
    )


def _verify_replay(
    store: RunStore,
    run_id: str,
    receipts: tuple[dict[str, str | None], ...],
    authorization: SmokeAuthorization,
) -> SmokeResult:
    by_key = {row.get("event_key"): row for row in receipts}
    if None in by_key or len(by_key) != len(receipts) or _COMPLETION not in by_key:
        raise SourceError("smoke run is unfinished or inconsistent; preserve its reservation")
    completion = by_key[_COMPLETION]
    prior = [
        row
        for row in receipts
        if (row.get("event_key") or "").startswith(_PREFIX) and row.get("event_key") != _COMPLETION
    ]
    try:
        record = json.loads(completion["reason"] or "")
        selected = dict(record["event"])
        selected["tipoff"] = datetime.fromisoformat(selected["tipoff"])
        selected["slate"] = tuple(
            SlateEvent(
                row["event_id"],
                row["home_team"],
                row["away_team"],
                datetime.fromisoformat(row["commence_time"]),
            )
            for row in selected["slate"]
        )
        event = SmokeEvent(**selected)
        result = SmokeResult(
            event,
            EvidenceMode(record["mode"]),
            tuple((platform, category) for platform, category in record["coverage"]),
            tuple(
                UnresolvedIdentity(
                    row["provider_label"],
                    tuple(row["platforms"]),
                    tuple(row["candidate_ids"]),
                    row["reason"],
                )
                for row in record["unresolved"]
            ),
            record["accepted_snapshots"],
            tuple(SmokeProjection(**row) for row in record["projections"]),
            record["payload_sha256"],
            record["credits_used"],
        )
        if (
            completion.get("event") != "DFS_SMOKE_COMPLETED"
            or completion.get("source") != SOURCE_ID
            or completion.get("run_id") != run_id
            or completion.get("subject") != _digest(record)
            or completion.get("result") != result.evidence_mode.name
            or result.evidence_mode is not authorization.evidence_mode
            or (
                result.evidence_mode is EvidenceMode.LIVE
                and (
                    authorization.event_scope is None
                    or result.event.event_id != authorization.event_scope.event_id
                    or result.unresolved
                )
            )
            or record["prior_receipts_sha256"] != _digest(prior)
            or set(by_key).issuperset(
                {
                    _RESERVATION,
                    _PREFIX + "http-events",
                    _PREFIX + "http-odds",
                    _PREFIX + "event-confirmed",
                    _PREFIX + "request-events",
                    _PREFIX + "request-odds",
                }
            )
            is False
        ):
            raise ValueError("unbound smoke completion")
        context = read_slate_run_context(store, run_id)
        if context.metadata.start_payload_sha256 != result.payload_sha256 or not any(
            board.snapshot_number == 1
            and board.payload_sha256 == result.payload_sha256
            and board.evidence_mode is result.evidence_mode
            and any(
                row.event_id == result.event.event_id
                and row.home_team == event.home_team
                and row.away_team == event.away_team
                and row.commence_time == event.tipoff
                for row in board.events
            )
            for board in context.event_boards
        ):
            raise ValueError("unbound board manifest")
        snapshots = [
            row.to_dict()
            for row in read_receipted_snapshot_ledger(store, run_id)
            if isinstance(row, SnapshotEvidence)
            and row.event_id == event.event_id
            and row.snapshot.number == 1
        ]
        if result.accepted_snapshots != len(snapshots) or record["snapshots_sha256"] != _digest(
            snapshots
        ):
            raise ValueError("unbound snapshots")
    except (FifthPickError, ValueError, TypeError, KeyError) as exc:
        raise SourceError(
            "stored smoke evidence is incomplete or does not match its receipts"
        ) from exc
    return result


def _current_time() -> datetime:
    return datetime.now(UTC)


def run_board_smoke(
    *,
    run_id: str,
    authorization: SmokeAuthorization | None = None,
    confirm_event: Callable[[SmokeEvent], bool] | None = None,
    review_identity: Callable[[UnresolvedIdentity], None] | None = None,
    aliases: Mapping[str, tuple[str, ...]] | None = None,
    store: RunStore | None = None,
    transport: Transport | None = None,
    environ: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> SmokeResult:
    """Execute one authorized attempt or verify a completed replay with no requests."""

    if (
        not isinstance(authorization, SmokeAuthorization)
        or authorization.run_id != run_id
        or not isinstance(authorization.approval_reference, str)
        or not authorization.approval_reference.strip()
        or authorization.evidence_mode not in (EvidenceMode.FIXTURE, EvidenceMode.LIVE)
        or not isinstance(authorization.expires_at, datetime)
        or authorization.expires_at.utcoffset() is None
        or confirm_event is None
    ):
        raise LiveAuthorizationError(
            "board smoke requires separate run authorization and confirmation"
        )

    mode = authorization.evidence_mode
    app_store = application_run_store()
    store = app_store if store is None else store
    if mode is EvidenceMode.LIVE:
        if clock is not None:
            raise LiveAuthorizationError("LIVE smoke requires the application clock")
        if (
            not isinstance(authorization.billing_reference, str)
            or not authorization.billing_reference.strip()
            or store.root != app_store.root
            or (transport is not None and type(transport) is not UrllibTransport)
        ):
            raise LiveAuthorizationError(
                "LIVE smoke requires current billing evidence and the "
                "application-owned transport and store"
            )
        if not isinstance(authorization.event_scope, LiveEventScope):
            raise LiveAuthorizationError("LIVE smoke requires a verified relevant event scope")
        authorization.event_scope.validate()
        transport = UrllibTransport() if transport is None else transport
    elif transport is None or environ is None:
        raise LiveAuthorizationError(
            "fixture smoke requires an explicit offline transport and credentials"
        )
    now = _current_time if clock is None else clock
    client = OddsApiClient(transport=transport, environ=environ, clock=now)
    if client.evidence_mode is not mode:
        raise LiveAuthorizationError("smoke authorization and transport evidence modes differ")

    alias_map = {} if aliases is None else dict(aliases)
    if (
        mode is EvidenceMode.LIVE
        and alias_map
        and (authorization.alias_review_sha256 != _digest(alias_map))
    ):
        raise LiveAuthorizationError("LIVE aliases require a matching reviewed-map digest")
    registry = Registry.from_universe(load_configs().approved_universe)
    resolver = IdentityResolver(registry, alias_map)
    policy = {
        "mode": mode.value,
        "request_limit": _REQUEST_LIMIT,
        "credit_limit": _CREDIT_LIMIT,
        "freshness_seconds": _FRESHNESS.total_seconds(),
        "snapshot": 1,
        "approval_sha256": _digest(authorization.approval_reference),
        "billing_sha256": _digest(authorization.billing_reference),
        "aliases_sha256": _digest(alias_map),
        "expires_at": authorization.expires_at.isoformat(),
        "markets": APPROVED_MARKETS,
        **(
            {"event_scope_sha256": _digest(authorization.event_scope.to_dict())}
            if authorization.event_scope is not None
            else {}
        ),
    }
    with collection_lock(store, run_id):
        receipts = store.read_receipts(run_id)
        reservation = _receipt(
            run_id, "reserved", "DFS_SMOKE_RESERVED", mode.name, _digest(policy), policy, now()
        )
        if receipts:
            previous = [row for row in receipts if row.get("event_key") == _RESERVATION]
            expected = reservation.to_dict()
            if len(previous) != 1 or previous[0] != {
                **expected,
                "timestamp": previous[0].get("timestamp"),
            }:
                raise SourceError("smoke run conflicts with its receipt-bound authorization")
            return _verify_replay(store, run_id, receipts, authorization)

        if store.run_directory(run_id).exists():
            raise SourceError("smoke requires a fresh run directory")
        if now().utcoffset() is None or now() >= authorization.expires_at:
            raise LiveAuthorizationError("smoke authorization is expired or has invalid clock")
        client.require_credentials()
        store.append_receipt(reservation)
        return _collect(
            run_id,
            store,
            client,
            authorization,
            confirm_event,
            review_identity,
            registry,
            resolver,
            alias_map,
            now,
            environ,
        )


def _collect(
    run_id: str,
    store: RunStore,
    client: OddsApiClient,
    grant: SmokeAuthorization,
    confirm_event: Callable[[SmokeEvent], bool],
    review_identity: Callable[[UnresolvedIdentity], None] | None,
    registry: Registry,
    resolver: IdentityResolver,
    aliases: Mapping[str, tuple[str, ...]],
    now: Callable[[], datetime],
    environ: Mapping[str, str] | None,
) -> SmokeResult:
    mode = grant.evidence_mode
    credential = (os.environ if environ is None else environ).get(API_KEY_ENV_VAR, "")
    selected = None
    requests: set[str] = set()
    observed: dict[str, int | None] = {}
    observed_dates: dict[str, str] = {}
    observed_quota: dict[str, QuotaSnapshot] = {}
    chicago = ZoneInfo(SLATE_TIMEZONE)
    scope = grant.event_scope
    allow = (
        authorized_projection_filter(resolver, {scope.event_id: scope.player_ids})
        if scope is not None and mode is EvidenceMode.LIVE
        else None
    )

    def authorize_request(url: str, at: datetime) -> None:
        if at >= grant.expires_at:
            raise SourceError("smoke authorization expired before request")
        if url == events_url() and not requests:
            kind = "events"
        elif (
            selected is not None
            and requests == {"events"}
            and at < selected.tipoff
            and url == odds_url(selected.event_id, OddsApiSourceConfig())
        ):
            kind = "odds"
        else:
            raise SourceError("request is outside the reserved smoke sequence")
        store.append_receipt(
            _receipt(
                run_id,
                f"request-{kind}",
                "DFS_SMOKE_HTTP_REQUEST",
                "ATTEMPTED",
                kind,
                {"url": redact_text(url, (credential,)), "requested_at": at.isoformat()},
                at,
            )
        )
        requests.add(kind)

    def observe(url: str, requested: datetime, retrieved: datetime, response: HttpResponse) -> None:
        kind = "events" if url == events_url() else "odds"
        digest = hashlib.sha256(response.body).hexdigest()
        if kind in observed or len(observed) == _REQUEST_LIMIT:
            raise SourceError("smoke already performed its bounded request")
        # Raw source bodies and credentials are never persisted.
        record: dict[str, object] = {
            "url": redact_text(url, (credential,)),
            "requested_at": requested.isoformat(),
            "retrieved_at": retrieved.isoformat(),
            "payload_sha256": digest,
        }
        observed[kind] = None
        observed_dates[kind] = requested.astimezone(chicago).date().isoformat()
        try:
            quota = parse_quota_headers(response.headers)
            record["quota"] = asdict(quota)
            observed[kind] = quota.last
            observed_quota[kind] = quota
            if response.status == 200 and (
                requested > retrieved
                or quota.remaining is None
                or (kind == "events" and mode is EvidenceMode.LIVE and quota.last != 0)
                or (kind == "odds" and (quota.last is None or not 0 <= quota.last <= _CREDIT_LIMIT))
            ):
                raise SourceError("unverified or unexpected smoke quota or observation time")
            if response.status == 200 and mode is EvidenceMode.LIVE:
                if quota.used is None or quota.used < 0 or quota.remaining is None:
                    raise SourceError("provider quota counters are incomplete")
                if kind == "odds":
                    before = observed_quota["events"]
                    if (
                        before.used is None
                        or before.remaining is None
                        or quota.used - before.used != quota.last
                        or before.remaining - quota.remaining != quota.last
                    ):
                        raise SourceError("provider quota counters disagree with the odds charge")
        finally:
            store.append_receipt(
                _receipt(
                    run_id,
                    f"http-{kind}",
                    "DFS_SMOKE_HTTP_RESPONSE",
                    str(response.status),
                    digest,
                    record,
                    retrieved,
                )
            )

    def select(schedule: tuple[SourceEvent, ...]) -> str:
        nonlocal selected
        at = now()
        slate_date = observed_dates["events"]
        if at.astimezone(chicago).date().isoformat() != slate_date:
            raise SourceError("Chicago slate date changed during discovery")
        slate = [
            row
            for row in schedule
            if (row.commence_time.astimezone(chicago).date().isoformat() == slate_date)
        ]
        eligible = [
            row for row in slate if row.commence_time > at and (scope is None or scope.matches(row))
        ]
        for row in schedule:
            for public_text in (row.event_id, row.home_team, row.away_team):
                _require_safe_text(public_text, credential)
        store.append_receipt(
            _receipt(
                run_id,
                "slate",
                "DFS_SMOKE_SLATE_DISCOVERED",
                mode.name,
                slate_date,
                [
                    {
                        "event_id": row.event_id,
                        "home": row.home_team,
                        "away": row.away_team,
                        "tipoff": row.commence_time.isoformat(),
                    }
                    for row in slate
                ],
                at,
            )
        )
        if not eligible:
            raise SourceError("no upcoming event on the current Chicago slate")
        event = min(eligible, key=lambda row: (row.commence_time, row.event_id))
        selected = SmokeEvent(
            event.event_id,
            event.home_team,
            event.away_team,
            event.commence_time,
            len(slate),
            slate_date,
            tuple(
                SlateEvent(row.event_id, row.home_team, row.away_team, row.commence_time)
                for row in slate
            ),
        )
        if confirm_event(selected) is not True:
            raise SourceError("selected event was not confirmed")
        confirmed_at = now()
        if (
            confirmed_at >= selected.tipoff
            or confirmed_at >= grant.expires_at
            or confirmed_at.astimezone(chicago).date().isoformat() != slate_date
        ):
            raise SourceError("selected event or authorization expired before odds")
        store.append_receipt(
            _receipt(
                run_id,
                "event-confirmed",
                "DFS_SMOKE_EVENT_CONFIRMED",
                mode.name,
                selected.event_id,
                _event_record(selected),
                confirmed_at,
            )
        )
        return selected.event_id

    try:
        board = client.fetch_board(
            live_authorized=True,
            budget=QuotaBudget(_CREDIT_LIMIT),
            retain_schedule=True,
            select_event=select,
            observe_response=observe,
            observe_request=authorize_request,
            projection_allowed=allow,
        )
        if selected is None or now() >= selected.tipoff:
            raise SourceError("the board was not acquired before tipoff")
        event = next(row for row in board.events if row.event_id == selected.event_id)
        for row in event.projections:
            _require_safe_text(row.provider_player_name, credential)
        board = validate_projection_rows(board, event, resolver, _FRESHNESS)
        unknown: dict[str, set[str]] = {}
        for row in board.projections:
            if not resolver.resolve_provider(row.provider_player_name).resolved:
                unknown.setdefault(row.provider_player_name, set()).add(row.platform.value)
        unresolved = []
        for label, platforms in sorted(unknown.items()):
            name_match = registry.player_by_canonical_name(label) or registry.player_by_alias(label)
            candidates = set(aliases.get(label, ()))
            if name_match is not None:
                candidates.add(name_match.player_id)
            item = UnresolvedIdentity(
                label,
                tuple(sorted(platforms)),
                tuple(sorted(candidates)),
                "No verified unambiguous provider identity",
            )
            unresolved.append(item)
            if review_identity is not None:
                review_identity(item)
        if now() >= selected.tipoff or now() >= grant.expires_at:
            raise SourceError("event or authorization expired before Snapshot 1 was recorded")
        if any(now() - row.source_update_time > _FRESHNESS for row in board.projections):
            raise SourceError("projection expired before Snapshot 1 was recorded")
        snapshots = SnapshotWorkflow(store, resolver, AuthorizationGate(), clock=now).collect(
            run_id, 1, board, event_scope=scope.event_id if allow is not None and scope else None
        )
        projections = tuple(
            SmokeProjection(
                row.provider_player_name,
                row.platform.value,
                row.category.value,
                row.direction.value,
                row.projection,
                row.source_update_time.isoformat(),
                row.retrieved_at.isoformat(),
            )
            for row in board.projections
        )
        credits = observed.get("odds")
        if credits is None:
            raise SourceError("odds receipt has no verified credit counter")
        result = SmokeResult(
            selected,
            mode,
            tuple(sorted({(row.platform, row.category) for row in projections})),
            tuple(unresolved),
            len(snapshots),
            projections,
            board.provenance.payload_sha256,
            credits,
        )
        prior = [
            row
            for row in store.read_receipts(run_id)
            if (row.get("event_key") or "").startswith(_PREFIX)
        ]
        data = {
            **asdict(result),
            "event": _event_record(selected),
            "mode": mode.value,
            "prior_receipts_sha256": _digest(prior),
            "snapshots_sha256": _digest([row.to_dict() for row in snapshots]),
        }
        store.append_receipt(
            _receipt(
                run_id,
                "completed",
                "DFS_SMOKE_COMPLETED",
                mode.name,
                _digest(data),
                data,
                now(),
            )
        )
        return result
    except (FifthPickError, ValueError, OSError) as exc:
        store.append_receipt(
            _receipt(
                run_id,
                "stopped",
                "DFS_SMOKE_STOPPED",
                "STOPPED",
                selected.event_id if selected else run_id,
                {"reason": _safe_error(exc, credential), "responses": sorted(observed)},
                now(),
            )
        )
        raise SourceError(f"board smoke stopped: {_safe_error(exc, credential)}") from None


def _require_safe_text(text: str, credential: str) -> None:
    if not text.isprintable() or redact_text(text, (credential,)) != text:
        raise SourceError("provider metadata contains unsafe text")


def _safe_error(exc: Exception, credential: str) -> str:
    content = redact_text(str(exc), (credential,))
    return "".join(char if char.isprintable() else " " for char in content)
