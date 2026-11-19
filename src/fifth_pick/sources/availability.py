"""Offline source-precedence boundary for normalized NBA availability fixtures."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from fifth_pick.evidence import EvidenceItem, EvidenceKind
from fifth_pick.sources.base import MalformedPayloadError
from fifth_pick.sources.supporting_fixture import (
    aware_timestamp,
    decode_payload,
    fixture_evidence,
    fixture_provenance,
    payload_hash,
    require_fresh,
)

_OFFICIAL = ("official-nba-injury-report", "nba-com")
_EDITORIAL = "sports-illustrated-nba"
_STATUSES = {"AVAILABLE", "PROBABLE", "QUESTIONABLE", "DOUBTFUL", "OUT"}


@dataclass(frozen=True, slots=True)
class FixtureAvailabilityObservation:
    """Normalized attributed availability, without claim of live source access."""

    role: str
    status: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class FixtureAvailability:
    player_id: str
    event_id: str
    retrieved_at: datetime
    payload_sha256: str
    observations: tuple[FixtureAvailabilityObservation, ...]
    selected: FixtureAvailabilityObservation | None

    @property
    def conflict(self) -> bool:
        return len({observation.status for observation in self.observations}) > 1

    def evidence(self, *, candidate_key: str, kind: EvidenceKind) -> tuple[EvidenceItem, ...]:
        if kind not in (
            EvidenceKind.AVAILABILITY,
            EvidenceKind.TEAMMATE_ABSENCE,
            EvidenceKind.OPPONENT_ABSENCE,
        ):
            raise MalformedPayloadError("invalid availability evidence kind")
        if self.selected is None:
            return ()
        selected = self.selected
        return (
            fixture_evidence(
                candidate_key,
                kind=kind,
                provenance=fixture_provenance(
                    f"nba-availability/{self.event_id}/{self.player_id}",
                    self.retrieved_at,
                    selected.updated_at,
                    self.payload_sha256,
                ),
                excerpt=f"{self.player_id} was listed {selected.status} for {self.event_id}",
                facts={
                    "canonical_player_id": self.player_id,
                    "event_id": self.event_id,
                    "status": selected.status,
                    "simulated_source_role": selected.role,
                    "reported_conflict": self.conflict,
                },
            ),
        )


def resolve_fixture_availability(
    body: bytes,
    *,
    player_id: str,
    event_id: str,
    retrieved_at: datetime,
    max_age: timedelta,
) -> FixtureAvailability:
    """Apply A12 to one pre-resolved player/event and keep all conflicting records."""
    raw = decode_payload(body)
    if not isinstance(raw, list) or not player_id.strip() or not event_id.strip():
        raise MalformedPayloadError("availability requires a scoped fixture array")
    observations = []
    seen: set[tuple[str, datetime]] = set()
    for row in raw:
        if not isinstance(row, dict) or (
            row.get("player_id") != player_id or row.get("event_id") != event_id
        ):
            raise MalformedPayloadError("availability does not match the selected player and event")
        role, status = row.get("role"), row.get("status")
        if (
            not isinstance(role, str)
            or role not in (*_OFFICIAL, _EDITORIAL)
            or not isinstance(status, str)
            or status not in _STATUSES
        ):
            raise MalformedPayloadError("unrecognized availability source role or status")
        updated_at = aware_timestamp(row.get("last_update"))
        require_fresh(updated_at, retrieved_at, max_age)
        if (role, updated_at) in seen:
            raise MalformedPayloadError("duplicate or conflicting availability observation")
        seen.add((role, updated_at))
        observations.append(FixtureAvailabilityObservation(role, status, updated_at))

    # Timestamp wins when official records disagree. For identical statuses at the same
    # timestamp, preserve the Injury Report's authority. A tied contradiction stays open.
    officials = [item for item in observations if item.role in _OFFICIAL]
    newest = max((item.updated_at for item in officials), default=None)
    latest = [item for item in officials if item.updated_at == newest]
    selected = (
        min(latest, key=lambda item: _OFFICIAL.index(item.role))
        if latest and len({item.status for item in latest}) == 1
        else None
    )
    return FixtureAvailability(
        player_id, event_id, retrieved_at, payload_hash(body), tuple(observations), selected
    )
