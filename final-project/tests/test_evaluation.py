import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import fifth_pick.storage as storage
from fifth_pick.cli import main
from fifth_pick.evaluation import EvaluationError, evaluation_view
from fifth_pick.fixture_workflow import collect_fixture_stage, final_view
from fifth_pick.product_review import review_material
from fifth_pick.review_bridge import process_request
from tests.test_fixture_cli import RUN, TIPOFF, write_fixtures


class ExperimentEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.fixtures = root / "fixture"
        self.store = storage.RunStore(root / "state")
        storage_patch = patch.object(storage, "APPLICATION_STORAGE_ROOT", self.store.root)
        storage_patch.start()
        self.addCleanup(storage_patch.stop)

    def finish_fixture(self, *, projection: bool = True) -> str:
        write_fixtures(self.fixtures, projection=projection)
        for number in (1, 2, 3):
            collect_fixture_stage(self.store, RUN, number, self.fixtures / str(number))
        final_view(self.store, RUN)
        report = evaluation_view(self.store, RUN)
        proposed = report["recommendation"]["current_proposal"]["proposed"]
        return proposed[0]["candidate_key"] if proposed else ""

    def command(self, *arguments: str, answers: tuple[str, ...]) -> None:
        with redirect_stdout(io.StringIO()), patch("builtins.input", side_effect=answers):
            self.assertEqual(main(arguments), 0)

    def test_missed_outcome_does_not_change_methodology_or_discipline_evidence(self) -> None:
        key = self.finish_fixture()
        self.command("decide", "--run-id", RUN, answers=("APPROVE",))
        before = evaluation_view(self.store, RUN)
        self.command(
            "result",
            "record",
            "--run-id",
            RUN,
            "--selection",
            key,
            answers=(
                "MISS",
                "synthetic-fixture",
                TIPOFF.isoformat(),
                f"fixture:results/{key}",
                "Synthetic PrizePicks Luka Doncic Assists Higher 9.5 settled MISS.",
                "YES",
            ),
        )
        after = evaluation_view(self.store, RUN)
        self.assertEqual(after["process"], before["process"])

        self.assertEqual(after["outcomes"]["status_counts"]["MISS"], 1)
        self.assertEqual(after["outcomes"]["scope"], "JOSEPH_APPROVED_ONLY")
        t20 = after["process"]["snapshots_and_t20"]["t20_changes"]
        latest = next(row for row in t20 if row["candidate_key"] == key)
        self.assertEqual(latest["projection"]["at_t20"], 9.5)
        self.assertEqual(latest["current_confidence"], "HIGH")
        self.assertEqual(after["outcomes"]["denominator"], 1)
        self.assertEqual(after["outcomes"]["records"][0]["selection_id"], key)
        self.assertEqual(after["owner_decisions"][0]["action"], "APPROVE")
        self.assertEqual(after["process"]["independent_review"]["status"], "NOT RECORDED")
        self.assertIn("IDENTITY_UNRESOLVED", after["process"]["identity_and_authorization"])

    def test_no_entry_has_zero_outcomes_and_replays_without_writing(self) -> None:
        self.finish_fixture(projection=False)
        path = self.store.run_directory(RUN)
        original = {file: file.read_bytes() for file in path.rglob("*") if file.is_file()}
        report = evaluation_view(self.store, RUN)
        self.assertEqual(report, evaluation_view(self.store, RUN))
        self.assertEqual(report["outcomes"]["denominator"], 0)
        self.assertEqual(
            report["recommendation"]["current_proposal"]["recommendation"],
            "NO ENTRY RECOMMENDED TODAY.",
        )
        self.assertEqual(original, {file: file.read_bytes() for file in original})

    def test_removed_proposal_has_no_counterfactual_settlement(self) -> None:
        key = self.finish_fixture()
        self.command("decide", "--run-id", RUN, answers=("MODIFY", ""))
        report = evaluation_view(self.store, RUN)
        self.assertEqual(report["recommendation"]["current_proposal"]["proposed"], [])
        self.assertEqual(
            report["recommendation"]["original_proposal"]["proposed"][0]["candidate_key"], key
        )
        self.assertEqual(report["owner_decisions"][0]["selection"], [])
        self.assertEqual(report["outcomes"]["counterfactual_status"], "NOT RECORDED")
        self.assertEqual(report["outcomes"]["records"], [])

    def test_missing_legacy_capture_is_disclosed(self) -> None:
        self.finish_fixture()
        self.command("decide", "--run-id", RUN, answers=("MODIFY", ""))
        audit_path = self.store.run_directory(RUN) / "audit.json"
        audit = json.loads(audit_path.read_bytes())
        change = audit["joseph_decisions"][0]
        change.pop("displayed_proposal", None)
        change.pop("displayed_proposal_sha256", None)
        audit_path.write_text(json.dumps(audit))
        report = evaluation_view(self.store, RUN)
        self.assertIsNone(report["recommendation"]["original_proposal"])
        self.assertIsNone(report["owner_decisions"][0]["displayed_proposal"])

    def test_altered_prior_decision_receipt_details_fail_closed(self) -> None:
        self.finish_fixture()
        self.command("decide", "--run-id", RUN, answers=("MODIFY", ""))
        audit_path = self.store.run_directory(RUN) / "audit.json"
        audit = json.loads(audit_path.read_bytes())
        audit["joseph_decisions"][0]["selection"] = ["different-selection"]
        audit_path.write_text(json.dumps(audit))
        with self.assertRaises(EvaluationError):
            evaluation_view(self.store, RUN)

    def test_only_exact_product_review_counts_as_independent_review(self) -> None:
        self.finish_fixture()
        request = review_material(self.store, RUN)
        request.pop("review_material")
        request["kind"] = "VERDICT"
        request["verdict_json"] = json.dumps(
            {"status": "PASS", "summary": "Synthetic deterministic fixture", "findings": []}
        )
        harness_sample = {**request, "subject": "non-product review example"}
        self.assertEqual(
            process_request(json.dumps(harness_sample), self.store, TIPOFF).exit_code, 0
        )
        independent = evaluation_view(self.store, RUN)["process"]["independent_review"]
        self.assertEqual(independent["status"], "NOT RECORDED")
        self.assertEqual(process_request(json.dumps(request), self.store, TIPOFF).exit_code, 0)
        independent = evaluation_view(self.store, RUN)["process"]["independent_review"]
        self.assertEqual(independent["status"], "REVIEWED_FOR_JOSEPH")
        self.assertEqual(independent["artifact_sha256"], request["initial_artifact_sha256"])
        self.assertEqual(len(independent["receipts"]), 1)
