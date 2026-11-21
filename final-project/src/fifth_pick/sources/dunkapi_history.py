"""Decode supplied DunkAPI payloads offline. Decoded records carry no LIVE authority."""

import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from fifth_pick.sources.base import MalformedPayloadError
from fifth_pick.sources.supporting_fixture import aware_timestamp, payload_hash

_MAX_BODY_BYTES = 1_048_576


class Participation(StrEnum):
    PLAYED = "PLAYED"
    DNP = "DNP"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class HistoryScope:
    player_id: str
    season_end_year: int
    first_date: date
    last_date: date
    page_size: int
    max_pages: int

    def __post_init__(self) -> None:
        _id(self.player_id)
        if (
            type(self.season_end_year) is not int
            or not 1947 <= self.season_end_year <= 9999
            or type(self.first_date) is not date
            or type(self.last_date) is not date
            or not self.season_end_year - 1
            <= self.first_date.year
            <= self.last_date.year
            <= self.season_end_year
            or self.first_date > self.last_date
            or type(self.page_size) is not int
            or not 1 <= self.page_size <= 100
            or type(self.max_pages) is not int
            or self.max_pages < 1
        ):
            raise MalformedPayloadError("invalid DunkAPI history request scope")

    @property
    def season(self) -> str:
        return f"{self.season_end_year - 1}-{self.season_end_year % 100:02d}"


@dataclass(frozen=True, slots=True)
class DunkPlayer:
    player_id: str
    name: str
    team: str
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class PlayerStats:
    points: int
    rebounds: int
    assists: int
    minutes: float


@dataclass(frozen=True, slots=True)
class ReportedMetadata:
    completed_at: datetime | None
    source_updated_at: datetime | None
    corrected_at: datetime | None
    revision_id: str | int | None


@dataclass(frozen=True, slots=True)
class DunkGameRow:
    player_id: str
    game_id: str
    game_date: date
    season: str
    season_end_year: int
    opponent: str
    home: bool
    participation: Participation
    stats: PlayerStats | None
    explicitly_final: bool
    metadata: ReportedMetadata


@dataclass(frozen=True, slots=True)
class DunkHistory:
    games: tuple[DunkGameRow, ...]
    payload_sha256: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DunkBoxScore:
    game_id: str
    scheduled_start_at: datetime | None
    metadata: ReportedMetadata
    payload_sha256: str


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MalformedPayloadError("expected a DunkAPI object")
    return value


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise MalformedPayloadError("duplicate DunkAPI JSON field")
    return fields


def _reject_constant(_: str) -> None:
    raise MalformedPayloadError("invalid DunkAPI JSON constant")


def _data(body: bytes) -> dict[str, object]:
    if not isinstance(body, bytes) or len(body) > _MAX_BODY_BYTES:
        raise MalformedPayloadError("invalid DunkAPI response size or type")
    try:
        envelope = json.loads(
            body, object_pairs_hook=_unique_fields, parse_constant=_reject_constant
        )
    except (ValueError, RecursionError) as exc:
        raise MalformedPayloadError("invalid DunkAPI response JSON") from exc
    data = _object(_object(envelope).get("data"))
    if data.get("league", "nba") != "nba":
        raise MalformedPayloadError("DunkAPI response does not match NBA scope")
    return data


def _rows(value: object, limit: int) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or len(value) > limit:
        raise MalformedPayloadError("invalid DunkAPI row collection")
    return tuple(_object(row) for row in value)


def _id(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,20}", value) or int(value) == 0:
        raise MalformedPayloadError("invalid DunkAPI identifier")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or not value.isprintable():
        raise MalformedPayloadError("invalid DunkAPI text field")
    return value


