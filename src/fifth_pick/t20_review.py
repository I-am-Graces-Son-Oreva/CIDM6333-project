"""M7 per-candidate T-20 review using the M5 and M6 validation boundaries."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from fifth_pick.evidence import EvidenceItem, EvidenceKind
from fifth_pick.methodology import (
    CandidateAudit,
    CandidateCase,
    Confidence,
    EvaluationStatus,
    MethodologyError,
    evaluate_candidate,
)
from fifth_pick.models import ReasonCode
from fifth_pick.receipts import Receipt
from fifth_pick.snapshots import SnapshotEvidence
from fifth_pick.sources.odds_api import SOURCE_ID
from fifth_pick.storage import RunStore, _atomic_write, application_run_store

T20_REVIEW_FILENAME: Final[str] = "t20-reviews.jsonl"
_T20_AVAILABILITY_KINDS: Final[frozenset[EvidenceKind]] = frozenset({EvidenceKind.AVAILABILITY})
_T20_ROLE_KINDS: Final[frozenset[EvidenceKind]] = frozenset(
    {EvidenceKind.ROLE_MINUTES, EvidenceKind.TEAMMATE_ABSENCE}
)
_T20_GAME_KINDS: Final[frozenset[EvidenceKind]] = frozenset(
    {
        EvidenceKind.MATCHUP,
        EvidenceKind.GAME_TOTAL,
        EvidenceKind.POINT_SPREAD,
        EvidenceKind.BLOWOUT_RISK,
        EvidenceKind.OPPONENT_ABSENCE,
        EvidenceKind.SCHEDULE,
    }
)
_T20_CURRENT_KINDS: Final[frozenset[EvidenceKind]] = frozenset(
    {
        EvidenceKind.PROJECTION_MOVEMENT,
        *_T20_AVAILABILITY_KINDS,
        *_T20_ROLE_KINDS,
        *_T20_GAME_KINDS,
        EvidenceKind.GENERAL_CONTEXT,
        EvidenceKind.FOUL_TROUBLE,
        EvidenceKind.OTHER,
    }
)


class T20Conclusion(StrEnum):
    """The frozen M7 conclusions; none is a Joseph approval or final pick."""

    STILL_STRONG = "STILL STRONG"
    DOWNGRADED = "DOWNGRADED"
    REMOVE_RECOMMENDED = "REMOVE RECOMMENDED"


class T20ReviewError(ValueError):
    """Raised when M7 review persistence or its invocation contract is invalid."""


@dataclass(frozen=True, slots=True)
class _T20ReviewReadiness:
    """Canonical fail-closed prerequisites for any positive T-20 conclusion."""

    ready: bool
    reason_codes: tuple[ReasonCode, ...]
    gaps: tuple[str, ...]
    audit_reasons: tuple[str, ...]
    snapshot_3: SnapshotEvidence | None
    projection_before: float | None
    projection_at_t20: float | None
    projection_changed: bool | None
    changed_evidence_ids: tuple[str, ...]
    changed_judgment_fields: tuple[str, ...]
    context_changed: bool


@dataclass(frozen=True, slots=True)
class T20Review:
    """One immutable review result and its M6 before/after evidence trail."""

    run_id: str
    candidate_key: str
    reviewed_at: datetime
    conclusion: T20Conclusion
    reason_codes: tuple[ReasonCode, ...]
    audit_reasons: tuple[str, ...]
    prior_audit: CandidateAudit | None
    current_audit: CandidateAudit | None
    snapshot_3_late: bool | None
    snapshot_3_recorded_at: datetime | None
    projection_before: float | None
    projection_at_t20: float | None
    projection_changed: bool | None
    changed_evidence_ids: tuple[str, ...]
    changed_judgment_fields: tuple[str, ...]
    context_changed: bool
    readiness_passed: bool
    readiness_gaps: tuple[str, ...]
    blocked: bool

    def to_dict(self) -> dict[str, object]:
        """Serialize the complete review trail without adding a finalization action."""

        snapshots = () if self.current_audit is None else self.current_audit.snapshots
        return {
            "run_id": self.run_id,
            "candidate_key": self.candidate_key,
            "reviewed_at": self.reviewed_at.isoformat(),
            "conclusion": self.conclusion.value,
            "blocked": self.blocked,
            "reason_codes": [reason.value for reason in self.reason_codes],
            "audit_reasons": list(self.audit_reasons),
            "prior_status": (None if self.prior_audit is None else self.prior_audit.status.value),
            "prior_confidence": (
                None
                if self.prior_audit is None or self.prior_audit.confidence is None
                else self.prior_audit.confidence.value
            ),
            "current_status": (
                None if self.current_audit is None else self.current_audit.status.value
            ),
            "current_confidence": (
                None
                if self.current_audit is None or self.current_audit.confidence is None
                else self.current_audit.confidence.value
            ),
            "snapshot_3_late": self.snapshot_3_late,
            "snapshot_3_recorded_at": (
                None
                if self.snapshot_3_recorded_at is None
                else self.snapshot_3_recorded_at.isoformat()
            ),
            "projection": {
                "before": self.projection_before,
                "at_t20": self.projection_at_t20,
                "changed": self.projection_changed,
            },
            "changed_evidence_ids": list(self.changed_evidence_ids),
            "changed_judgment_fields": list(self.changed_judgment_fields),
            "context_changed": self.context_changed,
            "readiness_passed": self.readiness_passed,
            "readiness_gaps": list(self.readiness_gaps),
            "previous_audit": (None if self.prior_audit is None else self.prior_audit.to_dict()),
            "current_audit": (None if self.current_audit is None else self.current_audit.to_dict()),
            "snapshots": [snapshot.to_dict() for snapshot in snapshots],
        }


def _aware(value: datetime) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _current_candidate_key(case: CandidateCase) -> str:
    return case.snapshots[-1].candidate_key if case.snapshots else "unresolved-candidate"


def _changed_evidence_ids(
    previous: CandidateAudit,
    current: CandidateAudit,
) -> tuple[str, ...]:
    def signatures(audit: CandidateAudit) -> dict[str, str]:
        return {
            item.evidence_id: json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True)
            for item in audit.evidence
        }

    before = signatures(previous)
    after = signatures(current)
    return tuple(
        sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    )


def _candidate_mismatch_reason(
    previous: CandidateAudit,
    current: CandidateAudit,
) -> ReasonCode | None:
    if previous.candidate.player != current.candidate.player:
        return ReasonCode.PLAYER_IDENTITY_UNRESOLVED
    if (
        previous.candidate.category is not current.candidate.category
        or previous.candidate.direction is not current.candidate.direction
    ):
        return ReasonCode.CATEGORY_NOT_AUTHORIZED
    if (
        previous.candidate.platform is not current.candidate.platform
        or previous.candidate.event != current.candidate.event
        or previous.candidate_key != current.candidate_key
    ):
        return ReasonCode.SOURCE_CONFLICT_UNRESOLVED
    return None


def _baseline_mismatch(
    previous: CandidateAudit,
    current: CandidateAudit,
) -> bool:
    previous_by_number = {item.snapshot.number: item for item in previous.snapshots}
    current_by_number = {item.snapshot.number: item for item in current.snapshots}
    return any(previous_by_number.get(number) != current_by_number.get(number) for number in (1, 2))


def _changed_judgment_fields(
    previous: CandidateAudit,
    current: CandidateAudit,
) -> tuple[str, ...]:
    def fields(audit: CandidateAudit) -> dict[str, object]:
        return {
            "rationale": audit.rationale,
            "supporting_evidence_ids": audit.supporting_evidence_ids,
            "meaningful_risk_ids": audit.meaningful_risk_ids,
            "exclusions": tuple(reason.value for reason in audit.exclusions),
            "status": audit.status.value,
            "confidence": None if audit.confidence is None else audit.confidence.value,
            "disposition": None if audit.disposition is None else audit.disposition.value,
            "methodology_sufficient_evidence": audit.methodology_sufficient_evidence,
            "major_unresolved_concern": audit.major_unresolved_concern,
            "senior_lower_support_ids": audit.senior_lower_support_ids,
            "senior_lower_disclosure": audit.senior_lower_disclosure,
            "rules_applied": audit.rules_applied,
            "gaps": tuple(
                json.dumps(gap.to_dict(), ensure_ascii=False, sort_keys=True) for gap in audit.gaps
            ),
            "history": audit.history,
            "is_senior": audit.is_senior,
            "trust_labels": audit.trust_labels,
            "foul_trouble": audit.foul_trouble,
            "evidence_mode": audit.evidence_mode.value,
        }

    before = fields(previous)
    after = fields(current)
    return tuple(sorted(name for name in before if before[name] != after[name]))


def _is_current_t20_evidence(
    item: EvidenceItem,
    *,
    target_at: datetime,
    reviewed_at: datetime,
) -> bool:
    retrieved_at = item.evidence.provenance.retrieved_at
    return target_at <= retrieved_at <= reviewed_at


def _t20_evidence_gaps(
    audit: CandidateAudit,
    *,
    target_at: datetime,
    reviewed_at: datetime,
) -> tuple[str, ...]:
    evidence = audit.evidence
    gaps: list[str] = []
    for label, kinds in (
        ("AVAILABILITY", _T20_AVAILABILITY_KINDS),
        ("ROLE_MINUTES or TEAMMATE_ABSENCE", _T20_ROLE_KINDS),
        ("game context", _T20_GAME_KINDS),
    ):
        matching = tuple(item for item in evidence if item.kind in kinds)
        if not any(
            _is_current_t20_evidence(item, target_at=target_at, reviewed_at=reviewed_at)
            for item in matching
        ):
            state = "missing" if not matching else "stale or outside the T-20 review"
            gaps.append(f"Required {label} evidence is {state}.")

    cited_ids = set(audit.supporting_evidence_ids) | set(audit.meaningful_risk_ids)
    cited_ids.update(audit.senior_lower_support_ids)
    for item in evidence:
        if (
            item.evidence_id in cited_ids
            and item.kind in _T20_CURRENT_KINDS
            and not _is_current_t20_evidence(
                item,
                target_at=target_at,
                reviewed_at=reviewed_at,
            )
        ):
            gaps.append(
                f"Cited {item.kind.value} evidence {item.evidence_id!r} is stale or outside "
                "the T-20 review."
            )
    return tuple(dict.fromkeys(gaps))


def _t20_review_readiness(
    prior: CandidateAudit | None,
    current: CandidateAudit | None,
    *,
    reviewed_at: datetime,
) -> _T20ReviewReadiness:
    """Establish all frozen M5/M6 prerequisites before a positive review."""

    reasons: list[ReasonCode] = []
    gaps: list[str] = []
    audit_reasons: list[str] = []

    if prior is None:
        reasons.append(ReasonCode.T20_CHECK_UNAVAILABLE)
        gaps.append("The prior M6 candidate audit could not be established.")
    elif prior.status is EvaluationStatus.BLOCKED:
        reasons.extend(prior.exclusions or (ReasonCode.PLAYER_IDENTITY_UNRESOLVED,))
        gaps.append("The prior candidate is blocked by M6 identity or authorization.")
    elif prior.status is not EvaluationStatus.QUALIFIED:
        reasons.extend(prior.exclusions or (ReasonCode.INSUFFICIENT_SUPPORTING_EVIDENCE,))
        gaps.append("The prior M6 candidate audit is not qualified for T-20 review.")

    if current is None:
        reasons.append(ReasonCode.T20_CHECK_UNAVAILABLE)
        gaps.append("The current M6 candidate audit could not be established.")
    elif current.status is EvaluationStatus.BLOCKED:
        reasons.extend(current.exclusions or (ReasonCode.CATEGORY_NOT_AUTHORIZED,))
        gaps.append("The current candidate is blocked by M6 identity or authorization.")
    elif current.status is not EvaluationStatus.QUALIFIED or not current.authorization_allowed:
        reasons.extend(current.exclusions or (ReasonCode.INSUFFICIENT_SUPPORTING_EVIDENCE,))
        gaps.append("The current M6 candidate audit is not qualified and authorized.")

    if prior is not None and current is not None:
        identity_reason = _candidate_mismatch_reason(prior, current)
        if identity_reason is not None:
            reasons.append(identity_reason)
            gaps.append("Current player, category, direction, platform, or event differs from M6.")
        if _baseline_mismatch(prior, current):
            reasons.append(ReasonCode.SOURCE_CONFLICT_UNRESOLVED)
            gaps.append("Snapshot 1 or Snapshot 2 differs from the prior M6 baseline.")

    snapshot_3 = (
        None
        if current is None
        else next((item for item in current.snapshots if item.snapshot.number == 3), None)
    )
    projection_before: float | None = None
    projection_at_t20: float | None = None
    projection_changed: bool | None = None
    if snapshot_3 is None:
        missed = (
            None
            if current is None
            else next((item for item in current.missed_snapshots if item.number == 3), None)
        )
        if missed is None:
            reasons.append(ReasonCode.T20_CHECK_UNAVAILABLE)
            gaps.append("Authoritative M6-validated Snapshot 3 is unavailable.")
        else:
            reasons.append(missed.reason)
            gaps.append("Snapshot 3 was recorded as missed and cannot be backfilled.")
    else:
        target_at = snapshot_3.target_at
        if snapshot_3.late:
            reasons.append(ReasonCode.T20_CHECK_UNAVAILABLE)
            gaps.append("Snapshot 3 is late; its recorded timestamps are preserved.")
        if (
            target_at is None
            or reviewed_at != target_at
            or snapshot_3.snapshot.recorded_at > reviewed_at
            or snapshot_3.snapshot.observation.retrieved_at > reviewed_at
            or reviewed_at >= snapshot_3.event_start
        ):
            reasons.append(ReasonCode.T20_CHECK_UNAVAILABLE)
            gaps.append("The review did not occur at the frozen Snapshot 3 T-20 target.")

        prior_snapshot_3 = (
            None
            if prior is None
            else next((item for item in prior.snapshots if item.snapshot.number == 3), None)
        )
        if (
            prior_snapshot_3 is not None
            and prior_snapshot_3.snapshot.recorded_at > snapshot_3.snapshot.recorded_at
        ):
            reasons.append(ReasonCode.T20_CHECK_UNAVAILABLE)
            gaps.append("Current Snapshot 3 predates the prior M6 audit state.")

        snapshot_2 = (
            None
            if current is None
            else next((item for item in current.snapshots if item.snapshot.number == 2), None)
        )
        if snapshot_2 is None:
            reasons.append(ReasonCode.PROJECTION_OBSERVATION_MISSED)
            gaps.append("Snapshot 2 is unavailable for the T-20 projection comparison.")
        else:
            projection_before = snapshot_2.snapshot.observation.projection
            projection_at_t20 = snapshot_3.snapshot.observation.projection
            projection_changed = projection_before != projection_at_t20

        if current is not None and target_at is not None:
            coverage_gaps = _t20_evidence_gaps(
                current,
                target_at=target_at,
                reviewed_at=reviewed_at,
            )
            if coverage_gaps:
                reasons.append(ReasonCode.T20_CHECK_UNAVAILABLE)
                gaps.extend(coverage_gaps)

    changed_evidence: tuple[str, ...] = ()
    changed_fields: tuple[str, ...] = ()
    context_changed = False
    if prior is not None and current is not None:
        changed_evidence = _changed_evidence_ids(prior, current)
        changed_fields = _changed_judgment_fields(prior, current)
        context_changed = bool(changed_evidence or changed_fields)
        audit_reasons.append(
            "M6 evidence items changed: " + ", ".join(changed_evidence)
            if changed_evidence
            else "M6 evidence items are unchanged."
        )
        audit_reasons.append(
            "M6 audit fields changed: " + ", ".join(changed_fields)
            if changed_fields
            else "Relevant M6 judgment and audit fields are unchanged."
        )

    if snapshot_3 is not None:
        audit_reasons.append(
            "Snapshot 3 is late; its actual timing is retained."
            if snapshot_3.late
            else "Snapshot 3's actual on-time record is retained."
        )
    audit_reasons.extend(gaps)
    if not reasons and not gaps:
        audit_reasons.append("Canonical T-20 review readiness passed.")

    return _T20ReviewReadiness(
        ready=not reasons and not gaps,
        reason_codes=tuple(dict.fromkeys(reasons)),
        gaps=tuple(dict.fromkeys(gaps)),
        audit_reasons=tuple(audit_reasons),
        snapshot_3=snapshot_3,
        projection_before=projection_before,
        projection_at_t20=projection_at_t20,
        projection_changed=projection_changed,
        changed_evidence_ids=changed_evidence,
        changed_judgment_fields=changed_fields,
        context_changed=context_changed,
    )


def _append_audit(store: RunStore, review: T20Review) -> str:
    record = review.to_dict()
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    event_key = f"t20-review-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
    record["event_key"] = event_key
    line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path = store.run_directory(review.run_id) / T20_REVIEW_FILENAME
    try:
        existing = path.read_bytes()
    except FileNotFoundError:
        existing = b""
    except OSError as exc:
        raise T20ReviewError("cannot read the existing M7 review audit") from exc

    for raw_line in existing.splitlines():
        try:
            prior_record = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise T20ReviewError("the M7 review audit is malformed") from exc
        if not isinstance(prior_record, dict):
            raise T20ReviewError("the M7 review audit contains a non-object record")
        if prior_record.get("event_key") == event_key:
            if prior_record != record:
                raise T20ReviewError("an M7 review event key has conflicting audit content")
            return event_key

    content = existing
    if content and not content.endswith(b"\n"):
        content += b"\n"
    content += f"{line}\n".encode()
    try:
        _atomic_write(path, content)
    except OSError as exc:
        raise T20ReviewError("cannot persist the M7 review audit") from exc
    return event_key


def _persist_review(store: RunStore, review: T20Review) -> None:
    event_key = _append_audit(store, review)
    reasons = (*[reason.value for reason in review.reason_codes], *review.audit_reasons)
    store.append_receipt(
        Receipt(
            timestamp=review.reviewed_at.isoformat(),
            event="T20_REVIEW",
            result=review.conclusion.value,
            subject=review.candidate_key,
            source=SOURCE_ID,
            reason="; ".join(reasons),
            run_id=review.run_id,
            event_key=event_key,
        )
    )


def review_t20(
    prior_case: CandidateCase,
    case: CandidateCase,
    *,
    reviewed_at: datetime,
    run_id: str,
    store: RunStore,
) -> T20Review:
    """Re-evaluate one candidate at T-20, record the M6 comparison, and stop.

    LIVE candidate cases are accepted only through M6's application-owned M5
    ledger validation and must persist their M7 receipt in that same store.
    FIXTURE cases remain explicit and can use an isolated offline store.
    """

    if not isinstance(prior_case, CandidateCase):
        raise T20ReviewError("prior_case must be an M6 CandidateCase")
    if not isinstance(case, CandidateCase):
        raise T20ReviewError("case must be an M6 CandidateCase")
    if not _aware(reviewed_at):
        raise T20ReviewError("reviewed_at must be timezone-aware")
    if not isinstance(run_id, str) or not run_id.strip():
        raise T20ReviewError("run_id must be non-empty")
    if type(store) is not RunStore:
        raise T20ReviewError("M7 requires the M5 RunStore")
    live_cases = (prior_case, case)
    if any(
        snapshot.evidence_mode.value == "live"
        for candidate_case in live_cases
        for snapshot in candidate_case.snapshots
    ):
        if any(candidate_case.snapshot_run_id != run_id for candidate_case in live_cases):
            raise T20ReviewError("LIVE M7 review must use the M5 snapshot run ID")
        if store.root != application_run_store().root:
            raise T20ReviewError("LIVE M7 receipts must use the application-owned M5 store")

    candidate_key = _current_candidate_key(case)
    try:
        prior_audit: CandidateAudit | None = evaluate_candidate(prior_case)
    except MethodologyError:
        prior_audit = None
    current_audit: CandidateAudit | None
    try:
        current_audit = evaluate_candidate(case)
    except MethodologyError:
        current_audit = None

    readiness = _t20_review_readiness(
        prior_audit,
        current_audit,
        reviewed_at=reviewed_at,
    )
    audit_reasons = list(readiness.audit_reasons)
    if readiness.snapshot_3 is not None:
        audit_reasons.append(
            "Projection changed between Snapshot 2 and Snapshot 3."
            if readiness.projection_changed
            else "Projection was unchanged between Snapshot 2 and Snapshot 3."
        )

    if not readiness.ready:
        conclusion = T20Conclusion.REMOVE_RECOMMENDED
        audit_reasons.append("T-20 review readiness failed; no positive conclusion was issued.")
    elif (
        prior_audit is not None
        and current_audit is not None
        and prior_audit.confidence is Confidence.HIGH
        and current_audit.confidence is Confidence.MEDIUM
    ):
        conclusion = T20Conclusion.DOWNGRADED
        audit_reasons.append("The current M6 judgment lowered confidence from HIGH to MEDIUM.")
    else:
        conclusion = T20Conclusion.STILL_STRONG
        audit_reasons.append("The current M6 methodology evaluation remains qualified.")

    review = T20Review(
        run_id=run_id,
        candidate_key=candidate_key,
        reviewed_at=reviewed_at,
        conclusion=conclusion,
        reason_codes=readiness.reason_codes,
        audit_reasons=tuple(audit_reasons),
        prior_audit=prior_audit,
        current_audit=current_audit,
        snapshot_3_late=(None if readiness.snapshot_3 is None else readiness.snapshot_3.late),
        snapshot_3_recorded_at=(
            None if readiness.snapshot_3 is None else readiness.snapshot_3.snapshot.recorded_at
        ),
        projection_before=readiness.projection_before,
        projection_at_t20=readiness.projection_at_t20,
        projection_changed=readiness.projection_changed,
        changed_evidence_ids=readiness.changed_evidence_ids,
        changed_judgment_fields=readiness.changed_judgment_fields,
        context_changed=readiness.context_changed,
        readiness_passed=readiness.ready,
        readiness_gaps=readiness.gaps,
        blocked=not readiness.ready,
    )
    _persist_review(store, review)
    return review
