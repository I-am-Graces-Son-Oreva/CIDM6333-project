import ast
import hashlib
import json
import re
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from fifth_pick.errors import UnsafeRunIdError
from fifth_pick.review import (
    ReviewCycle,
    ReviewError,
    ReviewEvent,
    ReviewEventName,
    ReviewPhase,
    ReviewStatus,
    ReviewTransition,
    ReviewVerdict,
    append_review_receipts,
    apply_review_verdict,
    dispatch_review_correction,
    parse_review_verdict,
    start_review_cycle,
)
from fifth_pick.storage import RunStore

RUN_ID = "m10-review-run"
SUBJECT = "phase1-review-scope"
INITIAL_DIGEST = "a" * 64
CORRECTED_DIGEST = "b" * 64
REVIEWED_AT = datetime(2026, 11, 17, 19, 30, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent


def verdict_json(status: str, findings: list[str] | None = None) -> str:
    return json.dumps(
        {
            "status": status,
            "summary": "The reviewed evidence is bounded.",
            "findings": [] if findings is None else findings,
        }
    )


class ReviewVerdictParsingTests(unittest.TestCase):
    def test_pass_accepts_empty_findings(self) -> None:
        verdict = parse_review_verdict(verdict_json("PASS"))

        self.assertIs(verdict.status, ReviewStatus.PASS)
        self.assertEqual(verdict.findings, ())
        self.assertEqual(verdict.summary, "The reviewed evidence is bounded.")

    def test_pass_preserves_supplied_findings(self) -> None:
        verdict = parse_review_verdict(verdict_json("PASS", ["Informational note."]))

        self.assertEqual(verdict.findings, ("Informational note.",))

    def test_fail_requires_at_least_one_finding(self) -> None:
        with self.assertRaises(ValueError):
            parse_review_verdict(verdict_json("FAIL"))

    def test_concerns_requires_at_least_one_finding(self) -> None:
        with self.assertRaises(ValueError):
            parse_review_verdict(verdict_json("CONCERNS"))

    def test_findings_are_preserved_in_order(self) -> None:
        verdict = parse_review_verdict(verdict_json("FAIL", ["First finding.", "Second finding."]))

        self.assertEqual(verdict.findings, ("First finding.", "Second finding."))

    def test_malformed_verdict_fails_closed(self) -> None:
        for raw in ("{", "[]", "null", '"PASS"'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_review_verdict(raw)

    def test_unknown_verdict_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            parse_review_verdict(verdict_json("APPROVE"))

    def test_status_is_case_sensitive(self) -> None:
        with self.assertRaises(ValueError):
            parse_review_verdict(verdict_json("pass"))

    def test_missing_fields_fail_closed(self) -> None:
        for payload in (
            {"summary": "Summary.", "findings": []},
            {"status": "PASS", "findings": []},
            {"status": "PASS", "summary": "Summary."},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_review_verdict(json.dumps(payload))

    def test_unknown_fields_fail_closed(self) -> None:
        payload = {
            "status": "PASS",
            "summary": "Summary.",
            "findings": [],
            "approval": True,
        }

        with self.assertRaises(ValueError):
            parse_review_verdict(json.dumps(payload))

    def test_duplicate_fields_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            parse_review_verdict(
                '{"status":"FAIL","status":"PASS","summary":"Summary.","findings":[]}'
            )

    def test_blank_summary_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            parse_review_verdict(json.dumps({"status": "PASS", "summary": " \n ", "findings": []}))

    def test_non_string_summary_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            parse_review_verdict(json.dumps({"status": "PASS", "summary": 3, "findings": []}))

    def test_findings_must_be_an_array_of_nonempty_strings(self) -> None:
        invalid_findings = ("finding", [1], [" "], {"finding": "text"}, None)
        for findings in invalid_findings:
            payload = {"status": "FAIL", "summary": "Summary.", "findings": findings}
            with self.subTest(findings=findings), self.assertRaises(ValueError):
                parse_review_verdict(json.dumps(payload))


class ReviewCycleTests(unittest.TestCase):
    def start(self):
        return start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST)

    def test_cycle_id_uses_canonical_json_and_full_sha256(self) -> None:
        expected_input = (
            '{"initial_artifact_sha256":"'
            + INITIAL_DIGEST
            + '","run_id":"m10-review-run","subject":"phase1-review-scope"}'
        ).encode("utf-8")
        expected_id = "review-" + hashlib.sha256(expected_input).hexdigest()

        cycle = self.start()

        self.assertEqual(cycle.review_cycle_id, expected_id)
        self.assertEqual(len(cycle.review_cycle_id.removeprefix("review-")), 64)

    def test_cycle_id_changes_with_run_subject_or_initial_digest(self) -> None:
        original = self.start().review_cycle_id
        other_run = start_review_cycle("other-run", SUBJECT, INITIAL_DIGEST)
        other_subject = start_review_cycle(RUN_ID, "other-subject", INITIAL_DIGEST)
        other_digest = start_review_cycle(RUN_ID, SUBJECT, CORRECTED_DIGEST)

        self.assertNotEqual(original, other_run.review_cycle_id)
        self.assertNotEqual(original, other_subject.review_cycle_id)
        self.assertNotEqual(original, other_digest.review_cycle_id)

    def test_empty_cycle_identity_fields_fail_closed(self) -> None:
        for run_id, subject in (("", SUBJECT), (RUN_ID, " ")):
            with self.subTest(run_id=run_id, subject=subject), self.assertRaises(ValueError):
                start_review_cycle(run_id, subject, INITIAL_DIGEST)

    def test_direct_verdict_construction_rejects_an_unknown_status(self) -> None:
        with self.assertRaises(ValueError):
            ReviewVerdict(cast(ReviewStatus, "APPROVE"), "Summary.", ("Finding.",))

    def test_malformed_initial_artifact_digest_fails_closed(self) -> None:
        for digest in ("a" * 63, "g" * 64, "A" * 64, ""):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                start_review_cycle(RUN_ID, SUBJECT, digest)

    def test_direct_cycle_construction_rejects_noncanonical_cycle_id(self) -> None:
        with self.assertRaises(ValueError):
            ReviewCycle(
                run_id=RUN_ID,
                subject=SUBJECT,
                initial_artifact_sha256=INITIAL_DIGEST,
                review_cycle_id="review-" + "f" * 64,
            )

    def test_direct_cycle_construction_rejects_forged_event_sequence(self) -> None:
        cycle = self.start()

        with self.assertRaises(ValueError):
            ReviewCycle(
                run_id=cycle.run_id,
                subject=cycle.subject,
                initial_artifact_sha256=cycle.initial_artifact_sha256,
                review_cycle_id=cycle.review_cycle_id,
                event_sequence=1,
            )

    def test_stopped_phase_rejects_unreachable_concerns_escalation_sequence(self) -> None:
        cycle = self.start()

        with self.assertRaises(ValueError):
            ReviewCycle(
                run_id=cycle.run_id,
                subject=cycle.subject,
                initial_artifact_sha256=cycle.initial_artifact_sha256,
                review_cycle_id=cycle.review_cycle_id,
                phase=ReviewPhase.STOPPED,
                correction_count=0,
                event_sequence=2,
            )

    def test_initial_pass_returns_to_joseph_without_approval(self) -> None:
        transition = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.PASS, "No findings.", ()),
            INITIAL_DIGEST,
        )

        self.assertIs(transition.cycle.phase, ReviewPhase.REVIEWED_FOR_JOSEPH)
        self.assertEqual(transition.cycle.correction_count, 0)
        self.assertEqual([event.event for event in transition.events], ["REVIEW_PASS"])
        self.assertEqual(transition.events[0].result, "PASS")

    def test_initial_fail_allows_one_correction_without_dispatching_it(self) -> None:
        transition = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.FAIL, "A control is missing.", ("Finding.",)),
            INITIAL_DIGEST,
        )

        self.assertIs(transition.cycle.phase, ReviewPhase.REVISION_REQUIRED)
        self.assertEqual(transition.cycle.correction_count, 0)
        self.assertTrue(transition.cycle.correction_available)
        self.assertEqual([event.event for event in transition.events], ["REVIEW_FAIL"])
        self.assertEqual(transition.events[0].sequence, 1)

    def test_correction_dispatch_is_receipted_once_before_second_review(self) -> None:
        first = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.FAIL, "A control is missing.", ("Finding.",)),
            INITIAL_DIGEST,
        )

        dispatched = dispatch_review_correction(first.cycle, INITIAL_DIGEST)

        self.assertIs(dispatched.cycle.phase, ReviewPhase.AWAITING_REVIEW_AFTER_CORRECTION)
        self.assertEqual(dispatched.cycle.correction_count, 1)
        self.assertFalse(dispatched.cycle.correction_available)
        self.assertEqual([event.event for event in dispatched.events], ["REVISION_ATTEMPT"])
        self.assertEqual(dispatched.events[0].result, "CORRECTION_REQUESTED")
        self.assertEqual(dispatched.events[0].sequence, 2)

    def test_one_correction_then_escalation(self) -> None:
        initial = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.FAIL, "First fail.", ("First finding.",)),
            INITIAL_DIGEST,
        )
        dispatched = dispatch_review_correction(initial.cycle, INITIAL_DIGEST)

        second = apply_review_verdict(
            dispatched.cycle,
            ReviewVerdict(ReviewStatus.FAIL, "Second fail.", ("Second finding.",)),
            CORRECTED_DIGEST,
        )

        self.assertIs(second.cycle.phase, ReviewPhase.ESCALATE_TO_JOSEPH)
        self.assertEqual(second.cycle.correction_count, 1)
        self.assertEqual(
            [event.event for event in second.events],
            ["REVIEW_FAIL", "ESCALATE_TO_JOSEPH"],
        )
        self.assertEqual([event.sequence for event in second.events], [3, 4])
        self.assertEqual(second.events[1].result, "ESCALATED_TO_JOSEPH")

    def test_concerns_does_not_pass(self) -> None:
        transition = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.CONCERNS, "Human judgment needed.", ("Concern.",)),
            INITIAL_DIGEST,
        )

        self.assertIsNot(transition.cycle.phase, ReviewPhase.REVIEWED_FOR_JOSEPH)
        self.assertNotIn("REVIEW_PASS", [event.event.value for event in transition.events])

    def test_concerns_escalates_to_joseph(self) -> None:
        transition = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.CONCERNS, "Human judgment needed.", ("Concern.",)),
            INITIAL_DIGEST,
        )

        self.assertIs(transition.cycle.phase, ReviewPhase.ESCALATE_TO_JOSEPH)
        self.assertEqual(transition.cycle.correction_count, 0)
        self.assertEqual(
            [event.event for event in transition.events],
            ["REVIEW_CONCERNS", "ESCALATE_TO_JOSEPH"],
        )
        self.assertEqual(
            [event.result for event in transition.events], ["CONCERNS", "ESCALATED_TO_JOSEPH"]
        )

    def test_concerns_after_correction_escalates_without_another_correction(self) -> None:
        initial = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.FAIL, "First fail.", ("Finding.",)),
            INITIAL_DIGEST,
        )
        dispatched = dispatch_review_correction(initial.cycle, INITIAL_DIGEST)

        concerns = apply_review_verdict(
            dispatched.cycle,
            ReviewVerdict(ReviewStatus.CONCERNS, "Still uncertain.", ("Concern.",)),
            CORRECTED_DIGEST,
        )

        self.assertIs(concerns.cycle.phase, ReviewPhase.ESCALATE_TO_JOSEPH)
        self.assertEqual(concerns.cycle.correction_count, 1)
        self.assertEqual(
            [event.event for event in concerns.events],
            ["REVIEW_CONCERNS", "ESCALATE_TO_JOSEPH"],
        )
        self.assertEqual([event.sequence for event in concerns.events], [3, 4])

    def test_pass_after_one_correction_returns_to_joseph(self) -> None:
        initial = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.FAIL, "First fail.", ("Finding.",)),
            INITIAL_DIGEST,
        )
        dispatched = dispatch_review_correction(initial.cycle, INITIAL_DIGEST)

        passed = apply_review_verdict(
            dispatched.cycle,
            ReviewVerdict(ReviewStatus.PASS, "Corrected.", ()),
            CORRECTED_DIGEST,
        )

        self.assertIs(passed.cycle.phase, ReviewPhase.REVIEWED_FOR_JOSEPH)
        self.assertEqual(passed.cycle.correction_count, 1)
        self.assertEqual([event.event for event in passed.events], ["REVIEW_PASS"])
        self.assertEqual(passed.events[0].sequence, 3)

    def test_review_cannot_repeat_before_the_correction_is_dispatched(self) -> None:
        initial = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.FAIL, "First fail.", ("Finding.",)),
            INITIAL_DIGEST,
        )

        stopped = apply_review_verdict(
            initial.cycle,
            ReviewVerdict(ReviewStatus.PASS, "Unscheduled review.", ()),
            CORRECTED_DIGEST,
        )

        self.assertIs(stopped.cycle.phase, ReviewPhase.STOPPED)
        self.assertEqual(stopped.events, ())

    def test_correction_cannot_be_dispatched_before_initial_fail(self) -> None:
        stopped = dispatch_review_correction(self.start(), INITIAL_DIGEST)

        self.assertIs(stopped.cycle.phase, ReviewPhase.STOPPED)
        self.assertEqual(stopped.events, ())

    def test_second_correction_attempt_stops_without_event(self) -> None:
        initial = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.FAIL, "First fail.", ("Finding.",)),
            INITIAL_DIGEST,
        )
        dispatched = dispatch_review_correction(initial.cycle, INITIAL_DIGEST)

        stopped = dispatch_review_correction(dispatched.cycle, CORRECTED_DIGEST)

        self.assertIs(stopped.cycle.phase, ReviewPhase.STOPPED)
        self.assertEqual(stopped.cycle.correction_count, 1)
        self.assertEqual(stopped.events, ())

    def test_terminal_state_cannot_accept_another_verdict(self) -> None:
        passed = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.PASS, "Passed.", ()),
            INITIAL_DIGEST,
        )

        with self.assertRaises(ReviewError):
            apply_review_verdict(
                passed.cycle,
                ReviewVerdict(ReviewStatus.FAIL, "Late fail.", ("Finding.",)),
                INITIAL_DIGEST,
            )

        self.assertIs(passed.cycle.phase, ReviewPhase.REVIEWED_FOR_JOSEPH)

    def test_initial_concerns_escalation_rejects_followup_transition(self) -> None:
        concerns = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.CONCERNS, "Human review.", ("Concern.",)),
            INITIAL_DIGEST,
        )

        self.assertIs(concerns.cycle.phase, ReviewPhase.ESCALATE_TO_JOSEPH)
        self.assertEqual([event.sequence for event in concerns.events], [1, 2])
        with self.assertRaises(ReviewError):
            apply_review_verdict(
                concerns.cycle,
                ReviewVerdict(ReviewStatus.PASS, "Invalid follow-up.", ()),
                INITIAL_DIGEST,
            )
        with self.assertRaises(ReviewError):
            dispatch_review_correction(concerns.cycle, INITIAL_DIGEST)

    def test_concerns_escalation_rejects_followup_correction(self) -> None:
        concerns = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.CONCERNS, "Human review.", ("Concern.",)),
            INITIAL_DIGEST,
        )

        with self.assertRaises(ReviewError):
            dispatch_review_correction(concerns.cycle, INITIAL_DIGEST)

        self.assertIs(concerns.cycle.phase, ReviewPhase.ESCALATE_TO_JOSEPH)
        self.assertEqual(concerns.cycle.correction_count, 0)

    def test_stopped_cycle_rejects_all_followup_transitions(self) -> None:
        initial = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.FAIL, "First fail.", ("Finding.",)),
            INITIAL_DIGEST,
        )
        stopped = apply_review_verdict(
            initial.cycle,
            ReviewVerdict(ReviewStatus.PASS, "Not dispatched.", ()),
            CORRECTED_DIGEST,
        )
        self.assertIs(stopped.cycle.phase, ReviewPhase.STOPPED)

        with self.assertRaises(ReviewError):
            apply_review_verdict(
                stopped.cycle,
                ReviewVerdict(ReviewStatus.PASS, "Late pass.", ()),
                INITIAL_DIGEST,
            )
        with self.assertRaises(ReviewError):
            dispatch_review_correction(stopped.cycle, INITIAL_DIGEST)

        self.assertIs(stopped.cycle.phase, ReviewPhase.STOPPED)

    def test_initial_review_must_match_initial_artifact_digest(self) -> None:
        stopped = apply_review_verdict(
            self.start(),
            ReviewVerdict(ReviewStatus.PASS, "Wrong artifact.", ()),
            CORRECTED_DIGEST,
        )

        self.assertIs(stopped.cycle.phase, ReviewPhase.STOPPED)
        self.assertEqual(stopped.events, ())


class ReviewReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = RunStore(self.temporary.name)

    def test_receipt_binds_run_cycle_event_and_does_not_record_reviewer_text(self) -> None:
        cycle = start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST)
        verdict = ReviewVerdict(
            ReviewStatus.PASS,
            "Private summary text.",
            ("Private finding text.",),
        )
        transition = apply_review_verdict(cycle, verdict, INITIAL_DIGEST)

        written = append_review_receipts(self.store, transition, REVIEWED_AT)
        receipt = written[0].receipt
        serialized = json.dumps(receipt)

        self.assertTrue(written[0].created)
        self.assertEqual(receipt["run_id"], RUN_ID)
        self.assertEqual(receipt["subject"], cycle.review_cycle_id)
        self.assertEqual(receipt["event"], "REVIEW_PASS")
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["source"], "fifth-pick-reviewer")
        self.assertEqual(receipt["timestamp"], REVIEWED_AT.isoformat())
        self.assertEqual(transition.events[0].review_cycle_id, cycle.review_cycle_id)
        self.assertEqual(
            receipt["event_key"],
            f"review-{cycle.review_cycle_id.removeprefix('review-')}-01-review_pass",
        )
        self.assertNotIn("Private summary text.", serialized)
        self.assertNotIn("Private finding text.", serialized)

    def test_concerns_and_escalation_are_appended_in_event_order(self) -> None:
        transition = apply_review_verdict(
            start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST),
            ReviewVerdict(ReviewStatus.CONCERNS, "Human review.", ("Concern.",)),
            INITIAL_DIGEST,
        )

        written = append_review_receipts(self.store, transition, REVIEWED_AT)

        self.assertEqual(
            [item.receipt["event"] for item in written],
            ["REVIEW_CONCERNS", "ESCALATE_TO_JOSEPH"],
        )
        self.assertEqual(
            [item.receipt["result"] for item in written], ["CONCERNS", "ESCALATED_TO_JOSEPH"]
        )
        self.assertEqual(
            [item.receipt["source"] for item in written],
            ["fifth-pick-reviewer", "fifth-pick-review-controller"],
        )
        cycle_digest = transition.cycle.review_cycle_id.removeprefix("review-")
        self.assertEqual(
            [item.receipt["event_key"] for item in written],
            [
                f"review-{cycle_digest}-01-review_concerns",
                f"review-{cycle_digest}-02-escalate_to_joseph",
            ],
        )

    def test_review_event_rejects_forged_event_name(self) -> None:
        cycle = start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST)

        with self.assertRaises(ReviewError):
            ReviewEvent(
                review_cycle_id=cycle.review_cycle_id,
                event=cast(ReviewEventName, "FORGED_EVENT"),
                result="PASS",
                sequence=1,
                revision=0,
                artifact_sha256=INITIAL_DIGEST,
                reason_code="VALIDATED_PASS",
            )

    def test_transition_rejects_mismatched_cycle_identifier(self) -> None:
        transition = apply_review_verdict(
            start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST),
            ReviewVerdict(ReviewStatus.PASS, "Passed.", ()),
            INITIAL_DIGEST,
        )
        forged = replace(transition.events[0], review_cycle_id="review-" + "f" * 64)

        with self.assertRaises(ReviewError):
            ReviewTransition(transition.cycle, (forged,))

    def test_transition_rejects_out_of_order_event_sequence(self) -> None:
        transition = apply_review_verdict(
            start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST),
            ReviewVerdict(ReviewStatus.PASS, "Passed.", ()),
            INITIAL_DIGEST,
        )
        forged = replace(transition.events[0], sequence=7)

        with self.assertRaises(ReviewError):
            ReviewTransition(transition.cycle, (forged,))

    def test_transition_rejects_inconsistent_revision_number(self) -> None:
        transition = apply_review_verdict(
            start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST),
            ReviewVerdict(ReviewStatus.PASS, "Passed.", ()),
            INITIAL_DIGEST,
        )
        forged = replace(transition.events[0], revision=1)

        with self.assertRaises(ReviewError):
            ReviewTransition(transition.cycle, (forged,))

    def test_transition_rejects_artifact_digest_mismatch(self) -> None:
        transition = apply_review_verdict(
            start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST),
            ReviewVerdict(ReviewStatus.PASS, "Passed.", ()),
            INITIAL_DIGEST,
        )
        forged = replace(transition.events[0], artifact_sha256=CORRECTED_DIGEST)

        with self.assertRaises(ReviewError):
            ReviewTransition(transition.cycle, (forged,))

    def test_receipt_append_revalidates_whole_transition_before_writing(self) -> None:
        transition = apply_review_verdict(
            start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST),
            ReviewVerdict(ReviewStatus.CONCERNS, "Human review.", ("Concern.",)),
            INITIAL_DIGEST,
        )
        object.__setattr__(transition.events[1], "sequence", 3)

        with self.assertRaises(ReviewError):
            append_review_receipts(self.store, transition, REVIEWED_AT)

        self.assertEqual(self.store.read_receipts(RUN_ID), ())

    def test_event_result_must_match_event_name(self) -> None:
        transition = apply_review_verdict(
            start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST),
            ReviewVerdict(ReviewStatus.PASS, "Passed.", ()),
            INITIAL_DIGEST,
        )

        with self.assertRaises(ReviewError):
            forged = replace(transition.events[0], result="FAIL")
            ReviewTransition(transition.cycle, (forged,))

    def test_receipt_retry_is_idempotent_and_keeps_original_timestamp(self) -> None:
        transition = apply_review_verdict(
            start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST),
            ReviewVerdict(ReviewStatus.PASS, "Passed.", ()),
            INITIAL_DIGEST,
        )

        first = append_review_receipts(self.store, transition, REVIEWED_AT)
        retry = append_review_receipts(
            self.store,
            transition,
            REVIEWED_AT + timedelta(minutes=1),
        )

        self.assertTrue(first[0].created)
        self.assertFalse(retry[0].created)
        self.assertEqual(retry[0].receipt, first[0].receipt)
        self.assertEqual(len(self.store.read_receipts(RUN_ID)), 1)

    def test_receipt_run_id_is_validated_by_existing_m2_store(self) -> None:
        transition = apply_review_verdict(
            start_review_cycle("../unsafe", SUBJECT, INITIAL_DIGEST),
            ReviewVerdict(ReviewStatus.PASS, "Passed.", ()),
            INITIAL_DIGEST,
        )

        with self.assertRaises(UnsafeRunIdError):
            append_review_receipts(self.store, transition, REVIEWED_AT)

    def test_receipt_timestamp_must_be_utc(self) -> None:
        transition = apply_review_verdict(
            start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST),
            ReviewVerdict(ReviewStatus.PASS, "Passed.", ()),
            INITIAL_DIGEST,
        )

        with self.assertRaises(ValueError):
            append_review_receipts(
                self.store,
                transition,
                datetime(2026, 11, 17, 19, 30),
            )

        with self.assertRaises(ValueError):
            append_review_receipts(
                self.store,
                transition,
                datetime(2026, 11, 17, 11, 30, tzinfo=timezone(timedelta(hours=-8))),
            )


