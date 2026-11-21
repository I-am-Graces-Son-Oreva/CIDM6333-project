"""Offline Controller submission tests using controlled ledger and evidence readers."""

import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fifth_pick.cli import main
from fifth_pick.evidence import EvidenceEffect, EvidenceItem, EvidenceKind, EvidenceSignificance
from fifth_pick.models import Category, Evidence, Provenance
from fifth_pick.snapshots import SnapshotEvidence
from fifth_pick.sources.base import EvidenceMode
from fifth_pick.storage import RunStore

KEY = "a" * 64
EVENT = "event1"
NOW = datetime(2026, 11, 21, 21, tzinfo=UTC)


def fact(kind, *, effect=EvidenceEffect.NEUTRAL):
    return EvidenceItem(
        kind.value,
        KEY,
        kind,
        Evidence(
            "Synthetic source for test",
            Provenance(
                "synthetic-test",
                NOW,
                NOW,
                "synthetic",
                "https://example.test/source",
                "b" * 64,
            ),
            "Synthetic excerpt",
        ),
        EvidenceMode.LIVE,
        effect,
        EvidenceSignificance.IMPORTANT,
    )


class LiveAssessmentCliTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.store = RunStore(directory)
        self.path = Path(directory) / "judgment.json"
        self.clock = self.enterContext(patch("fifth_pick.live_judgment_cli.datetime"))
        self.clock.now.return_value = NOW
        self.ledger = self.enterContext(
            patch("fifth_pick.live_judgment_cli.read_receipted_snapshot_ledger")
        )
        self.items = self.enterContext(
            patch("fifth_pick.live_judgment_cli.read_live_supporting_items")
        )
        self.enterContext(
            patch("fifth_pick.live_judgment_cli.application_run_store", return_value=self.store)
        )

    def scope(self, slot):
        self.args = [
            "controller-assess",
            "--run-id",
            "series",
            "--event-id",
            EVENT,
            "--candidate-key",
            KEY,
            "--snapshot",
            str(slot),
        ]
        self.ledger.return_value = tuple(
            Mock(
                spec=SnapshotEvidence,
                candidate_key=KEY,
                event_id=EVENT,
                candidate_id="stephen-curry",
                evidence_mode=EvidenceMode.LIVE,
                late=False,
                event_start=NOW + timedelta(hours=4),
                window_start=NOW + timedelta(minutes=20 if slot == 3 else 90),
                snapshot=SimpleNamespace(
                    number=number,
                    observation=SimpleNamespace(
                        category=Category.POINTS,
                        retrieved_at=NOW - timedelta(minutes=1),
                    ),
                ),
                to_dict=Mock(return_value={"synthetic": True, "slot": number}),
            )
            for number in range(1, slot + 1)
        )
        self.items.return_value = tuple(
            fact(kind)
            for kind in (
                EvidenceKind.AVAILABILITY,
                EvidenceKind.ROLE_MINUTES,
                EvidenceKind.GAME_TOTAL,
            )
        )

    def invoke(self, *, submit=False, confirmation=None):
        output, errors = StringIO(), StringIO()
        options = self.args + (["--judgment-file", str(self.path)] if submit else [])
        with redirect_stdout(output), redirect_stderr(errors):
            code = main(options, prompt=confirmation or (lambda _: "cancel"))
        return code, output.getvalue(), errors.getvalue()

    def judgment(self, digest, *, run_id="series", **changes):
        self.path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "scope_sha256": digest,
                    "judgment": {
                        "disposition": "ANALYSIS_ONLY",
                        "confidence": "LOW",
                        "rationale": "Controller supplied assessment.",
                        "supporting_evidence_ids": [],
                        "meaningful_risk_ids": [],
                        "sufficient_evidence": False,
                        **changes,
                    },
                }
            )
        )

    def test_both_slots_require_explicit_confirmation_and_only_record_assessment(self):
        for slot in (2, 3):
            self.scope(slot)
            status, preview, _ = self.invoke()
            self.assertEqual(status, 0)
            digest = json.loads(preview)["scope_sha256"]
            self.judgment(digest)
            count = len(self.store.read_receipts("series"))
            self.assertEqual(self.invoke(submit=True)[0], 1)
            self.assertEqual(len(self.store.read_receipts("series")), count)
            code, _, _ = self.invoke(
                submit=True,
                confirmation=lambda _, digest=digest: f"RECORD CONTROLLER ASSESSMENT {digest}",
            )
            self.assertEqual(code, 0)
        rows = self.store.read_receipts("series")
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["event"] for row in rows}, {"LIVE_METHODOLOGY_JUDGMENT"})

    def test_missing_t20_sources_expired_window_and_wrong_event_are_blocked(self):
        self.scope(3)
        self.items.return_value = (fact(EvidenceKind.GAME_TOTAL),)
        self.assertEqual(self.invoke()[0], 0)
        self.items.return_value = (fact(EvidenceKind.GENERAL_CONTEXT),)
        code, _, errors = self.invoke()
        self.assertEqual(code, 1)
        self.assertIn("Required game context", errors)
        self.scope(3)
        self.clock.now.return_value = NOW + timedelta(minutes=6)
        self.assertEqual(self.invoke()[0], 1)
        self.clock.now.return_value = NOW
        self.args[4] = "other-event"
        self.assertEqual(self.invoke()[0], 1)
        self.assertEqual(self.store.read_receipts("series"), ())

    def test_conflicting_availability_and_pre_snapshot_capture_are_blocked(self):
        self.scope(3)
        availability, *other = self.items.return_value
        self.items.return_value = (
            replace(availability, facts={"status": "AVAILABLE"}),
            replace(availability, evidence_id="conflicting", facts={"status": "OUT"}),
            *other,
        )
        self.assertIn("contradict", self.invoke()[2])
        self.scope(2)
        availability, *other = self.items.return_value
        older = NOW - timedelta(minutes=2)
        claim = replace(
            availability.evidence,
            provenance=replace(
                availability.evidence.provenance, source_timestamp=older, retrieved_at=older
            ),
        )
        self.items.return_value = (replace(availability, evidence=claim), *other)
        self.assertIn("stale", self.invoke()[2])
        self.assertEqual(self.store.read_receipts("series"), ())

    def test_stale_preview_contradiction_and_changed_sources_during_confirmation_fail(self):
        self.scope(2)
        digest = json.loads(self.invoke()[1])["scope_sha256"]
        confirm = f"RECORD CONTROLLER ASSESSMENT {digest}"
        self.judgment(digest, supporting_evidence_ids=["unverified"])
        self.assertEqual(self.invoke(submit=True, confirmation=lambda _: confirm)[0], 1)
        self.judgment(digest, disposition="QUALIFY")
        self.assertEqual(self.invoke(submit=True, confirmation=lambda _: confirm)[0], 1)
        self.judgment(digest, run_id="another-run")
        self.assertEqual(self.invoke(submit=True, confirmation=lambda _: confirm)[0], 1)
        self.judgment("f" * 64)
        self.assertEqual(self.invoke(submit=True, confirmation=lambda _: confirm)[0], 1)
        self.judgment(digest)

        def change_source(_):
            self.items.return_value += (fact(EvidenceKind.POINT_SPREAD),)
            return confirm

        self.assertEqual(self.invoke(submit=True, confirmation=change_source)[0], 1)
        self.assertEqual(self.store.read_receipts("series"), ())

    def test_t20_submission_rejects_stale_citation_despite_current_categories(self):
        self.scope(3)
        old = fact(EvidenceKind.POINT_SPREAD, effect=EvidenceEffect.SUPPORTS)
        before_t20 = NOW - timedelta(seconds=30)
        old = replace(
            old,
            evidence=replace(
                old.evidence,
                provenance=replace(
                    old.evidence.provenance,
                    retrieved_at=before_t20,
                    source_timestamp=before_t20,
                ),
            ),
        )
        self.items.return_value += (old,)
        digest = json.loads(self.invoke()[1])["scope_sha256"]
        self.judgment(digest, supporting_evidence_ids=[old.evidence_id])
        code, _, errors = self.invoke(
            submit=True,
            confirmation=lambda _: f"RECORD CONTROLLER ASSESSMENT {digest}",
        )
        self.assertEqual(code, 1)
        self.assertIn("outside the T-20 review", errors)
        self.assertEqual(self.store.read_receipts("series"), ())
