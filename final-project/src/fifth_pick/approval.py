"""M8 explicit Joseph decision and receipt-before-final-state gate."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from fifth_pick.errors import FifthPickError
from fifth_pick.finalization import (
    AUDIT_FILENAME,
    FINAL_FILENAME,
    NO_ENTRY_RECOMMENDATION,
    FinalizationError,
    _append_proposal_receipt,
    _manifest_start_board,
    _validate_pending_t20,
    proposal_fingerprint,
    proposal_receipt_key,
)
from fifth_pick.models import DecisionAction
from fifth_pick.receipts import Receipt
from fifth_pick.slate_manifest import read_slate_run_context
from fifth_pick.sources.base import EvidenceMode
from fifth_pick.sources.odds_api import SOURCE_ID
from fifth_pick.storage import RunStore, _atomic_write

JOSEPH_ACTOR: Final[str] = "Joseph Edafiadhe (Governance Zero)"
_FINAL_STATES: Final[frozenset[str]] = frozenset(
    {"AWAITING_JOSEPH", "APPROVED_BY_JOSEPH", "REJECTED_BY_JOSEPH", "BLOCKED"}
)
_FINAL_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "run_id",
        "state",
        "slate_version",
        "proposal_recorded_at",
        "recommendation",
        "slate",
        "proposed",
        "approval",
        "audit_file",
    }
)
_APPROVAL_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "action",
        "actor",
        "reason",
        "official_final",
        "decision_receipt_key",
        "decision_slate_version",
        "decision_recorded_at",
        "decision_selection",
    }
)


class ApprovalError(ValueError):
    """Raised when a human decision cannot be safely recorded."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_json(path: Path, record: dict[str, object]) -> None:
    content = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    try:
        _atomic_write(path, content.encode("utf-8"))
    except OSError as exc:
        raise ApprovalError(f"cannot persist {path.name}") from exc


def _read_final(store: RunStore, run_id: str) -> tuple[dict[str, object], Path]:
    run_directory = store.run_directory(run_id)
    path = run_directory / FINAL_FILENAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ApprovalError("no M8 final proposal exists for this run") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApprovalError("final.json is unreadable; refusing a decision") from exc
    if (
        not isinstance(raw, dict)
        or set(raw) != _FINAL_FIELDS
        or isinstance(raw.get("schema_version"), bool)
        or raw.get("schema_version") != 1
        or raw.get("run_id") != run_id
        or raw.get("state") not in _FINAL_STATES
        or isinstance(raw.get("slate_version"), bool)
        or not isinstance(raw.get("slate_version"), int)
        or raw["slate_version"] < 1
        or not isinstance(raw.get("proposed"), list)
        or not isinstance(raw.get("slate"), dict)
        or not isinstance(raw.get("recommendation"), str)
        or raw.get("audit_file") != AUDIT_FILENAME
        or not isinstance(raw.get("proposal_recorded_at"), str)
    ):
        raise ApprovalError("final.json has an invalid schema or run binding")
    approval = raw.get("approval")
    if not isinstance(approval, dict) or set(approval) != _APPROVAL_FIELDS:
        raise ApprovalError("final.json approval state is malformed")
    receipts = store.read_receipts(run_id)
    proposal_key = proposal_receipt_key(raw)
    proposal_matches = tuple(item for item in receipts if item.get("event_key") == proposal_key)
    expected_proposal = Receipt(
        timestamp=raw["proposal_recorded_at"],
        event="FINAL_SELECTION_PROPOSED",
        result=(
            "NO_ENTRY"
            if raw["recommendation"] == "NO ENTRY RECOMMENDED TODAY."
            else "AWAITING_JOSEPH"
        ),
        subject=proposal_fingerprint(raw),
        source=SOURCE_ID,
        reason=f"SLATE_VERSION={raw['slate_version']}",
        run_id=run_id,
        event_key=proposal_key,
    ).to_dict()
    if raw["state"] == "BLOCKED":
        raise ApprovalError("blocked M8 runs cannot accept a Joseph decision")
    if proposal_matches != (expected_proposal,):
        raise ApprovalError("final proposal has no matching application receipt")
    _validate_existing_decision(raw, receipts)
    return raw, path


