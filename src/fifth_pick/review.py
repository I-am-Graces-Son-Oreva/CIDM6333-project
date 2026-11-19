"""Fail-closed reviewer verdict parsing, bounded transitions, and M2 receipts."""

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from fifth_pick.receipts import Receipt
from fifth_pick.storage import AppendResult, RunStore

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REVIEW_CYCLE_ID_PATTERN = re.compile(r"^review-[0-9a-f]{64}$")
_VERDICT_FIELDS = frozenset({"status", "summary", "findings"})


class ReviewStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    CONCERNS = "CONCERNS"


class ReviewPhase(StrEnum):
    AWAITING_REVIEW = "AWAITING_REVIEW"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    AWAITING_REVIEW_AFTER_CORRECTION = "AWAITING_REVIEW_AFTER_CORRECTION"
    REVIEWED_FOR_JOSEPH = "REVIEWED_FOR_JOSEPH"
    ESCALATE_TO_JOSEPH = "ESCALATE_TO_JOSEPH"
    STOPPED = "STOPPED"


class ReviewEventName(StrEnum):
    REVIEW_PASS = "REVIEW_PASS"
    REVIEW_FAIL = "REVIEW_FAIL"
    REVIEW_CONCERNS = "REVIEW_CONCERNS"
    REVISION_ATTEMPT = "REVISION_ATTEMPT"
    ESCALATE_TO_JOSEPH = "ESCALATE_TO_JOSEPH"


class ReviewError(ValueError):
    """Raised when a review contract input is malformed."""


@dataclass(frozen=True, slots=True)
class ReviewVerdict:
    status: ReviewStatus
    summary: str
    findings: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, ReviewStatus):
            raise ReviewError("review status must use a supported typed value")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ReviewError("review summary must be non-empty text")
        if not isinstance(self.findings, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.findings
        ):
            raise ReviewError("review findings must be a tuple of non-empty strings")
        if self.status in (ReviewStatus.FAIL, ReviewStatus.CONCERNS) and not self.findings:
            raise ReviewError("FAIL and CONCERNS require at least one finding")


@dataclass(frozen=True, slots=True)
class ReviewCycle:
    run_id: str
    subject: str
    initial_artifact_sha256: str
    review_cycle_id: str
    phase: ReviewPhase = ReviewPhase.AWAITING_REVIEW
    correction_count: int = 0
    event_sequence: int = 0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.run_id, str)
            or not self.run_id.strip()
            or not isinstance(self.subject, str)
            or not self.subject.strip()
            or not _valid_sha256(self.initial_artifact_sha256)
            or self.review_cycle_id
            != _review_cycle_id(self.run_id, self.subject, self.initial_artifact_sha256)
        ):
            raise ReviewError("review cycle identity is malformed or noncanonical")
        if type(self.correction_count) is not int or self.correction_count not in (0, 1):
            raise ReviewError("review cycle correction count must be zero or one")
        if type(self.event_sequence) is not int or self.event_sequence < 0:
            raise ReviewError("review cycle event sequence must be a non-negative integer")

        valid_positions = {
            ReviewPhase.AWAITING_REVIEW: {(0, 0)},
            ReviewPhase.REVISION_REQUIRED: {(0, 1)},
            ReviewPhase.AWAITING_REVIEW_AFTER_CORRECTION: {(1, 2)},
            ReviewPhase.REVIEWED_FOR_JOSEPH: {(0, 1), (1, 3)},
            ReviewPhase.ESCALATE_TO_JOSEPH: {(0, 2), (1, 4)},
            ReviewPhase.STOPPED: {(0, 0), (0, 1), (1, 2)},
        }
        if (
            not isinstance(self.phase, ReviewPhase)
            or (self.correction_count, self.event_sequence) not in valid_positions[self.phase]
        ):
            raise ReviewError("review cycle phase and event position are inconsistent")

    @property
    def correction_available(self) -> bool:
        return self.phase is ReviewPhase.REVISION_REQUIRED and self.correction_count == 0


