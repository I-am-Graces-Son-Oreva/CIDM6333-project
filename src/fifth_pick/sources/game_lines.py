"""Offline parser for the approved Odds API NBA sport-level spreads and totals."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from fifth_pick.evidence import EvidenceItem, EvidenceKind
from fifth_pick.sources.base import MalformedPayloadError, SourceEvent
from fifth_pick.sources.supporting_fixture import (
    aware_timestamp,
    decode_payload,
    fixture_evidence,
    fixture_provenance,
    payload_hash,
    require_fresh,
)


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
