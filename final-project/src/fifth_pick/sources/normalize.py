"""Market/direction normalization and fail-closed identity binding for M4 boards."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from fifth_pick.identity import IdentityResolver
from fifth_pick.models import Category, Direction, ReasonCode
from fifth_pick.registry import RegistryPlayer
from fifth_pick.sources.base import SourceBoard, SourceProjection

MARKET_TO_CATEGORY: Final[Mapping[str, Category]] = MappingProxyType(
    {
        "player_points": Category.POINTS,
        "player_assists": Category.ASSISTS,
        "player_rebounds": Category.REBOUNDS,
        "player_points_rebounds_assists": Category.PRA,
        "player_rebounds_assists": Category.REBOUNDS_ASSISTS,
    }
)

OUTCOME_TO_DIRECTION: Final[Mapping[str, Direction]] = MappingProxyType(
    {
        "Over": Direction.HIGHER,
        "Under": Direction.LOWER,
    }
)


def normalize_market(market_key: str) -> Category | None:
    """Map an approved market key to its category, or None when not approved."""

    if not isinstance(market_key, str):
        return None
    return MARKET_TO_CATEGORY.get(market_key)


def normalize_direction(outcome_name: str) -> Direction | None:
    """Map an exact Over/Under outcome name to a direction, or None otherwise."""

    if not isinstance(outcome_name, str):
        return None
    return OUTCOME_TO_DIRECTION.get(outcome_name)


@dataclass(frozen=True, slots=True)
class ResolvedProjection:
    """One source projection joined to a canonical identity, fail-closed.

    An unresolved projection is preserved with its reason code. It is never dropped and
    never guessed: callers must treat it as unavailable.
    """

    projection: SourceProjection
    player: RegistryPlayer | None
    reason: ReasonCode | None
    identity_source: str

    @property
    def resolved(self) -> bool:
        """True only when exactly one canonical player was resolved."""

        return self.player is not None and self.reason is None


def resolve_identity(
    projection: SourceProjection, resolver: IdentityResolver
) -> ResolvedProjection:
    """Bind one projection to a canonical player using the provider alias index only.

    Only registered provider aliases resolve. Canonical display names are not accepted as
    provider names, and unknown or ambiguous names fail closed with a reason code.
    """

    resolution = resolver.resolve_provider(projection.provider_player_name)
    return ResolvedProjection(
        projection=projection,
        player=resolution.player,
        reason=resolution.reason,
        identity_source=resolution.source,
    )


def resolve_board(board: SourceBoard, resolver: IdentityResolver) -> tuple[ResolvedProjection, ...]:
    """Resolve every projection on a board, preserving unresolved entries."""

    return tuple(resolve_identity(projection, resolver) for projection in board.projections)