def _team_code(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{2,4}", value):
        raise MalformedPayloadError("invalid DunkAPI team abbreviation")
    return value


def _date(value: object) -> date:
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise MalformedPayloadError("invalid DunkAPI game date")


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise MalformedPayloadError("invalid DunkAPI integer")
    return value


def _minutes(value: object) -> float:
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,3}:[0-5][0-9]", value):
        minutes, seconds = value.split(":")
        return int(minutes) + int(seconds) / 60
    if (isinstance(value, int | float) and not isinstance(value, bool)) or (
        isinstance(value, str) and re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]+)?", value)
    ):
        try:
            result = float(value)
        except (ValueError, OverflowError):
            pass
        else:
            if math.isfinite(result) and result >= 0:
                return result
    raise MalformedPayloadError("invalid DunkAPI minutes")


def _performance(row: dict[str, object]) -> tuple[Participation, PlayerStats | None]:
    flag = row.get("did_not_play")
    if flag is not None and type(flag) is not bool:
        raise MalformedPayloadError("invalid DunkAPI participation flag")
    counts = tuple(
        None if row.get(key) is None else _count(row[key]) for key in ("pts", "reb", "ast")
    )
    minutes = None if row.get("minutes") is None else _minutes(row["minutes"])
    if flag is True:
        if any(counts) or minutes:
            raise MalformedPayloadError("DunkAPI DNP contradicts recorded performance")
        return Participation.DNP, None
    points, rebounds, assists = counts
    participation = Participation.PLAYED if flag is False else Participation.UNKNOWN
    if all(value is not None for value in (*counts, minutes)):
        assert points is not None and rebounds is not None and assists is not None
        assert minutes is not None
        if minutes > 0:
            return participation, PlayerStats(points, rebounds, assists, minutes)
    if flag is False or any(counts) or minutes:
        raise MalformedPayloadError("DunkAPI row has incomplete or contradictory performance")
    return participation, None


def _optional_timestamp(row: dict[str, object], *keys: str) -> datetime | None:
    values = {aware_timestamp(row[key]) for key in keys if row.get(key) is not None}
    if len(values) > 1:
        raise MalformedPayloadError("DunkAPI timestamps contradict each other")
    return next(iter(values), None)


def _metadata(row: dict[str, object]) -> ReportedMetadata:
    revision = row.get("revision_id")
    if revision is not None:
        revision = _count(revision) if type(revision) is int else _text(revision)
    return ReportedMetadata(
        _optional_timestamp(row, "completed_at", "ended_at", "finished_at"),
        _optional_timestamp(row, "source_updated_at", "updated_at"),
        _optional_timestamp(row, "corrected_at"),
        revision,
    )


def _regular_season(value: object) -> bool:
    return (type(value) is int and value == 2) or value == "regular"


def decode_identity(
    body: bytes, *, player_id: str, name: str, team_labels: tuple[str, ...], limit: int = 10
) -> DunkPlayer:
    """Check search results against explicit provider identity expectations."""
    _id(player_id)
    _text(name)
    if type(limit) is not int or not 1 <= limit <= 100 or not team_labels:
        raise MalformedPayloadError("invalid DunkAPI player search scope")
    for label in team_labels:
        _text(label)
    data = _data(body)
    player_ids = set()
    matches = []
    for row in _rows(data.get("players"), limit):
        key = _id(row.get("player_id"))
        label = _text(row.get("name"))
        if key in player_ids:
            raise MalformedPayloadError("duplicate DunkAPI player identifier")
        player_ids.add(key)
        if label == name:
            matches.append((key, _text(row.get("team"))))
    if len(matches) != 1 or matches[0][0] != player_id or matches[0][1] not in team_labels:
        raise MalformedPayloadError("DunkAPI identity does not match the expected player")
    return DunkPlayer(player_id, name, matches[0][1], payload_hash(body))


def _history_row(row: dict[str, object], scope: HistoryScope) -> DunkGameRow:
    game_date = _date(row.get("date"))
    status = row.get("status")
    home = row.get("home")
    if (
        ("player_id" in row and row["player_id"] != scope.player_id)
        or row.get("league", "nba") != "nba"
        or _count(row.get("season")) != scope.season_end_year
        or not _regular_season(row.get("season_type"))
        or not scope.first_date <= game_date <= scope.last_date
        or type(home) is not bool
        or ("status" in row and status != "final")
        or ("result" in row and row["result"] not in ("W", "L"))
        or (status is None and row.get("result") not in ("W", "L"))
    ):
        raise MalformedPayloadError("DunkAPI game is outside the requested regular-season scope")
    participation, stats = _performance(row)
    return DunkGameRow(
        scope.player_id,
        _id(row.get("game_id")),
        game_date,
        scope.season,
        scope.season_end_year,
        _team_code(row.get("opponent")),
        home,
        participation,
        stats,
        status == "final",
        _metadata(row),
    )


