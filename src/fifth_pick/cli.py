import json
import sys
from collections.abc import Sequence

from fifth_pick import __version__
from fifth_pick.approval import (
    ApprovalError,
    _apply_joseph_decision,
    load_pending_proposal,
)
from fifth_pick.models import DecisionAction
from fifth_pick.storage import application_run_store

USAGE = "usage: fifth-pick <command>\n\ncommands:\n  health\n  decide --run-id RUN_ID\n"
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
