"""Offline wire contract for the proposed BALLDONTLIE player history source.

This parser does not retrieve data or produce M6 evidence. Source approval, verified
identity mappings, full pagination, and timestamp provenance remain required.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date

from fifth_pick.sources.base import MalformedPayloadError
from fifth_pick.sources.supporting_fixture import decode_payload


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
