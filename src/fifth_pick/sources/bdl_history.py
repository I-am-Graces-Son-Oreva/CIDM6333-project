"""Bounded BALLDONTLIE history acquisition, separate from M6 evidence admission."""

import hashlib
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode

from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.registry import Registry
from fifth_pick.sources.base import (
    EvidenceMode,
    LiveAuthorizationError,
    MalformedPayloadError,
    SourceError,
)
from fifth_pick.sources.supporting_fixture import decode_payload
from fifth_pick.sources.transport import Transport

API_KEY_ENV_VAR = "BALLDONTLIE_API_KEY"
_STATS_URL = "https://api.balldontlie.io/v1/stats"


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
        player = Registry.from_universe(load_configs().approved_universe).player_by_id(
            canonical_player_id
        )
        gate = AuthorizationGate()
        if (
            player is None
            or not isinstance(identity_reference, str)
            or not identity_reference.strip()
            or not any(
                gate.authorize(player.player_id, grant.category, grant.direction).allowed
                for grant in player.grants
            )
        ):
            raise LiveAuthorizationError("history requires a corroborated authorized player scope")
        _integer(provider_player_id)
        _integer(season, minimum=1946)
        if type(before) is not date or before == date.min:
            raise SourceError("history requires an exclusive calendar-date boundary")
        if type(page_limit) is not int or not 1 <= page_limit <= 10:
            raise SourceError("history page budget must be between 1 and 10")
        credential = self._environ.get(API_KEY_ENV_VAR)
        if (
            not credential
            or not credential.isascii()
            or not credential.isprintable()
            or any(character.isspace() for character in credential)
        ):
            raise SourceError("BALLDONTLIE credential is missing or invalid")
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
                {"Authorization": credential, "Accept": "application/json"},
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
