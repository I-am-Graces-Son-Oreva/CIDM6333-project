import hashlib
import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast
from unittest.mock import patch

import fifth_pick.finalization as finalization_module
import fifth_pick.storage as storage_module
from fifth_pick.evidence import EvidenceGap, EvidenceKind, EvidenceSignificance
from fifth_pick.finalization import FinalizationError, finalize_slate
from fifth_pick.methodology import CandidateCase, Confidence, EvaluationStatus
from fifth_pick.models import Category, Direction, Platform, ReasonCode
from fifth_pick.ranking import rank_candidates
from fifth_pick.receipts import Receipt
from fifth_pick.slate_manifest import persist_m4_event_board
from fifth_pick.snapshots import SnapshotWorkflow
from fifth_pick.sources.base import SourceBoard
from fifth_pick.sources.fixtures import FixtureTransport
from fifth_pick.sources.odds_api import API_KEY_ENV_VAR, SOURCE_ID, OddsApiClient
from fifth_pick.sources.quota import QuotaBudget
from fifth_pick.storage import RunStore, application_run_store
from tests.m6_support import EVENT_ID, TIPOFF
from tests.m6_support import make_case as make_m6_case
from tests.test_m7_review import TARGET_AT, make_t20_case
from tests.test_methodology import make_case_from_m5_records, make_live_ledger
from tests.test_snapshots import MutableClock, make_workflow

RUN_ID = "m8-finalization-test"
STARTED_AT = datetime(2026, 11, 15, 17, 0, tzinfo=UTC)


def make_event_rows(
    game_count: int,
    *,
    event_times: tuple[datetime, ...] | None = None,
) -> tuple[dict[str, str], ...]:
    times = (
        event_times
        if event_times is not None
        else tuple(TIPOFF + timedelta(minutes=30 * index) for index in range(game_count))
    )
    if len(times) != game_count:
        raise AssertionError("event_times length must match game_count")
    return tuple(
        {
            "id": EVENT_ID if index == 0 else f"slate-game-{index}",
            "home_team": f"Home Team {index}",
            "away_team": f"Away Team {index}",
            "commence_time": commence_time.isoformat(),
        }
        for index, commence_time in enumerate(times)
    )


def make_m4_board(
    events: tuple[dict[str, str], ...],
    *,
    requested_at: datetime = STARTED_AT,
) -> SourceBoard:
    events_body = json.dumps(events).encode("utf-8")
    odds_bodies = {
        event["id"]: json.dumps({"id": event["id"], "bookmakers": []}).encode("utf-8")
        for event in events
    }
    client = OddsApiClient(
        transport=FixtureTransport(events_body=events_body, odds_bodies=odds_bodies),
        environ={API_KEY_ENV_VAR: "offline-m8-fixture-key"},
        clock=lambda: requested_at,
    )
    return client.fetch_board(
        live_authorized=True,
        budget=QuotaBudget(credits=max(1, len(events) * 5)),
    )


def record_run_slate(
    root: str,
    run_id: str,
    events: tuple[dict[str, str], ...],
    *,
    started_at: datetime = STARTED_AT,
) -> tuple[RunStore, SourceBoard]:
    store = RunStore(root)
    clock = MutableClock(started_at)
    workflow: SnapshotWorkflow = make_workflow(root, clock)
    board = make_m4_board(events, requested_at=started_at)
    workflow.collect(run_id, 1, board)
    workflow.collect(run_id, 3, board)
    return store, board


def make_candidate(
    name: str,
    *,
    confidence: Confidence = Confidence.HIGH,
    **kwargs,
) -> CandidateCase:
    case = make_m6_case(name=name, **kwargs)
    if confidence is not Confidence.HIGH:
        assert case.judgment is not None
        case = replace(case, judgment=replace(case.judgment, confidence=confidence))
    return case


def with_critical_t20_gap(case: CandidateCase) -> CandidateCase:
    return replace(
        case,
        gaps=(
            EvidenceGap(
                kind=EvidenceKind.AVAILABILITY,
                reason=ReasonCode.AVAILABILITY_UNRESOLVED,
                significance=EvidenceSignificance.CRITICAL,
                detail="T-20 availability is unresolved.",
            ),
        ),
    )


