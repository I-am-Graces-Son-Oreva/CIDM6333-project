import json
import multiprocessing
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from io import StringIO
from tempfile import TemporaryDirectory
from time import sleep
from unittest.mock import patch

from fifth_pick.errors import StorageError
from fifth_pick.receipts import Receipt
from fifth_pick.review import ReviewTransition, start_review_cycle
from fifth_pick.review_bridge import BridgeRequestError, _run_lock, main, process_request
from fifth_pick.storage import AppendResult, RunStore

RUN_ID = "m10-bridge-run"
SUBJECT = "m10-phase2-review"
INITIAL_DIGEST = "a" * 64
CORRECTED_DIGEST = "b" * 64
NOW = datetime(2026, 11, 17, 20, 0, tzinfo=UTC)


def hold_run_lock(root: str, locked, release) -> None:
    with _run_lock(RunStore(root), RUN_ID):
        locked.set()
        release.wait(10)


def wait_for_run_lock(root: str, first_locked, started, acquired) -> None:
    if not first_locked.wait(10):
        return
    started.set()
    with _run_lock(RunStore(root), RUN_ID):
        acquired.set()


def run_conflicting_bridge_request(
    root: str,
    payload: dict[str, object],
    ready,
    start,
    results,
) -> None:
    import fifth_pick.review_bridge as bridge

    append_receipts = bridge.append_review_receipts

    def delayed_append(
        store: RunStore,
        transition: ReviewTransition,
        occurred_at: datetime,
    ) -> tuple[AppendResult, ...]:
        sleep(0.5)
        return append_receipts(store, transition, occurred_at)

    ready.put(True)
    if not start.wait(10):
        results.put((2, "START_TIMEOUT"))
        return
    with patch.object(bridge, "append_review_receipts", side_effect=delayed_append):
        result = bridge.process_request(json.dumps(payload), RunStore(root), NOW)
    results.put((result.exit_code, result.response["state"]))


def verdict(status: str, findings: list[str] | None = None) -> str:
    return json.dumps(
        {
            "status": status,
            "summary": "The review result is bounded.",
            "findings": [] if findings is None else findings,
        }
    )


def completed_task_result(payload: str, task_id: str = "ses-reviewer-task") -> str:
    return (
        f'<task id="{task_id}" state="completed">\n'
        f"<task_result>\n{payload}\n</task_result>\n</task>"
    )


def request(
    *,
    kind: str = "VERDICT",
    revision: int = 0,
    current_digest: str = INITIAL_DIGEST,
    verdict_json: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "kind": kind,
        "run_id": RUN_ID,
        "subject": SUBJECT,
        "initial_artifact_sha256": INITIAL_DIGEST,
        "current_artifact_sha256": current_digest,
        "revision": revision,
    }
    if kind == "VERDICT":
        payload["verdict_json"] = verdict("PASS") if verdict_json is None else verdict_json
    return payload


class ReviewBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = RunStore(self.temporary.name)

    def process(self, payload: dict[str, object]):
        return process_request(json.dumps(payload), self.store, NOW)

    def test_initial_pass_appends_one_run_bound_m2_receipt(self) -> None:
        result = self.process(request())

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            set(result.response),
            {
                "review_cycle_id",
                "state",
                "correction_count",
                "correction_available",
                "receipt_event_keys",
            },
        )
        self.assertEqual(result.response["state"], "REVIEWED_FOR_JOSEPH")
        self.assertEqual(result.response["correction_count"], 0)
        self.assertFalse(result.response["correction_available"])
        receipt = self.store.read_receipts(RUN_ID)[0]
        self.assertEqual(receipt["run_id"], RUN_ID)
        self.assertEqual(receipt["subject"], result.response["review_cycle_id"])
        self.assertEqual(receipt["event"], "REVIEW_PASS")
        self.assertNotIn("The review result is bounded.", json.dumps(receipt))

    def test_completed_task_envelope_extracts_exact_reviewer_json(self) -> None:
        result = self.process(request(verdict_json=completed_task_result(verdict("PASS"))))

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.response["state"], "REVIEWED_FOR_JOSEPH")
        self.assertEqual(self.store.read_receipts(RUN_ID)[0]["event"], "REVIEW_PASS")

    def test_empty_summary_inside_task_result_envelope_stops_without_receipt(self) -> None:
        invalid_verdict = json.dumps({"status": "PASS", "summary": "", "findings": []})

        result = self.process(request(verdict_json=completed_task_result(invalid_verdict)))

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.response["state"], "STOPPED")
        self.assertEqual(self.store.read_receipts(RUN_ID), ())

    def test_incomplete_task_result_envelope_stops_without_receipt(self) -> None:
        incomplete = '<task id="ses-reviewer-task" state="completed"><task_result>{}</task>'

        result = self.process(request(verdict_json=incomplete))

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.response["state"], "STOPPED")
        self.assertEqual(self.store.read_receipts(RUN_ID), ())

    def test_one_fail_dispatch_and_rereview_reconstructs_receipt_order(self) -> None:
        failed = self.process(request(verdict_json=verdict("FAIL", ["Correct this finding."])))
        dispatched = self.process(request(kind="REVISION_DISPATCHED", revision=1))
        reviewed = self.process(
            request(
                revision=1,
                current_digest=CORRECTED_DIGEST,
                verdict_json=verdict("PASS"),
            )
        )

        self.assertEqual(failed.response["state"], "REVISION_REQUIRED")
        self.assertTrue(failed.response["correction_available"])
        self.assertEqual(dispatched.response["correction_count"], 1)
        self.assertFalse(dispatched.response["correction_available"])
        self.assertEqual(reviewed.response["state"], "REVIEWED_FOR_JOSEPH")
        receipts = self.store.read_receipts(RUN_ID)
        self.assertEqual(
            [receipt["event"] for receipt in receipts],
            ["REVIEW_FAIL", "REVISION_ATTEMPT", "REVIEW_PASS"],
        )
        sequence_numbers = []
        for receipt in receipts:
            event_key = receipt["event_key"]
            assert isinstance(event_key, str)
            sequence_numbers.append(event_key.rsplit("-", maxsplit=2)[-2])
        self.assertEqual(sequence_numbers, ["01", "02", "03"])

    def test_invalid_verdict_stops_without_receipt(self) -> None:
        result = self.process(request(verdict_json='{"status":"APPROVE"}'))

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.response["state"], "STOPPED")
        self.assertEqual(result.response["receipt_event_keys"], [])
        self.assertEqual(self.store.read_receipts(RUN_ID), ())

    def test_initial_artifact_mismatch_returns_stopped_nonzero(self) -> None:
        result = self.process(request(current_digest=CORRECTED_DIGEST))

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.response["state"], "STOPPED")
        self.assertEqual(result.response["receipt_event_keys"], [])
        self.assertEqual(self.store.read_receipts(RUN_ID), ())

    def test_out_of_order_revision_dispatch_stops_without_receipt(self) -> None:
        result = self.process(request(kind="REVISION_DISPATCHED", revision=1))

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.response["state"], "STOPPED")
        self.assertEqual(self.store.read_receipts(RUN_ID), ())

    def test_unknown_and_duplicate_envelope_fields_fail_before_receipts(self) -> None:
        unknown = request()
        unknown["approval"] = True
        duplicate = (
            '{"schema_version":1,"schema_version":1,"kind":"VERDICT",'
            '"run_id":"m10-bridge-run","subject":"m10-phase2-review",'
            f'"initial_artifact_sha256":"{INITIAL_DIGEST}",'
            f'"current_artifact_sha256":"{INITIAL_DIGEST}","revision":0,'
            f'"verdict_json":{json.dumps(verdict("PASS"))}'
            "}"
        )

        with self.assertRaises(BridgeRequestError):
            self.process(unknown)
        with self.assertRaises(BridgeRequestError):
            process_request(duplicate, self.store, NOW)

        self.assertEqual(self.store.read_receipts(RUN_ID), ())

    def test_malformed_outer_json_fails_nonzero_without_stdout_or_receipt(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with (
            patch("sys.stdin", StringIO("{")),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            exit_code = main(store=self.store, occurred_at=NOW)

        self.assertNotEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertTrue(stderr.getvalue())
        self.assertEqual(self.store.read_receipts(RUN_ID), ())

    def test_cli_emits_exactly_one_json_line_for_a_valid_request(self) -> None:
        stdout = StringIO()
        with (
            patch("sys.stdin", StringIO(json.dumps(request()))),
            redirect_stdout(stdout),
            redirect_stderr(StringIO()),
        ):
            exit_code = main(store=self.store, occurred_at=NOW)

        lines = stdout.getvalue().splitlines()
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["state"], "REVIEWED_FOR_JOSEPH")

    def test_identical_initial_retry_is_idempotent_but_conflicting_verdict_stops(self) -> None:
        first = self.process(request())
        retry = self.process(request())
        conflict = self.process(request(verdict_json=verdict("FAIL", ["Conflicting result."])))

        self.assertEqual(retry.response, first.response)
        self.assertEqual(conflict.exit_code, 2)
        self.assertEqual(conflict.response["state"], "STOPPED")
        self.assertEqual(len(self.store.read_receipts(RUN_ID)), 1)

    def test_identical_dispatch_replay_stops_without_launch_authorization(self) -> None:
        self.process(request(verdict_json=verdict("FAIL", ["Finding."])))
        payload = request(kind="REVISION_DISPATCHED", revision=1)

        first = self.process(payload)
        replay = self.process(payload)

        self.assertEqual(first.exit_code, 0)
        self.assertEqual(replay.exit_code, 2)
        self.assertEqual(replay.response["state"], "STOPPED")
        self.assertEqual(replay.response["correction_count"], 1)
        self.assertEqual(replay.response["receipt_event_keys"], [])
        self.assertEqual(len(self.store.read_receipts(RUN_ID)), 2)

    def test_second_dispatch_with_conflicting_digest_stops(self) -> None:
        self.process(request(verdict_json=verdict("FAIL", ["Finding."])))
        first_dispatch = self.process(request(kind="REVISION_DISPATCHED", revision=1))
        conflict = self.process(
            request(
                kind="REVISION_DISPATCHED",
                revision=1,
                current_digest=CORRECTED_DIGEST,
            )
        )

        self.assertEqual(first_dispatch.exit_code, 0)
        self.assertEqual(conflict.exit_code, 2)
        self.assertEqual(conflict.response["state"], "STOPPED")
        self.assertEqual(
            [receipt["event"] for receipt in self.store.read_receipts(RUN_ID)],
            ["REVIEW_FAIL", "REVISION_ATTEMPT"],
        )

    def test_first_dispatch_must_match_the_failed_review_artifact_digest(self) -> None:
        self.process(request(verdict_json=verdict("FAIL", ["Finding."])))

        result = self.process(
            request(
                kind="REVISION_DISPATCHED",
                revision=1,
                current_digest=CORRECTED_DIGEST,
            )
        )

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.response["state"], "STOPPED")
        self.assertEqual(
            [receipt["event"] for receipt in self.store.read_receipts(RUN_ID)], ["REVIEW_FAIL"]
        )

    def test_invalid_receipt_history_stops_before_appending(self) -> None:
        cycle = start_review_cycle(RUN_ID, SUBJECT, INITIAL_DIGEST)
        digest = cycle.review_cycle_id.removeprefix("review-")
        self.store.append_receipt(
            Receipt(
                timestamp=NOW.isoformat(),
                event="REVIEW_PASS",
                result="PASS",
                subject=cycle.review_cycle_id,
                source="forged-source",
                reason="forged",
                run_id=RUN_ID,
                event_key=f"review-{digest}-09-review_pass",
            )
        )

        result = self.process(request())

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.response["state"], "STOPPED")
        self.assertEqual(len(self.store.read_receipts(RUN_ID)), 1)

    def test_retry_recovers_a_partially_appended_multi_event_transition(self) -> None:
        payload = request(verdict_json=verdict("CONCERNS", ["Human judgment needed."]))
        append_receipt = self.store.append_receipt
        calls = 0

        def fail_second_append(receipt: Receipt, *, secrets=()):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise StorageError("injected second receipt failure")
            return append_receipt(receipt, secrets=secrets)

        with patch.object(self.store, "append_receipt", side_effect=fail_second_append):
            failed = self.process(payload)

        self.assertEqual(failed.exit_code, 2)
        self.assertEqual(
            [item["event"] for item in self.store.read_receipts(RUN_ID)], ["REVIEW_CONCERNS"]
        )

        retried = self.process(payload)

        self.assertEqual(retried.exit_code, 0)
        self.assertEqual(
            [item["event"] for item in self.store.read_receipts(RUN_ID)],
            ["REVIEW_CONCERNS", "ESCALATE_TO_JOSEPH"],
        )

    def test_per_run_lock_serializes_independent_processes(self) -> None:
        context = multiprocessing.get_context("spawn")
        first_locked = context.Event()
        release_first = context.Event()
        second_started = context.Event()
        second_acquired = context.Event()
        holder = context.Process(
            target=hold_run_lock,
            args=(self.temporary.name, first_locked, release_first),
        )
        waiter = context.Process(
            target=wait_for_run_lock,
            args=(self.temporary.name, first_locked, second_started, second_acquired),
        )
        holder.start()
        self.assertTrue(first_locked.wait(10))
        waiter.start()
        self.assertTrue(second_started.wait(10))
        try:
            self.assertFalse(second_acquired.wait(0.15))
        finally:
            release_first.set()
            holder.join(10)
            waiter.join(10)

        self.assertEqual(holder.exitcode, 0)
        self.assertEqual(waiter.exitcode, 0)
        self.assertTrue(second_acquired.is_set())

    def test_concurrent_conflicting_verdicts_preserve_one_receipt_and_stop_one_writer(self) -> None:
        self.assert_concurrent_requests_allow_one(
            (
                request(verdict_json=verdict("PASS")),
                request(verdict_json=verdict("FAIL", ["Conflicting concurrent result."])),
            ),
            ("REVIEW_PASS", "REVIEW_FAIL"),
        )

    def test_concurrent_confirmations_allow_only_one_launch(self) -> None:
        self.process(request(verdict_json=verdict("FAIL", ["Finding."])))
        payload = request(kind="REVISION_DISPATCHED", revision=1)
        self.assert_concurrent_requests_allow_one((payload, payload), ("REVISION_ATTEMPT",))

    def assert_concurrent_requests_allow_one(
        self, requests: tuple[dict[str, object], ...], expected_events: tuple[str, ...]
    ) -> None:
        before = self.store.read_receipts(RUN_ID)
        context = multiprocessing.get_context("spawn")
        ready = context.Queue()
        results = context.Queue()
        start = context.Event()
        workers = [
            context.Process(
                target=run_conflicting_bridge_request,
                args=(self.temporary.name, payload, ready, start, results),
            )
            for payload in requests
        ]
        for worker in workers:
            worker.start()
        self.assertTrue(ready.get(timeout=10))
        self.assertTrue(ready.get(timeout=10))
        start.set()
        outcomes = [results.get(timeout=10) for _ in workers]
        for worker in workers:
            worker.join(10)

        self.assertTrue(all(worker.exitcode == 0 for worker in workers))
        self.assertEqual(sorted(code for code, _state in outcomes), [0, 2])
        after = self.store.read_receipts(RUN_ID)
        self.assertEqual(after[: len(before)], before)
        (new_receipt,) = after[len(before) :]
        self.assertIn(new_receipt["event"], expected_events)


if __name__ == "__main__":
    unittest.main()
