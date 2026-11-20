import math
import unittest
from datetime import UTC, datetime

from fifth_pick.errors import ValidationError
from fifth_pick.models import (
    LIVE_MVP_CATEGORIES,
    Candidate,
    Category,
    Decision,
    DecisionAction,
    Direction,
    Evidence,
    Observation,
    Platform,
    Provenance,
    ReasonCode,
    Result,
    ResultStatus,
    Snapshot,
)

NOW = datetime(2026, 11, 15, 17, 0, tzinfo=UTC)
LATER = datetime(2026, 11, 15, 17, 5, tzinfo=UTC)


def make_observation(
    *,
    platform: Platform = Platform.PRIZEPICKS,
    player: str = "canonical:luka-doncic",
    category: Category = Category.POINTS,
    projection: float = 32.5,
    direction: Direction = Direction.HIGHER,
    event: str = "nba:2026-11-15:lal-dal",
    source_update_time: datetime = NOW,
    retrieved_at: datetime = LATER,
    snapshot_number: int = 1,
    source: str = "the-odds-api:us_dfs",
) -> Observation:
    return Observation(
        platform=platform,
        player=player,
        category=category,
        projection=projection,
        direction=direction,
        event=event,
        source_update_time=source_update_time,
        retrieved_at=retrieved_at,
        snapshot_number=snapshot_number,
        source=source,
    )


class ReasonCodeTests(unittest.TestCase):
    def test_reason_codes_are_complete(self) -> None:
        expected = {
            "PLAYER_IDENTITY_UNRESOLVED",
            "CATEGORY_NOT_AUTHORIZED",
            "PROJECTION_UNAVAILABLE",
            "PROJECTION_OBSERVATION_MISSED",
            "AVAILABILITY_UNRESOLVED",
            "ROLE_OR_MINUTES_UNRESOLVED",
            "T20_CHECK_UNAVAILABLE",
            "SOURCE_CONFLICT_UNRESOLVED",
            "INSUFFICIENT_SUPPORTING_EVIDENCE",
            "RESULT UNAVAILABLE",
            "SNAPSHOT_2_MISSED",
        }

        self.assertEqual({code.value for code in ReasonCode}, expected)

    def test_reason_codes_are_closed(self) -> None:
        with self.assertRaises(ValueError):
            ReasonCode("NOT_A_REASON_CODE")

    def test_three_point_attempts_is_vocabulary_only(self) -> None:
        self.assertIn(Category.THREE_POINT_ATTEMPTS, tuple(Category))
        self.assertNotIn(Category.THREE_POINT_ATTEMPTS, LIVE_MVP_CATEGORIES)
        self.assertEqual(
            LIVE_MVP_CATEGORIES,
            frozenset(
                {
                    Category.POINTS,
                    Category.ASSISTS,
                    Category.REBOUNDS,
                    Category.PRA,
                    Category.REBOUNDS_ASSISTS,
                }
            ),
        )


class ObservationTests(unittest.TestCase):
    def test_observation_retains_platform_specific_projection(self) -> None:
        prizepicks = make_observation(platform=Platform.PRIZEPICKS)
        underdog = make_observation(platform=Platform.UNDERDOG, projection=31.5)

        self.assertIs(prizepicks.platform, Platform.PRIZEPICKS)
        self.assertIs(underdog.platform, Platform.UNDERDOG)
        self.assertNotEqual(prizepicks.projection, underdog.projection)

    def test_observation_requires_core_fields_and_safe_projection(self) -> None:
        self.assertEqual(make_observation().snapshot_number, 1)

        with self.assertRaises(ValidationError):
            make_observation(player=" ")
        with self.assertRaises(ValidationError):
            make_observation(event="")
        with self.assertRaises(ValidationError):
            make_observation(source="")
        with self.assertRaises(ValidationError):
            make_observation(projection=math.inf)
        with self.assertRaises(ValidationError):
            make_observation(snapshot_number=4)


