"""Provider-neutral offline fixture for normalized completed player game history."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from fifth_pick.evidence import EvidenceItem, EvidenceKind, PerformanceSample
from fifth_pick.models import Category
from fifth_pick.sources.base import MalformedPayloadError
from fifth_pick.sources.bdl_history import HistoryGameRow
from fifth_pick.sources.supporting_fixture import (
    aware_timestamp,
    decode_payload,
    fixture_evidence,
    fixture_provenance,
    payload_hash,
    require_fresh,
)


@dataclass(frozen=True, slots=True)
class CompletedPlayerGame:
    game_id: str
    played_at: datetime
    completed_at: datetime
    season: str
    opponent: str
    points: int
    rebounds: int
    assists: int
    minutes: float

    def sample(self, category: Category) -> PerformanceSample:
        values = {
            Category.POINTS: self.points,
            Category.REBOUNDS: self.rebounds,
            Category.ASSISTS: self.assists,
            Category.PRA: self.points + self.rebounds + self.assists,
            Category.REBOUNDS_ASSISTS: self.rebounds + self.assists,
        }
        if category not in values:
            raise MalformedPayloadError("history category is outside the approved five")
        return PerformanceSample(self.played_at, values[category], self.opponent, self.season)


@dataclass(frozen=True, slots=True)
class HistoryGameTiming:
    game_date: date
    played_at: datetime
    completed_at: datetime
    season: int
    opponent_id: int
    canonical_opponent: str


def reconcile_history_timing(
    rows: tuple[HistoryGameRow, ...],
    timings: Mapping[int, HistoryGameTiming],
    *,
    provider_player_id: int,
    retrieved_at: datetime,
) -> tuple[CompletedPlayerGame, ...]:
    """Join already corroborated game timing to date-only history without inventing times."""
    ids = {row.game_id for row in rows}
    if (
        retrieved_at.utcoffset() is None
        or len(ids) != len(rows)
        or any(row.provider_player_id != provider_player_id for row in rows)
        or ids != timings.keys()
    ):
        raise MalformedPayloadError("history timing does not match the requested games")
    games = []
    for row in rows:
        timing = timings[row.game_id]
        if (
            timing.game_date != row.game_date
            or timing.season != row.season
            or timing.opponent_id != row.opponent_id
            or not timing.canonical_opponent.strip()
            or timing.played_at.utcoffset() is None
            or timing.completed_at.utcoffset() is None
            or not timing.played_at < timing.completed_at < retrieved_at
        ):
            raise MalformedPayloadError("history game timing is missing or inconsistent")
        games.append(
            CompletedPlayerGame(
                str(row.game_id),
                timing.played_at,
                timing.completed_at,
                f"{row.season}-{(row.season + 1) % 100:02d}",
                timing.canonical_opponent,
                row.points,
                row.rebounds,
                row.assists,
                row.minutes,
            )
        )
    if len({game.played_at for game in games}) != len(games):
        raise MalformedPayloadError("history has ambiguous game start times")
    return tuple(sorted(games, key=lambda game: game.played_at, reverse=True))


@dataclass(frozen=True, slots=True)
class FixturePlayerHistory:
    canonical_player_id: str
    games: tuple[CompletedPlayerGame, ...]
    retrieved_at: datetime
    updated_at: datetime
    payload_sha256: str

    def evidence(
        self, *, candidate_key: str, category: Category, season: str, opponent: str
    ) -> tuple[EvidenceItem, ...]:
        """Expose available exact samples to the existing M6 counting logic."""
        if not season.strip() or not opponent.strip():
            raise MalformedPayloadError("history requires the current season and opponent")
        provenance = fixture_provenance(
            f"player-history/{self.canonical_player_id}",
            self.retrieved_at,
            self.updated_at,
            self.payload_sha256,
        )
        head_to_head = tuple(
            game for game in self.games if game.season == season and game.opponent == opponent
        )
        return tuple(
            fixture_evidence(
                candidate_key,
                kind=kind,
                provenance=provenance,
                excerpt=(
                    f"{self.canonical_player_id} {category.value} in {len(games)} fixture games"
                ),
                facts={"canonical_player_id": self.canonical_player_id},
                samples=tuple(game.sample(category) for game in games),
            )
            for kind, games in (
                (EvidenceKind.LAST_8, self.games[:8]),
                (EvidenceKind.SAME_SEASON_H2H, head_to_head),
            )
            if games
        )


def parse_history_fixture(
    body: bytes, *, player_id: str, retrieved_at: datetime, max_age: timedelta
) -> FixturePlayerHistory:
    """Accept only previously resolved canonical identities and completed appearances."""
    raw = decode_payload(body)
    if (
        not player_id.strip()
        or not isinstance(raw, dict)
        or raw.get("player_id") != player_id
        or not isinstance(raw.get("games"), list)
    ):
        raise MalformedPayloadError("history payload has no matching canonical player")
    updated_at = aware_timestamp(raw.get("updated_at"))
    require_fresh(updated_at, retrieved_at, max_age)
    seen: set[str] = set()
    starts_seen: set[datetime] = set()
    games = []
    for row in raw["games"]:
        if not isinstance(row, dict) or row.get("player_id") != player_id:
            raise MalformedPayloadError("history row is not scoped to the canonical player")
        game_id, opponent, season = row.get("game_id"), row.get("opponent"), row.get("season")
        if not all(
            isinstance(value, str) and value.strip() for value in (game_id, opponent, season)
        ):
            raise MalformedPayloadError("history row is missing game, opponent, or season")
        if game_id in seen:
            raise MalformedPayloadError("duplicate player game")
        seen.add(game_id)
        played = aware_timestamp(row.get("played_at"))
        completed = aware_timestamp(row.get("completed_at"))
        if not played < completed <= updated_at:
            raise MalformedPayloadError("game was not completed at the history update")
        if played in starts_seen:
            raise MalformedPayloadError("history has simultaneous appearances for one player")
        starts_seen.add(played)
        points, rebounds, assists = row.get("points"), row.get("rebounds"), row.get("assists")
        if not all(type(value) is int and value >= 0 for value in (points, rebounds, assists)):
            raise MalformedPayloadError("invalid player game statistic")
        minutes = row.get("minutes")
        if (
            isinstance(minutes, bool)
            or not isinstance(minutes, int | float)
            or not math.isfinite(minutes)
            or minutes <= 0
        ):
            raise MalformedPayloadError("history row lacks a played game with valid minutes")
        games.append(
            CompletedPlayerGame(
                game_id,
                played,
                completed,
                season,
                opponent,
                points,
                rebounds,
                assists,
                float(minutes),
            )
        )
    games.sort(key=lambda game: (game.played_at, game.game_id), reverse=True)
    return FixturePlayerHistory(
        player_id, tuple(games), retrieved_at, updated_at, payload_hash(body)
    )
