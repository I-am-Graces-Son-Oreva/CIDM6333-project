"""M6 supporting-evidence validation and deterministic history summaries."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from urllib.parse import urlparse

from fifth_pick.errors import ValidationError
from fifth_pick.models import Direction, Evidence, Provenance, ReasonCode
from fifth_pick.receipts import ReceiptError, redact_text
from fifth_pick.sources.base import EvidenceMode

_SHA256_LENGTH = 64
_FIXTURE_SOURCE = "synthetic-fixture"
_FIXTURE_ACCESS_METHOD = "synthetic-fixture"


class EvidenceError(ValidationError):
    """Raised when supporting evidence is malformed or uses an unapproved source."""


class EvidenceKind(StrEnum):
    PROJECTION_MOVEMENT = "PROJECTION_MOVEMENT"
    LAST_8 = "LAST_8"
    SAME_SEASON_H2H = "SAME_SEASON_H2H"
    ROLE_MINUTES = "ROLE_MINUTES"
    AVAILABILITY = "AVAILABILITY"
    TEAMMATE_ABSENCE = "TEAMMATE_ABSENCE"
    OPPONENT_ABSENCE = "OPPONENT_ABSENCE"
    SCHEDULE = "SCHEDULE"
    GENERAL_CONTEXT = "GENERAL_CONTEXT"
    MATCHUP = "MATCHUP"
    GAME_TOTAL = "GAME_TOTAL"
    POINT_SPREAD = "POINT_SPREAD"
    BLOWOUT_RISK = "BLOWOUT_RISK"
    FOUL_TROUBLE = "FOUL_TROUBLE"
    OTHER = "OTHER"


class EvidenceEffect(StrEnum):
    """A contextual interpretation relative to the candidate's authorized direction."""

    SUPPORTS = "SUPPORTS"
    CONCERN = "CONCERN"
    CONFLICT = "CONFLICT"
    NEUTRAL = "NEUTRAL"


class EvidenceSignificance(StrEnum):
    """Frozen qualitative materiality labels; these are not numerical weights."""

    IMPORTANT = "IMPORTANT"
    MEANINGFUL = "MEANINGFUL"
    MINOR = "MINOR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class PerformanceSample:
    """One historical performance fact in an evidence excerpt."""

    played_at: datetime
    value: float
    opponent: str
    season: str

    def __post_init__(self) -> None:
        _require_aware(self.played_at, "played_at")
        if isinstance(self.value, bool) or not isinstance(self.value, (float, int)):
            raise EvidenceError("performance value must be a finite number")
        if not math.isfinite(self.value):
            raise EvidenceError("performance value must be a finite number")
        if not isinstance(self.opponent, str) or not self.opponent.strip():
            raise EvidenceError("performance opponent must be non-empty")
        if not isinstance(self.season, str) or not self.season.strip():
            raise EvidenceError("performance season must be non-empty")


