from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fifth_pick import __version__
from fifth_pick.approval import (
    ApprovalError,
    _apply_joseph_decision,
    load_approved_final,
    load_pending_proposal,
)
from fifth_pick.errors import FifthPickError
from fifth_pick.finalization import proposal_fingerprint
from fifth_pick.fixture_workflow import (
    candidates_view,
    collect_fixture_stage,
    final_view,
    is_fixture_workflow,
    require_complete_fixture,
)
from fifth_pick.models import DecisionAction, Provenance, ReasonCode, Result, ResultStatus
from fifth_pick.results import (
    LOOKUP_ATTEMPT_CONFIRMED,
    SETTLEMENT_CONFIRMED,
    ResultError,
    record_result,
)
from fifth_pick.sources.fixtures import FIXTURE_LABEL
from fifth_pick.storage import application_run_store

if TYPE_CHECKING:
    from fifth_pick.board_smoke import SmokeAuthorization

USAGE = (
    "usage: fifth-pick <command>\n\ncommands:\n"
    "  health\n"
    "  board-smoke --run-id RUN_ID\n"
    "  board-preflight\n"
    "  board-status\n"
    "  board-collect --run-id RUN_ID --scope FILE [--preflight FILE]"
    " [--series --snapshot {1,2,3}]\n"
    "  menu [--run-id RUN_ID]\n"
    "  analyze --run-id RUN_ID --snapshot {1,2} [--fixture DIRECTORY]\n"
    "  candidates --run-id RUN_ID\n"
    "  t20 --run-id RUN_ID [--fixture DIRECTORY]\n"
    "  final --run-id RUN_ID\n"
    "  audit --run-id RUN_ID\n"
    "  schedule --run-id RUN_ID\n"
    "  evaluate --run-id RUN_ID\n"
    "  review-material --run-id RUN_ID\n"
    "  review-status --run-id RUN_ID\n"
    "  review-correct --run-id RUN_ID --remove CANDIDATE_KEY --reason REASON\n"
    "  decide --run-id RUN_ID\n"
    "  result record --run-id RUN_ID --selection SELECTION_ID\n"
)
HEALTH = {
    "package": "fifth_pick",
    "status": "ok",
    "version": __version__,
}


def main(
    argv: Sequence[str] | None = None,
    *,
    prompt: Callable[[str], str] | None = None,
    smoke_authorization: SmokeAuthorization | None = None,
    verified_aliases: Mapping[str, tuple[str, ...]] | None = None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)

    if arguments == ["health"]:
        print(json.dumps(HEALTH, sort_keys=True))
        return 0

    if arguments and arguments[0] == "board-collect":
        from fifth_pick.live_board_cli import collect_live_board

        return collect_live_board(arguments[1:], prompt or input)

    if arguments == ["board-preflight"]:
        return _board_preflight(prompt or input)

    if arguments == ["board-status"]:
        from fifth_pick.live_board_cli import show_board_status

        return show_board_status(application_run_store(), datetime.now(UTC))

    if len(arguments) == 3 and arguments[:2] == ["board-smoke", "--run-id"]:
        return _board_smoke_command(
            arguments[2], prompt or input, smoke_authorization, verified_aliases
        )

    if arguments == ["menu"] or (len(arguments) == 3 and arguments[:2] == ["menu", "--run-id"]):
        from fifth_pick.menu import run_menu

        return run_menu(
            application_run_store(),
            lambda args, read: main(args, prompt=read),
            arguments[2] if len(arguments) == 3 else None,
            live_action=(
                _live_board_menu
                if smoke_authorization is None
                else lambda read: _board_smoke_command(
                    smoke_authorization.run_id, read, smoke_authorization, verified_aliases
                )
            ),
        )

    if arguments and arguments[0] in {
        "analyze",
        "candidates",
        "t20",
        "final",
        "audit",
        "schedule",
        "evaluate",
        "review-material",
        "review-status",
        "review-correct",
    }:
        return _fixture_command(arguments[0], arguments[1:])

    if len(arguments) == 3 and arguments[:2] == ["decide", "--run-id"]:
        run_id = arguments[2]
        if not run_id.strip():
            print(USAGE, file=sys.stderr)
            return 2
        try:
            final = _interactive_decision(run_id, prompt or input)
        except (FifthPickError, OSError, ValueError) as exc:
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
            path = _interactive_result_record(run_id, selection_id, prompt or input)
        except (FifthPickError, OSError, ValueError) as exc:
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