def load_pending_proposal(store: RunStore, run_id: str) -> dict[str, object]:
    """Read a receipt-verified proposal before asking Joseph for an action."""

    final, _path = _read_final(store, run_id)
    if final["state"] != "AWAITING_JOSEPH":
        raise ApprovalError("this slate already has a terminal Joseph decision")
    try:
        _validate_pending_t20(store, run_id, final)
    except FinalizationError as exc:
        raise ApprovalError(str(exc)) from exc
    return final


def load_approved_final(store: RunStore, run_id: str) -> dict[str, object]:
    """Read the receipt-verified official final selection without changing it."""

    final, _path = _read_final(store, run_id)
    approval = final["approval"]
    assert isinstance(approval, dict)
    if (
        final["state"] != "APPROVED_BY_JOSEPH"
        or approval.get("action") != "APPROVE"
        or approval.get("official_final") != final["proposed"]
    ):
        raise ApprovalError("run has no receipt-verified Joseph-approved final selection")
    return final


def _decision_event(action: str) -> str:
    return {
        "APPROVE": "JOSEPH_APPROVED",
        "REJECT": "JOSEPH_REJECTED",
        "MODIFY": "JOSEPH_MODIFIED",
    }[action]


def _decision_fingerprint(
    *,
    run_id: str,
    action: str,
    slate_version: int,
    selection: list[str],
    reason: str,
    state: str,
    proposal_digest: str | None,
) -> str:
    payload = {
        "run_id": run_id,
        "action": action,
        "slate_version": slate_version,
        "selection": selection,
        "reason": reason,
        "actor": JOSEPH_ACTOR,
        "state": state,
    }
    if proposal_digest is not None:
        payload["proposal_digest"] = proposal_digest
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _decision_receipt(
    *,
    run_id: str,
    action: str,
    slate_version: int,
    selection: list[str],
    reason: str,
    state: str,
    timestamp: str,
    proposal_digest: str | None = None,
) -> Receipt:
    fingerprint = _decision_fingerprint(
        run_id=run_id,
        action=action,
        slate_version=slate_version,
        selection=selection,
        reason=reason,
        state=state,
        proposal_digest=proposal_digest,
    )
    return Receipt(
        timestamp=timestamp,
        event=_decision_event(action),
        result=action,
        subject=fingerprint,
        source=JOSEPH_ACTOR,
        reason=(
            f"SLATE_VERSION={slate_version}"
            if not reason
            else f"SLATE_VERSION={slate_version}; {reason}"
        ),
        run_id=run_id,
        event_key=f"joseph-decision-{slate_version}-{action.lower()}-{fingerprint}",
    )


