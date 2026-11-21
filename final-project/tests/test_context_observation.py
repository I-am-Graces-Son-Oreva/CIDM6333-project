"""Synthetic validation of offline context archives. No source is actually authorized."""

import json
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from fifth_pick.config import ApprovedSource
from fifth_pick.evidence import EvidenceKind
from fifth_pick.receipts import Receipt
from fifth_pick.sources.base import LiveAuthorizationError, MalformedPayloadError, SourceEvent
from fifth_pick.sources.context_observation import validate_context_observation
from fifth_pick.sources.supporting_fixture import payload_hash

NOW = datetime(2026, 11, 21, 21, tzinfo=UTC)
EVENT = SourceEvent(
    "event1", "Golden State Warriors", "Boston Celtics", NOW + timedelta(minutes=19), ()
)
ARCHIVE = b"synthetic independent context excerpt for testing"
APPROVED = ApprovedSource(
    "test-context",
    "Synthetic test source",
    "context",
    ("injury and availability status", "teammate absence", "role and minutes"),
    "test:archived-report",
    None,
    "approved",
    (),
)
ROSTER = {
    "stephen-curry": EVENT.home_team,
    "synthetic-teammate": EVENT.home_team,
    "synthetic-opponent": EVENT.away_team,
}


def data(kind="AVAILABILITY", **changes):
    return {
        "event_id": EVENT.event_id,
        "player_id": "stephen-curry",
        "team": EVENT.home_team,
        "phase": "t20",
        "kind": kind,
        "source_id": APPROVED.source_id,
        "access_method": APPROVED.access_method,
        "reference": "https://example.test/archive",
        "source_timestamp": (NOW - timedelta(minutes=1)).isoformat(),
        "source_sha256": payload_hash(ARCHIVE),
        "excerpt": ARCHIVE.decode(),
        "fact": {"status": "AVAILABLE"},
        **changes,
    }


class ContextObservationTests(unittest.TestCase):
    def validate(self, record, *, approved=True, archive=ARCHIVE, change_receipt=None):
        body = json.dumps(record).encode()
        receipt = Receipt(
            NOW.isoformat(),
            "CONTEXT_OBSERVATION_ARCHIVED",
            "CAPTURED",
            "event1:stephen-curry:t20",
            "test-context",
            payload_hash(body),
            "series",
            f"context-observation-{payload_hash(body)}",
        )
        if approved:
            self.enterContext(
                patch(
                    "fifth_pick.sources.context_observation.load_configs",
                    return_value=SimpleNamespace(
                        approved_sources=SimpleNamespace(sources=(APPROVED,))
                    ),
                )
            )
        return validate_context_observation(
            body,
            archive,
            change_receipt or receipt,
            run_id="series",
            event=EVENT,
            candidate_player_id="stephen-curry",
            event_roster=ROSTER,
            phase="t20",
            as_of=NOW,
            max_age=timedelta(minutes=5),
        )

    def test_each_kind_returns_attributed_offline_facts(self):
        for kind, facts, subject in (
            ("AVAILABILITY", {"status": "AVAILABLE"}, "stephen-curry"),
            (
                "TEAMMATE_ABSENCE",
                {"status": "OUT", "teammate_id": "synthetic-teammate"},
                "synthetic-teammate",
            ),
            (
                "ROLE_MINUTES",
                {"role": "starter", "minutes_low": 24, "minutes_high": 29},
                "stephen-curry",
            ),
        ):
            with self.subTest(kind=kind):
                item = self.validate(data(kind, fact=facts))
                self.assertEqual(item.kind, EvidenceKind(kind))
                self.assertEqual(item.subject_player_id, subject)
                self.assertEqual(item.provenance.payload_hash, payload_hash(ARCHIVE))
                self.assertEqual(item.provenance.retrieved_at, NOW)
                self.assertFalse(hasattr(item, "evidence_mode"))

    def test_current_registry_cannot_authorize_the_unapproved_delivery(self):
        with self.assertRaises(LiveAuthorizationError):
            self.validate(
                data(
                    source_id="official-nba-injury-report",
                    access_method="official-nba-injury-report:direct-pdf",
                ),
                approved=False,
            )

    def test_rejects_stale_wrong_scope_wrong_team_and_unverified_facts(self):
        for record in (
            data(event_id="other"),
            data(team=EVENT.away_team),
            data(player_id="synthetic-teammate"),
            data(source_timestamp=(NOW - timedelta(minutes=6)).isoformat()),
            data(reference="https://example.test/archive?key=bogus"),
            data("ROLE_MINUTES", fact={"role": "starter", "minutes_low": 30, "minutes_high": 20}),
            data("TEAMMATE_ABSENCE", fact={"status": "OUT", "teammate_id": "synthetic-opponent"}),
            data(
                "TEAMMATE_ABSENCE",
                fact={"status": "QUESTIONABLE", "teammate_id": "synthetic-teammate"},
            ),
        ):
            with self.subTest(kind=record["kind"]), self.assertRaises(MalformedPayloadError):
                self.validate(record)
        with self.assertRaises(MalformedPayloadError):
            self.validate(data(), archive=ARCHIVE + b" altered")
        unrelated = Receipt(
            NOW.isoformat(),
            "CONTEXT_OBSERVATION_ARCHIVED",
            "CAPTURED",
            "other",
            "test-context",
            "wrong",
            "series",
            "other",
        )
        with self.assertRaises(MalformedPayloadError):
            self.validate(data(), change_receipt=unrelated)