def _board_preflight(read: Callable[[str], str]) -> int:
    from zoneinfo import ZoneInfo

    from fifth_pick.live_board_cli import preflight_path
    from fifth_pick.slate_manifest import SLATE_TIMEZONE
    from fifth_pick.sources.base import MissingApiKeyError
    from fifth_pick.sources.odds_api import FreeQuotaVerificationError, OddsApiClient
    from fifth_pick.sources.quota import (
        LAST_HEADER,
        REMAINING_HEADER,
        USED_HEADER,
        QuotaError,
        header_value,
        parse_quota_headers,
    )
    from fifth_pick.sources.transport import HttpResponse, TransportError, UrllibTransport
    from fifth_pick.storage import _atomic_write

    response: HttpResponse | None = None

    def capture_response(
        _url: str, _requested: datetime, _retrieved: datetime, received: HttpResponse
    ) -> None:
        nonlocal response
        response = received

    client = OddsApiClient(transport=UrllibTransport())
    try:
        client.require_credentials()
        if read("One quota-free event-list request. Type PREFLIGHT to proceed: ") != "PREFLIGHT":
            return 1
        events, quota = client.discover_free_events(
            authorized=True, observe_response=capture_response
        )
    except MissingApiKeyError as exc:
        print(f"Board preflight stopped: {exc}", file=sys.stderr)
        return 1
    except (FifthPickError, OSError, ValueError) as exc:
        status = response.status if response is not None else "unavailable"
        transport_details = ""
        if response is None:
            stage = "transport"
            category = exc.category if isinstance(exc, TransportError) else "unknown"
            transport_details = f", transport_category={category}"
        elif status in (401, 403):
            stage = "authentication or access denied"
        elif status in (402, 429):
            stage = "provider quota or rate limit"
        elif status != 200:
            stage = "HTTP response"
        elif isinstance(exc, (QuotaError, FreeQuotaVerificationError)):
            stage = "quota-header validation"
        else:
            stage = "event validation"

        counters = []
        if response is not None:
            for name in (REMAINING_HEADER, USED_HEADER, LAST_HEADER):
                value = header_value(response.headers, name)
                if value is None:
                    continue
                try:
                    parsed = parse_quota_headers({name: value})
                except QuotaError:
                    continue
                counters.extend(
                    f"{key}={count}" for key, count in asdict(parsed).items() if count is not None
                )
        quota_details = ", ".join(counters) or "unavailable"
        print(
            f"Board preflight stopped: stage={stage}, http_status={status}, "
            f"quota={quota_details}{transport_details}",
            file=sys.stderr,
        )
        return 1
    timezone = ZoneInfo(SLATE_TIMEZONE)
    now = datetime.now(timezone)
    report = json.dumps(
        {
            "mode": "LIVE_PROVIDER_DISCOVERY_ONLY",
            "slate_date": now.date().isoformat(),
            "checked_at": now.isoformat(),
            "quota": asdict(quota),
            "events": [
                {
                    "event_id": event.event_id,
                    "home_team": event.home_team,
                    "away_team": event.away_team,
                    "tipoff": event.commence_time.isoformat(),
                }
                for event in events
                if event.commence_time.astimezone(timezone).date() == now.date()
            ],
        },
        sort_keys=True,
    )
    path = preflight_path(application_run_store(), now.date())
    try:
        _atomic_write(path, (report + "\n").encode("utf-8"))
    except OSError:
        print(report)
        print("Board preflight succeeded but the manifest could not be saved.", file=sys.stderr)
        return 1
    print(report)
    return 0


def _live_board_menu(read: Callable[[str], str]) -> int:
    from fifth_pick.live_board_cli import show_board_status

    show_board_status(application_run_store(), datetime.now(UTC))
    return _board_preflight(read)