def decode_history(pages: tuple[tuple[int, bytes], ...], scope: HistoryScope) -> DunkHistory:
    """Validate a caller-supplied, terminal offset chain without fetching pages."""
    if not 1 <= len(pages) <= scope.max_pages:
        raise MalformedPayloadError("DunkAPI history exceeds its page scope")
    expected: int | None = 0
    games: dict[str, DunkGameRow] = {}
    digests = []
    for offset, body in pages:
        if _count(offset) != expected:
            raise MalformedPayloadError("DunkAPI history offsets are inconsistent")
        data = _data(body)
        rows = _rows(data.get("games"), scope.page_size)
        if (
            data.get("player_id") != scope.player_id
            or _count(data.get("count")) != len(rows)
            or "next_offset" not in data
        ):
            raise MalformedPayloadError("DunkAPI history page does not match the request")
        expected = None
        if data["next_offset"] is not None:
            expected = _count(data["next_offset"])
            if not rows or expected != offset + len(rows):
                raise MalformedPayloadError("DunkAPI history next offset is inconsistent")
        for raw in rows:
            row = _history_row(raw, scope)
            if row.game_id in games:
                raise MalformedPayloadError("duplicate DunkAPI history game")
            games[row.game_id] = row
        digests.append(payload_hash(body))
    if expected is not None:
        raise MalformedPayloadError("DunkAPI history pagination is incomplete")
    return DunkHistory(
        tuple(
            sorted(games.values(), key=lambda game: (game.game_date, game.game_id), reverse=True)
        ),
        tuple(digests),
    )


def verify_box_score(body: bytes, row: DunkGameRow, *, team_id: str) -> DunkBoxScore:
    """Cross-check a final box score for the exact already-decoded appearance."""
    _id(team_id)
    data = _data(body)
    game = _object(data.get("game"))
    own_side, other_side = ("home", "away") if row.home else ("away", "home")
    team, opponent = _object(game.get(own_side)), _object(game.get(other_side))
    players = _rows(data.get("players"), 100)
    ids = [_id(player.get("player_id")) for player in players]
    if (
        len(set(ids)) != len(ids)
        or row.player_id not in ids
        or _id(game.get("game_id")) != row.game_id
        or game.get("league", "nba") != "nba"
        or _count(game.get("season")) != row.season_end_year
        or ("season_type" in game and not _regular_season(game["season_type"]))
        or _date(game.get("date")) != row.game_date
        or game.get("status") != "final"
        or _id(team.get("team_id")) != team_id
        or _team_code(opponent.get("abbrev")) != row.opponent
        or ("team_id" in opponent and _id(opponent["team_id"]) == team_id)
        or ("abbrev" in team and _team_code(team["abbrev"]) == row.opponent)
    ):
        raise MalformedPayloadError("DunkAPI box score game or teams disagree with history")
    player = players[ids.index(row.player_id)]
    if (
        _id(player.get("team_id")) != team_id
        or row.participation is Participation.UNKNOWN
        or _performance(player) != (row.participation, row.stats)
    ):
        raise MalformedPayloadError(
            "DunkAPI box score participation or stats disagree with history"
        )
    metadata = _metadata(game)
    if (
        row.metadata.completed_at is not None
        and metadata.completed_at is not None
        and row.metadata.completed_at != metadata.completed_at
    ):
        raise MalformedPayloadError("DunkAPI box score completion disagrees with history")
    return DunkBoxScore(
        row.game_id, _optional_timestamp(game, "starts_at"), metadata, payload_hash(body)
    )
