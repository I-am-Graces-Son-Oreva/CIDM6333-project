"""Exact identity resolution with no fuzzy or implicit name fallback."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from fifth_pick.errors import ValidationError
from fifth_pick.models import ReasonCode
from fifth_pick.registry import Registry, RegistryPlayer


class IdentityError(ValidationError):
    """Raised when identity indexes are malformed or reference unknown players."""


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    """The outcome of one exact identity lookup."""

    input_name: str
    player: RegistryPlayer | None
    reason: ReasonCode | None
    source: str

    @property
    def resolved(self) -> bool:
        """True only when exactly one canonical player was resolved."""

        return self.player is not None and self.reason is None


def _unresolved(input_name: str) -> IdentityResolution:
    return IdentityResolution(
        input_name=input_name,
        player=None,
        reason=ReasonCode.PLAYER_IDENTITY_UNRESOLVED,
        source="unresolved",
    )


class IdentityResolver:
    """Resolve exact canonical names, registered aliases, or registered provider aliases."""

    def __init__(
        self,
        registry: Registry,
        provider_aliases: Mapping[str, Iterable[str]] | None = None,
    ) -> None:
        if not isinstance(registry, Registry):
            raise IdentityError("registry must be a Registry")

        self._registry = registry
        self._provider_aliases: dict[str, tuple[RegistryPlayer, ...]] = {}

        for provider_name, candidate_ids in (provider_aliases or {}).items():
            if not isinstance(provider_name, str) or not provider_name.strip():
                raise IdentityError("provider names must be non-empty strings")

            players: list[RegistryPlayer] = []
            for candidate_id in candidate_ids:
                if not isinstance(candidate_id, str):
                    raise IdentityError("provider candidate ids must be strings")
                player = registry.player_by_id(candidate_id)
                if player is None:
                    raise IdentityError(
                        f"provider alias {provider_name!r} references "
                        f"unknown player {candidate_id!r}"
                    )
                if player not in players:
                    players.append(player)

            self._provider_aliases[provider_name] = tuple(players)

    def resolve_canonical(self, name: str) -> IdentityResolution:
        """Resolve only an exact canonical display name or an exact registered alias."""

        if not isinstance(name, str) or not name:
            return _unresolved(name if isinstance(name, str) else repr(name))

        player = self._registry.player_by_canonical_name(name)
        if player is not None:
            return IdentityResolution(
                input_name=name,
                player=player,
                reason=None,
                source="canonical",
            )

        player = self._registry.player_by_alias(name)
        if player is not None:
            return IdentityResolution(
                input_name=name,
                player=player,
                reason=None,
                source="alias",
            )

        return _unresolved(name)

    def resolve_provider(self, provider_name: str) -> IdentityResolution:
        """Resolve only an explicitly registered provider alias.

        A canonical display name is not a provider alias. Unknown or ambiguous provider
        names fail closed.
        """

        if not isinstance(provider_name, str) or not provider_name:
            return _unresolved(
                provider_name if isinstance(provider_name, str) else repr(provider_name)
            )

        players = self._provider_aliases.get(provider_name)
        if players is None or len(players) != 1:
            return _unresolved(provider_name)

        return IdentityResolution(
            input_name=provider_name,
            player=players[0],
            reason=None,
            source="provider",
        )
