"""Typed domain vocabulary for the Fifth Pick."""

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from fifth_pick.errors import ValidationError


class Platform(StrEnum):
    """Approved fantasy platforms. Platform observations stay separate."""

    PRIZEPICKS = "prizepicks"
    UNDERDOG = "underdog"


class Category(StrEnum):
    """Category vocabulary. THREE_POINT_ATTEMPTS is not a live MVP category."""

    POINTS = "POINTS"
    ASSISTS = "ASSISTS"
    REBOUNDS = "REBOUNDS"
    PRA = "PRA"
    REBOUNDS_ASSISTS = "REBOUNDS_ASSISTS"
    THREE_POINT_ATTEMPTS = "THREE_POINT_ATTEMPTS"


LIVE_MVP_CATEGORIES: Final[frozenset[Category]] = frozenset(
    {
        Category.POINTS,
        Category.ASSISTS,
        Category.REBOUNDS,
        Category.PRA,
        Category.REBOUNDS_ASSISTS,
    }
)


class Direction(StrEnum):
    """Authorized selection direction."""

    HIGHER = "HIGHER"
    LOWER = "LOWER"


class DecisionAction(StrEnum):
    """Explicit human decision vocabulary."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"


class ResultStatus(StrEnum):
    """Result vocabulary. DNP and void are not MISS."""

    HIT = "HIT"
    MISS = "MISS"
    PUSH = "PUSH"
    VOID = "VOID"
    DNP = "DNP"
    RESULT_UNAVAILABLE = "RESULT UNAVAILABLE"


class ReasonCode(StrEnum):
    """Closed fail-closed reason vocabulary."""

    PLAYER_IDENTITY_UNRESOLVED = "PLAYER_IDENTITY_UNRESOLVED"
    CATEGORY_NOT_AUTHORIZED = "CATEGORY_NOT_AUTHORIZED"
    PROJECTION_UNAVAILABLE = "PROJECTION_UNAVAILABLE"
    PROJECTION_OBSERVATION_MISSED = "PROJECTION_OBSERVATION_MISSED"
    AVAILABILITY_UNRESOLVED = "AVAILABILITY_UNRESOLVED"
    ROLE_OR_MINUTES_UNRESOLVED = "ROLE_OR_MINUTES_UNRESOLVED"
    T20_CHECK_UNAVAILABLE = "T20_CHECK_UNAVAILABLE"
    SOURCE_CONFLICT_UNRESOLVED = "SOURCE_CONFLICT_UNRESOLVED"
    INSUFFICIENT_SUPPORTING_EVIDENCE = "INSUFFICIENT_SUPPORTING_EVIDENCE"
    RESULT_UNAVAILABLE = "RESULT UNAVAILABLE"
    SNAPSHOT_2_MISSED = "SNAPSHOT_2_MISSED"


def _require_non_empty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")


def _require_datetime(value: datetime, field: str) -> None:
    if not isinstance(value, datetime):
        raise ValidationError(f"{field} must be a datetime")


def _require_finite_number(value: float, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be a finite number")
    if not math.isfinite(value):
        raise ValidationError(f"{field} must be a finite number")


def _require_snapshot_number(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value not in (1, 2, 3):
        raise ValidationError("snapshot_number must be 1, 2, or 3")


@dataclass(frozen=True, slots=True)
class Observation:
    """One platform-specific projection observation."""

    platform: Platform
    player: str
    category: Category
    projection: float
    direction: Direction
    event: str
    source_update_time: datetime
    retrieved_at: datetime
    snapshot_number: int
    source: str
    multiplier: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.platform, Platform):
            raise ValidationError("platform must be a Platform")
        _require_non_empty(self.player, "player")
        if not isinstance(self.category, Category):
            raise ValidationError("category must be a Category")
        _require_finite_number(self.projection, "projection")
        if not isinstance(self.direction, Direction):
            raise ValidationError("direction must be a Direction")
        _require_non_empty(self.event, "event")
        _require_datetime(self.source_update_time, "source_update_time")
        _require_datetime(self.retrieved_at, "retrieved_at")
        _require_snapshot_number(self.snapshot_number)
        _require_non_empty(self.source, "source")
        if self.multiplier is not None:
            _require_finite_number(self.multiplier, "multiplier")


@dataclass(frozen=True, slots=True)
class Candidate:
    """An approved identity joined to one platform's category and direction."""

    player: str
    platform: Platform
    category: Category
    direction: Direction
    projection: float
    event: str

    def __post_init__(self) -> None:
        _require_non_empty(self.player, "player")
        if not isinstance(self.platform, Platform):
            raise ValidationError("platform must be a Platform")
        if not isinstance(self.category, Category):
            raise ValidationError("category must be a Category")
        if not isinstance(self.direction, Direction):
            raise ValidationError("direction must be a Direction")
        _require_finite_number(self.projection, "projection")
        _require_non_empty(self.event, "event")


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A numbered snapshot bound to its matching projection observation."""

    number: int
    observation: Observation
    recorded_at: datetime

    def __post_init__(self) -> None:
        _require_snapshot_number(self.number)
        if not isinstance(self.observation, Observation):
            raise ValidationError("observation must be an Observation")
        _require_datetime(self.recorded_at, "recorded_at")
        if self.number != self.observation.snapshot_number:
            raise ValidationError("snapshot number must match the observation")


@dataclass(frozen=True, slots=True)
class Provenance:
    """Stable source provenance for one evidence item."""

    source: str
    retrieved_at: datetime
    source_timestamp: datetime
    access_method: str
    reference: str
    payload_hash: str

    def __post_init__(self) -> None:
        _require_non_empty(self.source, "source")
        _require_datetime(self.retrieved_at, "retrieved_at")
        _require_datetime(self.source_timestamp, "source_timestamp")
        _require_non_empty(self.access_method, "access_method")
        _require_non_empty(self.reference, "reference")
        _require_non_empty(self.payload_hash, "payload_hash")


@dataclass(frozen=True, slots=True)
class Evidence:
    """An evidence claim with its required provenance."""

    claim: str
    provenance: Provenance
    excerpt: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.claim, "claim")
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")
        if self.excerpt is not None:
            _require_non_empty(self.excerpt, "excerpt")


@dataclass(frozen=True, slots=True)
class Decision:
    """An explicit human decision for one run and slate version."""

    action: DecisionAction
    run_id: str
    timestamp: datetime
    slate_version: int
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.action, DecisionAction):
            raise ValidationError("action must be a DecisionAction")
        _require_non_empty(self.run_id, "run_id")
        _require_datetime(self.timestamp, "timestamp")
        if (
            isinstance(self.slate_version, bool)
            or not isinstance(self.slate_version, int)
            or self.slate_version < 1
        ):
            raise ValidationError("slate_version must be a positive integer")
        if not isinstance(self.note, str):
            raise ValidationError("note must be a string")


@dataclass(frozen=True, slots=True)
class Result:
    """A settlement result that distinguishes unavailable data from MISS."""

    outcome: ResultStatus
    subject: str
    source: str
    recorded_at: datetime
    reason: ReasonCode | None = None
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ResultStatus):
            raise ValidationError("outcome must be a ResultStatus")
        _require_non_empty(self.subject, "subject")
        _require_non_empty(self.source, "source")
        _require_datetime(self.recorded_at, "recorded_at")
        if self.reason is not None and not isinstance(self.reason, ReasonCode):
            raise ValidationError("reason must be a ReasonCode")
        if self.provenance is not None and not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")