@dataclass(frozen=True, slots=True)
class ReviewEvent:
    review_cycle_id: str
    event: ReviewEventName
    result: str
    sequence: int
    revision: int
    artifact_sha256: str
    reason_code: str

    def __post_init__(self) -> None:
        expected_results = {
            ReviewEventName.REVIEW_PASS: "PASS",
            ReviewEventName.REVIEW_FAIL: "FAIL",
            ReviewEventName.REVIEW_CONCERNS: "CONCERNS",
            ReviewEventName.REVISION_ATTEMPT: "CORRECTION_REQUESTED",
            ReviewEventName.ESCALATE_TO_JOSEPH: "ESCALATED_TO_JOSEPH",
        }
        allowed_reasons = {
            ReviewEventName.REVIEW_PASS: {"VALIDATED_PASS"},
            ReviewEventName.REVIEW_FAIL: {"CORRECTION_AVAILABLE", "SECOND_FAIL"},
            ReviewEventName.REVIEW_CONCERNS: {"JOSEPH_REVIEW_REQUIRED"},
            ReviewEventName.REVISION_ATTEMPT: {"CORRECTION_DISPATCHED"},
            ReviewEventName.ESCALATE_TO_JOSEPH: {"CONCERNS", "SECOND_FAIL"},
        }
        if (
            not isinstance(self.review_cycle_id, str)
            or _REVIEW_CYCLE_ID_PATTERN.fullmatch(self.review_cycle_id) is None
            or not isinstance(self.event, ReviewEventName)
            or self.result != expected_results.get(self.event)
            or type(self.sequence) is not int
            or self.sequence < 1
            or type(self.revision) is not int
            or self.revision not in (0, 1)
            or not _valid_sha256(self.artifact_sha256)
            or not isinstance(self.reason_code, str)
            or self.reason_code not in allowed_reasons.get(self.event, set())
        ):
            raise ReviewError("review event is malformed")


@dataclass(frozen=True, slots=True)
class ReviewTransition:
    cycle: ReviewCycle
    events: tuple[ReviewEvent, ...]

    def __post_init__(self) -> None:
        _validate_review_transition(self)


def _validate_review_transition(transition: ReviewTransition) -> None:
    if not isinstance(transition.cycle, ReviewCycle) or not isinstance(transition.events, tuple):
        raise ReviewError("review transition is malformed")
    cycle = transition.cycle
    cycle.__post_init__()
    if not transition.events:
        if cycle.phase is not ReviewPhase.STOPPED:
            raise ReviewError("only a stopped transition may omit events")
        return
    if cycle.phase is ReviewPhase.STOPPED:
        raise ReviewError("a stopped cycle cannot emit review events")

    for event in transition.events:
        if not isinstance(event, ReviewEvent):
            raise ReviewError("review transition contains an untyped event")
        event.__post_init__()
        if event.review_cycle_id != cycle.review_cycle_id:
            raise ReviewError("review event cycle ID does not match its cycle")

    count = cycle.correction_count
    if cycle.phase is ReviewPhase.REVISION_REQUIRED:
        names = (ReviewEventName.REVIEW_FAIL,)
        results = ("FAIL",)
        sequences = (1,)
        reasons = ("CORRECTION_AVAILABLE",)
        revision = 0
    elif cycle.phase is ReviewPhase.AWAITING_REVIEW_AFTER_CORRECTION:
        names = (ReviewEventName.REVISION_ATTEMPT,)
        results = ("CORRECTION_REQUESTED",)
        sequences = (2,)
        reasons = ("CORRECTION_DISPATCHED",)
        revision = 1
    elif cycle.phase is ReviewPhase.REVIEWED_FOR_JOSEPH:
        names = (ReviewEventName.REVIEW_PASS,)
        results = ("PASS",)
        sequences = (1,) if count == 0 else (3,)
        reasons = ("VALIDATED_PASS",)
        revision = count
    elif cycle.phase is ReviewPhase.ESCALATE_TO_JOSEPH:
        if count == 0:
            names = (ReviewEventName.REVIEW_CONCERNS, ReviewEventName.ESCALATE_TO_JOSEPH)
            results = ("CONCERNS", "ESCALATED_TO_JOSEPH")
            sequences = (1, 2)
            reasons = ("JOSEPH_REVIEW_REQUIRED", "CONCERNS")
            revision = 0
        else:
            first = transition.events[0].event
            if first is ReviewEventName.REVIEW_FAIL:
                results = ("FAIL", "ESCALATED_TO_JOSEPH")
                reasons = ("SECOND_FAIL", "SECOND_FAIL")
            elif first is ReviewEventName.REVIEW_CONCERNS:
                results = ("CONCERNS", "ESCALATED_TO_JOSEPH")
                reasons = ("JOSEPH_REVIEW_REQUIRED", "CONCERNS")
            else:
                raise ReviewError("post-correction escalation has an invalid trigger")
            names = (first, ReviewEventName.ESCALATE_TO_JOSEPH)
            sequences = (3, 4)
            revision = 1
    else:
        raise ReviewError("review events do not match the cycle phase")

    if (
        tuple(event.event for event in transition.events) != names
        or tuple(event.result for event in transition.events) != results
        or tuple(event.sequence for event in transition.events) != sequences
        or tuple(event.reason_code for event in transition.events) != reasons
        or any(event.revision != revision for event in transition.events)
        or any(event.sequence > cycle.event_sequence for event in transition.events)
        or transition.events[-1].sequence != cycle.event_sequence
    ):
        raise ReviewError("review events do not match their cycle phase and sequence")

    digests = {event.artifact_sha256 for event in transition.events}
    if len(digests) != 1:
        raise ReviewError("events in one transition must bind the same artifact digest")
    if revision == 0 and digests != {cycle.initial_artifact_sha256}:
        raise ReviewError("initial review event digest does not match the cycle input")


