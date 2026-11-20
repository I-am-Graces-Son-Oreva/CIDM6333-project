"""Strict stdin/stdout adapter for OpenCode review lifecycle events."""

import fcntl
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from fifth_pick.errors import StorageError
from fifth_pick.receipts import Receipt
from fifth_pick.review import (
    ReviewCycle,
    ReviewError,
    ReviewEventName,
    ReviewPhase,
    ReviewStatus,
    ReviewTransition,
    ReviewVerdict,
    append_review_receipts,
    apply_review_verdict,
    dispatch_review_correction,
    parse_review_verdict,
    start_review_cycle,
)
from fifth_pick.storage import RunStore, _atomic_write, application_run_store

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REASON_PATTERN = re.compile(r"^revision=([01]); artifact_sha256=([0-9a-f]{64}); reason=([A-Z_]+)$")
_TASK_RESULT_PREFIX = re.compile(
    r'^<task id="([A-Za-z0-9_-]+)" state="completed">\s*<task_result>\s*'
)
_TASK_RESULT_SUFFIX = re.compile(r"\s*</task_result>\s*</task>\s*\Z")
_RECEIPT_FIELDS = frozenset(
    {
        "timestamp",
        "event",
        "result",
        "subject",
        "source",
        "reason",
        "run_id",
        "event_key",
    }
)


class BridgeRequestError(ValueError):
    """Raised when the outer bridge request is malformed."""


@dataclass(frozen=True, slots=True)
class BridgeResult:
    response: dict[str, object]
    exit_code: int


@dataclass(frozen=True, slots=True)
class _BridgeRequest:
    kind: str
    run_id: str
    subject: str
    initial_artifact_sha256: str
    current_artifact_sha256: str
    revision: int
    verdict_json: str | None


@dataclass(frozen=True, slots=True)
class _History:
    receipts: tuple[dict[str, str | None], ...]
    transitions: tuple[ReviewTransition, ...]
    cycle: ReviewCycle


