import json
import unittest
from datetime import UTC, datetime
from unittest.mock import Mock, patch

from fifth_pick.cli import main
from fifth_pick.sources.base import SourceError
from fifth_pick.sources.bdl_history import BdlHistoryClient
from fifth_pick.sources.transport import HttpResponse


class BdlValidationTests(unittest.TestCase):
    def test_stats_only_uses_one_exact_completed_game_query(self):
        from urllib.parse import parse_qs, urlsplit

        transport = Mock()
        transport.get.return_value = HttpResponse(200, {}, b'{"data":[],"meta":{}}')
        client = BdlHistoryClient(
            transport,
            environ={"BALLDONTLIE_API_KEY": "synthetic"},
            clock=lambda: datetime(2026, 11, 19, 3, tzinfo=UTC),
        )
        result = client.validate_verified_curry_stats()
        transport.get.assert_called_once()
        url, headers = transport.get.call_args.args
        parsed = urlsplit(url)
        self.assertEqual(parsed.path, "/v1/stats")
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "player_ids[]": ["115"],
                "seasons[]": ["2026"],
                "end_date": ["2026-11-17"],
                "period": ["0"],
                "per_page": ["100"],
            },
        )
        self.assertEqual(headers["Authorization"], "synthetic")
        self.assertEqual(result["request_count"], 1)
        self.assertEqual(result["completed_appearances"], 0)
        self.assertEqual(result["mode"], "STATS_VALIDATION_ONLY")
        self.assertEqual(result["stats_http_status"], 200)

    def test_stats_only_does_not_follow_cursor(self):
        transport = Mock()
        transport.get.return_value = HttpResponse(200, {}, b'{"data":[],"meta":{"next_cursor":2}}')
        client = BdlHistoryClient(transport, environ={"BALLDONTLIE_API_KEY": "synthetic"})
        with self.assertRaisesRegex(SourceError, "pagination is incomplete"):
            client.validate_verified_curry_stats()
        transport.get.assert_called_once()

    def test_identity_only_does_not_request_teams_or_stats(self):
        transport = Mock()
        transport.get.return_value = HttpResponse(
            200,
            {},
            b'{"data":{"id":115,"first_name":"Stephen","last_name":"Curry",'
            b'"draft_year":2009,"draft_round":1,"draft_number":7}}',
        )
        with (
            patch.dict("os.environ", {"BALLDONTLIE_API_KEY": "synthetic"}),
            patch("fifth_pick.sources.transport.UrllibTransport", return_value=transport),
            patch("builtins.print") as output,
        ):
            self.assertEqual(main(["bdl-validate", "--identity-only", "--confirm"]), 0)
        transport.get.assert_called_once_with(
            "https://api.balldontlie.io/v1/players/115",
            {"Authorization": "synthetic", "Accept": "application/json"},
        )
        status = json.loads(output.call_args.args[0])
        self.assertEqual(status["mode"], "IDENTITY_VALIDATION_ONLY")
        self.assertEqual(status["request_count"], 1)
        self.assertNotIn("synthetic", json.dumps(status))

    def test_auth_only_uses_one_free_tier_request_and_stops_on_401(self):
        transport = Mock()
        transport.get.return_value = HttpResponse(401, {}, b"private response")
        client = BdlHistoryClient(transport, environ={"BALLDONTLIE_API_KEY": "synthetic"})
        with self.assertRaisesRegex(
            SourceError, r"^BALLDONTLIE authentication probe returned HTTP 401$"
        ):
            client.probe_authentication()
        transport.get.assert_called_once_with(
            "https://api.balldontlie.io/v1/teams",
            {"Authorization": "synthetic", "Accept": "application/json"},
        )

    def test_cli_requires_exact_confirmation(self):
        with patch("fifth_pick.sources.transport.UrllibTransport") as transport:
            with patch("sys.stderr"):
                self.assertNotEqual(main(["bdl-validate"]), 0)
            transport.assert_not_called()

    def test_rate_limit_stops_without_retry_or_body_output(self):
        transport = Mock()
        transport.get.return_value = HttpResponse(429, {}, b"private response")
        client = BdlHistoryClient(transport, environ={"BALLDONTLIE_API_KEY": "synthetic"})
        with self.assertRaisesRegex(SourceError, r"^BALLDONTLIE identity returned HTTP 429$"):
            client.validate_curry_history()
        transport.get.assert_called_once()

    def test_exact_draft_identity_then_one_bounded_history_page(self):
        player = dict(
            id=115,
            first_name="Stephen",
            last_name="Curry",
            draft_year=2009,
            draft_round=1,
            draft_number=7,
        )
        for match in (True, False):
            with self.subTest(match=match):
                transport = Mock()
                identity = {"data": player if match else dict(player, draft_number=8)}
                transport.get.side_effect = [
                    HttpResponse(200, {}, json.dumps(identity).encode()),
                    HttpResponse(200, {}, b'{"data":[],"meta":{}}'),
                ]
                client = BdlHistoryClient(
                    transport,
                    environ={"BALLDONTLIE_API_KEY": "synthetic"},
                    clock=lambda: datetime(2026, 11, 19, tzinfo=UTC),
                )
                if match:
                    output = client.validate_curry_history()
                    self.assertEqual(output["completed_appearances"], 0)
                    self.assertEqual(transport.get.call_count, 2)
                    url, headers = transport.get.call_args.args
                    self.assertIn("player_ids%5B%5D=115", url)
                    self.assertNotIn("synthetic", url)
                    self.assertEqual(headers["Authorization"], "synthetic")
                    self.assertNotIn("synthetic", json.dumps(output))
                else:
                    with self.assertRaises(SourceError):
                        client.validate_curry_history()
                    transport.get.assert_called_once()

    def test_history_replay_rejects_tampered_or_stale_pages(self):
        from dataclasses import replace
        from datetime import date, timedelta
        from hashlib import sha256

        from fifth_pick.sources.bdl_history import HistoryRetrieval, verify_history_replay

        now = datetime(2026, 11, 19, tzinfo=UTC)
        body = b'{"data":[],"meta":{}}'
        receipt = HistoryRetrieval(None, now, sha256(body).hexdigest())

        def verify(payload, retrieval):
            return verify_history_replay(
                (payload,),
                (retrieval,),
                provider_player_id=115,
                season=2026,
                before=date(2026, 11, 18),
                as_of=now,
                max_age=timedelta(minutes=15),
                page_limit=1,
            )

        self.assertEqual(verify(body, receipt), ())
        for payload, retrieval in (
            (body + b" ", receipt),
            (body, replace(receipt, cursor=1)),
            (body, replace(receipt, retrieved_at=now - timedelta(minutes=16))),
        ):
            with self.assertRaises(SourceError):
                verify(payload, retrieval)

    def test_history_archive_receipt_binds_phase_season_cutoff_and_bytes(self):
        from datetime import date, timedelta
        from hashlib import sha256
        from tempfile import TemporaryDirectory

        from fifth_pick.sources.bdl_history import HistoryRetrieval, receipt_fixture_history
        from fifth_pick.storage import RunStore

        observed = datetime(2026, 11, 19, tzinfo=UTC)
        body = b'{"data":[],"meta":{}}'
        retrieval = HistoryRetrieval(None, observed, sha256(body).hexdigest())
        with TemporaryDirectory() as directory:
            store = RunStore(directory)

            def record(cutoff, *, verify_only=False):
                return receipt_fixture_history(
                    store,
                    "history-test",
                    (body,),
                    (retrieval,),
                    phase="t20",
                    provider_player_id=115,
                    season=2026,
                    before=cutoff,
                    as_of=observed,
                    max_age=timedelta(minutes=10),
                    page_limit=1,
                    verify_only=verify_only,
                )

            with self.assertRaisesRegex(SourceError, "receipt is missing"):
                record(date(2026, 11, 18), verify_only=True)
            self.assertEqual(store.read_receipts("history-test"), ())
            self.assertEqual(record(date(2026, 11, 18)), ())
            self.assertEqual(record(date(2026, 11, 18), verify_only=True), ())
            (receipt,) = store.read_receipts("history-test")
            self.assertEqual(receipt["source"], "synthetic-fixture")
            with self.assertRaises(SourceError):
                record(date(2026, 11, 17))