class FinalizationTests(unittest.TestCase):
    def test_live_pool_receipt_replays_but_rejects_replacement(self):
        from fifth_pick.finalization import FinalizationError, _pin_live_pool
        from fifth_pick.ranking import RankingResult

        ranking = RankingResult(ranked=(), audits=())
        for offset in (0, 1):
            _pin_live_pool(
                self.store,
                RUN_ID,
                ranking=ranking,
                keys=("first",),
                at=datetime(2026, 11, 18, 22, offset, tzinfo=UTC),
            )
        with self.assertRaisesRegex(FinalizationError, "cannot change the frozen"):
            _pin_live_pool(
                self.store,
                RUN_ID,
                ranking=ranking,
                keys=("replacement",),
                at=datetime(2026, 11, 18, 22, 2, tzinfo=UTC),
            )
        self.assertEqual(len(self.store.read_receipts(RUN_ID)), 1)

    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = RunStore(self.temporary.name)

    def finalize(
        self,
        cases: tuple[CandidateCase, ...],
        current_cases: tuple[tuple[CandidateCase, CandidateCase], ...] = (),
        *,
        run_id: str = RUN_ID,
        tie_breaks: tuple = (),
    ):
        finalizer = self.finalizer()
        return finalizer(
            cases,
            current_cases,
            run_id=run_id,
            store=self.store,
            tie_breaks=tie_breaks,
        )

    def finalizer(self):
        return cast(Any, finalize_slate)

    def review_cases(
        self,
        cases: tuple[CandidateCase, ...],
        *,
        remove: frozenset[str] = frozenset(),
        late: frozenset[str] = frozenset(),
    ) -> tuple[tuple[CandidateCase, CandidateCase], ...]:
        from fifth_pick.t20_review import review_t20

        current_cases = []
        for case in cases:
            current_base = case
            observation = case.snapshots[-1].snapshot.observation
            if observation.player in late:
                current_base = make_m6_case(
                    name=observation.player,
                    platform=observation.platform,
                    category=observation.category,
                    direction=observation.direction,
                    projections=(
                        case.snapshots[0].snapshot.observation.projection,
                        case.snapshots[1].snapshot.observation.projection,
                        case.snapshots[2].snapshot.observation.projection,
                    ),
                    late_snapshot_3=True,
                )
            current = make_t20_case(current_base)
            if observation.player in remove:
                current = with_critical_t20_gap(current)
            review_t20(
                case,
                current,
                reviewed_at=(
                    current.snapshots[-1].snapshot.recorded_at + timedelta(seconds=1)
                    if observation.player in late
                    else TARGET_AT
                ),
                run_id=RUN_ID,
                store=self.store,
            )
            current_cases.append((case, current))
        return tuple(current_cases)

    def prepared_slate(
        self,
        game_count: int,
        names: tuple[str, ...],
        *,
        remove: frozenset[str] = frozenset(),
        late: frozenset[str] = frozenset(),
    ) -> tuple[
        tuple[CandidateCase, ...],
        tuple[tuple[CandidateCase, CandidateCase], ...],
    ]:
        events = make_event_rows(game_count)
        record_run_slate(self.temporary.name, RUN_ID, events)
        cases = tuple(make_candidate(name) for name in names)
        return cases, self.review_cases(cases, remove=remove, late=late)

    def final_record(self) -> dict[str, Any]:
        path = self.store.run_directory(RUN_ID) / "final.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_valid_m6_and_m7_cases_produce_audited_joseph_proposal(self) -> None:
        cases, current = self.prepared_slate(3, ("Luka Doncic", "Derrick White"))

        result = self.finalize(cases, current)

        final = self.final_record()
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )
        expected_order = [item.audit.candidate.player for item in rank_candidates(cases).ranked]
        self.assertEqual(
            result.state.value,
            "AWAITING_JOSEPH",
            json.loads(
                (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
            )["blocking_reasons"],
        )
        self.assertEqual(final["state"], "AWAITING_JOSEPH")
        self.assertEqual([item["player"] for item in final["proposed"]], expected_order)
        self.assertEqual(final["approval"]["action"], None)
        self.assertEqual(final["approval"]["official_final"], None)
        self.assertTrue(audit["m6_ranking"]["ranked"])
        self.assertTrue(audit["m7_reviews"])
        self.assertTrue(self.store.read_receipts(RUN_ID))

    def test_authoritative_one_game_slate_is_half_with_ceiling_four(self) -> None:
        cases, current = self.prepared_slate(
            1,
            (
                "Luka Doncic",
                "Jayson Tatum",
                "Derrick White",
                "Payton Pritchard",
                "Paul George",
            ),
        )

        self.finalize(cases, current)
        final = self.final_record()

        self.assertEqual(final["slate"]["game_count"], 1)
        self.assertEqual(final["slate"]["classification"], "HALF")
        self.assertEqual(final["slate"]["maximum_selections"], 4)
        self.assertEqual(len(final["proposed"]), 4)

    def test_authoritative_four_game_slate_is_half_with_ceiling_four(self) -> None:
        cases, current = self.prepared_slate(
            4,
            ("Luka Doncic", "Jayson Tatum", "Derrick White", "Payton Pritchard"),
        )

        self.finalize(cases, current)
        final = self.final_record()

        self.assertEqual(final["slate"]["game_count"], 4)
        self.assertEqual(final["slate"]["classification"], "HALF")
        self.assertEqual(final["slate"]["maximum_selections"], 4)

    def test_authoritative_five_game_slate_is_full_with_ceiling_five(self) -> None:
        cases, current = self.prepared_slate(
            5,
            (
                "Luka Doncic",
                "Jayson Tatum",
                "Derrick White",
                "Payton Pritchard",
                "Paul George",
                "Michael Porter Jr.",
            ),
        )

        self.finalize(cases, current)
        final = self.final_record()

        self.assertEqual(final["slate"]["game_count"], 5)
        self.assertEqual(final["slate"]["classification"], "FULL")
        self.assertEqual(final["slate"]["maximum_selections"], 5)
        self.assertEqual(len(final["proposed"]), 5)

    def test_larger_authoritative_slate_remains_full_with_ceiling_five(self) -> None:
        cases, current = self.prepared_slate(7, ("Luka Doncic", "Derrick White"))

        self.finalize(cases, current)
        final = self.final_record()

        self.assertEqual(final["slate"]["game_count"], 7)
        self.assertEqual(final["slate"]["classification"], "FULL")
        self.assertEqual(final["slate"]["maximum_selections"], 5)
        self.assertEqual(len(final["proposed"]), 2)

    def test_low_candidate_is_not_promoted_to_fill_an_unused_slot(self) -> None:
        qualified = make_candidate("Derrick White")
        low = make_candidate("Payton Pritchard", confidence=Confidence.LOW)
        record_run_slate(self.temporary.name, RUN_ID, make_event_rows(5))
        current = self.review_cases((qualified, low))

        self.finalize((qualified, low), current)

        final = self.final_record()
        self.assertEqual(len(final["proposed"]), 1)
        self.assertEqual(final["proposed"][0]["player"], "Derrick White")
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )
        self.assertTrue(
            any(
                item["player"] == "Payton Pritchard"
                and EvaluationStatus.ANALYSIS_ONLY.value in item["reasons"]
                for item in audit["exclusions"]
            )
        )

    def test_zero_game_slate_returns_the_exact_no_entry_recommendation(self) -> None:
        record_run_slate(self.temporary.name, RUN_ID, ())

        result = self.finalize((), ())
        final = self.final_record()

        self.assertEqual(final["slate"]["game_count"], 0)
        self.assertEqual(final["recommendation"], "NO ENTRY RECOMMENDED TODAY.")
        self.assertEqual(final["proposed"], [])
        self.assertEqual(result.state.value, "NO_ENTRY")

    def test_unreadable_m7_ledger_does_not_suppress_zero_game_no_entry(self) -> None:
        record_run_slate(self.temporary.name, RUN_ID, ())
        original_read_text = Path.read_text

        def fail_m7_read(path, *args, **kwargs):
            if path.name == "t20-reviews.jsonl":
                raise PermissionError("injected M7 read failure")
            return original_read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", fail_m7_read):
            result = self.finalize((), ())

        final = self.final_record()
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result.state.value, "NO_ENTRY")
        self.assertEqual(final["recommendation"], "NO ENTRY RECOMMENDED TODAY.")
        self.assertEqual(audit["blocking_reasons"], [])

    def test_malformed_m7_ledger_does_not_suppress_zero_game_no_entry(self) -> None:
        record_run_slate(self.temporary.name, RUN_ID, ())
        (self.store.run_directory(RUN_ID) / "t20-reviews.jsonl").write_text(
            "{invalid json}\n",
            encoding="utf-8",
        )

        result = self.finalize((), ())
        final = self.final_record()
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )

        self.assertEqual(result.state.value, "NO_ENTRY")
        self.assertEqual(final["recommendation"], "NO ENTRY RECOMMENDED TODAY.")
        self.assertEqual(audit["blocking_reasons"], [])

    def test_malformed_m7_ledger_does_not_suppress_no_entry_without_ranked_candidates(self) -> None:
        record_run_slate(self.temporary.name, RUN_ID, make_event_rows(1))
        (self.store.run_directory(RUN_ID) / "t20-reviews.jsonl").write_text(
            "{invalid json}\n",
            encoding="utf-8",
        )

        result = self.finalize((make_candidate("Luka Doncic", confidence=Confidence.LOW),), ())
        final = self.final_record()
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )

        self.assertEqual(result.state.value, "NO_ENTRY")
        self.assertEqual(final["recommendation"], "NO ENTRY RECOMMENDED TODAY.")
        self.assertEqual(audit["blocking_reasons"], [])

    def test_unreadable_m7_ledger_does_not_suppress_no_entry_without_ranked_candidates(
        self,
    ) -> None:
        record_run_slate(self.temporary.name, RUN_ID, make_event_rows(1))
        original_read_text = Path.read_text

        def fail_m7_read(path, *args, **kwargs):
            if path.name == "t20-reviews.jsonl":
                raise PermissionError("injected M7 read failure")
            return original_read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", fail_m7_read):
            result = self.finalize(
                (make_candidate("Luka Doncic", confidence=Confidence.LOW),),
                (),
            )

        final = self.final_record()
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result.state.value, "NO_ENTRY")
        self.assertEqual(final["recommendation"], "NO ENTRY RECOMMENDED TODAY.")
        self.assertEqual(audit["blocking_reasons"], [])

    def test_malformed_m7_ledger_blocks_candidate_requiring_t20(self) -> None:
        cases, current = self.prepared_slate(1, ("Luka Doncic",))
        (self.store.run_directory(RUN_ID) / "t20-reviews.jsonl").write_text(
            "{invalid json}\n",
            encoding="utf-8",
        )

        result = self.finalize(cases, current)

        final = self.final_record()
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result.state.value, "BLOCKED")
        self.assertEqual(final["proposed"], [])
        self.assertTrue(
            any("M7 T-20 review ledger unavailable" in item for item in audit["blocking_reasons"])
        )
        self.assertIn(
            "FINALIZATION_BLOCKED",
            {item["event"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_unreadable_m7_ledger_blocks_candidate_requiring_t20(self) -> None:
        cases, current = self.prepared_slate(1, ("Luka Doncic",))
        original_read_text = Path.read_text

        def fail_m7_read(path, *args, **kwargs):
            if path.name == "t20-reviews.jsonl":
                raise PermissionError("injected M7 read failure")
            return original_read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", fail_m7_read):
            result = self.finalize(cases, current)

        final = self.final_record()
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result.state.value, "BLOCKED")
        self.assertEqual(final["proposed"], [])
        self.assertTrue(
            any("M7 T-20 review ledger unavailable" in item for item in audit["blocking_reasons"])
        )
        self.assertIn(
            "FINALIZATION_BLOCKED",
            {item["event"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_isolated_fixture_records_finalize_through_fixture_path(self) -> None:
        cases, current = self.prepared_slate(1, ("Luka Doncic",))

        result = self.finalize(cases, current)

        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )
        authoritative_board = audit["slate"]["authoritative_board"]
        self.assertEqual(result.state.value, "AWAITING_JOSEPH")
        self.assertEqual(authoritative_board["evidence_mode"], "fixture")
        self.assertTrue(
            all(item["evidence_mode"] == "FIXTURE" for item in audit["m6_ranking"]["audits"])
        )

    def test_live_finalization_rejects_caller_selected_storage(self) -> None:
        with (
            TemporaryDirectory() as application_root,
            TemporaryDirectory() as selected_root,
            patch.object(storage_module, "APPLICATION_STORAGE_ROOT", Path(application_root)),
        ):
            selected_store, _workflow, _records, _resolver = make_live_ledger(
                selected_root,
                RUN_ID,
            )

            result = finalize_slate((), (), run_id=RUN_ID, store=selected_store)

            audit = json.loads(
                (selected_store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result.state.value, "BLOCKED")
        self.assertTrue(
            any("application-owned" in item.lower() for item in audit["blocking_reasons"])
        )
        self.assertIsNone(audit["slate"].get("game_count"))

    def test_application_store_accepts_live_m4_and_m6_records_offline(self) -> None:
        with (
            TemporaryDirectory() as application_root,
            patch.object(storage_module, "APPLICATION_STORAGE_ROOT", Path(application_root)),
        ):
            _live_store, _workflow, records, _resolver = make_live_ledger(
                application_root,
                RUN_ID,
            )
            live_case = CandidateCase(
                snapshots=records,
                evidence=(),
                judgment=None,
                snapshot_run_id=RUN_ID,
            )

            result = finalize_slate(
                (live_case,),
                (),
                run_id=RUN_ID,
                store=application_run_store(),
            )
            audit = json.loads(
                (application_run_store().run_directory(RUN_ID) / "audit.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result.state.value, "NO_ENTRY")
        self.assertEqual(audit["slate"]["authoritative_board"]["evidence_mode"], "live")
        self.assertEqual(audit["m6_ranking"]["audits"][0]["evidence_mode"], "LIVE")

    def test_live_and_fixture_m6_evidence_mix_fails_closed(self) -> None:
        with (
            TemporaryDirectory() as application_root,
            patch.object(storage_module, "APPLICATION_STORAGE_ROOT", Path(application_root)),
        ):
            _live_store, _workflow, records, _resolver = make_live_ledger(
                application_root,
                RUN_ID,
            )
            mixed_case = make_case_from_m5_records(records, RUN_ID)

            result = finalize_slate(
                (mixed_case,),
                (),
                run_id=RUN_ID,
                store=application_run_store(),
            )
            audit = json.loads(
                (application_run_store().run_directory(RUN_ID) / "audit.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result.state.value, "BLOCKED")
        self.assertEqual(audit["m6_ranking"]["audits"][0]["evidence_mode"], "MIXED")
        self.assertTrue(any("mix" in item.lower() for item in audit["blocking_reasons"]))

    def test_live_and_fixture_m7_evidence_mix_fails_closed(self) -> None:
        cases, current = self.prepared_slate(1, ("Luka Doncic",))
        review_path = self.store.run_directory(RUN_ID) / "t20-reviews.jsonl"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["current_audit"]["evidence_mode"] = "LIVE"
        review_without_key = {key: value for key, value in review.items() if key != "event_key"}
        canonical = json.dumps(
            review_without_key,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        event_key = f"t20-review-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
        review["event_key"] = event_key
        review_path.write_text(
            json.dumps(review, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        review_reasons = (*review["reason_codes"], *review["audit_reasons"])
        self.store.append_receipt(
            Receipt(
                timestamp=review["reviewed_at"],
                event="T20_REVIEW",
                result=review["conclusion"],
                subject=review["candidate_key"],
                source=SOURCE_ID,
                reason="; ".join(review_reasons),
                run_id=RUN_ID,
                event_key=event_key,
            )
        )

        result = self.finalize(cases, current)
        final = self.final_record()
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )

        self.assertEqual(result.state.value, "BLOCKED")
        self.assertEqual(final["proposed"], [])
        self.assertTrue(any("M7" in item and "mode" in item for item in audit["blocking_reasons"]))

    def test_live_and_fixture_m4_boards_mix_fails_closed(self) -> None:
        with (
            TemporaryDirectory() as application_root,
            patch.object(storage_module, "APPLICATION_STORAGE_ROOT", Path(application_root)),
        ):
            live_store, _workflow, _records, _resolver = make_live_ledger(
                application_root,
                RUN_ID,
            )
            requested_at = STARTED_AT + timedelta(minutes=1)
            fixture_board = make_m4_board(make_event_rows(1), requested_at=requested_at)
            persist_m4_event_board(
                live_store,
                RUN_ID,
                2,
                fixture_board,
                requested_at,
            )

            result = finalize_slate(
                (),
                (),
                run_id=RUN_ID,
                store=application_run_store(),
            )
            audit = json.loads(
                (application_run_store().run_directory(RUN_ID) / "audit.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result.state.value, "BLOCKED")
        self.assertTrue(any("mix" in item.lower() for item in audit["blocking_reasons"]))

    def test_adjacent_local_dates_do_not_change_the_pinned_slate_count(self) -> None:
        request_at = datetime(2026, 11, 16, 5, 30, tzinfo=UTC)
        event_times = (
            datetime(2026, 11, 16, 5, 45, tzinfo=UTC),
            datetime(2026, 11, 16, 6, 15, tzinfo=UTC),
            datetime(2026, 11, 16, 6, 45, tzinfo=UTC),
            datetime(2026, 11, 16, 7, 15, tzinfo=UTC),
        )
        record_run_slate(
            self.temporary.name,
            RUN_ID,
            make_event_rows(4, event_times=event_times),
            started_at=request_at,
        )

        self.finalize((), ())
        final = self.final_record()

        self.assertEqual(final["slate"]["slate_date"], "2026-11-15")
        self.assertEqual(final["slate"]["game_count"], 1)
        self.assertEqual(final["slate"]["classification"], "HALF")

    def test_timezone_conversion_around_midnight_uses_chicago_calendar_date(self) -> None:
        request_at = datetime(2026, 11, 16, 5, 30, tzinfo=UTC)
        record_run_slate(
            self.temporary.name,
            RUN_ID,
            make_event_rows(
                2,
                event_times=(
                    datetime(2026, 11, 16, 5, 45, tzinfo=UTC),
                    datetime(2026, 11, 16, 6, 15, tzinfo=UTC),
                ),
            ),
            started_at=request_at,
        )

        self.finalize((), ())

        final = self.final_record()
        self.assertEqual(final["slate"]["slate_date"], "2026-11-15")
        self.assertEqual(final["slate"]["slate_timezone"], "America/Chicago")
        self.assertEqual(final["slate"]["game_count"], 1)

    def test_duplicate_m4_event_board_observations_count_event_id_once(self) -> None:
        events = make_event_rows(4)
        record_run_slate(self.temporary.name, RUN_ID, events)

        self.finalize((), ())
        final = self.final_record()

        self.assertEqual(final["slate"]["game_count"], 4)

    def test_candidate_event_count_cannot_replace_authoritative_slate_count(self) -> None:
        cases, current = self.prepared_slate(5, ("Luka Doncic",))

        self.finalize(cases, current)

        final = self.final_record()
        self.assertEqual(final["slate"]["game_count"], 5)
        self.assertEqual(final["slate"]["classification"], "FULL")

    def test_caller_cannot_supply_game_count_or_classification(self) -> None:
        cases, current = self.prepared_slate(4, ("Luka Doncic",))
        finalizer = self.finalizer()

        with self.assertRaises(TypeError):
            finalizer(cases, current, run_id=RUN_ID, store=self.store, game_count=5)
        with self.assertRaises(TypeError):
            finalizer(cases, current, run_id=RUN_ID, store=self.store, slate_type="FULL")

    def test_missing_authoritative_manifest_fails_closed_with_audit_reason(self) -> None:
        cases = (make_candidate("Luka Doncic"),)

        result = self.finalize(cases, ())
        final = self.final_record()
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )

        self.assertEqual(result.state.value, "BLOCKED")
        self.assertIsNone(final["slate"]["game_count"])
        self.assertTrue(any("manifest" in reason.lower() for reason in audit["blocking_reasons"]))
        self.assertIn(
            "FINALIZATION_BLOCKED",
            {item["event"] for item in self.store.read_receipts(RUN_ID)},
        )

    def test_fabricated_manifest_without_m5_receipt_fails_closed(self) -> None:
        run_directory = self.store.run_directory(RUN_ID)
        run_directory.mkdir(parents=True)
        (run_directory / "run.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "run_id": RUN_ID,
                    "started_at": STARTED_AT.isoformat(),
                    "slate_date": "2026-11-15",
                    "slate_timezone": "America/Chicago",
                    "start_source": "the-odds-api-us-dfs",
                    "start_payload_sha256": "a" * 64,
                }
            ),
            encoding="utf-8",
        )
        (run_directory / "m4-event-boards.jsonl").write_text(
            json.dumps({"run_id": RUN_ID, "event_ids": [EVENT_ID]}) + "\n",
            encoding="utf-8",
        )

        result = self.finalize((), ())

        self.assertEqual(result.state.value, "BLOCKED")
        self.assertEqual(self.final_record()["proposed"], [])

    def test_wrong_run_binding_fails_closed(self) -> None:
        record_run_slate(self.temporary.name, "another-run", make_event_rows(1))

        result = self.finalize((), (), run_id=RUN_ID)

        self.assertEqual(result.state.value, "BLOCKED")
        self.assertIsNone(self.final_record()["slate"]["game_count"])

    def test_valid_m4_owned_manifest_is_required_for_finalization(self) -> None:
        cases, current = self.prepared_slate(1, ("Luka Doncic",))

        result = self.finalize(cases, current)

        self.assertEqual(result.state.value, "AWAITING_JOSEPH")
        self.assertEqual(self.final_record()["slate"]["game_count"], 1)

    def test_stale_or_missing_t20_candidate_is_excluded(self) -> None:
        cases = (make_candidate("Luka Doncic"), make_candidate("Derrick White"))
        record_run_slate(self.temporary.name, RUN_ID, make_event_rows(2))
        current = self.review_cases(cases[:1], late=frozenset({"Luka Doncic"}))

        self.finalize(cases, current)
        final = self.final_record()
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )

        self.assertEqual(final["proposed"], [])
        reasons = [reason for exclusion in audit["exclusions"] for reason in exclusion["reasons"]]
        self.assertIn(ReasonCode.T20_CHECK_UNAVAILABLE.value, reasons)
        self.assertTrue(
            any(
                item["candidate_key"] == cases[1].snapshots[-1].candidate_key
                for item in audit["exclusions"]
            )
        )

    def test_t20_removal_does_not_replace_from_below_the_frozen_ceiling_pool(self) -> None:
        names = (
            "Luka Doncic",
            "Jayson Tatum",
            "Derrick White",
            "Payton Pritchard",
            "Paul George",
        )
        cases = tuple(make_candidate(name) for name in names)
        record_run_slate(self.temporary.name, RUN_ID, make_event_rows(1))
        current = self.review_cases(cases, remove=frozenset({"Luka Doncic"}))

        self.finalize(cases, current)
        final = self.final_record()

        self.assertEqual(len(final["proposed"]), 3)
        self.assertNotIn("Paul George", {item["player"] for item in final["proposed"]})

    def test_no_player_occupies_two_final_slots(self) -> None:
        cases = (
            make_candidate("Luka Doncic"),
            make_candidate("Luka Doncic", category=Category.PRA),
        )
        record_run_slate(self.temporary.name, RUN_ID, make_event_rows(1))
        current = self.review_cases(cases)

        self.finalize(cases, current)

        final = self.final_record()
        self.assertEqual(len(final["proposed"]), 1)
        self.assertEqual(len({item["player_id"] for item in final["proposed"]}), 1)

    def test_senior_priority_and_m6_qualitative_order_are_preserved(self) -> None:
        cases = (
            make_candidate("Derrick White"),
            make_candidate("Luka Doncic", confidence=Confidence.MEDIUM),
            make_candidate("Jayson Tatum"),
        )
        record_run_slate(self.temporary.name, RUN_ID, make_event_rows(5))
        current = self.review_cases(cases)
        expected = [item.audit.candidate_key for item in rank_candidates(cases).ranked]

        self.finalize(cases, current)

        final = self.final_record()
        self.assertEqual([item["candidate_key"] for item in final["proposed"]], expected)

    def test_unauthorized_candidate_is_excluded_before_final_membership(self) -> None:
        cases = (make_candidate("Outside Universe Player"),)
        record_run_slate(self.temporary.name, RUN_ID, make_event_rows(1))

        self.finalize(cases, ())

        final = self.final_record()
        self.assertEqual(final["proposed"], [])
        audit = json.loads(
            (self.store.run_directory(RUN_ID) / "audit.json").read_text(encoding="utf-8")
        )
        self.assertTrue(
            any(
                ReasonCode.PLAYER_IDENTITY_UNRESOLVED.value in item["reasons"]
                for item in audit["exclusions"]
            )
        )

    def test_unauthorized_category_and_direction_cannot_enter_final_set(self) -> None:
        cases = (
            make_candidate("Luka Doncic", category=Category.REBOUNDS_ASSISTS),
            make_candidate("Mitchell Robinson", direction=Direction.HIGHER),
        )
        record_run_slate(self.temporary.name, RUN_ID, make_event_rows(1))

        self.finalize(cases, ())

        self.assertEqual(self.final_record()["proposed"], [])

    def test_wrong_platform_t20_case_cannot_satisfy_ranked_candidate(self) -> None:
        prior = make_candidate("Luka Doncic")
        current = make_t20_case(make_candidate("Luka Doncic", platform=Platform.UNDERDOG))
        record_run_slate(self.temporary.name, RUN_ID, make_event_rows(1))

        self.finalize((prior,), ((prior, current),))

        self.assertEqual(self.final_record()["proposed"], [])

    def test_finalization_rejects_caller_supplied_rank_or_review_results(self) -> None:
        record_run_slate(self.temporary.name, RUN_ID, make_event_rows(1))
        finalizer = cast(Any, finalize_slate)
        fake_ranked_result = type("FakeRankedResult", (), {"ranked": (), "audits": ()})()

        with self.assertRaises(TypeError):
            finalizer(fake_ranked_result, (), run_id=RUN_ID, store=self.store)

    def test_repeated_finalization_is_idempotent_and_does_not_recompute_replacements(self) -> None:
        cases, current = self.prepared_slate(1, ("Luka Doncic", "Derrick White"))

        first = self.finalize(cases, current)
        first_bytes = (self.store.run_directory(RUN_ID) / "final.json").read_bytes()
        first_receipts = self.store.read_receipts(RUN_ID)
        second = self.finalize((), ())

        self.assertEqual(second.state, first.state)
        self.assertEqual(
            (self.store.run_directory(RUN_ID) / "final.json").read_bytes(), first_bytes
        )
        self.assertEqual(self.store.read_receipts(RUN_ID), first_receipts)

    def test_retry_reuses_the_persisted_proposal_receipt_timestamp(self) -> None:
        cases, current = self.prepared_slate(1, ("Luka Doncic",))
        write_json = finalization_module._write_json

        def fail_final_write(path, record) -> None:
            if path.name == "final.json":
                raise FinalizationError("injected final artifact failure")
            write_json(path, record)

        with (
            patch.object(finalization_module, "_write_json", side_effect=fail_final_write),
            self.assertRaises(FinalizationError),
        ):
            finalize_slate(cases, current, run_id=RUN_ID, store=self.store)

        proposal_receipt = next(
            item
            for item in self.store.read_receipts(RUN_ID)
            if item["event"] == "FINAL_SELECTION_PROPOSED"
        )
        self.finalize(cases, current)
        final = self.final_record()

        self.assertEqual(final["proposal_recorded_at"], proposal_receipt["timestamp"])

    def test_retry_reuses_the_persisted_blocked_receipt_timestamp(self) -> None:
        write_json = finalization_module._write_json

        def fail_final_write(path, record) -> None:
            if path.name == "final.json":
                raise FinalizationError("injected blocked artifact failure")
            write_json(path, record)

        with (
            patch.object(finalization_module, "_write_json", side_effect=fail_final_write),
            self.assertRaises(FinalizationError),
        ):
            finalize_slate((), (), run_id=RUN_ID, store=self.store)

        blocked_receipt = next(
            item
            for item in self.store.read_receipts(RUN_ID)
            if item["event"] == "FINALIZATION_BLOCKED"
        )
        retry = self.finalize((), ())
        final = self.final_record()

        self.assertEqual(retry.state.value, "BLOCKED")
        self.assertEqual(final["proposal_recorded_at"], blocked_receipt["timestamp"])
        self.assertEqual(self.finalize((), ()).state.value, "BLOCKED")

    def test_finalization_does_not_add_m9_or_submission_behavior(self) -> None:
        cases, current = self.prepared_slate(1, ("Luka Doncic",))

        self.finalize(cases, current)

        run_directory = self.store.run_directory(RUN_ID)
        final_text = (run_directory / "final.json").read_text(encoding="utf-8").lower()
        self.assertNotIn("hit", final_text)
        self.assertNotIn("miss", final_text)
        self.assertFalse((run_directory / "results.json").exists())
        self.assertFalse((run_directory / "submission.json").exists())
        self.assertEqual(
            {path.name for path in run_directory.iterdir()},
            {
                "receipts.jsonl",
                "run.json",
                "m4-event-boards.jsonl",
                "t20-reviews.jsonl",
                "final.json",
                "audit.json",
            },
        )


if __name__ == "__main__":
    unittest.main()
