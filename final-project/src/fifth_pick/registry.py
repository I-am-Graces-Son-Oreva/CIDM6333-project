"""Canonical player registry built from the approved universe."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from fifth_pick.config import ApprovedUniverseConfig
from fifth_pick.errors import ValidationError
from fifth_pick.models import Category, Direction

_PLAYER_ID_NON_ALNUM: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")


class RegistryError(ValidationError):
    """Raised when registry data is duplicate, ambiguous, or malformed."""


def canonical_player_id(name: str) -> str:
    """Derive a deterministic local ID from a canonical display name.

    This function is only for stable local IDs. It is never used to match input names.
    """

    if not isinstance(name, str) or not name.strip():
        raise RegistryError("canonical player name must be a non-empty string")

    player_id = _PLAYER_ID_NON_ALNUM.sub("-", name.lower()).strip("-")
    if not player_id:
        raise RegistryError(f"cannot derive a player ID from {name!r}")
    return player_id


@dataclass(frozen=True, slots=True)
class AuthorizationGrant:
    """One exact player category and direction authorization."""

    category: Category
    direction: Direction


@dataclass(frozen=True, slots=True)
class RegistryPlayer:
    """One canonical player with exact grants and registered aliases."""

    player_id: str
    canonical_name: str
    grants: frozenset[AuthorizationGrant]
    aliases: tuple[str, ...] = ()
    foul_trouble: bool = False


@dataclass(frozen=True, slots=True, init=False)
class Registry:
    """Exact canonical-name, alias, and ID indexes over the approved universe."""

    _players: tuple[RegistryPlayer, ...]
    _by_id: Mapping[str, RegistryPlayer]
    _by_name: Mapping[str, RegistryPlayer]
    _by_alias: Mapping[str, RegistryPlayer]

    def __init__(self, players: tuple[RegistryPlayer, ...]) -> None:
        ordered_players = tuple(sorted(players, key=lambda player: player.canonical_name))
        by_id: dict[str, RegistryPlayer] = {}
        by_name: dict[str, RegistryPlayer] = {}
        by_alias: dict[str, RegistryPlayer] = {}

        for player in ordered_players:
            if not isinstance(player, RegistryPlayer):
                raise RegistryError("registry entries must be RegistryPlayer")
            if not player.player_id or not player.canonical_name:
                raise RegistryError("registry player id and name must be non-empty")
            if player.player_id in by_id:
                raise RegistryError(f"duplicate player id: {player.player_id!r}")
            if player.canonical_name in by_name:
                raise RegistryError(f"duplicate canonical name: {player.canonical_name!r}")
            by_id[player.player_id] = player
            by_name[player.canonical_name] = player

        for player in ordered_players:
            if len(set(player.aliases)) != len(player.aliases):
                raise RegistryError(f"duplicate alias on {player.canonical_name!r}")
            for alias in player.aliases:
                if not isinstance(alias, str) or not alias.strip():
                    raise RegistryError("aliases must be non-empty strings")
                if alias in by_name:
                    raise RegistryError(f"alias shadows a canonical name: {alias!r}")
                if alias in by_alias:
                    raise RegistryError(f"duplicate alias: {alias!r}")
                by_alias[alias] = player

        object.__setattr__(self, "_players", ordered_players)
        object.__setattr__(self, "_by_id", MappingProxyType(by_id))
        object.__setattr__(self, "_by_name", MappingProxyType(by_name))
        object.__setattr__(self, "_by_alias", MappingProxyType(by_alias))

    @classmethod
    def from_universe(cls, universe: ApprovedUniverseConfig) -> "Registry":
        """Build a registry from the owner-approved universe."""

        players: list[RegistryPlayer] = []
        for entry in universe.entries:
            player_id = canonical_player_id(entry.name)
            grants = frozenset(
                AuthorizationGrant(category=universe_category.category, direction=direction)
                for universe_category in entry.categories
                for direction in universe_category.directions
            )
            players.append(
                RegistryPlayer(
                    player_id=player_id,
                    canonical_name=entry.name,
                    grants=grants,
                    aliases=entry.aliases,
                    foul_trouble=entry.foul_trouble,
                )
            )
        return cls(tuple(players))

    def players(self) -> tuple[RegistryPlayer, ...]:
        """Return all registry players in deterministic name order."""

        return self._players

    def player_by_id(self, player_id: str) -> RegistryPlayer | None:
        """Return a player only for an exact canonical ID."""

        return self._by_id.get(player_id)

    def player_by_canonical_name(self, name: str) -> RegistryPlayer | None:
        """Return a player only for an exact canonical display name."""

        return self._by_name.get(name)

    def player_by_alias(self, alias: str) -> RegistryPlayer | None:
        """Return a player only for an exactly registered alias."""

        return self._by_alias.get(alias)

    def __len__(self) -> int:
        return len(self._players)
