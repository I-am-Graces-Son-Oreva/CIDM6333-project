"""Read-only experiment evaluation over persisted, receipt-verified fixture runs."""

import json
from collections import Counter
from typing import Any, cast

from fifth_pick.approval import JOSEPH_ACTOR, _decision_receipt
from fifth_pick.errors import StorageError
from fifth_pick.finalization import (
    NO_ENTRY_RECOMMENDATION,
    proposal_fingerprint,
    proposal_receipt_key,
)
from fifth_pick.models import ResultStatus
from fifth_pick.product_review import _correction_binding, product_audit, review_status
from fifth_pick.sources.odds_api import SOURCE_ID
from fifth_pick.storage import RunStore


class EvaluationError(ValueError):
    """Run evidence is unavailable or cannot be verified for evaluation."""


_PROPOSAL_FIELDS = frozenset({"run_id", "slate_version", "slate", "recommendation", "proposed"})
_DECISION_STATES = {
    "MODIFY": "AWAITING_JOSEPH",
    "REJECT": "REJECTED_BY_JOSEPH",
    "APPROVE": "APPROVED_BY_JOSEPH",
}


def _record(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvaluationError("evaluation requires a persisted object")
    return value


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        raise EvaluationError("evaluation requires persisted records")
    return [_record(row) for row in value]


def _proposal_snapshot(record: dict[str, Any]) -> dict[str, object]:
    return {field: record[field] for field in sorted(_PROPOSAL_FIELDS)}


def _saved_proposal(
    decision: dict[str, Any],
    run_id: str,
    version: int,
    receipts: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    proposal = decision.get("displayed_proposal")
    digest = decision.get("displayed_proposal_sha256")
    if proposal is None and digest is None:
        return None
    saved = _record(proposal)
    if (
        set(saved) != _PROPOSAL_FIELDS
        or saved["run_id"] != run_id
        or type(saved["slate_version"]) is not int
        or saved["slate_version"] != version
        or proposal_fingerprint(saved) != digest
    ):
        raise EvaluationError("historical proposal does not match its recorded digest")
    _rows(saved["proposed"])
    receipt = receipts.get(proposal_receipt_key(saved))
    expected_result = (
        "NO_ENTRY" if saved["recommendation"] == NO_ENTRY_RECOMMENDATION else "AWAITING_JOSEPH"
    )
    if (
        receipt is None
        or receipt.get("event") != "FINAL_SELECTION_PROPOSED"
        or receipt.get("run_id") != run_id
        or receipt.get("source") != SOURCE_ID
        or receipt.get("subject") != digest
        or receipt.get("result") != expected_result
        or receipt.get("reason") != f"SLATE_VERSION={version}"
    ):
        raise EvaluationError("historical proposal has no matching application receipt")
    return saved


def _verified_decisions(
    changes: object,
    run_id: str,
    final: dict[str, Any] | None,
    receipts: dict[str, dict[str, Any]],
    *,
    corrected_version: int | None = None,
) -> list[dict[str, object]]:
    trail: list[dict[str, object]] = []
    version = 1
    for decision in _rows(changes):
        if corrected_version == version + 1 and decision.get("slate_version") == version + 1:
            version += 1
        action = decision.get("action")
        selection = decision.get("selection")
        reason = decision.get("reason")
        timestamp = decision.get("recorded_at")
        key = decision.get("receipt_event_key")
        if (
            not isinstance(action, str)
            or action not in _DECISION_STATES
            or decision.get("actor") != JOSEPH_ACTOR
            or type(decision.get("slate_version")) is not int
            or decision["slate_version"] != version
            or not isinstance(selection, list)
            or any(not isinstance(candidate_key, str) for candidate_key in selection)
            or len(set(selection)) != len(selection)
            or not isinstance(reason, str)
            or not isinstance(timestamp, str)
            or not isinstance(key, str)
        ):
            raise EvaluationError("historical Joseph decision is malformed")
        saved = _saved_proposal(decision, run_id, version, receipts)
        proposal_digest = None
        if action == "APPROVE":
            # M8 binds contemporary nonempty approvals to the displayed payload.
            # Legacy approvals remain verifiable through the accepted M8 contract.
            approved = final if saved is None else saved
            if approved is not None and any(
                "t20_event_key" in item for item in _rows(approved["proposed"])
            ):
                proposal_digest = proposal_fingerprint(approved)
        expected = _decision_receipt(
            run_id=run_id,
            action=action,
            slate_version=version,
            selection=selection,
            reason=reason,
            state=_DECISION_STATES[action],
            timestamp=timestamp,
            proposal_digest=proposal_digest,
        ).to_dict()
        if key != expected["event_key"] or receipts.get(key) != expected:
            raise EvaluationError("historical Joseph decision has no matching application receipt")
        trail.append(
            {
                "action": action,
                "actor": JOSEPH_ACTOR,
                "slate_version": version,
                "selection": selection,
                "reason": reason,
                "recorded_at": timestamp,
                "receipt_event_key": key,
                "displayed_proposal": saved,
            }
        )
        version += 1
    registered_keys = {
        key
        for key, receipt in receipts.items()
        if receipt.get("event") in {"JOSEPH_APPROVED", "JOSEPH_REJECTED", "JOSEPH_MODIFIED"}
    }
    if registered_keys != {row["receipt_event_key"] for row in trail}:
        raise EvaluationError("historical Joseph decision receipts and the audit trail disagree")
    awaiting_corrected_decision = (
        final is not None
        and final["slate_version"] == corrected_version
        and final["approval"]["action"] is None
        and bool(trail)
        and trail[-1]["slate_version"] == final["slate_version"] - 1
    )
    if (
        trail
        and not awaiting_corrected_decision
        and (
            final is None
            or final["approval"]["decision_receipt_key"] != trail[-1]["receipt_event_key"]
        )
    ):
        raise EvaluationError("Joseph's current decision does not match the audit trail")
    return trail


def _process_metrics(
    audit: dict[str, Any],
    final: dict[str, Any] | None,
    final_audit: dict[str, Any],
    receipts: list[dict[str, Any]],
    reviewer: dict[str, object],
) -> dict[str, object]:
    ranking = _record(final_audit.get("m6_ranking", {}))
    evaluations = _rows(ranking.get("audits", []))
    snapshot_receipts = [
        row
        for row in receipts
        if isinstance(row.get("event"), str) and row["event"].startswith("SNAPSHOT_")
    ]
    review_rows = _rows(audit["t20_reviews"])
    board_rows = _rows(audit["board_manifests"])
    supporting_rows = [item for row in evaluations for item in _rows(row["evidence"])]
    slate = _record(final["slate"]) if final is not None else {}
    proposed = _rows(final["proposed"]) if final is not None else []
    maximum = slate.get("maximum_selections")
    approval = _record(final["approval"]) if final is not None else {}
    return {
        "methodology": {
            "assessment": "RECORDED EVIDENCE" if "m6_ranking" in final_audit else "NOT RECORDED",
            "rule_versions": final_audit.get("rule_versions"),
            "rule_ids": sorted({rule for row in evaluations for rule in row["rules_applied"]}),
            "candidate_status_counts": dict(Counter(row["status"] for row in evaluations)),
            "ranking": ranking.get("ranked", []),
            "exclusions": final_audit.get("exclusions", []),
            "stop_reason": final_audit.get("stop_reason"),
        },
        "discipline": {
            "game_count": slate.get("game_count"),
            "slate_classification": slate.get("classification"),
            "selection_ceiling": maximum,
            "proposed_count": len(proposed) if final is not None else None,
            "within_ceiling": len(proposed) <= maximum if type(maximum) is int else None,
            "one_pick_per_player": (
                len({item["player_id"] for item in proposed}) == len(proposed)
                if final is not None
                else None
            ),
            "final_state": final["state"] if final is not None else None,
            "joseph_decision_receipt": approval.get("decision_receipt_key"),
        },
        "evidence_quality": {
            "board_payload_hashes": [row["payload_sha256"] for row in board_rows],
            "supporting_evidence_count": len(supporting_rows),
            "supporting_source_counts": dict(Counter(row["source"] for row in supporting_rows)),
            "disclosed_gaps": [
                {"candidate_key": row["candidate_key"], "gaps": row["gaps"]}
                for row in evaluations
                if row["gaps"]
            ],
        },
        "identity_and_authorization": dict(
            Counter(
                row["result"]
                for row in snapshot_receipts
                if row.get("event") == "SNAPSHOT_REJECTED"
            )
        ),
        "snapshots_and_t20": {
            "snapshot_receipt_counts": dict(Counter(row["event"] for row in snapshot_receipts)),
            "projection_history": audit["snapshots"],
            "t20_conclusion_counts": dict(Counter(row["conclusion"] for row in review_rows)),
            "t20_changes": [
                {
                    "candidate_key": row["candidate_key"],
                    "conclusion": row["conclusion"],
                    "event_key": row["event_key"],
                    "reason_codes": row["reason_codes"],
                    "projection": row["projection"],
                    "reviewed_at": row["reviewed_at"],
                    "prior_confidence": row["prior_confidence"],
                    "current_confidence": row["current_confidence"],
                    "changed_evidence_ids": row["changed_evidence_ids"],
                    "changed_judgment_fields": row["changed_judgment_fields"],
                    "readiness_gaps": row["readiness_gaps"],
                }
                for row in review_rows
            ],
        },
        "independent_review": reviewer,
    }


def evaluation_view(store: RunStore, run_id: str) -> dict[str, Any]:
    """Report evidence as recorded, without replaying judgments under today's rules."""

    try:
        audit = cast(dict[str, Any], product_audit(store, run_id))
        receipts = _rows(audit["receipts"])
        by_key = {row["event_key"]: row for row in receipts}
        if None in by_key or len(by_key) != len(receipts):
            raise EvaluationError("evaluation requires unique application receipt identities")
        final = None if audit["final"] is None else _record(audit["final"])
        final_audit = _record(audit["finalization_audit"] or {})
        correction = _correction_binding(store, run_id)
        corrected_version = None if correction is None else correction["corrected_version"]
        if corrected_version is not None and type(corrected_version) is not int:
            raise EvaluationError("correction version is malformed")
        decisions = _verified_decisions(
            final_audit.get("joseph_decisions", []),
            run_id,
            final,
            by_key,
            corrected_version=corrected_version,
        )
        results = _rows(_record(audit["results"] or {}).get("results", []))
        counts = {status.value: 0 for status in ResultStatus}
        for result in results:
            counts[result["result"]["outcome"]] += 1
        current = _proposal_snapshot(final) if final is not None else None
        original = current
        if final is not None and final["slate_version"] > 1:
            original = decisions[0]["displayed_proposal"] if decisions else None
            if correction is not None and corrected_version == 2:
                original = json.loads(str(correction["original_material"]))["proposal"]
        reviewer: dict[str, object] = {"status": "NOT RECORDED"}
        if final is not None and final["state"] != "BLOCKED":
            status = review_status(store, run_id)
            if status.get("proposal_sha256") != proposal_fingerprint(final):
                raise EvaluationError("proposal version changed during evaluation")
            if status.get("receipts"):
                reviewer = {"status": status["state"], **status}
        return {
            "schema_version": 1,
            "run_id": run_id,
            "mode": audit["mode"],
            "recommendation": {
                "original_proposal": original,
                "current_proposal": current,
                "original_status": "RECORDED" if original is not None else "NOT RECORDED",
            },
            "process": _process_metrics(audit, final, final_audit, receipts, reviewer),
            "owner_decisions": decisions,
            "outcomes": {
                "scope": "JOSEPH_APPROVED_ONLY",
                "status_counts": counts,
                "denominator": counts["HIT"] + counts["MISS"],
                "records": results,
                "counterfactual_status": "NOT RECORDED",
            },
        }
    except (StorageError, OSError, ValueError, TypeError, KeyError) as exc:
        raise EvaluationError(f"could not verify recorded experiment evidence: {exc}") from exc
