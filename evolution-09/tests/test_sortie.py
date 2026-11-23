"""Offline development tests. These are separate from the graded sortie."""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sortie import (  # noqa: E402  # ty: ignore[import-not-found]
    FreeRouter,
    Ledger,
    ResourceLock,
    preflight,
    receipt,
    verdict,
)


class SortieDevelopmentTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.ledger = Ledger(self.root / "ledger.jsonl")

    def test_receipt_records_actual_exit_code_and_output_hash(self):
        result = receipt(self.root, "control", [sys.executable, "-c", "print('ok')"], "dev")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(
            result["stdout_sha256"],
            "dc51b8c96c2d745df3bd5590d990230a482fd247123599548e0632fdbf97fc22",
        )
        self.assertEqual(json.loads((self.root / "receipts/control.json").read_text()), result)
        with self.assertRaises(FileExistsError):
            receipt(self.root, "control", [sys.executable, "-c", "raise SystemExit(1)"], "dev")

    def test_refutation_requires_real_receipt_field(self):
        evidence = {"exit_code": 1}
        self.assertEqual(
            verdict('{"verdict":"REFUTED","cites":"exit_code","missing":""}', evidence)["cites"],
            "exit_code",
        )
        with self.assertRaises(ValueError):
            verdict('{"verdict":"REFUTED","cites":"invented","missing":""}', evidence)

    def test_lock_denies_and_records_expiry_before_reclaim(self):
        lock = ResourceLock(self.root / "locks", "board", self.ledger)
        with patch("sortie.time.time", return_value=100):
            first = lock.acquire("first", 5)
            assert first is not None
            self.assertIsNone(lock.acquire("second", 5))
            self.assertFalse(lock.release("wrong"))
        with patch("sortie.time.time", return_value=106):
            second = lock.acquire("second", 5)
            assert second is not None
            self.assertFalse(lock.release(first))
            self.assertTrue(lock.release(second))
        events = [json.loads(line)["event"] for line in self.ledger.path.read_text().splitlines()]
        self.assertEqual(
            [e for e in events if e != "lock_release_denied"],
            ["lock_acquired", "lock_denied", "lock_expired", "lock_acquired", "lock_released"],
        )

    def test_simultaneous_workers_cannot_both_hold_lock(self):
        lock = ResourceLock(self.root / "locks", "board", self.ledger)
        pid = os.fork()
        if pid == 0:
            os._exit(0 if lock.acquire("child", 60) is not None else 2)
        parent_token = lock.acquire("parent", 60)
        _, status = os.waitpid(pid, 0)
        self.assertEqual(
            int(parent_token is not None) + int(os.waitstatus_to_exitcode(status) == 0), 1
        )

    def test_preflight_refuses_without_e8_pass_and_chase_go(self):
        with (
            patch("sortie.git", side_effect=["CHASE VERDICT — FAIL", "Pending", ""]),
            self.assertRaisesRegex(ValueError, "E8 Chase PASS.*E9 Chase GO"),
        ):
            preflight()

    def test_router_accounts_for_both_token_counts_and_zero_cost(self):
        reply = {
            "model": "qwen3:4b",
            "message": {"content": "result"},
            "prompt_eval_count": 12,
            "eval_count": 4,
            "done_reason": "stop",
        }
        with patch("sortie.build_opener") as opener:
            opener.return_value.open.return_value = io.StringIO(json.dumps(reply))
            body = FreeRouter(self.ledger).call("adversary", "synthetic test packet")
        self.assertEqual(body, "result")
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertEqual(json.loads(request.data)["model"], "qwen3:4b")
        summary = json.loads(self.ledger.path.read_text().splitlines()[-1])
        self.assertEqual(summary["tokens"], {"input": 12, "output": 4})
        self.assertEqual(summary["cost"], "0.00")

    def test_router_records_missing_usage_and_stops(self):
        with (
            patch("sortie.build_opener") as opener,
            self.assertRaisesRegex(ValueError, "Local model call stopped"),
        ):
            opener.return_value.open.return_value = io.StringIO("{}")
            FreeRouter(self.ledger).call("worker", "synthetic fixture")
        event = json.loads(self.ledger.path.read_text().splitlines()[-1])
        self.assertEqual(event["status"], "unverified_or_failed")
        self.assertIsNone(event["tokens"])
        self.assertEqual(event["cost"], "0.00")

    def test_preflight_rejects_go_superseded_by_no_go(self):
        card = "## CHASE\nGO — Reviewer — 2026-01-01\nNO-GO — Reviewer — 2026-01-02: pending"
        with (
            patch("sortie.git", side_effect=["CHASE VERDICT — PASS", card, ""]),
            self.assertRaisesRegex(ValueError, "dated E9 Chase GO is absent"),
        ):
            preflight()

    def test_preflight_accepts_assignment_go_format_after_e8_pass(self):
        card = "## CHASE\nGO — Reviewer, 2026-01-01"
        with patch("sortie.git", side_effect=["CHASE VERDICT — PASS", card, "", "approved-rev"]):
            self.assertEqual(preflight(), "approved-rev")
