import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from fifth_pick import __version__
from fifth_pick.approval import (
    ApprovalError,
    _apply_joseph_decision,
    load_approved_final,
    load_pending_proposal,
)
from fifth_pick.models import DecisionAction, Provenance, ReasonCode, Result, ResultStatus
from fifth_pick.results import (
    LOOKUP_ATTEMPT_CONFIRMED,
    SETTLEMENT_CONFIRMED,
    ResultError,
    record_result,
)
from fifth_pick.storage import application_run_store

USAGE = (
    "usage: fifth-pick <command>\n\ncommands:\n"
    "  health\n"
    "  decide --run-id RUN_ID\n"
    "  result record --run-id RUN_ID --selection SELECTION_ID\n"
)
HEALTH = {
    "package": "fifth_pick",
    "status": "ok",
    "version": __version__,
}


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)

    if arguments == ["health"]:
        print(json.dumps(HEALTH, sort_keys=True))
        return 0

    if len(arguments) == 3 and arguments[:2] == ["decide", "--run-id"]:
        run_id = arguments[2]
        if not run_id.strip():
            print(USAGE, file=sys.stderr)
            return 2
        try:
            final = _interactive_decision(run_id)
        except (ApprovalError, OSError, ValueError) as exc:
            print(f"decision not recorded: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(final, ensure_ascii=False, sort_keys=True))
        return 0

    if (
        len(arguments) == 6
        and arguments[:3] == ["result", "record", "--run-id"]
        and arguments[4] == "--selection"
    ):
        run_id = arguments[3]
        selection_id = arguments[5]
        if not run_id.strip() or not selection_id.strip():
            print(USAGE, file=sys.stderr)
            return 2
        try:
            path = _interactive_result_record(run_id, selection_id)
        except (ApprovalError, ResultError, OSError, ValueError) as exc:
            print(f"result not recorded: {exc}", file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "status": "RESULT RECORDED",
                    "run_id": run_id,
                    "selection_id": selection_id,
                    "artifact": path.name,
                },
                sort_keys=True,
            )
        )
        return 0

    print(USAGE, file=sys.stderr)
    return 2


def _interactive_decision(run_id: str) -> dict[str, object]:
    store = application_run_store()
    proposal = load_pending_proposal(store, run_id)
    print("Proposed final set")
    proposed = proposal["proposed"]
    assert isinstance(proposed, list)
    if not proposed:
        print("  (no selections)")
    for item in proposed:
        assert isinstance(item, dict)
        print(
            f"  {item['player']} | {item['platform']} | {item['category']} "
            f"{item['direction']} {item['projection']} | key={item['candidate_key']}"
        )
    action_text = input("Joseph's decision (APPROVE / REJECT / MODIFY): ")
    try:
        action = DecisionAction(action_text)
    except ValueError as exc:
        raise ApprovalError("decision must be APPROVE, REJECT, or MODIFY") from exc

    selected: tuple[str, ...] = ()
    reason = ""
    if action is DecisionAction.MODIFY:
        response = input("Candidate keys to retain, comma-separated (blank for none): ")
        selected = tuple(item.strip() for item in response.split(",") if item.strip())
    elif action is DecisionAction.REJECT:
        reason = input("Reason for rejection: ").strip()
        if not reason:
            raise ApprovalError("REJECT requires a reason")

    return _apply_joseph_decision(
        run_id=run_id,
        store=store,
        action=action,
        selected_candidate_keys=selected,
        reason=reason,
    )