def _canonical_samples(
    samples: tuple[PerformanceSample, ...],
) -> tuple[PerformanceSample, ...]:
    by_game: dict[tuple[datetime, str, str], PerformanceSample] = {}
    for sample in samples:
        identity = (sample.played_at, sample.opponent, sample.season)
        previous = by_game.get(identity)
        if previous is not None:
            if previous.value != sample.value:
                raise EvidenceError("one historical game has conflicting performance values")
            continue
        by_game[identity] = sample
    return tuple(
        sorted(
            by_game.values(),
            key=lambda sample: (sample.played_at, sample.opponent, sample.season),
        )
    )


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One candidate-scoped source claim with explicit qualitative assessment."""

    evidence_id: str
    candidate_key: str
    kind: EvidenceKind
    evidence: Evidence
    evidence_mode: EvidenceMode
    effect: EvidenceEffect
    significance: EvidenceSignificance
    samples: tuple[PerformanceSample, ...] = ()
    facts: Mapping[str, str | int | float | bool] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise EvidenceError("evidence_id must be non-empty")
        if not isinstance(self.candidate_key, str) or len(self.candidate_key) != _SHA256_LENGTH:
            raise EvidenceError("candidate_key must be a SHA-256 digest")
        if not isinstance(self.kind, EvidenceKind):
            raise EvidenceError("kind must be an EvidenceKind")
        if not isinstance(self.evidence, Evidence):
            raise EvidenceError("evidence must be an Evidence record")
        if self.evidence_mode not in (EvidenceMode.LIVE, EvidenceMode.FIXTURE):
            raise EvidenceError("evidence_mode must be LIVE or FIXTURE")
        if not isinstance(self.effect, EvidenceEffect):
            raise EvidenceError("effect must be an EvidenceEffect")
        if not isinstance(self.significance, EvidenceSignificance):
            raise EvidenceError("significance must be an EvidenceSignificance")
        if not isinstance(self.samples, tuple) or any(
            not isinstance(sample, PerformanceSample) for sample in self.samples
        ):
            raise EvidenceError("samples must contain PerformanceSample values")
        object.__setattr__(self, "samples", _canonical_samples(self.samples))
        historical = self.kind in (EvidenceKind.LAST_8, EvidenceKind.SAME_SEASON_H2H)
        if historical and not self.samples:
            raise EvidenceError("historical evidence must contain performance samples")
        if not historical and self.samples:
            raise EvidenceError("only last-8 or H2H evidence may contain performance samples")
        facts = {} if self.facts is None else dict(self.facts)
        for name, value in facts.items():
            if not isinstance(name, str) or not isinstance(value, (str, int, float, bool)):
                raise EvidenceError("evidence facts must be JSON-compatible scalar values")
            if isinstance(value, float) and not math.isfinite(value):
                raise EvidenceError("evidence facts must be finite")
        object.__setattr__(self, "facts", MappingProxyType(facts))

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "candidate_key": self.candidate_key,
            "kind": self.kind.value,
            "mode": self.evidence_mode.value,
            "effect": self.effect.value,
            "significance": self.significance.value,
            "claim": self.evidence.claim,
            "source": self.evidence.provenance.source,
            "retrieved_at": self.evidence.provenance.retrieved_at.isoformat(),
            "source_timestamp": self.evidence.provenance.source_timestamp.isoformat(),
            "access_method": self.evidence.provenance.access_method,
            "reference": self.evidence.provenance.reference,
            "payload_hash": self.evidence.provenance.payload_hash,
            "excerpt": self.evidence.excerpt,
            "samples": [
                {
                    "played_at": sample.played_at.isoformat(),
                    "value": sample.value,
                    "opponent": sample.opponent,
                    "season": sample.season,
                }
                for sample in self.samples
            ],
            "facts": dict(self.facts or {}),
        }


@dataclass(frozen=True, slots=True)
class EvidenceGap:
    """One explicitly disclosed missing-evidence condition."""

    kind: EvidenceKind
    reason: ReasonCode
    significance: EvidenceSignificance
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EvidenceKind):
            raise EvidenceError("gap kind must be an EvidenceKind")
        if not isinstance(self.reason, ReasonCode):
            raise EvidenceError("gap reason must be a ReasonCode")
        if not isinstance(self.significance, EvidenceSignificance):
            raise EvidenceError("gap significance must be an EvidenceSignificance")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise EvidenceError("gap detail must be non-empty")

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind.value,
            "reason": self.reason.value,
            "significance": self.significance.value,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class HistorySummary:
    """Deterministic counts relative to one candidate's current projection."""

    kind: EvidenceKind
    sample_count: int
    higher_count: int
    lower_count: int
    push_count: int
    favorable_count: int
    unfavorable_count: int
    incomplete: bool
    outcomes: tuple[str, ...]


