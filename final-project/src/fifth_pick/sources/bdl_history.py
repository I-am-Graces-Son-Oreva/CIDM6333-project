"""Bounded BALLDONTLIE history acquisition, separate from M6 evidence admission."""

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.receipts import Receipt
from fifth_pick.registry import Registry
from fifth_pick.sources.base import (
    EvidenceMode,
    LiveAuthorizationError,
    MalformedPayloadError,
    SourceError,
)
from fifth_pick.sources.supporting_fixture import decode_payload
from fifth_pick.sources.transport import Transport
from fifth_pick.storage import RunStore, collection_lock

API_KEY_ENV_VAR = "BALLDONTLIE_API_KEY"
_STATS_URL = "https://api.balldontlie.io/v1/stats"
_CURRY_CANONICAL_ID = "stephen-curry"
_CURRY_PROVIDER_ID = 115
_CURRY_VERIFIED_IDENTITY_SHA256 = "23b3529d34ff3c37184732f5c6c631bcbb0b93353ab7e0e409b1a7c9307f1612"


@dataclass(frozen=True, slots=True)
class HistoryGameRow:
    provider_player_id: int
    game_id: int
    game_date: date
    season: int
    opponent_id: int
    points: int
    rebounds: int
    assists: int
    minutes: float


@dataclass(frozen=True, slots=True)
class HistoryPage:
    games: tuple[HistoryGameRow, ...]
    next_cursor: int | None
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class HistoryRetrieval:
    cursor: int | None
    retrieved_at: datetime
    payload_sha256: str


