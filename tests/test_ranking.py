import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any, cast

from fifth_pick.evidence import (
    EvidenceEffect,
    EvidenceGap,
    EvidenceItem,
    EvidenceKind,
    EvidenceSignificance,
)
from fifth_pick.methodology import (
    AuditEvidenceMode,
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
from fifth_pick.ranking import NearTieDecision, RankingError, rank_candidates, write_candidates
from fifth_pick.registry import canonical_player_id
from fifth_pick.storage import RunStore
from tests.m6_support import make_case as make_base_case
from tests.m6_support import make_judgment


def make_case(
    name: str = "Luka Doncic",
    *,
    confidence: Confidence = Confidence.HIGH,
    direction: Direction = Direction.HIGHER,
    category: Category = Category.POINTS,
    disposition: MethodologyDisposition = MethodologyDisposition.QUALIFY,
    evidence: tuple[EvidenceItem, ...] | None = None,
    gaps: tuple[EvidenceGap, ...] = (),
    role_effect: EvidenceEffect = EvidenceEffect.SUPPORTS,
    projections: tuple[float, float, float] = (32.5, 33.0, 33.5),
    late_snapshot_3: bool = False,
) -> CandidateCase:
    case = make_base_case(
        name=name,
        category=category,
        direction=direction,
        evidence=evidence,
        gaps=gaps,
        projections=projections,
        late_snapshot_3=late_snapshot_3,
    )
    candidate_evidence = case.evidence
    if role_effect is not EvidenceEffect.SUPPORTS:
        candidate_evidence = tuple(
            replace(item, effect=role_effect) if item.evidence_id == "role" else item
            for item in candidate_evidence
        )
    actual_senior = canonical_player_id(name) in {
        canonical_player_id("Luka Doncic"),
        canonical_player_id("Victor Wembanyama"),
        canonical_player_id("Nikola Jokic"),
        canonical_player_id("Stephen Curry"),
        canonical_player_id("Jayson Tatum"),
        canonical_player_id("Devin Booker"),
        canonical_player_id("Jalen Brunson"),
        canonical_player_id("Tyrese Maxey"),
        canonical_player_id("Joel Embiid"),
        canonical_player_id("Kawhi Leonard"),
        canonical_player_id("Donovan Mitchell"),
        canonical_player_id("Kevin Durant"),
        canonical_player_id("Giannis Antetokounmpo"),
        canonical_player_id("Anthony Davis"),
        canonical_player_id("Anthony Edwards"),
        canonical_player_id("Shai Gilgeous-Alexander"),
        canonical_player_id("Damian Lillard"),
        canonical_player_id("Deni Avdija"),
    }
    if actual_senior and direction is Direction.LOWER:
        candidate_evidence = tuple(
            replace(item, effect=EvidenceEffect.SUPPORTS)
            if item.evidence_id == "blowout-risk"
            else replace(item, effect=EvidenceEffect.CONCERN)
            if item.evidence_id == "spread"
            else item
            for item in candidate_evidence
        )
    supporting_ids = tuple(
        item.evidence_id
        for item in candidate_evidence
        if item.effect is EvidenceEffect.SUPPORTS
        and item.significance in (EvidenceSignificance.IMPORTANT, EvidenceSignificance.MEANINGFUL)
    )
    risk_ids = tuple(
        item.evidence_id
        for item in candidate_evidence
        if item.effect in (EvidenceEffect.CONCERN, EvidenceEffect.CONFLICT)
        and item.significance in (EvidenceSignificance.MEANINGFUL, EvidenceSignificance.CRITICAL)
    )
    judgment = make_judgment(
        candidate_evidence,
        confidence=confidence,
        disposition=disposition,
        senior_lower_support_ids=("blowout-risk",)
        if actual_senior and direction is Direction.LOWER
        else (),
        senior_lower_disclosure=(
            "Synthetic reduced-minutes context."
            if actual_senior and direction is Direction.LOWER
            else ""
        ),
    )
    judgment = replace(
        judgment,
        supporting_evidence_ids=supporting_ids,
        meaningful_risk_ids=risk_ids,
    )
    return replace(case, evidence=candidate_evidence, judgment=judgment)


def candidate_key(case: CandidateCase) -> str:
    return case.snapshots[-1].candidate_key


def case_judgment(case: CandidateCase) -> MethodologyJudgment:
    if case.judgment is None:
        raise AssertionError("ranking fixture requires a methodology judgment")
    return case.judgment


def rank_cases(cases: tuple[CandidateCase, ...], *, tie_breaks: tuple[NearTieDecision, ...] = ()):
    return rank_candidates(cases, tie_breaks=tie_breaks)


def with_projection(case: CandidateCase, projection: float) -> CandidateCase:
    snapshots = tuple(
        replace(
            item,
            snapshot=replace(
                item.snapshot,
                observation=replace(item.snapshot.observation, projection=projection),
            ),
            source_excerpt={**item.source_excerpt, "projection": projection},
        )
        if item.snapshot.number == 3
        else item
        for item in case.snapshots
    )
    return replace(case, snapshots=snapshots)


def with_last8_outcomes(case: CandidateCase, outcomes: tuple[str, ...]) -> CandidateCase:
    line = case.snapshots[-1].snapshot.observation.projection
    evidence = tuple(
        replace(
            item,
            samples=tuple(
                replace(sample, value=line + 1 if outcome == "HIGHER" else line - 1)
                for sample, outcome in zip(
                    sorted(item.samples, key=lambda sample: sample.played_at, reverse=True),
                    (*outcomes, *("HIGHER" for _ in range(len(item.samples) - len(outcomes)))),
                    strict=True,
                )
            ),
        )
        if item.kind is EvidenceKind.LAST_8
        else item
        for item in case.evidence
    )
    return replace(case, evidence=evidence)


class RankingTests(unittest.TestCase):
    def assert_near_tie_rejected(
        self,
        first: CandidateCase,
        second: CandidateCase,
        *,
        evidence_id: str,
    ) -> None:
        keys = (candidate_key(first), candidate_key(second))
        decision = NearTieDecision(
            candidate_keys=keys,
            preferred_order=(keys[1], keys[0]),
            rationale="A material recorded input differs.",
            evidence_ids=(evidence_id,),
            one_slot_remains=True,
        )

        with self.assertRaises(RankingError):
            rank_cases((first, second), tie_breaks=(decision,))

    def test_ranking_evaluates_candidate_cases_internally(self) -> None:
        case = make_case("Luka Doncic")
        ranked = rank_candidates((case,))

        self.assertEqual([item.audit.candidate.player for item in ranked.ranked], ["Luka Doncic"])

    def test_ranking_rejects_caller_supplied_methodology_results(self) -> None:
        case = make_case("Luka Doncic")
        audit = evaluate_candidate(case)
        forged_audit = replace(audit, confidence=Confidence.HIGH)
        result = SimpleNamespace(audits=(forged_audit,))

        with self.assertRaises(RankingError):
            rank_candidates(cast(Any, result))
        with self.assertRaises(RankingError):
            rank_candidates(cast(Any, (audit,)))

    def test_extracted_methodology_values_cannot_certify_a_forged_audit_for_ranking(self) -> None:
        case = make_case("Luka Doncic")
        audit = evaluate_candidate(case)
        forged_audit = replace(audit, candidate=replace(audit.candidate, projection=99.0))
        extracted_values = (
            audit.candidate,
            audit.candidate_id,
            audit.candidate_key,
            audit.status,
            audit.confidence,
            audit.evidence,
            audit.history,
            audit.gaps,
            audit.snapshots,
        )
        forged_result = SimpleNamespace(audits=(forged_audit,), internals=extracted_values)

        with self.assertRaises(RankingError):
            rank_candidates(cast(Any, forged_result))

    def test_candidates_persistence_rejects_caller_supplied_forged_result(self) -> None:
        case = make_case("Luka Doncic")
        audit = evaluate_candidate(case)
        forged_audit = replace(audit, candidate=replace(audit.candidate, projection=99.0))
        forged_result = SimpleNamespace(audits=(forged_audit,))

        with TemporaryDirectory() as temporary_root:
            store = RunStore(Path(temporary_root))
            with self.assertRaises(RankingError):
                write_candidates(cast(Any, forged_result), store, "forged-m6-run")
            self.assertFalse((store.run_directory("forged-m6-run") / "candidates.json").exists())

    def test_malformed_candidate_audit_fails_with_ranking_error(self) -> None:
        malformed = replace(
            evaluate_candidate(make_case("Luka Doncic")),
            status=cast(Any, "QUALIFIED"),
        )

        with self.assertRaises(RankingError):
            rank_candidates(cast(Any, (malformed,)))

    def test_malformed_near_tie_shape_fails_with_ranking_error(self) -> None:
        malformed = NearTieDecision(
            candidate_keys=cast(Any, ("only-one-key",)),
            preferred_order=("only-one-key", "only-one-key"),
            rationale="Malformed candidate pair.",
            evidence_ids=("last8",),
            one_slot_remains=True,
        )

        with self.assertRaises(RankingError):
            rank_cases((), tie_breaks=(malformed,))

    def test_senior_priority_beats_ordinary_non_senior(self) -> None:
        non_senior = make_case("Derrick White", confidence=Confidence.HIGH)
        senior = make_case("Luka Doncic", confidence=Confidence.MEDIUM)

        result = rank_cases((non_senior, senior))

        self.assertEqual(
            [item.audit.candidate.player for item in result.ranked],
            ["Luka Doncic", "Derrick White"],
        )

    def test_senior_priority_uses_authoritative_classification(self) -> None:
        mislabeled_non_senior = make_case("Derrick White", confidence=Confidence.HIGH)
        actual_senior = make_case("Luka Doncic", confidence=Confidence.MEDIUM)

        result = rank_cases((mislabeled_non_senior, actual_senior))

        self.assertEqual(
            [item.audit.candidate.player for item in result.ranked],
            ["Luka Doncic", "Derrick White"],
        )

    def test_senior_lower_does_not_receive_senior_higher_priority(self) -> None:
        senior_lower = make_case(
            "Luka Doncic", confidence=Confidence.MEDIUM, direction=Direction.LOWER
        )
        non_senior_higher = make_case("Derrick White", confidence=Confidence.HIGH)

        result = rank_cases((senior_lower, non_senior_higher))

        self.assertEqual(
            [item.audit.candidate.player for item in result.ranked],
            ["Derrick White", "Luka Doncic"],
        )

    def test_evidence_orders_candidates_within_senior_group(self) -> None:
        medium_senior = make_case("Luka Doncic", confidence=Confidence.MEDIUM)
        high_senior = make_case("Jayson Tatum", confidence=Confidence.HIGH)

        result = rank_cases((medium_senior, high_senior))

        self.assertEqual(
            [item.audit.candidate.player for item in result.ranked],
            ["Jayson Tatum", "Luka Doncic"],
        )

    def test_near_tie_non_senior_discretion_requires_explanation(self) -> None:
        first = make_case("Derrick White", confidence=Confidence.MEDIUM)
        second = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)
        keys = (candidate_key(first), candidate_key(second))

        with self.assertRaises(RankingError):
            rank_cases(
                (first, second),
                tie_breaks=(NearTieDecision(keys, (keys[1], keys[0]), "", ("last8",), True),),
            )

        decision = NearTieDecision(
            candidate_keys=keys,
            preferred_order=(keys[1], keys[0]),
            rationale="The supplied fixture evidence favors the second candidate.",
            evidence_ids=("last8", "role"),
            one_slot_remains=True,
        )
        result = rank_cases((first, second), tie_breaks=(decision,))

        self.assertEqual(
            [item.audit.candidate_key for item in result.ranked],
            list(reversed(keys)),
        )
        self.assertIn("fixture evidence", result.ranked[0].reason)

    def test_near_tie_discretion_does_not_override_different_evidence_strength(self) -> None:
        stronger = make_case("Derrick White", confidence=Confidence.MEDIUM)
        weaker = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)
        weaker_evidence = tuple(item for item in weaker.evidence if item.evidence_id != "role")
        weaker_judgment = replace(
            case_judgment(weaker),
            supporting_evidence_ids=("last8",),
        )
        weaker = replace(weaker, evidence=weaker_evidence, judgment=weaker_judgment)
        keys = (candidate_key(stronger), candidate_key(weaker))
        decision = NearTieDecision(
            candidate_keys=keys,
            preferred_order=(keys[1], keys[0]),
            rationale="The supplied fixture evidence favors the second candidate.",
            evidence_ids=("last8",),
            one_slot_remains=True,
        )

        with self.assertRaises(RankingError):
            rank_cases((stronger, weaker), tie_breaks=(decision,))

    def test_near_tie_rejects_a_material_evidence_gap_mismatch(self) -> None:
        supported = make_case("Derrick White", confidence=Confidence.MEDIUM)
        gap = EvidenceGap(
            kind=EvidenceKind.AVAILABILITY,
            reason=ReasonCode.AVAILABILITY_UNRESOLVED,
            significance=EvidenceSignificance.MEANINGFUL,
            detail="Availability context is unresolved.",
        )
        unresolved = replace(
            make_case("Payton Pritchard", confidence=Confidence.MEDIUM),
            gaps=(gap,),
        )
        keys = (candidate_key(supported), candidate_key(unresolved))
        decision = NearTieDecision(
            candidate_keys=keys,
            preferred_order=(keys[1], keys[0]),
            rationale="A comparison cannot ignore the availability gap.",
            evidence_ids=("last8",),
            one_slot_remains=True,
        )

        with self.assertRaises(RankingError):
            rank_cases((supported, unresolved), tie_breaks=(decision,))

    def test_near_tie_rejects_different_minor_gap_disclosures(self) -> None:
        first = make_case("Derrick White", confidence=Confidence.MEDIUM)
        second = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)
        first = replace(
            first,
            gaps=(
                EvidenceGap(
                    kind=EvidenceKind.AVAILABILITY,
                    reason=ReasonCode.AVAILABILITY_UNRESOLVED,
                    significance=EvidenceSignificance.MINOR,
                    detail="A minor availability limitation is recorded.",
                ),
            ),
        )
        second = replace(
            second,
            gaps=(
                EvidenceGap(
                    kind=EvidenceKind.AVAILABILITY,
                    reason=ReasonCode.AVAILABILITY_UNRESOLVED,
                    significance=EvidenceSignificance.MINOR,
                    detail="A different minor availability limitation is recorded.",
                ),
            ),
        )
        keys = (candidate_key(first), candidate_key(second))
        decision = NearTieDecision(
            candidate_keys=keys,
            preferred_order=(keys[1], keys[0]),
            rationale="The records have different disclosed limitations.",
            evidence_ids=("role",),
            one_slot_remains=True,
        )

        with self.assertRaises(RankingError):
            rank_cases((first, second), tie_breaks=(decision,))

    def test_near_tie_rejects_different_history_outcome_sequences(self) -> None:
        first = with_last8_outcomes(
            make_case("Derrick White", confidence=Confidence.MEDIUM),
            ("HIGHER", "HIGHER", "LOWER", "LOWER", "HIGHER", "LOWER", "HIGHER", "LOWER"),
        )
        second = with_last8_outcomes(
            make_case("Payton Pritchard", confidence=Confidence.MEDIUM),
            ("HIGHER", "LOWER", "HIGHER", "LOWER", "HIGHER", "LOWER", "HIGHER", "LOWER"),
        )
        keys = (candidate_key(first), candidate_key(second))
        decision = NearTieDecision(
            candidate_keys=keys,
            preferred_order=(keys[1], keys[0]),
            rationale="The sequence pattern differs despite matching counts.",
            evidence_ids=("last8",),
            one_slot_remains=True,
        )

        with self.assertRaises(RankingError):
            rank_cases((first, second), tie_breaks=(decision,))

    def test_near_tie_rejects_different_recorded_role_facts(self) -> None:
        first = make_case("Derrick White", confidence=Confidence.MEDIUM)
        second = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)
        second_evidence = tuple(
            replace(item, facts={"role": "synthetic-unstable", "minutes_security": "fragile"})
            if item.evidence_id == "role"
            else item
            for item in second.evidence
        )
        second = replace(second, evidence=second_evidence)
        keys = (candidate_key(first), candidate_key(second))
        decision = NearTieDecision(
            candidate_keys=keys,
            preferred_order=(keys[1], keys[0]),
            rationale="Recorded role/minutes facts differ materially.",
            evidence_ids=("role",),
            one_slot_remains=True,
        )

        with self.assertRaises(RankingError):
            rank_cases((first, second), tie_breaks=(decision,))

    def test_near_tie_rejects_different_evidence_claims(self) -> None:
        first = make_case("Derrick White", confidence=Confidence.MEDIUM)
        second = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)
        second = replace(
            second,
            evidence=tuple(
                replace(item, evidence=replace(item.evidence, claim="Different role claim."))
                if item.evidence_id == "role"
                else item
                for item in second.evidence
            ),
        )

        self.assert_near_tie_rejected(first, second, evidence_id="role")

    def test_near_tie_rejects_different_evidence_excerpts(self) -> None:
        first = make_case("Derrick White", confidence=Confidence.MEDIUM)
        second = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)
        second = replace(
            second,
            evidence=tuple(
                replace(
                    item,
                    evidence=replace(item.evidence, excerpt="Different role/minutes excerpt."),
                )
                if item.evidence_id == "role"
                else item
                for item in second.evidence
            ),
        )

        self.assert_near_tie_rejected(first, second, evidence_id="role")

    def test_near_tie_rejects_different_evidence_provenance(self) -> None:
        first = make_case("Derrick White", confidence=Confidence.MEDIUM)
        second = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)
        second = replace(
            second,
            evidence=tuple(
                replace(
                    item,
                    evidence=replace(
                        item.evidence,
                        provenance=replace(
                            item.evidence.provenance,
                            reference="fixture:evidence/different-role-source",
                        ),
                    ),
                )
                if item.evidence_id == "role"
                else item
                for item in second.evidence
            ),
        )

        self.assert_near_tie_rejected(first, second, evidence_id="role")

    def test_near_tie_rejects_different_raw_history_samples(self) -> None:
        first = make_case("Derrick White", confidence=Confidence.MEDIUM)
        second = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)
        second = replace(
            second,
            evidence=tuple(
                replace(
                    item,
                    samples=tuple(
                        replace(sample, value=sample.value + 0.25) for sample in item.samples
                    ),
                )
                if item.kind is EvidenceKind.LAST_8
                else item
                for item in second.evidence
            ),
        )

        self.assert_near_tie_rejected(first, second, evidence_id="last8")

    def test_near_tie_rejects_different_candidate_projections(self) -> None:
        first = make_case("Derrick White", confidence=Confidence.MEDIUM)
        second = with_projection(make_case("Payton Pritchard", confidence=Confidence.MEDIUM), 35.0)

        self.assert_near_tie_rejected(first, second, evidence_id="role")

    def test_near_tie_rejects_different_validated_snapshot_paths(self) -> None:
        first = make_case(
            "Derrick White",
            confidence=Confidence.MEDIUM,
            projections=(32.5, 33.0, 33.5),
        )
        second = make_case(
            "Payton Pritchard",
            confidence=Confidence.MEDIUM,
            projections=(32.0, 33.0, 33.5),
        )

        self.assert_near_tie_rejected(first, second, evidence_id="role")

    def test_near_tie_rejects_different_snapshot_3_late_state(self) -> None:
        first = make_case("Derrick White", confidence=Confidence.MEDIUM)
        second = make_case(
            "Payton Pritchard",
            confidence=Confidence.MEDIUM,
            late_snapshot_3=True,
        )

        self.assert_near_tie_rejected(first, second, evidence_id="role")

    def test_near_tie_cannot_reorder_across_intervening_senior_lower(self) -> None:
        first = make_case("Derrick White", confidence=Confidence.MEDIUM, direction=Direction.LOWER)
        intervening_senior_lower = make_case(
            "Luka Doncic",
            confidence=Confidence.MEDIUM,
            direction=Direction.LOWER,
        )
        second = make_case(
            "Payton Pritchard", confidence=Confidence.MEDIUM, direction=Direction.LOWER
        )
        keys = (candidate_key(first), candidate_key(second))
        decision = NearTieDecision(
            candidate_keys=keys,
            preferred_order=(keys[1], keys[0]),
            rationale="The non-Senior candidates are otherwise tied.",
            evidence_ids=("last8",),
            one_slot_remains=True,
        )

        with self.assertRaises(RankingError):
            rank_cases((first, intervening_senior_lower, second), tie_breaks=(decision,))

    def test_equal_confidence_ranks_support_over_concern_without_label_sorting(self) -> None:
        supporting = make_case("Derrick White", confidence=Confidence.MEDIUM)
        concerned = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)
        concerned_evidence = tuple(
            replace(item, effect=EvidenceEffect.CONCERN) if item.evidence_id == "role" else item
            for item in concerned.evidence
        )
        concerned = replace(
            concerned,
            evidence=concerned_evidence,
            judgment=replace(
                case_judgment(concerned),
                supporting_evidence_ids=tuple(
                    evidence_id
                    for evidence_id in case_judgment(concerned).supporting_evidence_ids
                    if evidence_id != "role"
                ),
            ),
        )

        result = rank_cases((concerned, supporting))

        self.assertEqual(
            [item.audit.candidate.player for item in result.ranked],
            ["Derrick White", "Payton Pritchard"],
        )

    def test_equal_confidence_uses_material_history_before_missing_history(self) -> None:
        complete = make_case("Derrick White", confidence=Confidence.MEDIUM)
        missing = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)
        missing_evidence = tuple(
            item for item in missing.evidence if item.kind is not EvidenceKind.LAST_8
        )
        missing_judgment = replace(
            case_judgment(missing),
            supporting_evidence_ids=("role",),
        )
        missing = replace(missing, evidence=missing_evidence, judgment=missing_judgment)

        result = rank_cases((missing, complete))

        self.assertEqual(
            [item.audit.candidate.player for item in result.ranked],
            ["Derrick White", "Payton Pritchard"],
        )

    def test_equal_confidence_preserves_the_most_material_concern_for_comparison(self) -> None:
        more_risk = make_case("Derrick White", confidence=Confidence.MEDIUM)
        risk_item = next(
            item for item in more_risk.evidence if item.kind is EvidenceKind.BLOWOUT_RISK
        )
        more_risk = replace(
            more_risk,
            evidence=(
                *more_risk.evidence,
                replace(
                    risk_item,
                    evidence_id="blowout-important",
                    significance=EvidenceSignificance.IMPORTANT,
                ),
                replace(
                    risk_item,
                    evidence_id="blowout-minor",
                    significance=EvidenceSignificance.MINOR,
                ),
            ),
        )
        less_risk = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)

        result = rank_cases((more_risk, less_risk))

        self.assertEqual(
            [item.audit.candidate.player for item in result.ranked],
            ["Payton Pritchard", "Derrick White"],
        )

    def test_weaker_duplicate_gap_cannot_replace_stronger_gap(self) -> None:
        meaningful_gap = EvidenceGap(
            kind=EvidenceKind.AVAILABILITY,
            reason=ReasonCode.AVAILABILITY_UNRESOLVED,
            significance=EvidenceSignificance.MEANINGFUL,
            detail="A meaningful availability concern remains.",
        )
        minor_duplicate = replace(
            meaningful_gap,
            significance=EvidenceSignificance.MINOR,
            detail="A weaker duplicate availability note.",
        )
        first = make_case(
            "Derrick White",
            confidence=Confidence.MEDIUM,
            gaps=(meaningful_gap, minor_duplicate),
        )
        second = make_case(
            "Payton Pritchard",
            confidence=Confidence.MEDIUM,
            gaps=(meaningful_gap,),
        )

        result = rank_cases((second, first))

        self.assertEqual(
            [item.audit.candidate.player for item in result.ranked],
            ["Payton Pritchard", "Derrick White"],
        )
        self.assertEqual(result.audits[1].gaps, (meaningful_gap,))

    def test_overlapping_near_tie_decisions_are_rejected(self) -> None:
        first = make_case("Derrick White", confidence=Confidence.MEDIUM)
        second = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)
        third = make_case("Sam Hauser", confidence=Confidence.MEDIUM)
        first_pair = (candidate_key(first), candidate_key(second))
        second_pair = (candidate_key(second), candidate_key(third))
        decisions = (
            NearTieDecision(
                first_pair,
                (first_pair[1], first_pair[0]),
                "The second candidate is preferred.",
                ("last8",),
                True,
            ),
            NearTieDecision(
                second_pair,
                (second_pair[1], second_pair[0]),
                "The third candidate is preferred.",
                ("last8",),
                True,
            ),
        )

        with self.assertRaises(RankingError):
            rank_cases((first, second, third), tie_breaks=decisions)

    def test_trust_tier_does_not_authorize_ranking(self) -> None:
        trusted_but_unauthorized = make_case("Paolo Banchero", category=Category.PRA)
        qualified = make_case("Luka Doncic")

        result = rank_cases((trusted_but_unauthorized, qualified))

        self.assertEqual([item.audit.candidate.player for item in result.ranked], ["Luka Doncic"])
        self.assertIs(result.audits[0].status, EvaluationStatus.BLOCKED)
        self.assertEqual(result.audits[0].trust_labels, ())

    def test_ranking_cannot_add_unauthorized_candidate(self) -> None:
        blocked = make_case("Outside Universe Player")

        result = rank_cases((blocked,))

        self.assertEqual(result.ranked, ())
        self.assertTrue(result.zero_qualified_candidates)

    def test_qualified_audit_without_authorization_is_not_ranked(self) -> None:
        audit: CandidateAudit = evaluate_candidate(make_case("Luka Doncic"))
        forged = replace(
            audit,
            authorization_allowed=False,
        )

        with self.assertRaises(RankingError):
            rank_candidates(cast(Any, (forged,)))

    def test_outside_universe_case_is_not_ranked(self) -> None:
        forged = make_case("Outside Universe Player")

        result = rank_cases((forged,))

        self.assertEqual(result.ranked, ())

    def test_ranking_rechecks_exact_registry_identity_before_disclosure(self) -> None:
        case = make_case("Luka Doncic")
        mismatched_snapshots = tuple(
            replace(
                item,
                snapshot=replace(
                    item.snapshot,
                    observation=replace(item.snapshot.observation, player="Luka  Doncic"),
                ),
            )
            for item in case.snapshots
        )

        result = rank_cases((replace(case, snapshots=mismatched_snapshots),))

        self.assertIs(result.audits[0].status, EvaluationStatus.BLOCKED)
        self.assertIn(ReasonCode.PLAYER_IDENTITY_UNRESOLVED, result.audits[0].exclusions)
        self.assertEqual(result.audits[0].evidence, ())
        self.assertEqual(result.audits[0].gaps, ())

    def test_unauthorized_incomplete_case_is_blocked_before_gap_disclosure(self) -> None:
        gap = EvidenceGap(
            kind=EvidenceKind.AVAILABILITY,
            reason=ReasonCode.AVAILABILITY_UNRESOLVED,
            significance=EvidenceSignificance.CRITICAL,
            detail="Caller-supplied unresolved availability.",
        )
        incomplete = replace(
            make_case("Outside Universe Player", gaps=(gap,)),
            snapshots=make_case("Outside Universe Player").snapshots[:2],
        )

        result = rank_cases((incomplete,))

        self.assertIs(result.audits[0].status, EvaluationStatus.BLOCKED)
        self.assertEqual(result.audits[0].evidence, ())
        self.assertEqual(result.audits[0].gaps, ())

    def test_ranking_canonicalizes_cases_and_rejects_audit_outputs(self) -> None:
        case = make_case("Luka Doncic")
        evaluated: CandidateAudit = evaluate_candidate(case)

        result = rank_cases((case,))

        self.assertEqual(
            [item.audit.candidate.player for item in result.ranked],
            ["Luka Doncic"],
        )
        with self.assertRaises(RankingError):
            rank_candidates(cast(Any, (evaluated,)))

    def test_forged_audit_fields_are_not_accepted_as_ranking_inputs(self) -> None:
        audit: CandidateAudit = evaluate_candidate(make_case("Luka Doncic"))
        invalid_evidence = replace(
            audit.evidence[0],
            evidence=replace(
                audit.evidence[0].evidence,
                provenance=replace(audit.evidence[0].evidence.provenance, payload_hash="bad"),
            ),
        )
        gap = EvidenceGap(
            kind=EvidenceKind.AVAILABILITY,
            reason=ReasonCode.AVAILABILITY_UNRESOLVED,
            significance=EvidenceSignificance.CRITICAL,
            detail="Forged audit gap.",
        )
        forged_audits = (
            ("status", replace(audit, status=EvaluationStatus.BLOCKED)),
            ("confidence", replace(audit, confidence=Confidence.LOW)),
            ("authorization", replace(audit, authorization_allowed=False)),
            ("senior", replace(audit, is_senior=False)),
            ("identity", replace(audit, candidate_id="outside-universe-player")),
            ("key", replace(audit, candidate_key="0" * 64)),
            (
                "candidate projection",
                replace(audit, candidate=replace(audit.candidate, projection=50)),
            ),
            ("evidence", replace(audit, evidence=())),
            ("provenance", replace(audit, evidence=(invalid_evidence, *audit.evidence[1:]))),
            ("evidence mode", replace(audit, evidence_mode=AuditEvidenceMode.LIVE)),
            ("history", replace(audit, history=())),
            ("gaps", replace(audit, gaps=(gap,))),
            ("movement", replace(audit, movement=None)),
            ("trust labels", replace(audit, trust_labels=("PRA_TRUST",))),
            ("foul trouble", replace(audit, foul_trouble=not audit.foul_trouble)),
            ("rules", replace(audit, rules_applied=())),
            ("exclusions", replace(audit, exclusions=(ReasonCode.CATEGORY_NOT_AUTHORIZED,))),
            ("rationale", replace(audit, rationale="Forged rationale.")),
            ("disposition", replace(audit, disposition=MethodologyDisposition.ANALYSIS_ONLY)),
            ("support citations", replace(audit, supporting_evidence_ids=())),
            ("risk citations", replace(audit, meaningful_risk_ids=())),
            ("sufficiency", replace(audit, methodology_sufficient_evidence=False)),
            ("major concern", replace(audit, major_unresolved_concern=True)),
            ("Senior LOWER disclosure", replace(audit, senior_lower_disclosure="Forged.")),
            ("Senior LOWER support", replace(audit, senior_lower_support_ids=())),
        )

        for field, forged in forged_audits:
            with self.subTest(field=field), self.assertRaises(RankingError):
                rank_candidates(cast(Any, (forged,)))

    def test_ranking_revalidates_case_provenance_and_discloses_history_gaps(self) -> None:
        case = make_case("Luka Doncic")
        invalid_evidence = tuple(
            replace(
                item,
                evidence=replace(
                    item.evidence,
                    provenance=replace(item.evidence.provenance, payload_hash="bad"),
                ),
            )
            if item.evidence_id == "role"
            else item
            for item in case.evidence
        )
        invalid_case = replace(case, evidence=invalid_evidence)

        rejected = rank_cases((invalid_case,))

        self.assertEqual(rejected.ranked, ())
        self.assertIs(rejected.audits[0].status, EvaluationStatus.INSUFFICIENT_EVIDENCE)

        partial_history = tuple(
            replace(item, samples=item.samples[:5]) if item.kind is EvidenceKind.LAST_8 else item
            for item in case.evidence
        )
        disclosed = rank_cases((replace(case, evidence=partial_history),))

        self.assertEqual(len(disclosed.ranked), 1)
        self.assertEqual(disclosed.audits[0].history[0].sample_count, 5)
        self.assertTrue(any(gap.kind is EvidenceKind.LAST_8 for gap in disclosed.audits[0].gaps))

    def test_duplicate_history_sample_cannot_change_ranking(self) -> None:
        first = make_case("Derrick White", confidence=Confidence.MEDIUM)
        second = make_case("Payton Pritchard", confidence=Confidence.MEDIUM)
        duplicated = replace(
            first,
            evidence=tuple(
                replace(
                    item,
                    samples=(
                        *item.samples,
                        max(item.samples, key=lambda sample: sample.played_at),
                    ),
                )
                if item.kind is EvidenceKind.LAST_8
                else item
                for item in first.evidence
            ),
        )

        original = rank_cases((second, first))
        after_duplicate = rank_cases((second, duplicated))

        self.assertEqual(
            [item.audit.candidate.player for item in after_duplicate.ranked],
            [item.audit.candidate.player for item in original.ranked],
        )
        self.assertEqual(after_duplicate.audits[1].history, original.audits[1].history)

    def test_qualified_high_audit_with_empty_evidence_is_not_ranked(self) -> None:
        forged = replace(evaluate_candidate(make_case("Luka Doncic")), evidence=())

        with self.assertRaises(RankingError):
            rank_candidates(cast(Any, (forged,)))

        case = make_case("Luka Doncic")
        with self.assertRaises(MethodologyError):
            evaluate_candidate(replace(case, evidence=()))

    def test_qualified_high_audit_with_one_important_signal_is_not_ranked(self) -> None:
        case = make_case("Luka Doncic")
        one_signal = tuple(item for item in case.evidence if item.evidence_id == "last8")
        judgment = replace(
            case_judgment(case),
            supporting_evidence_ids=("last8",),
            meaningful_risk_ids=(),
        )
        insufficient = replace(case, evidence=one_signal, judgment=judgment)

        with self.assertRaises(MethodologyError):
            evaluate_candidate(insufficient)

    def test_forged_status_and_confidence_cannot_override_analysis_only_methodology(self) -> None:
        analysis_only = replace(
            evaluate_candidate(make_case("Luka Doncic")),
            status=EvaluationStatus.ANALYSIS_ONLY,
            confidence=Confidence.LOW,
            disposition=MethodologyDisposition.ANALYSIS_ONLY,
        )
        forged = replace(
            analysis_only,
            status=EvaluationStatus.QUALIFIED,
            confidence=Confidence.HIGH,
        )

        with self.assertRaises(RankingError):
            rank_candidates(cast(Any, (forged,)))

    def test_zero_qualified_candidates_is_valid(self) -> None:
        case = make_case("Luka Doncic")
        insufficient = replace(
            case,
            judgment=replace(case_judgment(case), sufficient_evidence=False),
        )

        result = rank_cases((insufficient,))

        self.assertEqual(result.ranked, ())
        self.assertTrue(result.zero_qualified_candidates)

    def test_ranking_result_serializes_rank_reason_and_all_audits(self) -> None:
        senior = make_case("Luka Doncic")
        blocked = make_case("Paolo Banchero")

        serialized = rank_cases((blocked, senior)).to_dict()

        ranked = serialized["ranked"]
        self.assertIsInstance(ranked, list)
        if isinstance(ranked, list):
            self.assertEqual(ranked[0]["rank"], 1)
            self.assertIn("Senior HIGHER priority", ranked[0]["reason"])
        audits = serialized["audits"]
        self.assertIsInstance(audits, list)
        if isinstance(audits, list):
            self.assertEqual(len(audits), 2)

    def test_fixture_ranking_writes_atomic_run_scoped_candidates_json(self) -> None:
        case = make_case("Luka Doncic")

        with TemporaryDirectory() as temporary_root:
            store = RunStore(Path(temporary_root))

            path = write_candidates((case,), store, "fixture-m6-run")

            self.assertEqual(path, store.run_directory("fixture-m6-run") / "candidates.json")
            serialized = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(serialized["ranked"][0]["candidate_key"], candidate_key(case))
            self.assertFalse(serialized["zero_qualified_candidates"])


if __name__ == "__main__":
    unittest.main()
