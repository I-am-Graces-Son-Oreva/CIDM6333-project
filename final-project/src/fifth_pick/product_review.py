"""Bind actual product evidence to the existing native Reviewer receipt cycle."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime

from fifth_pick.approval import _read_final, load_pending_proposal
from fifth_pick.finalization import (
    AUDIT_FILENAME,
    FINAL_FILENAME,
    NO_ENTRY_RECOMMENDATION,
    _append_proposal_receipt,
    _load_t20_reviews,
    _manifest_start_board,
    _validate_pending_t20,
    _write_json,
    proposal_fingerprint,
)
from fifth_pick.fixture_workflow import audit_view, is_fixture_workflow
from fifth_pick.receipts import Receipt
from fifth_pick.results import RESULTS_FILENAME, _read_results
from fifth_pick.review import ReviewError, ReviewPhase, start_review_cycle
from fifth_pick.review_bridge import _artifact_digest, _load_history, _run_lock
from fifth_pick.slate_manifest import read_slate_run_context
from fifth_pick.snapshots import read_application_snapshot_ledger
from fifth_pick.sources.base import EvidenceMode
from fifth_pick.sources.odds_api import SOURCE_ID
from fifth_pick.storage import RunStore, _atomic_write, application_run_store

_CORRECTION = "product-review-correction"


def expired_live_selections(store: RunStore, run_id: str, proposal: dict) -> tuple[str, ...]:
    """Flag expired pending lines without rewriting or releasing another proposal."""
    board = _manifest_start_board(read_slate_run_context(store, run_id))
    if board.evidence_mode is not EvidenceMode.LIVE or proposal["state"] != "AWAITING_JOSEPH":
        return ()
    now = datetime.now(UTC)
    tipoffs = {event.event_id: event.commence_time for event in board.events}
    return tuple(
        row["candidate_key"]
        for row in proposal["proposed"]
        if row["event"] not in tipoffs or now >= tipoffs[row["event"]]
    )


def _correction_binding(store: RunStore, run_id: str) -> dict[str, object] | None:
    path = store.run_directory(run_id) / f"{_CORRECTION}.json"
    receipts = [r for r in store.read_receipts(run_id) if r["event_key"] == _CORRECTION]
    if not receipts and not path.exists():
        return None
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
        if (
            len(receipts) != 1
            or receipts[0]["event"] != "PRODUCT_PROPOSAL_CORRECTED"
            or receipts[0]["source"] != "fifth-pick-review-controller"
            or receipts[0]["run_id"] != run_id
            or receipts[0]["subject"] != value["corrected_proposal"]
            or receipts[0]["reason"] != hashlib.sha256(raw).hexdigest()
            or hashlib.sha256(value["original_material"].encode()).hexdigest()
            != value["original_digest"]
        ):
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ReviewError("product correction binding is incomplete or invalid") from exc
    return value


def operator_audit(store: RunStore, run_id: str) -> dict[str, object]:
    """Open receipt-only attempts for inspection without admitting them as product evidence."""
    if store.root != application_run_store().root:
        return product_audit(store, run_id)
    receipts = store.read_receipts(run_id)
    source_receipts = [row for row in receipts if row["source"] == SOURCE_ID]
    if not any(
        row["event"] == "DFS_BOARD_RESERVED"
        and row["result"] == "RESERVED"
        and row["run_id"] == run_id
        for row in source_receipts
    ) or any(row["event"] == "DFS_BOARD_COLLECTED" for row in source_receipts):
        return product_audit(store, run_id)
    if any(row["run_id"] != run_id for row in receipts):
        raise ReviewError("collection receipt run mismatch")
    stopped = any(
        row["event"] == "DFS_BOARD_STOPPED" and row["source"] == SOURCE_ID for row in receipts
    )
    return {
        "run_id": run_id,
        "status": "COLLECTION_STOPPED" if stopped else "COLLECTION_INCOMPLETE",
        "mode": "RECEIPTS_ONLY",
        "final": None,
        "finalization_audit": None,
        "board_manifests": [],
        "snapshots": [],
        "t20_reviews": [],
        "receipts": receipts,
        "results": None,
    }


def product_audit(store: RunStore, run_id: str) -> dict[str, object]:
    """Read actual receipt-verified product evidence in its original mode."""
    if is_fixture_workflow(store, run_id):
        return audit_view(store, run_id)
    if store.root != application_run_store().root:
        raise ReviewError("LIVE review requires the application-owned store")
    context = read_slate_run_context(store, run_id)
    if _manifest_start_board(context).evidence_mode is not EvidenceMode.LIVE:
        raise ReviewError("product review requires a recognized LIVE or fixture run")
    final_record = audit_record = results = None
    directory = store.run_directory(run_id)
    if (directory / FINAL_FILENAME).exists():
        final_record, _ = _read_final(store, run_id)
        if final_record["state"] == "AWAITING_JOSEPH":
            _validate_pending_t20(store, run_id, final_record)
        audit_record = json.loads((directory / AUDIT_FILENAME).read_text(encoding="utf-8"))
        if not isinstance(audit_record, dict) or audit_record.get("run_id") != run_id:
            raise ReviewError("product audit does not match the LIVE run")
        if (directory / RESULTS_FILENAME).exists():
            if final_record["state"] != "APPROVED_BY_JOSEPH":
                raise ReviewError("settlement requires an approved proposal")
            results, _ = _read_results(store, run_id, final_record)
    return {
        "run_id": run_id,
        "mode": EvidenceMode.LIVE.value,
        "final": final_record,
        "finalization_audit": audit_record,
        "board_manifests": [asdict(board) for board in context.event_boards],
        "snapshots": [entry.to_dict() for entry in read_application_snapshot_ledger(run_id)],
        "t20_reviews": _load_t20_reviews(store, run_id),
        "receipts": store.read_receipts(run_id),
        "results": results,
    }


def review_material(store: RunStore, run_id: str) -> dict[str, str | int]:
    """Return exact arguments for the existing /fifth-pick-review command."""
    evidence = product_audit(store, run_id)
    final = evidence["final"]
    audit = evidence["finalization_audit"]
    if not isinstance(final, dict) or not isinstance(audit, dict) or final["state"] == "BLOCKED":
        raise ReviewError("a receipt-verified final proposal is required for product review")
    proposed = {
        field: final[field]
        for field in ("run_id", "slate_version", "slate", "recommendation", "proposed")
    }
    binding = _correction_binding(store, run_id)
    material = json.dumps(
        {
            "purpose": "Review NBA proposal authorization, evidence, timing and discipline.",
            "mode": evidence["mode"],
            "proposal": proposed,
            "proposal_sha256": proposal_fingerprint(final),
            "board_manifests": evidence["board_manifests"],
            "snapshots": evidence["snapshots"],
            "t20_reviews": evidence["t20_reviews"],
            "audit": {key: value for key, value in audit.items() if key != "joseph_decisions"},
            **(
                {
                    "correction": {
                        key: binding[key] for key in ("original_digest", "removed", "reason")
                    }
                }
                if binding
                else {}
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(material.encode()).hexdigest()
    subject = f"nba-proposal-v{final['slate_version']}"
    initial_digest = digest
    revision = 0
    if binding:
        if (
            proposal_fingerprint(final) == binding["corrected_proposal"]
            and final["slate_version"] == binding["corrected_version"]
        ):
            subject = str(binding["subject"])
            initial_digest = str(binding["original_digest"])
            revision = 1
        elif not (
            isinstance(final["slate_version"], int)
            and isinstance(binding["corrected_version"], int)
            and final["slate_version"] > binding["corrected_version"]
            and isinstance(final.get("approval"), dict)
            and final["approval"].get("action") == "MODIFY"
        ):
            raise ReviewError("current proposal does not match the recorded correction")
    return {
        "schema_version": 1,
        "run_id": run_id,
        "subject": subject,
        "initial_artifact_sha256": initial_digest,
        "current_artifact_sha256": digest,
        "revision": revision,
        "review_material": material,
    }


def review_status(store: RunStore, run_id: str) -> dict[str, object]:
    """Read native controller receipts for this exact product proposal."""

    material = review_material(store, run_id)
    cycle = start_review_cycle(
        run_id, str(material["subject"]), str(material["initial_artifact_sha256"])
    )
    history = _load_history(store, cycle)
    state = history.cycle.phase.value
    expected_receipts = sum(len(transition.events) for transition in history.transitions)
    pending_verdict = f"product-verdict-{cycle.review_cycle_id}-0"
    if len(history.receipts) != expected_receipts or (
        history.cycle.phase is ReviewPhase.AWAITING_REVIEW
        and (
            (store.run_directory(run_id) / f"{pending_verdict}.json").exists()
            or any(row["event_key"] == pending_verdict for row in store.read_receipts(run_id))
        )
    ):
        state = "INCOMPLETE_REVIEW_RECEIPTS"
    elif history.cycle.phase in (
        ReviewPhase.REVIEWED_FOR_JOSEPH,
        ReviewPhase.ESCALATE_TO_JOSEPH,
    ) and (
        history.cycle.correction_count != material["revision"]
        or _artifact_digest(history.receipts[-1]) != material["current_artifact_sha256"]
    ):
        state = "CORRECTION_REQUIRES_PROPOSAL_BINDING"
    output = {
        "run_id": run_id,
        "state": state,
        "subject": cycle.subject,
        "review_cycle_id": cycle.review_cycle_id,
        "artifact_sha256": material["current_artifact_sha256"],
        "proposal_sha256": json.loads(str(material["review_material"]))["proposal_sha256"],
        "receipts": history.receipts,
    }
    if state == ReviewPhase.ESCALATE_TO_JOSEPH.value:
        key = f"product-verdict-{cycle.review_cycle_id}-{material['revision']}"
        try:
            raw = (store.run_directory(run_id) / f"{key}.json").read_bytes()
            notes = json.loads(raw)
            records = [row for row in store.read_receipts(run_id) if row["event_key"] == key]
            if (
                len(records) != 1
                or records[0]["event"] != "PRODUCT_REVIEW_VERDICT"
                or records[0]["source"] != "fifth-pick-reviewer"
                or records[0]["subject"] != material["current_artifact_sha256"]
                or notes["artifact_sha256"] != material["current_artifact_sha256"]
                or records[0]["reason"] != hashlib.sha256(raw).hexdigest()
                or records[0]["result"] != notes["status"]
                or notes["status"] != history.receipts[-2]["result"]
            ):
                raise ValueError
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ReviewError("escalated review has no exact verified findings") from exc
        output["verdict"] = notes
        output["verdict_sha256"] = hashlib.sha256(raw).hexdigest()
    return output


def review_handoff(store: RunStore, run_id: str) -> dict[str, object]:
    """Reconstruct a bounded Controller checkpoint without granting dispatch authority."""
    status = review_status(store, run_id)
    state = status["state"]
    next_step = {
        ReviewPhase.AWAITING_REVIEW: "CONFIRM_INITIAL_REVIEW_NOT_ATTEMPTED",
        ReviewPhase.REVIEWED_FOR_JOSEPH: "CHECK_DECISION_AND_TIMING",
        ReviewPhase.ESCALATE_TO_JOSEPH: "LOAD_VERIFIED_FINDINGS_FOR_JOSEPH",
    }.get(str(state), "STOP_AND_RECONCILE_WITH_JOSEPH")
    return {
        "schema_version": 1,
        **{
            field: status[field]
            for field in (
                "run_id",
                "state",
                "subject",
                "review_cycle_id",
                "artifact_sha256",
                "proposal_sha256",
            )
        },
        "next_step": next_step,
        "dispatch_authorized": False,
    }


def record_product_correction(
    store: RunStore, run_id: str, *, remove: tuple[str, ...], reason: str
) -> dict[str, str | int]:
    """Apply the Controller's one bounded Builder correction without changing evidence."""
    with _run_lock(store, run_id):
        original = review_material(store, run_id)
        cycle = start_review_cycle(
            run_id, str(original["subject"]), str(original["initial_artifact_sha256"])
        )
        history = _load_history(store, cycle)
        if (
            original["revision"] != 0
            or history.cycle.phase is not ReviewPhase.AWAITING_REVIEW_AFTER_CORRECTION
            or len(history.receipts) != 2
            or not reason.strip()
            or not reason.isprintable()
            or not remove
            or len(remove) != len(set(remove))
        ):
            raise ReviewError("no unused confirmed product correction is available")
        proposal = load_pending_proposal(store, run_id)
        proposed = proposal["proposed"]
        assert isinstance(proposed, list)
        if not set(remove) <= {row["candidate_key"] for row in proposed}:
            raise ReviewError("correction can only remove exact existing selections")
        version = proposal["slate_version"]
        assert isinstance(version, int)
        recorded_at = datetime.now(UTC)
        now = recorded_at.isoformat()
        corrected = [row for row in proposed if row["candidate_key"] not in remove]
        context = read_slate_run_context(store, run_id)
        board = _manifest_start_board(context)
        if board.evidence_mode is EvidenceMode.LIVE:
            tipoffs = {event.event_id: event.commence_time for event in board.events}
            if any(
                row["event"] not in tipoffs or recorded_at >= tipoffs[row["event"]]
                for row in corrected
            ):
                raise ReviewError("corrected proposal would retain a closed decision window")
        prior_approval = proposal["approval"]
        assert isinstance(prior_approval, dict)
        updated = dict(
            proposal,
            proposed=corrected,
            slate_version=version + 1,
            proposal_recorded_at=now,
            approval=dict.fromkeys(prior_approval),
        )
        if not corrected:
            updated["recommendation"] = NO_ENTRY_RECOMMENDATION
        fingerprint = proposal_fingerprint(updated)
        binding = {
            "subject": original["subject"],
            "original_digest": original["initial_artifact_sha256"],
            "original_material": original["review_material"],
            "corrected_proposal": fingerprint,
            "corrected_version": version + 1,
            "removed": remove,
            "reason": reason,
        }
        raw = json.dumps(binding, sort_keys=True).encode()
        directory = store.run_directory(run_id)
        _atomic_write(directory / f"{_CORRECTION}.json", raw)
        store.append_receipt(
            Receipt(
                now,
                "PRODUCT_PROPOSAL_CORRECTED",
                "PENDING_REVIEW",
                fingerprint,
                "fifth-pick-review-controller",
                hashlib.sha256(raw).hexdigest(),
                run_id,
                _CORRECTION,
            )
        )
        _append_proposal_receipt(
            store, updated, result="AWAITING_JOSEPH" if corrected else "NO_ENTRY"
        )
        _write_json(directory / FINAL_FILENAME, updated)
        return review_material(store, run_id)
