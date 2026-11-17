"""M6 evidence-based ranking without numerical scoring or slate finalization."""

import json
from dataclasses import dataclass
from functools import cmp_to_key
from pathlib import Path

from fifth_pick.errors import StorageError
from fifth_pick.evidence import (
    EvidenceEffect,
    EvidenceKind,
    EvidenceSignificance,
)
from fifth_pick.methodology import (
    CandidateAudit,
    CandidateCase,
    Confidence,
    EvaluationStatus,
    _evaluate_candidate_cases,
)
from fifth_pick.models import Direction, ReasonCode
from fifth_pick.receipts import redact_text
from fifth_pick.snapshots import SnapshotEvidence
from fifth_pick.storage import RunStore, _atomic_write


class RankingError(ValueError):
    """Raised when a ranking or discretionary tie-break is invalid."""


@dataclass(frozen=True, slots=True)
class NearTieDecision:
    candidate_keys: tuple[str, str]
    preferred_order: tuple[str, str]
    rationale: str
    evidence_ids: tuple[str, ...]
    one_slot_remains: bool


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    rank: int
    audit: CandidateAudit
    reason: str


@dataclass(frozen=True, slots=True)
class RankingResult:
    ranked: tuple[RankedCandidate, ...]
    audits: tuple[CandidateAudit, ...]

    @property
    def zero_qualified_candidates(self) -> bool:
        return not self.ranked

    def to_dict(self) -> dict[str, object]:
        return {
            "ranked": [
                {
                    "rank": item.rank,
                    "candidate_key": item.audit.candidate_key,
                    "reason": item.reason,
                    "audit": item.audit.to_dict(),
                }
                for item in self.ranked
            ],
            "audits": [audit.to_dict() for audit in self.audits],
            "zero_qualified_candidates": self.zero_qualified_candidates,
        }


def rank_candidates(
    cases: tuple[CandidateCase, ...],
    *,
    tie_breaks: tuple[NearTieDecision, ...] = (),
) -> RankingResult:
    if not isinstance(cases, tuple) or any(not isinstance(case, CandidateCase) for case in cases):
        raise RankingError("ranking requires a tuple of CandidateCase records")
    if not isinstance(tie_breaks, tuple) or any(
        not isinstance(decision, NearTieDecision) for decision in tie_breaks
    ):
        raise RankingError("tie_breaks must contain NearTieDecision records")
    audits = _evaluate_candidate_cases(cases)

    candidate_keys = tuple(audit.candidate_key for audit in audits)
    if len(set(candidate_keys)) != len(candidate_keys):
        raise RankingError("audits contain duplicate candidate keys")

    eligible = []
    for audit in audits:
        if (
            audit.status is EvaluationStatus.QUALIFIED
            and audit.confidence in (Confidence.HIGH, Confidence.MEDIUM)
            and audit.authorization_allowed
        ):
            eligible.append(audit)
    eligible.sort(key=cmp_to_key(_compare_candidates))
    reasons = {audit.candidate_key: _ranking_reason(audit) for audit in eligible}
    tie_broken_keys: set[str] = set()

    for decision in tie_breaks:
        if (
            not isinstance(decision.candidate_keys, tuple)
            or len(decision.candidate_keys) != 2
            or any(not isinstance(key, str) or not key.strip() for key in decision.candidate_keys)
            or not isinstance(decision.preferred_order, tuple)
            or len(decision.preferred_order) != 2
            or any(not isinstance(key, str) or not key.strip() for key in decision.preferred_order)
            or not isinstance(decision.evidence_ids, tuple)
            or any(not isinstance(item, str) or not item.strip() for item in decision.evidence_ids)
            or not isinstance(decision.rationale, str)
            or not isinstance(decision.one_slot_remains, bool)
        ):
            raise RankingError("near-tie decision fields are malformed")
        first_key, second_key = decision.candidate_keys
        if first_key in tie_broken_keys or second_key in tie_broken_keys:
            raise RankingError("near-tie decisions cannot overlap")
        tied = {audit.candidate_key: audit for audit in eligible}
        first = tied.get(first_key)
        second = tied.get(second_key)
        if (
            first is None
            or second is None
            or first_key == second_key
            or decision.preferred_order
            not in (
                (first_key, second_key),
                (second_key, first_key),
            )
            or not decision.one_slot_remains
            or not decision.rationale.strip()
            or not decision.evidence_ids
            or first.is_senior
            or second.is_senior
            or first.confidence is not second.confidence
            or _evidence_signature(first) != _evidence_signature(second)
        ):
            raise RankingError(
                "near-tie discretion requires two comparable non-Senior candidates, "
                "one remaining slot, cited evidence, and an explanation"
            )
        evidence_ids = tuple(redact_text(item) for item in decision.evidence_ids)
        available_evidence = {item.evidence_id for item in (*first.evidence, *second.evidence)}
        if not set(evidence_ids) <= available_evidence:
            raise RankingError("near-tie decision cites evidence outside the compared candidates")
        tie_broken_keys.update((first_key, second_key))
        preferred_first, preferred_second = decision.preferred_order
        first_index = next(
            index for index, audit in enumerate(eligible) if audit.candidate_key == first_key
        )
        second_index = next(
            index for index, audit in enumerate(eligible) if audit.candidate_key == second_key
        )
        if abs(first_index - second_index) != 1:
            raise RankingError(
                "near-tie candidates must be adjacent; reordering cannot cross a candidate"
            )
        left_index = min(first_index, second_index)
        eligible[left_index], eligible[left_index + 1] = (
            tied[preferred_first],
            tied[preferred_second],
        )
        explanation = (
            f"Non-Senior near-tie discretion: {redact_text(decision.rationale)} "
            f"(evidence: {', '.join(evidence_ids)})"
        )
        reasons[preferred_first] = explanation
        reasons[preferred_second] = explanation

    ranked = tuple(
        RankedCandidate(rank=index, audit=audit, reason=reasons[audit.candidate_key])
        for index, audit in enumerate(eligible, start=1)
    )
    return RankingResult(ranked=ranked, audits=audits)


