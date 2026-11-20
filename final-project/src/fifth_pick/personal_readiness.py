"""Personal board scope and credit forecasting over verified schedule and roster inputs."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.identity import IdentityResolver
from fifth_pick.registry import Registry
from fifth_pick.slate_manifest import SLATE_TIMEZONE
from fifth_pick.snapshots import snapshot_2_target
from fifth_pick.sources.base import SourceError, SourceEvent
from fifth_pick.sources.odds_api import APPROVED_MARKETS, ProjectionFilter, validate_event_id


def forecast_daily_board(
    events: tuple[SourceEvent, ...],
    roster_ids: Mapping[str, tuple[str, ...]],
    *,
    as_of: datetime,
) -> dict[str, object]:
    """Estimate a fresh three-observation run from exact canonical roster IDs."""

    if as_of.utcoffset() is None:
        raise SourceError("board forecast requires an aware clock")
    timezone = ZoneInfo(SLATE_TIMEZONE)
    day = as_of.astimezone(timezone).date()
    slate = {
        event.event_id: event
        for event in events
        if event.commence_time.astimezone(timezone).date() == day
    }
    if len({event.event_id for event in events}) != len(events):
        raise SourceError("duplicate event in the forecast schedule")
    registry = Registry.from_universe(load_configs().approved_universe)
    gate = AuthorizationGate()
    rostered, granted = set(), set()
    relevant, timely = [], []
    for event_id, event in slate.items():
        player_ids = set(roster_ids.get(event_id, ()))
        rostered.update(player_id for player_id in player_ids if registry.player_by_id(player_id))
        eligible = {
            player_id
            for player_id in player_ids
            if (player := registry.player_by_id(player_id)) is not None
            and any(
                gate.authorize(player_id, item.category, item.direction).allowed
                for item in player.grants
            )
        }
        granted.update(eligible)
        if eligible:
            relevant.append(event_id)
            if snapshot_2_target(as_of, event.commence_time) is not None:
                timely.append(event_id)
    credits = len(timely) * len(APPROVED_MARKETS)
    return {
        "slate_date": day.isoformat(),
        "official_game_count": len(slate),
        "slate_ceiling": 5 if len(slate) >= 5 else 4 if slate else 0,
        "relevant_game_count": len(relevant),
        "rostered_universe_players": len(rostered),
        "rostered_players_with_a_live_grant": len(granted),
        "relevant_event_ids": sorted(relevant),
        "timely_event_ids": sorted(timely),
        "unverified_roster_event_ids": sorted(slate.keys() - roster_ids.keys()),
        "snapshot_1_credit_ceiling": credits,
        "three_snapshot_credit_ceiling": credits * 3,
    }


def authorized_projection_filter(
    resolver: IdentityResolver, roster_ids: Mapping[str, tuple[str, ...]]
) -> ProjectionFilter:
    """Build a pre-parser filter for verified, event-scoped exact grants."""

    gate = AuthorizationGate()

    def allowed(event_id, name, category, direction):
        identity = resolver.resolve_provider(name)
        return (
            identity.resolved
            and identity.player is not None
            and identity.player.player_id in roster_ids.get(event_id, ())
            and gate.authorize(identity.player.player_id, category, direction).allowed
        )

    return allowed


@dataclass(frozen=True, slots=True)
class LiveEventScope:
    """A reviewed provider event and canonical roster from the live preflight."""

    event_id: str
    home_team: str
    away_team: str
    tipoff: datetime
    player_ids: tuple[str, ...]

    def validate(self) -> None:
        validate_event_id(self.event_id)
        if self.tipoff.utcoffset() is None or not self.home_team or not self.away_team:
            raise SourceError("live event scope requires teams and a timezone-aware tipoff")
        registry = Registry.from_universe(load_configs().approved_universe)
        gate = AuthorizationGate()
        if not self.player_ids or any(
            (player := registry.player_by_id(player_id)) is None
            or not any(
                gate.authorize(player_id, grant.category, grant.direction).allowed
                for grant in player.grants
            )
            for player_id in self.player_ids
        ):
            raise SourceError("live event scope requires only canonical players with live grants")

    def matches(self, event: SourceEvent) -> bool:
        return (
            event.event_id == self.event_id
            and event.home_team == self.home_team
            and event.away_team == self.away_team
            and event.commence_time == self.tipoff
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "tipoff": self.tipoff.isoformat(),
            "player_ids": self.player_ids,
        }
