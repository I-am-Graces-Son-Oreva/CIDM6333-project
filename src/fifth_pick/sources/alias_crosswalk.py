"""Join separately verified roster and board-identity records by stable identity."""

from collections import Counter
from dataclasses import dataclass

from fifth_pick.personal_readiness import LiveEventScope
from fifth_pick.sources.base import SourceError


@dataclass(frozen=True, slots=True)
class RosterIdentity:
    stable_id: str
    canonical_id: str
    team: str
    reference: str


@dataclass(frozen=True, slots=True)
class BoardIdentity:
    stable_id: str
    provider_label: str
    event_id: str
    team: str
    reference: str


def join_event_aliases(
    scope: LiveEventScope,
    roster: tuple[RosterIdentity, ...],
    board: tuple[BoardIdentity, ...],
) -> tuple[dict[str, str], dict[str, str]]:
    """Prepare an alias scope for review; record references are external evidence."""
    scope.validate()
    authorized = set(scope.player_ids)
    teams = {scope.away_team, scope.home_team}
    stable_counts = Counter(row.stable_id for row in roster)
    verified: dict[str, RosterIdentity] = {}
    canonical_ids: set[str] = set()
    for row in roster:
        if row.canonical_id not in authorized or row.team not in teams:
            continue
        if (
            not row.stable_id.strip()
            or not row.reference.strip()
            or stable_counts[row.stable_id] != 1
            or row.canonical_id in canonical_ids
        ):
            raise SourceError("duplicate or incomplete authorized roster identity")
        verified[row.stable_id] = row
        canonical_ids.add(row.canonical_id)
    aliases: dict[str, str] = {}
    evidence: dict[str, str] = {}
    for row in board:
        if row.event_id != scope.event_id:
            continue
        person = verified.get(row.stable_id)
        if person is None:
            continue
        label = row.provider_label
        if (
            row.team != person.team
            or not label.strip()
            or not label.isprintable()
            or not row.reference.strip()
            or label in aliases
        ):
            raise SourceError("conflicting or incomplete authorized provider alias")
        aliases[label] = person.canonical_id
        evidence[label] = f"roster={person.reference} | board={row.reference}"
    # An exact label reused for a different person is unsafe, even if that person
    # is out of scope. Check label structure only and retain no outside identity.
    if any(
        row.event_id == scope.event_id
        and row.provider_label in aliases
        and row.stable_id not in verified
        for row in board
    ):
        raise SourceError("provider reused an authorized label for another identity")
    return aliases, evidence
