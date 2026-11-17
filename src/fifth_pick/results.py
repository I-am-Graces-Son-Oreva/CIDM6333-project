"""M9 result recording bound to Joseph's receipt-verified approved slate."""

import hashlib
import json
import math
import re
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Final, cast

from fifth_pick.approval import JOSEPH_ACTOR, ApprovalError, load_approved_final
from fifth_pick.errors import StorageError
from fifth_pick.finalization import AUDIT_FILENAME
from fifth_pick.models import Provenance, ReasonCode, Result, ResultStatus
from fifth_pick.receipts import Receipt, redact_text
from fifth_pick.sources.odds_api import SOURCE_ID
from fifth_pick.storage import RunStore, _atomic_write, application_run_store

RESULTS_FILENAME: Final[str] = "results.json"
RESULT_RECORDED_EVENT: Final[str] = "RESULT_RECORDED"
SETTLEMENT_CONFIRMED: Final[str] = "SETTLEMENT_CONFIRMED"
LOOKUP_ATTEMPT_CONFIRMED: Final[str] = "LOOKUP_ATTEMPT_CONFIRMED"
_SHA256_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_DETERMINATE_RESULTS: Final[frozenset[ResultStatus]] = frozenset(
    {
        ResultStatus.HIT,
        ResultStatus.MISS,
        ResultStatus.PUSH,
        ResultStatus.VOID,
        ResultStatus.DNP,
    }
)
_RESULT_RECORD_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "slate_version",
        "decision_receipt_key",
        "selection_id",
        "selection",
        "t20_review_event_key",
        "t20_projection",
        "result",
        "fixture",
        "result_receipt_event_key",
        "evidence_excerpt",
        "evidence_confirmation",
    }
)
_RESULT_FIELDS: Final[frozenset[str]] = frozenset(
    {"outcome", "subject", "source", "recorded_at", "reason", "provenance"}
)
_PROVENANCE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "source",
        "retrieved_at",
        "source_timestamp",
        "access_method",
        "reference",
        "payload_hash",
    }
)