def _board_smoke_command(
    run_id: str,
    read: Callable[[str], str],
    authorization: SmokeAuthorization | None,
    verified_aliases: Mapping[str, tuple[str, ...]] | None = None,
) -> int:
    from fifth_pick.board_smoke import SmokeEvent, run_board_smoke
    from fifth_pick.menu import Back

    if authorization is None:
        print("LIVE disabled. A separate owner grant and current billing evidence are required.")
        return 1

    def confirm(event: SmokeEvent) -> bool:
        print(
            f"{event.away_team} at {event.home_team} · {event.tipoff.isoformat()} · "
            f"{event.slate_game_count} games on the Chicago slate"
        )
        try:
            return read("Type CONFIRM to request this event's odds: ") == "CONFIRM"
        except Back:
            return False

    if read("Two requests, five credits, no retries. Type DISCOVER to proceed: ") != "DISCOVER":
        print("LIVE discovery cancelled.")
        return 1
    try:
        report = run_board_smoke(
            run_id=run_id,
            authorization=authorization,
            confirm_event=confirm,
            aliases=verified_aliases,
        )
    except (FifthPickError, OSError, ValueError) as exc:
        print(f"Board smoke stopped: {exc}", file=sys.stderr)
        return 1
    output = asdict(report)
    output["event"]["slate_classification"] = report.event.slate_classification
    output["market_coverage"] = report.market_coverage
    output["missing_coverage"] = report.missing_coverage
    output["status"] = "PARTIAL_COVERAGE" if report.missing_coverage else "BOARD_COVERAGE_RECORDED"
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, default=str))
    return 0


