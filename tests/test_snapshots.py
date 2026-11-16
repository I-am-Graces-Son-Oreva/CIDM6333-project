import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from tempfile import TemporaryDirectory
from typing import cast

from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.identity import IdentityResolver
from fifth_pick.models import Category, Direction, Platform, ReasonCode
from fifth_pick.registry import Registry, RegistryPlayer
from fifth_pick.snapshots import SnapshotError, SnapshotWorkflow, snapshot_2_target
from fifth_pick.sources.base import (
    BoardProvenance,
    EvidenceMode,
    SourceBoard,
    SourceProjection,
)
from fifth_pick.sources.fixtures import FixtureTransport
from fifth_pick.sources.odds_api import (
    API_KEY_ENV_VAR,
    SOURCE_ID,
    OddsApiClient,
)
from fifth_pick.sources.quota import QuotaBudget
from fifth_pick.storage import RunStore

NOW = datetime(2026, 11, 15, 17, 0, tzinfo=UTC)
TIPOFF = datetime(2026, 11, 15, 20, 0, tzinfo=UTC)
EVENT_ID = "evt-bos-nyk-1"
RUN_ID = "run-snapshot-test"


class MutableClock:
    def __init__(self, current: datetime = NOW) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


def make_projection(
    retrieved_at: datetime,
    *,
    player_name: str = "L. Doncic",
    platform: Platform = Platform.PRIZEPICKS,
    category: Category = Category.POINTS,
    projection: float = 32.5,
    direction: Direction = Direction.HIGHER,
    event_id: str = EVENT_ID,
) -> SourceProjection:
    return SourceProjection(
        platform=platform,
        provider_player_name=player_name,
        category=category,
        projection=projection,
        direction=direction,
        event_id=event_id,
        source_update_time=retrieved_at - timedelta(minutes=2),
        retrieved_at=retrieved_at,
    )


def make_board(
    retrieved_at: datetime,
    *projections: SourceProjection,
    tipoff_at: datetime = TIPOFF,
) -> SourceBoard:
    market_keys = {
        Category.POINTS: "player_points",
        Category.ASSISTS: "player_assists",
        Category.REBOUNDS: "player_rebounds",
        Category.PRA: "player_points_rebounds_assists",
        Category.REBOUNDS_ASSISTS: "player_rebounds_assists",
    }
    outcome_names = {Direction.HIGHER: "Over", Direction.LOWER: "Under"}
    bookmakers: dict[str, dict[str, object]] = {}
    for projection in projections:
        bookmaker = bookmakers.setdefault(
            projection.platform.value,
            {"key": projection.platform.value, "markets": []},
        )
        markets = bookmaker["markets"]
        assert isinstance(markets, list)
        market_key = market_keys[projection.category]
        market = next((item for item in markets if item["key"] == market_key), None)
        if market is None:
            market = {
                "key": market_key,
                "last_update": projection.source_update_time.isoformat(),
                "outcomes": [],
            }
            markets.append(market)
        outcomes = market["outcomes"]
        assert isinstance(outcomes, list)
        outcomes.append(
            {
                "name": outcome_names[projection.direction],
                "description": projection.provider_player_name,
                "point": projection.projection,
            }
        )

    events_body = json.dumps(
        [
            {
                "id": EVENT_ID,
                "home_team": "Boston Celtics",
                "away_team": "New York Knicks",
                "commence_time": tipoff_at.isoformat(),
            }
        ]
    ).encode("utf-8")
    odds_body = json.dumps({"id": EVENT_ID, "bookmakers": list(bookmakers.values())}).encode(
        "utf-8"
    )
    transport = FixtureTransport(events_body=events_body, odds_bodies={EVENT_ID: odds_body})
    client = OddsApiClient(
        transport=transport,
        environ={API_KEY_ENV_VAR: "fixture-only-test-value"},
        clock=lambda: retrieved_at,
    )
    return client.fetch_board(live_authorized=True, budget=QuotaBudget(credits=100))


def make_workflow(root: str, clock: MutableClock) -> SnapshotWorkflow:
    registry = Registry.from_universe(load_configs().approved_universe)
    resolver = IdentityResolver(
        registry,
        provider_aliases={
            "L. Doncic": ("luka-doncic",),
            "M. Robinson": ("mitchell-robinson",),
        },
    )
    return SnapshotWorkflow(
        RunStore(root),
        resolver,
        AuthorizationGate(),
        clock=clock,
    )


class SnapshotWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.clock = MutableClock()
        self.store = RunStore(self.temporary.name)
        self.workflow = make_workflow(self.temporary.name, self.clock)

    def record_snapshot_1(self) -> None:
        board = make_board(NOW, make_projection(NOW))
        self.workflow.collect(RUN_ID, 1, board)

    def record_snapshot_2(self) -> None:
        self.record_snapshot_1()
        observed_at = datetime(2026, 11, 15, 18, 20, tzinfo=UTC)
        self.clock.current = observed_at
        board = make_board(observed_at, make_projection(observed_at))
        self.workflow.collect(RUN_ID, 2, board)

    def test_snapshot_1_uses_first_legitimate_success(self) -> None:
        board = make_board(NOW, make_projection(NOW))

        snapshots = self.workflow.collect(RUN_ID, 1, board)

        self.assertEqual(len(snapshots), 1)
        record = snapshots[0]
        self.assertEqual(record.snapshot.number, 1)
        self.assertEqual(record.snapshot.observation.player, "Luka Doncic")
        self.assertEqual(record.snapshot.observation.retrieved_at, NOW)
        self.assertEqual(record.snapshot.recorded_at, NOW)
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        self.assertTrue(ledger.is_file())

    def test_snapshot_1_after_tipoff_is_missed(self) -> None:
        late_at = TIPOFF + timedelta(minutes=1)
        self.clock.current = late_at

        snapshots = self.workflow.collect(
            RUN_ID,
            1,
            make_board(late_at, make_projection(late_at)),
        )

        self.assertEqual(snapshots, ())
        missed = self.workflow.read_missed(RUN_ID)
        self.assertEqual(len(missed), 1)
        self.assertEqual(missed[0].number, 1)
        self.assertIs(missed[0].reason, ReasonCode.PROJECTION_OBSERVATION_MISSED)

    def test_snapshot_2_is_midpoint_with_60_minute_floor_where_possible(self) -> None:
        target = snapshot_2_target(NOW, TIPOFF)

        self.assertEqual(target, datetime(2026, 11, 15, 18, 20, tzinfo=UTC))
        assert target is not None
        self.assertGreaterEqual(target - NOW, timedelta(minutes=60))

    def test_snapshot_2_latest_target_is_60_minutes_before_t20(self) -> None:
        snapshot_1_at = datetime(2026, 11, 15, 18, 0, tzinfo=UTC)

        target = snapshot_2_target(snapshot_1_at, TIPOFF)

        self.assertEqual(target, datetime(2026, 11, 15, 18, 40, tzinfo=UTC))
        assert target is not None
        self.assertEqual(TIPOFF - target, timedelta(minutes=80))

    def test_snapshot_2_missed_records_reason_code(self) -> None:
        self.record_snapshot_1()
        self.clock.current = datetime(2026, 11, 15, 18, 41, tzinfo=UTC)

        missed = self.workflow.mark_snapshot_2_missed(RUN_ID, EVENT_ID)

        self.assertEqual(len(missed), 1)
        self.assertIs(missed[0].reason, ReasonCode.SNAPSHOT_2_MISSED)
        self.assertIs(self.workflow.read_missed(RUN_ID)[0].reason, ReasonCode.SNAPSHOT_2_MISSED)
        receipts = self.store.read_receipts(RUN_ID)
        self.assertIn(ReasonCode.SNAPSHOT_2_MISSED.value, {item["reason"] for item in receipts})

    def test_duplicate_snapshot_is_idempotent(self) -> None:
        board = make_board(NOW, make_projection(NOW))

        first = self.workflow.collect(RUN_ID, 1, board)
        second = self.workflow.collect(RUN_ID, 1, board)

        self.assertEqual(len(self.workflow.read(RUN_ID)), 1)
        self.assertEqual(second, first)
        self.assertIn(
            "SNAPSHOT_DUPLICATE",
            {item["event"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_missed_slot_is_recorded_not_backfilled(self) -> None:
        self.record_snapshot_1()
        self.clock.current = datetime(2026, 11, 15, 18, 41, tzinfo=UTC)
        self.workflow.mark_snapshot_2_missed(RUN_ID, EVENT_ID)
        self.clock.current = datetime(2026, 11, 15, 18, 45, tzinfo=UTC)
        late_board = make_board(self.clock.current, make_projection(self.clock.current))

        snapshots = self.workflow.collect(RUN_ID, 2, late_board)

        self.assertEqual(snapshots, ())
        self.assertEqual([item.snapshot.number for item in self.workflow.read(RUN_ID)], [1])
        reasons = {item["reason"] for item in self.store.read_receipts(RUN_ID)}
        self.assertIn(ReasonCode.SNAPSHOT_2_MISSED.value, reasons)
        self.assertIn(ReasonCode.PROJECTION_OBSERVATION_MISSED.value, reasons)

    def test_snapshot_2_without_projection_is_recorded_missed(self) -> None:
        self.record_snapshot_1()
        observed_at = datetime(2026, 11, 15, 18, 41, tzinfo=UTC)
        self.clock.current = observed_at

        self.workflow.collect(RUN_ID, 2, make_board(observed_at))

        missed = self.workflow.read_missed(RUN_ID)
        self.assertEqual(len(missed), 1)
        self.assertEqual(missed[0].number, 2)
        self.assertIs(missed[0].reason, ReasonCode.SNAPSHOT_2_MISSED)

    def test_snapshot_2_absent_projection_can_retry_before_latest_target(self) -> None:
        self.record_snapshot_1()
        target = datetime(2026, 11, 15, 18, 20, tzinfo=UTC)
        self.clock.current = target
        self.workflow.collect(RUN_ID, 2, make_board(target))
        retry_at = datetime(2026, 11, 15, 18, 30, tzinfo=UTC)
        self.clock.current = retry_at

        snapshots = self.workflow.collect(
            RUN_ID,
            2,
            make_board(retry_at, make_projection(retry_at)),
        )

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].snapshot.observation.retrieved_at, retry_at)
        self.assertEqual(self.workflow.read_missed(RUN_ID), ())

    def test_snapshot_2_recording_time_must_follow_snapshot_1_recording(self) -> None:
        first_observed_at = datetime(2026, 11, 15, 18, 30, tzinfo=UTC)
        self.clock.current = datetime(2026, 11, 15, 18, 40, tzinfo=UTC)
        self.workflow.collect(
            RUN_ID,
            1,
            make_board(first_observed_at, make_projection(first_observed_at)),
        )
        second_observed_at = datetime(2026, 11, 15, 18, 35, tzinfo=UTC)
        self.clock.current = datetime(2026, 11, 15, 18, 38, tzinfo=UTC)

        snapshots = self.workflow.collect(
            RUN_ID,
            2,
            make_board(second_observed_at, make_projection(second_observed_at)),
        )

        self.assertEqual(snapshots, ())
        self.assertEqual([item.snapshot.number for item in self.workflow.read(RUN_ID)], [1])
        self.assertIn(
            "OUT_OF_ORDER",
            {item["result"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_event_tipoff_change_fails_closed_between_snapshots(self) -> None:
        self.record_snapshot_1()
        observed_at = datetime(2026, 11, 15, 18, 20, tzinfo=UTC)
        self.clock.current = observed_at
        changed_tipoff = TIPOFF + timedelta(minutes=30)

        snapshots = self.workflow.collect(
            RUN_ID,
            2,
            make_board(observed_at, make_projection(observed_at), tipoff_at=changed_tipoff),
        )

        self.assertEqual(snapshots, ())
        self.assertIn(
            ReasonCode.SOURCE_CONFLICT_UNRESOLVED.value,
            {item["reason"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_empty_board_tipoff_change_fails_closed_without_missed_slot(self) -> None:
        self.record_snapshot_1()
        observed_at = datetime(2026, 11, 15, 18, 41, tzinfo=UTC)
        changed_tipoff = TIPOFF + timedelta(minutes=30)
        self.clock.current = observed_at

        self.workflow.collect(
            RUN_ID,
            2,
            make_board(observed_at, tipoff_at=changed_tipoff),
        )

        self.assertEqual(self.workflow.read_missed(RUN_ID), ())
        self.assertIn(
            ReasonCode.SOURCE_CONFLICT_UNRESOLVED.value,
            {item["reason"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_tipoff_change_blocks_new_candidate_for_existing_event(self) -> None:
        self.workflow.collect(
            RUN_ID,
            1,
            make_board(NOW, make_projection(NOW)),
        )
        later_at = NOW + timedelta(minutes=5)
        self.clock.current = later_at

        snapshots = self.workflow.collect(
            RUN_ID,
            1,
            make_board(
                later_at,
                make_projection(
                    later_at,
                    player_name="M. Robinson",
                    direction=Direction.LOWER,
                ),
                tipoff_at=TIPOFF + timedelta(minutes=30),
            ),
        )

        self.assertEqual(snapshots, ())
        self.assertEqual(len(self.workflow.read(RUN_ID)), 1)
        self.assertIn(
            ReasonCode.SOURCE_CONFLICT_UNRESOLVED.value,
            {item["reason"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_future_source_observation_fails_closed(self) -> None:
        future = NOW + timedelta(minutes=1)

        with self.assertRaises(SnapshotError):
            self.workflow.collect(
                RUN_ID,
                1,
                make_board(future, make_projection(future)),
            )

    def test_source_update_after_retrieval_fails_closed(self) -> None:
        projection = SourceProjection(
            platform=Platform.PRIZEPICKS,
            provider_player_name="L. Doncic",
            category=Category.POINTS,
            projection=32.5,
            direction=Direction.HIGHER,
            event_id=EVENT_ID,
            source_update_time=NOW + timedelta(seconds=1),
            retrieved_at=NOW,
        )

        with self.assertRaises(SnapshotError):
            self.workflow.collect(RUN_ID, 1, make_board(NOW, projection))

    def test_projection_retrieved_before_board_request_fails_closed(self) -> None:
        observed_at = NOW
        board_retrieved_at = NOW + timedelta(minutes=5)
        base = make_board(board_retrieved_at, make_projection(observed_at))
        event = base.events[0]
        stale_projection = replace(event.projections[0], retrieved_at=observed_at)
        stale_event = replace(event, projections=(stale_projection,))
        board = replace(base, events=(stale_event,))
        self.clock.current = board_retrieved_at

        with self.assertRaises(SnapshotError):
            self.workflow.collect(RUN_ID, 1, board)

    def test_out_of_order_slot_is_rejected(self) -> None:
        observed_at = datetime(2026, 11, 15, 18, 20, tzinfo=UTC)
        self.clock.current = observed_at
        board = make_board(observed_at, make_projection(observed_at))

        snapshots = self.workflow.collect(RUN_ID, 2, board)

        self.assertEqual(snapshots, ())
        self.assertEqual(self.workflow.read(RUN_ID), ())
        self.assertIn(
            "SNAPSHOT_REJECTED",
            {item["event"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_snapshot_3_uses_t25_to_t20_window(self) -> None:
        self.record_snapshot_2()
        observed_at = datetime(2026, 11, 15, 19, 38, tzinfo=UTC)
        self.clock.current = observed_at
        board = make_board(observed_at, make_projection(observed_at))

        snapshots = self.workflow.collect(RUN_ID, 3, board)

        self.assertEqual(len(snapshots), 1)
        third = snapshots[0]
        self.assertEqual(third.snapshot.number, 3)
        self.assertFalse(third.late)
        self.assertGreaterEqual(
            third.snapshot.observation.retrieved_at,
            TIPOFF - timedelta(minutes=25),
        )
        self.assertLessEqual(
            third.snapshot.observation.retrieved_at,
            TIPOFF - timedelta(minutes=20),
        )

    def test_snapshot_3_absent_projection_can_retry_inside_window(self) -> None:
        self.record_snapshot_2()
        first_attempt = TIPOFF - timedelta(minutes=25)
        self.clock.current = first_attempt
        self.workflow.collect(RUN_ID, 3, make_board(first_attempt))
        retry_at = TIPOFF - timedelta(minutes=22)
        self.clock.current = retry_at

        snapshots = self.workflow.collect(
            RUN_ID,
            3,
            make_board(retry_at, make_projection(retry_at)),
        )

        self.assertEqual(len(snapshots), 1)
        self.assertFalse(snapshots[0].late)
        self.assertEqual(self.workflow.read_missed(RUN_ID), ())

    def test_absent_snapshot_3_can_retry_after_t20_before_tipoff(self) -> None:
        self.record_snapshot_2()
        failed_at = TIPOFF - timedelta(minutes=15)
        self.clock.current = failed_at
        self.workflow.collect(RUN_ID, 3, make_board(failed_at))
        retry_at = TIPOFF - timedelta(minutes=10)
        self.clock.current = retry_at

        snapshots = self.workflow.collect(
            RUN_ID,
            3,
            make_board(retry_at, make_projection(retry_at)),
        )

        self.assertEqual(len(snapshots), 1)
        self.assertTrue(snapshots[0].late)
        self.assertEqual(self.workflow.read_missed(RUN_ID), ())

    def test_early_absent_snapshot_3_does_not_miss_open_snapshot_2(self) -> None:
        self.record_snapshot_1()
        early_attempt = datetime(2026, 11, 15, 18, 20, tzinfo=UTC)
        self.clock.current = early_attempt
        self.workflow.collect(RUN_ID, 3, make_board(early_attempt))

        self.assertEqual(self.workflow.read_missed(RUN_ID), ())
        snapshot_2_at = datetime(2026, 11, 15, 18, 30, tzinfo=UTC)
        self.clock.current = snapshot_2_at
        snapshots = self.workflow.collect(
            RUN_ID,
            2,
            make_board(snapshot_2_at, make_projection(snapshot_2_at)),
        )

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].snapshot.number, 2)

    def test_late_snapshot_3_is_recorded_honestly(self) -> None:
        self.record_snapshot_2()
        late_at = datetime(2026, 11, 15, 19, 45, tzinfo=UTC)
        self.clock.current = late_at
        board = make_board(late_at, make_projection(late_at))

        snapshots = self.workflow.collect(RUN_ID, 3, board)

        self.assertEqual(len(snapshots), 1)
        self.assertTrue(snapshots[0].late)
        self.assertEqual(snapshots[0].snapshot.observation.retrieved_at, late_at)
        self.assertNotEqual(
            snapshots[0].snapshot.observation.retrieved_at,
            TIPOFF - timedelta(minutes=20),
        )
        self.assertIn(
            "SNAPSHOT_LATE",
            {item["event"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_snapshot_3_source_retrieval_must_follow_snapshot_1(self) -> None:
        snapshot_1_at = TIPOFF - timedelta(minutes=10)
        self.clock.current = snapshot_1_at
        self.workflow.collect(
            RUN_ID,
            1,
            make_board(snapshot_1_at, make_projection(snapshot_1_at)),
        )
        self.clock.current = TIPOFF - timedelta(minutes=5)
        stale_at = TIPOFF - timedelta(minutes=20)
        board = make_board(stale_at, make_projection(stale_at))

        snapshots = self.workflow.collect(RUN_ID, 3, board)

        self.assertEqual(snapshots, ())
        self.assertEqual([item.snapshot.number for item in self.workflow.read(RUN_ID)], [1])
        self.assertIn(
            "OUT_OF_ORDER",
            {item["result"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_supporting_refresh_does_not_add_snapshot(self) -> None:
        with self.assertRaises(SnapshotError):
            self.workflow.collect(RUN_ID, 1, cast(SourceBoard, object()))

        self.assertEqual(self.workflow.read(RUN_ID), ())

    def test_snapshot_provenance_is_complete(self) -> None:
        board = make_board(NOW, make_projection(NOW))
        snapshots = self.workflow.collect(
            RUN_ID,
            1,
            board,
        )

        self.assertEqual(len(snapshots), 1)
        record = snapshots[0]
        self.assertEqual(record.snapshot.observation.platform, Platform.PRIZEPICKS)
        self.assertEqual(record.snapshot.observation.category, Category.POINTS)
        self.assertIs(record.snapshot.observation.direction, Direction.HIGHER)
        self.assertEqual(record.snapshot.observation.event, EVENT_ID)
        self.assertEqual(record.snapshot.observation.source_update_time, NOW - timedelta(minutes=2))
        self.assertEqual(record.snapshot.observation.retrieved_at, NOW)
        self.assertEqual(record.provenance.source, SOURCE_ID)
        self.assertEqual(record.provenance.source_timestamp, NOW - timedelta(minutes=2))
        self.assertEqual(record.provenance.retrieved_at, NOW)
        self.assertEqual(record.provenance.access_method, "synthetic-fixture-transport")
        self.assertEqual(record.provenance.payload_hash, board.provenance.payload_sha256)
        self.assertIs(record.evidence_mode, EvidenceMode.FIXTURE)
        self.assertEqual(record.source_excerpt["provider_player_name"], "L. Doncic")
        self.assertEqual(record.source_excerpt["projection"], 32.5)

    def test_fixture_origin_is_preserved_in_snapshot(self) -> None:
        board = make_board(NOW, make_projection(NOW))
        self.assertEqual(getattr(board.provenance, "evidence_mode", None), "fixture")

        record = self.workflow.collect(RUN_ID, 1, board)[0]

        self.assertEqual(getattr(record, "evidence_mode", None), "fixture")

    def test_unknown_evidence_origin_fails_closed(self) -> None:
        fixture_board = make_board(NOW, make_projection(NOW))
        board = SourceBoard(
            provenance=replace(
                fixture_board.provenance,
                request_url=fixture_board.provenance.request_url,
            ),
            events=fixture_board.events,
        )

        with self.assertRaises(SnapshotError):
            self.workflow.collect(RUN_ID, 1, board)

    def test_fixture_evidence_mode_cannot_be_relabelled_live(self) -> None:
        fixture_board = make_board(NOW, make_projection(NOW))

        with self.assertRaises(TypeError):
            replace(
                fixture_board.provenance,
                evidence_mode=EvidenceMode.LIVE,
            )

    def test_board_provenance_has_no_caller_fixture_mode_setter(self) -> None:
        fixture_board = make_board(NOW, make_projection(NOW))

        self.assertFalse(hasattr(fixture_board.provenance, "_mark_fixture"))

    def test_supporting_platform_observations_remain_separate(self) -> None:
        board = make_board(
            NOW,
            make_projection(NOW, platform=Platform.PRIZEPICKS, projection=32.5),
            make_projection(NOW, platform=Platform.UNDERDOG, projection=31.5),
        )

        snapshots = self.workflow.collect(RUN_ID, 1, board)

        self.assertEqual(len(snapshots), 2)
        self.assertEqual(
            {item.snapshot.observation.platform for item in snapshots},
            {Platform.PRIZEPICKS, Platform.UNDERDOG},
        )
        self.assertEqual(
            {item.snapshot.observation.projection for item in snapshots},
            {31.5, 32.5},
        )
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        self.assertEqual(len(ledger.read_text(encoding="utf-8").splitlines()), 2)

    def test_unknown_provider_identity_fails_closed(self) -> None:
        board = make_board(NOW, make_projection(NOW, player_name="Unknown Player"))

        snapshots = self.workflow.collect(RUN_ID, 1, board)

        self.assertEqual(snapshots, ())
        self.assertEqual(self.workflow.read(RUN_ID), ())
        self.assertIn(
            ReasonCode.PLAYER_IDENTITY_UNRESOLVED.value,
            {item["reason"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_provider_resolver_cannot_relabel_authorized_player(self) -> None:
        bundle = load_configs()
        source_registry = Registry.from_universe(bundle.approved_universe)
        luka = source_registry.player_by_id("luka-doncic")
        assert luka is not None
        forged_player = RegistryPlayer(
            player_id=luka.player_id,
            canonical_name="Not Luka Doncic",
            grants=luka.grants,
        )
        forged_registry = Registry((forged_player,))
        forged_resolver = IdentityResolver(
            forged_registry,
            provider_aliases={"L. Doncic": (luka.player_id,)},
        )
        self.workflow = SnapshotWorkflow(
            self.store,
            forged_resolver,
            AuthorizationGate(),
            clock=self.clock,
        )

        snapshots = self.workflow.collect(
            RUN_ID,
            1,
            make_board(NOW, make_projection(NOW)),
        )

        self.assertEqual(snapshots, ())
        self.assertIn(
            ReasonCode.PLAYER_IDENTITY_UNRESOLVED.value,
            {item["reason"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_unauthorized_projection_is_not_snapshotted(self) -> None:
        board = make_board(
            NOW,
            make_projection(
                NOW,
                player_name="M. Robinson",
                category=Category.POINTS,
                direction=Direction.HIGHER,
            ),
        )

        snapshots = self.workflow.collect(RUN_ID, 1, board)

        self.assertEqual(snapshots, ())
        self.assertIn(
            ReasonCode.CATEGORY_NOT_AUTHORIZED.value,
            {item["reason"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_snapshot_3_after_tipoff_is_recorded_missed(self) -> None:
        self.record_snapshot_2()
        self.clock.current = TIPOFF + timedelta(minutes=1)
        board = make_board(self.clock.current, make_projection(self.clock.current))

        snapshots = self.workflow.collect(RUN_ID, 3, board)

        self.assertEqual(snapshots, ())
        missed = self.workflow.read_missed(RUN_ID)
        self.assertEqual(
            [(item.number, item.reason) for item in missed],
            [(3, ReasonCode.PROJECTION_OBSERVATION_MISSED)],
        )

    def test_post_tipoff_collection_marks_old_snapshot_3_projection_missed(self) -> None:
        self.record_snapshot_2()
        projection_at = TIPOFF - timedelta(minutes=30)
        board_at = projection_at + timedelta(minutes=1)
        self.clock.current = TIPOFF + timedelta(minutes=1)
        board = make_board(board_at, make_projection(board_at))

        snapshots = self.workflow.collect(RUN_ID, 3, board)

        self.assertEqual(snapshots, ())
        self.assertEqual(
            [(item.number, item.reason) for item in self.workflow.read_missed(RUN_ID)],
            [(3, ReasonCode.PROJECTION_OBSERVATION_MISSED)],
        )

    def test_infeasible_snapshot_2_schedule_returns_no_target(self) -> None:
        snapshot_1_at = datetime(2026, 11, 15, 19, 0, tzinfo=UTC)

        self.assertIsNone(snapshot_2_target(snapshot_1_at, TIPOFF))

    def test_non_approved_board_fails_closed(self) -> None:
        board = make_board(NOW, make_projection(NOW))
        wrong_provenance = BoardProvenance(
            source_id="unapproved-source",
            region=board.provenance.region,
            bookmakers=board.provenance.bookmakers,
            markets=board.provenance.markets,
            request_timestamp=board.provenance.request_timestamp,
            retrieved_at=board.provenance.retrieved_at,
            source_update_time=board.provenance.source_update_time,
            payload_sha256=board.provenance.payload_sha256,
            request_url=board.provenance.request_url,
            quota=board.provenance.quota,
        )
        unapproved_board = SourceBoard(provenance=wrong_provenance, events=board.events)

        with self.assertRaises(SnapshotError):
            self.workflow.collect(RUN_ID, 1, unapproved_board)

    def test_malformed_snapshot_ledger_fails_closed(self) -> None:
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text("{invalid json}\n", encoding="utf-8")

        with self.assertRaises(SnapshotError):
            self.workflow.read(RUN_ID)

    def test_non_integer_snapshot_number_in_ledger_fails_closed(self) -> None:
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        ledger.parent.mkdir(parents=True)
        entry = {
            "kind": "missed",
            "number": 2.0,
            "candidate_id": "luka-doncic",
            "candidate_key": "a" * 64,
            "event_id": EVENT_ID,
            "reason": ReasonCode.SNAPSHOT_2_MISSED.value,
            "recorded_at": NOW.isoformat(),
        }
        ledger.write_text(json.dumps(entry) + "\n", encoding="utf-8")

        with self.assertRaises(SnapshotError):
            self.workflow.read_missed(RUN_ID)

    def test_snapshot_and_missed_state_for_same_slot_fails_closed(self) -> None:
        self.record_snapshot_1()
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        snapshot_entry = json.loads(ledger.read_text(encoding="utf-8"))
        missed_entry = {
            "kind": "missed",
            "number": 1,
            "candidate_id": snapshot_entry["candidate_id"],
            "candidate_key": snapshot_entry["candidate_key"],
            "event_id": EVENT_ID,
            "reason": ReasonCode.PROJECTION_OBSERVATION_MISSED.value,
            "recorded_at": NOW.isoformat(),
        }
        ledger.write_text(
            json.dumps(snapshot_entry) + "\n" + json.dumps(missed_entry) + "\n",
            encoding="utf-8",
        )

        with self.assertRaises(SnapshotError):
            self.workflow.read(RUN_ID)

    def test_snapshot_excerpt_must_match_recorded_observation(self) -> None:
        self.record_snapshot_1()
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        entry = json.loads(ledger.read_text(encoding="utf-8"))
        entry["source_excerpt"]["projection"] = 99.5
        ledger.write_text(json.dumps(entry) + "\n", encoding="utf-8")

        with self.assertRaises(SnapshotError):
            self.workflow.read(RUN_ID)

    def test_snapshot_excerpt_provider_name_must_be_nonempty_text(self) -> None:
        self.record_snapshot_1()
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        entry = json.loads(ledger.read_text(encoding="utf-8"))
        entry["source_excerpt"]["provider_player_name"] = 42.0
        ledger.write_text(json.dumps(entry) + "\n", encoding="utf-8")

        with self.assertRaises(SnapshotError):
            self.workflow.read(RUN_ID)

    def test_snapshot_3_recorded_after_tipoff_fails_closed(self) -> None:
        self.record_snapshot_2()
        late_at = TIPOFF - timedelta(minutes=15)
        self.clock.current = late_at
        self.workflow.collect(RUN_ID, 3, make_board(late_at, make_projection(late_at)))
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        for entry in entries:
            if entry["kind"] == "snapshot" and entry["number"] == 3:
                entry["recorded_at"] = (TIPOFF + timedelta(minutes=1)).isoformat()
        ledger.write_text(
            "".join(json.dumps(entry) + "\n" for entry in entries),
            encoding="utf-8",
        )

        with self.assertRaises(SnapshotError):
            self.workflow.read(RUN_ID)

    def test_persisted_source_update_after_retrieval_fails_closed(self) -> None:
        self.record_snapshot_1()
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        entry = json.loads(ledger.read_text(encoding="utf-8"))
        future_update = (NOW + timedelta(seconds=1)).isoformat()
        entry["observation"]["source_update_time"] = future_update
        entry["provenance"]["source_timestamp"] = future_update
        entry["source_excerpt"]["source_update_time"] = future_update
        ledger.write_text(json.dumps(entry) + "\n", encoding="utf-8")

        with self.assertRaises(SnapshotError):
            self.workflow.read(RUN_ID)

    def test_persisted_snapshots_require_consistent_event_tipoff(self) -> None:
        self.record_snapshot_2()
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        for entry in entries:
            if entry["kind"] == "snapshot" and entry["number"] == 2:
                entry["event_start"] = (TIPOFF + timedelta(minutes=30)).isoformat()
        ledger.write_text(
            "".join(json.dumps(entry) + "\n" for entry in entries),
            encoding="utf-8",
        )

        with self.assertRaises(SnapshotError):
            self.workflow.read(RUN_ID)

    def test_persisted_event_tipoff_is_consistent_across_candidates(self) -> None:
        at = NOW
        board = make_board(
            at,
            make_projection(at, platform=Platform.PRIZEPICKS),
            make_projection(
                at,
                player_name="M. Robinson",
                direction=Direction.LOWER,
                platform=Platform.UNDERDOG,
            ),
        )
        self.workflow.collect(RUN_ID, 1, board)
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        entries[1]["event_start"] = (TIPOFF + timedelta(minutes=30)).isoformat()
        ledger.write_text(
            "".join(json.dumps(entry) + "\n" for entry in entries),
            encoding="utf-8",
        )

        with self.assertRaises(SnapshotError):
            self.workflow.read(RUN_ID)

    def test_persisted_snapshot_2_requires_snapshot_1_first(self) -> None:
        self.record_snapshot_2()
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

        ledger.write_text(json.dumps(entries[1]) + "\n", encoding="utf-8")

        with self.assertRaises(SnapshotError):
            self.workflow.read(RUN_ID)

    def test_persisted_ledger_rejects_snapshot_2_before_snapshot_1(self) -> None:
        self.record_snapshot_2()
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

        ledger.write_text(
            "".join(json.dumps(entry) + "\n" for entry in reversed(entries)),
            encoding="utf-8",
        )

        with self.assertRaises(SnapshotError):
            self.workflow.read(RUN_ID)

    def test_persisted_snapshot_3_requires_snapshot_2_or_miss_first(self) -> None:
        self.record_snapshot_2()
        snapshot_3_at = TIPOFF - timedelta(minutes=22)
        self.clock.current = snapshot_3_at
        self.workflow.collect(
            RUN_ID,
            3,
            make_board(snapshot_3_at, make_projection(snapshot_3_at)),
        )
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        orphaned = [entry for entry in entries if entry.get("number") != 2]
        ledger.write_text(
            "".join(json.dumps(entry) + "\n" for entry in orphaned),
            encoding="utf-8",
        )

        with self.assertRaises(SnapshotError):
            self.workflow.read(RUN_ID)

    def test_persisted_missed_slot_must_match_snapshot_1_identity(self) -> None:
        self.record_snapshot_1()
        self.clock.current = datetime(2026, 11, 15, 18, 41, tzinfo=UTC)
        self.workflow.mark_snapshot_2_missed(RUN_ID, EVENT_ID)
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        for entry in entries:
            if entry["kind"] == "missed":
                entry["candidate_id"] = "jayson-tatum"
                entry["event_id"] = "evt-other-game"
        ledger.write_text(
            "".join(json.dumps(entry) + "\n" for entry in entries),
            encoding="utf-8",
        )

        with self.assertRaises(SnapshotError):
            self.workflow.read_missed(RUN_ID)

    def test_persisted_snapshot_3_miss_before_tipoff_fails_closed(self) -> None:
        self.record_snapshot_2()
        self.clock.current = TIPOFF + timedelta(minutes=1)
        self.workflow.collect(
            RUN_ID,
            3,
            make_board(self.clock.current, make_projection(self.clock.current)),
        )
        ledger = self.store.run_directory(RUN_ID) / "snapshots" / "ledger.jsonl"
        entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        for entry in entries:
            if entry["kind"] == "missed" and entry["number"] == 3:
                entry["recorded_at"] = (TIPOFF - timedelta(minutes=1)).isoformat()
        ledger.write_text(
            "".join(json.dumps(entry) + "\n" for entry in entries),
            encoding="utf-8",
        )

        with self.assertRaises(SnapshotError):
            self.workflow.read_missed(RUN_ID)


if __name__ == "__main__":
    unittest.main()