class CandidateTests(unittest.TestCase):
    def test_candidate_carries_identity_category_direction_and_platform(self) -> None:
        candidate = Candidate(
            player="canonical:luka-doncic",
            platform=Platform.UNDERDOG,
            category=Category.PRA,
            direction=Direction.LOWER,
            projection=48.5,
            event="nba:2026-11-15:lal-dal",
        )

        self.assertIs(candidate.platform, Platform.UNDERDOG)
        self.assertIs(candidate.category, Category.PRA)
        self.assertIs(candidate.direction, Direction.LOWER)

        with self.assertRaises(ValidationError):
            Candidate(
                player=" ",
                platform=Platform.UNDERDOG,
                category=Category.PRA,
                direction=Direction.LOWER,
                projection=48.5,
                event="nba:2026-11-15:lal-dal",
            )


class SnapshotTests(unittest.TestCase):
    def test_snapshot_number_matches_observation(self) -> None:
        observation = make_observation(snapshot_number=2)
        snapshot = Snapshot(number=2, observation=observation, recorded_at=LATER)

        self.assertEqual(snapshot.number, 2)
        self.assertIs(snapshot.observation, observation)

        with self.assertRaises(ValidationError):
            Snapshot(number=3, observation=observation, recorded_at=LATER)


class EvidenceTests(unittest.TestCase):
    def test_evidence_requires_provenance(self) -> None:
        provenance = Provenance(
            source="official-nba-injury-report",
            retrieved_at=NOW,
            source_timestamp=NOW,
            access_method="approved-manual",
            reference="nba-injury-report:2026-11-15",
            payload_hash="sha256:" + "a" * 64,
        )
        evidence = Evidence(claim="Player is listed as available.", provenance=provenance)

        self.assertIs(evidence.provenance, provenance)

        with self.assertRaises(ValidationError):
            Evidence(claim=" ", provenance=provenance)
        with self.assertRaises(ValidationError):
            Provenance(
                source=" ",
                retrieved_at=NOW,
                source_timestamp=NOW,
                access_method="approved-manual",
                reference="nba-injury-report:2026-11-15",
                payload_hash="sha256:" + "a" * 64,
            )


class DecisionTests(unittest.TestCase):
    def test_decision_requires_explicit_action_and_run(self) -> None:
        decision = Decision(
            action=DecisionAction.APPROVE,
            run_id="run-20261115",
            timestamp=NOW,
            slate_version=1,
        )

        self.assertIs(decision.action, DecisionAction.APPROVE)

        with self.assertRaises(ValueError):
            DecisionAction("PROCEED")
        with self.assertRaises(ValidationError):
            Decision(
                action=DecisionAction.APPROVE,
                run_id=" ",
                timestamp=NOW,
                slate_version=1,
            )


class ResultTests(unittest.TestCase):
    def test_result_keeps_unavailable_and_dnp_distinct_from_miss(self) -> None:
        unavailable = Result(
            outcome=ResultStatus.RESULT_UNAVAILABLE,
            subject="canonical:luka-doncic",
            source="manual:platform-settled",
            recorded_at=NOW,
        )
        dnp = Result(
            outcome=ResultStatus.DNP,
            subject="canonical:luka-doncic",
            source="manual:platform-settled",
            recorded_at=NOW,
        )
        miss = Result(
            outcome=ResultStatus.MISS,
            subject="canonical:luka-doncic",
            source="manual:platform-settled",
            recorded_at=NOW,
        )

        self.assertNotEqual(dnp.outcome, miss.outcome)
        self.assertNotEqual(unavailable.outcome, miss.outcome)

        with self.assertRaises(ValueError):
            ResultStatus("WIN")
        with self.assertRaises(ValidationError):
            Result(
                outcome=ResultStatus.HIT,
                subject=" ",
                source="manual:platform-settled",
                recorded_at=NOW,
            )