class PhaseOneDocumentTests(unittest.TestCase):
    def test_four_project_skills_exist_with_discovery_descriptions(self) -> None:
        names = (
            "evaluate-candidate",
            "validate-evidence",
            "final-slate-review",
            "t20-review",
        )
        for name in names:
            path = REPO_ROOT / ".opencode" / "skills" / name / "SKILL.md"
            with self.subTest(skill=name):
                self.assertTrue(path.is_file())
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"))
                self.assertIn(f"name: {name}\n", text)
                self.assertRegex(text, r"(?m)^description: Use when\b")

    def test_assurance_table_has_control_and_evidence_per_risk(self) -> None:
        path = ROOT / "docs" / "fifth-pick" / "assurance.md"
        text = path.read_text(encoding="utf-8")
        table_rows: list[list[str]] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|") or not stripped.endswith("|"):
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(set(cell) <= {"-", ":"} for cell in cells):
                continue
            table_rows.append(cells)

        self.assertGreaterEqual(len(table_rows), 2)
        self.assertEqual(
            table_rows[0],
            ["Risk / control", "Implemented control", "Evidence", "Status"],
        )
        self.assertTrue(all(len(row) == 4 and all(row) for row in table_rows))

        test_file = ROOT / "tests" / "test_review_loop.py"
        test_names = {
            node.name
            for node in ast.walk(ast.parse(test_file.read_text(encoding="utf-8")))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        blocked_rows = []
        for risk, control, evidence, status in table_rows[1:]:
            risk_lower = risk.lower()
            if "reviewer edit" in risk_lower:
                blocked_rows.append((control, evidence, status))
                self.assertTrue(status.startswith("**BLOCKED"))
            if status.startswith("GUIDANCE ONLY"):
                self.assertIn("does not replace mechanical", control)
            if status.startswith("PASS"):
                self.assertNotIn(".opencode/agents/", evidence)
                for unsupported_claim in (
                    "prompt instruction",
                    "static permission configuration",
                    "missing tool",
                    "unchanged file alone",
                ):
                    self.assertNotIn(unsupported_claim, control.lower())
                test_refs = re.findall(
                    r"`tests/test_review_loop\.py::(test_[a-z0-9_]+)`",
                    evidence,
                )
                if test_refs:
                    self.assertTrue(set(test_refs).issubset(test_names))
                if "docs/fifth-pick/gates.md" in evidence:
                    self.assertIn("docs/fifth-pick/gates.md", evidence)
                    for command in (
                        "uv run ruff check",
                        "uv run ruff format --check",
                        "uv run ty check",
                        "uv run python -m unittest discover -s tests",
                    ):
                        self.assertIn(command, evidence)
                elif not test_refs:
                    self.fail("PASS assurance row must cite an executable test or quality gate")

            path_refs = re.findall(r"`((?:tests|docs|src|\.opencode)/[^`]+)`", evidence)
            for reference in path_refs:
                referenced_path = reference.split("::", maxsplit=1)[0]
                base = REPO_ROOT if referenced_path.startswith(".opencode/") else ROOT
                self.assertTrue((base / referenced_path).exists(), reference)

        self.assertTrue(blocked_rows)
        self.assertTrue(any("unavailable tools" in line.lower() for line in text.splitlines()))


if __name__ == "__main__":
    unittest.main()
