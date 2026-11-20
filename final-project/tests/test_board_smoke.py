from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from fifth_pick.board_smoke import SmokeAuthorization, run_board_smoke
from fifth_pick.personal_readiness import LiveEventScope
from fifth_pick.sources.base import EvidenceMode, LiveAuthorizationError, SourceError
from fifth_pick.sources.fixtures import load_board_fixture
from fifth_pick.sources.odds_api import API_KEY_ENV_VAR, OddsApiSourceConfig, events_url, odds_url
from fifth_pick.sources.transport import UrllibTransport
from fifth_pick.storage import RunStore
from tests.test_odds_api import FIXTURE_DIR


class BoardSmokeTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = RunStore(Path(directory.name))
        self.transport = load_board_fixture(FIXTURE_DIR)
        self.now = datetime(2026, 11, 15, 17, 10, tzinfo=UTC)
        self.scope = LiveEventScope(
            "evt-bos-nyk-20261115",
            "Boston Celtics",
            "New York Knicks",
            datetime(2026, 11, 16, tzinfo=UTC),
            ("jayson-tatum",),
        )
        self.grant = SmokeAuthorization(
            "smoke-test",
            EvidenceMode.FIXTURE,
            "approved-synthetic-rehearsal",
            datetime(2026, 11, 15, 18, 0, tzinfo=UTC),
        )

    def run_fixture(self, confirm_event):
        return run_board_smoke(
            run_id="smoke-test",
            authorization=self.grant,
            confirm_event=confirm_event,
            store=self.store,
            transport=self.transport,
            environ={API_KEY_ENV_VAR: "synthetic-secret"},
            clock=lambda: self.now,
        )

    def test_default_disabled_before_constructing_http(self):
        with (
            patch("fifth_pick.board_smoke.UrllibTransport") as transport,
            self.assertRaises(LiveAuthorizationError),
        ):
            run_board_smoke(run_id="smoke-test")
        transport.assert_not_called()

    def test_one_list_one_odds_discovered_in_chicago_and_receipted_replay(self):
        selected = []
        with patch.object(self.transport, "get", wraps=self.transport.get) as call:
            result = self.run_fixture(lambda event: selected.append(event) is None)
            replay = self.run_fixture(lambda _: self.fail("no confirmation on replay"))
        event = selected[0]
        self.assertEqual(event.event_id, "evt-bos-nyk-20261115")
        self.assertEqual(
            [row.args[0] for row in call.call_args_list],
            [events_url(), odds_url(event.event_id, OddsApiSourceConfig())],
        )
        self.assertEqual(result, replay)
        self.assertEqual(result.evidence_mode, EvidenceMode.FIXTURE)
        self.assertTrue(result.unresolved)
        self.assertIn("jayson-tatum", result.unresolved[0].candidate_ids)
        self.assertEqual(result.accepted_snapshots, 0)
        receipts = self.store.read_receipts("smoke-test")
        self.assertNotIn("synthetic-secret", str(receipts))

    def test_decline_spends_no_odds_and_cannot_retry(self):
        with patch.object(self.transport, "get", wraps=self.transport.get) as call:
            with self.assertRaises(SourceError):
                self.run_fixture(lambda _: False)
            with self.assertRaises(SourceError):
                self.run_fixture(lambda _: True)
        self.assertEqual([row.args[0] for row in call.call_args_list], [events_url()])

    def test_refuses_live_transport_under_fixture_grant(self):
        with (
            patch.object(UrllibTransport, "get", side_effect=AssertionError("network")),
            self.assertRaises(LiveAuthorizationError),
        ):
            run_board_smoke(
                run_id="smoke-test",
                authorization=self.grant,
                confirm_event=lambda _: True,
                store=self.store,
                transport=UrllibTransport(),
                clock=lambda: self.now,
            )

    def test_mocked_live_transport_stops_before_odds_on_missing_billing_or_free_quota(self):
        grant = replace(self.grant, evidence_mode=EvidenceMode.LIVE, event_scope=self.scope)
        with (
            patch("fifth_pick.board_smoke.application_run_store", return_value=self.store),
            patch("fifth_pick.board_smoke._current_time", return_value=self.now),
            patch.object(UrllibTransport, "get", side_effect=self.transport.get) as call,
        ):
            for candidate in (grant, replace(grant, billing_reference="test-only-current-pricing")):
                with self.assertRaises(SourceError):
                    run_board_smoke(
                        run_id="smoke-test",
                        authorization=candidate,
                        confirm_event=lambda _: self.fail("do not confirm unverified quota"),
                        environ={API_KEY_ENV_VAR: "synthetic-secret"},
                    )
            self.assertEqual([row.args[0] for row in call.call_args_list], [events_url()])

    def test_mocked_live_receipts_contain_no_secret_and_verify_quota(self):
        grant = replace(
            self.grant,
            evidence_mode=EvidenceMode.LIVE,
            billing_reference="test-only-current-pricing",
            event_scope=self.scope,
        )

        def response(url, headers):
            result = self.transport.get(url, headers)
            if url == events_url():
                return replace(
                    result,
                    headers={
                        "x-requests-remaining": "500",
                        "x-requests-used": "0",
                        "x-requests-last": "0",
                    },
                )
            return result

        with (
            patch("fifth_pick.board_smoke.application_run_store", return_value=self.store),
            patch("fifth_pick.board_smoke._current_time", return_value=self.now),
            patch.object(UrllibTransport, "get", side_effect=response) as call,
        ):
            result = run_board_smoke(
                run_id="smoke-test",
                authorization=grant,
                confirm_event=lambda _: True,
                environ={API_KEY_ENV_VAR: "synthetic-secret"},
            )
        self.assertEqual(result.evidence_mode, EvidenceMode.LIVE)
        self.assertEqual(result.credits_used, 5)
        self.assertEqual(result.projections, ())
        self.assertEqual(result.unresolved, ())
        self.assertNotIn("Jayson Tatum", str(self.store.read_receipts("smoke-test")))
        self.assertEqual(result.event.slate_game_count, 2)
        self.assertEqual(result.event.slate_classification, "HALF")
        self.assertEqual(len(result.event.slate), 2)
        self.assertEqual(len(call.call_args_list), 2)
        self.assertNotIn("synthetic-secret", str(self.store.read_receipts("smoke-test")))

    def test_freshness_failure_has_http_receipts_but_no_snapshot(self):
        self.now = datetime(2026, 11, 15, 18, 1, tzinfo=UTC)
        self.grant = replace(self.grant, expires_at=datetime(2026, 11, 15, 19, 0, tzinfo=UTC))
        with self.assertRaisesRegex(SourceError, "stale"):
            self.run_fixture(lambda _: True)
        rows = self.store.read_receipts("smoke-test")
        self.assertEqual(sum(row["event"] == "DFS_SMOKE_HTTP_RESPONSE" for row in rows), 2)
        self.assertFalse(any(row["event"] == "SNAPSHOT_ACCEPTED" for row in rows))

    def test_replay_rejects_tampered_http_receipt_without_new_fetch(self):
        import json

        with patch.object(self.transport, "get", wraps=self.transport.get) as requests:
            self.run_fixture(lambda _: True)
            path = self.store.run_directory("smoke-test") / "receipts.jsonl"
            rows = list(map(json.loads, path.read_text().splitlines()))
            next(row for row in rows if row["event_key"] == "dfs-smoke-http-events")["result"] = (
                "418"
            )
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(SourceError, "stored smoke evidence"):
                self.run_fixture(lambda _: self.fail("replay should not confirm"))
            self.assertEqual(requests.call_count, 2)

    def test_preverified_provider_alias_allows_exact_m5_resolution(self):
        review = []
        result = run_board_smoke(
            run_id="smoke-test",
            authorization=self.grant,
            confirm_event=lambda _: True,
            review_identity=review.append,
            aliases={"Jayson Tatum": ("jayson-tatum",)},
            store=self.store,
            transport=self.transport,
            environ={API_KEY_ENV_VAR: "synthetic-secret"},
            clock=lambda: self.now,
        )
        self.assertGreater(result.accepted_snapshots, 0)
        self.assertEqual(tuple(review), result.unresolved)
        self.assertFalse(any(row.provider_label == "Jayson Tatum" for row in review))

    def test_interrupted_attempt_records_sanitized_request_and_never_retries(self):
        from fifth_pick.sources.transport import TransportError

        with patch.object(
            self.transport, "get", side_effect=TransportError("synthetic-secret")
        ) as call:
            for _ in range(2):
                with self.assertRaises(SourceError):
                    self.run_fixture(lambda _: False)
        self.assertEqual(call.call_count, 1)
        rows = self.store.read_receipts("smoke-test")
        self.assertTrue(
            any(
                row["event"] == "DFS_SMOKE_HTTP_REQUEST" and events_url() in (row["reason"] or "")
                for row in rows
            )
        )
        self.assertFalse(any(row["event"] == "DFS_SMOKE_HTTP_RESPONSE" for row in rows))
        self.assertNotIn("synthetic-secret", str(rows))

    def test_live_rejects_caller_clock_before_constructing_http(self):
        grant = replace(self.grant, evidence_mode=EvidenceMode.LIVE, billing_reference="test")
        with (
            patch("fifth_pick.board_smoke.UrllibTransport") as transport,
            self.assertRaisesRegex(LiveAuthorizationError, "application clock"),
        ):
            run_board_smoke(
                run_id=grant.run_id,
                authorization=grant,
                confirm_event=lambda _: True,
                clock=lambda: self.now,
            )
        transport.assert_not_called()