def _validate_existing_decision(
    final: dict[str, object],
    receipts: tuple[dict[str, str | None], ...],
) -> None:
    approval = final["approval"]
    assert isinstance(approval, dict)
    action = approval.get("action")
    state = final["state"]
    if action is None:
        if state != "AWAITING_JOSEPH" or any(
            approval.get(field) is not None
            for field in (
                "actor",
                "reason",
                "official_final",
                "decision_receipt_key",
                "decision_slate_version",
                "decision_recorded_at",
                "decision_selection",
            )
        ):
            raise ApprovalError("unreceipted approval state is not allowed")
        return
    if action not in {item.value for item in DecisionAction}:
        raise ApprovalError("final.json contains an unknown Joseph decision")
    actor = approval.get("actor")
    decision_reason = approval.get("reason")
    decision_version = approval.get("decision_slate_version")
    decision_at = approval.get("decision_recorded_at")
    selection = approval.get("decision_selection")
    receipt_key = approval.get("decision_receipt_key")
    if (
        actor != JOSEPH_ACTOR
        or not isinstance(decision_reason, str)
        or isinstance(decision_version, bool)
        or not isinstance(decision_version, int)
        or decision_version < 1
        or not isinstance(decision_at, str)
        or not isinstance(selection, list)
        or any(not isinstance(item, str) for item in selection)
        or not isinstance(receipt_key, str)
    ):
        raise ApprovalError("final.json Joseph decision record is malformed")
    expected_state = {
        "APPROVE": "APPROVED_BY_JOSEPH",
        "REJECT": "REJECTED_BY_JOSEPH",
        "MODIFY": "AWAITING_JOSEPH",
    }[action]
    if state != expected_state:
        raise ApprovalError("Joseph decision and final state do not match")
    proposed = final["proposed"]
    assert isinstance(proposed, list)
    expected_proposed_keys = [
        item.get("candidate_key")
        for item in proposed
        if isinstance(item, dict) and isinstance(item.get("candidate_key"), str)
    ]
    if action == "APPROVE":
        if (
            approval.get("official_final") != proposed
            or selection != expected_proposed_keys
            or decision_version != final["slate_version"]
        ):
            raise ApprovalError("approved final set does not match the receipted proposal")
    elif action == "REJECT":
        if (
            approval.get("official_final") != []
            or selection
            or decision_version != final["slate_version"]
        ):
            raise ApprovalError("rejected final set does not match the receipted decision")
    elif (
        approval.get("official_final") is not None
        or decision_version + 1 != final["slate_version"]
        or selection != expected_proposed_keys
    ):
        raise ApprovalError("modified slate does not match the receipted human subset")
    try:
        expected = _decision_receipt(
            run_id=str(final["run_id"]),
            action=action,
            slate_version=decision_version,
            selection=selection,
            reason=decision_reason,
            state=expected_state,
            timestamp=decision_at,
            proposal_digest=(
                proposal_fingerprint(final)
                if action == "APPROVE"
                and any(isinstance(item, dict) and "t20_event_key" in item for item in proposed)
                else None
            ),
        ).to_dict()
    except (KeyError, TypeError, ValueError) as exc:
        raise ApprovalError("Joseph decision receipt fields are malformed") from exc
    if receipt_key != expected["event_key"] or tuple(
        item for item in receipts if item.get("event_key") == receipt_key
    ) != (expected,):
        raise ApprovalError("Joseph decision has no matching application receipt")


def _update_audit(store: RunStore, run_id: str, decision: dict[str, object]) -> None:
    path = store.run_directory(run_id) / AUDIT_FILENAME
    try:
        audit = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApprovalError("M8 audit is unreadable; final state was not changed") from exc
    if not isinstance(audit, dict) or audit.get("run_id") != run_id:
        raise ApprovalError("M8 audit has an invalid run binding")
    decisions = audit.get("joseph_decisions")
    if not isinstance(decisions, list):
        raise ApprovalError("M8 audit decision trail is malformed")
    event_key = decision["receipt_event_key"]
    if not any(
        isinstance(item, dict) and item.get("receipt_event_key") == event_key for item in decisions
    ):
        decisions.append(decision)
    _write_json(path, audit)


def _apply_joseph_decision(
    *,
    run_id: str,
    store: RunStore,
    action: DecisionAction,
    displayed_proposal_digest: str,
    selected_candidate_keys: tuple[str, ...] = (),
    reason: str = "",
    review_exception_sha256: str | None = None,
) -> dict[str, object]:
    """Serialize Joseph's decision with product review and correction writes."""
    from fifth_pick.review_bridge import _run_lock

    if type(store) is not RunStore:
        raise ApprovalError("Joseph decisions require the M2 RunStore")
    with _run_lock(store, run_id):
        return _apply_locked_joseph_decision(
            run_id=run_id,
            store=store,
            action=action,
            displayed_proposal_digest=displayed_proposal_digest,
            selected_candidate_keys=selected_candidate_keys,
            reason=reason,
            review_exception_sha256=review_exception_sha256,
        )


