"""Offline parser for the approved Odds API NBA sport-level spreads and totals."""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from fifth_pick.evidence import EvidenceEffect, EvidenceItem, EvidenceKind, EvidenceSignificance
from fifth_pick.models import Evidence, Provenance
from fifth_pick.receipts import Receipt
from fifth_pick.snapshots import read_receipted_snapshot_ledger, shared_slate_start
from fifth_pick.sources.base import (
    BudgetExceededError,
    EvidenceMode,
    LiveAuthorizationError,
    MalformedPayloadError,
    MissingApiKeyError,
    SourceError,
    SourceEvent,
)
from fifth_pick.sources.odds_api import API_KEY_ENV_VAR, validate_event_id
from fifth_pick.sources.quota import QuotaSnapshot, parse_quota_headers
from fifth_pick.sources.supporting_fixture import (
    aware_timestamp,
    decode_payload,
    fixture_evidence,
    fixture_provenance,
    payload_hash,
    require_fresh,
)
from fifth_pick.sources.transport import Transport
from fifth_pick.storage import RunStore, _atomic_write, collection_lock

_LINES_CREDITS = 2


@dataclass(frozen=True, slots=True)
class GameLinesGrant:
    run_id: str
    event_id: str
    bookmaker: str
    phases: tuple[str, ...]
    credit_limit: int

    def scope(self) -> str:
        validate_event_id(self.event_id)
        if (
            not re.fullmatch(r"[a-z][a-z0-9_-]*", self.bookmaker)
            or not self.phases
            or not set(self.phases) <= {"analysis", "t20"}
            or len(set(self.phases)) != len(self.phases)
            or type(self.credit_limit) is not int
            or self.credit_limit != _LINES_CREDITS * len(self.phases)
        ):
            raise LiveAuthorizationError("invalid game-lines bookmaker, phases, or credit ceiling")
        return json.dumps(
            {
                "event_id": self.event_id,
                "bookmaker": self.bookmaker,
                "phases": sorted(self.phases),
                "credit_limit": self.credit_limit,
            },
            sort_keys=True,
        )

    def receipt(self, when: datetime) -> Receipt:
        if when.utcoffset() is None:
            raise LiveAuthorizationError("game-lines authorization time must be timezone-aware")
        return Receipt(
            when.isoformat(),
            "LIVE_GAME_LINES_GRANT",
            "AUTHORIZED",
            self.event_id,
            "fifth-pick",
            self.scope(),
            self.run_id,
            "game-lines-live-grant",
        )


def record_game_lines_grant(store: RunStore, grant: GameLinesGrant, when: datetime) -> None:
    """Record Joseph's exact scope without opening a provider connection."""
    receipt = grant.receipt(when)
    with collection_lock(store, grant.run_id):
        existing = [
            row
            for row in store.read_receipts(grant.run_id)
            if row["event_key"] == receipt.event_key
        ]
        if existing:
            original_at = aware_timestamp(existing[0]["timestamp"])
            if len(existing) != 1 or existing[0] != grant.receipt(original_at).to_dict():
                raise LiveAuthorizationError("game-lines grant differs from the recorded scope")
        else:
            store.append_receipt(receipt)


@dataclass(frozen=True, slots=True)
class GameLinesAcquisition:
    event_id: str
    bookmaker: str
    phase: str
    retrieved_at: datetime
    total: float
    home_spread: float
    payload_sha256: str