@contextmanager
def _run_lock(store: RunStore, run_id: str) -> Generator[None, None, None]:
    """Serialize bridge history reads and receipt appends per M2 run."""

    lock_directory = store.root / ".review-locks"
    lock_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory_stat = lock_directory.lstat()
    if not stat.S_ISDIR(directory_stat.st_mode) or stat.S_IMODE(directory_stat.st_mode) & 0o077:
        raise StorageError("review lock directory must be a private directory")

    lock_name = hashlib.sha256(run_id.encode("utf-8")).hexdigest() + ".lock"
    lock_path = lock_directory / lock_name
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        raise StorageError("safe per-run lock files are unsupported on this platform")
    flags = os.O_CREAT | os.O_RDWR | no_follow
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise StorageError("cannot open the per-run review lock") from exc

    try:
        file_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or stat.S_IMODE(file_stat.st_mode) & 0o077
            or file_stat.st_uid != os.geteuid()
        ):
            raise StorageError("per-run review lock must be a private regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    except OSError as exc:
        raise StorageError("cannot acquire the per-run review lock") from exc
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _reject_duplicate_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise BridgeRequestError(f"duplicate bridge field: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise BridgeRequestError(f"unsupported JSON constant: {value}")


def _reviewer_json(raw: str) -> str:
    if not raw.lstrip().startswith("<task"):
        return raw
    prefix = _TASK_RESULT_PREFIX.match(raw)
    suffix = _TASK_RESULT_SUFFIX.search(raw, prefix.end() if prefix is not None else 0)
    if prefix is None or suffix is None or suffix.start() < prefix.end():
        raise ReviewError("OpenCode Reviewer task result envelope is malformed or incomplete")
    return raw[prefix.end() : suffix.start()]


def _parse_request(raw: str) -> _BridgeRequest:
    if not isinstance(raw, str):
        raise BridgeRequestError("bridge request must be UTF-8 JSON text")
    try:
        payload = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_fields,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise BridgeRequestError("bridge request is malformed JSON") from exc
    if not isinstance(payload, dict):
        raise BridgeRequestError("bridge request must be one JSON object")

    kind = payload.get("kind")
    common = {
        "schema_version",
        "kind",
        "run_id",
        "subject",
        "initial_artifact_sha256",
        "current_artifact_sha256",
        "revision",
    }
    if not isinstance(kind, str) or kind not in ("VERDICT", "REVISION_DISPATCHED"):
        raise BridgeRequestError("bridge request fields or kind are unsupported")
    expected = common | ({"verdict_json"} if kind == "VERDICT" else set())
    if frozenset(payload) != expected:
        raise BridgeRequestError("bridge request fields or kind are unsupported")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise BridgeRequestError("bridge schema_version must be integer 1")
    if type(payload["revision"]) is not int or payload["revision"] not in (0, 1):
        raise BridgeRequestError("bridge revision must be integer 0 or 1")
    if kind == "REVISION_DISPATCHED" and payload["revision"] != 1:
        raise BridgeRequestError("revision dispatch must use revision 1")
    run_id = payload["run_id"]
    subject = payload["subject"]
    if not isinstance(run_id, str) or not run_id.strip():
        raise BridgeRequestError("bridge run_id must be non-empty text")
    if not isinstance(subject, str) or not subject.strip():
        raise BridgeRequestError("bridge subject must be non-empty text")
    for field in ("initial_artifact_sha256", "current_artifact_sha256"):
        if not isinstance(payload[field], str) or _SHA256_PATTERN.fullmatch(payload[field]) is None:
            raise BridgeRequestError(f"bridge {field} must be lowercase SHA-256 hex")
    initial_digest = payload["initial_artifact_sha256"]
    current_digest = payload["current_artifact_sha256"]
    if not isinstance(initial_digest, str) or not isinstance(current_digest, str):
        raise BridgeRequestError("bridge artifact digests must be text")
    revision = payload["revision"]
    verdict_json: str | None = None
    if kind == "VERDICT":
        raw_verdict = payload["verdict_json"]
        if not isinstance(raw_verdict, str):
            raise BridgeRequestError("bridge verdict_json must be JSON text")
        verdict_json = raw_verdict

    if kind == "VERDICT" and verdict_json is None:
        raise BridgeRequestError("bridge verdict_json must be JSON text")
    return _BridgeRequest(
        kind=kind,
        run_id=run_id,
        subject=subject,
        initial_artifact_sha256=initial_digest,
        current_artifact_sha256=current_digest,
        revision=revision,
        verdict_json=verdict_json,
    )


def _status_from_receipt(receipt: dict[str, str | None]) -> ReviewStatus:
    event = receipt.get("event")
    result = receipt.get("result")
    if (event, result) == (ReviewEventName.REVIEW_PASS.value, ReviewStatus.PASS.value):
        return ReviewStatus.PASS
    if (event, result) == (ReviewEventName.REVIEW_FAIL.value, ReviewStatus.FAIL.value):
        return ReviewStatus.FAIL
    if (event, result) == (ReviewEventName.REVIEW_CONCERNS.value, ReviewStatus.CONCERNS.value):
        return ReviewStatus.CONCERNS
    raise ReviewError("review receipt history contains an unsupported verdict")


def _artifact_digest(receipt: dict[str, str | None]) -> str:
    reason = receipt.get("reason")
    match = _REASON_PATTERN.fullmatch(reason or "")
    if match is None:
        raise ReviewError("review receipt history has an invalid bounded reason")
    return match.group(2)


def _matches_receipts(
    cycle: ReviewCycle,
    receipts: tuple[dict[str, str | None], ...],
    transitions: tuple[ReviewTransition, ...],
    *,
    allow_prefix: bool = False,
) -> bool:
    events = tuple(event for transition in transitions for event in transition.events)
    if len(receipts) > len(events) or (not allow_prefix and len(receipts) != len(events)):
        return False

    cycle_digest = cycle.review_cycle_id.removeprefix("review-")
    for receipt, event in zip(receipts, events, strict=not allow_prefix):
        source = (
            "fifth-pick-reviewer"
            if event.event
            in (
                ReviewEventName.REVIEW_PASS,
                ReviewEventName.REVIEW_FAIL,
                ReviewEventName.REVIEW_CONCERNS,
            )
            else "fifth-pick-review-controller"
        )
        expected = {
            "event": event.event.value,
            "result": event.result,
            "subject": cycle.review_cycle_id,
            "source": source,
            "reason": (
                f"revision={event.revision}; artifact_sha256={event.artifact_sha256}; "
                f"reason={event.reason_code}"
            ),
            "run_id": cycle.run_id,
            "event_key": (
                f"review-{cycle_digest}-{event.sequence:02d}-{event.event.value.lower()}"
            ),
        }
        if frozenset(receipt) != _RECEIPT_FIELDS or any(
            receipt.get(field) != value for field, value in expected.items()
        ):
            return False
        timestamp = receipt.get("timestamp")
        try:
            parsed = datetime.fromisoformat(timestamp or "")
        except ValueError:
            return False
        if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
            return False

    return True


def _load_history(store: RunStore, initial_cycle: ReviewCycle) -> _History:
    all_receipts = store.read_receipts(initial_cycle.run_id)
    cycle_digest = initial_cycle.review_cycle_id.removeprefix("review-")
    key_prefix = f"review-{cycle_digest}-"
    receipts = tuple(
        receipt
        for receipt in all_receipts
        if receipt.get("subject") == initial_cycle.review_cycle_id
        or (receipt.get("event_key") or "").startswith(key_prefix)
    )
    if not receipts:
        return _History((), (), initial_cycle)

    if any(
        receipt.get("subject") != initial_cycle.review_cycle_id
        or not (receipt.get("event_key") or "").startswith(key_prefix)
        for receipt in receipts
    ):
        raise ReviewError("review receipt history has a mismatched cycle binding")

    first = receipts[0]
    first_status = _status_from_receipt(first)
    first_transition = apply_review_verdict(
        initial_cycle,
        ReviewVerdict(
            first_status,
            "Stored reviewer verdict.",
            () if first_status is ReviewStatus.PASS else ("Stored finding.",),
        ),
        _artifact_digest(first),
    )
    transitions = [first_transition]
    if first_status is not ReviewStatus.FAIL:
        if not _matches_receipts(initial_cycle, receipts, tuple(transitions), allow_prefix=True):
            raise ReviewError("review receipt history is inconsistent")
        return _History(receipts, tuple(transitions), first_transition.cycle)

    if len(receipts) == 1:
        if not _matches_receipts(initial_cycle, receipts, tuple(transitions), allow_prefix=True):
            raise ReviewError("review receipt history is inconsistent")
        return _History(receipts, tuple(transitions), first_transition.cycle)

    revision_receipt = receipts[1]
    revision_digest = _artifact_digest(revision_receipt)
    dispatch_transition = dispatch_review_correction(first_transition.cycle, revision_digest)
    transitions.append(dispatch_transition)
    if len(receipts) == 2:
        if not _matches_receipts(initial_cycle, receipts, tuple(transitions), allow_prefix=True):
            raise ReviewError("review receipt history is inconsistent")
        return _History(receipts, tuple(transitions), dispatch_transition.cycle)

    reviewed_receipt = receipts[2]
    reviewed_status = _status_from_receipt(reviewed_receipt)
    reviewed_transition = apply_review_verdict(
        dispatch_transition.cycle,
        ReviewVerdict(
            reviewed_status,
            "Stored reviewer verdict.",
            () if reviewed_status is ReviewStatus.PASS else ("Stored finding.",),
        ),
        _artifact_digest(reviewed_receipt),
    )
    transitions.append(reviewed_transition)
    if not _matches_receipts(initial_cycle, receipts, tuple(transitions), allow_prefix=True):
        raise ReviewError("review receipt history is inconsistent")

    return _History(receipts, tuple(transitions), reviewed_transition.cycle)


def _response(
    cycle: ReviewCycle,
    transitions: tuple[ReviewTransition, ...],
    *,
    exit_code: int,
) -> BridgeResult:
    public_state = {
        ReviewPhase.REVIEWED_FOR_JOSEPH: "REVIEWED_FOR_JOSEPH",
        ReviewPhase.REVISION_REQUIRED: "REVISION_REQUIRED",
        ReviewPhase.AWAITING_REVIEW_AFTER_CORRECTION: "REVISION_REQUIRED",
        ReviewPhase.ESCALATE_TO_JOSEPH: "ESCALATE_TO_JOSEPH",
        ReviewPhase.STOPPED: "STOPPED",
    }[cycle.phase]
    event_keys = [
        f"review-{cycle.review_cycle_id.removeprefix('review-')}-"
        f"{event.sequence:02d}-{event.event.value.lower()}"
        for transition in transitions
        for event in transition.events
    ]
    return BridgeResult(
        response={
            "review_cycle_id": cycle.review_cycle_id,
            "state": public_state,
            "correction_count": cycle.correction_count,
            "correction_available": cycle.correction_available,
            "receipt_event_keys": event_keys,
        },
        exit_code=exit_code,
    )


def _stopped(cycle: ReviewCycle, correction_count: int | None = None) -> BridgeResult:
    return BridgeResult(
        response={
            "review_cycle_id": cycle.review_cycle_id,
            "state": "STOPPED",
            "correction_count": (
                cycle.correction_count if correction_count is None else correction_count
            ),
            "correction_available": False,
            "receipt_event_keys": [],
        },
        exit_code=2,
    )


def process_request(raw_request: str, store: RunStore, occurred_at: datetime) -> BridgeResult:
    """Validate one request, reconstruct its cycle from M2 receipts, and append its transition."""

    request = _parse_request(raw_request)
    if not isinstance(store, RunStore):
        raise BridgeRequestError("bridge requires the existing M2 RunStore")
    try:
        store.run_directory(request.run_id)
        cycle = start_review_cycle(
            request.run_id,
            request.subject,
            request.initial_artifact_sha256,
        )
    except (ReviewError, StorageError, ValueError) as exc:
        raise BridgeRequestError("bridge review identity is invalid") from exc

    try:
        with _run_lock(store, request.run_id):
            return _process_locked_request(request, store, cycle, occurred_at)
    except (OSError, StorageError):
        return _stopped(cycle)


def _process_locked_request(
    request: _BridgeRequest,
    store: RunStore,
    cycle: ReviewCycle,
    occurred_at: datetime,
) -> BridgeResult:
    try:
        history = _load_history(store, cycle)
        if request.subject.startswith("nba-proposal-v"):
            from fifth_pick.product_review import review_material

            exact = review_material(store, request.run_id)
            if (
                exact["subject"] != request.subject
                or exact["initial_artifact_sha256"] != request.initial_artifact_sha256
                or exact["current_artifact_sha256"] != request.current_artifact_sha256
                or exact["revision"]
                != (0 if request.kind == "REVISION_DISPATCHED" else request.revision)
            ):
                return _stopped(history.cycle)
    except (ReviewError, OSError, StorageError, ValueError):
        return _stopped(cycle)

    if request.kind == "VERDICT":
        assert request.verdict_json is not None
        try:
            parsed_verdict = parse_review_verdict(_reviewer_json(request.verdict_json))
        except ReviewError:
            return _stopped(history.cycle, history.cycle.correction_count)

        revision = request.revision
        if revision == 0:
            if history.transitions and history.cycle.phase is not ReviewPhase.AWAITING_REVIEW:
                transition = apply_review_verdict(
                    cycle,
                    parsed_verdict,
                    request.current_artifact_sha256,
                )
                if not _matches_receipts(
                    cycle,
                    history.receipts,
                    (transition,),
                    allow_prefix=True,
                ):
                    return _stopped(history.cycle, history.cycle.correction_count)
            elif history.cycle.phase is not ReviewPhase.AWAITING_REVIEW:
                return _stopped(history.cycle, history.cycle.correction_count)
            else:
                transition = apply_review_verdict(
                    cycle,
                    parsed_verdict,
                    request.current_artifact_sha256,
                )
        else:
            if len(history.transitions) < 2 or history.cycle.correction_count != 1:
                return _stopped(history.cycle, history.cycle.correction_count)
            dispatch_transition = history.transitions[1]
            if history.cycle.phase is ReviewPhase.AWAITING_REVIEW_AFTER_CORRECTION:
                transition = apply_review_verdict(
                    history.cycle,
                    parsed_verdict,
                    request.current_artifact_sha256,
                )
            else:
                transition = apply_review_verdict(
                    dispatch_transition.cycle,
                    parsed_verdict,
                    request.current_artifact_sha256,
                )
                if not _matches_receipts(
                    cycle,
                    history.receipts,
                    (*history.transitions[:2], transition),
                    allow_prefix=True,
                ):
                    return _stopped(history.cycle, history.cycle.correction_count)
    else:
        if request.subject.startswith("nba-proposal-v") and any(
            row["event"] == "REVISION_ATTEMPT" for row in store.read_receipts(cycle.run_id)
        ):
            return _stopped(history.cycle, history.cycle.correction_count)
        if len(history.transitions) == 1 and history.cycle.phase is ReviewPhase.REVISION_REQUIRED:
            failed_digest = history.transitions[0].events[0].artifact_sha256
            if request.current_artifact_sha256 != failed_digest:
                return _stopped(history.cycle, history.cycle.correction_count)
            transition = dispatch_review_correction(
                history.cycle,
                request.current_artifact_sha256,
            )
        else:
            # A persisted attempt consumes the launch authorization, even after interruption.
            return _stopped(history.cycle, history.cycle.correction_count)

    if transition.cycle.phase is ReviewPhase.STOPPED:
        return _stopped(history.cycle, history.cycle.correction_count)

    try:
        if request.kind == "VERDICT" and request.subject.startswith("nba-proposal-v"):
            event = transition.events[0]
            key = f"product-verdict-{cycle.review_cycle_id}-{event.revision}"
            data = json.dumps(
                {
                    "artifact_sha256": event.artifact_sha256,
                    "status": parsed_verdict.status.value,
                    "summary": parsed_verdict.summary,
                    "findings": parsed_verdict.findings,
                },
                sort_keys=True,
            ).encode()
            path = store.run_directory(cycle.run_id) / f"{key}.json"
            if path.exists() and path.read_bytes() != data:
                return _stopped(history.cycle, history.cycle.correction_count)
            _atomic_write(path, data)
            store.append_receipt(
                Receipt(
                    occurred_at.isoformat(),
                    "PRODUCT_REVIEW_VERDICT",
                    event.result,
                    event.artifact_sha256,
                    "fifth-pick-reviewer",
                    hashlib.sha256(data).hexdigest(),
                    cycle.run_id,
                    key,
                )
            )
        appends = append_review_receipts(store, transition, occurred_at)
    except (ReviewError, OSError, StorageError, ValueError):
        return _stopped(history.cycle, history.cycle.correction_count)
    if request.kind == "REVISION_DISPATCHED" and not (len(appends) == 1 and appends[0].created):
        return _stopped(transition.cycle)
    return _response(transition.cycle, (transition,), exit_code=0)


def main(*, store: RunStore | None = None, occurred_at: datetime | None = None) -> int:
    """Read one JSON request and write exactly one JSON response, with diagnostics on stderr."""

    try:
        result = process_request(
            sys.stdin.read(),
            application_run_store() if store is None else store,
            datetime.now(UTC) if occurred_at is None else occurred_at,
        )
    except BridgeRequestError as exc:
        print(f"fifth-pick review bridge: {exc}", file=sys.stderr)
        return 2

    sys.stdout.write(json.dumps(result.response, separators=(",", ":"), sort_keys=True) + "\n")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
