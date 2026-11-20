import json
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast
from unittest.mock import patch

import fifth_pick.storage as storage_module
from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.evidence import EvidenceEffect, EvidenceGap, EvidenceKind, EvidenceSignificance
from fifth_pick.identity import IdentityResolver
from fifth_pick.methodology import (
    CandidateAudit,
    CandidateCase,
    Confidence,
    EvaluationStatus,
    MethodologyDisposition,
    MethodologyError,
    MethodologyJudgment,
    evaluate_candidate,
)
from fifth_pick.models import Category, Direction, ReasonCode
from fifth_pick.ranking import rank_candidates, write_candidates
from fifth_pick.registry import Registry
from fifth_pick.snapshots import (
    MissedSnapshot,
    SnapshotEvidence,
    SnapshotWorkflow,
    read_snapshot_ledger,
    snapshot_2_target,
)
from fifth_pick.sources.base import EvidenceMode
from fifth_pick.storage import RunStore
from tests.m6_support import make_case, make_evidence_item, make_evidence_set, make_judgment
from tests.test_snapshots import (
    MutableClock,
    make_board,
    make_projection,
)


def make_live_ledger(
    root: str,
    run_id: str,
    slots: tuple[int, ...] = (1, 2, 3),
) -> tuple[RunStore, SnapshotWorkflow, tuple[SnapshotEvidence, ...], IdentityResolver]:
    clock = MutableClock()
    registry = Registry.from_universe(load_configs().approved_universe)
    resolver = IdentityResolver(
        registry,
        provider_aliases={"Luka Doncic": ("luka-doncic",)},
    )
    store = RunStore(root)
    workflow = SnapshotWorkflow(store, resolver, AuthorizationGate(), clock=clock)
    first_at = clock.current
    offsets = {1: 0, 2: 80, 3: 158}
    for number in slots:
        observed_at = first_at + timedelta(minutes=offsets[number])
        clock.current = observed_at
        board = make_board(
            observed_at,
            make_projection(observed_at, player_name="Luka Doncic"),
        )
        object.__setattr__(board.provenance, "_evidence_mode", EvidenceMode.LIVE)
        workflow.collect(run_id, number, board)
    return store, workflow, workflow.read(run_id), resolver


def make_case_from_m5_records(
    snapshots: tuple[SnapshotEvidence, ...],
    run_id: str,
    *,
    missed: tuple[MissedSnapshot, ...] = (),
) -> CandidateCase:
    evidence = make_evidence_set(snapshots[0].candidate_key)
    return CandidateCase(
        snapshots=snapshots,
        missed=missed,
        evidence=evidence,
        judgment=make_judgment(evidence),
        snapshot_run_id=run_id,
    )