def _interactive_result_record(run_id: str, selection_id: str) -> Path:
    store = application_run_store()
    final = load_approved_final(store, run_id)
    approval = final["approval"]
    assert isinstance(approval, dict)
    official_final = approval["official_final"]
    assert isinstance(official_final, list)
    selected = next(
        (
            item
            for item in official_final
            if isinstance(item, dict) and item.get("candidate_key") == selection_id
        ),
        None,
    )
    if selected is None:
        raise ResultError("selection ID is not in Joseph's approved final set")

    print("Approved selection")
    print(
        f"  {selected['player']} | {selected['platform']} | {selected['category']} "
        f"{selected['direction']} {selected['projection']} | key={selection_id}"
    )
    print(f"  event={selected['event']}")
    outcome_text = input("Settled result (HIT / MISS / PUSH / VOID / DNP / RESULT UNAVAILABLE): ")
    try:
        outcome = ResultStatus(outcome_text)
    except ValueError as exc:
        raise ResultError("result must use the exact supported status vocabulary") from exc
    source = input("Settlement source: ").strip()
    if not source:
        raise ResultError("settlement source is required")
    recorded_at = datetime.now(UTC)
    reason = None
    provenance = None
    evidence_excerpt = None
    evidence_confirmation = None
    if outcome is ResultStatus.RESULT_UNAVAILABLE:
        reason = ReasonCode.RESULT_UNAVAILABLE
        lookup_available = input("Lookup/attempt provenance available? (YES/NO): ").strip()
        if lookup_available not in ("YES", "NO"):
            raise ResultError("lookup provenance answer must be YES or NO")
        lookup_evidence = lookup_available == "YES"
    else:
        lookup_evidence = False

    if lookup_evidence or outcome is not ResultStatus.RESULT_UNAVAILABLE:
        source_timestamp_text = input("Source timestamp (ISO-8601): ")
        try:
            source_timestamp = datetime.fromisoformat(source_timestamp_text)
        except ValueError as exc:
            raise ResultError("source timestamp must be ISO-8601") from exc
        if source_timestamp.tzinfo is None or source_timestamp.utcoffset() is None:
            raise ResultError("source timestamp must be timezone-aware")
        reference = input("Player-specific settlement reference: ").strip()
        excerpt_text = input("Minimal settlement source excerpt: ").strip()
        if excerpt_text:
            print(f"Evidence excerpt: {excerpt_text}")
            selection_details = (
                f"player={selected['player']}; platform={selected['platform']}; "
                f"market={selected['category']} {selected['direction']}; "
                f"line={selected['projection']}; event={selected['event']}"
            )
            if lookup_evidence:
                confirmation_prompt = (
                    f"Confirm this excerpt is a lookup attempt for {selection_details}. "
                    "This does not establish a settlement outcome; confirm only if every "
                    "displayed detail matches. (YES/NO): "
                )
            else:
                confirmation_prompt = (
                    "Have you checked that this source excerpt itself supports "
                    f"{selection_details}; "
                    f"entered_outcome={outcome.value}? Confirm only if every detail is supported. "
                    "The application does not independently authenticate the source. Otherwise "
                    "answer NO and the result will be recorded as RESULT UNAVAILABLE. (YES/NO): "
                )
            confirmation = input(confirmation_prompt).strip()
            if confirmation not in ("YES", "NO"):
                raise ResultError("evidence confirmation must be YES or NO")
            if confirmation == "YES":
                evidence_excerpt = excerpt_text
                evidence_confirmation = (
                    LOOKUP_ATTEMPT_CONFIRMED if lookup_evidence else SETTLEMENT_CONFIRMED
                )
                provenance = Provenance(
                    source=source,
                    retrieved_at=recorded_at,
                    source_timestamp=source_timestamp,
                    access_method="manual-entry",
                    reference=reference,
                    payload_hash=hashlib.sha256(excerpt_text.encode("utf-8")).hexdigest(),
                )
        if not lookup_evidence and evidence_confirmation != SETTLEMENT_CONFIRMED:
            outcome = ResultStatus.RESULT_UNAVAILABLE
            reason = ReasonCode.RESULT_UNAVAILABLE
            evidence_excerpt = None
            evidence_confirmation = None
            provenance = None
            print("Settlement evidence was not confirmed; recording RESULT UNAVAILABLE.")
    result = Result(
        outcome=outcome,
        subject=selection_id,
        source=source,
        recorded_at=recorded_at,
        reason=reason,
        provenance=provenance,
    )
    return record_result(
        store,
        run_id,
        selection_id,
        result,
        evidence_excerpt=evidence_excerpt,
        evidence_confirmation=evidence_confirmation,
    )