def _require_aware(value: datetime, field: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise EvidenceError(f"{field} must be a timezone-aware datetime")


def _redacted_evidence(evidence: Evidence) -> Evidence:
    try:
        provenance = Provenance(
            source=redact_text(evidence.provenance.source),
            retrieved_at=evidence.provenance.retrieved_at,
            source_timestamp=evidence.provenance.source_timestamp,
            access_method=redact_text(evidence.provenance.access_method),
            reference=redact_text(evidence.provenance.reference),
            payload_hash=evidence.provenance.payload_hash,
        )
        return Evidence(
            claim=redact_text(evidence.claim),
            provenance=provenance,
            excerpt=(None if evidence.excerpt is None else redact_text(evidence.excerpt)),
        )
    except ReceiptError as exc:
        raise EvidenceError("evidence redaction failed") from exc


def _redacted_facts(
    facts: Mapping[str, str | int | float | bool] | None,
) -> dict[str, str | int | float | bool]:
    redacted: dict[str, str | int | float | bool] = {}
    for name, value in sorted((facts or {}).items()):
        redacted_name = redact_text(name)
        redacted_value = redact_text(value) if isinstance(value, str) else value
        if redacted_name in redacted:
            raise EvidenceError("redaction produced duplicate fact names")
        redacted[redacted_name] = redacted_value
    return redacted


def _redacted_samples(samples: tuple[PerformanceSample, ...]) -> tuple[PerformanceSample, ...]:
    return tuple(
        sorted(
            (
                PerformanceSample(
                    played_at=sample.played_at,
                    value=sample.value,
                    opponent=redact_text(sample.opponent),
                    season=redact_text(sample.season),
                )
                for sample in samples
            ),
            key=lambda sample: (
                sample.played_at,
                sample.value,
                sample.opponent,
                sample.season,
            ),
        )
    )


def _validate_source(item: EvidenceItem) -> None:
    source_id = item.evidence.provenance.source
    reference = item.evidence.provenance.reference
    parsed = urlparse(reference)
    if "stats.nba.com" in parsed.netloc.lower() or parsed.path.lower().startswith("/stats/"):
        raise EvidenceError("NBA statistical endpoints are not an approved evidence source")
    if item.evidence_mode is EvidenceMode.LIVE:
        raise EvidenceError("live supporting-source retrieval is unavailable in M6")
    if (
        source_id != _FIXTURE_SOURCE
        or item.evidence.provenance.access_method != _FIXTURE_ACCESS_METHOD
    ):
        raise EvidenceError("fixture evidence must use the explicit synthetic-fixture source")
    if not reference.startswith("fixture:"):
        raise EvidenceError("fixture evidence reference must be labeled fixture")


def validate_evidence_items(
    items: Sequence[EvidenceItem],
    *,
    candidate_key: str,
) -> tuple[EvidenceItem, ...]:
    """Validate provenance for fixture evidence without retrieving any source."""

    if not isinstance(candidate_key, str) or len(candidate_key) != _SHA256_LENGTH:
        raise EvidenceError("candidate_key must be a SHA-256 digest")
    validated: list[EvidenceItem] = []
    seen: set[str] = set()
    seen_history_context: set[EvidenceKind] = set()
    for item in items:
        if not isinstance(item, EvidenceItem):
            raise EvidenceError("items must contain EvidenceItem values")
        if item.candidate_key != candidate_key:
            raise EvidenceError("evidence belongs to a different candidate")
        evidence_id = redact_text(item.evidence_id)
        if evidence_id in seen:
            raise EvidenceError("duplicate evidence_id")
        seen.add(evidence_id)
        if item.kind in (
            EvidenceKind.MATCHUP,
            EvidenceKind.LAST_8,
            EvidenceKind.SAME_SEASON_H2H,
        ):
            if item.kind in seen_history_context:
                raise EvidenceError(f"multiple {item.kind.value} records are ambiguous")
            seen_history_context.add(item.kind)
        provenance = item.evidence.provenance
        if provenance.source_timestamp > provenance.retrieved_at:
            raise EvidenceError("source timestamp cannot be later than retrieval")
        if len(provenance.payload_hash) != _SHA256_LENGTH or any(
            character not in "0123456789abcdef" for character in provenance.payload_hash
        ):
            raise EvidenceError("evidence payload_hash must be a SHA-256 digest")
        if item.evidence.excerpt is None:
            raise EvidenceError("supporting evidence requires an auditable excerpt")
        _validate_source(item)
        validated.append(
            EvidenceItem(
                evidence_id=evidence_id,
                candidate_key=item.candidate_key,
                kind=item.kind,
                evidence=_redacted_evidence(item.evidence),
                evidence_mode=item.evidence_mode,
                effect=item.effect,
                significance=item.significance,
                samples=_redacted_samples(item.samples),
                facts=_redacted_facts(item.facts),
            )
        )
    return tuple(sorted(validated, key=lambda item: item.evidence_id))


def summarize_history(
    item: EvidenceItem,
    *,
    line: float,
    direction: Direction,
    current_season: str,
    opponent: str,
) -> HistorySummary:
    """Count supplied history against the line; never infer a predictive score."""

    if not isinstance(item, EvidenceItem) or item.kind not in (
        EvidenceKind.LAST_8,
        EvidenceKind.SAME_SEASON_H2H,
    ):
        raise EvidenceError("history summary requires LAST_8 or SAME_SEASON_H2H evidence")
    if isinstance(line, bool) or not isinstance(line, (int, float)) or not math.isfinite(line):
        raise EvidenceError("line must be a finite number")
    if not isinstance(direction, Direction):
        raise EvidenceError("direction must be a Direction")
    if not isinstance(current_season, str) or not current_season.strip():
        raise EvidenceError("current_season must be non-empty")
    if not isinstance(opponent, str) or not opponent.strip():
        raise EvidenceError("opponent must be non-empty")
    if item.kind is EvidenceKind.LAST_8:
        samples = tuple(sorted(item.samples, key=lambda sample: sample.played_at, reverse=True)[:8])
        incomplete = len(samples) < 8
    else:
        samples = tuple(
            sorted(
                (
                    sample
                    for sample in item.samples
                    if sample.season == current_season and sample.opponent == opponent
                ),
                key=lambda sample: sample.played_at,
                reverse=True,
            )
        )
        incomplete = not samples

    higher = sum(sample.value > line for sample in samples)
    lower = sum(sample.value < line for sample in samples)
    pushes = sum(sample.value == line for sample in samples)
    favorable = higher if direction is Direction.HIGHER else lower
    unfavorable = lower if direction is Direction.HIGHER else higher
    outcomes = tuple(
        "HIGHER" if sample.value > line else "LOWER" if sample.value < line else "PUSH"
        for sample in samples
    )
    return HistorySummary(
        kind=item.kind,
        sample_count=len(samples),
        higher_count=higher,
        lower_count=lower,
        push_count=pushes,
        favorable_count=favorable,
        unfavorable_count=unfavorable,
        incomplete=incomplete,
        outcomes=outcomes,
    )
