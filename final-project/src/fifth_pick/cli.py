from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
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
from fifth_pick.slate_manifest import read_slate_run_context
from fifth_pick.sources.base import EvidenceMode
from fifth_pick.sources.fixtures import FIXTURE_LABEL
from fifth_pick.storage import application_run_store

if TYPE_CHECKING:
    from fifth_pick.board_smoke import SmokeAuthorization

USAGE = (
    "usage: fifth-pick <command>\n\ncommands:\n"
    "  health\n"
    "  board-smoke --run-id RUN_ID\n"
    "  board-preflight [--date YYYY-MM-DD] [--expected-games COUNT]\n"
    "  board-status [--date YYYY-MM-DD]\n"
    "  board-inspect --run-id RUN_ID --event-id EVENT_ID [--snapshot {1,2,3}]\n"
    "  game-lines-grant --run-id RUN_ID --event-id EVENT_ID --bookmaker KEY"
    " --phase {analysis,t20} [--phase {analysis,t20}] --max-credits COUNT\n"
    "  game-lines-collect --run-id RUN_ID --phase {analysis,t20}\n"
    "  bdl-validate [--auth-only | --identity-only | --stats-only] --confirm\n"
    "  board-collect --run-id RUN_ID --scope FILE [--preflight FILE]"
    " [--series --snapshot {1,2,3}]\n"
    "  menu [--run-id RUN_ID]\n"
    "  analyze --run-id RUN_ID --snapshot {1,2} [--fixture DIRECTORY]\n"
    "    [--history-candidate-key KEY --history-archive DIRECTORY SHA256]\n"
    "  candidates --run-id RUN_ID\n"
    "  history-compare --run-id RUN_ID --candidate-key KEY --snapshot {1,2,3}"
    " --archive DIRECTORY SHA256 [--archive DIRECTORY SHA256 ...]\n"
    "  t20 --run-id RUN_ID [--fixture DIRECTORY]\n"
    "  controller-assess --run-id RUN_ID --event-id EVENT_ID --candidate-key KEY"
    " --snapshot {2,3} [--judgment-file FILE]\n"
    "  final --run-id RUN_ID\n"
    "  audit --run-id RUN_ID\n"
    "  schedule --run-id RUN_ID\n"
    "  evaluate --run-id RUN_ID\n"
    "  review-material --run-id RUN_ID\n"
    "  review-status --run-id RUN_ID\n"
    "  review-handoff --run-id RUN_ID\n"
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
    _menu_form: bool = False,
    smoke_authorization: SmokeAuthorization | None = None,
    verified_aliases: Mapping[str, tuple[str, ...]] | None = None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)

    if arguments == ["health"]:
        print(json.dumps(HEALTH, sort_keys=True))
        return 0

    if arguments in (
        ["bdl-validate", "--confirm"],
        ["bdl-validate", "--auth-only", "--confirm"],
        ["bdl-validate", "--identity-only", "--confirm"],
        ["bdl-validate", "--stats-only", "--confirm"],
    ):
        from fifth_pick.sources.base import SourceError
        from fifth_pick.sources.bdl_history import BdlHistoryClient
        from fifth_pick.sources.transport import TransportError, UrllibTransport

        try:
            client = BdlHistoryClient(UrllibTransport())
            if "--auth-only" in arguments:
                result = client.probe_authentication()
            elif "--identity-only" in arguments:
                result = client.validate_curry_identity()
            elif "--stats-only" in arguments:
                result = client.validate_verified_curry_stats()
            else:
                result = client.validate_curry_history()
        except TransportError as exc:
            print(f"BALLDONTLIE validation stopped: {exc.category}", file=sys.stderr)
            return 1
        except SourceError as exc:
            print(f"BALLDONTLIE validation stopped: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, sort_keys=True))
        return 0

    if arguments and arguments[0] == "board-inspect":
        from fifth_pick.board_inspect_cli import board_inspect

        return board_inspect(arguments[1:])

    if arguments and arguments[0] == "board-collect":
        from fifth_pick.live_board_cli import collect_live_board

        return collect_live_board(arguments[1:], prompt or input)

    if arguments and arguments[0] == "history-compare":
        from fifth_pick.history_compare_cli import history_compare

        return history_compare(arguments[1:])

    if arguments and arguments[0] == "controller-assess":
        from fifth_pick.live_judgment_cli import controller_assess

        return controller_assess(arguments[1:], prompt or (input if sys.stdin.isatty() else None))

    if arguments and arguments[0] == "game-lines-grant":
        return _game_lines_grant(arguments[1:], prompt or input)

    if arguments and arguments[0] == "game-lines-collect":
        return _game_lines_collect(arguments[1:], prompt or input)

    if arguments and arguments[0] in {"board-preflight", "board-status"}:
        from fifth_pick.live_board_cli import show_board_status

        command = arguments[0]
        parser = argparse.ArgumentParser(prog=f"fifth-pick {command}", allow_abbrev=False)
        parser.add_argument("--date", type=date.fromisoformat)
        if command == "board-preflight":
            parser.add_argument("--expected-games", type=int)
        try:
            options = parser.parse_args(arguments[1:])
            if command == "board-preflight":
                if options.expected_games is not None and options.expected_games <= 0:
                    parser.error("--expected-games must be positive")
                return _board_preflight(
                    prompt or input, day=options.date, expected_games=options.expected_games
                )
            return show_board_status(application_run_store(), datetime.now(UTC), day=options.date)
        except SystemExit as exc:
            return 0 if exc.code == 0 else 2

    if len(arguments) == 3 and arguments[:2] == ["board-smoke", "--run-id"]:
        return _board_smoke_command(
            arguments[2], prompt or input, smoke_authorization, verified_aliases
        )

    if arguments == ["menu"] or (len(arguments) == 3 and arguments[:2] == ["menu", "--run-id"]):
        from fifth_pick.menu import run_menu

        return run_menu(
            application_run_store(),
            lambda args, read: main(args, prompt=read, _menu_form=True),
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
        "review-handoff",
        "review-correct",
    }:
        return _fixture_command(arguments[0], arguments[1:])

    if len(arguments) == 3 and arguments[:2] == ["decide", "--run-id"]:
        run_id = arguments[2]
        if not run_id.strip():
            print(USAGE, file=sys.stderr)
            return 2
        try:
            final = _interactive_decision(run_id, prompt or input, menu_form=_menu_form)
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
            path = _interactive_result_record(
                run_id, selection_id, prompt or input, menu_form=_menu_form
            )
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


def _board_preflight(
    read: Callable[[str], str], *, day: date | None = None, expected_games: int | None = None
) -> int:
    from zoneinfo import ZoneInfo

    from fifth_pick.live_board_cli import coverage_path, preflight_path
    from fifth_pick.official_slate import (
        load_official_slate,
        provider_event_row,
        reconcile_coverage,
    )
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

    timezone = ZoneInfo(SLATE_TIMEZONE)
    today = datetime.now(timezone).date()
    slate_date = today if day is None else day
    if slate_date < today:
        print("Board preflight stopped: the requested slate is in the past.", file=sys.stderr)
        return 1
    try:
        official = load_official_slate(slate_date)
    except FifthPickError as exc:
        print(f"Board preflight stopped: {exc}", file=sys.stderr)
        return 1
    if (
        official is not None
        and expected_games is not None
        and expected_games != len(official.games)
    ):
        print(
            "Board preflight stopped: expected count conflicts with the official slate.",
            file=sys.stderr,
        )
        return 1
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
    now = datetime.now(timezone)
    slate = [
        event for event in events if event.commence_time.astimezone(timezone).date() == slate_date
    ]
    coverage = (
        reconcile_coverage(official, events, day=slate_date) if official is not None else None
    )
    partial = (
        not coverage["provider_matches_official_slate"]
        if coverage is not None
        else expected_games is not None and len(slate) != expected_games
    )
    report = json.dumps(
        {
            "mode": "LIVE_PROVIDER_COVERAGE_ONLY" if partial else "LIVE_PROVIDER_DISCOVERY_ONLY",
            "slate_date": slate_date.isoformat(),
            "expected_games": expected_games,
            "checked_at": now.isoformat(),
            "quota": asdict(quota),
            "events": [provider_event_row(event) for event in slate],
            "provider_discovered_game_count": len(slate),
            "coverage": coverage,
        },
        sort_keys=True,
    )
    store = application_run_store()
    try:
        content = (report + "\n").encode("utf-8")
        if partial:
            _atomic_write(coverage_path(store, slate_date), content)
        if not partial:
            _atomic_write(preflight_path(store, slate_date), content)
    except OSError:
        print(report)
        print("Board preflight succeeded but the manifest could not be saved.", file=sys.stderr)
        return 1
    print(report)
    if partial:
        print(
            "Board preflight found incomplete or conflicting provider coverage. "
            "Saved diagnostics only. No collection manifest was written.",
            file=sys.stderr,
        )
    return int(partial)


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


def _game_lines_grant(arguments: list[str], read: Callable[[str], str]) -> int:
    from fifth_pick.board_collection import live_slot_has_bound_aliases
    from fifth_pick.sources.game_lines import GameLinesGrant, record_game_lines_grant

    parser = argparse.ArgumentParser(prog="fifth-pick game-lines-grant", allow_abbrev=False)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--bookmaker", required=True)
    parser.add_argument("--phase", choices=("analysis", "t20"), action="append", required=True)
    parser.add_argument("--max-credits", type=int, required=True)
    try:
        args = parser.parse_args(arguments)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    try:
        store = application_run_store()
        grant = GameLinesGrant(
            args.run_id, args.event_id, args.bookmaker, tuple(args.phase), args.max_credits
        )
        scope = grant.scope()
        context = read_slate_run_context(store, args.run_id)
        if not context.event_boards or any(
            board.evidence_mode is not EvidenceMode.LIVE for board in context.event_boards
        ):
            raise ValueError("a receipt-bound LIVE slate is required")
        event = next(
            (row for row in context.event_boards[0].events if row.event_id == args.event_id), None
        )
        if event is None or event.commence_time <= datetime.now(UTC):
            raise ValueError("the scoped event is absent or has already started")
        if not live_slot_has_bound_aliases(args.run_id, 1, args.event_id):
            raise ValueError("the event requires an authorized, receipt-bound Snapshot 1")
        print(scope)
        if read("Joseph only. Type AUTHORIZE GAME LINES to record this grant: ") != (
            "AUTHORIZE GAME LINES"
        ):
            return 1
        now = datetime.now(UTC)
        if event.commence_time <= now:
            raise ValueError("the scoped event started before confirmation")
        record_game_lines_grant(store, grant, now)
    except (FifthPickError, ValueError, OSError, EOFError) as exc:
        print(f"Game-lines authorization stopped: {exc}", file=sys.stderr)
        return 1
    print("Game-lines authorization recorded. No request was made.")
    return 0


def _game_lines_collect(arguments: list[str], read: Callable[[str], str]) -> int:
    from fifth_pick.board_collection import live_slot_has_bound_aliases
    from fifth_pick.snapshots import T20_OFFSET, SnapshotEvidence, read_receipted_snapshot_ledger
    from fifth_pick.sources.base import SourceEvent
    from fifth_pick.sources.game_lines import GameLinesGrant, acquire_game_lines
    from fifth_pick.sources.odds_api import OddsApiClient
    from fifth_pick.sources.supporting_fixture import aware_timestamp
    from fifth_pick.sources.transport import TransportError, UrllibTransport
    from fifth_pick.t20_review import review_window_allows

    parser = argparse.ArgumentParser(prog="fifth-pick game-lines-collect", allow_abbrev=False)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phase", choices=("analysis", "t20"), required=True)
    try:
        args = parser.parse_args(arguments)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2

    stage = "saved grant and LIVE slate"
    try:
        store = application_run_store()
        receipts = store.read_receipts(args.run_id)
        grants = [row for row in receipts if row["event_key"] == "game-lines-live-grant"]
        if len(grants) != 1:
            raise ValueError("expected one saved grant")
        saved = json.loads(grants[0]["reason"] or "")
        grant = GameLinesGrant(
            args.run_id,
            saved["event_id"],
            saved["bookmaker"],
            tuple(saved["phases"]),
            saved["credit_limit"],
        )
        granted_at = aware_timestamp(grants[0]["timestamp"])
        if (
            grants[0] != grant.receipt(granted_at).to_dict()
            or granted_at > datetime.now(UTC)
            or args.phase not in grant.phases
        ):
            raise ValueError("saved grant does not authorize this phase")
        context = read_slate_run_context(store, args.run_id)
        if not context.event_boards or any(
            board.evidence_mode is not EvidenceMode.LIVE for board in context.event_boards
        ):
            raise ValueError("expected a receipt-bound LIVE slate")
        events = [row for row in context.event_boards[0].events if row.event_id == grant.event_id]
        if len(events) != 1:
            raise ValueError("granted event is not uniquely present")
        row = events[0]
        event = SourceEvent(row.event_id, row.home_team, row.away_team, row.commence_time, ())
        target = event.commence_time - T20_OFFSET
        slot = 2 if args.phase == "analysis" else 3
        if not live_slot_has_bound_aliases(args.run_id, slot, event.event_id) or not any(
            isinstance(snapshot, SnapshotEvidence)
            and snapshot.event_id == event.event_id
            and snapshot.snapshot.number == slot
            and not snapshot.late
            for snapshot in read_receipted_snapshot_ledger(store, args.run_id)
        ):
            print(
                f"Game-lines collection requires a timely, completed LIVE Snapshot {slot}.",
                file=sys.stderr,
            )
            return 1
        key = f"game-lines-live-{args.phase}-{event.event_id}"
        if any(row["event_key"] == key for row in receipts):
            print("Game-lines phase was already attempted. Inspect the run audit.", file=sys.stderr)
            return 1
        print(grant.scope())
        if (
            read(
                f"Joseph only. For {args.phase}, one free quota check and up to 2 credits. "
                "Type COLLECT GAME LINES: "
            )
            != "COLLECT GAME LINES"
        ):
            return 1
        stage = "authorized timing window"
        now = datetime.now(UTC)
        if not (now < target if slot == 2 else review_window_allows(target, now, live=True)):
            raise ValueError("phase is outside its collection window")
        stage = "quota-free event and balance check"
        transport = UrllibTransport()
        current, quota = OddsApiClient(transport=transport).discover_free_events(authorized=True)
        if event not in current:
            raise ValueError("provider event no longer matches the LIVE slate")
        stage = "scoped request, quota reconciliation, and receipt validation"
        result = acquire_game_lines(
            store,
            grant,
            transport=transport,
            phase=args.phase,
            event=event,
            quota_before=quota,
            max_age=timedelta(minutes=10),
            authorized=True,
        )
    except TransportError as exc:
        print(f"Game-lines collection stopped during {stage} ({exc.category}).", file=sys.stderr)
        return 1
    except (FifthPickError, OSError, ValueError, TypeError, KeyError, EOFError) as exc:
        print(
            f"Game-lines collection stopped during {stage} ({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(asdict(result), default=lambda value: value.isoformat(), sort_keys=True))
    return 0


def _fixture_command(command: str, arguments: list[str]) -> int:
    parser = argparse.ArgumentParser(prog=f"fifth-pick {command}", allow_abbrev=False)
    parser.add_argument("--run-id", required=True)
    if command in {"analyze", "t20"}:
        parser.add_argument("--fixture", type=Path)
    if command == "analyze":
        parser.add_argument("--snapshot", required=True, type=int, choices=(1, 2))
        parser.add_argument("--history-candidate-key")
        parser.add_argument(
            "--history-archive", nargs=2, action="append", metavar=("DIRECTORY", "SHA256")
        )
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
            historical = None
            if command == "analyze" and (args.history_candidate_key or args.history_archive):
                from fifth_pick.history_compare_cli import compare_archives

                if args.fixture is not None or not (
                    args.history_candidate_key and args.history_archive
                ):
                    raise ValueError(
                        "LIVE history comparison requires a candidate key and archives"
                    )
                try:
                    historical = compare_archives(
                        args.run_id,
                        args.history_candidate_key,
                        number,
                        args.history_archive,
                        required_mode=EvidenceMode.LIVE,
                    )
                except (TypeError, KeyError, RecursionError) as exc:
                    raise ValueError("invalid history archive structure") from exc
            if args.fixture is not None:
                output = collect_fixture_stage(store, args.run_id, number, args.fixture)
            else:
                from fifth_pick.live_analysis import live_analysis_view

                output = (
                    live_analysis_view(store, args.run_id, review=True)
                    if command == "t20"
                    else live_analysis_view(store, args.run_id, review=False, snapshot=number)
                )
                blocked = output["status"] == "BLOCKED"
                if historical is not None:
                    output["historical_comparison"] = historical
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
        elif command == "review-handoff":
            from fifth_pick.product_review import review_handoff

            output = review_handoff(store, args.run_id)
        elif command == "review-correct":
            from fifth_pick.product_review import record_product_correction

            output = record_product_correction(
                store, args.run_id, remove=tuple(args.remove), reason=args.reason
            )
        else:
            from fifth_pick.product_review import operator_audit

            view = candidates_view if command == "candidates" else operator_audit
            output = view(store, args.run_id)
    except (FifthPickError, OSError, ValueError) as exc:
        print(f"{command} stopped: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, default=str))
    return int(blocked)


def _interactive_decision(
    run_id: str, read: Callable[[str], str], *, menu_form: bool = False
) -> dict[str, object]:
    from fifth_pick.approval import JOSEPH_ACTOR
    from fifth_pick.menu_presentation import fields, picks, review_assessments, selection_keys
    from fifth_pick.product_review import expired_live_selections, review_status
    from fifth_pick.review import ReviewError

    store = application_run_store()
    fixture_run = (
        require_complete_fixture(store, run_id) if is_fixture_workflow(store, run_id) else None
    )
    proposal = load_pending_proposal(store, run_id)
    expired = (
        ()
        if is_fixture_workflow(store, run_id)
        else expired_live_selections(store, run_id, proposal)
    )
    print("Proposed final set")
    proposed = proposal["proposed"]
    assert isinstance(proposed, list)
    if menu_form:
        assessments = review_assessments(fixture_run.reviews) if fixture_run else None
        picks(proposed, supporting=True, assessments=assessments)
        for index, item in enumerate(proposed, 1):
            if item["candidate_key"] in expired:
                print(f"Selection #{index}: decision window closed. Approval unavailable.")
    else:
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
    prompt = "Joseph's decision (APPROVE / REJECT / MODIFY)"
    action_text = read(prompt + (" [A / R / M]: " if menu_form else ": "))
    if menu_form:
        action_text = action_text.strip().upper()
        action_text = {"A": "APPROVE", "R": "REJECT", "M": "MODIFY"}.get(action_text, action_text)
    try:
        action = DecisionAction(action_text)
    except ValueError as exc:
        if menu_form:
            raise ApprovalError(
                "Invalid decision. Enter APPROVE, REJECT, or MODIFY. Shortcuts: A, R, M."
            ) from exc
        raise ApprovalError("decision must be APPROVE, REJECT, or MODIFY") from exc

    selected: tuple[str, ...] = ()
    reason = ""
    exception_digest = None
    if action is DecisionAction.MODIFY:
        if menu_form:
            print("Selection numbers apply only to the proposal shown above.")
            response = read("Selection numbers to retain, comma-separated (blank for none): ")
            selected = selection_keys(response, proposed)
        else:
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

    recorded = _apply_joseph_decision(
        run_id=run_id,
        store=store,
        action=action,
        displayed_proposal_digest=proposal_fingerprint(proposal),
        selected_candidate_keys=selected,
        reason=reason,
        review_exception_sha256=exception_digest,
    )

    if menu_form:
        print()
        fields(
            "Decision submitted",
            (
                ("Decision", action.value),
                ("Authority", JOSEPH_ACTOR),
                (
                    "Selections retained",
                    len(proposed) if action is DecisionAction.APPROVE else len(selected),
                ),
            ),
        )

    return recorded


def _interactive_result_record(
    run_id: str, selection_id: str, read: Callable[[str], str], *, menu_form: bool = False
) -> Path:
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
        f"{selected['direction']} {selected['projection']}"
        + ("" if menu_form else f" | key={selection_id}")
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
        reference_prompt = "Player-specific settlement reference: "
        if menu_form and fixture:
            reference_prompt = (
                "Settlement reference (type FIXTURE to use this selection's demo reference): "
            )
        reference = read(reference_prompt).strip()
        if menu_form and fixture and reference == "FIXTURE":
            reference = f"fixture:results/{selection_id}"
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