def _apply_locked_joseph_decision(
    *,
    run_id: str,
    store: RunStore,
    action: DecisionAction,
    displayed_proposal_digest: str,
    selected_candidate_keys: tuple[str, ...],
    reason: str,
    review_exception_sha256: str | None,
) -> dict[str, object]:
    """Apply one explicitly supplied decision after validating its current proposal receipt."""

    if not isinstance(action, DecisionAction):
        raise ApprovalError("action must be APPROVE, REJECT, or MODIFY")
    if not isinstance(selected_candidate_keys, tuple) or any(
        not isinstance(item, str) or not item.strip() for item in selected_candidate_keys
    ):
        raise ApprovalError("selected candidate keys must be a tuple of non-empty strings")
    if not isinstance(reason, str):
        raise ApprovalError("decision reason must be text")
    if action is DecisionAction.REJECT and not reason.strip():
        raise ApprovalError("REJECT requires a reason")
    final = load_pending_proposal(store, run_id)
    final_path = store.run_directory(run_id) / FINAL_FILENAME
    if proposal_fingerprint(final) != displayed_proposal_digest:
        raise ApprovalError("proposal changed while awaiting Joseph's decision; review it again")
    proposed = final["proposed"]
    assert isinstance(proposed, list)
    proposal_keys = tuple(
        item["candidate_key"]
        for item in proposed
        if isinstance(item, dict) and isinstance(item.get("candidate_key"), str)
    )
    if len(proposal_keys) != len(proposed):
        raise ApprovalError("proposal contains a malformed candidate identity")
    if action is DecisionAction.APPROVE:
        if selected_candidate_keys:
            raise ApprovalError("APPROVE accepts the complete displayed proposal only")
        selection = list(proposal_keys)
        official_final: list[object] | None = list(proposed)
        new_state = "APPROVED_BY_JOSEPH"
    elif action is DecisionAction.REJECT:
        if selected_candidate_keys:
            raise ApprovalError("REJECT does not accept candidate selections")
        selection = []
        official_final = []
        new_state = "REJECTED_BY_JOSEPH"
    else:
        if len(set(selected_candidate_keys)) != len(selected_candidate_keys):
            raise ApprovalError("MODIFY cannot repeat a candidate")
        if not set(selected_candidate_keys) <= set(proposal_keys):
            raise ApprovalError("MODIFY may only retain candidates in the displayed proposal")
        retained = set(selected_candidate_keys)
        selection = [key for key in proposal_keys if key in retained]
        official_final = None
        new_state = "AWAITING_JOSEPH"

    decision_at = datetime.now(UTC)
    product_correction = (final_path.parent / "product-review-correction.json").exists()
    if action is DecisionAction.APPROVE and (proposed or product_correction):
        board = _manifest_start_board(read_slate_run_context(store, run_id))
        if board.evidence_mode is EvidenceMode.LIVE:
            from fifth_pick.snapshots import read_receipted_snapshot_ledger, shared_slate_start

            slate_start = shared_slate_start(read_receipted_snapshot_ledger(store, run_id))
            if slate_start is not None and decision_at >= slate_start:
                raise ApprovalError(
                    "LIVE approval requires the first official game to be pre-tipoff"
                )
            tipoffs = {event.event_id: event.commence_time for event in board.events}
            if any(
                not isinstance(item, dict)
                or not isinstance(item.get("event"), str)
                or item["event"] not in tipoffs
                or decision_at >= tipoffs[item["event"]]
                for item in proposed
            ):
                raise ApprovalError("LIVE approval requires every selected event to be pre-tipoff")
        if board.evidence_mode is EvidenceMode.LIVE or product_correction:
            from fifth_pick.product_review import review_status
            from fifth_pick.review import ReviewError, ReviewPhase

            try:
                reviewed = review_status(store, run_id)
            except (FifthPickError, ReviewError) as exc:
                raise ApprovalError("LIVE approval requires a reviewed exact proposal") from exc
            if reviewed["proposal_sha256"] != displayed_proposal_digest:
                raise ApprovalError("review belongs to a different proposal version")
            verdict = reviewed.get("verdict")
            acknowledged = (
                not product_correction
                and reviewed["state"] == ReviewPhase.ESCALATE_TO_JOSEPH.value
                and isinstance(verdict, dict)
                and verdict.get("status") == "CONCERNS"
                and review_exception_sha256 is not None
                and review_exception_sha256 == reviewed.get("verdict_sha256")
                and bool(reason.strip())
            )
            if reviewed["state"] != ReviewPhase.REVIEWED_FOR_JOSEPH.value and not acknowledged:
                raise ApprovalError("LIVE approval requires a reviewed exact proposal")
            if acknowledged:
                reason = (
                    f"JOSEPH_CONCERNS_ACKNOWLEDGED sha256={review_exception_sha256}; "
                    f"{reason.strip()}"
                )
            decision_at = datetime.now(UTC)
            if board.evidence_mode is EvidenceMode.LIVE and any(
                decision_at >= tipoffs[item["event"]] for item in proposed
            ):
                raise ApprovalError("LIVE approval requires every selected event to be pre-tipoff")

    displayed_proposal = {
        field: final[field]
        for field in ("run_id", "slate_version", "slate", "recommendation", "proposed")
    }
    now = decision_at.isoformat()
    slate_version = final["slate_version"]
    assert isinstance(slate_version, int)
    decision = _decision_receipt(
        run_id=run_id,
        action=action.value,
        slate_version=slate_version,
        selection=selection,
        reason=reason.strip(),
        state=new_state,
        timestamp=now,
        proposal_digest=displayed_proposal_digest
        if action is DecisionAction.APPROVE and proposed
        else None,
    )
    persisted = store.append_receipt(decision)
    persisted_timestamp = persisted.receipt.get("timestamp")
    if not isinstance(persisted_timestamp, str):
        raise ApprovalError("persisted Joseph decision receipt has no timestamp")
    now = persisted_timestamp
    approval = final["approval"]
    assert isinstance(approval, dict)
    approval.update(
        {
            "action": action.value,
            "actor": JOSEPH_ACTOR,
            "reason": reason.strip(),
            "official_final": official_final,
            "decision_receipt_key": decision.event_key,
            "decision_slate_version": slate_version,
            "decision_recorded_at": now,
            "decision_selection": selection,
        }
    )
    final["state"] = new_state

    if action is DecisionAction.MODIFY:
        final["proposed"] = [
            item
            for item in proposed
            if isinstance(item, dict) and item.get("candidate_key") in set(selection)
        ]
        final["slate_version"] = slate_version + 1
        final["proposal_recorded_at"] = now
        _append_modified_proposal_receipt(store, final)
    _update_audit(
        store,
        run_id,
        {
            "action": action.value,
            "actor": JOSEPH_ACTOR,
            "reason": reason.strip(),
            "slate_version": slate_version,
            "selection": selection,
            "recorded_at": now,
            "receipt_event_key": decision.event_key,
            "displayed_proposal": displayed_proposal,
            "displayed_proposal_sha256": displayed_proposal_digest,
        },
    )
    _write_json(final_path, final)
    return final


def _append_modified_proposal_receipt(store: RunStore, final: dict[str, object]) -> None:
    result = (
        "NO_ENTRY" if final.get("recommendation") == NO_ENTRY_RECOMMENDATION else "AWAITING_JOSEPH"
    )
    _append_proposal_receipt(store, final, result=result)
