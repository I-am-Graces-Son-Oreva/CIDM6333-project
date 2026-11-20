import contextlib
import hashlib
import io
import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import fifth_pick.results as results_module
import fifth_pick.storage as storage_module
import tests.test_finalization as finalization_tests
from fifth_pick.cli import main
from fifth_pick.evidence import EvidenceEffect
from fifth_pick.finalization import _append_proposal_receipt
from fifth_pick.methodology import Confidence
from fifth_pick.models import Provenance, ReasonCode, Result, ResultStatus
from fifth_pick.storage import RunStore
from fifth_pick.t20_review import review_t20
from tests.m6_support import make_case

NOW = datetime(2026, 11, 17, 18, 0, tzinfo=UTC)
RUN_ID = finalization_tests.RUN_ID
TARGET_AT = finalization_tests.TARGET_AT


class ResultWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = RunStore(self.temporary.name)
        self.storage_patch = patch.object(
            storage_module,
            "APPLICATION_STORAGE_ROOT",
            Path(self.temporary.name),
        )
        self.storage_patch.start()
        self.addCleanup(self.storage_patch.stop)

    def create_run(
        self,
        names: tuple[str, ...] = ("Luka Doncic",),
        *,
        approve: bool = True,
        changed_at_t20: bool = False,
    ) -> dict[str, Any]:
        finalization_tests.record_run_slate(
            self.temporary.name,
            RUN_ID,
            finalization_tests.make_event_rows(2),
        )
        prior_cases = tuple(finalization_tests.make_candidate(name) for name in names)
        current_cases = tuple(finalization_tests.make_t20_case(case) for case in prior_cases)
        if changed_at_t20:
            current = finalization_tests.make_t20_case(make_case(projections=(32.5, 33.0, 36.0)))
            assert current.judgment is not None
            current_cases = (
                replace(
                    current,
                    evidence=tuple(
                        replace(item, effect=EvidenceEffect.CONCERN)
                        if item.evidence_id == "role"
                        else item
                        for item in current.evidence
                    ),
                    judgment=replace(
                        current.judgment,
                        confidence=Confidence.MEDIUM,
                        supporting_evidence_ids=("last8",),
                        meaningful_risk_ids=("role", "blowout-risk"),
                        rationale="T-20 role evidence is now concerning.",
                    ),
                ),
            )
        for prior, current in zip(prior_cases, current_cases, strict=True):
            review_t20(
                prior,
                current,
                reviewed_at=TARGET_AT,
                run_id=RUN_ID,
                store=self.store,
            )
        finalization_tests.finalize_slate(
            prior_cases,
            tuple(zip(prior_cases, current_cases, strict=True)),
            run_id=RUN_ID,
            store=self.store,
        )
        if approve:
            exit_code, _stdout, stderr = self.decide("APPROVE")
            self.assertEqual(exit_code, 0, stderr)
        return json.loads(
            (self.store.run_directory(RUN_ID) / "final.json").read_text(encoding="utf-8")
        )

    def decide(self, action: str, *responses: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("builtins.input", side_effect=(action, *responses)),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = main(["decide", "--run-id", RUN_ID])
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def result(
        self,
        selection_id: str,
        outcome: ResultStatus,
        *,
        source: str = "synthetic-fixture",
        access_method: str = "synthetic-fixture",
        include_provenance: bool = True,
        subject: str | None = None,
        recorded_at: datetime = NOW,
    ) -> Result:
        provenance = None
        if include_provenance:
            excerpt = self.evidence_excerpt(selection_id, outcome)
            provenance = Provenance(
                source=source,
                retrieved_at=recorded_at,
                source_timestamp=recorded_at - timedelta(minutes=1),
                access_method=access_method,
                reference=(
                    f"fixture:result/{selection_id}"
                    if access_method == "synthetic-fixture"
                    else f"platform-settlement:player/{selection_id}"
                ),
                payload_hash=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            )
        return Result(
            outcome=outcome,
            subject=selection_id if subject is None else subject,
            source=source,
            recorded_at=recorded_at,
            reason=(
                ReasonCode.RESULT_UNAVAILABLE
                if outcome is ResultStatus.RESULT_UNAVAILABLE
                else None
            ),
            provenance=provenance,
        )

    def evidence_excerpt(self, selection_id: str, outcome: ResultStatus) -> str:
        return f"Settlement excerpt for approved selection {selection_id}: {outcome.value}"

    def record(self, selection_id: str, result: Result) -> Path:
        excerpt = (
            self.evidence_excerpt(selection_id, result.outcome)
            if result.provenance is not None
            else None
        )
        confirmation = None
        if excerpt is not None:
            confirmation = (
                "SETTLEMENT_CONFIRMED"
                if result.outcome is not ResultStatus.RESULT_UNAVAILABLE
                else "LOOKUP_ATTEMPT_CONFIRMED"
            )
        return results_module.record_result(
            self.store,
            RUN_ID,
            selection_id,
            result,
            evidence_excerpt=excerpt,
            evidence_confirmation=confirmation,
        )

    def result_artifact(self) -> dict[str, Any]:
        return json.loads(
            (self.store.run_directory(RUN_ID) / "results.json").read_text(encoding="utf-8")
        )

    def test_changed_t20_values_are_displayed_approved_and_settled(self) -> None:
        final = self.create_run(approve=False, changed_at_t20=True)
        proposed = final["proposed"][0]
        audit_path = self.store.run_directory(RUN_ID) / results_module.AUDIT_FILENAME
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        review = audit["m7_reviews"][0]
        self.assertEqual(review["conclusion"], "DOWNGRADED")
        self.assertEqual(review["previous_audit"]["candidate"]["projection"], 33.5)
        self.assertEqual(review["previous_audit"]["confidence"], "HIGH")
        ranked = audit["m6_ranking"]["ranked"][0]
        self.assertEqual(proposed["rank"], ranked["rank"])
        self.assertEqual(proposed["reason"], ranked["reason"])
        self.assertEqual(
            ranked["audit"]["methodology_rationale"],
            review["previous_audit"]["methodology_rationale"],
        )
        self.assertEqual(proposed["projection"], 36.0)
        self.assertEqual(proposed["confidence"], "MEDIUM")
        self.assertEqual(proposed["t20_status"], "DOWNGRADED")
        self.assertEqual(proposed["t20_event_key"], review["event_key"])

        exit_code, stdout, stderr = self.decide("APPROVE")
        self.assertEqual(exit_code, 0, stderr)
        for value in ("36.0", "MEDIUM", "DOWNGRADED", "T-20 role evidence is now concerning."):
            self.assertIn(value, stdout)
        self.assertIn("Synthetic fixture evidence role.", proposed["material_risks"])
        for risk in proposed["material_risks"]:
            self.assertIn(risk, stdout)
        selection_id = proposed["candidate_key"]
        self.record(selection_id, self.result(selection_id, ResultStatus.HIT))
        result = self.result_artifact()["results"][0]
        self.assertEqual(result["selection"], proposed)
        self.assertEqual(result["t20_review_event_key"], review["event_key"])
        self.assertEqual(result["t20_projection"], 36.0)

    def test_pending_decision_refuses_mismatched_t20_receipt(self) -> None:
        self.create_run(approve=False)
        receipts_path = self.store.receipts_path(RUN_ID)
        receipts = self.store.read_receipts(RUN_ID)
        next(item for item in receipts if item["event"] == "T20_REVIEW")["reason"] = "MISMATCH"
        receipts_path.write_text(
            "".join(json.dumps(item) + "\n" for item in receipts), encoding="utf-8"
        )
        run_dir = self.store.run_directory(RUN_ID)
        before = {path: path.read_bytes() for path in run_dir.iterdir() if path.is_file()}

        exit_code, _stdout, stderr = self.decide("APPROVE")

        self.assertNotEqual(exit_code, 0)
        self.assertIn("recreate", stderr)
        self.assertEqual(
            {path: path.read_bytes() for path in run_dir.iterdir() if path.is_file()}, before
        )

    def test_pending_stale_projection_is_blocked_even_with_matching_proposal_receipt(self) -> None:
        final = self.create_run(approve=False, changed_at_t20=True)
        path = self.store.run_directory(RUN_ID) / "final.json"
        final["proposed"][0].update(projection=33.5, confidence="HIGH")
        _append_proposal_receipt(self.store, final, result="AWAITING_JOSEPH")
        path.write_text(json.dumps(final), encoding="utf-8")
        before = path.read_bytes(), self.store.read_receipts(RUN_ID)

        exit_code, stdout, stderr = self.decide("APPROVE")

        self.assertNotEqual(exit_code, 0)
        self.assertNotIn("Proposed final set", stdout)
        self.assertIn("recreate", stderr)
        self.assertEqual((path.read_bytes(), self.store.read_receipts(RUN_ID)), before)

    def test_substituted_proposal_receipt_cannot_rebind_approval(self) -> None:
        final = self.create_run(changed_at_t20=True)
        path = self.store.run_directory(RUN_ID) / "final.json"
        proposed = final["proposed"][0]
        selection_id = proposed["candidate_key"]
        proposed["confidence"] = "HIGH"
        final["approval"]["official_final"] = final["proposed"]
        _append_proposal_receipt(self.store, final, result="AWAITING_JOSEPH")
        path.write_text(json.dumps(final), encoding="utf-8")
        receipts_before = self.store.read_receipts(RUN_ID)

        with self.assertRaisesRegex(results_module.ResultError, "receipt-verified APPROVE"):
            self.record(selection_id, self.result(selection_id, ResultStatus.HIT))

        self.assertEqual(self.store.read_receipts(RUN_ID), receipts_before)

    def test_hit_and_miss_require_trustworthy_result(self) -> None:
        final = self.create_run(("Luka Doncic", "Derrick White"))
        approved = final["approval"]["official_final"]
        self.assertEqual(len(approved), 2)

        for item, outcome in zip(approved, (ResultStatus.HIT, ResultStatus.MISS), strict=True):
            with self.subTest(outcome=outcome):
                missing_provenance = self.result(
                    item["candidate_key"],
                    outcome,
                    include_provenance=False,
                )
                with self.assertRaises(results_module.ResultError):
                    self.record(item["candidate_key"], missing_provenance)

                self.record(item["candidate_key"], self.result(item["candidate_key"], outcome))

        outcomes = {
            item["selection_id"]: item["result"]["outcome"]
            for item in self.result_artifact()["results"]
        }
        self.assertEqual(
            outcomes,
            {
                approved[0]["candidate_key"]: "HIT",
                approved[1]["candidate_key"]: "MISS",
            },
        )

    def test_dnp_is_not_miss(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]

        self.record(selection_id, self.result(selection_id, ResultStatus.DNP))

        record = self.result_artifact()["results"][0]
        self.assertEqual(record["result"]["outcome"], "DNP")

    def test_void_is_push_or_void(self) -> None:
        final = self.create_run(("Luka Doncic", "Derrick White"))
        approved = final["approval"]["official_final"]

        self.record(
            approved[0]["candidate_key"],
            self.result(approved[0]["candidate_key"], ResultStatus.VOID),
        )
        self.record(
            approved[1]["candidate_key"],
            self.result(approved[1]["candidate_key"], ResultStatus.PUSH),
        )

        outcomes = {item["result"]["outcome"] for item in self.result_artifact()["results"]}
        self.assertEqual(outcomes, {"VOID", "PUSH"})

    def test_team_score_is_not_player_result(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        team_result = self.result(
            selection_id,
            ResultStatus.HIT,
            source="the-odds-api",
            access_method="manual-entry",
        )
        assert team_result.provenance is not None
        team_result = replace(
            team_result,
            provenance=replace(
                team_result.provenance,
                reference=f"https://api.the-odds-api.com/v4/sports/nba/scores/{selection_id}",
            ),
        )

        with self.assertRaises(results_module.ResultError):
            self.record(selection_id, team_result)

        self.assertFalse((self.store.run_directory(RUN_ID) / "results.json").exists())

    def test_result_provenance_reference_must_bind_the_exact_selection(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        result = self.result(
            selection_id,
            ResultStatus.HIT,
            source="platform-settled",
            access_method="manual-entry",
        )
        assert result.provenance is not None
        unrelated = replace(
            result,
            provenance=replace(
                result.provenance,
                reference="platform-settlement:player/unrelated-selection",
            ),
        )

        with self.assertRaises(results_module.ResultError):
            self.record(selection_id, unrelated)

        self.assertFalse((self.store.run_directory(RUN_ID) / "results.json").exists())

    def test_manual_result_requires_provenance(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        manual_result = self.result(
            selection_id,
            ResultStatus.HIT,
            source="manual-entry",
            access_method="manual-entry",
            include_provenance=False,
        )

        with self.assertRaises(results_module.ResultError):
            self.record(selection_id, manual_result)

        self.assertFalse((self.store.run_directory(RUN_ID) / "results.json").exists())

    def test_missing_result_is_unavailable(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        unavailable = self.result(
            selection_id,
            ResultStatus.RESULT_UNAVAILABLE,
            source="manual-entry",
            include_provenance=False,
        )

        self.record(selection_id, unavailable)

        record = self.result_artifact()["results"][0]
        self.assertEqual(record["result"]["outcome"], "RESULT UNAVAILABLE")
        self.assertEqual(record["result"]["reason"], "RESULT UNAVAILABLE")
        self.assertIsNone(record["evidence_excerpt"])
        self.assertIsNone(record["evidence_confirmation"])

    def test_determinate_result_requires_matching_excerpt_and_confirmation(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        result = self.result(selection_id, ResultStatus.HIT)
        excerpt = self.evidence_excerpt(selection_id, ResultStatus.HIT)
        cases = (
            (None, "SETTLEMENT_CONFIRMED"),
            (excerpt + " changed", "SETTLEMENT_CONFIRMED"),
            (excerpt, None),
            (excerpt, "LOOKUP_ATTEMPT_CONFIRMED"),
        )

        for evidence_excerpt, confirmation in cases:
            with (
                self.subTest(excerpt=evidence_excerpt, confirmation=confirmation),
                self.assertRaises(results_module.ResultError),
            ):
                results_module.record_result(
                    self.store,
                    RUN_ID,
                    selection_id,
                    result,
                    evidence_excerpt=evidence_excerpt,
                    evidence_confirmation=confirmation,
                )

        self.assertFalse((self.store.run_directory(RUN_ID) / "results.json").exists())

    def test_result_artifact_persists_excerpt_hash_and_confirmation(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        result = self.result(selection_id, ResultStatus.HIT)
        excerpt = self.evidence_excerpt(selection_id, ResultStatus.HIT)

        self.record(selection_id, result)

        entry = self.result_artifact()["results"][0]
        self.assertEqual(entry["evidence_excerpt"], excerpt)
        self.assertEqual(
            entry["result"]["provenance"]["payload_hash"],
            hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(entry["evidence_confirmation"], "SETTLEMENT_CONFIRMED")
        result_receipt = next(
            item for item in self.store.read_receipts(RUN_ID) if item["event"] == "RESULT_RECORDED"
        )
        receipt_reason = result_receipt["reason"]
        self.assertIsInstance(receipt_reason, str)
        assert isinstance(receipt_reason, str)
        self.assertIn(
            f"EVIDENCE_SHA256={hashlib.sha256(excerpt.encode('utf-8')).hexdigest()}",
            receipt_reason,
        )
        self.assertIn("EVIDENCE_CONFIRMATION=SETTLEMENT_CONFIRMED", receipt_reason)

    def test_tampered_or_missing_evidence_fails_closed_on_retry(self) -> None:
        final = self.create_run(("Luka Doncic", "Derrick White"))
        approved = final["approval"]["official_final"]
        first_key = approved[0]["candidate_key"]
        second_key = approved[1]["candidate_key"]
        self.record(first_key, self.result(first_key, ResultStatus.HIT))
        results_path = self.store.run_directory(RUN_ID) / "results.json"
        original = json.loads(results_path.read_text(encoding="utf-8"))
        receipts_before = self.store.read_receipts(RUN_ID)

        for evidence_excerpt in ("tampered evidence", None):
            with self.subTest(evidence_excerpt=evidence_excerpt):
                artifact = json.loads(json.dumps(original))
                if evidence_excerpt is None:
                    artifact["results"][0].pop("evidence_excerpt")
                else:
                    artifact["results"][0]["evidence_excerpt"] = evidence_excerpt
                results_path.write_text(json.dumps(artifact), encoding="utf-8")

                with self.assertRaises(results_module.ResultError):
                    self.record(second_key, self.result(second_key, ResultStatus.MISS))

                self.assertEqual(self.store.read_receipts(RUN_ID), receipts_before)

    def test_grading_uses_approved_selection_state(self) -> None:
        final = self.create_run(approve=False)
        selection_id = final["proposed"][0]["candidate_key"]

        with self.assertRaises(results_module.ResultError):
            self.record(selection_id, self.result(selection_id, ResultStatus.HIT))

        self.assertFalse((self.store.run_directory(RUN_ID) / "results.json").exists())

    def test_result_rejects_rejected_approval_state(self) -> None:
        final = self.create_run(approve=False)
        selection_id = final["proposed"][0]["candidate_key"]
        reject_exit, _stdout, reject_stderr = self.decide("REJECT", "No approved set.")
        self.assertEqual(reject_exit, 0, reject_stderr)

        with self.assertRaises(results_module.ResultError):
            self.record(selection_id, self.result(selection_id, ResultStatus.HIT))

    def test_result_rejects_modified_but_unapproved_state(self) -> None:
        final = self.create_run(("Luka Doncic", "Derrick White"), approve=False)
        selection_id = final["proposed"][0]["candidate_key"]
        modify_exit, _stdout, modify_stderr = self.decide("MODIFY", selection_id)
        self.assertEqual(modify_exit, 0, modify_stderr)

        with self.assertRaises(results_module.ResultError):
            self.record(selection_id, self.result(selection_id, ResultStatus.HIT))

    def test_result_rejects_wrong_run_id(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        result = self.result(selection_id, ResultStatus.HIT)

        with self.assertRaises(results_module.ResultError):
            results_module.record_result(
                self.store,
                "different-run",
                selection_id,
                result,
                evidence_excerpt=self.evidence_excerpt(selection_id, ResultStatus.HIT),
                evidence_confirmation="SETTLEMENT_CONFIRMED",
            )

    def test_result_must_target_a_candidate_in_official_final(self) -> None:
        self.create_run()
        outside_key = "f" * 64

        with self.assertRaises(results_module.ResultError):
            self.record(outside_key, self.result(outside_key, ResultStatus.HIT))

        self.assertFalse((self.store.run_directory(RUN_ID) / "results.json").exists())

    def test_fixture_result_is_marked_as_fixture(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        fixture = self.result(
            selection_id,
            ResultStatus.HIT,
            source="synthetic-fixture",
            access_method="synthetic-fixture",
        )

        self.record(selection_id, fixture)

        record = self.result_artifact()["results"][0]
        self.assertTrue(record["fixture"])
        self.assertEqual(record["result"]["provenance"]["access_method"], "synthetic-fixture")

    def test_result_receipt_is_idempotent(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        result = self.result(selection_id, ResultStatus.HIT)

        self.record(selection_id, result)
        first_artifact = (self.store.run_directory(RUN_ID) / "results.json").read_bytes()
        self.record(selection_id, result)

        receipts = tuple(
            item for item in self.store.read_receipts(RUN_ID) if item["event"] == "RESULT_RECORDED"
        )
        self.assertEqual(
            (self.store.run_directory(RUN_ID) / "results.json").read_bytes(), first_artifact
        )
        self.assertEqual(len(receipts), 1)

    def test_conflicting_result_fails_closed(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        self.record(selection_id, self.result(selection_id, ResultStatus.HIT))
        first_artifact = (self.store.run_directory(RUN_ID) / "results.json").read_bytes()

        with self.assertRaises(results_module.ResultError):
            self.record(selection_id, self.result(selection_id, ResultStatus.MISS))

        self.assertEqual(
            (self.store.run_directory(RUN_ID) / "results.json").read_bytes(), first_artifact
        )
        self.assertEqual(
            self.result_artifact()["results"][0]["result"]["outcome"],
            "HIT",
        )

    def test_existing_result_row_missing_receipt_event_key_fails_closed(self) -> None:
        final = self.create_run(("Luka Doncic", "Derrick White"))
        approved = final["approval"]["official_final"]
        self.record(
            approved[0]["candidate_key"],
            self.result(approved[0]["candidate_key"], ResultStatus.HIT),
        )
        result_path = self.store.run_directory(RUN_ID) / "results.json"
        artifact = json.loads(result_path.read_text(encoding="utf-8"))
        artifact["results"][0].pop("result_receipt_event_key")
        result_path.write_text(json.dumps(artifact), encoding="utf-8")
        receipts_before = self.store.read_receipts(RUN_ID)

        with self.assertRaises(results_module.ResultError):
            self.record(
                approved[1]["candidate_key"],
                self.result(approved[1]["candidate_key"], ResultStatus.MISS),
            )

        self.assertEqual(self.store.read_receipts(RUN_ID), receipts_before)

    def test_existing_result_row_without_receipt_fails_closed(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        result = self.result(selection_id, ResultStatus.HIT)
        self.record(selection_id, result)
        receipts = tuple(
            item for item in self.store.read_receipts(RUN_ID) if item["event"] != "RESULT_RECORDED"
        )
        self.store.receipts_path(RUN_ID).write_text(
            "".join(
                json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in receipts
            ),
            encoding="utf-8",
        )
        receipts_before = self.store.read_receipts(RUN_ID)

        with self.assertRaises(results_module.ResultError):
            self.record(selection_id, result)

        self.assertEqual(self.store.read_receipts(RUN_ID), receipts_before)

    def test_malformed_existing_result_row_fails_closed(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        results_path = self.store.run_directory(RUN_ID) / "results.json"
        results_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "run_id": RUN_ID,
                    "results": [{"selection_id": selection_id}],
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(results_module.ResultError):
            self.record(selection_id, self.result(selection_id, ResultStatus.HIT))

    def test_result_receipt_binds_the_persisted_approved_selection_snapshot(self) -> None:
        final = self.create_run(("Luka Doncic", "Derrick White"))
        approved = final["approval"]["official_final"]
        first_key = approved[0]["candidate_key"]
        second_key = approved[1]["candidate_key"]
        self.record(first_key, self.result(first_key, ResultStatus.HIT))

        result_path = self.store.run_directory(RUN_ID) / "results.json"
        artifact = json.loads(result_path.read_text(encoding="utf-8"))
        artifact["results"][0]["selection"]["player"] = "Jayson Tatum"
        result_path.write_text(json.dumps(artifact), encoding="utf-8")
        receipts_before = self.store.read_receipts(RUN_ID)

        with self.assertRaises(results_module.ResultError):
            self.record(second_key, self.result(second_key, ResultStatus.MISS))

        self.assertEqual(self.store.read_receipts(RUN_ID), receipts_before)

    def test_existing_result_rejects_tampered_m7_review_content(self) -> None:
        final = self.create_run(("Luka Doncic", "Derrick White"))
        approved = final["approval"]["official_final"]
        first_key = approved[0]["candidate_key"]
        second_key = approved[1]["candidate_key"]
        self.record(first_key, self.result(first_key, ResultStatus.HIT))

        audit_path = self.store.run_directory(RUN_ID) / results_module.AUDIT_FILENAME
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        review = next(item for item in audit["m7_reviews"] if item["candidate_key"] == first_key)
        review["audit_reasons"].append("TAMPERED")
        audit_path.write_text(json.dumps(audit), encoding="utf-8")
        receipts_before = self.store.read_receipts(RUN_ID)

        with self.assertRaises(results_module.ResultError):
            self.record(second_key, self.result(second_key, ResultStatus.MISS))

        self.assertEqual(self.store.read_receipts(RUN_ID), receipts_before)

    def test_existing_result_rejects_tampered_m7_receipt(self) -> None:
        final = self.create_run(("Luka Doncic", "Derrick White"))
        approved = final["approval"]["official_final"]
        first_key = approved[0]["candidate_key"]
        second_key = approved[1]["candidate_key"]
        self.record(first_key, self.result(first_key, ResultStatus.HIT))
        result_record = self.result_artifact()["results"][0]
        review_key = result_record["t20_review_event_key"]

        receipts_path = self.store.receipts_path(RUN_ID)
        receipts = [
            json.loads(line) for line in receipts_path.read_text(encoding="utf-8").splitlines()
        ]
        review_receipt = next(item for item in receipts if item["event_key"] == review_key)
        review_receipt["reason"] = "TAMPERED"
        receipts_path.write_text(
            "".join(
                json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in receipts
            ),
            encoding="utf-8",
        )
        receipts_before = self.store.read_receipts(RUN_ID)

        with self.assertRaises(results_module.ResultError):
            self.record(second_key, self.result(second_key, ResultStatus.MISS))

        self.assertEqual(self.store.read_receipts(RUN_ID), receipts_before)

    def test_existing_result_rejects_tampered_t20_projection(self) -> None:
        final = self.create_run(("Luka Doncic", "Derrick White"))
        approved = final["approval"]["official_final"]
        first_key = approved[0]["candidate_key"]
        second_key = approved[1]["candidate_key"]
        self.record(first_key, self.result(first_key, ResultStatus.HIT))

        results_path = self.store.run_directory(RUN_ID) / "results.json"
        artifact = json.loads(results_path.read_text(encoding="utf-8"))
        artifact["results"][0]["t20_projection"] += 1
        results_path.write_text(json.dumps(artifact), encoding="utf-8")
        receipts_before = self.store.read_receipts(RUN_ID)

        with self.assertRaises(results_module.ResultError):
            self.record(second_key, self.result(second_key, ResultStatus.MISS))

        self.assertEqual(self.store.read_receipts(RUN_ID), receipts_before)

    def test_retry_rejects_naive_or_invalid_persisted_receipt_timestamp(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        result = self.result(
            selection_id,
            ResultStatus.RESULT_UNAVAILABLE,
            source="manual-entry",
            access_method="manual-entry",
            include_provenance=False,
        )

        def fail_artifact_write(path, record) -> None:
            raise results_module.ResultError("injected results artifact failure")

        with (
            patch.object(results_module, "_write_results", side_effect=fail_artifact_write),
            self.assertRaises(results_module.ResultError),
        ):
            self.record(selection_id, result)

        receipts_path = self.store.receipts_path(RUN_ID)
        for timestamp in ("2026-11-17T18:00:00", "not-a-timestamp"):
            with self.subTest(timestamp=timestamp):
                receipts = [
                    json.loads(line)
                    for line in receipts_path.read_text(encoding="utf-8").splitlines()
                ]
                result_receipt = next(
                    item for item in receipts if item["event"] == "RESULT_RECORDED"
                )
                result_receipt["timestamp"] = timestamp
                receipts_path.write_text(
                    "".join(
                        json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n"
                        for item in receipts
                    ),
                    encoding="utf-8",
                )

                with self.assertRaises(results_module.ResultError):
                    self.record(selection_id, result)

                self.assertFalse((self.store.run_directory(RUN_ID) / "results.json").exists())

    def test_retry_reuses_persisted_result_receipt_timestamp(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        first_result = self.result(selection_id, ResultStatus.HIT)

        def fail_artifact_write(path, record) -> None:
            raise results_module.ResultError("injected results artifact failure")

        with (
            patch.object(results_module, "_write_results", side_effect=fail_artifact_write),
            self.assertRaises(results_module.ResultError),
        ):
            self.record(selection_id, first_result)

        result_receipt = next(
            item for item in self.store.read_receipts(RUN_ID) if item["event"] == "RESULT_RECORDED"
        )
        assert first_result.provenance is not None
        retry_at = first_result.recorded_at + timedelta(seconds=2)
        retry_result = replace(
            first_result,
            recorded_at=retry_at,
            provenance=replace(first_result.provenance, retrieved_at=retry_at),
        )
        self.record(selection_id, retry_result)

        record = self.result_artifact()["results"][0]
        self.assertEqual(record["result"]["recorded_at"], result_receipt["timestamp"])
        self.assertEqual(
            record["result"]["provenance"]["retrieved_at"],
            result_receipt["timestamp"],
        )

    def test_result_record_cli_uses_the_existing_executable(self) -> None:
        final = self.create_run()
        selection = final["approval"]["official_final"][0]
        selection_id = selection["candidate_key"]
        source_timestamp = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        excerpt = (
            f"{selection['player']} | {selection['platform']} | {selection['category']} "
            f"{selection['direction']} {selection['projection']} | HIT"
        )
        responses = (
            "HIT",
            "manual-entry",
            source_timestamp,
            f"platform-settlement:player/{selection_id}",
            excerpt,
            "YES",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("builtins.input", side_effect=responses) as mocked_input,
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = main(["result", "record", "--run-id", RUN_ID, "--selection", selection_id])

        self.assertEqual(exit_code, 0, stderr.getvalue())
        record = self.result_artifact()["results"][0]
        self.assertIn(selection_id, stdout.getvalue())
        self.assertEqual(record["result"]["outcome"], "HIT")
        self.assertEqual(record["result"]["provenance"]["access_method"], "manual-entry")
        self.assertEqual(record["evidence_excerpt"], excerpt)
        self.assertEqual(
            record["result"]["provenance"]["payload_hash"],
            hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(record["evidence_confirmation"], "SETTLEMENT_CONFIRMED")
        confirmation_prompt = mocked_input.call_args_list[-1].args[0]
        for selection_detail in (
            selection["player"],
            selection["platform"],
            selection["category"],
            selection["direction"],
            str(selection["projection"]),
            selection["event"],
            "HIT",
        ):
            self.assertIn(str(selection_detail), confirmation_prompt)
        self.assertIn("excerpt itself", confirmation_prompt.lower())
        self.assertIn("does not independently authenticate the source", confirmation_prompt.lower())

    def test_result_unavailable_cli_retains_available_lookup_provenance(self) -> None:
        final = self.create_run()
        selection_id = final["approval"]["official_final"][0]["candidate_key"]
        source_timestamp = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        excerpt = (
            f"Lookup attempt for approved player selection {selection_id}: no settlement found"
        )
        responses = (
            "RESULT UNAVAILABLE",
            "manual-entry",
            "YES",
            source_timestamp,
            f"settlement-check:player/{selection_id}",
            excerpt,
            "YES",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("builtins.input", side_effect=responses) as mocked_input,
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = main(["result", "record", "--run-id", RUN_ID, "--selection", selection_id])

        record = self.result_artifact()["results"][0]
        self.assertEqual(exit_code, 0, stderr.getvalue())
        self.assertEqual(record["result"]["outcome"], "RESULT UNAVAILABLE")
        self.assertEqual(record["result"]["reason"], "RESULT UNAVAILABLE")
        self.assertEqual(
            record["result"]["provenance"]["reference"],
            f"settlement-check:player/{selection_id}",
        )
        self.assertEqual(record["evidence_excerpt"], excerpt)
        self.assertEqual(
            record["result"]["provenance"]["payload_hash"],
            hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(record["evidence_confirmation"], "LOOKUP_ATTEMPT_CONFIRMED")
        lookup_prompt = mocked_input.call_args_list[-1].args[0]
        for selection_detail in (
            final["approval"]["official_final"][0]["player"],
            final["approval"]["official_final"][0]["platform"],
            final["approval"]["official_final"][0]["category"],
            final["approval"]["official_final"][0]["direction"],
            str(final["approval"]["official_final"][0]["projection"]),
            final["approval"]["official_final"][0]["event"],
        ):
            self.assertIn(str(selection_detail), lookup_prompt)
        self.assertIn("does not establish a settlement outcome", lookup_prompt.lower())

    def test_cli_unconfirmed_settlement_remains_unavailable(self) -> None:
        final = self.create_run()
        selection = final["approval"]["official_final"][0]
        selection_id = selection["candidate_key"]
        source_timestamp = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        excerpt = "Settlement excerpt does not match the approved selection"
        responses = (
            "HIT",
            "manual-entry",
            source_timestamp,
            f"platform-settlement:player/{selection_id}",
            excerpt,
            "NO",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("builtins.input", side_effect=responses) as mocked_input,
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = main(["result", "record", "--run-id", RUN_ID, "--selection", selection_id])

        entry = self.result_artifact()["results"][0]
        self.assertEqual(exit_code, 0, stderr.getvalue())
        self.assertIn("RESULT UNAVAILABLE", stdout.getvalue())
        self.assertEqual(entry["result"]["outcome"], "RESULT UNAVAILABLE")
        self.assertIsNone(entry["evidence_excerpt"])
        self.assertIsNone(entry["evidence_confirmation"])
        self.assertIsNone(entry["result"]["provenance"])
        confirmation_prompt = mocked_input.call_args_list[-1].args[0]
        for selection_detail in (
            selection["player"],
            selection["platform"],
            selection["category"],
            selection["direction"],
            str(selection["projection"]),
            selection["event"],
            "HIT",
        ):
            self.assertIn(str(selection_detail), confirmation_prompt)

    def test_cli_rejects_unrecognized_evidence_confirmation(self) -> None:
        final = self.create_run()
        selection = final["approval"]["official_final"][0]
        selection_id = selection["candidate_key"]
        source_timestamp = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        excerpt = "Source excerpt supplied for the approved settlement"
        responses = (
            "HIT",
            "manual-entry",
            source_timestamp,
            f"platform-settlement:player/{selection_id}",
            excerpt,
            "MAYBE",
        )
        stderr = io.StringIO()

        with (
            patch("builtins.input", side_effect=responses),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = main(["result", "record", "--run-id", RUN_ID, "--selection", selection_id])

        self.assertEqual(exit_code, 1)
        self.assertIn("evidence confirmation must be YES or NO", stderr.getvalue())
        self.assertFalse((self.store.run_directory(RUN_ID) / "results.json").exists())

    def test_result_record_cli_rejects_unapproved_run(self) -> None:
        final = self.create_run(approve=False)
        selection_id = final["proposed"][0]["candidate_key"]

        with (
            patch("builtins.input", side_effect=AssertionError("unapproved run must not prompt")),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            exit_code = main(["result", "record", "--run-id", RUN_ID, "--selection", selection_id])

        self.assertEqual(exit_code, 1)
        self.assertFalse((self.store.run_directory(RUN_ID) / "results.json").exists())


if __name__ == "__main__":
    unittest.main()
