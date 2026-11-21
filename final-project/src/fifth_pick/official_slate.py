"""Reconcile the independent official NBA schedule with quota-free provider discovery."""

import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fifth_pick.config import DEFAULT_CONFIG_DIR
from fifth_pick.slate_manifest import SLATE_TIMEZONE
from fifth_pick.sources.base import SourceError, SourceEvent

_TEAM_NAMES = {"Los Angeles Clippers": "LA Clippers"}


def _matchup(away: str, home: str) -> tuple[str, str]:
    return _TEAM_NAMES.get(away, away), _TEAM_NAMES.get(home, home)


@dataclass(frozen=True, slots=True)
class OfficialGame:
    away_team: str
    home_team: str
    scheduled_tipoff: datetime

    @property
    def matchup(self) -> tuple[str, str]:
        return _matchup(self.away_team, self.home_team)

    def to_dict(self) -> dict[str, str]:
        return {
            "away_team": self.away_team,
            "home_team": self.home_team,
            "scheduled_tipoff": self.scheduled_tipoff.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class OfficialSlate:
    source: str
    games: tuple[OfficialGame, ...]

    def game_for(self, away: str, home: str) -> OfficialGame | None:
        key = _matchup(away, home)
        return next((game for game in self.games if game.matchup == key), None)


def load_official_slate(day: date) -> OfficialSlate | None:
    path = DEFAULT_CONFIG_DIR / "official-slates" / f"{day.isoformat()}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise SourceError("official schedule record is unreadable") from exc
    chicago = ZoneInfo(SLATE_TIMEZONE)
    try:
        source = data["source"]
        games = tuple(
            OfficialGame(
                row["away_team"], row["home_team"], datetime.fromisoformat(row["scheduled_tipoff"])
            )
            for row in data["games"]
        )
        if (
            data["slate_date"] != day.isoformat()
            or source != f"https://www.nba.com/games?date={day.isoformat()}"
            or not games
            or len({game.matchup for game in games}) != len(games)
            or any(
                not isinstance(game.away_team, str)
                or not isinstance(game.home_team, str)
                or not game.away_team.strip()
                or not game.home_team.strip()
                or game.matchup[0] == game.matchup[1]
                or game.scheduled_tipoff.utcoffset() is None
                or game.scheduled_tipoff.astimezone(chicago).date() != day
                for game in games
            )
        ):
            raise ValueError
    except (KeyError, ValueError, TypeError) as exc:
        raise SourceError("official schedule record is invalid") from exc
    return OfficialSlate(source, games)


def provider_event_row(event: SourceEvent) -> dict[str, str]:
    return {
        "event_id": event.event_id,
        "home_team": event.home_team,
        "away_team": event.away_team,
        "tipoff": event.commence_time.isoformat(),
    }


def reconcile_coverage(
    official: OfficialSlate, events: tuple[SourceEvent, ...], *, day: date
) -> dict[str, Any]:
    chicago = ZoneInfo(SLATE_TIMEZONE)
    official_keys = {game.matchup for game in official.games}
    dates = Counter()
    matched: dict[tuple[str, str], list[SourceEvent]] = {}
    other_dates = []
    unexpected = []
    for event in events:
        local_date = event.commence_time.astimezone(chicago).date()
        dates[local_date.isoformat()] += 1
        key = _matchup(event.away_team, event.home_team)
        if local_date != day:
            if key in official_keys and abs((local_date - day).days) == 1:
                other_dates.append(
                    dict(provider_event_row(event), chicago_date=local_date.isoformat())
                )
        elif key in official_keys:
            matched.setdefault(key, []).append(event)
        else:
            unexpected.append(provider_event_row(event))
    missing = [game.to_dict() for game in official.games if game.matchup not in matched]
    ambiguous = [
        game.to_dict() for game in official.games if len(matched.get(game.matchup, ())) > 1
    ]
    timing_differences = [
        dict(provider_event_row(event), official_scheduled_tipoff=game.scheduled_tipoff.isoformat())
        for game in official.games
        for event in matched.get(game.matchup, ())
        if event.commence_time != game.scheduled_tipoff
    ]
    return {
        "official_schedule_source": official.source,
        "official_game_count": len(official.games),
        "selection_ceiling": 5 if len(official.games) >= 5 else 4,
        "official_games": [game.to_dict() for game in official.games],
        "provider_matches_official_slate": not (missing or ambiguous or unexpected),
        "provider_returned_event_count": len(events),
        "provider_event_count_by_chicago_date": dict(dates),
        "provider_discovered_game_count": dates[day.isoformat()],
        "unavailable_from_provider": missing,
        "ambiguous_provider_matchups": ambiguous,
        "unexpected_provider_events": unexpected,
        "official_matchups_on_other_provider_dates": other_dates,
        "provider_tipoff_differences": timing_differences,
        "provider_covered_authorized_player_events": [],
        "authorized_player_event_coverage": "UNVERIFIED_BY_EVENT_DISCOVERY",
    }
