"""Exact authorization over the approved player, category, and direction universe."""

from collections.abc import Iterable
from dataclasses import dataclass

from fifth_pick.config import CategoryMapConfig, load_configs
from fifth_pick.errors import ValidationError
from fifth_pick.models import LIVE_MVP_CATEGORIES, Category, Direction, ReasonCode
from fifth_pick.registry import AuthorizationGrant, Registry


class DuplicatePlayerError(ValidationError):
    """Raised when one canonical player appears in more than one slot."""


def validate_one_player_one_slot(player_ids: Iterable[str]) -> tuple[str, ...]:
    """Validate narrow player uniqueness for candidate or final slots.

    This is not M8 finalization. It only rejects a repeated canonical player ID.
    """

    result: list[str] = []
    seen: set[str] = set()

    for player_id in player_ids:
        if not isinstance(player_id, str) or not player_id:
            raise ValidationError("player ids must be non-empty strings")
        if player_id in seen:
            raise DuplicatePlayerError(f"player {player_id!r} occupies more than one slot")
        seen.add(player_id)
        result.append(player_id)

    return tuple(result)


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """One exact authorization result with universe provenance."""

    allowed: bool
    player_id: str | None
    category: Category | None
    direction: Direction | None
    reason: ReasonCode | None
    detail: str
    universe_version: str
    universe_effective_date: str


@dataclass(frozen=True, slots=True, init=False)
class AuthorizationGate:
    """Authorize only exact registry grants that are inside the live MVP.

    The gate owns its authoritative configuration. Callers cannot supply a
    registry, category map, live-category set, or universe metadata, and the
    gate and its nested policy indexes are immutable after construction.
    """

    _registry: Registry
    _category_map: CategoryMapConfig
    _universe_version: str
    _universe_effective_date: str
    _live_categories: frozenset[Category]

    def __init__(self) -> None:
        bundle = load_configs()
        metadata = bundle.approved_universe.metadata
        if metadata.content_version is None or metadata.effective_date is None:
            raise ValidationError("approved universe metadata is incomplete")

        object.__setattr__(self, "_registry", Registry.from_universe(bundle.approved_universe))
        object.__setattr__(self, "_category_map", bundle.category_map)
        object.__setattr__(self, "_universe_version", metadata.content_version)
        object.__setattr__(self, "_universe_effective_date", metadata.effective_date)
        object.__setattr__(self, "_live_categories", LIVE_MVP_CATEGORIES)

    def map_category(self, market_label: str) -> Category | None:
        """Map an exact provider market label to a canonical category."""

        return self._category_map.resolve(market_label)

    def authorize(
        self,
        player_id: str,
        category: Category,
        direction: Direction,
    ) -> AuthorizationDecision:
        """Authorize exactly one player, category, and direction."""

        safe_category = category if isinstance(category, Category) else None
        safe_direction = direction if isinstance(direction, Direction) else None

        if not isinstance(player_id, str) or not player_id:
            return self._denied(
                player_id=None,
                category=safe_category,
                direction=safe_direction,
                reason=ReasonCode.PLAYER_IDENTITY_UNRESOLVED,
                detail="player identity is unresolved",
            )

        player = self._registry.player_by_id(player_id)
        if player is None:
            return self._denied(
                player_id=None,
                category=safe_category,
                direction=safe_direction,
                reason=ReasonCode.PLAYER_IDENTITY_UNRESOLVED,
                detail="player is not in the canonical registry",
            )

        if safe_category is None or safe_direction is None:
            return self._denied(
                player_id=player.player_id,
                category=safe_category,
                direction=safe_direction,
                reason=ReasonCode.CATEGORY_NOT_AUTHORIZED,
                detail="category or direction is not canonical",
            )

        if safe_category not in self._live_categories:
            return self._denied(
                player_id=player.player_id,
                category=safe_category,
                direction=safe_direction,
                reason=ReasonCode.CATEGORY_NOT_AUTHORIZED,
                detail="category is outside the live MVP",
            )

        grant = AuthorizationGrant(category=safe_category, direction=safe_direction)
        if grant not in player.grants:
            return self._denied(
                player_id=player.player_id,
                category=safe_category,
                direction=safe_direction,
                reason=ReasonCode.CATEGORY_NOT_AUTHORIZED,
                detail="player is not authorized for this category and direction",
            )

        return AuthorizationDecision(
            allowed=True,
            player_id=player.player_id,
            category=safe_category,
            direction=safe_direction,
            reason=None,
            detail="player, category, and direction are authorized",
            universe_version=self._universe_version,
            universe_effective_date=self._universe_effective_date,
        )

    def _denied(
        self,
        *,
        player_id: str | None,
        category: Category | None,
        direction: Direction | None,
        reason: ReasonCode,
        detail: str,
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=False,
            player_id=player_id,
            category=category,
            direction=direction,
            reason=reason,
            detail=detail,
            universe_version=self._universe_version,
            universe_effective_date=self._universe_effective_date,
        )
