import hashlib
import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fifth_pick.evidence import (
    EvidenceEffect,
    EvidenceError,
    EvidenceItem,
    EvidenceKind,
    EvidenceSignificance,
    PerformanceSample,
    summarize_history,
    validate_evidence_items,
)
from fifth_pick.models import Direction, Evidence, Provenance
from fifth_pick.receipts import REDACTION_MARKER
from fifth_pick.sources.base import EvidenceMode

NOW = datetime(2026, 11, 15, 18, 0, tzinfo=UTC)
CANDIDATE_KEY = "a" * 64
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "evidence" / "m6-history.json"


def make_item(
    *,
    kind: EvidenceKind = EvidenceKind.MATCHUP,
    source: str = "synthetic-fixture",
    access_method: str = "synthetic-fixture",
    reference: str = "fixture:evidence/m6-case",
    mode: EvidenceMode = EvidenceMode.FIXTURE,
    samples: tuple[PerformanceSample, ...] = (),
) -> EvidenceItem:
    provenance = Provenance(
        source=source,
        retrieved_at=NOW,
        source_timestamp=NOW - timedelta(minutes=1),
        access_method=access_method,
        reference=reference,
        payload_hash=hashlib.sha256(b"synthetic fixture").hexdigest(),
    )
    return EvidenceItem(
        evidence_id=f"evidence-{kind.value.lower()}",
        candidate_key=CANDIDATE_KEY,
        kind=kind,
        evidence=Evidence(
            claim="Synthetic evidence for deterministic tests.",
            provenance=provenance,
            excerpt="fixture excerpt",
        ),
        evidence_mode=mode,
        effect=EvidenceEffect.SUPPORTS,
        significance=EvidenceSignificance.IMPORTANT,
        samples=samples,
    )


class M6ModuleTests(unittest.TestCase):
    def test_m6_modules_and_fixture_directory_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        required = (
            root / "src" / "fifth_pick" / "evidence.py",
            root / "src" / "fifth_pick" / "methodology.py",
            root / "src" / "fifth_pick" / "ranking.py",
            root / "tests" / "fixtures" / "evidence",
        )

        self.assertTrue(
            all(path.exists() for path in required), "M6 modules or fixtures are missing"
        )


class EvidenceValidationTests(unittest.TestCase):
    def test_evidence_item_serializes_its_provenance_and_excerpt(self) -> None:
        item = make_item()

        serialized = item.to_dict()

        self.assertEqual(serialized["evidence_id"], item.evidence_id)
        self.assertEqual(serialized["source"], "synthetic-fixture")
        self.assertEqual(serialized["excerpt"], "fixture excerpt")

    def test_supporting_evidence_requires_approved_source_and_provenance(self) -> None:
        fixture = make_item()

        validated = validate_evidence_items((fixture,), candidate_key=CANDIDATE_KEY)

        self.assertEqual(validated, (fixture,))
        with self.assertRaises(EvidenceError):
            validate_evidence_items(
                (make_item(source="unapproved-source", access_method="fixture"),),
                candidate_key=CANDIDATE_KEY,
            )
        with self.assertRaises(EvidenceError):
            validate_evidence_items(
                (
                    make_item(
                        source="nba-com",
                        access_method="unapproved-manual-fetch",
                        mode=EvidenceMode.LIVE,
                    ),
                ),
                candidate_key=CANDIDATE_KEY,
            )

    def test_nba_stats_endpoint_is_rejected(self) -> None:
        evidence = make_item(
            source="nba-com",
            access_method="nba-com",
            reference="https://stats.nba.com/stats/playergamelog",
            mode=EvidenceMode.LIVE,
        )

        with self.assertRaises(EvidenceError):
            validate_evidence_items((evidence,), candidate_key=CANDIDATE_KEY)

    def test_fixture_evidence_redacts_sensitive_reference_values(self) -> None:
        evidence = make_item(
            reference="fixture:https://example.test/report?apiKey=fixture-secret&section=injury"
        )

        validated = validate_evidence_items((evidence,), candidate_key=CANDIDATE_KEY)

        self.assertNotIn("fixture-secret", validated[0].evidence.provenance.reference)
        self.assertIn(REDACTION_MARKER, validated[0].evidence.provenance.reference)

    def test_live_supporting_evidence_requires_configured_access_method(self) -> None:
        evidence = make_item(
            source="official-nba-injury-report",
            access_method="unapproved-manual-fetch",
            reference="official-injury-report:2026-11-15",
            mode=EvidenceMode.LIVE,
        )

        with self.assertRaises(EvidenceError):
            validate_evidence_items((evidence,), candidate_key=CANDIDATE_KEY)

    def test_live_odds_board_context_is_not_authenticated_as_supporting_evidence(self) -> None:
        evidence = make_item(
            kind=EvidenceKind.GAME_TOTAL,
            source="the-odds-api-us-dfs",
            access_method="the-odds-api:us_dfs",
            reference="the-odds-api:event:claimed-total",
            mode=EvidenceMode.LIVE,
        )

        with self.assertRaises(EvidenceError):
            validate_evidence_items((evidence,), candidate_key=CANDIDATE_KEY)

    def test_redaction_covers_evidence_ids_facts_and_sample_text(self) -> None:
        sample = PerformanceSample(
            played_at=NOW,
            value=20.0,
            opponent="https://example.test/opponent?token=sample-secret",
            season="https://example.test/season?key=season-secret",
        )
        evidence = replace(
            make_item(kind=EvidenceKind.LAST_8, samples=(sample,)),
            evidence_id="https://example.test/evidence?apiKey=id-secret",
            facts={
                "https://example.test/fact-key?token=key-secret": (
                    "https://example.test/fact?password=fact-secret"
                )
            },
        )

        validated = validate_evidence_items((evidence,), candidate_key=CANDIDATE_KEY)[0]
        serialized = json.dumps(validated.to_dict())

        for secret in (
            "id-secret",
            "key-secret",
            "fact-secret",
            "sample-secret",
            "season-secret",
        ):
            self.assertNotIn(secret, serialized)
        self.assertIn(REDACTION_MARKER, serialized)