class MethodologyTests(unittest.TestCase):
    def test_methodology_judgment_requires_a_nonempty_rationale(self) -> None:
        with self.assertRaises(MethodologyError):
            MethodologyJudgment(
                disposition=MethodologyDisposition.QUALIFY,
                confidence=Confidence.HIGH,
                rationale=" ",
                supporting_evidence_ids=("last8", "role"),
                meaningful_risk_ids=("blowout-risk",),
                sufficient_evidence=True,
            )

    def test_candidate_requires_all_three_snapshot_records(self) -> None:
        case = make_case()
        incomplete = replace(case, snapshots=case.snapshots[:2])

        audit = evaluate_candidate(incomplete)

        self.assertIs(audit.status, EvaluationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIsNone(audit.confidence)
        self.assertIn(ReasonCode.PROJECTION_OBSERVATION_MISSED, audit.exclusions)

    def test_candidate_audit_serializes_validated_missed_marker(self) -> None:
        case = make_case()
        missed = MissedSnapshot(
            number=3,
            candidate_id=case.snapshots[0].candidate_id,
            candidate_key=case.snapshots[0].candidate_key,
            event_id=case.snapshots[0].event_id,
            reason=ReasonCode.PROJECTION_OBSERVATION_MISSED,
            recorded_at=case.snapshots[1].event_start + timedelta(minutes=1),
        )

        serialized = evaluate_candidate(
            replace(case, snapshots=case.snapshots[:2], missed=(missed,))
        ).to_dict()

        missed_markers = serialized["missed_snapshots"]
        self.assertIsInstance(missed_markers, list)
        if isinstance(missed_markers, list):
            marker = missed_markers[0]
            self.assertIsInstance(marker, dict)
            if isinstance(marker, dict):
                self.assertEqual(marker["number"], 3)
                self.assertEqual(marker["reason"], "PROJECTION_OBSERVATION_MISSED")

    def test_incomplete_unauthorized_candidate_is_blocked_before_gap_output(self) -> None:
        gap = EvidenceGap(
            kind=EvidenceKind.AVAILABILITY,
            reason=ReasonCode.AVAILABILITY_UNRESOLVED,
            significance=EvidenceSignificance.CRITICAL,
            detail="Synthetic unresolved availability.",
        )
        case = make_case(name="Outside Universe Player", gaps=(gap,))
        incomplete = replace(case, snapshots=case.snapshots[:2])

        audit = evaluate_candidate(incomplete)

        self.assertIs(audit.status, EvaluationStatus.BLOCKED)
        self.assertEqual(audit.gaps, ())
        self.assertIn(ReasonCode.PLAYER_IDENTITY_UNRESOLVED, audit.exclusions)

    def test_candidate_rejects_snapshot_recording_time_regression(self) -> None:
        case = make_case()
        first, second, third = case.snapshots
        late_first = replace(
            first,
            snapshot=replace(
                first.snapshot,
                recorded_at=first.snapshot.recorded_at + timedelta(minutes=90),
            ),
        )
        early_second = replace(
            second,
            snapshot=replace(
                second.snapshot,
                recorded_at=first.snapshot.recorded_at + timedelta(minutes=85),
            ),
        )

        with self.assertRaises(MethodologyError):
            evaluate_candidate(replace(case, snapshots=(late_first, early_second, third)))

    def test_candidate_rejects_inconsistent_event_start_across_snapshots(self) -> None:
        case = make_case()
        first, second, third = case.snapshots
        later_start = first.event_start + timedelta(minutes=5)
        inconsistent = replace(
            case,
            snapshots=(
                replace(first, event_start=later_start),
                replace(second, event_start=later_start),
                third,
            ),
        )

        with self.assertRaises(MethodologyError):
            evaluate_candidate(inconsistent)

    def test_candidate_rejects_snapshot_2_target_not_derived_from_snapshot_1(self) -> None:
        case = make_case()
        first, second, third = case.snapshots
        self.assertEqual(
            second.target_at,
            snapshot_2_target(first.snapshot.observation.retrieved_at, first.event_start),
        )
        assert second.target_at is not None
        inconsistent = replace(
            case,
            snapshots=(
                first,
                replace(second, target_at=second.target_at + timedelta(minutes=1)),
                third,
            ),
        )

        with self.assertRaises(MethodologyError):
            evaluate_candidate(inconsistent)

    def test_candidate_rejects_unapproved_snapshot_source_and_event_reference(self) -> None:
        case = make_case()
        snapshots = []
        for item in case.snapshots:
            observation = replace(item.snapshot.observation, source="caller-source")
            snapshots.append(
                replace(
                    item,
                    snapshot=replace(item.snapshot, observation=observation),
                    provenance=replace(item.provenance, source="caller-source"),
                )
            )
        with self.assertRaises(MethodologyError):
            evaluate_candidate(replace(case, snapshots=tuple(snapshots)))

        first = case.snapshots[0]
        mismatched_reference = replace(
            first,
            provenance=replace(
                first.provenance,
                reference="the-odds-api-us-dfs:event:another-event",
            ),
        )
        with self.assertRaises(MethodologyError):
            evaluate_candidate(replace(case, snapshots=(mismatched_reference, *case.snapshots[1:])))

    def test_live_snapshot_requires_a_matching_m5_ledger_path(self) -> None:
        case = make_case()
        live_snapshots = tuple(
            replace(
                item,
                evidence_mode=EvidenceMode.LIVE,
                provenance=replace(
                    item.provenance,
                    access_method="https-get-x-api-key-header",
                ),
            )
            for item in case.snapshots
        )

        with self.assertRaises(MethodologyError):
            evaluate_candidate(replace(case, snapshots=live_snapshots))

    def test_live_snapshot_must_equal_the_validated_m5_ledger_record(self) -> None:
        run_id = "m6-ledger-origin-test"
        with TemporaryDirectory() as temporary_root:
            clock = MutableClock()
            registry = Registry.from_universe(load_configs().approved_universe)
            resolver = IdentityResolver(
                registry,
                provider_aliases={"Luka Doncic": ("luka-doncic",)},
            )
            workflow = SnapshotWorkflow(
                RunStore(temporary_root),
                resolver,
                AuthorizationGate(),
                clock=clock,
            )
            first_at = clock.current
            workflow.collect(
                run_id,
                1,
                make_board(first_at, make_projection(first_at, player_name="Luka Doncic")),
            )

            second_at = first_at + timedelta(minutes=80)
            clock.current = second_at
            workflow.collect(
                run_id,
                2,
                make_board(second_at, make_projection(second_at, player_name="Luka Doncic")),
            )

            third_at = first_at + timedelta(minutes=158)
            clock.current = third_at
            workflow.collect(
                run_id,
                3,
                make_board(third_at, make_projection(third_at, player_name="Luka Doncic")),
            )

            persisted = workflow.read(run_id)
            claimed_live = tuple(
                replace(
                    item,
                    evidence_mode=EvidenceMode.LIVE,
                    provenance=replace(
                        item.provenance,
                        access_method="https-get-x-api-key-header",
                    ),
                )
                for item in persisted
            )
            self.assertTrue(all(item.evidence_mode is EvidenceMode.FIXTURE for item in persisted))
            self.assertTrue(all(item.evidence_mode is EvidenceMode.LIVE for item in claimed_live))
            self.assertNotEqual(claimed_live, persisted)
            evidence = make_evidence_set(persisted[0].candidate_key)
            forged = replace(
                make_case(),
                snapshots=claimed_live,
                evidence=evidence,
                judgment=make_judgment(evidence),
                snapshot_run_id=run_id,
            )

            with (
                patch.object(
                    storage_module,
                    "APPLICATION_STORAGE_ROOT",
                    Path(temporary_root),
                ),
                self.assertRaises(MethodologyError),
            ):
                evaluate_candidate(forged)

    def test_legitimate_live_snapshot_from_m5_ledger_is_accepted(self) -> None:
        run_id = "m6-live-ledger-valid-test"
        with TemporaryDirectory() as temporary_root:
            _store, _workflow, records, _ = make_live_ledger(temporary_root, run_id)
            case = make_case_from_m5_records(records, run_id)
            with patch.object(
                storage_module,
                "APPLICATION_STORAGE_ROOT",
                Path(temporary_root),
            ):
                try:
                    result = rank_candidates((case,))
                except MethodologyError:
                    self.fail("application-owned M5 storage did not resolve its recorded run")

        self.assertIs(result.audits[0].status, EvaluationStatus.QUALIFIED)
        self.assertEqual(result.audits[0].snapshot_run_id, run_id)

    def test_arbitrary_runstore_cannot_authorize_live_candidate(self) -> None:
        run_id = "m6-arbitrary-store-test"
        with TemporaryDirectory() as temporary_root:
            store, _workflow, records, _ = make_live_ledger(temporary_root, run_id)
            case = make_case_from_m5_records(records, run_id)

            with self.assertRaises(TypeError):
                cast(Any, rank_candidates)((case,), snapshot_store=store)

    def test_schema_valid_ledger_outside_application_root_is_not_authoritative(self) -> None:
        run_id = "m6-outside-root-test"
        with TemporaryDirectory() as fabricated_root, TemporaryDirectory() as trusted_root:
            store, _workflow, records, _ = make_live_ledger(fabricated_root, run_id)
            fabricated = tuple(
                replace(
                    item,
                    provenance=replace(item.provenance, payload_hash="b" * 64),
                )
                for item in records
            )
            ledger_path = store.run_directory(run_id) / "snapshots" / "ledger.jsonl"
            ledger_path.write_text(
                "".join(
                    json.dumps(item.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
                    for item in fabricated
                ),
                encoding="utf-8",
            )
            self.assertEqual(read_snapshot_ledger(store, run_id), fabricated)
            case = make_case_from_m5_records(fabricated, run_id)
            with (
                patch.object(
                    storage_module,
                    "APPLICATION_STORAGE_ROOT",
                    Path(trusted_root),
                ),
                self.assertRaises(MethodologyError),
            ):
                write_candidates((case,), store, "m6-fake-ledger-output")
            self.assertFalse(
                (store.run_directory("m6-fake-ledger-output") / "candidates.json").exists()
            )

    def test_mismatched_case_run_id_cannot_reuse_another_m5_ledger(self) -> None:
        run_id = "m6-mismatched-run-test"
        with TemporaryDirectory() as temporary_root:
            _store, _workflow, records, _ = make_live_ledger(temporary_root, run_id)
            case = make_case_from_m5_records(records, "another-m5-run")
            with (
                patch.object(
                    storage_module,
                    "APPLICATION_STORAGE_ROOT",
                    Path(temporary_root),
                ),
                self.assertRaises(MethodologyError),
            ):
                rank_candidates((case,))

    def test_live_m5_ledger_requires_matching_snapshot_receipts(self) -> None:
        run_id = "m6-live-receipt-binding-test"
        with TemporaryDirectory() as temporary_root:
            store, _workflow, records, _ = make_live_ledger(temporary_root, run_id)
            case = make_case_from_m5_records(records, run_id)
            receipts = tuple(
                receipt
                for receipt in store.read_receipts(run_id)
                if receipt.get("event_key") != f"snapshot-accepted-2-{records[1].candidate_key}"
            )
            store.receipts_path(run_id).write_text(
                "".join(
                    json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
                    for receipt in receipts
                ),
                encoding="utf-8",
            )
            with (
                patch.object(
                    storage_module,
                    "APPLICATION_STORAGE_ROOT",
                    Path(temporary_root),
                ),
                self.assertRaises(MethodologyError),
            ):
                rank_candidates((case,))

    def test_fixture_candidate_uses_offline_path_without_m5_store(self) -> None:
        with (
            TemporaryDirectory() as temporary_root,
            patch.object(
                storage_module,
                "APPLICATION_STORAGE_ROOT",
                Path(temporary_root),
            ),
        ):
            result = rank_candidates((make_case(),))

        self.assertIs(result.audits[0].status, EvaluationStatus.QUALIFIED)
        self.assertIsNone(result.audits[0].snapshot_run_id)

    def test_overridden_snapshot_workflow_read_cannot_authenticate_live_records(self) -> None:
        run_id = "m6-live-read-override-test"
        with TemporaryDirectory() as temporary_root:
            _store, workflow, records, _ = make_live_ledger(temporary_root, run_id)
            forged = tuple(
                replace(
                    item,
                    provenance=replace(item.provenance, payload_hash="f" * 64),
                )
                for item in records
            )
            workflow.read = lambda run_id: forged if run_id else ()
            case = make_case_from_m5_records(forged, run_id)

            with (
                patch.object(
                    storage_module,
                    "APPLICATION_STORAGE_ROOT",
                    Path(temporary_root),
                ),
                self.assertRaises(MethodologyError),
            ):
                evaluate_candidate(case)

    def test_overridden_snapshot_workflow_read_missed_cannot_authenticate_marker(self) -> None:
        run_id = "m6-live-missed-override-test"
        with TemporaryDirectory() as temporary_root:
            _store, workflow, records, _ = make_live_ledger(
                temporary_root,
                run_id,
                slots=(1, 2),
            )
            first = records[0]
            marker = MissedSnapshot(
                number=3,
                candidate_id=first.candidate_id,
                candidate_key=first.candidate_key,
                event_id=first.event_id,
                reason=ReasonCode.PROJECTION_OBSERVATION_MISSED,
                recorded_at=first.event_start + timedelta(minutes=1),
            )
            workflow.read_missed = lambda run_id: (marker,) if run_id else ()
            case = make_case_from_m5_records(records, run_id, missed=(marker,))

            with (
                patch.object(
                    storage_module,
                    "APPLICATION_STORAGE_ROOT",
                    Path(temporary_root),
                ),
                self.assertRaises(MethodologyError),
            ):
                evaluate_candidate(case)

    def test_mutated_snapshot_workflow_read_state_cannot_authenticate_live_records(self) -> None:
        run_id = "m6-live-read-state-override-test"
        with TemporaryDirectory() as temporary_root:
            _store, workflow, records, _ = make_live_ledger(temporary_root, run_id)
            forged = tuple(
                replace(
                    item,
                    provenance=replace(item.provenance, payload_hash="e" * 64),
                )
                for item in records
            )
            workflow._read_entries = lambda run_id: list(forged) if run_id else []
            case = make_case_from_m5_records(forged, run_id)

            with (
                patch.object(
                    storage_module,
                    "APPLICATION_STORAGE_ROOT",
                    Path(temporary_root),
                ),
                self.assertRaises(MethodologyError),
            ):
                evaluate_candidate(case)

    def test_fake_snapshot_workflow_subclass_cannot_authenticate_live_records(self) -> None:
        run_id = "m6-live-workflow-subclass-test"
        with TemporaryDirectory() as temporary_root:
            store, workflow, records, resolver = make_live_ledger(temporary_root, run_id)
            forged = tuple(
                replace(
                    item,
                    provenance=replace(item.provenance, payload_hash="d" * 64),
                )
                for item in records
            )

            class ForgedWorkflow(SnapshotWorkflow):
                def read(self, run_id: str) -> tuple[SnapshotEvidence, ...]:
                    _ = run_id
                    return forged

                def read_missed(self, run_id: str) -> tuple[MissedSnapshot, ...]:
                    _ = run_id
                    return ()

            fake = ForgedWorkflow(store, resolver, AuthorizationGate())
            case = make_case_from_m5_records(forged, run_id)

            with self.assertRaises(TypeError):
                cast(Any, evaluate_candidate)(case, snapshot_workflow=fake)

    def test_candidate_blocks_provider_excerpt_for_different_player(self) -> None:
        case = make_case()
        first, second, third = case.snapshots
        mismatched_first = replace(
            first,
            source_excerpt={**first.source_excerpt, "provider_player_name": "Jayson Tatum"},
        )

        audit = evaluate_candidate(replace(case, snapshots=(mismatched_first, second, third)))

        self.assertIs(audit.status, EvaluationStatus.BLOCKED)
        self.assertIn(ReasonCode.PLAYER_IDENTITY_UNRESOLVED, audit.exclusions)
        self.assertEqual(audit.evidence, ())
        self.assertEqual(audit.gaps, ())

    def test_candidate_rejects_missed_marker_with_mismatched_identity(self) -> None:
        case = make_case()
        incomplete = replace(
            case,
            snapshots=case.snapshots[:2],
            missed=(
                MissedSnapshot(
                    number=3,
                    candidate_id="different-player",
                    candidate_key=case.snapshots[0].candidate_key,
                    event_id=case.snapshots[0].event_id,
                    reason=ReasonCode.PROJECTION_OBSERVATION_MISSED,
                    recorded_at=case.snapshots[1].snapshot.recorded_at,
                ),
            ),
        )

        with self.assertRaises(MethodologyError):
            evaluate_candidate(incomplete)

    def test_candidate_rejects_missed_marker_before_adjacent_snapshot(self) -> None:
        case = make_case()
        missed = MissedSnapshot(
            number=3,
            candidate_id=case.snapshots[0].candidate_id,
            candidate_key=case.snapshots[0].candidate_key,
            event_id=case.snapshots[0].event_id,
            reason=ReasonCode.PROJECTION_OBSERVATION_MISSED,
            recorded_at=case.snapshots[0].snapshot.recorded_at,
        )
        incomplete = replace(case, snapshots=case.snapshots[:2], missed=(missed,))

        with self.assertRaises(MethodologyError):
            evaluate_candidate(incomplete)

    def test_candidate_rejects_conflicting_duplicate_missed_markers(self) -> None:
        case = make_case()
        missed = MissedSnapshot(
            number=3,
            candidate_id=case.snapshots[0].candidate_id,
            candidate_key=case.snapshots[0].candidate_key,
            event_id=case.snapshots[0].event_id,
            reason=ReasonCode.PROJECTION_OBSERVATION_MISSED,
            recorded_at=case.snapshots[1].snapshot.recorded_at + timedelta(minutes=1),
        )
        conflicting = replace(missed, recorded_at=missed.recorded_at + timedelta(minutes=1))
        incomplete = replace(case, snapshots=case.snapshots[:2], missed=(missed, conflicting))

        with self.assertRaises(MethodologyError):
            evaluate_candidate(incomplete)

    def test_missing_evidence_produces_named_reason(self) -> None:
        gap = EvidenceGap(
            kind=EvidenceKind.AVAILABILITY,
            reason=ReasonCode.AVAILABILITY_UNRESOLVED,
            significance=EvidenceSignificance.CRITICAL,
            detail="Availability could materially change this candidate.",
        )
        case = make_case(gaps=(gap,))

        audit = evaluate_candidate(case)

        self.assertIsInstance(audit, CandidateAudit)
        self.assertIs(audit.status, EvaluationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn(ReasonCode.AVAILABILITY_UNRESOLVED, audit.exclusions)
        self.assertEqual(audit.gaps, (gap,))

    def test_last8_h2h_and_game_environment_are_recorded(self) -> None:
        audit = evaluate_candidate(make_case())

        self.assertIsInstance(audit, CandidateAudit)
        summaries = {summary.kind: summary for summary in audit.history_summaries}
        last8 = summaries[EvidenceKind.LAST_8]
        h2h = summaries[EvidenceKind.SAME_SEASON_H2H]
        self.assertEqual(last8.sample_count, 8)
        self.assertEqual(audit.candidate.projection, 33.5)
        self.assertEqual((last8.higher_count, last8.lower_count), (4, 4))
        self.assertEqual(h2h.sample_count, 1)
        self.assertEqual(h2h.favorable_count, 1)
        kinds = {item.kind for item in audit.evidence}
        self.assertIn(EvidenceKind.GAME_TOTAL, kinds)
        self.assertIn(EvidenceKind.POINT_SPREAD, kinds)

    def test_evidence_order_does_not_change_canonical_audit(self) -> None:
        case = make_case()

        original = evaluate_candidate(case).to_dict()
        reordered = evaluate_candidate(
            replace(case, evidence=tuple(reversed(case.evidence)))
        ).to_dict()

        self.assertEqual(reordered, original)

    def test_duplicate_history_context_kinds_fail_closed(self) -> None:
        case = make_case()
        duplicates = []
        for kind in (
            EvidenceKind.MATCHUP,
            EvidenceKind.LAST_8,
            EvidenceKind.SAME_SEASON_H2H,
        ):
            source = next(item for item in case.evidence if item.kind is kind)
            duplicate = replace(source, evidence_id=f"duplicate-{kind.value.lower()}")
            if kind is EvidenceKind.MATCHUP:
                duplicate = replace(
                    duplicate, facts={"season": "different-season", "opponent": "Elsewhere"}
                )
            duplicates.append(duplicate)
        duplicated_case = replace(case, evidence=(*case.evidence, *duplicates))

        audit = evaluate_candidate(duplicated_case)

        self.assertIs(audit.status, EvaluationStatus.INSUFFICIENT_EVIDENCE)

    def test_high_confidence_requires_distinct_underlying_support_signals(self) -> None:
        case = make_case()
        role = next(item for item in case.evidence if item.evidence_id == "role")
        duplicate = replace(role, evidence_id="role-copy", kind=EvidenceKind.OTHER)
        assert case.judgment is not None
        judgment = replace(
            case.judgment,
            supporting_evidence_ids=("role", "role-copy"),
        )
        duplicated_signal_case = replace(
            case,
            evidence=(*case.evidence, duplicate),
            judgment=judgment,
        )

        with self.assertRaises(MethodologyError):
            evaluate_candidate(duplicated_signal_case)

    def test_missing_same_season_h2h_is_disclosed_as_minor_gap(self) -> None:
        case = make_case()
        evidence = tuple(
            item for item in case.evidence if item.kind is not EvidenceKind.SAME_SEASON_H2H
        )

        audit = evaluate_candidate(replace(case, evidence=evidence))

        h2h_gap = next(gap for gap in audit.gaps if gap.kind is EvidenceKind.SAME_SEASON_H2H)
        self.assertIs(h2h_gap.significance, EvidenceSignificance.MINOR)
        self.assertIn("not supplied", h2h_gap.detail)

    def test_incomplete_last8_is_disclosed_as_minor_gap(self) -> None:
        case = make_case()
        evidence = tuple(
            replace(item, samples=item.samples[:5]) if item.kind is EvidenceKind.LAST_8 else item
            for item in case.evidence
        )

        audit = evaluate_candidate(replace(case, evidence=evidence))

        last8_gap = next(gap for gap in audit.gaps if gap.kind is EvidenceKind.LAST_8)
        self.assertIs(last8_gap.significance, EvidenceSignificance.MINOR)
        self.assertIn("5", last8_gap.detail)

    def test_senior_lower_requires_strong_contextual_support(self) -> None:
        case = make_case(
            name="Luka Doncic",
            direction=Direction.LOWER,
        )

        audit = evaluate_candidate(case)

        self.assertIsInstance(audit, CandidateAudit)
        self.assertIs(audit.status, EvaluationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn(ReasonCode.INSUFFICIENT_SUPPORTING_EVIDENCE, audit.exclusions)

    def test_foul_trouble_is_not_an_automatic_medium_cap(self) -> None:
        snapshots = make_case(name="Karl-Anthony Towns").snapshots
        key = snapshots[0].candidate_key
        evidence = make_evidence_set(key, include_foul_trouble=True)
        case = make_case(
            name="Karl-Anthony Towns",
            evidence=evidence,
        )

        audit = evaluate_candidate(case)

        self.assertIsInstance(audit, CandidateAudit)
        self.assertTrue(audit.foul_trouble)
        self.assertIs(audit.confidence, Confidence.HIGH)
        self.assertIn("FOUL_TROUBLE_CAUTION", audit.rules_applied)

    def test_methodology_uses_no_numeric_confidence_weights(self) -> None:
        audit = evaluate_candidate(make_case())

        self.assertIsInstance(audit, CandidateAudit)
        self.assertFalse(hasattr(audit, "score"))
        self.assertFalse(hasattr(audit, "confidence_weight"))
        self.assertIn("NO_NUMERIC_CONFIDENCE_WEIGHTS", audit.rules_applied)

    def test_trust_tier_does_not_authorize_candidate(self) -> None:
        case = make_case(
            name="Paolo Banchero",
            category=Category.PRA,
            direction=Direction.HIGHER,
        )

        audit = evaluate_candidate(case)

        self.assertIsInstance(audit, CandidateAudit)
        self.assertIs(audit.status, EvaluationStatus.BLOCKED)
        self.assertIn(ReasonCode.CATEGORY_NOT_AUTHORIZED, audit.exclusions)
        self.assertEqual(audit.trust_labels, ())

    def test_blocked_identity_is_not_reported_as_resolved_in_audit(self) -> None:
        audit = evaluate_candidate(make_case(name="Outside Universe Player"))

        serialized = audit.to_dict()
        stages = serialized["stages"]

        self.assertIsInstance(stages, dict)
        if isinstance(stages, dict):
            self.assertEqual(stages["identity"], "UNRESOLVED")
            self.assertEqual(stages["authorization"], "BLOCKED")
            self.assertEqual(stages["methodology"], "NOT_RUN")

    def test_candidate_audit_trail_is_complete(self) -> None:
        audit = evaluate_candidate(make_case())
        self.assertIsInstance(audit, CandidateAudit)
        serialized = audit.to_dict()

        self.assertEqual(serialized["candidate_key"], audit.candidate_key)
        self.assertTrue(serialized["evidence"])
        stages = serialized["stages"]
        self.assertIsInstance(stages, dict)
        if isinstance(stages, dict):
            self.assertIn("authorization", stages)
            self.assertIn("methodology", stages)
        self.assertTrue(serialized["methodology_rationale"])
        self.assertTrue(serialized["rules_applied"])

    def test_candidate_audit_discloses_validated_snapshot_path_and_late_state(self) -> None:
        case = make_case(late_snapshot_3=True)

        serialized = evaluate_candidate(case).to_dict()

        snapshots = serialized["snapshots"]
        self.assertIsInstance(snapshots, list)
        if isinstance(snapshots, list):
            self.assertEqual(
                [item["observation"]["projection"] for item in snapshots],
                [32.5, 33.0, 33.5],
            )
            self.assertTrue(snapshots[2]["late"])
            self.assertEqual(
                snapshots[2]["provenance"]["payload_hash"],
                case.snapshots[2].provenance.payload_hash,
            )

    def test_candidate_audit_redacts_rationale_and_gap_detail(self) -> None:
        case = make_case()
        assert case.judgment is not None
        secret_evidence_id = "https://example.test/evidence?apiKey=evidence-id-secret"
        evidence = tuple(
            replace(item, evidence_id=secret_evidence_id) if item.evidence_id == "last8" else item
            for item in case.evidence
        )
        judgment = replace(
            case.judgment,
            rationale="Context at https://example.test/report?apiKey=rationale-secret.",
            supporting_evidence_ids=(secret_evidence_id, "role"),
        )
        gap = EvidenceGap(
            kind=EvidenceKind.GENERAL_CONTEXT,
            reason=ReasonCode.INSUFFICIENT_SUPPORTING_EVIDENCE,
            significance=EvidenceSignificance.MINOR,
            detail="See https://example.test/gap?token=gap-secret.",
        )
        case = replace(case, evidence=evidence, judgment=judgment, gaps=(gap,))

        serialized = json.dumps(evaluate_candidate(case).to_dict())

        self.assertNotIn("rationale-secret", serialized)
        self.assertNotIn("gap-secret", serialized)
        self.assertNotIn("evidence-id-secret", serialized)

    def test_critical_gap_overrides_qualifying_judgment(self) -> None:
        gap = EvidenceGap(
            kind=EvidenceKind.ROLE_MINUTES,
            reason=ReasonCode.ROLE_OR_MINUTES_UNRESOLVED,
            significance=EvidenceSignificance.CRITICAL,
            detail="Opportunity is unresolved.",
        )
        case = make_case(gaps=(gap,))

        audit = evaluate_candidate(case)

        self.assertIsInstance(audit, CandidateAudit)
        self.assertIs(audit.status, EvaluationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIsNone(audit.confidence)

    def test_high_confidence_requires_multiple_important_aligned_signals(self) -> None:
        evidence = make_evidence_set(make_case().snapshots[0].candidate_key)
        judgment = MethodologyJudgment(
            disposition=MethodologyDisposition.QUALIFY,
            confidence=Confidence.HIGH,
            rationale="Only one signal is cited.",
            supporting_evidence_ids=("last8",),
            meaningful_risk_ids=(),
            sufficient_evidence=True,
        )

        with self.assertRaises(MethodologyError):
            evaluate_candidate(make_case(evidence=evidence, judgment=judgment))

    def test_high_confidence_cannot_ignore_a_meaningful_evidence_gap(self) -> None:
        gap = EvidenceGap(
            kind=EvidenceKind.MATCHUP,
            reason=ReasonCode.SOURCE_CONFLICT_UNRESOLVED,
            significance=EvidenceSignificance.MEANINGFUL,
            detail="A material matchup conflict remains unresolved.",
        )

        with self.assertRaises(MethodologyError):
            evaluate_candidate(make_case(gaps=(gap,)))

    def test_medium_confidence_requires_a_cited_meaningful_risk(self) -> None:
        evidence = make_evidence_set(make_case().snapshots[0].candidate_key)
        judgment = MethodologyJudgment(
            disposition=MethodologyDisposition.QUALIFY,
            confidence=Confidence.MEDIUM,
            rationale="No meaningful conflict is cited.",
            supporting_evidence_ids=("last8", "role"),
            meaningful_risk_ids=(),
            sufficient_evidence=True,
        )

        with self.assertRaises(MethodologyError):
            evaluate_candidate(make_case(evidence=evidence, judgment=judgment))

    def test_senior_lower_can_qualify_with_cited_context_and_disclosure(self) -> None:
        key = make_case(name="Luka Doncic", direction=Direction.LOWER).snapshots[0].candidate_key
        evidence = (
            make_evidence_item(
                key,
                "blowout-support",
                EvidenceKind.BLOWOUT_RISK,
                facts={"risk": "synthetic blowout supports reduced minutes"},
            ),
            make_evidence_item(
                key,
                "role",
                EvidenceKind.ROLE_MINUTES,
                facts={"role": "synthetic secure starter"},
            ),
            make_evidence_item(
                key,
                "meaningful-risk",
                EvidenceKind.MATCHUP,
                effect=EvidenceEffect.CONCERN,
                significance=EvidenceSignificance.MEANINGFUL,
            ),
        )
        judgment = MethodologyJudgment(
            disposition=MethodologyDisposition.QUALIFY,
            confidence=Confidence.MEDIUM,
            rationale="Cited context supports the difficult Senior Lower direction.",
            supporting_evidence_ids=("blowout-support", "role"),
            meaningful_risk_ids=("meaningful-risk",),
            sufficient_evidence=True,
            senior_lower_support_ids=("blowout-support",),
            senior_lower_disclosure="Blowout risk may reduce fourth-quarter minutes.",
        )

        audit = evaluate_candidate(
            make_case(
                name="Luka Doncic",
                direction=Direction.LOWER,
                evidence=evidence,
                judgment=judgment,
            )
        )

        self.assertIsInstance(audit, CandidateAudit)
        self.assertIs(audit.status, EvaluationStatus.QUALIFIED)
        self.assertIs(audit.confidence, Confidence.MEDIUM)
        self.assertIn("SENIOR_LOWER_CONTEXT_REQUIRED", audit.rules_applied)


if __name__ == "__main__":
    unittest.main()
