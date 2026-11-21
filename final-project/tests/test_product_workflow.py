import json
import unittest
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from fifth_pick.fixture_workflow import collect_fixture_stage, final_view
from fifth_pick.menu import DEMO
from fifth_pick.product_review import review_handoff, review_material, review_status
from fifth_pick.review_bridge import process_request
from fifth_pick.schedule import schedule_view
from fifth_pick.storage import RunStore
from tests.test_fixture_cli import TIMES, TIPOFF


class ProductWorkflowTests(unittest.TestCase):
    def test_audit_opens_receipt_only_collection_without_admitting_evidence(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch

        from fifth_pick.cli import main
        from fifth_pick.receipts import Receipt
        from fifth_pick.sources.odds_api import SOURCE_ID

        for key, event, result in (
            ("reserved", "DFS_BOARD_RESERVED", "RESERVED"),
            ("quarantine", "DFS_BOARD_LABEL_QUARANTINE", "CAPTURED"),
            ("stopped", "DFS_BOARD_STOPPED", "STOPPED"),
        ):
            self.store.append_receipt(
                Receipt(
                    TIMES[0].isoformat(),
                    event,
                    result,
                    "event",
                    SOURCE_ID,
                    "diagnostic",
                    self.run_id,
                    f"dfs-board-1-event-{key}",
                )
            )
        before = self.store.receipts_path(self.run_id).read_bytes()
        with (
            patch("fifth_pick.cli.application_run_store", return_value=self.store),
            patch("fifth_pick.product_review.application_run_store", return_value=self.store),
            redirect_stdout(StringIO()) as output,
        ):
            self.assertEqual(main(["audit", "--run-id", self.run_id]), 0)
        audit = json.loads(output.getvalue())
        self.assertEqual(audit["status"], "COLLECTION_STOPPED")
        self.assertEqual(audit["snapshots"], [])
        self.assertIsNone(audit["final"])
        self.assertEqual(len(audit["receipts"]), 3)
        self.assertFalse((self.store.run_directory(self.run_id) / "run.json").exists())
        self.assertEqual(self.store.receipts_path(self.run_id).read_bytes(), before)
        directory = self.store.run_directory(self.run_id)
        (directory / "run.json").write_text("{}")
        (directory / "m4-event-boards.jsonl").write_text("{}\n")
        with (
            patch("fifth_pick.cli.application_run_store", return_value=self.store),
            patch("fifth_pick.product_review.application_run_store", return_value=self.store),
            redirect_stdout(StringIO()) as partial_output,
        ):
            self.assertEqual(main(["audit", "--run-id", self.run_id]), 0)
        self.assertEqual(json.loads(partial_output.getvalue())["mode"], "RECEIPTS_ONLY")

    def test_live_analysis_can_display_comparison_without_admitting_it(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch

        from fifth_pick.cli import main
        from fifth_pick.sources.base import EvidenceMode

        key = "a" * 64
        archive = ["archive", "b" * 64]
        view = {"status": "BLOCKED", "candidates": [{"supporting_evidence": []}]}
        result = {"status": "ANALYSIS_ONLY", "counts": {"HIGHER": 1}}
        with (
            patch("fifth_pick.cli.application_run_store", return_value=self.store),
            patch("fifth_pick.live_analysis.live_analysis_view", return_value=view),
            patch(
                "fifth_pick.history_compare_cli.compare_archives", return_value=result
            ) as compare,
            redirect_stdout(StringIO()) as output,
        ):
            self.assertEqual(
                main(
                    [
                        "analyze",
                        "--run-id",
                        self.run_id,
                        "--snapshot",
                        "2",
                        "--history-candidate-key",
                        key,
                        "--history-archive",
                        *archive,
                    ]
                ),
                1,
            )
        compare.assert_called_once_with(
            self.run_id, key, 2, [archive], required_mode=EvidenceMode.LIVE
        )
        self.assertEqual(json.loads(output.getvalue())["historical_comparison"], result)
        self.assertEqual(view["candidates"], [{"supporting_evidence": []}])
        self.assertEqual(self.store.read_receipts(self.run_id), ())

    def test_live_commands_without_fixture_route_to_the_receipt_backed_gate(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch

        from fifth_pick.cli import main

        with (
            patch("fifth_pick.cli.application_run_store", return_value=self.store),
            patch("fifth_pick.live_analysis.live_analysis_view") as view,
            redirect_stdout(StringIO()),
        ):
            view.return_value = {"status": "BLOCKED", "reason": "T20_CHECK_UNAVAILABLE"}
            self.assertEqual(main(["analyze", "--run-id", self.run_id, "--snapshot", "1"]), 1)
            view.assert_called_with(self.store, self.run_id, review=False, snapshot=1)
            self.assertEqual(main(["t20", "--run-id", self.run_id]), 1)
            view.assert_called_with(self.store, self.run_id, review=True)
        self.assertEqual(self.store.read_receipts(self.run_id), ())

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = RunStore(Path(tmp.name))
        self.run_id = "product-review"

    def collect(self, count):
        for slot in range(1, count + 1):
            collect_fixture_stage(self.store, self.run_id, slot, DEMO / str(slot))

    def test_fresh_controller_handoff_is_bounded_and_read_only(self):
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        from unittest.mock import patch

        from fifth_pick.cli import main

        self.collect(3)
        final_view(self.store, self.run_id)
        before = self.store.read_receipts(self.run_id)
        status = review_status(self.store, self.run_id)
        output, errors = StringIO(), StringIO()
        with (
            patch("fifth_pick.cli.application_run_store", return_value=RunStore(self.store.root)),
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            result = main(["review-handoff", "--run-id", self.run_id])
        self.assertEqual(result, 0, errors.getvalue())
        handoff = json.loads(output.getvalue())
        self.assertEqual(handoff["state"], "AWAITING_REVIEW")
        self.assertEqual(handoff["next_step"], "CONFIRM_INITIAL_REVIEW_NOT_ATTEMPTED")
        self.assertEqual(handoff["artifact_sha256"], status["artifact_sha256"])
        self.assertEqual(handoff["proposal_sha256"], status["proposal_sha256"])
        self.assertFalse(handoff["dispatch_authorized"])
        self.assertNotIn("review_material", handoff)
        self.assertNotIn("receipts", handoff)
        self.assertLess(len(output.getvalue()), 1024)
        self.assertEqual(self.store.read_receipts(self.run_id), before)

        verdict_key = f"product-verdict-{status['review_cycle_id']}-0"
        (self.store.run_directory(self.run_id) / f"{verdict_key}.json").write_text(
            "{}", encoding="utf-8"
        )
        interrupted = review_handoff(RunStore(self.store.root), self.run_id)
        self.assertEqual(interrupted["state"], "INCOMPLETE_REVIEW_RECEIPTS")
        self.assertEqual(interrupted["next_step"], "STOP_AND_RECONCILE_WITH_JOSEPH")
        self.assertFalse(interrupted["dispatch_authorized"])

    def test_t20_readiness_reports_due_and_late_with_actual_time(self):
        self.collect(2)
        due = cast(dict[str, Any], schedule_view(self.store, self.run_id, as_of=TIMES[2]))
        late = cast(
            dict[str, Any],
            schedule_view(self.store, self.run_id, as_of=TIMES[2] + timedelta(seconds=1)),
        )
        self.assertEqual({row["snapshot_3"] for row in due["candidates"]}, {"DUE"})
        self.assertEqual({row["snapshot_3"] for row in late["candidates"]}, {"LATE_ONLY"})
        self.assertEqual(due["events"][0]["tipoff"], TIPOFF.isoformat())

    def test_review_material_uses_proposal_and_exact_m10_receipt(self):
        self.collect(3)
        final_view(self.store, self.run_id)
        bundle = review_material(self.store, self.run_id)
        self.assertIn("Luka Doncic", str(bundle["review_material"]))
        self.assertEqual(review_status(self.store, self.run_id)["state"], "AWAITING_REVIEW")
        request = {key: value for key, value in bundle.items() if key != "review_material"}
        request["kind"] = "VERDICT"
        request["verdict_json"] = json.dumps(
            {"status": "PASS", "summary": "Synthetic test", "findings": []}
        )
        result = process_request(json.dumps(request), self.store, TIMES[2])
        self.assertEqual(result.exit_code, 0, result.response)
        self.assertEqual(review_status(self.store, self.run_id)["state"], "REVIEWED_FOR_JOSEPH")

    def test_one_product_correction_requires_exact_corrected_pass(self):
        from fifth_pick.approval import ApprovalError, _apply_joseph_decision, load_pending_proposal
        from fifth_pick.finalization import proposal_fingerprint
        from fifth_pick.models import DecisionAction
        from fifth_pick.review import ReviewError

        self.collect(3)
        final_view(self.store, self.run_id)
        original = review_material(self.store, self.run_id)
        proposal = load_pending_proposal(self.store, self.run_id)
        proposed = proposal["proposed"]
        assert isinstance(proposed, list)
        key = proposed[0]["candidate_key"]

        def bridge(bundle, status=None):
            request = {k: v for k, v in bundle.items() if k != "review_material"}
            request["kind"] = "REVISION_DISPATCHED" if status is None else "VERDICT"
            if status is None:
                request["revision"] = 1
            else:
                request["verdict_json"] = json.dumps(
                    {"status": status, "summary": "Fixture review", "findings": ["Fixture finding"]}
                )
            return process_request(json.dumps(request), self.store, TIMES[2])

        from fifth_pick.product_review import record_product_correction

        self.assertEqual(bridge(original, "FAIL").exit_code, 0)
        with self.assertRaises(ReviewError):
            record_product_correction(self.store, self.run_id, remove=(key,), reason="Fixture")
        self.assertEqual(bridge(original).exit_code, 0)
        recovered = review_handoff(RunStore(self.store.root), self.run_id)
        self.assertEqual(recovered["next_step"], "STOP_AND_RECONCILE_WITH_JOSEPH")
        self.assertFalse(recovered["dispatch_authorized"])
        revised = record_product_correction(
            self.store, self.run_id, remove=(key,), reason="Remove the cited fixture selection"
        )
        self.assertEqual(revised["revision"], 1)
        self.assertEqual(revised["initial_artifact_sha256"], original["initial_artifact_sha256"])
        self.assertNotEqual(revised["current_artifact_sha256"], original["current_artifact_sha256"])
        self.assertNotEqual(bridge(original).exit_code, 0)
        new_proposal = load_pending_proposal(self.store, self.run_id)
        self.assertEqual(new_proposal["proposed"], [])
        with self.assertRaisesRegex(ApprovalError, "reviewed exact proposal"):
            _apply_joseph_decision(
                run_id=self.run_id,
                store=self.store,
                action=DecisionAction.APPROVE,
                displayed_proposal_digest=proposal_fingerprint(new_proposal),
            )
        self.assertEqual(bridge(revised, "PASS").exit_code, 0)
        self.assertEqual(review_status(self.store, self.run_id)["state"], "REVIEWED_FOR_JOSEPH")
        approved = _apply_joseph_decision(
            run_id=self.run_id,
            store=self.store,
            action=DecisionAction.APPROVE,
            displayed_proposal_digest=proposal_fingerprint(new_proposal),
        )
        self.assertEqual(approved["state"], "APPROVED_BY_JOSEPH")
        from fifth_pick.evaluation import evaluation_view

        report = evaluation_view(self.store, self.run_id)
        self.assertEqual(report["recommendation"]["original_proposal"]["slate_version"], 1)
        self.assertEqual(report["recommendation"]["current_proposal"]["slate_version"], 2)

    def test_product_concerns_preserve_exact_original_findings(self):
        from datetime import datetime
        from types import SimpleNamespace
        from unittest.mock import patch

        from fifth_pick.approval import ApprovalError, _apply_joseph_decision, load_pending_proposal
        from fifth_pick.finalization import proposal_fingerprint
        from fifth_pick.models import DecisionAction
        from fifth_pick.slate_manifest import read_slate_run_context
        from fifth_pick.sources.base import EvidenceMode

        self.collect(3)
        final_view(self.store, self.run_id)
        bundle = review_material(self.store, self.run_id)
        request = {k: v for k, v in bundle.items() if k != "review_material"}
        request["kind"] = "VERDICT"
        request["verdict_json"] = json.dumps(
            {"status": "CONCERNS", "summary": "Fixture concern", "findings": ["Specific finding"]}
        )
        self.assertEqual(process_request(json.dumps(request), self.store, TIMES[2]).exit_code, 0)
        status = review_status(self.store, self.run_id)
        self.assertEqual(status["state"], "ESCALATE_TO_JOSEPH")
        verdict = status["verdict"]
        assert isinstance(verdict, dict)
        self.assertEqual(verdict["findings"], ["Specific finding"])
        proposal = load_pending_proposal(self.store, self.run_id)
        events = read_slate_run_context(self.store, self.run_id).event_boards[0].events
        live = SimpleNamespace(evidence_mode=EvidenceMode.LIVE, events=events)
        digest = status["verdict_sha256"]
        assert isinstance(digest, str)
        with (
            patch("fifth_pick.approval._manifest_start_board", return_value=live),
            patch("fifth_pick.approval.datetime", wraps=datetime) as clock,
        ):
            clock.now.return_value = TIMES[2]
            with self.assertRaisesRegex(ApprovalError, "reviewed exact proposal"):
                _apply_joseph_decision(
                    run_id=self.run_id,
                    store=self.store,
                    action=DecisionAction.APPROVE,
                    displayed_proposal_digest=proposal_fingerprint(proposal),
                )
            accepted = _apply_joseph_decision(
                run_id=self.run_id,
                store=self.store,
                action=DecisionAction.APPROVE,
                displayed_proposal_digest=proposal_fingerprint(proposal),
                review_exception_sha256=digest,
                reason="Owner fixture decision",
            )
        self.assertEqual(accepted["state"], "APPROVED_BY_JOSEPH")
        self.assertTrue(
            any(digest in (row["reason"] or "") for row in self.store.read_receipts(self.run_id))
        )

    def test_live_path_has_no_public_grant_and_does_not_request_credentials(self):
        import contextlib
        import io
        from unittest.mock import Mock

        from fifth_pick.cli import main

        prompt = Mock(side_effect=AssertionError("no prompt expected"))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["board-smoke", "--run-id", "no-grant"], prompt=prompt), 1)
        self.assertIn("LIVE disabled", output.getvalue())
        prompt.assert_not_called()

    def test_live_approval_deadline_does_not_write_a_decision(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from fifth_pick.approval import ApprovalError, _apply_joseph_decision, load_pending_proposal
        from fifth_pick.finalization import proposal_fingerprint
        from fifth_pick.models import DecisionAction
        from fifth_pick.slate_manifest import read_slate_run_context
        from fifth_pick.sources.base import EvidenceMode

        self.collect(3)
        final_view(self.store, self.run_id)
        proposal = load_pending_proposal(self.store, self.run_id)
        events = read_slate_run_context(self.store, self.run_id).event_boards[0].events
        late_manifest = SimpleNamespace(evidence_mode=EvidenceMode.LIVE, events=events)
        before = self.store.read_receipts(self.run_id)
        with (
            patch("fifth_pick.approval._manifest_start_board", return_value=late_manifest),
            self.assertRaisesRegex(ApprovalError, "pre-tipoff"),
        ):
            _apply_joseph_decision(
                run_id=self.run_id,
                store=self.store,
                action=DecisionAction.APPROVE,
                displayed_proposal_digest=proposal_fingerprint(proposal),
            )
        self.assertEqual(self.store.read_receipts(self.run_id), before)

    def test_pretipoff_live_selection_requires_review_of_its_exact_proposal(self):
        from datetime import datetime
        from types import SimpleNamespace
        from unittest.mock import patch

        from fifth_pick.approval import ApprovalError, _apply_joseph_decision, load_pending_proposal
        from fifth_pick.finalization import proposal_fingerprint
        from fifth_pick.models import DecisionAction
        from fifth_pick.slate_manifest import read_slate_run_context
        from fifth_pick.sources.base import EvidenceMode

        self.collect(3)
        final_view(self.store, self.run_id)
        proposal = load_pending_proposal(self.store, self.run_id)
        events = read_slate_run_context(self.store, self.run_id).event_boards[0].events
        live_manifest = SimpleNamespace(evidence_mode=EvidenceMode.LIVE, events=events)
        before = self.store.read_receipts(self.run_id)
        with (
            patch("fifth_pick.approval._manifest_start_board", return_value=live_manifest),
            patch("fifth_pick.approval.datetime", wraps=datetime) as clock,
            self.assertRaisesRegex(ApprovalError, "reviewed exact proposal"),
        ):
            clock.now.return_value = TIMES[2]
            _apply_joseph_decision(
                run_id=self.run_id,
                store=self.store,
                action=DecisionAction.APPROVE,
                displayed_proposal_digest=proposal_fingerprint(proposal),
            )
        self.assertEqual(self.store.read_receipts(self.run_id), before)
        bundle = review_material(self.store, self.run_id)
        request = {key: value for key, value in bundle.items() if key != "review_material"}
        request["kind"] = "VERDICT"
        request["verdict_json"] = json.dumps(
            {"status": "PASS", "summary": "Synthetic test", "findings": []}
        )
        self.assertEqual(process_request(json.dumps(request), self.store, TIMES[2]).exit_code, 0)
        with (
            patch("fifth_pick.approval._manifest_start_board", return_value=live_manifest),
            patch("fifth_pick.approval.datetime", wraps=datetime) as clock,
        ):
            clock.now.return_value = TIMES[2]
            approved = _apply_joseph_decision(
                run_id=self.run_id,
                store=self.store,
                action=DecisionAction.APPROVE,
                displayed_proposal_digest=proposal_fingerprint(proposal),
            )
        self.assertEqual(approved["state"], "APPROVED_BY_JOSEPH")

    def test_staggered_event_targets_do_not_share_a_clock(self):
        from tests.test_finalization import make_event_rows, record_run_slate

        record_run_slate(
            str(self.store.root),
            self.run_id,
            make_event_rows(2, event_times=(TIPOFF, TIPOFF + timedelta(hours=2))),
        )
        view = cast(dict[str, Any], schedule_view(self.store, self.run_id, as_of=TIMES[2]))
        self.assertEqual(
            [event["t20_target_at"] for event in view["events"]],
            [TIMES[2].isoformat(), (TIMES[2] + timedelta(hours=2)).isoformat()],
        )

    def test_incomplete_escalation_is_not_reported_as_delivered(self):
        self.collect(3)
        final_view(self.store, self.run_id)
        request = {
            key: value
            for key, value in review_material(self.store, self.run_id).items()
            if key != "review_material"
        }
        request["kind"] = "VERDICT"
        request["verdict_json"] = json.dumps(
            {"status": "CONCERNS", "summary": "Synthetic test", "findings": ["Example concern"]}
        )
        result = process_request(json.dumps(request), self.store, TIMES[2])
        self.assertEqual(result.exit_code, 0, result.response)
        self.assertEqual(review_status(self.store, self.run_id)["state"], "ESCALATE_TO_JOSEPH")
        path = self.store.receipts_path(self.run_id)
        rows = self.store.read_receipts(self.run_id)
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows if row["event"] != "ESCALATE_TO_JOSEPH"),
            encoding="utf-8",
        )
        self.assertEqual(
            review_status(self.store, self.run_id)["state"], "INCOMPLETE_REVIEW_RECEIPTS"
        )

    def test_cli_explicitly_reports_partial_platform_coverage(self):
        import contextlib
        import io
        from unittest.mock import patch

        from fifth_pick.board_smoke import SmokeAuthorization, SmokeEvent, SmokeResult
        from fifth_pick.cli import main
        from fifth_pick.sources.base import EvidenceMode

        event = SmokeEvent("event", "Home", "Away", TIPOFF, 1, "2026-11-15", ())
        result = SmokeResult(
            event,
            EvidenceMode.FIXTURE,
            (("prizepicks", "POINTS"),),
            (),
            0,
            (),
            "a" * 64,
            4,
        )
        output = io.StringIO()
        with (
            patch("fifth_pick.board_smoke.run_board_smoke", return_value=result),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(
                main(
                    ["board-smoke", "--run-id", "smoke"],
                    prompt=lambda _: "DISCOVER",
                    smoke_authorization=SmokeAuthorization(
                        "smoke", EvidenceMode.FIXTURE, "test", TIPOFF
                    ),
                ),
                0,
            )
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "PARTIAL_COVERAGE")
        self.assertIn(["underdog", "player_points"], report["missing_coverage"])
        self.assertEqual(report["event"]["slate_classification"], "HALF")