def _reject_terminal_cycle(cycle: ReviewCycle) -> None:
    if cycle.phase in (
        ReviewPhase.REVIEWED_FOR_JOSEPH,
        ReviewPhase.ESCALATE_TO_JOSEPH,
        ReviewPhase.STOPPED,
    ):
        raise ReviewError("review cycle is terminal")


def _reject_duplicate_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReviewError(f"duplicate reviewer field: {key}")
        result[key] = value
    return result


def parse_review_verdict(raw: str) -> ReviewVerdict:
    """Parse exactly one typed reviewer JSON object; invalid output fails closed."""

    if not isinstance(raw, str):
        raise ReviewError("reviewer output must be JSON text")
    try:
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_fields)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ReviewError("reviewer output is malformed JSON") from exc
    if not isinstance(payload, dict) or frozenset(payload) != _VERDICT_FIELDS:
        raise ReviewError("reviewer output must contain exactly status, summary, and findings")

    status_value = payload["status"]
    if not isinstance(status_value, str):
        raise ReviewError("review status must be text")
    try:
        status = ReviewStatus(status_value)
    except ValueError as exc:
        raise ReviewError("review status is unknown") from exc

    summary = payload["summary"]
    if not isinstance(summary, str) or not summary.strip():
        raise ReviewError("review summary must be non-empty text")

    findings = payload["findings"]
    if not isinstance(findings, list) or any(
        not isinstance(item, str) or not item.strip() for item in findings
    ):
        raise ReviewError("review findings must be an array of non-empty strings")
    if status in (ReviewStatus.FAIL, ReviewStatus.CONCERNS) and not findings:
        raise ReviewError("FAIL and CONCERNS require at least one finding")

    return ReviewVerdict(status=status, summary=summary, findings=tuple(findings))


def _valid_sha256(value: str) -> bool:
    return isinstance(value, str) and _SHA256_PATTERN.fullmatch(value) is not None


