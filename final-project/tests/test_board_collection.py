import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fifth_pick.board_collection import BoardCollector, BoardPolicy
from fifth_pick.errors import FifthPickError
from fifth_pick.slate_manifest import read_slate_run_context
from fifth_pick.sources.base import (
    BudgetExceededError,
    MalformedPayloadError,
    MissingApiKeyError,
    QuotaExhaustedError,
    SourceError,
    UnauthorizedResponseError,
)
from fifth_pick.sources.fixtures import FixtureTransport
from fifth_pick.sources.odds_api import API_KEY_ENV_VAR, OddsApiSourceConfig, events_url, odds_url
from fifth_pick.sources.transport import UrllibTransport
from fifth_pick.storage import RunStore
from tests.test_odds_api import FIXTURE_DIR, SECRET, fixture_responses

NOW = datetime(2026, 11, 15, 17, 10, tzinfo=UTC)
EVENT = "evt-lal-dal-20261115"
OTHER = "evt-bos-nyk-20261115"
RUN = "board-test"


class BoardCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = RunStore(directory.name)
        self.policy = BoardPolicy(
            credit_limit=5,
            event_ids=(EVENT, OTHER),
            max_projection_age=timedelta(minutes=30),
            aliases={"Luka Doncic": ("luka-doncic",), "LeBron James": ("lebron-james",)},
            alias_review_reference="fixture:reviewed-provider-aliases",
        )
        self.responses = fixture_responses()
        self.transport = FixtureTransport(
            events_body=(FIXTURE_DIR / "events.json").read_bytes(), odds_bodies={}
        )
        self.calls: list[str] = []
        patcher = patch.object(self.transport, "get", side_effect=self.respond)
        patcher.start()
        self.addCleanup(patcher.stop)

    def respond(self, url, headers):
        self.calls.append(url)
        return self.responses[url]

    def collector(self, *, transport=None, environ=None):
        return BoardCollector(
            self.store,
            self.policy,
            transport=self.transport if transport is None else transport,
            environ={API_KEY_ENV_VAR: SECRET} if environ is None else environ,
            clock=lambda: NOW,
        )

    def test_selected_event_replay_and_durable_run_budget(self):
        entries = self.collector().collect(RUN, 1, EVENT, request_authorized=True)
        self.assertTrue(entries)
        self.assertTrue(all(entry.event_id == EVENT for entry in entries))
        expected = [events_url(), odds_url(EVENT, OddsApiSourceConfig())]
        self.assertEqual(self.calls, expected)
        receipts = self.store.read_receipts(RUN)
        self.assertEqual(self.collector().collect(RUN, 1, EVENT, request_authorized=True), entries)
        self.assertEqual(self.store.read_receipts(RUN), receipts)
        with self.assertRaises(BudgetExceededError):
            self.collector().collect(RUN, 1, OTHER, request_authorized=True)
        self.assertEqual(self.calls, expected)

    def test_missing_authorization_credentials_and_live_mode_make_no_calls(self):
        with self.assertRaises(SourceError):
            self.collector().collect(RUN, 1, EVENT)
        with self.assertRaises(SourceError):
            self.collector(environ={}).collect(RUN, 1, EVENT, request_authorized=True)
        with (
            patch.object(UrllibTransport, "get", side_effect=AssertionError("network")),
            self.assertRaises(SourceError),
        ):
            self.collector(transport=UrllibTransport()).collect(
                RUN, 1, EVENT, request_authorized=True
            )
        self.assertEqual(self.calls, [])

    def update_response(self, url, **changes):
        self.responses[url] = replace(self.responses[url], **changes)

    def change_odds(self, callback):
        url = odds_url(EVENT, OddsApiSourceConfig())
        data = json.loads(self.responses[url].body)
        callback(data)
        self.update_response(url, body=json.dumps(data).encode())

    def test_partial_http_failure_reserves_credit_and_never_retries(self):
        odds = odds_url(EVENT, OddsApiSourceConfig())
        self.update_response(odds, status=401)
        with self.assertRaises(UnauthorizedResponseError):
            self.collector().collect(RUN, 1, EVENT, request_authorized=True)
        receipts = self.store.read_receipts(RUN)
        self.assertEqual(
            [row["result"] for row in receipts if row["event"] == "DFS_HTTP_RESPONSE"],
            ["200", "401"],
        )
        self.assertEqual(
            [row["reason"] for row in receipts if row["event"] == "DFS_BOARD_RESERVED"],
            ["credits=5"],
        )
        self.assertNotIn(SECRET, json.dumps(receipts))
        self.assertFalse((self.store.run_directory(RUN) / "snapshots").exists())
        self.update_response(odds, status=200)
        with self.assertRaisesRegex(SourceError, "unfinished collection"):
            self.collector().collect(RUN, 1, EVENT, request_authorized=True)
        self.assertEqual(self.calls, [events_url(), odds])
        self.assertEqual(self.store.read_receipts(RUN), receipts)

    def test_provider_quota_exhaustion_stops_before_paid_request(self):
        self.update_response(events_url(), headers={"x-requests-remaining": "4"})
        with self.assertRaises(QuotaExhaustedError):
            self.collector().collect(RUN, 1, EVENT, request_authorized=True)
        self.assertEqual(self.calls, [events_url()])

    def test_out_of_scope_event_is_rejected_before_any_transport_call(self):
        with self.assertRaisesRegex(SourceError, "outside the authorized request scope"):
            self.collector().collect(RUN, 1, "outside", request_authorized=True)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.store.run_directory(RUN).exists())

    def test_stale_board_has_no_snapshot_and_preserves_response_metadata(self):
        self.policy = replace(self.policy, max_projection_age=timedelta(minutes=1))
        with self.assertRaisesRegex(SourceError, "stale"):
            self.collector().collect(RUN, 1, EVENT, request_authorized=True)
        receipts = self.store.read_receipts(RUN)
        metadata = json.loads(
            next(
                row["reason"] for row in receipts if row["event_key"] == f"dfs-board-1-{EVENT}-odds"
            )
            or ""
        )
        self.assertTrue(metadata["url"].endswith("bookmakers=prizepicks,underdog"))
        self.assertEqual(metadata["retrieved_at"], NOW.isoformat())
        self.assertEqual(len(metadata["payload_sha256"]), 64)
        self.assertFalse((self.store.run_directory(RUN) / "snapshots").exists())

    def test_ambiguous_alias_is_not_guessed_and_scope_preserves_full_catalog(self):
        self.policy = replace(
            self.policy,
            aliases={**self.policy.aliases, "Luka Doncic": ("luka-doncic", "jayson-tatum")},
        )
        entries = self.collector().collect(RUN, 1, EVENT, request_authorized=True)
        self.assertTrue(entries)
        self.assertEqual({row.candidate_id for row in entries}, {"lebron-james"})
        receipts = self.store.read_receipts(RUN)
        self.assertTrue(any(row["result"] == "IDENTITY_UNRESOLVED" for row in receipts))
        context = read_slate_run_context(self.store, RUN)
        self.assertEqual(
            {event.event_id for event in context.event_boards[0].events}, {EVENT, OTHER}
        )

    def test_exact_duplicate_collapses_but_conflicting_line_blocks_event(self):
        def duplicate(data, *, conflict):
            outcomes = data["bookmakers"][0]["markets"][0]["outcomes"]
            outcome = dict(outcomes[0])
            if conflict:
                outcome["point"] += 1
            outcomes.append(outcome)

        self.change_odds(lambda data: duplicate(data, conflict=False))
        entries = self.collector().collect(RUN, 1, EVENT, request_authorized=True)
        self.assertEqual(len(entries), len({entry.candidate_key for entry in entries}))
        self.assertEqual(
            {row.snapshot.observation.platform.value for row in entries},
            {"prizepicks", "underdog"},
        )
        self.change_odds(lambda data: duplicate(data, conflict=True))
        with self.assertRaisesRegex(MalformedPayloadError, "conflicting duplicate"):
            self.collector().collect("conflicting-board", 1, EVENT, request_authorized=True)
        self.assertFalse((self.store.run_directory("conflicting-board") / "snapshots").exists())

    def test_wrong_event_response_is_rejected(self):
        self.change_odds(lambda data: data.update(id=OTHER))
        with self.assertRaisesRegex(MalformedPayloadError, "identity differs"):
            self.collector().collect(RUN, 1, EVENT, request_authorized=True)

    def test_replay_rejects_policy_change_and_tampered_metadata(self):
        self.collector().collect(RUN, 1, EVENT, request_authorized=True)
        self.policy = replace(self.policy, credit_limit=10)
        with self.assertRaisesRegex(SourceError, "pinned policy"):
            self.collector().collect(RUN, 1, EVENT, request_authorized=True)
        self.policy = replace(self.policy, credit_limit=5)
        path = self.store.receipts_path(RUN)
        data = [json.loads(line) for line in path.read_text().splitlines()]
        key = f"dfs-board-1-{EVENT}-odds"
        next(row for row in data if row["event_key"] == key)["result"] = "402"
        path.write_text("".join(json.dumps(row) + "\n" for row in data))
        with self.assertRaisesRegex(SourceError, "stored board"):
            self.collector().collect(RUN, 1, EVENT, request_authorized=True)
        self.assertEqual(len(self.calls), 2)

    def test_concurrent_confirmation_reserves_once(self):
        collector = self.collector()

        def collect():
            return collector.collect(RUN, 1, EVENT, request_authorized=True)

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(collect)
            second = pool.submit(collect)
            self.assertEqual(first.result(timeout=10), second.result(timeout=10))
        self.assertEqual(self.calls, [events_url(), odds_url(EVENT, OddsApiSourceConfig())])
        self.assertEqual(
            sum(row["event"] == "DFS_BOARD_RESERVED" for row in self.store.read_receipts(RUN)), 1
        )

    def test_existing_non_stage_run_is_not_adopted(self):
        self.store.run_directory(RUN).mkdir(parents=True)
        with self.assertRaisesRegex(SourceError, "requires a fresh run"):
            self.collector().collect(RUN, 1, EVENT, request_authorized=True)
        self.assertEqual(self.calls, [])

    def test_offline_collector_does_not_inherit_ambient_credentials(self):
        with patch.dict(os.environ, {API_KEY_ENV_VAR: SECRET}):
            collector = BoardCollector(
                self.store, self.policy, transport=self.transport, clock=lambda: NOW
            )
            with self.assertRaises(MissingApiKeyError):
                collector.collect(RUN, 1, EVENT, request_authorized=True)
        self.assertEqual(self.calls, [])

    def live_collector(self, *, slate_ids=(EVENT, OTHER), series=False, official_offset=None):
        from fifth_pick.board_collection import LiveBoardGrant
        from fifth_pick.personal_readiness import LiveEventScope

        policy = replace(self.policy, event_ids=(EVENT,), credit_limit=15 if series else 5)
        if series and official_offset is None:
            official_offset = timedelta()
        scope = LiveEventScope(
            EVENT,
            "Los Angeles Lakers",
            "Dallas Mavericks",
            datetime(2026, 11, 16, 2, tzinfo=UTC),
            ("luka-doncic",),
        )
        grant = LiveBoardGrant(
            RUN,
            "approved test",
            "verified test billing",
            scope.tipoff if series else NOW + timedelta(minutes=5),
            policy.fingerprint(),
            (scope,),
            slate_ids,
            (1, 2, 3) if series else (1,),
            None if official_offset is None else scope.tipoff + official_offset,
            None if official_offset is None else "https://www.nba.com/schedule",
        )
        self.update_response(
            events_url(),
            headers={"x-requests-last": "0", "x-requests-remaining": "500", "x-requests-used": "0"},
        )
        return BoardCollector(
            self.store,
            policy,
            transport=UrllibTransport(),
            live_grant=grant,
            environ={API_KEY_ENV_VAR: SECRET},
        )

    def test_wrong_live_event_is_not_archived(self):
        self.change_odds(lambda data: data.update(id=OTHER))
        with (
            patch("fifth_pick.board_collection.application_run_store", return_value=self.store),
            patch("fifth_pick.board_collection._application_clock", return_value=NOW),
            patch.object(UrllibTransport, "get", side_effect=self.respond),
            self.assertRaises(SourceError),
        ):
            self.live_collector().collect(RUN, 1, EVENT, request_authorized=True)
        self.assertFalse(list(self.store.run_directory(RUN).glob("*.body")))
        self.assertTrue(
            any(row["event"] == "DFS_BOARD_STOPPED" for row in self.store.read_receipts(RUN))
        )

    def test_quarantine_uses_one_response_and_never_admits_unmatched_labels(self):
        from fifth_pick.board_collection import live_slot_has_bound_aliases

        self.change_odds(
            lambda data: data["bookmakers"][0]["markets"][0]["outcomes"].append(
                {"name": "Over", "description": "Unmatched label", "point": "untrusted"}
            )
        )
        with (
            patch("fifth_pick.board_collection.application_run_store", return_value=self.store),
            patch("fifth_pick.board_collection._application_clock", return_value=NOW),
            patch.object(UrllibTransport, "get", side_effect=self.respond),
        ):
            original = self.live_collector()
            assert original._grant is not None
            policy = replace(original._policy, aliases={})
            provider = original._grant.events[0].tipoff
            cutoff = provider - timedelta(minutes=90)
            grant = replace(
                original._grant,
                policy_sha256=policy.fingerprint(),
                expires_at=cutoff,
                official_tipoff=provider - timedelta(minutes=10),
                timing_reference="https://example.test/official",
            )

            def review(labels):
                self.assertIn("Unmatched label", labels)
                self.assertIn("Luka Doncic", labels)
                self.assertFalse(live_slot_has_bound_aliases(RUN, 1, EVENT))
                return {"Luka Doncic": "luka-doncic"}, {
                    "Luka Doncic": "https://example.test/identity"
                }

            collector = BoardCollector(
                self.store,
                policy,
                transport=UrllibTransport(),
                live_grant=grant,
                environ={API_KEY_ENV_VAR: SECRET},
                review_quarantined_labels=review,
            )
            entries = collector.collect(RUN, 1, EVENT, request_authorized=True)
            self.assertTrue(entries)
            self.assertEqual({row.candidate_id for row in entries}, {"luka-doncic"})
            self.assertTrue(all(row.event_start == provider for row in entries))
            self.assertTrue(live_slot_has_bound_aliases(RUN, 1, EVENT))
            self.assertEqual(collector.collect(RUN, 1, EVENT, request_authorized=True), entries)
        self.assertEqual(self.calls, [events_url(), odds_url(EVENT, OddsApiSourceConfig())])
        receipts = self.store.read_receipts(RUN)
        self.assertIn("Unmatched label", str(receipts))
        self.assertIn(cutoff.isoformat(), str(receipts))
        self.assertNotIn(SECRET, str(receipts))

    def test_identity_review_crossing_cutoff_leaves_quarantine_without_snapshot_or_retry(self):
        from fifth_pick.snapshots import read_receipted_snapshot_ledger

        with (
            patch("fifth_pick.board_collection.application_run_store", return_value=self.store),
            patch("fifth_pick.board_collection._application_clock", return_value=NOW) as clock,
            patch.object(UrllibTransport, "get", side_effect=self.respond),
        ):
            original = self.live_collector()
            assert original._grant is not None
            policy = replace(original._policy, aliases={})
            provider = original._grant.events[0].tipoff
            cutoff = provider - timedelta(minutes=90)
            grant = replace(
                original._grant,
                policy_sha256=policy.fingerprint(),
                expires_at=cutoff,
                official_tipoff=provider - timedelta(minutes=10),
                timing_reference="https://example.test/official",
            )

            def review(_labels):
                clock.return_value = cutoff
                return {"Luka Doncic": "luka-doncic"}, {
                    "Luka Doncic": "https://example.test/identity"
                }

            collector = BoardCollector(
                self.store,
                policy,
                transport=UrllibTransport(),
                live_grant=grant,
                environ={API_KEY_ENV_VAR: SECRET},
                review_quarantined_labels=review,
            )
            with self.assertRaises(SourceError):
                collector.collect(RUN, 1, EVENT, request_authorized=True)
            self.assertEqual(read_receipted_snapshot_ledger(self.store, RUN), ())
            self.assertTrue(
                any(
                    row["event"] == "DFS_BOARD_LABEL_QUARANTINE"
                    for row in self.store.read_receipts(RUN)
                )
            )
            clock.return_value = NOW
            with self.assertRaisesRegex(SourceError, "unfinished collection"):
                collector.collect(RUN, 1, EVENT, request_authorized=True)
        self.assertEqual(self.calls, [events_url(), odds_url(EVENT, OddsApiSourceConfig())])

    def test_interrupted_identity_review_records_stop_without_retry(self):
        from fifth_pick.snapshots import read_receipted_snapshot_ledger

        with (
            patch("fifth_pick.board_collection.application_run_store", return_value=self.store),
            patch("fifth_pick.board_collection._application_clock", return_value=NOW),
            patch.object(UrllibTransport, "get", side_effect=self.respond),
        ):
            original = self.live_collector()
            assert original._grant is not None
            policy = replace(original._policy, aliases={})
            provider = original._grant.events[0].tipoff
            cutoff = provider - timedelta(minutes=90)
            grant = replace(
                original._grant,
                policy_sha256=policy.fingerprint(),
                expires_at=cutoff,
                official_tipoff=provider - timedelta(minutes=10),
                timing_reference="https://example.test/official",
            )

            def review(_labels):
                raise KeyboardInterrupt

            collector = BoardCollector(
                self.store,
                policy,
                transport=UrllibTransport(),
                live_grant=grant,
                environ={API_KEY_ENV_VAR: SECRET},
                review_quarantined_labels=review,
            )
            with self.assertRaises(SourceError):
                collector.collect(RUN, 1, EVENT, request_authorized=True)
            self.assertEqual(read_receipted_snapshot_ledger(self.store, RUN), ())
            self.assertTrue(
                any(
                    row["event"] == "DFS_BOARD_LABEL_QUARANTINE"
                    for row in self.store.read_receipts(RUN)
                )
            )
            self.assertTrue(
                any(
                    row["event"] == "DFS_BOARD_STOPPED" and row["reason"] == "KeyboardInterrupt"
                    for row in self.store.read_receipts(RUN)
                )
            )
            with self.assertRaisesRegex(SourceError, "unfinished collection"):
                collector.collect(RUN, 1, EVENT, request_authorized=True)
        archive = self.store.run_directory(RUN) / f"dfs-board-1-{EVENT}-odds.body"
        expected = self.responses[odds_url(EVENT, OddsApiSourceConfig())].body
        self.assertEqual(archive.read_bytes(), expected)
        from fifth_pick.board_inspect_cli import inspect_board
        from fifth_pick.sources.alias_crosswalk import BoardIdentity, RosterIdentity

        before = self.store.receipts_path(RUN).read_bytes()
        held = inspect_board(self.store, RUN, EVENT, 1)
        self.assertEqual(held["lines"], [])
        self.assertIn("Luka Doncic", str(held["quarantined_labels"]))
        roster = (
            RosterIdentity(
                "nba-id", "luka-doncic", "Los Angeles Lakers", "https://example.test/roster"
            ),
        )
        identities = (
            BoardIdentity(
                "nba-id",
                "Luka Doncic",
                EVENT,
                "Los Angeles Lakers",
                "https://example.test/identity",
            ),
        )
        result = inspect_board(self.store, RUN, EVENT, 1, roster=roster, identities=identities)
        self.assertFalse(result["live_admission"])
        self.assertTrue(result["lines"])
        self.assertEqual(self.store.receipts_path(RUN).read_bytes(), before)
        self.assertFalse((self.store.run_directory(RUN) / "run.json").exists())
        archive.write_bytes(expected + b" ")
        with self.assertRaisesRegex(FifthPickError, "differs from the capture receipt"):
            inspect_board(self.store, RUN, EVENT, 1)

        self.assertEqual(self.calls, [events_url(), odds_url(EVENT, OddsApiSourceConfig())])

    def test_uncommitted_snapshot_rows_are_excluded_from_operational_ledger(self):
        from fifth_pick.snapshots import (
            SnapshotWorkflow,
            read_receipted_snapshot_ledger,
            read_snapshot_ledger,
        )

        collect = SnapshotWorkflow.collect

        def collect_then_expire(workflow, *args, **kwargs):
            entries = collect(workflow, *args, **kwargs)
            self.assertTrue(entries)
            clock.return_value = cutoff
            return entries

        with (
            patch("fifth_pick.board_collection.application_run_store", return_value=self.store),
            patch("fifth_pick.board_collection._application_clock", return_value=NOW) as clock,
            patch.object(UrllibTransport, "get", side_effect=self.respond),
        ):
            original = self.live_collector()
            assert original._grant is not None
            policy = replace(original._policy, aliases={})
            provider = original._grant.events[0].tipoff
            cutoff = provider - timedelta(minutes=90)
            grant = replace(
                original._grant,
                policy_sha256=policy.fingerprint(),
                expires_at=cutoff,
                official_tipoff=provider - timedelta(minutes=10),
                timing_reference="https://example.test/official",
            )

            def review(_labels):
                return {"Luka Doncic": "luka-doncic"}, {
                    "Luka Doncic": "https://example.test/identity"
                }

            collector = BoardCollector(
                self.store,
                policy,
                transport=UrllibTransport(),
                live_grant=grant,
                environ={API_KEY_ENV_VAR: SECRET},
                review_quarantined_labels=review,
            )
            with (
                patch.object(SnapshotWorkflow, "collect", collect_then_expire),
                self.assertRaises(SourceError),
            ):
                collector.collect(RUN, 1, EVENT, request_authorized=True)
            self.assertTrue(read_snapshot_ledger(self.store, RUN))
            clock.return_value = NOW
            self.assertEqual(read_receipted_snapshot_ledger(self.store, RUN), ())
            self.assertTrue(
                any(
                    row["event"] == "DFS_BOARD_LABEL_QUARANTINE"
                    for row in self.store.read_receipts(RUN)
                )
            )
            self.assertTrue(
                any(row["event"] == "DFS_BOARD_STOPPED" for row in self.store.read_receipts(RUN))
            )
            with self.assertRaisesRegex(SourceError, "unfinished collection"):
                collector.collect(RUN, 1, EVENT, request_authorized=True)
        self.assertEqual(self.calls, [events_url(), odds_url(EVENT, OddsApiSourceConfig())])

    def test_live_grant_filters_before_parsing_and_replays_without_network(self):
        from fifth_pick.sources.base import EvidenceMode

        def append_untrusted(data):
            data["bookmakers"][0]["markets"][0]["outcomes"].append(
                {"name": "Over", "description": "Out of universe", "point": "not a number"}
            )

        self.change_odds(append_untrusted)
        with (
            patch("fifth_pick.board_collection.application_run_store", return_value=self.store),
            patch("fifth_pick.board_collection._application_clock", return_value=NOW),
            patch.object(UrllibTransport, "get", side_effect=self.respond),
        ):
            collector = self.live_collector()
            entries = collector.collect(RUN, 1, EVENT, request_authorized=True)
            self.assertEqual(collector.collect(RUN, 1, EVENT, request_authorized=True), entries)
        self.assertTrue(entries)
        self.assertEqual({entry.candidate_id for entry in entries}, {"luka-doncic"})
        self.assertEqual({entry.evidence_mode for entry in entries}, {EvidenceMode.LIVE})
        self.assertEqual(self.calls, [events_url(), odds_url(EVENT, OddsApiSourceConfig())])
        receipts = str(self.store.read_receipts(RUN))
        for forbidden in ("Out of universe", "LeBron James", SECRET):
            self.assertNotIn(forbidden, receipts)
        response = next(
            row
            for row in self.store.read_receipts(RUN)
            if row["event_key"] == f"dfs-board-1-{EVENT}-odds"
        )
        coverage = json.loads(response["reason"] or "")["provider_market_coverage"]
        self.assertIn(["prizepicks", "player_rebounds_assists"], coverage)
        self.assertNotIn(
            "REBOUNDS_ASSISTS", {entry.snapshot.observation.category.name for entry in entries}
        )

    def test_live_series_reuses_one_policy_and_only_collects_due_slots(self):
        from unittest.mock import Mock

        from fifth_pick.evidence import (
            EvidenceEffect,
            EvidenceItem,
            EvidenceKind,
            EvidenceSignificance,
            PerformanceSample,
        )
        from fifth_pick.live_analysis import live_analysis_view, read_live_supporting_items
        from fifth_pick.live_judgment import read_live_judgment, record_live_judgment
        from fifth_pick.methodology import (
            CandidateCase,
            Confidence,
            MethodologyDisposition,
            MethodologyJudgment,
            evaluate_candidate,
        )
        from fifth_pick.models import Evidence, ReasonCode
        from fifth_pick.snapshots import SnapshotEvidence, read_receipted_snapshot_ledger
        from fifth_pick.sources.base import EvidenceMode, SourceEvent
        from fifth_pick.sources.game_lines import (
            GameLinesGrant,
            acquire_game_lines,
            record_game_lines_grant,
        )
        from fifth_pick.sources.quota import QuotaSnapshot
        from fifth_pick.sources.transport import HttpResponse
        from tests.test_supporting_sources import game_lines_payload

        odds = odds_url(EVENT, OddsApiSourceConfig())
        with (
            patch("fifth_pick.board_collection.application_run_store", return_value=self.store),
            patch("fifth_pick.live_analysis.application_run_store", return_value=self.store),
            patch("fifth_pick.snapshots.application_run_store", return_value=self.store),
            patch("fifth_pick.board_collection._application_clock", return_value=NOW) as clock,
            patch.object(UrllibTransport, "get", side_effect=self.respond),
        ):
            with self.assertRaisesRegex(SourceError, "matching tipoff clocks"):
                self.live_collector(series=True, official_offset=-timedelta(minutes=10))
            self.assertEqual(self.calls, [])
            collector = self.live_collector(series=True, official_offset=timedelta())
            assert collector._grant is not None
            with self.assertRaisesRegex(SourceError, "requires independent official timing"):
                BoardCollector(
                    self.store,
                    collector._policy,
                    transport=UrllibTransport(),
                    live_grant=replace(collector._grant, official_tipoff=None),
                    environ={API_KEY_ENV_VAR: SECRET},
                )
            with self.assertRaisesRegex(SourceError, "unsupported LIVE snapshot grant"):
                BoardCollector(
                    self.store,
                    collector._policy,
                    transport=UrllibTransport(),
                    live_grant=replace(collector._grant, slots=(1, 3), official_tipoff=None),
                    environ={API_KEY_ENV_VAR: SECRET},
                )
            self.assertEqual(self.calls, [])
            self.assertTrue(collector.collect(RUN, 1, EVENT, request_authorized=True))
            with self.assertRaisesRegex(SourceError, "no authorized observations are due"):
                collector.collect(RUN, 3, EVENT, request_authorized=True)
            self.assertEqual(self.calls, [events_url(), odds])
            for slot, at in (
                (2, datetime(2026, 11, 15, 21, 30, tzinfo=UTC)),
                (3, datetime(2026, 11, 16, 1, 37, tzinfo=UTC)),
            ):
                clock.return_value = at
                self.update_response(
                    events_url(),
                    headers={
                        "x-requests-last": "0",
                        "x-requests-remaining": str(500 - 4 * (slot - 1)),
                        "x-requests-used": str(4 * (slot - 1)),
                    },
                )
                self.update_response(
                    odds,
                    headers={
                        "x-requests-last": "4",
                        "x-requests-remaining": str(500 - 4 * slot),
                        "x-requests-used": str(4 * slot),
                    },
                )

                def refresh_updates(data, *, observed_at=at):
                    timestamp = observed_at.isoformat()
                    for book in data["bookmakers"]:
                        book["last_update"] = timestamp
                        for market in book["markets"]:
                            market["last_update"] = timestamp

                self.change_odds(refresh_updates)
                rows = collector.collect(RUN, slot, EVENT, request_authorized=True)
                self.assertTrue(rows)
                self.assertTrue(all(row.snapshot.number == slot and not row.late for row in rows))
                if slot == 2:
                    stage = rows[0]
                    line = stage.snapshot.observation.projection
                    sample = EvidenceItem(
                        "history-phase-test",
                        stage.candidate_key,
                        EvidenceKind.LAST_8,
                        Evidence("Controlled history test", stage.provenance),
                        EvidenceMode.LIVE,
                        EvidenceEffect.NEUTRAL,
                        EvidenceSignificance.IMPORTANT,
                        samples=(
                            PerformanceSample(at - timedelta(days=1), line, "Boston", "2026-27"),
                        ),
                    )

                    def phase_items(
                        _run, key, *_args, bound=sample, candidate=stage.candidate_key, **_kwargs
                    ):
                        return (bound,) if key == candidate else ()

                    with patch(
                        "fifth_pick.live_analysis.read_live_supporting_items",
                        side_effect=phase_items,
                    ):
                        phase_report = live_analysis_view(
                            self.store, RUN, review=False, snapshot=2, as_of=at
                        )
                    phase_rows = phase_report["candidates"]
                    assert isinstance(phase_rows, list)
                    phase_row = next(
                        row for row in phase_rows if row["candidate_key"] == stage.candidate_key
                    )
                    self.assertEqual(phase_row["historical_comparisons"][0]["push_count"], 1)
                    self.assertEqual(phase_report["status"], "BLOCKED")

            self.assertEqual(collector.collect(RUN, 3, EVENT, request_authorized=True), rows)
            manifest_event = next(
                event
                for event in read_slate_run_context(self.store, RUN).event_boards[0].events
                if event.event_id == EVENT
            )
            event = SourceEvent(
                EVENT,
                manifest_event.home_team,
                manifest_event.away_team,
                manifest_event.commence_time,
                (),
            )
            analysis_at = datetime(2026, 11, 15, 21, 30, tzinfo=UTC)
            t20_at = event.commence_time - timedelta(minutes=20)
            grant = GameLinesGrant(RUN, EVENT, "fixture-book", ("analysis", "t20"), 4)
            record_game_lines_grant(self.store, grant, analysis_at)
            for phase, when in (("analysis", analysis_at), ("t20", t20_at)):
                (payload,) = game_lines_payload()
                payload.update(
                    id=EVENT,
                    home_team=event.home_team,
                    away_team=event.away_team,
                    commence_time=event.commence_time.isoformat(),
                )
                book = payload["bookmakers"][0]
                book["last_update"] = when.isoformat()
                book["markets"][0]["outcomes"][0]["name"] = event.home_team
                book["markets"][0]["outcomes"][1]["name"] = event.away_team
                transport = Mock(evidence_mode=EvidenceMode.LIVE)
                transport.get.return_value = HttpResponse(
                    200,
                    {"x-requests-last": "2", "x-requests-used": "12", "x-requests-remaining": "8"},
                    json.dumps([payload]).encode(),
                )
                acquire_game_lines(
                    self.store,
                    grant,
                    transport=transport,
                    phase=phase,
                    event=event,
                    quota_before=QuotaSnapshot(10, 10),
                    max_age=timedelta(minutes=10),
                    clock=lambda at=when: at,
                    environ={API_KEY_ENV_VAR: SECRET},
                    authorized=True,
                )
            first_view = live_analysis_view(self.store, RUN, review=False, snapshot=1)
            first_candidates = first_view["candidates"]
            assert isinstance(first_candidates, list)
            self.assertTrue(first_candidates)
            self.assertTrue(all(row["timely_snapshot_slots"] == [1] for row in first_candidates))
            self.assertTrue(all(not row["supporting_evidence"] for row in first_candidates))
            second_view = live_analysis_view(
                self.store,
                RUN,
                review=False,
                snapshot=2,
                as_of=analysis_at,
            )
            second_candidates = second_view["candidates"]
            assert isinstance(second_candidates, list)
            self.assertTrue(
                any(row["timely_snapshot_slots"] == [1, 2] for row in second_candidates)
            )
            self.assertTrue(
                all(
                    item["evidence_id"].startswith("game-lines-analysis-")
                    for row in second_candidates
                    for item in row["supporting_evidence"]
                )
            )
            status = live_analysis_view(self.store, RUN, review=True, as_of=t20_at)
            candidates = status["candidates"]
            assert isinstance(candidates, list)
            self.assertTrue(any(row["board_sequence_complete"] for row in candidates))
            self.assertEqual(
                {item["kind"] for row in candidates for item in row["supporting_evidence"]},
                {EvidenceKind.GAME_TOTAL.value, EvidenceKind.POINT_SPREAD.value},
            )
            self.assertEqual(status["status"], "BLOCKED")
            diagnostics = " ".join(str(row["blockers"]) for row in candidates)
            self.assertNotIn("AVAILABILITY", diagnostics)
            self.assertNotIn("ROLE_MINUTES", diagnostics)
            self.assertIn("AVAILABILITY", str(candidates[0]["context_limitations"]))
            self.assertIn("Controller", diagnostics)
            key = rows[0].candidate_key
            observations = tuple(
                row
                for row in read_receipted_snapshot_ledger(self.store, RUN)
                if isinstance(row, SnapshotEvidence) and row.candidate_key == key
            )
            facts = read_live_supporting_items(RUN, key, EVENT, slot=3, as_of=t20_at)
            case = CandidateCase(
                observations,
                evidence=facts,
                snapshot_run_id=RUN,
                supporting_slot=3,
                supporting_as_of=t20_at,
            )
            self.assertEqual(
                evaluate_candidate(case).evidence,
                tuple(
                    sorted(
                        facts,
                        key=lambda item: item.evidence_id,
                    )
                ),
            )
            tampered = replace(facts[0], facts={"total": 999})
            audit = evaluate_candidate(replace(case, evidence=(tampered, *facts[1:])))
            self.assertIn(ReasonCode.SOURCE_CONFLICT_UNRESOLVED, audit.exclusions)
            third = observations[-1]
            self.assertIsNone(read_live_judgment(self.store, RUN, third, facts, as_of=t20_at))
            judgment = MethodologyJudgment(
                MethodologyDisposition.ANALYSIS_ONLY,
                Confidence.LOW,
                "Controlled replay has no qualifying history.",
                (),
                (),
                False,
            )
            record_live_judgment(
                self.store,
                RUN,
                third,
                facts,
                judgment,
                observed_at=t20_at,
                controller_confirmed=True,
            )
            self.assertEqual(
                read_live_judgment(self.store, RUN, third, facts, as_of=t20_at),
                judgment,
            )
            before_review = self.store.read_receipts(RUN)
            self.assertEqual(
                live_analysis_view(self.store, RUN, review=True, as_of=t20_at)["status"],
                "BLOCKED",
            )
            self.assertEqual(self.store.read_receipts(RUN), before_review)
            with self.assertRaisesRegex(ValueError, "phase or time"):
                read_live_judgment(
                    self.store,
                    RUN,
                    third,
                    facts,
                    as_of=t20_at - timedelta(seconds=1),
                )
            with self.assertRaisesRegex(ValueError, "source state"):
                read_live_judgment(self.store, RUN, third, (tampered, *facts[1:]), as_of=t20_at)
        self.assertEqual(self.calls, [events_url(), odds] * 3)
        receipts = self.store.read_receipts(RUN)
        self.assertEqual(sum(row["event"] == "DFS_BOARD_RESERVED" for row in receipts), 3)

    def test_live_series_skips_third_request_when_second_window_was_missed(self):
        odds = odds_url(EVENT, OddsApiSourceConfig())
        with (
            patch("fifth_pick.board_collection.application_run_store", return_value=self.store),
            patch("fifth_pick.board_collection._application_clock", return_value=NOW) as clock,
            patch.object(UrllibTransport, "get", side_effect=self.respond),
        ):
            collector = self.live_collector(series=True)
            self.assertTrue(collector.collect(RUN, 1, EVENT, request_authorized=True))
            clock.return_value = datetime(2026, 11, 16, 1, 37, tzinfo=UTC)
            with self.assertRaisesRegex(SourceError, "second observation"):
                collector.collect(RUN, 3, EVENT, request_authorized=True)
        self.assertEqual(self.calls, [events_url(), odds])

    def test_live_analysis_checks_replayed_board_without_creating_review_or_network_calls(self):
        from fifth_pick.live_analysis import live_analysis_view

        with (
            patch("fifth_pick.board_collection.application_run_store", return_value=self.store),
            patch("fifth_pick.live_analysis.application_run_store", return_value=self.store),
            patch("fifth_pick.snapshots.application_run_store", return_value=self.store),
            patch("fifth_pick.board_collection._application_clock", return_value=NOW),
            patch.object(UrllibTransport, "get", side_effect=self.respond),
        ):
            collector = self.live_collector()
            collector.collect(RUN, 1, EVENT, request_authorized=True)
            previous = self.store.read_receipts(RUN)
            result = live_analysis_view(self.store, RUN, review=True)
        self.assertEqual(result["reason"], "T20_CHECK_UNAVAILABLE")
        self.assertIn("timely Snapshot 2", str(result["blockers"]))
        candidates = result["candidates"]
        assert isinstance(candidates, list)
        self.assertTrue(candidates)
        for candidate in candidates:
            self.assertEqual(candidate["timely_snapshot_slots"], [1])
            self.assertFalse(candidate["board_sequence_complete"])
            self.assertEqual(candidate["player_id"], "luka-doncic")
            self.assertEqual(candidate["observations"][0]["snapshot"], 1)
            self.assertIn("line", candidate["observations"][0])
            self.assertIn("platform", candidate["observations"][0])
        self.assertIn("approved LIVE player-history source", str(result["blockers"]))
        self.assertEqual(self.store.read_receipts(RUN), previous)
        self.assertEqual(self.calls, [events_url(), odds_url(EVENT, OddsApiSourceConfig())])

    def test_live_crosswalk_alias_requires_fully_bound_collector_snapshot_bytes(self):
        from fifth_pick.methodology import CandidateCase, MethodologyError, evaluate_candidate
        from fifth_pick.models import ReasonCode

        label = "Roster-linked provider label"
        self.policy = replace(self.policy, aliases={**self.policy.aliases, label: ("luka-doncic",)})

        def change_label(data):
            for book in data["bookmakers"]:
                for market in book["markets"]:
                    for outcome in market["outcomes"]:
                        if outcome.get("description") == "Luka Doncic":
                            outcome["description"] = label

        self.change_odds(change_label)
        with (
            patch("fifth_pick.board_collection.application_run_store", return_value=self.store),
            patch("fifth_pick.snapshots.application_run_store", return_value=self.store),
            patch("fifth_pick.board_collection._application_clock", return_value=NOW),
            patch.object(UrllibTransport, "get", side_effect=self.respond),
        ):
            collector = self.live_collector()
            entries = collector.collect(RUN, 1, EVENT, request_authorized=True)
            case = CandidateCase((entries[0],), snapshot_run_id=RUN)
            self.assertNotIn(
                ReasonCode.PLAYER_IDENTITY_UNRESOLVED, evaluate_candidate(case).exclusions
            )
            path = self.store.receipts_path(RUN)
            original = path.read_text()
            receipts = [json.loads(line) for line in original.splitlines()]
            for event in ("DFS_BOARD_POLICY", "DFS_BOARD_RESERVED", "DFS_HTTP_REQUEST"):
                path.write_text(
                    "".join(json.dumps(row) + "\n" for row in receipts if row["event"] != event)
                )
                with self.assertRaisesRegex(MethodologyError, "not bound"):
                    evaluate_candidate(case)
            path.write_text(original)
            completed = next(r for r in receipts if r["event"] == "DFS_BOARD_COLLECTED")
            metadata = json.loads(completed["reason"])
            metadata["snapshots_sha256"] = "0" * 64
            completed["reason"] = json.dumps(metadata)
            path.write_text("".join(json.dumps(row) + "\n" for row in receipts))
            with self.assertRaisesRegex(MethodologyError, "not bound"):
                evaluate_candidate(case)

    def test_paid_dispatch_rejects_grant_matching_provider_but_missing_official_game(self):
        from datetime import date

        from fifth_pick.official_slate import OfficialGame, OfficialSlate

        official = OfficialSlate(
            "fixture:published-schedule",
            (
                OfficialGame("Dallas Mavericks", "Los Angeles Lakers", NOW),
                OfficialGame("New York Knicks", "Boston Celtics", NOW),
                OfficialGame("Utah Jazz", "Denver Nuggets", NOW),
            ),
        )
        with (
            patch("fifth_pick.board_collection.application_run_store", return_value=self.store),
            patch("fifth_pick.board_collection._application_clock", return_value=NOW),
            patch("fifth_pick.official_slate.load_official_slate", return_value=official) as lookup,
            patch.object(UrllibTransport, "get", side_effect=self.respond),
            self.assertRaisesRegex(SourceError, "stopped"),
        ):
            self.live_collector().collect(RUN, 1, EVENT, request_authorized=True)
        lookup.assert_called_once_with(date(2026, 11, 15))
        self.assertEqual(self.calls, [events_url()])

    def test_live_slate_change_stops_before_odds(self):
        with (
            patch("fifth_pick.board_collection.application_run_store", return_value=self.store),
            patch("fifth_pick.board_collection._application_clock", return_value=NOW),
            patch.object(UrllibTransport, "get", side_effect=self.respond),
            self.assertRaisesRegex(SourceError, "stopped"),
        ):
            self.live_collector(slate_ids=(EVENT,)).collect(RUN, 1, EVENT, request_authorized=True)
        self.assertEqual(self.calls, [events_url()])