class HistorySummaryTests(unittest.TestCase):
    def test_last8_and_same_season_h2h_counts_are_deterministic(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        last8_samples = tuple(
            PerformanceSample(
                played_at=datetime.fromisoformat(sample["played_at"]),
                value=sample["value"],
                opponent=sample["opponent"],
                season=sample["season"],
            )
            for sample in fixture["last_8"]
        )
        h2h_samples = tuple(
            PerformanceSample(
                played_at=datetime.fromisoformat(sample["played_at"]),
                value=sample["value"],
                opponent=sample["opponent"],
                season=sample["season"],
            )
            for sample in fixture["same_season_h2h"]
        )
        last8 = make_item(kind=EvidenceKind.LAST_8, samples=last8_samples)
        h2h = make_item(
            kind=EvidenceKind.SAME_SEASON_H2H,
            samples=h2h_samples,
        )

        last8_summary = summarize_history(
            last8,
            line=34.0,
            direction=Direction.HIGHER,
            current_season=fixture["season"],
            opponent=fixture["opponent"],
        )
        h2h_summary = summarize_history(
            h2h,
            line=34.0,
            direction=Direction.HIGHER,
            current_season=fixture["season"],
            opponent=fixture["opponent"],
        )

        self.assertEqual(last8_summary.sample_count, 8)
        self.assertEqual((last8_summary.higher_count, last8_summary.lower_count), (3, 4))
        self.assertFalse(last8_summary.incomplete)
        self.assertEqual(h2h_summary.sample_count, 1)
        self.assertEqual(h2h_summary.favorable_count, 1)

    def test_duplicate_game_sample_does_not_change_history_summary(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        samples = tuple(
            PerformanceSample(
                played_at=datetime.fromisoformat(sample["played_at"]),
                value=sample["value"],
                opponent=sample["opponent"],
                season=sample["season"],
            )
            for sample in fixture["last_8"]
        )
        original = make_item(kind=EvidenceKind.LAST_8, samples=samples)
        duplicate = replace(
            original,
            samples=(*original.samples, max(original.samples, key=lambda sample: sample.played_at)),
        )

        original_summary = summarize_history(
            original,
            line=34.0,
            direction=Direction.HIGHER,
            current_season=fixture["season"],
            opponent=fixture["opponent"],
        )
        duplicate_summary = summarize_history(
            duplicate,
            line=34.0,
            direction=Direction.HIGHER,
            current_season=fixture["season"],
            opponent=fixture["opponent"],
        )

        self.assertEqual(duplicate_summary, original_summary)

    def test_same_game_with_conflicting_values_is_rejected(self) -> None:
        original = make_item(
            kind=EvidenceKind.LAST_8,
            samples=(
                PerformanceSample(
                    played_at=NOW - timedelta(days=1),
                    value=20.0,
                    opponent="Synthetic Opponent",
                    season="2026-27",
                ),
            ),
        )
        conflicting = replace(original.samples[0], value=25.0)

        with self.assertRaises(EvidenceError):
            replace(original, samples=(*original.samples, conflicting))


if __name__ == "__main__":
    unittest.main()
