import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import fifth_pick.approval as approval_module
import fifth_pick.storage as storage_module
import tests.test_finalization as finalization_tests
from fifth_pick.approval import ApprovalError
from fifth_pick.cli import main
from fifth_pick.methodology import CandidateCase
from fifth_pick.storage import RunStore
from fifth_pick.t20_review import review_t20
from tests.m6_support import make_case as make_m6_case
from tests.test_finalization import RUN_ID, make_event_rows, make_t20_case, record_run_slate


class ApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = RunStore(self.temporary.name)

    def create_proposal(self, names: tuple[str, ...] = ("Luka Doncic",)) -> dict[str, Any]:
        record_run_slate(self.temporary.name, RUN_ID, make_event_rows(2))
        prior_cases: tuple[CandidateCase, ...] = tuple(make_m6_case(name=name) for name in names)
        current_cases = tuple(make_t20_case(case) for case in prior_cases)
        for prior, current in zip(prior_cases, current_cases, strict=True):
            review_t20(
                prior,
                current,
                reviewed_at=finalization_tests.TARGET_AT,
                run_id=RUN_ID,
                store=self.store,
            )
        finalization_tests.finalize_slate(
            prior_cases,
            tuple(zip(prior_cases, current_cases, strict=True)),
            run_id=RUN_ID,
            store=self.store,
        )
        return json.loads(
            (self.store.run_directory(RUN_ID) / "final.json").read_text(encoding="utf-8")
        )

    def decide(self, action: str, *responses: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(
                storage_module,
                "APPLICATION_STORAGE_ROOT",
                Path(self.temporary.name),
            ),
            patch("builtins.input", side_effect=(action, *responses)),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = main(["decide", "--run-id", RUN_ID])
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_finalization_alone_does_not_create_approved_state(self) -> None:
        final = self.create_proposal()
        receipts = self.store.read_receipts(RUN_ID)

        self.assertEqual(final["state"], "AWAITING_JOSEPH")
        self.assertEqual(final["approval"]["action"], None)
        self.assertEqual(final["approval"]["official_final"], None)
        self.assertNotIn("JOSEPH_APPROVED", {item["event"] for item in receipts})

    def test_approval_action_cannot_be_supplied_as_a_cli_field(self) -> None:
        self.create_proposal()
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(
                storage_module,
                "APPLICATION_STORAGE_ROOT",
                Path(self.temporary.name),
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = main(["decide", "--run-id", RUN_ID, "--action", "APPROVE"])

        self.assertEqual(exit_code, 2)
        self.assertIn("usage", stderr.getvalue().lower())
        self.assertNotIn(
            "JOSEPH_APPROVED",
            {item["event"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_caller_forged_approved_artifact_fails_closed_without_receipt(self) -> None:
        final = self.create_proposal()
        final["state"] = "APPROVED_BY_JOSEPH"
        final["approval"] = {
            "action": "APPROVE",
            "actor": "Joseph Edafiadhe (Governance Zero)",
            "official_final": final["proposed"],
        }
        final_path = self.store.run_directory(RUN_ID) / "final.json"
        final_path.write_text(json.dumps(final), encoding="utf-8")

        with (
            patch.object(
                storage_module,
                "APPLICATION_STORAGE_ROOT",
                Path(self.temporary.name),
            ),
            patch("builtins.input", side_effect=AssertionError("forged state must not prompt")),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            exit_code = main(["decide", "--run-id", RUN_ID])

        self.assertEqual(exit_code, 1)
        self.assertNotIn(
            "JOSEPH_APPROVED",
            {item["event"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_joseph_approval_uses_interactive_path_and_records_receipt(self) -> None:
        proposed = self.create_proposal(("Luka Doncic", "Derrick White"))

        exit_code, stdout, stderr = self.decide("APPROVE")

        final = json.loads(
            (self.store.run_directory(RUN_ID) / "final.json").read_text(encoding="utf-8")
        )
        receipt = next(
            item for item in self.store.read_receipts(RUN_ID) if item["event"] == "JOSEPH_APPROVED"
        )
        self.assertEqual(exit_code, 0, stderr)
        self.assertIn("Proposed final set", stdout)
        self.assertEqual(final["state"], "APPROVED_BY_JOSEPH")
        self.assertEqual(
            [item["candidate_key"] for item in final["approval"]["official_final"]],
            [item["candidate_key"] for item in proposed["proposed"]],
        )
        self.assertEqual(receipt["result"], "APPROVE")
        reason = receipt["reason"]
        assert isinstance(reason, str)
        self.assertIn("SLATE_VERSION=1", reason)
        self.assertTrue(receipt["timestamp"])
        self.assertTrue(receipt["event_key"])

    def test_retry_reuses_the_persisted_decision_receipt_timestamp_through_cli(self) -> None:
        self.create_proposal()
        write_json = approval_module._write_json

        def fail_final_write(path, record) -> None:
            if path.name == "final.json":
                raise ApprovalError("injected final artifact failure")
            write_json(path, record)

        with patch.object(approval_module, "_write_json", side_effect=fail_final_write):
            first_exit, _stdout, _stderr = self.decide("APPROVE")
        self.assertEqual(first_exit, 1)

        decision_receipt = next(
            item for item in self.store.read_receipts(RUN_ID) if item["event"] == "JOSEPH_APPROVED"
        )
        retry_exit, _stdout, stderr = self.decide("APPROVE")
        self.assertEqual(retry_exit, 0, stderr)
        final = json.loads(
            (self.store.run_directory(RUN_ID) / "final.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            final["approval"]["decision_recorded_at"],
            decision_receipt["timestamp"],
        )

    def test_decision_action_must_match_the_exact_uppercase_vocabulary(self) -> None:
        proposed = self.create_proposal()

        exit_code, _stdout, _stderr = self.decide("approve")

        final = json.loads(
            (self.store.run_directory(RUN_ID) / "final.json").read_text(encoding="utf-8")
        )
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(final["state"], "AWAITING_JOSEPH")
        self.assertEqual(final["proposed"], proposed["proposed"])
        self.assertNotIn(
            "JOSEPH_APPROVED", {item["event"] for item in self.store.read_receipts(RUN_ID)}
        )

    def test_no_entry_modify_remains_decidable_and_receipts_stay_consistent(self) -> None:
        record_run_slate(self.temporary.name, RUN_ID, ())
        finalization_tests.finalize_slate((), (), run_id=RUN_ID, store=self.store)

        modify_exit, _stdout, modify_stderr = self.decide("MODIFY", "")

        modified = json.loads(
            (self.store.run_directory(RUN_ID) / "final.json").read_text(encoding="utf-8")
        )
        receipts = self.store.read_receipts(RUN_ID)
        self.assertEqual(modify_exit, 0, modify_stderr)
        self.assertEqual(modified["state"], "AWAITING_JOSEPH")
        self.assertEqual(modified["slate_version"], 2)
        self.assertEqual(modified["recommendation"], "NO ENTRY RECOMMENDED TODAY.")
        self.assertEqual(modified["proposed"], [])
        self.assertTrue(
            any(
                item["event"] == "FINAL_SELECTION_PROPOSED"
                and item["result"] == "NO_ENTRY"
                and item["reason"] == "SLATE_VERSION=2"
                for item in receipts
            )
        )

        approve_exit, _stdout, approve_stderr = self.decide("APPROVE")
        approved = json.loads(
            (self.store.run_directory(RUN_ID) / "final.json").read_text(encoding="utf-8")
        )
        self.assertEqual(approve_exit, 0, approve_stderr)
        self.assertEqual(approved["state"], "APPROVED_BY_JOSEPH")
        self.assertEqual(approved["approval"]["official_final"], [])

    def test_decision_writer_is_not_a_public_api_or_alternate_cli_command(self) -> None:
        self.assertFalse(hasattr(approval_module, "apply_joseph_decision"))

        for command in ("approve", "reject", "modify", "finalize"):
            with self.subTest(command=command), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([command, "--run-id", RUN_ID]), 2)

    def test_joseph_rejection_is_terminal_and_does_not_replace_candidates(self) -> None:
        proposed = self.create_proposal(("Luka Doncic", "Jayson Tatum"))

        exit_code, _stdout, stderr = self.decide("REJECT", "No approved set today.")

        final = json.loads(
            (self.store.run_directory(RUN_ID) / "final.json").read_text(encoding="utf-8")
        )
        self.assertEqual(exit_code, 0, stderr)
        self.assertEqual(final["state"], "REJECTED_BY_JOSEPH")
        self.assertEqual(final["approval"]["official_final"], [])
        self.assertEqual(final["proposed"], proposed["proposed"])
        self.assertEqual(
            {item["event"] for item in self.store.read_receipts(RUN_ID)}.intersection(
                {"JOSEPH_REJECTED", "FINAL_SELECTION_PROPOSED"}
            ),
            {"JOSEPH_REJECTED", "FINAL_SELECTION_PROPOSED"},
        )

        before = (self.store.run_directory(RUN_ID) / "final.json").read_bytes()
        finalization_tests.finalize_slate((), (), run_id=RUN_ID, store=self.store)
        self.assertEqual((self.store.run_directory(RUN_ID) / "final.json").read_bytes(), before)

    def test_modify_records_human_subset_but_still_requires_approval(self) -> None:
        proposed = self.create_proposal(("Luka Doncic", "Derrick White", "Payton Pritchard"))
        kept_key = proposed["proposed"][1]["candidate_key"]

        exit_code, _stdout, stderr = self.decide("MODIFY", kept_key)

        modified = json.loads(
            (self.store.run_directory(RUN_ID) / "final.json").read_text(encoding="utf-8")
        )
        self.assertEqual(exit_code, 0, stderr)
        self.assertEqual(modified["state"], "AWAITING_JOSEPH")
        self.assertEqual(modified["slate_version"], 2)
        self.assertEqual(modified["approval"]["action"], "MODIFY")
        self.assertEqual(
            [item["candidate_key"] for item in modified["proposed"]],
            [kept_key],
        )
        self.assertIsNone(modified["approval"]["official_final"])
        modify_receipt = next(
            item for item in self.store.read_receipts(RUN_ID) if item["event"] == "JOSEPH_MODIFIED"
        )
        reason = modify_receipt["reason"]
        assert isinstance(reason, str)
        self.assertIn("SLATE_VERSION=1", reason)

    def test_decision_cannot_add_a_candidate_not_in_the_proposal(self) -> None:
        proposed = self.create_proposal(("Luka Doncic", "Derrick White"))
        unauthorized_key = "f" * 64
        self.assertNotIn(unauthorized_key, {item["candidate_key"] for item in proposed["proposed"]})

        exit_code, _stdout, _stderr = self.decide("MODIFY", unauthorized_key)

        final = json.loads(
            (self.store.run_directory(RUN_ID) / "final.json").read_text(encoding="utf-8")
        )
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(final["state"], "AWAITING_JOSEPH")
        self.assertEqual(final["proposed"], proposed["proposed"])
        self.assertNotIn(
            "JOSEPH_MODIFIED", {item["event"] for item in self.store.read_receipts(RUN_ID)}
        )

    def test_login_submission_and_wager_commands_do_not_exist(self) -> None:
        for command in ("login", "submit", "wager", "money"):
            with self.subTest(command=command), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([command]), 2)


if __name__ == "__main__":
    unittest.main()