def _review_cycle_id(run_id: str, subject: str, initial_artifact_sha256: str) -> str:
    canonical = json.dumps(
        {
            "run_id": run_id,
            "subject": subject,
            "initial_artifact_sha256": initial_artifact_sha256,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"review-{digest}"


def start_review_cycle(run_id: str, subject: str, initial_artifact_sha256: str) -> ReviewCycle:
    """Create deterministic cycle identity for one run, subject, and initial input."""

    if not isinstance(run_id, str) or not run_id.strip():
        raise ReviewError("run_id must be non-empty text")
    if not isinstance(subject, str) or not subject.strip():
        raise ReviewError("review subject must be non-empty text")
    if not _valid_sha256(initial_artifact_sha256):
        raise ReviewError("initial artifact digest must be lowercase SHA-256 hex")

    return ReviewCycle(
        run_id=run_id,
        subject=subject,
        initial_artifact_sha256=initial_artifact_sha256,
        review_cycle_id=_review_cycle_id(run_id, subject, initial_artifact_sha256),
    )


def _stopped(cycle: ReviewCycle) -> ReviewTransition:
    return ReviewTransition(cycle=replace(cycle, phase=ReviewPhase.STOPPED), events=())


def _event(
    *,
    review_cycle_id: str,
    name: ReviewEventName,
    result: str,
    sequence: int,
    revision: int,
    artifact_sha256: str,
    reason_code: str,
) -> ReviewEvent:
    return ReviewEvent(
        review_cycle_id=review_cycle_id,
        event=name,
        result=result,
        sequence=sequence,
        revision=revision,
        artifact_sha256=artifact_sha256,
        reason_code=reason_code,
    )


def apply_review_verdict(
    cycle: ReviewCycle,
    verdict: ReviewVerdict,
    artifact_sha256: str,
) -> ReviewTransition:
    """Apply a valid verdict without side effects or Joseph final approval."""

    if not isinstance(cycle, ReviewCycle) or not isinstance(verdict, ReviewVerdict):
        raise ReviewError("review transition requires a cycle and typed verdict")
    _reject_terminal_cycle(cycle)
    if not _valid_sha256(artifact_sha256):
        return _stopped(cycle)

    if cycle.phase is ReviewPhase.AWAITING_REVIEW:
        if cycle.correction_count != 0 or artifact_sha256 != cycle.initial_artifact_sha256:
            return _stopped(cycle)
        revision = 0
    elif (
        cycle.phase is ReviewPhase.AWAITING_REVIEW_AFTER_CORRECTION and cycle.correction_count == 1
    ):
        revision = 1
    else:
        return _stopped(cycle)

    sequence = cycle.event_sequence + 1
    if verdict.status is ReviewStatus.PASS:
        next_cycle = replace(
            cycle,
            phase=ReviewPhase.REVIEWED_FOR_JOSEPH,
            event_sequence=sequence,
        )
        events = (
            _event(
                review_cycle_id=cycle.review_cycle_id,
                name=ReviewEventName.REVIEW_PASS,
                result=ReviewStatus.PASS.value,
                sequence=sequence,
                revision=revision,
                artifact_sha256=artifact_sha256,
                reason_code="VALIDATED_PASS",
            ),
        )
    elif verdict.status is ReviewStatus.FAIL and revision == 0:
        next_cycle = replace(
            cycle,
            phase=ReviewPhase.REVISION_REQUIRED,
            event_sequence=sequence,
        )
        events = (
            _event(
                review_cycle_id=cycle.review_cycle_id,
                name=ReviewEventName.REVIEW_FAIL,
                result=ReviewStatus.FAIL.value,
                sequence=sequence,
                revision=revision,
                artifact_sha256=artifact_sha256,
                reason_code="CORRECTION_AVAILABLE",
            ),
        )
    elif verdict.status is ReviewStatus.FAIL:
        next_cycle = replace(
            cycle,
            phase=ReviewPhase.ESCALATE_TO_JOSEPH,
            event_sequence=sequence + 1,
        )
        events = (
            _event(
                review_cycle_id=cycle.review_cycle_id,
                name=ReviewEventName.REVIEW_FAIL,
                result=ReviewStatus.FAIL.value,
                sequence=sequence,
                revision=revision,
                artifact_sha256=artifact_sha256,
                reason_code="SECOND_FAIL",
            ),
            _event(
                review_cycle_id=cycle.review_cycle_id,
                name=ReviewEventName.ESCALATE_TO_JOSEPH,
                result="ESCALATED_TO_JOSEPH",
                sequence=sequence + 1,
                revision=revision,
                artifact_sha256=artifact_sha256,
                reason_code="SECOND_FAIL",
            ),
        )
    elif verdict.status is ReviewStatus.CONCERNS:
        next_cycle = replace(
            cycle,
            phase=ReviewPhase.ESCALATE_TO_JOSEPH,
            event_sequence=sequence + 1,
        )
        events = (
            _event(
                review_cycle_id=cycle.review_cycle_id,
                name=ReviewEventName.REVIEW_CONCERNS,
                result=ReviewStatus.CONCERNS.value,
                sequence=sequence,
                revision=revision,
                artifact_sha256=artifact_sha256,
                reason_code="JOSEPH_REVIEW_REQUIRED",
            ),
            _event(
                review_cycle_id=cycle.review_cycle_id,
                name=ReviewEventName.ESCALATE_TO_JOSEPH,
                result="ESCALATED_TO_JOSEPH",
                sequence=sequence + 1,
                revision=revision,
                artifact_sha256=artifact_sha256,
                reason_code="CONCERNS",
            ),
        )
    else:
        return _stopped(cycle)

    return ReviewTransition(cycle=next_cycle, events=events)


def dispatch_review_correction(cycle: ReviewCycle, artifact_sha256: str) -> ReviewTransition:
    """Record the single Builder correction only when it is actually dispatched."""

    if not isinstance(cycle, ReviewCycle):
        raise ReviewError("correction dispatch requires a review cycle")
    _reject_terminal_cycle(cycle)
    if (
        cycle.phase is not ReviewPhase.REVISION_REQUIRED
        or not cycle.correction_available
        or not _valid_sha256(artifact_sha256)
    ):
        return _stopped(cycle)

    sequence = cycle.event_sequence + 1
    next_cycle = replace(
        cycle,
        phase=ReviewPhase.AWAITING_REVIEW_AFTER_CORRECTION,
        correction_count=1,
        event_sequence=sequence,
    )
    event = _event(
        review_cycle_id=cycle.review_cycle_id,
        name=ReviewEventName.REVISION_ATTEMPT,
        result="CORRECTION_REQUESTED",
        sequence=sequence,
        revision=1,
        artifact_sha256=artifact_sha256,
        reason_code="CORRECTION_DISPATCHED",
    )
    return ReviewTransition(cycle=next_cycle, events=(event,))


def append_review_receipts(
    store: RunStore,
    transition: ReviewTransition,
    occurred_at: datetime,
) -> tuple[AppendResult, ...]:
    """Append observable review events through the unchanged M2 RunStore contract."""

    if not isinstance(store, RunStore) or not isinstance(transition, ReviewTransition):
        raise ReviewError("receipt append requires an M2 RunStore and review transition")
    _validate_review_transition(transition)
    if (
        not isinstance(occurred_at, datetime)
        or occurred_at.tzinfo is None
        or occurred_at.utcoffset() != timedelta(0)
    ):
        raise ReviewError("review receipt timestamp must be timezone-aware UTC")

    cycle = transition.cycle
    cycle_digest = cycle.review_cycle_id.removeprefix("review-")
    results: list[AppendResult] = []
    for item in transition.events:
        source = (
            "fifth-pick-reviewer"
            if item.event
            in (
                ReviewEventName.REVIEW_PASS,
                ReviewEventName.REVIEW_FAIL,
                ReviewEventName.REVIEW_CONCERNS,
            )
            else "fifth-pick-review-controller"
        )
        receipt = Receipt(
            timestamp=occurred_at.isoformat(),
            event=item.event.value,
            result=item.result,
            subject=cycle.review_cycle_id,
            source=source,
            reason=(
                f"revision={item.revision}; artifact_sha256={item.artifact_sha256}; "
                f"reason={item.reason_code}"
            ),
            run_id=cycle.run_id,
            event_key=(f"review-{cycle_digest}-{item.sequence:02d}-{item.event.value.lower()}"),
        )
        results.append(store.append_receipt(receipt))

    return tuple(results)