def write_candidates(
    cases: tuple[CandidateCase, ...],
    store: RunStore,
    run_id: str,
    *,
    tie_breaks: tuple[NearTieDecision, ...] = (),
) -> Path:
    """Evaluate candidate cases, rank their internal audits, and persist the run audit."""

    if not isinstance(store, RunStore):
        raise RankingError("store must be a RunStore")
    result = rank_candidates(
        cases,
        tie_breaks=tie_breaks,
    )
    run_directory = store.run_directory(run_id)
    path = run_directory / "candidates.json"
    if not path.resolve().is_relative_to(run_directory):
        raise RankingError("candidate artifact path escapes the run directory")
    content = json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    try:
        _atomic_write(path, content.encode("utf-8"))
    except OSError as exc:
        raise StorageError(f"cannot write candidate artifact for run {run_id!r}") from exc
    return path


def _evidence_signature(audit: CandidateAudit) -> tuple[object, ...]:
    candidate_context = (
        audit.candidate.platform.value,
        audit.candidate.category.value,
        audit.candidate.direction.value,
        audit.candidate.event,
        audit.candidate.projection,
        audit.snapshot_run_id,
        None if audit.movement is None else audit.movement.value,
        audit.trust_labels,
        audit.foul_trouble,
    )
    snapshot_path = tuple(_snapshot_signature(item) for item in audit.snapshots)
    evidence_signals = tuple(
        sorted(
            (
                item.kind.value,
                item.effect.value,
                item.significance.value,
                item.evidence.claim,
                item.evidence.excerpt,
                item.evidence.provenance.source,
                item.evidence.provenance.retrieved_at.isoformat(),
                item.evidence.provenance.source_timestamp.isoformat(),
                item.evidence.provenance.access_method,
                item.evidence.provenance.reference,
                item.evidence.provenance.payload_hash,
                json.dumps(dict(item.facts or {}), ensure_ascii=False, sort_keys=True),
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
            for item in audit.evidence
        )
    )
    history = tuple(
        sorted(
            (
                item.kind.value,
                item.sample_count,
                item.higher_count,
                item.lower_count,
                item.push_count,
                item.favorable_count,
                item.unfavorable_count,
                item.incomplete,
                item.outcomes,
            )
            for item in audit.history
        )
    )
    gaps = tuple(
        sorted(
            (gap.kind.value, gap.reason.value, gap.significance.value, gap.detail)
            for gap in audit.gaps
        )
    )
    return candidate_context, snapshot_path, evidence_signals, history, gaps


def _snapshot_signature(snapshot: SnapshotEvidence) -> tuple[object, ...]:
    observation = snapshot.snapshot.observation
    provenance = snapshot.provenance
    excerpt = dict(snapshot.source_excerpt)
    excerpt.pop("provider_player_name", None)
    return (
        snapshot.snapshot.number,
        snapshot.evidence_mode.value,
        snapshot.event_id,
        snapshot.event_start.isoformat(),
        None if snapshot.target_at is None else snapshot.target_at.isoformat(),
        snapshot.late,
        snapshot.snapshot.recorded_at.isoformat(),
        observation.platform.value,
        observation.category.value,
        observation.direction.value,
        observation.event,
        observation.projection,
        observation.source_update_time.isoformat(),
        observation.retrieved_at.isoformat(),
        observation.source,
        observation.multiplier,
        provenance.source,
        provenance.retrieved_at.isoformat(),
        provenance.source_timestamp.isoformat(),
        provenance.access_method,
        provenance.reference,
        provenance.payload_hash,
        json.dumps(excerpt, ensure_ascii=False, sort_keys=True),
    )


def _compare_candidates(first: CandidateAudit, second: CandidateAudit) -> int:
    first_senior_priority = first.is_senior and first.candidate.direction is Direction.HIGHER
    second_senior_priority = second.is_senior and second.candidate.direction is Direction.HIGHER
    if first_senior_priority != second_senior_priority:
        return -1 if first_senior_priority else 1
    if first.confidence is not second.confidence:
        return -1 if first.confidence is Confidence.HIGH else 1
    return _compare_evidence_strength(first, second)


def _compare_evidence_strength(first: CandidateAudit, second: CandidateAudit) -> int:
    relations: list[int | None] = []
    if first.foul_trouble != second.foul_trouble:
        relations.append(1 if first.foul_trouble else -1)

    first_support = _support_profile(first)
    second_support = _support_profile(second)
    for kind in first_support.keys() | second_support.keys():
        left = first_support.get(kind)
        right = second_support.get(kind)
        relations.append(_compare_positive_signal(left, right))

    first_risks = _risk_profile(first)
    second_risks = _risk_profile(second)
    for kind in first_risks.keys() | second_risks.keys():
        left = first_risks.get(kind)
        right = second_risks.get(kind)
        relations.append(_compare_risk_signal(left, right))

    first_gaps = _gap_profile(first)
    second_gaps = _gap_profile(second)
    for kind in first_gaps.keys() | second_gaps.keys():
        left = first_gaps.get(kind)
        right = second_gaps.get(kind)
        relations.append(_compare_gap_signal(left, right))

    first_history = {item.kind: item for item in first.history}
    second_history = {item.kind: item for item in second.history}
    for kind in first_history.keys() | second_history.keys():
        left = first_history.get(kind)
        right = second_history.get(kind)
        relations.append(_compare_history(left, right))

    return _dominant_relation(relations)


def _support_profile(audit: CandidateAudit) -> dict[EvidenceKind, EvidenceSignificance]:
    result: dict[EvidenceKind, EvidenceSignificance] = {}
    for item in audit.evidence:
        if item.effect is EvidenceEffect.SUPPORTS:
            existing = result.get(item.kind)
            if existing is None or _compare_significance(item.significance, existing) < 0:
                result[item.kind] = item.significance
    return result


def _risk_profile(
    audit: CandidateAudit,
) -> dict[EvidenceKind, dict[EvidenceEffect, EvidenceSignificance]]:
    result: dict[EvidenceKind, dict[EvidenceEffect, EvidenceSignificance]] = {}
    for item in audit.evidence:
        if item.effect not in (EvidenceEffect.CONCERN, EvidenceEffect.CONFLICT):
            continue
        profile = result.setdefault(item.kind, {})
        existing = profile.get(item.effect)
        if existing is None or _compare_significance(item.significance, existing) < 0:
            profile[item.effect] = item.significance
    return result


def _gap_profile(
    audit: CandidateAudit,
) -> dict[EvidenceKind, dict[ReasonCode, EvidenceSignificance]]:
    result: dict[EvidenceKind, dict[ReasonCode, EvidenceSignificance]] = {}
    for gap in audit.gaps:
        profile = result.setdefault(gap.kind, {})
        existing = profile.get(gap.reason)
        if existing is None or _compare_significance(gap.significance, existing) < 0:
            profile[gap.reason] = gap.significance
    return result


def _compare_positive_signal(
    first: EvidenceSignificance | None,
    second: EvidenceSignificance | None,
) -> int | None:
    if first is None:
        return 1 if second is not None else 0
    if second is None:
        return -1
    return _compare_significance(first, second)


def _compare_risk_signal(
    first: dict[EvidenceEffect, EvidenceSignificance] | None,
    second: dict[EvidenceEffect, EvidenceSignificance] | None,
) -> int | None:
    if first is None:
        return 0 if second is None else -1
    if second is None:
        return 1
    relations = []
    for effect in first.keys() | second.keys():
        left = first.get(effect)
        right = second.get(effect)
        if left is None:
            relations.append(-1)
        elif right is None:
            relations.append(1)
        else:
            relations.append(-_compare_significance(left, right))
    return _dominant_relation(relations)


def _compare_gap_signal(
    first: dict[ReasonCode, EvidenceSignificance] | None,
    second: dict[ReasonCode, EvidenceSignificance] | None,
) -> int | None:
    if first is None:
        return 0 if second is None else -1
    if second is None:
        return 1
    relations = []
    for reason in first.keys() | second.keys():
        left = first.get(reason)
        right = second.get(reason)
        if left is None:
            relations.append(-1)
        elif right is None:
            relations.append(1)
        else:
            relations.append(-_compare_significance(left, right))
    return _dominant_relation(relations)


def _compare_history(first, second) -> int | None:
    if first is None or second is None:
        return 0
    if first.kind is not second.kind:
        return None
    if first.incomplete is not second.incomplete:
        return 1 if first.incomplete else -1
    if first.sample_count != second.sample_count:
        return None
    relations = [
        -1
        if first.favorable_count > second.favorable_count
        else 1
        if first.favorable_count < second.favorable_count
        else 0,
        -1
        if first.unfavorable_count < second.unfavorable_count
        else 1
        if first.unfavorable_count > second.unfavorable_count
        else 0,
    ]
    return _dominant_relation(relations)


def _compare_significance(
    first: EvidenceSignificance,
    second: EvidenceSignificance,
) -> int:
    if first is second:
        return 0
    order = (
        EvidenceSignificance.MINOR,
        EvidenceSignificance.MEANINGFUL,
        EvidenceSignificance.IMPORTANT,
        EvidenceSignificance.CRITICAL,
    )
    return -1 if order.index(first) > order.index(second) else 1


def _dominant_relation(relations: list[int | None]) -> int:
    if any(relation is None for relation in relations):
        return 0
    nonzero = {relation for relation in relations if relation}
    if nonzero == {-1}:
        return -1
    if nonzero == {1}:
        return 1
    return 0


def _ranking_reason(audit: CandidateAudit) -> str:
    confidence = "UNASSIGNED" if audit.confidence is None else audit.confidence.value
    if audit.is_senior and audit.candidate.direction is Direction.HIGHER:
        return f"Senior HIGHER priority; {confidence} evidence-based confidence."
    return f"Overall evidence under the frozen methodology; {confidence} confidence."