def acquire_game_lines(
    store: RunStore,
    grant: GameLinesGrant,
    *,
    transport: Transport,
    phase: str,
    event: SourceEvent,
    quota_before: QuotaSnapshot,
    max_age: timedelta,
    authorized: bool = False,
    environ: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> GameLinesAcquisition:
    """Execute one approved supporting request; reservations survive failure or interruption."""
    if (
        authorized is not True
        or getattr(transport, "evidence_mode", None) is not EvidenceMode.LIVE
        or grant.event_id != event.event_id
        or phase not in grant.phases
    ):
        raise LiveAuthorizationError("game lines require exact event, bookmaker and phase approval")
    if (
        quota_before.remaining is None
        or quota_before.used is None
        or quota_before.used < 0
        or quota_before.remaining < _LINES_CREDITS
    ):
        raise BudgetExceededError("game lines lack a sufficient verified credit budget")
    _, url = _request_scope(event, phase, grant.bookmaker)
    key = f"game-lines-live-{phase}-{event.event_id}"
    credential = (os.environ if environ is None else environ).get(API_KEY_ENV_VAR)
    if (
        not credential
        or not credential.isascii()
        or not credential.isprintable()
        or any(character.isspace() for character in credential)
    ):
        raise MissingApiKeyError("game lines require an environment credential")
    with collection_lock(store, grant.run_id):
        requested_at = clock()
        slate_start = shared_slate_start(read_receipted_snapshot_ledger(store, grant.run_id))
        target = (slate_start or event.commence_time) - timedelta(minutes=20)
        latest_review = target + timedelta(minutes=5)
        in_window = requested_at.utcoffset() is not None and (
            requested_at < target
            if phase == "analysis"
            else target <= requested_at <= latest_review
        )
        if not in_window or max_age <= timedelta():
            raise LiveAuthorizationError("game-lines request is outside the authorized timing")
        receipts = store.read_receipts(grant.run_id)
        grants = [row for row in receipts if row["event_key"] == "game-lines-live-grant"]
        if len(grants) != 1:
            raise LiveAuthorizationError("a previously recorded game-lines grant is required")
        granted_at = aware_timestamp(grants[0]["timestamp"])
        if granted_at > requested_at or grants[0] != grant.receipt(granted_at).to_dict():
            raise LiveAuthorizationError("game-lines grant differs from the recorded scope")
        reservations = [row for row in receipts if row["event"] == "LIVE_GAME_LINES_RESERVED"]
        if any(row["event_key"] == key for row in reservations) or (
            (len(reservations) + 1) * _LINES_CREDITS > grant.credit_limit
        ):
            raise BudgetExceededError("game-lines phase was already attempted or budget exhausted")
        store.append_receipt(
            Receipt(
                requested_at.isoformat(),
                "LIVE_GAME_LINES_RESERVED",
                "ATTEMPTED",
                event.event_id,
                "the-odds-api",
                url,
                grant.run_id,
                key,
            ),
            secrets=(credential,),
        )
        response = transport.get(url, {"x-api-key": credential, "Accept": "application/json"})
        observed_at = clock()
        closes = target if phase == "analysis" else latest_review
        if observed_at.utcoffset() is None or not requested_at <= observed_at <= closes:
            raise MalformedPayloadError("game-lines response arrived outside the authorized timing")
        digest = payload_hash(response.body)
        store.append_receipt(
            Receipt(
                observed_at.isoformat(),
                "LIVE_GAME_LINES_RESPONSE",
                f"HTTP_{response.status}",
                event.event_id,
                "the-odds-api",
                digest,
                grant.run_id,
                f"{key}-response",
            )
        )
        if response.status != 200:
            raise SourceError(f"game-lines request returned HTTP {response.status}")
        after = parse_quota_headers(response.headers)
        if (
            after.last != _LINES_CREDITS
            or after.remaining != quota_before.remaining - _LINES_CREDITS
            or after.used != quota_before.used + _LINES_CREDITS
        ):
            raise BudgetExceededError("game-lines credit counters do not reconcile")
        lines = _complete_lines(response.body, event, grant.bookmaker, observed_at, max_age)
        assert lines.total is not None and lines.home_spread is not None
        if credential.encode() in response.body:
            raise MalformedPayloadError("game-lines payload contains credential material")
        path = store.run_directory(grant.run_id) / f"{key}.json"
        if path.exists() or path.is_symlink():
            raise MalformedPayloadError("game-lines payload path is already occupied")
        _atomic_write(path, response.body)
        store.append_receipt(
            Receipt(
                observed_at.isoformat(),
                "LIVE_GAME_LINES_VALIDATED",
                "VALIDATED",
                event.event_id,
                "the-odds-api",
                json.dumps(
                    {
                        "sha256": digest,
                        "charged": after.last,
                        "max_age_seconds": max_age.total_seconds(),
                    },
                    sort_keys=True,
                ),
                grant.run_id,
                f"{key}-validated",
            )
        )
    return GameLinesAcquisition(
        event.event_id,
        grant.bookmaker,
        phase,
        observed_at,
        lines.total,
        lines.home_spread,
        digest,
    )


def read_live_game_lines(
    store: RunStore,
    run_id: str,
    event: SourceEvent,
    *,
    phase: str,
    as_of: datetime,
    max_age: timedelta | None = None,
) -> tuple[FixtureGameLines, str] | None:
    """Revalidate exact stored bytes against the approved LIVE request and receipt chain."""
    validate_event_id(event.event_id)
    if phase not in ("analysis", "t20"):
        raise MalformedPayloadError("unknown game-lines phase")
    key = f"game-lines-live-{phase}-{event.event_id}"
    role_keys = ("game-lines-live-grant", key, f"{key}-response", f"{key}-validated")
    rows = [row for row in store.read_receipts(run_id) if row["event_key"] in role_keys]
    if not any(row["event_key"] != role_keys[0] for row in rows):
        return None
    if [row["event_key"] for row in rows] != list(role_keys):
        raise MalformedPayloadError("game-lines receipt chain is incomplete")
    grant_row, request, response, validation = rows
    try:
        scope = json.loads(grant_row["reason"] or "")
        grant = GameLinesGrant(
            run_id,
            event.event_id,
            scope["bookmaker"],
            tuple(scope["phases"]),
            scope["credit_limit"],
        )
        evidence = json.loads(validation["reason"] or "")
        seconds = evidence["max_age_seconds"]
        if type(seconds) not in (float, int) or not math.isfinite(seconds):
            raise ValueError
        bound = timedelta(seconds=seconds)
        digest = evidence["sha256"]
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise MalformedPayloadError("game-lines receipt metadata is invalid") from exc
    slate_start = shared_slate_start(read_receipted_snapshot_ledger(store, run_id))
    requested = aware_timestamp(request["timestamp"])
    retrieved = aware_timestamp(response["timestamp"])
    granted = aware_timestamp(grant_row["timestamp"])
    reference = _request_scope(event, phase, grant.bookmaker)[1]
    if (
        as_of.utcoffset() is None
        or not granted <= requested <= retrieved <= as_of
        or as_of >= (slate_start or event.commence_time)
        or phase not in grant.phases
        or bound <= timedelta()
        or grant_row != grant.receipt(granted).to_dict()
        or request
        != Receipt(
            requested.isoformat(),
            "LIVE_GAME_LINES_RESERVED",
            "ATTEMPTED",
            event.event_id,
            "the-odds-api",
            reference,
            run_id,
            key,
        ).to_dict()
        or response
        != Receipt(
            retrieved.isoformat(),
            "LIVE_GAME_LINES_RESPONSE",
            "HTTP_200",
            event.event_id,
            "the-odds-api",
            digest,
            run_id,
            f"{key}-response",
        ).to_dict()
        or validation
        != Receipt(
            retrieved.isoformat(),
            "LIVE_GAME_LINES_VALIDATED",
            "VALIDATED",
            event.event_id,
            "the-odds-api",
            json.dumps(
                {
                    "sha256": digest,
                    "charged": _LINES_CREDITS,
                    "max_age_seconds": seconds,
                },
                sort_keys=True,
            ),
            run_id,
            f"{key}-validated",
        ).to_dict()
    ):
        raise MalformedPayloadError("game-lines receipt does not match event, grant, or phase")
    target = (slate_start or event.commence_time) - timedelta(minutes=20)
    if phase == "analysis" and not requested < target:
        raise MalformedPayloadError("game-lines analysis phase is out of window")
    if phase == "t20" and not target <= requested <= retrieved <= target + timedelta(minutes=5):
        raise MalformedPayloadError("game-lines T-20 phase is out of window")
    path = store.run_directory(run_id) / f"{key}.json"
    if path.is_symlink():
        raise MalformedPayloadError("game-lines archive path is invalid")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise MalformedPayloadError("game-lines archive is missing") from exc
    if payload_hash(payload) != digest:
        raise MalformedPayloadError("game-lines archive digest does not match its receipt")
    lines = _complete_lines(payload, event, grant.bookmaker, retrieved, bound)
    for updated in (lines.total_updated_at, lines.spread_updated_at):
        if updated is None:
            raise MalformedPayloadError("game-lines source time is missing")
        require_fresh(updated, as_of, bound if max_age is None else min(max_age, bound))
    return lines, reference


def live_game_line_items(
    store: RunStore,
    run_id: str,
    *,
    event: SourceEvent,
    candidate_key: str,
    phase: str,
    as_of: datetime,
) -> tuple[EvidenceItem, ...]:
    """Construct neutral facts from the authorized durable response."""
    result = read_live_game_lines(store, run_id, event, phase=phase, as_of=as_of)
    if result is None:
        return ()
    lines, reference = result
    items = []
    for kind, name, value, updated in (
        (EvidenceKind.GAME_TOTAL, "total", lines.total, lines.total_updated_at),
        (EvidenceKind.POINT_SPREAD, "spread", lines.home_spread, lines.spread_updated_at),
    ):
        assert value is not None and updated is not None
        excerpt = f"{lines.bookmaker_key} {name} {value} for event {event.event_id}"
        items.append(
            EvidenceItem(
                evidence_id=f"game-lines-{phase}-{kind.value}",
                candidate_key=candidate_key,
                kind=kind,
                evidence=Evidence(
                    excerpt,
                    Provenance(
                        "the-odds-api",
                        lines.retrieved_at,
                        updated,
                        "the-odds-api:game-lines",
                        reference,
                        lines.payload_sha256,
                    ),
                    excerpt,
                ),
                evidence_mode=EvidenceMode.LIVE,
                effect=EvidenceEffect.NEUTRAL,
                significance=EvidenceSignificance.MEANINGFUL,
                facts={name: value, "event_id": event.event_id, "bookmaker": lines.bookmaker_key},
            )
        )
    return tuple(items)


def _request_scope(event: SourceEvent, phase: str, bookmaker: str) -> tuple[str, str]:
    validate_event_id(event.event_id)
    if phase not in ("analysis", "t20") or not re.fullmatch(r"[a-z][a-z0-9_-]*", bookmaker):
        raise MalformedPayloadError("invalid game-lines phase or bookmaker scope")
    query = urlencode(
        {"eventIds": event.event_id, "bookmakers": bookmaker, "markets": "spreads,totals"}
    )
    return (
        f"game-lines-fixture-{phase}-{event.event_id}",
        f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds?{query}",
    )


def _complete_lines(
    body: bytes, event: SourceEvent, bookmaker: str, observed_at: datetime, max_age: timedelta
) -> FixtureGameLines:
    if observed_at.utcoffset() is None or observed_at >= event.commence_time:
        raise MalformedPayloadError("game-lines replay requires a pre-tipoff observation")
    rows = parse_game_lines_fixture(
        body,
        expected_events=(event,),
        retrieved_at=observed_at,
        max_age=max_age,
        bookmaker_keys=frozenset({bookmaker}),
        exact_scope=True,
    )
    if len(rows) != 1 or rows[0].total is None or rows[0].home_spread is None:
        raise MalformedPayloadError("game-lines replay requires exact spread and total coverage")
    return rows[0]


def replay_game_lines_request(
    store: RunStore,
    run_id: str,
    *,
    transport: Transport,
    event: SourceEvent,
    phase: str,
    bookmaker: str,
    observed_at: datetime,
    max_age: timedelta,
) -> FixtureGameLines:
    """Replay one bounded game-lines request, retaining its exact payload digest."""
    if getattr(transport, "evidence_mode", None) is not EvidenceMode.FIXTURE:
        raise LiveAuthorizationError("game-lines replay requires a fixture transport")
    base_key, url = _request_scope(event, phase, bookmaker)
    if observed_at.utcoffset() is None or observed_at >= event.commence_time:
        raise MalformedPayloadError("game-lines replay requires a pre-tipoff observation")
    with collection_lock(store, run_id):
        if any(row["event_key"] == base_key for row in store.read_receipts(run_id)):
            raise MalformedPayloadError("game-lines phase already attempted")
        store.append_receipt(
            Receipt(
                observed_at.isoformat(),
                "FIXTURE_GAME_LINES_REQUEST",
                "ATTEMPTED",
                event.event_id,
                "synthetic-fixture",
                url,
                run_id,
                base_key,
            )
        )
        response = transport.get(url, {"Accept": "application/json"})
        if response.status != 200:
            raise MalformedPayloadError(f"game-lines replay returned HTTP {response.status}")
        lines = _complete_lines(response.body, event, bookmaker, observed_at, max_age)
        store.append_receipt(
            Receipt(
                observed_at.isoformat(),
                "FIXTURE_GAME_LINES_RESPONSE",
                "VALIDATED",
                event.event_id,
                "synthetic-fixture",
                lines.payload_sha256,
                run_id,
                f"{base_key}-response",
            )
        )
    return lines


def verify_game_lines_replay(
    store: RunStore,
    run_id: str,
    body: bytes,
    *,
    event: SourceEvent,
    phase: str,
    bookmaker: str,
    max_age: timedelta,
    as_of: datetime,
) -> FixtureGameLines:
    """Revalidate replayed bytes against both scoped fixture receipts."""
    key, url = _request_scope(event, phase, bookmaker)
    response_key = f"{key}-response"
    matched = tuple(
        row for row in store.read_receipts(run_id) if row["event_key"] in (key, response_key)
    )
    if len(matched) != 2:
        raise MalformedPayloadError("game-lines replay receipts are incomplete")
    request, response = matched
    observed_at = aware_timestamp(request["timestamp"])
    timestamp = observed_at.isoformat()
    expected_request = Receipt(
        timestamp,
        "FIXTURE_GAME_LINES_REQUEST",
        "ATTEMPTED",
        event.event_id,
        "synthetic-fixture",
        url,
        run_id,
        key,
    )
    expected_response = Receipt(
        timestamp,
        "FIXTURE_GAME_LINES_RESPONSE",
        "VALIDATED",
        event.event_id,
        "synthetic-fixture",
        payload_hash(body),
        run_id,
        response_key,
    )
    if request != expected_request.to_dict() or response != expected_response.to_dict():
        raise MalformedPayloadError("game-lines replay receipts do not match the payload and scope")
    if as_of.utcoffset() is None or not observed_at <= as_of < event.commence_time:
        raise MalformedPayloadError("game-lines use must follow retrieval and precede tipoff")
    lines = _complete_lines(body, event, bookmaker, observed_at, max_age)
    for updated_at in (lines.total_updated_at, lines.spread_updated_at):
        if updated_at is None:
            raise MalformedPayloadError("game-lines source time is missing")
        require_fresh(updated_at, as_of, max_age)
    return lines


@dataclass(frozen=True, slots=True)
class FixtureGameLines:
    """One bookmaker's two market values for a verified fixture event."""

    event_id: str
    bookmaker_key: str
    home_team: str
    away_team: str
    total: float | None
    home_spread: float | None
    retrieved_at: datetime
    total_updated_at: datetime | None
    spread_updated_at: datetime | None
    payload_sha256: str

    def evidence(self, *, candidate_key: str) -> tuple[EvidenceItem, ...]:
        def provenance(updated_at: datetime):
            return fixture_provenance(
                f"nba-lines/{self.event_id}/{self.bookmaker_key}",
                self.retrieved_at,
                updated_at,
                self.payload_sha256,
            )

        items = []
        facts = {"event_id": self.event_id, "bookmaker": self.bookmaker_key}
        if self.total is not None and self.total_updated_at is not None:
            items.append(
                fixture_evidence(
                    candidate_key,
                    kind=EvidenceKind.GAME_TOTAL,
                    provenance=provenance(self.total_updated_at),
                    excerpt=f"{self.event_id} game total {self.total}",
                    facts={**facts, "total": self.total},
                )
            )
        if self.home_spread is not None and self.spread_updated_at is not None:
            items.append(
                fixture_evidence(
                    candidate_key,
                    kind=EvidenceKind.POINT_SPREAD,
                    provenance=provenance(self.spread_updated_at),
                    excerpt=f"{self.event_id} {self.home_team} home spread {self.home_spread}",
                    facts={**facts, "home_team": self.home_team, "spread": self.home_spread},
                )
            )
        return tuple(items)


def _market_points(market: dict, expected: set[str]) -> dict[str, float]:
    points: dict[str, float] = {}
    outcomes = market.get("outcomes")
    if not isinstance(outcomes, list):
        raise MalformedPayloadError("game lines require two market outcomes")
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            raise MalformedPayloadError("invalid game-line outcome")
        name, point = outcome.get("name"), outcome.get("point")
        if (
            not isinstance(name, str)
            or name not in expected
            or name in points
            or isinstance(point, bool)
            or not isinstance(point, int | float)
            or not math.isfinite(point)
        ):
            raise MalformedPayloadError("unexpected, duplicate, or invalid game-line outcome")
        points[name] = float(point)
    if points.keys() != expected:
        raise MalformedPayloadError("game line missing a side")
    return points


def parse_game_lines_fixture(
    body: bytes,
    *,
    expected_events: tuple[SourceEvent, ...],
    retrieved_at: datetime,
    max_age: timedelta,
    bookmaker_keys: frozenset[str],
    exact_scope: bool = False,
) -> tuple[FixtureGameLines, ...]:
    """Decode exact scoped NBA games and bookmakers, keeping their lines separate."""
    raw = decode_payload(body)
    if not isinstance(raw, list) or not bookmaker_keys:
        raise MalformedPayloadError("game lines require a response array and bookmaker scope")
    expected = {event.event_id: event for event in expected_events}
    if len(expected) != len(expected_events):
        raise MalformedPayloadError("duplicate expected event")
    events_seen: set[str] = set()
    digest = payload_hash(body)
    records = []
    for row in raw:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise MalformedPayloadError("invalid game-lines event")
        event = expected.get(row["id"])
        if event is None:
            if exact_scope:
                raise MalformedPayloadError("game-lines response returned an unrequested event")
            continue
        if (
            event.event_id in events_seen
            or row.get("sport_key") != "basketball_nba"
            or row.get("home_team") != event.home_team
            or row.get("away_team") != event.away_team
            or aware_timestamp(row.get("commence_time")) != event.commence_time
        ):
            raise MalformedPayloadError("conflicting game-lines event identity")
        events_seen.add(event.event_id)
        bookmakers = row.get("bookmakers")
        if not isinstance(bookmakers, list):
            raise MalformedPayloadError("invalid game-lines bookmaker list")
        books_seen: set[str] = set()
        for book in bookmakers:
            if not isinstance(book, dict) or not isinstance(book.get("key"), str):
                raise MalformedPayloadError("invalid game-lines bookmaker")
            key = book["key"]
            if key not in bookmaker_keys:
                if exact_scope:
                    raise MalformedPayloadError(
                        "game-lines response returned an unrequested bookmaker"
                    )
                continue
            markets = book.get("markets")
            if key in books_seen or not isinstance(markets, list):
                raise MalformedPayloadError("duplicate bookmaker or invalid market list")
            books_seen.add(key)
            updated = aware_timestamp(book.get("last_update"))
            require_fresh(updated, retrieved_at, max_age)
            if retrieved_at >= event.commence_time:
                raise MalformedPayloadError("pregame lines were retrieved after tipoff")
            values: dict[str, float] = {}
            updates: dict[str, datetime] = {}
            for market in markets:
                if not isinstance(market, dict) or not isinstance(market.get("key"), str):
                    raise MalformedPayloadError("invalid game-lines market")
                market_key = market["key"]
                if market_key not in ("spreads", "totals"):
                    if exact_scope:
                        raise MalformedPayloadError(
                            "game-lines response returned an unrequested market"
                        )
                    continue
                if market_key in values:
                    raise MalformedPayloadError("duplicate game-lines market")
                source_time = (
                    aware_timestamp(market["last_update"]) if "last_update" in market else updated
                )
                require_fresh(source_time, retrieved_at, max_age)
                updates[market_key] = source_time
                if market_key == "totals":
                    points = _market_points(market, {"Over", "Under"})
                    if points["Over"] <= 0 or points["Over"] != points["Under"]:
                        raise MalformedPayloadError("inconsistent total market sides")
                    values[market_key] = points["Over"]
                else:
                    points = _market_points(market, {event.home_team, event.away_team})
                    if points[event.home_team] != -points[event.away_team]:
                        raise MalformedPayloadError("inconsistent spread market sides")
                    values[market_key] = points[event.home_team]
            if values:
                records.append(
                    FixtureGameLines(
                        event.event_id,
                        key,
                        event.home_team,
                        event.away_team,
                        values.get("totals"),
                        values.get("spreads"),
                        retrieved_at,
                        updates.get("totals"),
                        updates.get("spreads"),
                        digest,
                    )
                )
    return tuple(records)
