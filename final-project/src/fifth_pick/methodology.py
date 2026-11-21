"""M6 contextual methodology, confidence guards, and candidate audit records."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.errors import StorageError
from fifth_pick.evidence import (
    EvidenceEffect,
    EvidenceError,
    EvidenceGap,
    EvidenceItem,
    EvidenceKind,
    EvidenceSignificance,
    HistorySummary,
    _validate_evidence_items,
    summarize_history,
)
from fifth_pick.models import Candidate, Category, Direction, ReasonCode
from fifth_pick.receipts import redact_text
from fifth_pick.registry import Registry, canonical_player_id
from fifth_pick.snapshots import (
    MissedSnapshot,
    SnapshotError,
    SnapshotEvidence,
    read_application_snapshot_ledger,
    validate_snapshot_sequence,
)
from fifth_pick.sources.base import EvidenceMode


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class MethodologyDisposition(StrEnum):
    QUALIFY = "QUALIFY"
    REJECT = "REJECT"
    ANALYSIS_ONLY = "ANALYSIS_ONLY"


class EvaluationStatus(StrEnum):
    BLOCKED = "BLOCKED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT EVIDENCE"
    REJECTED = "REJECTED"
    QUALIFIED = "QUALIFIED"
    ANALYSIS_ONLY = "ANALYSIS_ONLY"


class ProjectionMovement(StrEnum):
    RISING = "RISING"
    FALLING = "FALLING"
    STABLE = "STABLE"
    FLUCTUATING = "FLUCTUATING"


class AuditEvidenceMode(StrEnum):
    LIVE = "LIVE"
    FIXTURE = "FIXTURE"
    MIXED = "MIXED"


@dataclass(frozen=True, slots=True)
class CandidateCase:
    snapshots: tuple[SnapshotEvidence, ...]
    missed: tuple[MissedSnapshot, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()
    gaps: tuple[EvidenceGap, ...] = ()
    judgment: "MethodologyJudgment | None" = None
    snapshot_run_id: str | None = None
    supporting_slot: int | None = None
    supporting_as_of: datetime | None = None


@dataclass(frozen=True, slots=True)
class MethodologyJudgment:
    disposition: MethodologyDisposition
    confidence: Confidence
    rationale: str
    supporting_evidence_ids: tuple[str, ...]
    meaningful_risk_ids: tuple[str, ...]
    sufficient_evidence: bool
    major_unresolved_concern: bool = False
    senior_lower_support_ids: tuple[str, ...] = ()
    senior_lower_disclosure: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, MethodologyDisposition):
            raise MethodologyError("disposition must be a MethodologyDisposition")
        if not isinstance(self.confidence, Confidence):
            raise MethodologyError("confidence must be a Confidence")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise MethodologyError("methodology rationale must be non-empty")
        for name, values in (
            ("supporting_evidence_ids", self.supporting_evidence_ids),
            ("meaningful_risk_ids", self.meaningful_risk_ids),
            ("senior_lower_support_ids", self.senior_lower_support_ids),
        ):
            if (
                not isinstance(values, tuple)
                or any(not isinstance(value, str) or not value.strip() for value in values)
                or len(set(values)) != len(values)
            ):
                raise MethodologyError(f"{name} must contain unique non-empty IDs")
        if not isinstance(self.sufficient_evidence, bool):
            raise MethodologyError("sufficient_evidence must be a boolean")
        if not isinstance(self.major_unresolved_concern, bool):
            raise MethodologyError("major_unresolved_concern must be a boolean")
        if not isinstance(self.senior_lower_disclosure, str):
            raise MethodologyError("senior_lower_disclosure must be text")


@dataclass(frozen=True, slots=True)
class CandidateAudit:
    candidate: Candidate
    candidate_id: str
    candidate_key: str
    status: EvaluationStatus
    confidence: Confidence | None
    evidence_mode: AuditEvidenceMode
    movement: ProjectionMovement | None
    history: tuple[HistorySummary, ...]
    evidence: tuple[EvidenceItem, ...]
    gaps: tuple[EvidenceGap, ...]
    is_senior: bool
    trust_labels: tuple[str, ...]
    foul_trouble: bool
    rules_applied: tuple[str, ...]
    exclusions: tuple[ReasonCode, ...]
    rationale: str
    authorization_allowed: bool = False
    disposition: MethodologyDisposition | None = None
    supporting_evidence_ids: tuple[str, ...] = ()
    meaningful_risk_ids: tuple[str, ...] = ()
    senior_lower_disclosure: str = ""
    methodology_sufficient_evidence: bool = False
    major_unresolved_concern: bool = False
    senior_lower_support_ids: tuple[str, ...] = ()
    snapshots: tuple[SnapshotEvidence, ...] = ()
    missed_snapshots: tuple[MissedSnapshot, ...] = ()
    snapshot_run_id: str | None = None

    @property
    def history_summaries(self) -> tuple[HistorySummary, ...]:
        return self.history

    def to_dict(self) -> dict[str, object]:
        kinds = {item.kind for item in self.evidence}
        rules = set(self.rules_applied)
        serialized: dict[str, object] = {
            "candidate": {
                "player": self.candidate.player,
                "platform": self.candidate.platform.value,
                "category": self.candidate.category.value,
                "direction": self.candidate.direction.value,
                "projection": self.candidate.projection,
                "event": self.candidate.event,
            },
            "candidate_id": self.candidate_id,
            "candidate_key": self.candidate_key,
            "status": self.status.value,
            "confidence": None if self.confidence is None else self.confidence.value,
            "evidence_mode": self.evidence_mode.value,
            "movement": None if self.movement is None else self.movement.value,
            "history": [
                {
                    "kind": item.kind.value,
                    "sample_count": item.sample_count,
                    "higher_count": item.higher_count,
                    "lower_count": item.lower_count,
                    "push_count": item.push_count,
                    "favorable_count": item.favorable_count,
                    "unfavorable_count": item.unfavorable_count,
                    "incomplete": item.incomplete,
                    "outcomes": list(item.outcomes),
                }
                for item in self.history
            ],
            "evidence": [item.to_dict() for item in self.evidence],
            "gaps": [gap.to_dict() for gap in self.gaps],
            "is_senior": self.is_senior,
            "trust_labels": list(self.trust_labels),
            "foul_trouble": self.foul_trouble,
            "rules_applied": list(self.rules_applied),
            "exclusions": [reason.value for reason in self.exclusions],
            "methodology_rationale": self.rationale,
            "methodology_disposition": (
                None if self.disposition is None else self.disposition.value
            ),
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "meaningful_risk_ids": list(self.meaningful_risk_ids),
            "senior_lower_disclosure": self.senior_lower_disclosure,
            "methodology_sufficient_evidence": self.methodology_sufficient_evidence,
            "major_unresolved_concern": self.major_unresolved_concern,
            "senior_lower_support_ids": list(self.senior_lower_support_ids),
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
            "missed_snapshots": [marker.to_dict() for marker in self.missed_snapshots],
            "snapshot_run_id": self.snapshot_run_id,
            "stages": {
                "board_retrieval": (
                    "OBSERVED"
                    if self.rules_applied and "THREE_LEGITIMATE_SNAPSHOTS_REQUIRED" not in rules
                    else "INCOMPLETE"
                ),
                "identity": (
                    "UNRESOLVED"
                    if ReasonCode.PLAYER_IDENTITY_UNRESOLVED in self.exclusions
                    else "RESOLVED"
                ),
                "authorization": (
                    "ALLOWED"
                    if self.authorization_allowed
                    else "BLOCKED"
                    if self.status is EvaluationStatus.BLOCKED
                    else "NOT ESTABLISHED"
                ),
                "matchup_context": (
                    "RECORDED"
                    if kinds.intersection(
                        {
                            EvidenceKind.MATCHUP,
                            EvidenceKind.GAME_TOTAL,
                            EvidenceKind.POINT_SPREAD,
                            EvidenceKind.BLOWOUT_RISK,
                        }
                    )
                    else "MISSING"
                ),
                "role_minutes": "RECORDED" if EvidenceKind.ROLE_MINUTES in kinds else "MISSING",
                "senior_priority": "APPLIED" if "SENIOR_PRIORITY" in rules else "NOT_APPLICABLE",
                "non_senior_showoff": (
                    "APPLIED" if "NON_SENIOR_SHOWOFF_HEURISTIC" in rules else "NOT_APPLICABLE"
                ),
                "category_trust": "CLASSIFIED" if self.trust_labels else "NO_TRUST_LABEL",
                "foul_trouble": "CAUTION" if self.foul_trouble else "NO_ANNOTATION",
                "methodology": (self.status.value if self.authorization_allowed else "NOT_RUN"),
                "confidence": (
                    self.confidence.value if self.confidence is not None else "NOT_ASSIGNED"
                ),
            },
        }
        return {key: _redact_serialized_text(value) for key, value in serialized.items()}


class MethodologyError(ValueError):
    """Raised when an M6 assessment is malformed or contradicts frozen rules."""


def _redact_serialized_text(value: object) -> object:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [_redact_serialized_text(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_serialized_text(item) for key, item in value.items()}
    return value


def _canonicalize_gaps(gaps: Sequence[EvidenceGap]) -> tuple[EvidenceGap, ...]:
    significance_order = (
        EvidenceSignificance.MINOR,
        EvidenceSignificance.MEANINGFUL,
        EvidenceSignificance.IMPORTANT,
        EvidenceSignificance.CRITICAL,
    )
    strongest: dict[tuple[EvidenceKind, ReasonCode], tuple[int, list[EvidenceGap]]] = {}
    for gap in gaps:
        canonical = replace(gap, detail=redact_text(gap.detail))
        profile = (canonical.kind, canonical.reason)
        rank = significance_order.index(canonical.significance)
        existing = strongest.get(profile)
        if existing is None or rank > existing[0]:
            strongest[profile] = (rank, [canonical])
        elif rank == existing[0] and canonical not in existing[1]:
            existing[1].append(canonical)
    return tuple(
        sorted(
            (gap for _, values in strongest.values() for gap in values),
            key=lambda gap: (
                gap.kind.value,
                gap.reason.value,
                -significance_order.index(gap.significance),
                gap.detail,
            ),
        )
    )


def _canonicalize_judgment(
    judgment: MethodologyJudgment | None,
    evidence: tuple[EvidenceItem, ...],
) -> MethodologyJudgment | None:
    if judgment is None:
        return None
    canonical_ids = {item.evidence_id: redact_text(item.evidence_id) for item in evidence}

    def remap(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(canonical_ids.get(value, value) for value in values)

    return replace(
        judgment,
        rationale=redact_text(judgment.rationale),
        supporting_evidence_ids=tuple(sorted(remap(judgment.supporting_evidence_ids))),
        meaningful_risk_ids=tuple(sorted(remap(judgment.meaningful_risk_ids))),
        senior_lower_support_ids=tuple(sorted(remap(judgment.senior_lower_support_ids))),
        senior_lower_disclosure=redact_text(judgment.senior_lower_disclosure),
    )


def evaluate_candidate(
    case: CandidateCase,
) -> CandidateAudit:
    if not isinstance(case, CandidateCase) or not isinstance(case.snapshots, tuple):
        raise MethodologyError("case must contain a tuple of snapshot evidence")
    if (
        not isinstance(case.missed, tuple)
        or any(not isinstance(item, MissedSnapshot) for item in case.missed)
        or not isinstance(case.evidence, tuple)
        or any(not isinstance(item, EvidenceItem) for item in case.evidence)
        or not isinstance(case.gaps, tuple)
        or any(not isinstance(item, EvidenceGap) for item in case.gaps)
        or (case.judgment is not None and not isinstance(case.judgment, MethodologyJudgment))
        or (
            case.snapshot_run_id is not None
            and (not isinstance(case.snapshot_run_id, str) or not case.snapshot_run_id.strip())
        )
    ):
        raise MethodologyError("missed slots, evidence, and gaps must use their typed records")
    if not case.snapshots or any(not isinstance(item, SnapshotEvidence) for item in case.snapshots):
        raise MethodologyError("at least one valid snapshot is required to identify a candidate")

    snapshots_by_number = {item.snapshot.number: item for item in case.snapshots}
    if len(snapshots_by_number) != len(case.snapshots):
        raise MethodologyError("candidate snapshots contain a duplicate slot")
    snapshots = tuple(snapshots_by_number[number] for number in sorted(snapshots_by_number))
    latest = snapshots[-1]
    # Prior LIVE judgments are evaluated against the projection they actually saw.
    # The later snapshot remains in the case so M5 can verify the complete sequence.
    prior_live = case.supporting_slot == 2 and all(
        row.evidence_mode is EvidenceMode.LIVE for row in snapshots
    )
    baseline = snapshots_by_number.get(2, latest) if prior_live else latest
    observation = baseline.snapshot.observation
    movement_snapshots = (
        tuple(item for item in snapshots if item.snapshot.number <= 2) if prior_live else snapshots
    )
    candidate = Candidate(
        player=observation.player,
        platform=observation.platform,
        category=observation.category,
        direction=observation.direction,
        projection=observation.projection,
        event=observation.event,
    )
    candidate_id = latest.candidate_id
    candidate_key = latest.candidate_key
    for item in snapshots:
        observed = item.snapshot.observation
        if (
            item.candidate_id != candidate_id
            or item.candidate_key != candidate_key
            or observed.player != candidate.player
            or observed.platform is not candidate.platform
            or observed.category is not candidate.category
            or observed.direction is not candidate.direction
            or observed.event != candidate.event
            or canonical_player_id(observed.player) != candidate_id
        ):
            raise MethodologyError("snapshot records do not identify one canonical candidate")
    configs = load_configs()
    all_live = all(item.evidence_mode is EvidenceMode.LIVE for item in snapshots)
    registry_player = Registry.from_universe(configs.approved_universe).player_by_id(candidate_id)
    provider_names_match = registry_player is not None and all(
        item.source_excerpt["provider_player_name"]
        in (registry_player.canonical_name, *registry_player.aliases)
        for item in snapshots
    )
    if (
        registry_player is None
        or registry_player.canonical_name != candidate.player
        or candidate_id != canonical_player_id(candidate.player)
        or (not provider_names_match and not all_live)
    ):
        return CandidateAudit(
            candidate=candidate,
            candidate_id=candidate_id,
            candidate_key=candidate_key,
            status=EvaluationStatus.BLOCKED,
            confidence=None,
            evidence_mode=_evidence_mode(tuple(item.evidence_mode for item in snapshots)),
            movement=None,
            history=(),
            evidence=(),
            gaps=(),
            is_senior=False,
            trust_labels=(),
            foul_trouble=False,
            rules_applied=("AUTHORIZATION_FIRST", "NO_NUMERIC_CONFIDENCE_WEIGHTS"),
            exclusions=(ReasonCode.PLAYER_IDENTITY_UNRESOLVED,),
            rationale="candidate does not match an exact canonical registry identity",
        )

    authorization = AuthorizationGate().authorize(
        candidate_id, candidate.category, candidate.direction
    )
    evidence_mode = _evidence_mode(tuple(item.evidence_mode for item in snapshots))
    rules = ["AUTHORIZATION_FIRST", "NO_NUMERIC_CONFIDENCE_WEIGHTS"]
    reasons: list[ReasonCode] = []

    if not authorization.allowed:
        has_all_snapshots = tuple(sorted(snapshots_by_number)) == (1, 2, 3)
        return CandidateAudit(
            candidate=candidate,
            candidate_id=candidate_id,
            candidate_key=candidate_key,
            status=EvaluationStatus.BLOCKED,
            confidence=None,
            evidence_mode=evidence_mode,
            movement=_projection_movement(snapshots) if has_all_snapshots else None,
            history=(),
            evidence=(),
            gaps=(),
            is_senior=False,
            trust_labels=(),
            foul_trouble=False,
            rules_applied=tuple(rules),
            exclusions=(authorization.reason or ReasonCode.CATEGORY_NOT_AUTHORIZED,),
            rationale=authorization.detail,
        )

    has_live_snapshots = any(item.evidence_mode is EvidenceMode.LIVE for item in snapshots)
    snapshot_run_id: str | None = None
    if has_live_snapshots:
        if not case.snapshot_run_id:
            raise MethodologyError("LIVE snapshots require their validated M5 run ledger")
        try:
            ledger_records = read_application_snapshot_ledger(case.snapshot_run_id)
            ledger_snapshots = tuple(
                item
                for item in ledger_records
                if isinstance(item, SnapshotEvidence)
                if item.candidate_key == candidate_key
            )
            ledger_missed = tuple(
                item
                for item in ledger_records
                if isinstance(item, MissedSnapshot)
                if item.candidate_key == candidate_key
            )
        except StorageError as exc:
            raise MethodologyError("LIVE snapshots could not be read from the M5 ledger") from exc
        snapshots_match = tuple(sorted(snapshots, key=lambda item: item.snapshot.number)) == tuple(
            sorted(ledger_snapshots, key=lambda item: item.snapshot.number)
        )
        missed_match = tuple(sorted(case.missed, key=lambda item: item.number)) == tuple(
            sorted(ledger_missed, key=lambda item: item.number)
        )
        if not snapshots_match or not missed_match:
            raise MethodologyError("LIVE snapshots do not match their validated M5 ledger records")
        if not provider_names_match:
            from fifth_pick.board_collection import live_slot_has_bound_aliases

            if any(
                not live_slot_has_bound_aliases(
                    case.snapshot_run_id, item.snapshot.number, item.event_id
                )
                for item in snapshots
            ):
                raise MethodologyError("LIVE provider alias is not bound to a completed board slot")
        snapshot_run_id = case.snapshot_run_id

    try:
        snapshot_records = validate_snapshot_sequence(snapshots, case.missed)
    except SnapshotError as exc:
        raise MethodologyError("candidate snapshot sequence violates the M5 contract") from exc
    canonical_missed = tuple(item for item in snapshot_records if isinstance(item, MissedSnapshot))
    canonical_gaps = _canonicalize_gaps(case.gaps)

    if tuple(sorted(snapshots_by_number)) != (1, 2, 3):
        missed = next(
            (
                item
                for item in snapshot_records
                if isinstance(item, MissedSnapshot) and item.number in (1, 2, 3)
            ),
            None,
        )
        reasons.append(
            ReasonCode.PROJECTION_OBSERVATION_MISSED if missed is None else missed.reason
        )
        return CandidateAudit(
            candidate=candidate,
            candidate_id=candidate_id,
            candidate_key=candidate_key,
            status=EvaluationStatus.INSUFFICIENT_EVIDENCE,
            confidence=None,
            evidence_mode=evidence_mode,
            movement=None,
            history=(),
            evidence=(),
            gaps=canonical_gaps,
            is_senior=False,
            trust_labels=(),
            foul_trouble=False,
            rules_applied=tuple((*rules, "THREE_LEGITIMATE_SNAPSHOTS_REQUIRED")),
            exclusions=tuple(reasons),
            rationale="Three legitimate, non-backfilled projection snapshots are required.",
            authorization_allowed=True,
            snapshots=snapshots,
            missed_snapshots=canonical_missed,
            snapshot_run_id=snapshot_run_id,
        )

    evidence_mode = _evidence_mode(
        tuple(item.evidence_mode for item in snapshots)
        + tuple(item.evidence_mode for item in case.evidence)
    )
    try:
        verified_live = ()
        if all_live and any(item.evidence_mode is EvidenceMode.LIVE for item in case.evidence):
            supporting_snapshot = snapshots_by_number.get(case.supporting_slot or 0)
            if (
                snapshot_run_id is None
                or case.supporting_slot not in (2, 3)
                or not isinstance(case.supporting_as_of, datetime)
                or supporting_snapshot is None
                or supporting_snapshot.late
                or any(
                    item.evidence.provenance.retrieved_at
                    < supporting_snapshot.snapshot.observation.retrieved_at
                    for item in case.evidence
                )
            ):
                raise EvidenceError("LIVE supporting evidence requires an exact run and stage")
            from fifth_pick.live_analysis import read_live_supporting_items

            verified_live = read_live_supporting_items(
                snapshot_run_id,
                candidate_key,
                latest.event_id,
                slot=case.supporting_slot,
                as_of=case.supporting_as_of,
                player_id=candidate_id,
                category=candidate.category,
            )
        evidence = _validate_evidence_items(
            case.evidence,
            candidate_key=candidate_key,
            verified_live=verified_live,
        )
    except EvidenceError as exc:
        return CandidateAudit(
            candidate=candidate,
            candidate_id=candidate_id,
            candidate_key=candidate_key,
            status=EvaluationStatus.INSUFFICIENT_EVIDENCE,
            confidence=None,
            evidence_mode=evidence_mode,
            movement=_projection_movement(movement_snapshots),
            history=(),
            evidence=(),
            gaps=canonical_gaps,
            is_senior=False,
            trust_labels=(),
            foul_trouble=False,
            rules_applied=tuple((*rules, "SUPPORTING_EVIDENCE_VALIDATED")),
            exclusions=(ReasonCode.SOURCE_CONFLICT_UNRESOLVED,),
            rationale=redact_text(f"Supporting evidence failed validation: {exc}"),
            authorization_allowed=True,
            snapshots=snapshots,
            snapshot_run_id=snapshot_run_id,
        )

    judgment = _canonicalize_judgment(case.judgment, case.evidence)
    player = candidate_id
    senior_ids = {canonical_player_id(name) for name in configs.trust_tiers.senior}
    is_senior = player in senior_ids
    trust_labels = _trust_labels(player, candidate.category, configs)
    foul_trouble = any(item.kind is EvidenceKind.FOUL_TROUBLE for item in evidence)
    foul_trouble = foul_trouble or (
        False if registry_player is None else registry_player.foul_trouble
    )
    history = _history_summaries(evidence, candidate, event_start=snapshots[0].event_start)
    gaps = list(canonical_gaps)
    summaries = {summary.kind: summary for summary in history}
    last8 = summaries.get(EvidenceKind.LAST_8)
    if (last8 is None or last8.incomplete) and not any(
        gap.kind is EvidenceKind.LAST_8 for gap in gaps
    ):
        detail = (
            "last-eight history was not supplied."
            if last8 is None
            else f"last-eight history contains {last8.sample_count} of 8 games."
        )
        gaps.append(
            EvidenceGap(
                kind=EvidenceKind.LAST_8,
                reason=ReasonCode.INSUFFICIENT_SUPPORTING_EVIDENCE,
                significance=EvidenceSignificance.MINOR,
                detail=detail,
            )
        )
    h2h = summaries.get(EvidenceKind.SAME_SEASON_H2H)
    if (h2h is None or h2h.incomplete) and not any(
        gap.kind is EvidenceKind.SAME_SEASON_H2H for gap in gaps
    ):
        detail = (
            "same-season head-to-head history was not supplied."
            if h2h is None
            else "no same-season head-to-head samples matched today's opponent."
        )
        gaps.append(
            EvidenceGap(
                kind=EvidenceKind.SAME_SEASON_H2H,
                reason=ReasonCode.INSUFFICIENT_SUPPORTING_EVIDENCE,
                significance=EvidenceSignificance.MINOR,
                detail=detail,
            )
        )
    gaps = _canonicalize_gaps(gaps)
    movement = _projection_movement(movement_snapshots)
    rules.extend(("SNAPSHOT_INTEGRITY_VALIDATED", "SUPPORTING_EVIDENCE_VALIDATED"))
    if is_senior and candidate.direction is Direction.HIGHER:
        rules.append("SENIOR_PRIORITY")
    if not is_senior and candidate.category is Category.POINTS:
        rules.append("NON_SENIOR_SHOWOFF_HEURISTIC")
    if trust_labels:
        rules.append("CATEGORY_TRUST_CLASSIFIED_AFTER_AUTHORIZATION")
    if foul_trouble:
        rules.append("FOUL_TROUBLE_CAUTION")

    critical_gaps = tuple(gap for gap in gaps if gap.significance is EvidenceSignificance.CRITICAL)
    if critical_gaps:
        return CandidateAudit(
            candidate=candidate,
            candidate_id=candidate_id,
            candidate_key=candidate_key,
            status=EvaluationStatus.INSUFFICIENT_EVIDENCE,
            confidence=None,
            evidence_mode=evidence_mode,
            movement=movement,
            history=history,
            evidence=evidence,
            gaps=gaps,
            is_senior=is_senior,
            trust_labels=trust_labels,
            foul_trouble=foul_trouble,
            rules_applied=tuple(rules),
            exclusions=tuple(dict.fromkeys(gap.reason for gap in critical_gaps)),
            rationale="Critical evidence gaps prevent a confidence judgment.",
            authorization_allowed=True,
            snapshots=snapshots,
            snapshot_run_id=snapshot_run_id,
        )

    if judgment is None or not judgment.sufficient_evidence:
        return CandidateAudit(
            candidate=candidate,
            candidate_id=candidate_id,
            candidate_key=candidate_key,
            status=EvaluationStatus.INSUFFICIENT_EVIDENCE,
            confidence=None,
            evidence_mode=evidence_mode,
            movement=movement,
            history=history,
            evidence=evidence,
            gaps=gaps,
            is_senior=is_senior,
            trust_labels=trust_labels,
            foul_trouble=foul_trouble,
            rules_applied=tuple(rules),
            exclusions=(ReasonCode.INSUFFICIENT_SUPPORTING_EVIDENCE,),
            rationale=(
                "No sufficient methodology judgment was supplied."
                if judgment is None
                else judgment.rationale
            ),
            authorization_allowed=True,
            snapshots=snapshots,
            snapshot_run_id=snapshot_run_id,
        )

    _validate_judgment_evidence(judgment, evidence, gaps)

    if is_senior and candidate.direction is Direction.LOWER:
        if not _senior_lower_context_supported(judgment, candidate, evidence):
            return CandidateAudit(
                candidate=candidate,
                candidate_id=candidate_id,
                candidate_key=candidate_key,
                status=EvaluationStatus.INSUFFICIENT_EVIDENCE,
                confidence=None,
                evidence_mode=evidence_mode,
                movement=movement,
                history=history,
                evidence=evidence,
                gaps=gaps,
                is_senior=is_senior,
                trust_labels=trust_labels,
                foul_trouble=foul_trouble,
                rules_applied=tuple((*rules, "SENIOR_LOWER_CONTEXT_REQUIRED")),
                exclusions=(ReasonCode.INSUFFICIENT_SUPPORTING_EVIDENCE,),
                rationale=(
                    "Senior LOWER requires cited blowout/reduced-minutes support and disclosure."
                ),
                authorization_allowed=True,
                disposition=judgment.disposition,
                supporting_evidence_ids=judgment.supporting_evidence_ids,
                meaningful_risk_ids=judgment.meaningful_risk_ids,
                senior_lower_disclosure=judgment.senior_lower_disclosure,
                methodology_sufficient_evidence=judgment.sufficient_evidence,
                major_unresolved_concern=judgment.major_unresolved_concern,
                senior_lower_support_ids=judgment.senior_lower_support_ids,
                snapshots=snapshots,
                snapshot_run_id=snapshot_run_id,
            )
        rules.append("SENIOR_LOWER_CONTEXT_REQUIRED")

    status = _status_for_judgment(judgment)
    rationale = judgment.rationale
    if judgment.senior_lower_disclosure:
        rationale = f"{rationale} Senior LOWER risk: {judgment.senior_lower_disclosure}"
    return CandidateAudit(
        candidate=candidate,
        candidate_id=candidate_id,
        candidate_key=candidate_key,
        status=status,
        confidence=judgment.confidence,
        evidence_mode=evidence_mode,
        movement=movement,
        history=history,
        evidence=evidence,
        gaps=gaps,
        is_senior=is_senior,
        trust_labels=trust_labels,
        foul_trouble=foul_trouble,
        rules_applied=tuple(rules),
        exclusions=tuple(gap.reason for gap in gaps),
        rationale=rationale,
        authorization_allowed=True,
        disposition=judgment.disposition,
        supporting_evidence_ids=judgment.supporting_evidence_ids,
        meaningful_risk_ids=judgment.meaningful_risk_ids,
        senior_lower_disclosure=judgment.senior_lower_disclosure,
        methodology_sufficient_evidence=judgment.sufficient_evidence,
        major_unresolved_concern=judgment.major_unresolved_concern,
        senior_lower_support_ids=judgment.senior_lower_support_ids,
        snapshots=snapshots,
        snapshot_run_id=snapshot_run_id,
    )


def _validate_judgment_evidence(
    judgment: MethodologyJudgment,
    evidence: tuple[EvidenceItem, ...],
    gaps: tuple[EvidenceGap, ...],
) -> None:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    if len(set(judgment.supporting_evidence_ids)) != len(judgment.supporting_evidence_ids):
        raise MethodologyError("supporting evidence IDs must be unique")
    if len(set(judgment.meaningful_risk_ids)) != len(judgment.meaningful_risk_ids):
        raise MethodologyError("meaningful risk IDs must be unique")
    supporting: list[EvidenceItem] = []
    for evidence_id in judgment.supporting_evidence_ids:
        item = evidence_by_id.get(evidence_id)
        if item is None or item.effect is not EvidenceEffect.SUPPORTS:
            raise MethodologyError(
                "supporting evidence IDs must cite validated supporting evidence"
            )
        supporting.append(item)
    for evidence_id in judgment.meaningful_risk_ids:
        item = evidence_by_id.get(evidence_id)
        if item is None or item.effect not in (EvidenceEffect.CONCERN, EvidenceEffect.CONFLICT):
            raise MethodologyError("meaningful risk IDs must cite validated concern or conflict")

    if judgment.confidence is Confidence.HIGH:
        important_aligned = {
            _evidence_signal_signature(item)
            for item in supporting
            if item.significance is EvidenceSignificance.IMPORTANT
        }
        critical_conflict = any(
            item.effect in (EvidenceEffect.CONCERN, EvidenceEffect.CONFLICT)
            and item.significance is EvidenceSignificance.CRITICAL
            for item in evidence
        )
        meaningful_gap = any(gap.significance is EvidenceSignificance.MEANINGFUL for gap in gaps)
        if (
            not judgment.sufficient_evidence
            or len(important_aligned) < 2
            or judgment.major_unresolved_concern
            or critical_conflict
            or meaningful_gap
        ):
            raise MethodologyError(
                "HIGH confidence requires sufficient evidence, multiple important aligned "
                "signals, and no major unresolved concern"
            )
    elif judgment.confidence is Confidence.MEDIUM:
        cited_risk = any(
            evidence_by_id[evidence_id].significance
            in (EvidenceSignificance.MEANINGFUL, EvidenceSignificance.CRITICAL)
            for evidence_id in judgment.meaningful_risk_ids
        )
        if (
            not judgment.sufficient_evidence
            or not cited_risk
            and not any(gap.significance is EvidenceSignificance.MEANINGFUL for gap in gaps)
        ):
            raise MethodologyError(
                "MEDIUM confidence requires sufficient evidence and a disclosed meaningful "
                "risk or conflict"
            )


def _evidence_signal_signature(item: EvidenceItem) -> tuple[object, ...]:
    provenance = item.evidence.provenance
    return (
        item.effect.value,
        item.significance.value,
        item.evidence.claim,
        item.evidence.excerpt,
        provenance.source,
        provenance.retrieved_at.isoformat(),
        provenance.source_timestamp.isoformat(),
        provenance.access_method,
        provenance.reference,
        provenance.payload_hash,
        tuple(sorted((item.facts or {}).items())),
        tuple(
            sorted(
                (
                    sample.played_at.isoformat(),
                    sample.value,
                    sample.opponent,
                    sample.season,
                )
                for sample in item.samples
            )
        ),
    )


def _senior_lower_context_supported(
    judgment: MethodologyJudgment,
    candidate: Candidate,
    evidence: tuple[EvidenceItem, ...],
) -> bool:
    contextual_support = any(
        item.evidence_id in judgment.senior_lower_support_ids
        and item.evidence_id in judgment.supporting_evidence_ids
        and item.effect is EvidenceEffect.SUPPORTS
        and item.significance in (EvidenceSignificance.IMPORTANT, EvidenceSignificance.MEANINGFUL)
        and item.kind in (EvidenceKind.BLOWOUT_RISK, EvidenceKind.ROLE_MINUTES)
        for item in evidence
    )
    return (
        candidate.direction is not Direction.LOWER
        or judgment.confidence is not Confidence.LOW
        and contextual_support
        and bool(judgment.senior_lower_disclosure.strip())
    )


def _status_for_judgment(judgment: MethodologyJudgment) -> EvaluationStatus:
    if not judgment.sufficient_evidence:
        return EvaluationStatus.INSUFFICIENT_EVIDENCE
    if judgment.disposition is MethodologyDisposition.REJECT:
        return EvaluationStatus.REJECTED
    if (
        judgment.disposition is MethodologyDisposition.ANALYSIS_ONLY
        or judgment.confidence is Confidence.LOW
    ):
        return EvaluationStatus.ANALYSIS_ONLY
    return EvaluationStatus.QUALIFIED


def _evidence_mode(modes: tuple[EvidenceMode, ...]) -> AuditEvidenceMode:
    values = {mode.value for mode in modes}
    if len(values) > 1:
        return AuditEvidenceMode.MIXED
    if values == {"live"}:
        return AuditEvidenceMode.LIVE
    return AuditEvidenceMode.FIXTURE


def _projection_movement(snapshots: tuple[SnapshotEvidence, ...]) -> ProjectionMovement:
    values = tuple(item.snapshot.observation.projection for item in snapshots)
    rises = tuple(right - left for left, right in zip(values, values[1:], strict=False))
    if all(change == 0 for change in rises):
        return ProjectionMovement.STABLE
    if all(change >= 0 for change in rises):
        return ProjectionMovement.RISING
    if all(change <= 0 for change in rises):
        return ProjectionMovement.FALLING
    return ProjectionMovement.FLUCTUATING


def _history_summaries(
    evidence: tuple[EvidenceItem, ...], candidate: Candidate, *, event_start: datetime | None = None
) -> tuple[HistorySummary, ...]:
    matchup = next((item for item in evidence if item.kind is EvidenceKind.MATCHUP), None)
    facts = {} if matchup is None else matchup.facts or {}
    season = facts.get("season")
    opponent = facts.get("opponent")
    summaries = []
    for item in evidence:
        if item.kind is EvidenceKind.LAST_8:
            summaries.append(
                summarize_history(
                    item,
                    line=candidate.projection,
                    direction=candidate.direction,
                    current_season=str(season or "unknown"),
                    opponent=str(opponent or "unknown"),
                )
            )
        elif item.kind is EvidenceKind.SAME_SEASON_H2H:
            h2h_season, h2h_opponent = season, opponent
            if (
                matchup is None
                and item.evidence_mode is EvidenceMode.LIVE
                and event_start is not None
                and event_start.utcoffset() is not None
                and item.facts is not None
                and item.facts.get("event_id") == candidate.event
                and item.facts.get("corroboration_sha256")
            ):
                # The LIVE history reader already restricted these rows to the
                # independently corroborated event opponent and requested season.
                scopes = {(sample.season, sample.opponent) for sample in item.samples}
                chicago = event_start.astimezone(ZoneInfo("America/Chicago"))
                year = chicago.year if chicago.month >= 10 else chicago.year - 1
                expected = f"{year}-{(year + 1) % 100:02d}"
                if len(scopes) == 1 and all(
                    sample.played_at < event_start for sample in item.samples
                ):
                    ((recorded_season, recorded_opponent),) = scopes
                    if recorded_season == expected:
                        h2h_season, h2h_opponent = recorded_season, recorded_opponent
            if h2h_season and h2h_opponent:
                summaries.append(
                    summarize_history(
                        item,
                        line=candidate.projection,
                        direction=candidate.direction,
                        current_season=str(h2h_season),
                        opponent=str(h2h_opponent),
                    )
                )
    return tuple(sorted(summaries, key=lambda summary: summary.kind.value))


def _trust_labels(player_id: str, category: Category, configs) -> tuple[str, ...]:
    trusted_by_category = {
        "PRA": configs.trust_tiers.pra_trust,
        "ASSISTS": configs.trust_tiers.assist_trust,
        "REBOUNDS": configs.trust_tiers.rebound_trust,
    }
    names = trusted_by_category.get(category.value, ())
    return (
        (f"{category.value}_TRUST",)
        if player_id in {canonical_player_id(name) for name in names}
        else ()
    )


def _evaluate_candidate_cases(
    cases: tuple[CandidateCase, ...],
) -> tuple[CandidateAudit, ...]:
    if not isinstance(cases, tuple) or any(not isinstance(case, CandidateCase) for case in cases):
        raise MethodologyError("cases must be a tuple of CandidateCase records")
    return tuple(evaluate_candidate(case) for case in cases)