class BdlHistoryClient:
    """Retrieve a bounded set of rows for one already corroborated provider ID."""

    def __init__(
        self,
        transport: Transport,
        *,
        environ: Mapping[str, str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._transport = transport
        self._environ = os.environ if environ is None else environ
        self._clock = (lambda: datetime.now(UTC)) if clock is None else clock

    def fetch(
        self,
        *,
        canonical_player_id: str,
        identity_reference: str,
        provider_player_id: int,
        season: int,
        before: date,
        page_limit: int,
        authorized: bool = False,
    ) -> tuple[tuple[HistoryGameRow, ...], tuple[HistoryRetrieval, ...]]:
        if authorized is not True:
            raise LiveAuthorizationError("BALLDONTLIE history requires explicit authorization")
        if getattr(self._transport, "evidence_mode", None) is not EvidenceMode.FIXTURE:
            raise LiveAuthorizationError(
                "BALLDONTLIE LIVE activation requires a verified provider identity binding"
            )
        if not isinstance(identity_reference, str) or not identity_reference.strip():
            raise LiveAuthorizationError("history requires a corroborated authorized player scope")
        _require_authorized_player(canonical_player_id)
        return self._fetch_pages(provider_player_id, season, before, page_limit)

    def _headers(self) -> dict[str, str]:
        credential = self._environ.get(API_KEY_ENV_VAR)
        if (
            not credential
            or not credential.isascii()
            or not credential.isprintable()
            or any(character.isspace() for character in credential)
        ):
            raise SourceError("BALLDONTLIE credential is missing or invalid")
        return {"Authorization": credential, "Accept": "application/json"}

    def validate_curry_history(self) -> dict[str, object]:
        """Run the two-request historical pilot for one corroborated authorized player."""
        identity = self.validate_curry_identity()
        return {
            **identity,
            **self._curry_stats(),
            "mode": "LIVE_SOURCE_VALIDATION_ONLY",
            "request_count": 2,
        }

    def validate_verified_curry_stats(self) -> dict[str, object]:
        """Probe Stats once using the owner-reported, documented identity validation."""
        _require_authorized_player(_CURRY_CANONICAL_ID)
        return {
            **self._curry_stats(),
            "mode": "STATS_VALIDATION_ONLY",
            "canonical_player_id": _CURRY_CANONICAL_ID,
            "provider_player_id": _CURRY_PROVIDER_ID,
            "identity_payload_sha256": _CURRY_VERIFIED_IDENTITY_SHA256,
            "request_count": 1,
        }

    def _curry_stats(self) -> dict[str, object]:
        now = self._clock()
        if now.utcoffset() is None:
            raise SourceError("history query time must be timezone-aware")
        before = now.astimezone(ZoneInfo("America/Chicago")).date()
        season = before.year if before.month >= 10 else before.year - 1
        games, retrievals = self._fetch_pages(_CURRY_PROVIDER_ID, season, before, 1)
        return {
            "stats_http_status": 200,
            "season": season,
            "before_chicago_date": before.isoformat(),
            "completed_appearances": len(games),
            "last_eight_dates": [game.game_date.isoformat() for game in games[:8]],
            "history_retrieved_at": retrievals[0].retrieved_at.isoformat(),
            "history_payload_sha256": retrievals[0].payload_sha256,
        }

    def validate_curry_identity(self) -> dict[str, object]:
        """Reconcile the NBA and provider IDs without requesting any player stats."""
        _require_authorized_player(_CURRY_CANONICAL_ID)
        # NBA profile 201939 and the provider's documented player 115 share a unique
        # draft slot. Verify the actual provider record before spending a second request.
        identity_url = f"https://api.balldontlie.io/v1/players/{_CURRY_PROVIDER_ID}"
        response = self._transport.get(identity_url, self._headers())
        if response.status != 200:
            raise SourceError(f"BALLDONTLIE identity returned HTTP {response.status}")
        player = _object(_object(decode_payload(response.body)).get("data"))
        if (
            _integer(player.get("id")) != _CURRY_PROVIDER_ID
            or player.get("first_name") != "Stephen"
            or player.get("last_name") != "Curry"
            or _integer(player.get("draft_year")) != 2009
            or _integer(player.get("draft_round")) != 1
            or _integer(player.get("draft_number")) != 7
        ):
            raise SourceError("BALLDONTLIE identity did not match the official draft record")
        return {
            "mode": "IDENTITY_VALIDATION_ONLY",
            "identity_http_status": response.status,
            "canonical_player_id": _CURRY_CANONICAL_ID,
            "provider_player_id": _CURRY_PROVIDER_ID,
            "official_identity_reference": "https://www.nba.com/player/201939/stephen-curry",
            "provider_identity_reference": identity_url,
            "identity_payload_sha256": hashlib.sha256(response.body).hexdigest(),
            "request_count": 1,
        }

    def probe_authentication(self) -> dict[str, object]:
        """Check credential acceptance against an endpoint included in every NBA tier."""
        response = self._transport.get("https://api.balldontlie.io/v1/teams", self._headers())
        if response.status != 200:
            raise SourceError(f"BALLDONTLIE authentication probe returned HTTP {response.status}")
        payload = _object(decode_payload(response.body))
        teams = payload.get("data")
        if not isinstance(teams, list) or not teams:
            raise MalformedPayloadError("BALLDONTLIE authentication probe has no team records")
        for team in teams:
            _integer(_object(team).get("id"))
        return {"mode": "AUTH_VALIDATION_ONLY", "http_status": 200, "request_count": 1}

    def _fetch_pages(
        self, provider_player_id: int, season: int, before: date, page_limit: int
    ) -> tuple[tuple[HistoryGameRow, ...], tuple[HistoryRetrieval, ...]]:
        _integer(provider_player_id)
        _integer(season, minimum=1946)
        if type(before) is not date or before == date.min:
            raise SourceError("history requires an exclusive calendar-date boundary")
        if type(page_limit) is not int or not 1 <= page_limit <= 10:
            raise SourceError("history page budget must be between 1 and 10")
        headers = self._headers()
        args = {
            "player_ids[]": provider_player_id,
            "seasons[]": season,
            "end_date": (before - timedelta(days=1)).isoformat(),
            "period": 0,
            "per_page": 100,
        }
        pages: list[tuple[int | None, HistoryPage]] = []
        receipts = []
        cursor = None
        requested_cursors = set()
        for _ in range(page_limit):
            if cursor in requested_cursors:
                raise SourceError("BALLDONTLIE history cursor repeated")
            requested_cursors.add(cursor)
            query = args if cursor is None else dict(args, cursor=cursor)
            response = self._transport.get(
                f"{_STATS_URL}?{urlencode(query)}",
                headers,
            )
            if response.status != 200:
                raise SourceError(f"BALLDONTLIE history returned HTTP {response.status}")
            retrieved = self._clock()
            if retrieved.utcoffset() is None:
                raise SourceError("history retrieval time must be timezone-aware")
            page = parse_history_page(response.body, {provider_player_id})
            if any(row.season != season or row.game_date >= before for row in page.games):
                raise SourceError("BALLDONTLIE history response is outside its requested scope")
            pages.append((cursor, page))
            receipts.append(HistoryRetrieval(cursor, retrieved, page.payload_sha256))
            cursor = page.next_cursor
            if cursor is None:
                break
        return complete_history(tuple(pages), max_pages=page_limit), tuple(receipts)


def _require_authorized_player(canonical_player_id: str) -> None:
    player = Registry.from_universe(load_configs().approved_universe).player_by_id(
        canonical_player_id
    )
    gate = AuthorizationGate()
    if player is None or not any(
        gate.authorize(player.player_id, grant.category, grant.direction).allowed
        for grant in player.grants
    ):
        raise LiveAuthorizationError("history requires an authorized player")


def _integer(value: object, *, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise MalformedPayloadError("history page has an invalid integer field")
    return value


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MalformedPayloadError("history page has a missing object")
    return value


def _minutes(value: object) -> float:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,3}(?::[0-5][0-9])?", value):
        raise MalformedPayloadError("history row has invalid minutes")
    minutes, _, seconds = value.partition(":")
    elapsed = int(minutes) + int(seconds or "0") / 60
    if elapsed <= 0:
        raise MalformedPayloadError("history row does not establish a played appearance")
    return elapsed


def parse_history_page(body: bytes, verified_player_ids: set[int]) -> HistoryPage:
    """Decode one bounded page for exact, already-mapped player IDs."""
    if not verified_player_ids or any(type(i) is not int or i < 1 for i in verified_player_ids):
        raise MalformedPayloadError("history requires verified positive player IDs")
    payload = _object(decode_payload(body))
    rows = payload.get("data")
    meta = _object(payload.get("meta"))
    cursor = _integer(meta["next_cursor"]) if "next_cursor" in meta else None
    if not isinstance(rows, list) or len(rows) > 100:
        raise MalformedPayloadError("history response is not one bounded page")
    games = []
    seen = set()
    for item in rows:
        row = _object(item)
        player = _integer(_object(row.get("player")).get("id"))
        if player not in verified_player_ids:
            raise MalformedPayloadError("history response contains an out-of-scope player")
        game = _object(row.get("game"))
        game_id = _integer(game.get("id"))
        if (player, game_id) in seen:
            raise MalformedPayloadError("history page contains a duplicate appearance")
        seen.add((player, game_id))
        if game.get("status_state") != "final" or game.get("postponed") is not False:
            raise MalformedPayloadError("history row does not establish a completed game")
        raw_date = game.get("date")
        try:
            if not isinstance(raw_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
                raise ValueError("expected a calendar date")
            played = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise MalformedPayloadError("history row has an invalid game date") from exc
        home = _integer(game.get("home_team_id"))
        away = _integer(game.get("visitor_team_id"))
        team = _integer(_object(row.get("team")).get("id"))
        if home == away or team not in (home, away):
            raise MalformedPayloadError("history appearance is outside the game matchup")
        games.append(
            HistoryGameRow(
                player,
                game_id,
                played,
                _integer(game.get("season")),
                away if team == home else home,
                _integer(row.get("pts"), minimum=0),
                _integer(row.get("reb"), minimum=0),
                _integer(row.get("ast"), minimum=0),
                _minutes(row.get("min")),
            )
        )
    return HistoryPage(tuple(games), cursor, hashlib.sha256(body).hexdigest())


def complete_history(
    pages: tuple[tuple[int | None, HistoryPage], ...], *, max_pages: int
) -> tuple[HistoryGameRow, ...]:
    """Reject incomplete, looping, duplicate, or over-budget page sequences."""
    if type(max_pages) is not int or not 1 <= len(pages) <= max_pages:
        raise MalformedPayloadError("history pagination exceeds its explicit bound")
    cursor = None
    cursors = set()
    games: dict[tuple[int, int], HistoryGameRow] = {}
    for requested, page in pages:
        if requested != cursor or requested in cursors:
            raise MalformedPayloadError("history pagination is inconsistent")
        cursors.add(requested)
        cursor = page.next_cursor
        for game in page.games:
            key = (game.provider_player_id, game.game_id)
            if key in games:
                raise MalformedPayloadError("history contains a duplicated game across pages")
            games[key] = game
    if cursor is not None:
        raise MalformedPayloadError("history pagination is incomplete")
    return tuple(
        sorted(games.values(), key=lambda game: (game.game_date, game.game_id), reverse=True)
    )


def verify_history_replay(
    payloads: tuple[bytes, ...],
    retrievals: tuple[HistoryRetrieval, ...],
    *,
    provider_player_id: int,
    season: int,
    before: date,
    as_of: datetime,
    max_age: timedelta,
    page_limit: int,
) -> tuple[HistoryGameRow, ...]:
    """Verify an offline archive against caller-supplied retrieval metadata."""
    _integer(provider_player_id)
    _integer(season, minimum=1946)
    if type(before) is not date or type(page_limit) is not int or not 1 <= page_limit <= 10:
        raise MalformedPayloadError("history archive has an invalid date or page budget")
    if not 1 <= len(payloads) == len(retrievals) <= page_limit:
        raise MalformedPayloadError("history archive does not match its retrieval count")
    if as_of.utcoffset() is None or max_age <= timedelta():
        raise MalformedPayloadError("history archive requires an aware freshness boundary")
    pages = []
    previous = None
    for payload, receipt in zip(payloads, retrievals, strict=True):
        observed = receipt.retrieved_at
        if (
            observed.utcoffset() is None
            or not timedelta() <= as_of - observed <= max_age
            or (previous is not None and observed < previous)
            or hashlib.sha256(payload).hexdigest() != receipt.payload_sha256
        ):
            raise MalformedPayloadError("history archive digest or retrieval time does not match")
        previous = observed
        page = parse_history_page(payload, {provider_player_id})
        if any(row.season != season or row.game_date >= before for row in page.games):
            raise MalformedPayloadError("history archive is outside its requested scope")
        pages.append((receipt.cursor, page))
    return complete_history(tuple(pages), max_pages=page_limit)


def receipt_fixture_history(
    store: RunStore,
    run_id: str,
    payloads: tuple[bytes, ...],
    retrievals: tuple[HistoryRetrieval, ...],
    *,
    phase: str,
    provider_player_id: int,
    season: int,
    before: date,
    as_of: datetime,
    max_age: timedelta,
    page_limit: int,
    verify_only: bool = False,
) -> tuple[HistoryGameRow, ...]:
    """Record an immutable replay scope without granting LIVE evidence authority."""
    if phase not in ("analysis", "t20"):
        raise MalformedPayloadError("history replay requires a recognized phase")
    rows = verify_history_replay(
        payloads,
        retrievals,
        provider_player_id=provider_player_id,
        season=season,
        before=before,
        as_of=as_of,
        max_age=max_age,
        page_limit=page_limit,
    )
    receipt = Receipt(
        as_of.isoformat(),
        "FIXTURE_HISTORY_REPLAY",
        "VALIDATED",
        str(provider_player_id),
        "synthetic-fixture",
        json.dumps(
            {
                "season": season,
                "before": before.isoformat(),
                "max_age_seconds": max_age.total_seconds(),
                "page_limit": page_limit,
                "pages": [
                    [page.cursor, page.retrieved_at.isoformat(), page.payload_sha256]
                    for page in retrievals
                ],
            },
            sort_keys=True,
        ),
        run_id,
        f"history-fixture-{phase}-{provider_player_id}",
    )
    with nullcontext() if verify_only else collection_lock(store, run_id):
        existing = [
            row for row in store.read_receipts(run_id) if row["event_key"] == receipt.event_key
        ]
        if existing and existing != [receipt.to_dict()]:
            raise MalformedPayloadError("history replay conflicts with the recorded scope")
        if not existing:
            if verify_only:
                raise MalformedPayloadError("history replay receipt is missing")
            store.append_receipt(receipt)
    return rows


def select_history_rows(
    games: tuple[HistoryGameRow, ...], *, provider_player_id: int, season: int, opponent_id: int
) -> tuple[tuple[HistoryGameRow, ...], tuple[HistoryGameRow, ...]]:
    """Select date-level samples without claiming that delivery is complete or fresh."""
    _integer(provider_player_id)
    _integer(season, minimum=1946)
    _integer(opponent_id)
    if any(game.provider_player_id != provider_player_id or game.season > season for game in games):
        raise MalformedPayloadError("history samples contain an unexpected player or season")
    if len({game.game_date for game in games}) != len(games):
        raise MalformedPayloadError("history requires unambiguous dates to order appearances")
    ordered = tuple(sorted(games, key=lambda game: game.game_date, reverse=True))
    return (
        ordered[:8],
        tuple(
            game for game in ordered if game.season == season and game.opponent_id == opponent_id
        ),
    )