def _fixture_command(command: str, arguments: list[str]) -> int:
    parser = argparse.ArgumentParser(prog=f"fifth-pick {command}", allow_abbrev=False)
    parser.add_argument("--run-id", required=True)
    if command in {"analyze", "t20"}:
        parser.add_argument("--fixture", type=Path)
    if command == "analyze":
        parser.add_argument("--snapshot", required=True, type=int, choices=(1, 2))
    if command == "review-correct":
        parser.add_argument("--remove", action="append", required=True)
        parser.add_argument("--reason", required=True)
    try:
        args = parser.parse_args(arguments)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    store = application_run_store()
    blocked = False
    try:
        if command in {"analyze", "t20"}:
            number = args.snapshot if command == "analyze" else 3
            if args.fixture is not None:
                output = collect_fixture_stage(store, args.run_id, number, args.fixture)
            else:
                from fifth_pick.live_analysis import live_analysis_view

                output = live_analysis_view(store, args.run_id, review=command == "t20")
                blocked = True
        elif command == "final":
            if is_fixture_workflow(store, args.run_id):
                output, blocked = final_view(store, args.run_id)
            else:
                from fifth_pick.product_review import expired_live_selections, product_audit

                audit = product_audit(store, args.run_id)
                final_record = audit["final"]
                if not isinstance(final_record, dict):
                    raise ValueError("LIVE has no receipt-bound final proposal")
                expired = expired_live_selections(store, args.run_id, final_record)
                output = dict(final_record, expired_selection_keys=expired)
                blocked = bool(expired)
        elif command == "schedule":
            from fifth_pick.schedule import schedule_view

            output = schedule_view(store, args.run_id, as_of=datetime.now(UTC))
        elif command == "evaluate":
            from fifth_pick.evaluation import evaluation_view

            output = evaluation_view(store, args.run_id)
        elif command in {"review-material", "review-status"}:
            from fifth_pick.product_review import review_material, review_status

            output = (
                review_material(store, args.run_id)
                if command == "review-material"
                else review_status(store, args.run_id)
            )
        elif command == "review-correct":
            from fifth_pick.product_review import record_product_correction

            output = record_product_correction(
                store, args.run_id, remove=tuple(args.remove), reason=args.reason
            )
        else:
            from fifth_pick.product_review import product_audit

            view = candidates_view if command == "candidates" else product_audit
            output = view(store, args.run_id)
    except (FifthPickError, OSError, ValueError) as exc:
        print(f"{command} stopped: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, default=str))
    return int(blocked)


def _interactive_decision(run_id: str, read: Callable[[str], str]) -> dict[str, object]:
    from fifth_pick.product_review import expired_live_selections, review_status
    from fifth_pick.review import ReviewError

    store = application_run_store()
    if is_fixture_workflow(store, run_id):
        require_complete_fixture(store, run_id)
    proposal = load_pending_proposal(store, run_id)
    expired = (
        ()
        if is_fixture_workflow(store, run_id)
        else expired_live_selections(store, run_id, proposal)
    )
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
        print(f"    T-20 {item['t20_status']} | confidence {item['confidence']}")
        if item["candidate_key"] in expired:
            print("    Decision window closed. This selection cannot be approved.")
        print(f"    {item['t20_rationale']}")
        for risk in item["material_risks"]:
            print(f"    Material risk: {risk}")
    try:
        reviewed = review_status(store, run_id)
    except (FifthPickError, ReviewError, OSError):
        reviewed = {}
    verdict = reviewed.get("verdict")
    if isinstance(verdict, dict):
        print("Escalated Reviewer findings")
        print(json.dumps(verdict, ensure_ascii=True, sort_keys=True))
    action_text = read("Joseph's decision (APPROVE / REJECT / MODIFY): ")
    try:
        action = DecisionAction(action_text)
    except ValueError as exc:
        raise ApprovalError("decision must be APPROVE, REJECT, or MODIFY") from exc

    selected: tuple[str, ...] = ()
    reason = ""
    exception_digest = None
    if action is DecisionAction.MODIFY:
        response = read("Candidate keys to retain, comma-separated (blank for none): ")
        selected = tuple(item.strip() for item in response.split(",") if item.strip())
    elif action is DecisionAction.REJECT:
        reason = read("Reason for rejection: ").strip()
        if not reason:
            raise ApprovalError("REJECT requires a reason")
    elif isinstance(verdict, dict) and verdict.get("status") == "CONCERNS":
        digest = reviewed.get("verdict_sha256")
        if (
            isinstance(digest, str)
            and read("To accept these findings explicitly, type APPROVE WITH CONCERNS: ")
            == "APPROVE WITH CONCERNS"
        ):
            exception_digest = digest
            reason = read("Joseph's reason for approving with concerns: ").strip()

    return _apply_joseph_decision(
        run_id=run_id,
        store=store,
        action=action,
        displayed_proposal_digest=proposal_fingerprint(proposal),
        selected_candidate_keys=selected,
        reason=reason,
        review_exception_sha256=exception_digest,
    )


def _interactive_result_record(run_id: str, selection_id: str, read: Callable[[str], str]) -> Path:
    store = application_run_store()
    final = load_approved_final(store, run_id)
    fixture = is_fixture_workflow(store, run_id)
    if fixture:
        require_complete_fixture(store, run_id)
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
    outcome_text = read("Settled result (HIT / MISS / PUSH / VOID / DNP / RESULT UNAVAILABLE): ")
    try:
        outcome = ResultStatus(outcome_text)
    except ValueError as exc:
        raise ResultError("result must use the exact supported status vocabulary") from exc
    source = read("Settlement source: ").strip()
    if not source:
        raise ResultError("settlement source is required")
    if fixture and source != FIXTURE_LABEL:
        raise ResultError("fixture workflow requires the synthetic-fixture settlement source")
    recorded_at = datetime.now(UTC)
    reason = None
    provenance = None
    evidence_excerpt = None
    evidence_confirmation = None
    if outcome is ResultStatus.RESULT_UNAVAILABLE:
        reason = ReasonCode.RESULT_UNAVAILABLE
        lookup_available = read("Lookup/attempt provenance available? (YES/NO): ").strip()
        if lookup_available not in ("YES", "NO"):
            raise ResultError("lookup provenance answer must be YES or NO")
        lookup_evidence = lookup_available == "YES"
    else:
        lookup_evidence = False

    if lookup_evidence or outcome is not ResultStatus.RESULT_UNAVAILABLE:
        source_timestamp_text = read("Source timestamp (ISO-8601): ")
        try:
            source_timestamp = datetime.fromisoformat(source_timestamp_text)
        except ValueError as exc:
            raise ResultError("source timestamp must be ISO-8601") from exc
        if source_timestamp.tzinfo is None or source_timestamp.utcoffset() is None:
            raise ResultError("source timestamp must be timezone-aware")
        reference = read("Player-specific settlement reference: ").strip()
        excerpt_text = read("Minimal settlement source excerpt: ").strip()
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
            confirmation = read(confirmation_prompt).strip()
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
                    access_method=FIXTURE_LABEL if fixture else "manual-entry",
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
