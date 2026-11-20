import hashlib
import json
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import fifth_pick.storage as storage_module
from fifth_pick.evidence import (
    EvidenceEffect,
    EvidenceGap,
    EvidenceItem,
    EvidenceKind,
    EvidenceSignificance,
)
from fifth_pick.methodology import (
    CandidateCase,
    Confidence,
    EvaluationStatus,
    MethodologyDisposition,
)
from fifth_pick.models import Category, Direction, ReasonCode
from fifth_pick.snapshots import MissedSnapshot
from fifth_pick.storage import RunStore
from fifth_pick.t20_review import T20Conclusion, review_t20, review_window_allows
from tests.m6_support import make_case as make_m6_case
from tests.m6_support import make_evidence_item, make_evidence_set, make_judgment
from tests.test_methodology import make_case_from_m5_records, make_live_ledger

RUN_ID = "m7-offline-review"
TARGET_AT = make_m6_case().snapshots[0].event_start - timedelta(minutes=20)


def make_case(**kwargs):
    return make_m6_case(**kwargs)


T20_ROLE_CONTEXT = frozenset({EvidenceKind.ROLE_MINUTES, EvidenceKind.TEAMMATE_ABSENCE})
T20_GAME_CONTEXT = frozenset(
    {
        EvidenceKind.MATCHUP,
        EvidenceKind.GAME_TOTAL,
        EvidenceKind.POINT_SPREAD,
        EvidenceKind.BLOWOUT_RISK,
        EvidenceKind.OPPONENT_ABSENCE,
        EvidenceKind.SCHEDULE,
    }
)


def make_evidence_current(item: EvidenceItem) -> EvidenceItem:
    provenance = item.evidence.provenance
    return replace(
        item,
        evidence=replace(
            item.evidence,
            provenance=replace(
                provenance,
                retrieved_at=TARGET_AT,
                source_timestamp=TARGET_AT - timedelta(minutes=1),
            ),
        ),
    )


def make_t20_case(
    case: CandidateCase,
    *,
    availability: bool = True,
    role_context: bool = True,
    game_context: bool = True,
) -> CandidateCase:
    evidence = []
    for item in case.evidence:
        should_refresh = (
            item.kind is EvidenceKind.AVAILABILITY
            and availability
            or item.kind in T20_ROLE_CONTEXT
            and role_context
            or item.kind in T20_GAME_CONTEXT
            and game_context
        )
        evidence.append(make_evidence_current(item) if should_refresh else item)

    key = case.snapshots[0].candidate_key
    if availability and not any(item.kind is EvidenceKind.AVAILABILITY for item in evidence):
        evidence.append(
            make_evidence_current(
                make_evidence_item(
                    key,
                    "t20-availability",
                    EvidenceKind.AVAILABILITY,
                    effect=EvidenceEffect.NEUTRAL,
                    significance=EvidenceSignificance.IMPORTANT,
                )
            )
        )
    return replace(case, evidence=tuple(evidence))


def with_projection_movement_evidence(
    case: CandidateCase,
    *,
    current_at_t20: bool,
) -> CandidateCase:
    movement = make_evidence_item(
        case.snapshots[0].candidate_key,
        "projection-movement",
        EvidenceKind.PROJECTION_MOVEMENT,
        effect=EvidenceEffect.SUPPORTS,
        significance=EvidenceSignificance.IMPORTANT,
    )
    if current_at_t20:
        movement = make_evidence_current(movement)
    assert case.judgment is not None
    return replace(
        case,
        evidence=(*case.evidence, movement),
        judgment=replace(
            case.judgment,
            supporting_evidence_ids=("last8", "role", "projection-movement"),
        ),
    )


def changed_event(case, event_id: str):
    first = case.snapshots[0]
    observation = first.snapshot.observation
    identity = json.dumps(
        [
            event_id,
            observation.platform.value,
            first.candidate_id,
            observation.category.value,
            observation.direction.value,
        ],
        separators=(",", ":"),
    )
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    snapshots = []
    for item in case.snapshots:
        current = item.snapshot.observation
        changed_observation = replace(current, event=event_id)
        snapshots.append(
            replace(
                item,
                candidate_key=key,
                event_id=event_id,
                snapshot=replace(item.snapshot, observation=changed_observation),
                provenance=replace(
                    item.provenance,
                    reference=f"{item.provenance.source}:event:{event_id}",
                ),
                source_excerpt={**item.source_excerpt, "event_id": event_id},
            )
        )
    evidence = make_evidence_set(key)
    return replace(
        case,
        snapshots=tuple(snapshots),
        evidence=evidence,
        judgment=make_judgment(evidence),
    )


