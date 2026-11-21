"""Provider-neutral offline join of history rows and independently supplied game facts."""

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fifth_pick.sources.base import MalformedPayloadError
from fifth_pick.sources.player_history import CompletedPlayerGame


class AppearanceStats(Protocol):
    @property
    def points(self) -> int: ...
    @property
    def rebounds(self) -> int: ...
    @property
    def assists(self) -> int: ...
    @property
    def minutes(self) -> float: ...


@dataclass(frozen=True, slots=True)
class GameCorroboration:
    game_id: str
    game_date: date
    season: str
    canonical_player_id: str
    home_team: str
    away_team: str
    player_team: str
    provider_opponent: str
    played_at: datetime
    completed_at: datetime
    game_timezone: str
    reference: str


def reconcile_game(
    proof: GameCorroboration,
    *,
    game_id: str,
    game_date: date,
    season: str,
    canonical_player_id: str,
    provider_opponent: str,
    home: bool,
    stats: AppearanceStats | None,
    retrieved_at: datetime,
    provider_completed_at: datetime | None,
) -> CompletedPlayerGame | None:
    """Validate exact game facts and chronology. A non-appearance emits no sample."""
    own, opponent = (
        (proof.home_team, proof.away_team) if home else (proof.away_team, proof.home_team)
    )
    if (
        not proof.reference.strip()
        or proof.game_id != game_id
        or proof.game_date != game_date
        or proof.season != season
        or proof.canonical_player_id != canonical_player_id
        or proof.provider_opponent != provider_opponent
        or not own.strip()
        or not opponent.strip()
        or own == opponent
        or proof.player_team != own
        or any(
            stamp.utcoffset() is None
            for stamp in (proof.played_at, proof.completed_at, retrieved_at)
        )
    ):
        raise MalformedPayloadError("history corroboration contradicts game scope or chronology")
    try:
        played_at = proof.played_at.astimezone(UTC)
        completed_at = proof.completed_at.astimezone(UTC)
        cutoff = retrieved_at.astimezone(UTC)
        local_day = proof.played_at.astimezone(ZoneInfo(proof.game_timezone)).date()
    except (ZoneInfoNotFoundError, ValueError, OverflowError) as exc:
        raise MalformedPayloadError("history corroboration has an invalid game timezone") from exc
    if (
        local_day != game_date
        or not played_at < completed_at < cutoff
        or (
            provider_completed_at is not None
            and (provider_completed_at.utcoffset() is None or provider_completed_at != completed_at)
        )
    ):
        raise MalformedPayloadError("history actual times contradict game chronology")
    if stats is None:
        return None
    counts = (stats.points, stats.rebounds, stats.assists)
    if (
        any(type(count) is not int or count < 0 for count in counts)
        or isinstance(stats.minutes, bool)
        or not math.isfinite(stats.minutes)
        or stats.minutes <= 0
    ):
        raise MalformedPayloadError("history appearance has invalid statistics")
    return CompletedPlayerGame(
        game_id, played_at, completed_at, season, opponent, *counts, stats.minutes
    )