class ResultError(ValueError):
    """Raised when result evidence or its approved-selection binding is invalid."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _serialize_provenance(provenance: Provenance | None) -> dict[str, str] | None:
    if provenance is None:
        return None
    return {
        "source": redact_text(provenance.source),
        "retrieved_at": provenance.retrieved_at.isoformat(),
        "source_timestamp": provenance.source_timestamp.isoformat(),
        "access_method": redact_text(provenance.access_method),
        "reference": redact_text(provenance.reference),
        "payload_hash": provenance.payload_hash,
    }


def _serialize_result(result: Result) -> dict[str, object]:
    return {
        "outcome": result.outcome.value,
        "subject": result.subject,
        "source": redact_text(result.source),
        "recorded_at": result.recorded_at.isoformat(),
        "reason": None if result.reason is None else result.reason.value,
        "provenance": _serialize_provenance(result.provenance),
    }


def _result_fingerprint(result: Result) -> str:
    record = _serialize_result(result)
    record.pop("recorded_at")
    provenance = record.get("provenance")
    if isinstance(provenance, dict):
        provenance.pop("retrieved_at")
    return hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()


def _validate_result(result: Result, selection_id: str) -> bool:
    if not isinstance(result, Result):
        raise ResultError("result must be a typed M2 Result")
    if result.subject != selection_id:
        raise ResultError("result subject must equal the approved selection candidate_key")
    if not _is_aware(result.recorded_at):
        raise ResultError("result recorded_at must be timezone-aware")
    if result.outcome is ResultStatus.RESULT_UNAVAILABLE:
        if result.reason is not ReasonCode.RESULT_UNAVAILABLE:
            raise ResultError("RESULT UNAVAILABLE requires its named reason code")
    elif result.outcome in _DETERMINATE_RESULTS and result.provenance is None:
        raise ResultError("a determinate result requires provenance")

    provenance = result.provenance
    if provenance is not None:
        if (
            provenance.source != result.source
            or not _is_aware(provenance.retrieved_at)
            or not _is_aware(provenance.source_timestamp)
            or provenance.source_timestamp > provenance.retrieved_at
            or provenance.retrieved_at > result.recorded_at
            or _SHA256_PATTERN.fullmatch(provenance.payload_hash) is None
            or selection_id not in provenance.reference
        ):
            raise ResultError("result provenance is inconsistent or not selection-bound")
        source_reference = f"{result.source} {provenance.reference}".casefold()
        if (
            ("odds-api" in source_reference and "scores" in source_reference)
            or "/scores" in source_reference
            or "team-score" in source_reference
        ):
            raise ResultError("team-score data is not an adjudicated player result")

    fixture_markers = (
        result.source == "synthetic-fixture",
        provenance is not None and provenance.source == "synthetic-fixture",
        provenance is not None and provenance.access_method == "synthetic-fixture",
        provenance is not None and provenance.reference.startswith("fixture:"),
    )
    if any(fixture_markers) and not all(fixture_markers):
        raise ResultError("fixture result provenance is inconsistently marked")
    return all(fixture_markers)


def _validate_result_evidence(
    result: Result,
    evidence_excerpt: object,
    evidence_confirmation: object,
) -> str | None:
    provenance = result.provenance
    if result.outcome is ResultStatus.RESULT_UNAVAILABLE:
        if evidence_excerpt is None:
            if provenance is not None or evidence_confirmation is not None:
                raise ResultError("unavailable result evidence fields are incomplete")
            return None
        if provenance is None or evidence_confirmation != LOOKUP_ATTEMPT_CONFIRMED:
            raise ResultError("lookup evidence requires matching provenance and confirmation")
    elif (
        evidence_excerpt is None
        or provenance is None
        or evidence_confirmation != SETTLEMENT_CONFIRMED
    ):
        raise ResultError("determinate result requires evidence and settlement confirmation")

    if not isinstance(evidence_excerpt, str) or not evidence_excerpt.strip():
        raise ResultError("evidence excerpt must be non-empty text")
    if redact_text(evidence_excerpt) != evidence_excerpt:
        raise ResultError("evidence excerpt must not contain sensitive URL query values")
    if provenance is None:
        raise ResultError("evidence excerpt has no source provenance")
    expected_hash = hashlib.sha256(evidence_excerpt.encode("utf-8")).hexdigest()
    if provenance.payload_hash != expected_hash:
        raise ResultError("evidence excerpt does not match its provenance payload hash")
    return cast(str | None, evidence_confirmation)


def _validate_t20_review(
    review: dict[str, object],
    run_id: str,
    selection_id: str,
    receipts: tuple[dict[str, str | None], ...],
) -> tuple[str, int | float]:
    if review.get("run_id") != run_id or review.get("candidate_key") != selection_id:
        raise ResultError("M7 review audit has an invalid run or selection binding")
    event_key = review.get("event_key")
    if not isinstance(event_key, str):
        raise ResultError("M7 review audit has no event key")
    review_payload = {key: value for key, value in review.items() if key != "event_key"}
    expected_key = (
        f"t20-review-{hashlib.sha256(_canonical_json(review_payload).encode('utf-8')).hexdigest()}"
    )
    if event_key != expected_key:
        raise ResultError("M7 review audit content hash does not match")
    try:
        reviewed_at_text = review["reviewed_at"]
        if not isinstance(reviewed_at_text, str):
            raise TypeError("reviewed_at must be text")
        reviewed_at = datetime.fromisoformat(reviewed_at_text)
    except (KeyError, TypeError, ValueError) as exc:
        raise ResultError("M7 review timestamp is malformed") from exc
    reason_codes = review.get("reason_codes")
    audit_reasons = review.get("audit_reasons")
    conclusion = review.get("conclusion")
    if (
        not _is_aware(reviewed_at)
        or not isinstance(reason_codes, list)
        or any(not isinstance(item, str) for item in reason_codes)
        or not isinstance(audit_reasons, list)
        or any(not isinstance(item, str) for item in audit_reasons)
        or not isinstance(conclusion, str)
    ):
        raise ResultError("M7 review audit is malformed")
    expected_receipt = Receipt(
        timestamp=reviewed_at.isoformat(),
        event="T20_REVIEW",
        result=conclusion,
        subject=selection_id,
        source=SOURCE_ID,
        reason="; ".join((*reason_codes, *audit_reasons)),
        run_id=run_id,
        event_key=event_key,
    ).to_dict()
    if tuple(item for item in receipts if item.get("event_key") == event_key) != (
        expected_receipt,
    ):
        raise ResultError("M7 review audit has no matching application receipt")
    if (
        conclusion not in {"STILL STRONG", "DOWNGRADED"}
        or review.get("readiness_passed") is not True
        or review.get("blocked") is not False
    ):
        raise ResultError("approved selection has no positive receipt-bound M7 review")
    projection = review.get("projection")
    t20_projection = projection.get("at_t20") if isinstance(projection, dict) else None
    if (
        isinstance(t20_projection, bool)
        or not isinstance(t20_projection, int | float)
        or not math.isfinite(t20_projection)
    ):
        raise ResultError("approved selection has no trustworthy T-20 projection")
    return event_key, t20_projection


def _approved_context(
    store: RunStore,
    run_id: str,
    selection_id: str,
) -> tuple[dict[str, object], dict[str, object], str, int | float]:
    try:
        final = load_approved_final(store, run_id)
    except (ApprovalError, StorageError, ValueError) as exc:
        raise ResultError("result grading requires Joseph's receipt-verified APPROVE") from exc

    approval = final["approval"]
    assert isinstance(approval, dict)
    official_final = approval["official_final"]
    assert isinstance(official_final, list)
    selections = tuple(
        item
        for item in official_final
        if isinstance(item, dict) and item.get("candidate_key") == selection_id
    )
    if len(selections) != 1:
        raise ResultError("selection_id is not in the exact Joseph-approved final set")
    slate_version = final["slate_version"]
    decision_receipt_key = approval["decision_receipt_key"]
    if (
        isinstance(slate_version, bool)
        or not isinstance(slate_version, int)
        or slate_version < 1
        or not isinstance(decision_receipt_key, str)
        or not decision_receipt_key
    ):
        raise ResultError("approved final state has no valid slate version or decision receipt")

    if final.get("audit_file") != AUDIT_FILENAME:
        raise ResultError("approved final state names an unsupported audit file")
    run_directory = store.run_directory(run_id)
    audit_path = run_directory / AUDIT_FILENAME
    if not audit_path.resolve().is_relative_to(run_directory):
        raise ResultError("M8 audit path escapes the run directory")
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResultError("M8 audit is unreadable; refusing to grade a result") from exc
    if not isinstance(audit, dict) or audit.get("run_id") != run_id:
        raise ResultError("M8 audit has an invalid run binding")
    slate = audit.get("slate")
    board = slate.get("authoritative_board") if isinstance(slate, dict) else None
    if not isinstance(board, dict) or board.get("evidence_mode") not in ("live", "fixture"):
        raise ResultError("M8 audit has no valid authoritative evidence mode")
    if board["evidence_mode"] == "live" and store.root != application_run_store().root:
        raise ResultError("LIVE result recording requires the application-owned RunStore")

    reviews = audit.get("m7_reviews")
    if not isinstance(reviews, list):
        raise ResultError("M8 audit has no M7 review records")
    matching_reviews = tuple(
        item
        for item in reviews
        if isinstance(item, dict) and item.get("candidate_key") == selection_id
    )
    if len(matching_reviews) != 1:
        raise ResultError("approved selection has no unique M7 review audit")
    review = matching_reviews[0]
    try:
        receipts = store.read_receipts(run_id)
    except StorageError as exc:
        raise ResultError("M8 receipts are unreadable; refusing to grade a result") from exc
    event_key, t20_projection = _validate_t20_review(
        review,
        run_id,
        selection_id,
        receipts,
    )
    return final, selections[0], event_key, t20_projection


def _read_results(
    store: RunStore,
    run_id: str,
    approved_final: dict[str, object],
) -> tuple[dict[str, object], Path]:
    run_directory = store.run_directory(run_id)
    path = run_directory / RESULTS_FILENAME
    if not path.resolve().is_relative_to(run_directory):
        raise ResultError("results artifact path escapes the run directory")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"schema_version": 1, "run_id": run_id, "results": []}, path
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResultError("existing results.json is unreadable") from exc
    if (
        not isinstance(raw, dict)
        or set(raw) != {"schema_version", "run_id", "results"}
        or isinstance(raw.get("schema_version"), bool)
        or raw.get("schema_version") != 1
        or raw.get("run_id") != run_id
        or not isinstance(raw.get("results"), list)
        or any(not isinstance(item, dict) for item in raw["results"])
    ):
        raise ResultError("existing results.json has an invalid schema or run binding")
    try:
        audit = json.loads(
            (store.run_directory(run_id) / AUDIT_FILENAME).read_text(encoding="utf-8")
        )
        receipts = store.read_receipts(run_id)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, StorageError) as exc:
        raise ResultError(
            "existing results cannot be verified against M8 audit and receipts"
        ) from exc
    if not isinstance(audit, dict) or audit.get("run_id") != run_id:
        raise ResultError("existing M8 audit has an invalid run binding")
    for item in raw["results"]:
        _validate_stored_result(item, run_id, approved_final, audit, receipts)
    return raw, path


def _write_results(path: Path, record: dict[str, object]) -> None:
    content = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    try:
        _atomic_write(path, content.encode("utf-8"))
    except OSError as exc:
        raise ResultError("cannot persist results.json") from exc


def _result_event_key(slate_version: int, selection_id: str) -> str:
    return f"result-recorded-{slate_version}-{selection_id}"


def _result_receipt_reason(result: Result, evidence_confirmation: str | None) -> str:
    reason = f"RESULT_SHA256={_result_fingerprint(result)}"
    if result.reason is not None:
        reason += f"; {result.reason.value}"
    if result.provenance is not None:
        reason += f"; PROVENANCE={redact_text(result.provenance.reference)}"
        reason += f"; EVIDENCE_SHA256={result.provenance.payload_hash}"
    if evidence_confirmation is not None:
        reason += f"; EVIDENCE_CONFIRMATION={evidence_confirmation}"
    return reason


def _deserialize_result(
    data: dict[str, object],
    selection_id: str,
) -> tuple[Result, bool]:
    if set(data) != _RESULT_FIELDS:
        raise ResultError("stored result has unknown or missing fields")
    subject = data["subject"]
    source = data["source"]
    recorded_at_text = data["recorded_at"]
    if (
        not isinstance(subject, str)
        or not isinstance(source, str)
        or not isinstance(recorded_at_text, str)
    ):
        raise ResultError("stored result identity or timestamp is malformed")
    try:
        outcome = ResultStatus(data["outcome"])
        recorded_at = datetime.fromisoformat(recorded_at_text)
        reason = None if data["reason"] is None else ReasonCode(data["reason"])
    except (TypeError, ValueError) as exc:
        raise ResultError("stored result vocabulary or timestamp is invalid") from exc

    raw_provenance = data["provenance"]
    provenance = None
    if raw_provenance is not None:
        if (
            not isinstance(raw_provenance, dict)
            or set(raw_provenance) != _PROVENANCE_FIELDS
            or any(
                not isinstance(raw_provenance[field], str)
                for field in (
                    "source",
                    "retrieved_at",
                    "source_timestamp",
                    "access_method",
                    "reference",
                    "payload_hash",
                )
            )
        ):
            raise ResultError("stored result provenance is malformed")
        try:
            provenance = Provenance(
                source=raw_provenance["source"],
                retrieved_at=datetime.fromisoformat(raw_provenance["retrieved_at"]),
                source_timestamp=datetime.fromisoformat(raw_provenance["source_timestamp"]),
                access_method=raw_provenance["access_method"],
                reference=raw_provenance["reference"],
                payload_hash=raw_provenance["payload_hash"],
            )
        except (TypeError, ValueError) as exc:
            raise ResultError("stored result provenance is invalid") from exc
    try:
        result = Result(
            outcome=outcome,
            subject=subject,
            source=source,
            recorded_at=recorded_at,
            reason=reason,
            provenance=provenance,
        )
    except (TypeError, ValueError) as exc:
        raise ResultError("stored result has invalid typed fields") from exc
    fixture = _validate_result(result, selection_id)
    return result, fixture


def _validate_stored_result(
    entry: dict[str, object],
    run_id: str,
    approved_final: dict[str, object],
    audit: dict[str, object],
    receipts: tuple[dict[str, str | None], ...],
) -> None:
    if set(entry) != _RESULT_RECORD_FIELDS:
        raise ResultError("stored result record has unknown or missing fields")
    slate_version = entry["slate_version"]
    selection_id = entry["selection_id"]
    decision_key = entry["decision_receipt_key"]
    result_receipt_key = entry["result_receipt_event_key"]
    t20_review_key = entry["t20_review_event_key"]
    selection = entry["selection"]
    approval = approved_final.get("approval")
    approved_selections = approval.get("official_final") if isinstance(approval, dict) else None
    approved_selection = (
        tuple(
            item
            for item in approved_selections
            if isinstance(item, dict) and item.get("candidate_key") == selection_id
        )
        if isinstance(approved_selections, list)
        else ()
    )
    if (
        isinstance(slate_version, bool)
        or not isinstance(slate_version, int)
        or slate_version < 1
        or not isinstance(selection_id, str)
        or _SHA256_PATTERN.fullmatch(selection_id) is None
        or not isinstance(decision_key, str)
        or not isinstance(result_receipt_key, str)
        or not isinstance(t20_review_key, str)
        or not isinstance(selection, dict)
        or selection.get("candidate_key") != selection_id
        or len(approved_selection) != 1
        or selection != approved_selection[0]
        or slate_version != approved_final.get("slate_version")
        or decision_key
        != (approval.get("decision_receipt_key") if isinstance(approval, dict) else None)
        or isinstance(entry["t20_projection"], bool)
        or not isinstance(entry["t20_projection"], int | float)
        or not math.isfinite(entry["t20_projection"])
        or not isinstance(entry["fixture"], bool)
        or result_receipt_key != _result_event_key(slate_version, selection_id)
    ):
        raise ResultError("stored result selection binding is malformed")

    result_data = entry["result"]
    if not isinstance(result_data, dict):
        raise ResultError("stored result payload is malformed")
    result, fixture = _deserialize_result(result_data, selection_id)
    if fixture is not entry["fixture"]:
        raise ResultError("stored result fixture marker does not match its provenance")
    evidence_confirmation = _validate_result_evidence(
        result,
        entry["evidence_excerpt"],
        entry["evidence_confirmation"],
    )

    decisions = audit.get("joseph_decisions")
    if not isinstance(decisions, list):
        raise ResultError("M8 audit has no Joseph decision trail")
    matching_decisions = tuple(
        decision
        for decision in decisions
        if isinstance(decision, dict) and decision.get("receipt_event_key") == decision_key
    )
    if len(matching_decisions) != 1:
        raise ResultError("stored result has no unique M8 approval audit reference")
    decision = matching_decisions[0]
    decision_selection = decision.get("selection")
    if (
        decision.get("action") != "APPROVE"
        or decision.get("slate_version") != slate_version
        or not isinstance(decision_selection, list)
        or selection_id not in decision_selection
    ):
        raise ResultError("stored result is not in the referenced Joseph-approved slate")
    matching_approval_receipts = tuple(
        receipt for receipt in receipts if receipt.get("event_key") == decision_key
    )
    if (
        len(matching_approval_receipts) != 1
        or matching_approval_receipts[0].get("event") != "JOSEPH_APPROVED"
        or matching_approval_receipts[0].get("result") != "APPROVE"
        or matching_approval_receipts[0].get("run_id") != run_id
        or matching_approval_receipts[0].get("source") != JOSEPH_ACTOR
        or matching_approval_receipts[0].get("reason") != f"SLATE_VERSION={slate_version}"
    ):
        raise ResultError("stored result approval reference has no matching Joseph receipt")

    reviews = audit.get("m7_reviews")
    if not isinstance(reviews, list):
        raise ResultError("M8 audit has no M7 review records")
    matching_reviews = tuple(
        review
        for review in reviews
        if isinstance(review, dict)
        and review.get("candidate_key") == selection_id
        and review.get("event_key") == t20_review_key
    )
    if len(matching_reviews) != 1:
        raise ResultError("stored result has no unique M7 review audit reference")
    review_event_key, review_projection = _validate_t20_review(
        matching_reviews[0],
        run_id,
        selection_id,
        receipts,
    )
    if review_event_key != t20_review_key or entry["t20_projection"] != review_projection:
        raise ResultError("stored result T-20 projection does not match its M7 review")

    expected_result_receipt = Receipt(
        timestamp=result.recorded_at.isoformat(),
        event=RESULT_RECORDED_EVENT,
        result=result.outcome.value,
        subject=selection_id,
        source=redact_text(result.source),
        reason=_result_receipt_reason(result, evidence_confirmation),
        run_id=run_id,
        event_key=result_receipt_key,
    ).to_dict()
    if result_receipt_key != _result_event_key(slate_version, selection_id) or tuple(
        receipt for receipt in receipts if receipt.get("event_key") == result_receipt_key
    ) != (expected_result_receipt,):
        raise ResultError("stored result has no matching RESULT_RECORDED receipt")


def _same_result(existing: dict[str, object], proposed: dict[str, object]) -> bool:
    if any(
        existing.get(field) != proposed.get(field)
        for field in (
            "slate_version",
            "decision_receipt_key",
            "selection_id",
            "selection",
            "t20_review_event_key",
            "t20_projection",
            "fixture",
            "result_receipt_event_key",
            "evidence_excerpt",
            "evidence_confirmation",
        )
    ):
        return False
    existing_result = existing.get("result")
    proposed_result = proposed.get("result")
    if not isinstance(existing_result, dict) or not isinstance(proposed_result, dict):
        return False
    existing_payload = dict(existing_result)
    proposed_payload = dict(proposed_result)
    existing_payload.pop("recorded_at", None)
    proposed_payload.pop("recorded_at", None)
    for payload in (existing_payload, proposed_payload):
        provenance = payload.get("provenance")
        if isinstance(provenance, dict):
            provenance.pop("retrieved_at", None)
    return existing_payload == proposed_payload


def record_result(
    store: RunStore,
    run_id: str,
    selection_id: str,
    result: Result,
    *,
    evidence_excerpt: str | None,
    evidence_confirmation: str | None,
) -> Path:
    """Persist a sourced settlement and its verified excerpt for an approved selection."""

    if type(store) is not RunStore:
        raise ResultError("result recording requires the M2 RunStore")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ResultError("run_id must be non-empty")
    if not isinstance(selection_id, str) or _SHA256_PATTERN.fullmatch(selection_id) is None:
        raise ResultError("selection_id must be the M8 candidate_key")
    fixture = _validate_result(result, selection_id)
    evidence_confirmation = _validate_result_evidence(
        result,
        evidence_excerpt,
        evidence_confirmation,
    )

    try:
        final, selection, t20_event_key, t20_projection = _approved_context(
            store,
            run_id,
            selection_id,
        )
    except StorageError as exc:
        raise ResultError("approved result context could not be read") from exc
    approval = final["approval"]
    assert isinstance(approval, dict)
    slate_version = final["slate_version"]
    assert isinstance(slate_version, int)
    decision_receipt_key = approval["decision_receipt_key"]
    assert isinstance(decision_receipt_key, str)
    result_event_key = f"result-recorded-{slate_version}-{selection_id}"
    result_payload = _serialize_result(result)
    result_entry: dict[str, object] = {
        "slate_version": slate_version,
        "decision_receipt_key": decision_receipt_key,
        "selection_id": selection_id,
        "selection": selection,
        "t20_review_event_key": t20_event_key,
        "t20_projection": t20_projection,
        "result": result_payload,
        "fixture": fixture,
        "result_receipt_event_key": result_event_key,
        "evidence_excerpt": evidence_excerpt,
        "evidence_confirmation": evidence_confirmation,
    }
    results_record, results_path = _read_results(store, run_id, final)
    results_list = cast(list[dict[str, object]], results_record["results"])
    existing = tuple(
        item
        for item in results_list
        if item.get("slate_version") == slate_version and item.get("selection_id") == selection_id
    )
    if len(existing) > 1 or (existing and not _same_result(existing[0], result_entry)):
        raise ResultError("a conflicting result already exists for this approved selection")

    reason = _result_receipt_reason(result, evidence_confirmation)
    try:
        persisted = store.append_receipt(
            Receipt(
                timestamp=result.recorded_at.isoformat(),
                event=RESULT_RECORDED_EVENT,
                result=result.outcome.value,
                subject=selection_id,
                source=redact_text(result.source),
                reason=reason,
                run_id=run_id,
                event_key=result_event_key,
            )
        )
    except StorageError as exc:
        raise ResultError("result receipt conflicts with an existing settlement") from exc
    persisted_timestamp = persisted.receipt.get("timestamp")
    if not isinstance(persisted_timestamp, str):
        raise ResultError("persisted result receipt has no timestamp")
    try:
        persisted_at = datetime.fromisoformat(persisted_timestamp)
    except ValueError as exc:
        raise ResultError("persisted result receipt timestamp is invalid") from exc
    if not _is_aware(persisted_at):
        raise ResultError("persisted result receipt timestamp must be timezone-aware")
    persisted_result = replace(result, recorded_at=persisted_at)
    if (
        persisted_result.provenance is not None
        and persisted_result.provenance.retrieved_at > persisted_at
    ):
        persisted_result = replace(
            persisted_result,
            provenance=replace(persisted_result.provenance, retrieved_at=persisted_at),
        )
    if _validate_result(persisted_result, selection_id) != fixture:
        raise ResultError("persisted result receipt changed fixture provenance")
    result_entry["result"] = _serialize_result(persisted_result)
    if existing:
        results_list = [result_entry if item is existing[0] else item for item in results_list]
    else:
        results_list.append(result_entry)
    results_record["results"] = results_list
    results_list.sort(key=lambda item: (item["slate_version"], item["selection_id"]))
    _write_results(results_path, results_record)
    return results_path