class T20ReviewTests(unittest.TestCase):
    def test_approved_live_review_window_boundaries(self):
        from datetime import UTC, datetime

        target = datetime(2026, 11, 18, 22, tzinfo=UTC)
        for offset, allowed in ((-1, False), (0, True), (300, True), (301, False)):
            with self.subTest(offset=offset):
                at = target + timedelta(seconds=offset)
                self.assertEqual(review_window_allows(target, at, live=True), allowed)
                self.assertEqual(review_window_allows(target, at, live=False), offset == 0)

    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = RunStore(self.temporary.name)

    def review(
        self,
        current: CandidateCase,
        previous: CandidateCase | None = None,
        reviewed_at=None,
        prepare_t20: bool = True,
    ):
        prior_case = make_case() if previous is None else previous
        current = make_t20_case(current) if prepare_t20 else current
        current_snapshot = current.snapshots[-1]
        default_time = max(TARGET_AT, current_snapshot.snapshot.recorded_at)
        return review_t20(
            prior_case,
            current,
            reviewed_at=default_time if reviewed_at is None else reviewed_at,
            run_id=RUN_ID,
            store=self.store,
        )

    def test_on_time_t20_state_is_reviewed_with_complete_receipt_and_audit(self) -> None:
        case = make_case()

        review = self.review(case, reviewed_at=TARGET_AT)

        self.assertIs(review.conclusion, T20Conclusion.STILL_STRONG)
        self.assertFalse(review.snapshot_3_late)
        self.assertEqual(review.projection_before, 33.0)
        self.assertEqual(review.projection_at_t20, 33.5)
        receipts = self.store.read_receipts(RUN_ID)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["event"], "T20_REVIEW")
        self.assertEqual(receipts[0]["result"], "STILL STRONG")
        self.assertEqual(receipts[0]["subject"], case.snapshots[-1].candidate_key)
        self.assertTrue(receipts[0]["event_key"])
        audit_path = self.store.run_directory(RUN_ID) / "t20-reviews.jsonl"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        self.assertEqual(audit["reason_codes"], [])
        self.assertEqual(audit["prior_status"], EvaluationStatus.QUALIFIED.value)
        self.assertEqual(audit["current_status"], EvaluationStatus.QUALIFIED.value)
        self.assertEqual(audit["projection"]["before"], 33.0)
        self.assertEqual(audit["projection"]["at_t20"], 33.5)
        self.assertTrue(audit["projection"]["changed"])
        self.assertTrue(review.readiness_passed)
        self.assertEqual(review.readiness_gaps, ())

    def test_late_snapshot_3_remains_late_and_is_not_retimed(self) -> None:
        case = make_case(late_snapshot_3=True)
        late_recorded_at = case.snapshots[-1].snapshot.recorded_at

        review = self.review(case, reviewed_at=late_recorded_at + timedelta(minutes=1))

        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.T20_CHECK_UNAVAILABLE, review.reason_codes)
        self.assertTrue(review.snapshot_3_late)
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "t20-reviews.jsonl").read_text(encoding="utf-8")
        )
        self.assertEqual(audit["snapshot_3_recorded_at"], late_recorded_at.isoformat())
        self.assertTrue(audit["snapshot_3_late"])

    def test_missed_snapshot_3_is_removed_without_backfill(self) -> None:
        complete = make_case()
        first, second = complete.snapshots[:2]
        missed = replace(
            complete,
            snapshots=(first, second),
            missed=(
                MissedSnapshot(
                    number=3,
                    candidate_id=first.candidate_id,
                    candidate_key=first.candidate_key,
                    event_id=first.event_id,
                    reason=ReasonCode.PROJECTION_OBSERVATION_MISSED,
                    recorded_at=first.event_start + timedelta(seconds=1),
                ),
            ),
        )

        review = self.review(
            missed,
            reviewed_at=first.event_start + timedelta(seconds=2),
        )

        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.PROJECTION_OBSERVATION_MISSED, review.reason_codes)
        self.assertEqual(len(review.current_audit.snapshots), 2)
        self.assertEqual(len(review.current_audit.missed_snapshots), 1)
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "t20-reviews.jsonl").read_text(encoding="utf-8")
        )
        self.assertEqual(len(audit["snapshots"]), 2)

    def test_review_after_tipoff_rejects_stale_t20_state(self) -> None:
        case = make_case()
        tipoff = case.snapshots[-1].event_start

        review = self.review(case, reviewed_at=tipoff + timedelta(seconds=1))

        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.T20_CHECK_UNAVAILABLE, review.reason_codes)

    def test_review_after_the_frozen_t20_target_cannot_be_positive(self) -> None:
        case = make_case()

        review = self.review(case, reviewed_at=TARGET_AT + timedelta(seconds=1))

        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.T20_CHECK_UNAVAILABLE, review.reason_codes)
        self.assertIn("target", " ".join(review.readiness_gaps).lower())

    def test_changed_event_identity_is_not_reviewed_as_the_prior_candidate(self) -> None:
        case = changed_event(make_case(), "different-event")

        review = self.review(case)

        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.SOURCE_CONFLICT_UNRESOLVED, review.reason_codes)

    def test_unauthorized_player_is_removed(self) -> None:
        review = self.review(make_case(name="Outside Universe Player"))

        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.PLAYER_IDENTITY_UNRESOLVED, review.reason_codes)
        self.assertIsNone(review.snapshot_3_late)
        self.assertIsNone(review.snapshot_3_recorded_at)

    def test_unauthorized_category_is_removed(self) -> None:
        review = self.review(make_case(category=Category.REBOUNDS_ASSISTS))

        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.CATEGORY_NOT_AUTHORIZED, review.reason_codes)

    def test_unauthorized_direction_is_removed(self) -> None:
        review = self.review(make_case(name="Mitchell Robinson", direction=Direction.HIGHER))

        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.CATEGORY_NOT_AUTHORIZED, review.reason_codes)

    def test_projection_change_is_reported_without_a_materiality_threshold(self) -> None:
        case = make_case(projections=(32.5, 33.0, 36.0))

        review = self.review(case)

        self.assertTrue(review.projection_changed)
        self.assertEqual(review.projection_before, 33.0)
        self.assertEqual(review.projection_at_t20, 36.0)
        self.assertFalse(hasattr(review, "score"))
        self.assertFalse(hasattr(review, "movement_threshold"))

    def test_evidence_and_context_deterioration_downgrades_qualified_candidate(self) -> None:
        original = make_case()
        evidence = tuple(
            replace(item, effect=EvidenceEffect.CONCERN) if item.evidence_id == "role" else item
            for item in original.evidence
        )
        assert original.judgment is not None
        judgment = replace(
            original.judgment,
            confidence=Confidence.MEDIUM,
            supporting_evidence_ids=("last8",),
            meaningful_risk_ids=("role", "blowout-risk"),
            rationale="T-20 role evidence is now concerning.",
        )
        current = replace(original, evidence=evidence, judgment=judgment)

        review = self.review(current)

        self.assertIs(review.current_audit.status, EvaluationStatus.QUALIFIED)
        self.assertIs(review.current_audit.confidence, Confidence.MEDIUM)
        self.assertIs(review.conclusion, T20Conclusion.DOWNGRADED)
        self.assertIn("role", review.changed_evidence_ids)
        self.assertTrue(review.context_changed)

    def test_candidate_that_becomes_unqualified_is_removed(self) -> None:
        original = make_case()
        critical_gap = EvidenceGap(
            kind=EvidenceKind.AVAILABILITY,
            reason=ReasonCode.AVAILABILITY_UNRESOLVED,
            significance=EvidenceSignificance.CRITICAL,
            detail="T-20 availability is unresolved.",
        )
        current = replace(original, gaps=(critical_gap,))

        review = self.review(current)

        self.assertIs(review.current_audit.status, EvaluationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.AVAILABILITY_UNRESOLVED, review.reason_codes)

    def test_candidate_remaining_qualified_is_retained(self) -> None:
        review = self.review(make_case())

        self.assertIs(review.current_audit.status, EvaluationStatus.QUALIFIED)
        self.assertIs(review.conclusion, T20Conclusion.STILL_STRONG)
        self.assertTrue(review.readiness_passed)

    def test_missing_t20_availability_context_fails_closed(self) -> None:
        case = make_t20_case(make_case(), availability=False)

        review = self.review(case, prepare_t20=False)

        self.assertIs(review.current_audit.status, EvaluationStatus.QUALIFIED)
        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.T20_CHECK_UNAVAILABLE, review.reason_codes)
        self.assertTrue(any("AVAILABILITY" in gap for gap in review.readiness_gaps))

    def test_stale_t20_availability_context_fails_closed(self) -> None:
        case = make_t20_case(make_case(), availability=False)
        stale_availability = make_evidence_item(
            case.snapshots[0].candidate_key,
            "stale-t20-availability",
            EvidenceKind.AVAILABILITY,
            effect=EvidenceEffect.NEUTRAL,
        )
        case = replace(case, evidence=(*case.evidence, stale_availability))

        review = self.review(case, prepare_t20=False)

        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertTrue(
            any("AVAILABILITY" in gap and "stale" in gap for gap in review.readiness_gaps)
        )

    def test_stale_cited_projection_movement_fails_t20_readiness(self) -> None:
        case = with_projection_movement_evidence(
            make_case(),
            current_at_t20=False,
        )

        review = self.review(case)

        self.assertIs(review.current_audit.status, EvaluationStatus.QUALIFIED)
        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.T20_CHECK_UNAVAILABLE, review.reason_codes)
        self.assertTrue(any("PROJECTION_MOVEMENT" in gap for gap in review.readiness_gaps))

    def test_current_cited_projection_movement_passes_t20_readiness(self) -> None:
        case = with_projection_movement_evidence(
            make_case(),
            current_at_t20=True,
        )

        review = self.review(case)

        self.assertIs(review.conclusion, T20Conclusion.STILL_STRONG)
        self.assertTrue(review.readiness_passed)
        self.assertFalse(any("PROJECTION_MOVEMENT" in gap for gap in review.readiness_gaps))

    def test_missing_t20_role_and_teammate_context_fails_closed(self) -> None:
        case = make_t20_case(make_case(), role_context=False)

        review = self.review(case, prepare_t20=False)

        self.assertIs(review.current_audit.status, EvaluationStatus.QUALIFIED)
        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertTrue(any("ROLE_MINUTES" in gap for gap in review.readiness_gaps))
        self.assertTrue(any("TEAMMATE_ABSENCE" in gap for gap in review.readiness_gaps))

    def test_missing_t20_game_context_fails_closed(self) -> None:
        case = make_t20_case(make_case(), game_context=False)

        review = self.review(case, prepare_t20=False)

        self.assertIs(review.current_audit.status, EvaluationStatus.QUALIFIED)
        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertTrue(any("game context" in gap.lower() for gap in review.readiness_gaps))

    def test_changed_m6_rationale_is_disclosed_as_a_context_change(self) -> None:
        case = make_case()
        assert case.judgment is not None
        case = replace(
            case,
            judgment=replace(case.judgment, rationale="Updated T-20 methodology rationale."),
        )

        review = self.review(case)

        self.assertIn("rationale", review.changed_judgment_fields)
        self.assertTrue(review.context_changed)

    def test_changed_m6_supporting_evidence_ids_are_disclosed(self) -> None:
        case = make_case()
        assert case.judgment is not None
        case = replace(
            case,
            judgment=replace(case.judgment, supporting_evidence_ids=("last8", "matchup")),
        )

        review = self.review(case)

        self.assertIn("supporting_evidence_ids", review.changed_judgment_fields)
        self.assertTrue(review.context_changed)

    def test_changed_m6_risk_evidence_ids_are_disclosed(self) -> None:
        case = make_case()
        evidence = tuple(
            replace(item, effect=EvidenceEffect.CONCERN) if item.evidence_id == "spread" else item
            for item in case.evidence
        )
        assert case.judgment is not None
        case = replace(
            case,
            evidence=evidence,
            judgment=replace(case.judgment, meaningful_risk_ids=("spread",)),
        )

        review = self.review(case)

        self.assertIn("meaningful_risk_ids", review.changed_judgment_fields)
        self.assertTrue(review.context_changed)

    def test_readiness_uses_no_numeric_freshness_or_selection_threshold(self) -> None:
        case = make_case(projections=(32.5, 33.0, 33.01))

        review = self.review(case)
        serialized = review.to_dict()

        self.assertIs(review.conclusion, T20Conclusion.STILL_STRONG)
        self.assertTrue(review.readiness_passed)
        self.assertIs(review.current_audit.confidence, Confidence.HIGH)
        self.assertNotIn("score", serialized)
        self.assertNotIn("weight", serialized)
        self.assertNotIn("freshness_threshold", serialized)
        self.assertNotIn("confidence_threshold", serialized)

    def test_prior_rejected_candidate_cannot_reenter_at_t20(self) -> None:
        prior = make_case()
        assert prior.judgment is not None
        prior = replace(
            prior,
            judgment=replace(
                prior.judgment,
                disposition=MethodologyDisposition.REJECT,
            ),
        )

        review = self.review(make_case(), previous=prior)

        self.assertIs(review.prior_audit.status, EvaluationStatus.REJECTED)
        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.INSUFFICIENT_SUPPORTING_EVIDENCE, review.reason_codes)

    def test_prior_insufficient_candidate_cannot_be_promoted_at_t20(self) -> None:
        prior = make_case(
            gaps=(
                EvidenceGap(
                    kind=EvidenceKind.AVAILABILITY,
                    reason=ReasonCode.AVAILABILITY_UNRESOLVED,
                    significance=EvidenceSignificance.CRITICAL,
                    detail="Prior availability evidence is unresolved.",
                ),
            )
        )

        review = self.review(make_case(), previous=prior)

        self.assertIs(review.prior_audit.status, EvaluationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.AVAILABILITY_UNRESOLVED, review.reason_codes)

    def test_prior_analysis_only_candidate_cannot_be_promoted_at_t20(self) -> None:
        prior = make_case()
        assert prior.judgment is not None
        prior = replace(
            prior,
            judgment=replace(
                prior.judgment,
                confidence=Confidence.LOW,
                disposition=MethodologyDisposition.ANALYSIS_ONLY,
            ),
        )

        review = self.review(make_case(), previous=prior)

        self.assertIs(review.prior_audit.status, EvaluationStatus.ANALYSIS_ONLY)
        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIn(ReasonCode.INSUFFICIENT_SUPPORTING_EVIDENCE, review.reason_codes)

    def test_live_t20_input_must_match_the_application_m5_ledger(self) -> None:
        with (
            TemporaryDirectory() as temporary_root,
            patch.object(
                storage_module,
                "APPLICATION_STORAGE_ROOT",
                Path(temporary_root),
            ),
        ):
            store, _workflow, records, _resolver = make_live_ledger(
                temporary_root,
                RUN_ID,
            )
            prior = make_case_from_m5_records(records, RUN_ID)
            forged = tuple(
                replace(
                    item,
                    provenance=replace(item.provenance, payload_hash="f" * 64),
                )
                if item.snapshot.number == 3
                else item
                for item in records
            )
            current = make_case_from_m5_records(forged, RUN_ID)

            review = review_t20(
                prior,
                current,
                reviewed_at=TARGET_AT,
                run_id=RUN_ID,
                store=store,
            )

        self.assertIs(review.conclusion, T20Conclusion.REMOVE_RECOMMENDED)
        self.assertIsNone(review.current_audit)
        self.assertIsNone(review.snapshot_3_late)
        self.assertIsNone(review.snapshot_3_recorded_at)
        self.assertIn(ReasonCode.T20_CHECK_UNAVAILABLE, review.reason_codes)

    def test_review_does_not_finalize_or_replace_a_candidate(self) -> None:
        review = self.review(make_case())
        run_directory = self.store.run_directory(RUN_ID)

        self.assertFalse(hasattr(review, "approved"))
        self.assertFalse(hasattr(review, "finalized"))
        self.assertFalse((run_directory / "candidates.json").exists())
        self.assertFalse((run_directory / "final.json").exists())
        self.assertEqual(
            {path.name for path in run_directory.iterdir()},
            {"receipts.jsonl", "t20-reviews.jsonl"},
        )


if __name__ == "__main__":
    unittest.main()
