"""In-memory M4 source projections. No snapshot, observation, or M5+ records.

M4 stops at the boundary of the M2 ``Observation``/M5 ``Snapshot`` store: it produces a
platform-scoped, provenance-bearing board that a later milestone may turn into
observations. Nothing here assigns snapshot numbers or backfills evidence.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from fifth_pick.errors import FifthPickError
from fifth_pick.models import LIVE_MVP_CATEGORIES, Category, Direction, Platform
from fifth_pick.sources.quota import QuotaSnapshot


class EvidenceMode(StrEnum):
    """Whether a board came from the live adapter or deterministic fixture transport."""

    LIVE = "live"
    FIXTURE = "fixture"
    UNKNOWN = "unknown"


class SourceError(FifthPickError):
    """Base class for fail-closed source adapter errors."""


class MissingApiKeyError(SourceError):
    """Raised when the approved API key is absent from the environment."""


class LiveAuthorizationError(SourceError):
    """Raised when live retrieval is attempted without explicit authorization."""


class BudgetExceededError(SourceError):
    """Raised when the estimated board cost exceeds the authorized credit budget."""


class UnauthorizedResponseError(SourceError):
    """Raised when the source rejects the request credentials."""


class MalformedPayloadError(SourceError):
    """Raised when a response payload is missing required structure."""


class QuotaExhaustedError(SourceError):
    """Raised when the source reports no remaining quota."""


def _require_non_empty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SourceError(f"{field} must be a non-empty string")


def _require_finite_number(value: float, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SourceError(f"{field} must be a finite number")
    if not math.isfinite(value):
        raise SourceError(f"{field} must be a finite number")


def _require_datetime(value: datetime, field: str) -> None:
    if not isinstance(value, datetime):
        raise SourceError(f"{field} must be a datetime")


@dataclass(frozen=True, slots=True)
class SourceProjection:
    """One platform-scoped projection exactly as the source reported it.

    This is a pre-snapshot value: it carries provenance timestamps but no snapshot
    number and no canonical identity. Identity resolution happens separately and
    fail-closed.
    """

    platform: Platform
    provider_player_name: str
    category: Category
    projection: float
    direction: Direction
    event_id: str
    source_update_time: datetime
    retrieved_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.platform, Platform):
            raise SourceError("platform must be a Platform")
        _require_non_empty(self.provider_player_name, "provider_player_name")
        if not isinstance(self.category, Category):
            raise SourceError("category must be a Category")
        if self.category not in LIVE_MVP_CATEGORIES:
            raise SourceError("category must be a live MVP category")
        _require_finite_number(self.projection, "projection")
        if not isinstance(self.direction, Direction):
            raise SourceError("direction must be a Direction")
        _require_non_empty(self.event_id, "event_id")
        _require_datetime(self.source_update_time, "source_update_time")
        _require_datetime(self.retrieved_at, "retrieved_at")


@dataclass(frozen=True, slots=True)
class SourceEvent:
    """One source event with its platform-scoped projections."""

    event_id: str
    home_team: str
    away_team: str
    commence_time: datetime
    projections: tuple[SourceProjection, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.event_id, "event_id")
        _require_non_empty(self.home_team, "home_team")
        _require_non_empty(self.away_team, "away_team")
        _require_datetime(self.commence_time, "commence_time")
        if not isinstance(self.projections, tuple):
            raise SourceError("projections must be a tuple")
        for projection in self.projections:
            if not isinstance(projection, SourceProjection):
                raise SourceError("projections must contain SourceProjection values")
            if projection.event_id != self.event_id:
                raise SourceError("projection event_id must match its event")


@dataclass(frozen=True, slots=True)
class BoardProvenance:
    """Stable provenance for one retrieved board. Contains no credentials."""

    source_id: str
    region: str
    bookmakers: tuple[str, ...]
    markets: tuple[str, ...]
    request_timestamp: datetime
    retrieved_at: datetime
    source_update_time: datetime | None
    payload_sha256: str
    request_url: str
    quota: QuotaSnapshot
    _evidence_mode: EvidenceMode = field(
        default=EvidenceMode.UNKNOWN,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        _require_non_empty(self.source_id, "source_id")
        _require_non_empty(self.region, "region")
        if not self.bookmakers:
            raise SourceError("bookmakers must not be empty")
        if not self.markets:
            raise SourceError("markets must not be empty")
        _require_datetime(self.request_timestamp, "request_timestamp")
        _require_datetime(self.retrieved_at, "retrieved_at")
        if self.source_update_time is not None:
            _require_datetime(self.source_update_time, "source_update_time")
        _require_non_empty(self.payload_sha256, "payload_sha256")
        _require_non_empty(self.request_url, "request_url")
        if not isinstance(self.quota, QuotaSnapshot):
            raise SourceError("quota must be a QuotaSnapshot")

    @property
    def evidence_mode(self) -> EvidenceMode:
        """Return the mode stamped by the built-in M4 transport adapter."""

        return self._evidence_mode


@dataclass(frozen=True, slots=True)
class SourceBoard:
    """One retrieved, provenance-bearing board of platform-scoped projections."""

    provenance: BoardProvenance
    events: tuple[SourceEvent, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, BoardProvenance):
            raise SourceError("provenance must be a BoardProvenance")
        if not isinstance(self.events, tuple):
            raise SourceError("events must be a tuple")
        seen: set[str] = set()
        for event in self.events:
            if not isinstance(event, SourceEvent):
                raise SourceError("events must contain SourceEvent values")
            if event.event_id in seen:
                raise SourceError("event ids must be unique within a board")
            seen.add(event.event_id)

    @property
    def projections(self) -> tuple[SourceProjection, ...]:
        """All projections in board order. Platforms stay separate."""

        return tuple(projection for event in self.events for projection in event.projections)
