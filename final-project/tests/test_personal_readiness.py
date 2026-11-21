import unittest
from datetime import UTC, datetime, timedelta

from fifth_pick.personal_readiness import forecast_daily_board
from fifth_pick.sources.base import SourceEvent


class PersonalForecastTests(unittest.TestCase):
    def test_full_frozen_universe_uses_exact_grants_and_event_scope(self):
        from fifth_pick.authorization import AuthorizationGate
        from fifth_pick.config import load_configs
        from fifth_pick.identity import IdentityResolver
        from fifth_pick.models import LIVE_MVP_CATEGORIES, Direction
        from fifth_pick.personal_readiness import authorized_projection_filter
        from fifth_pick.registry import Registry

        registry = Registry.from_universe(load_configs().approved_universe)
        players = registry.players()
        self.assertEqual(len(players), 156)
        gate = AuthorizationGate()
        resolver = IdentityResolver(
            registry, {player.canonical_name: (player.player_id,) for player in players}
        )
        allowed = authorized_projection_filter(
            resolver, {"scoped": tuple(player.player_id for player in players)}
        )
        for player in players:
            for category in LIVE_MVP_CATEGORIES:
                for direction in Direction:
                    self.assertEqual(
                        allowed("scoped", player.canonical_name, category, direction),
                        gate.authorize(player.player_id, category, direction).allowed,
                    )
                    self.assertFalse(allowed("other", player.canonical_name, category, direction))

    def test_distinguishes_full_slate_from_relevant_and_timely_games(self):
        now = datetime(2026, 11, 18, 23, 0, tzinfo=UTC)
        events = tuple(
            SourceEvent(f"game-{i}", f"Home {i}", f"Away {i}", now + timedelta(minutes=m), ())
            for i, m in enumerate((30, 90, 120, 150, 180))
        )
        forecast = forecast_daily_board(
            events,
            {
                "game-0": ("luka-doncic",),
                "game-1": ("luka-doncic",),
                "game-2": ("malik-monk",),
                "game-3": ("outside",),
            },
            as_of=now,
        )
        self.assertEqual(forecast["official_game_count"], 5)
        self.assertEqual(forecast["slate_ceiling"], 5)
        self.assertEqual(forecast["relevant_game_count"], 2)
        self.assertEqual(forecast["timely_event_ids"], ["game-1"])
        self.assertEqual(forecast["snapshot_1_credit_ceiling"], 5)
        self.assertEqual(forecast["three_snapshot_credit_ceiling"], 15)
        self.assertEqual(forecast["unverified_roster_event_ids"], ["game-4"])

    def test_free_quota_uses_only_the_events_endpoint(self):
        from fifth_pick.sources.odds_api import API_KEY_ENV_VAR, OddsApiClient, events_url
        from fifth_pick.sources.transport import HttpResponse
        from tests.test_odds_api import FakeTransport

        transport = FakeTransport(
            {
                events_url(): HttpResponse(
                    200,
                    {
                        "x-requests-remaining": "123",
                        "x-requests-used": "10",
                        "x-requests-last": "0",
                    },
                    b"[]",
                )
            }
        )
        client = OddsApiClient(transport=transport, environ={API_KEY_ENV_VAR: "synthetic-key"})
        self.assertEqual(client.check_free_quota(authorized=True).remaining, 123)
        self.assertEqual([url for url, _ in transport.calls], [events_url()])

    def test_preflight_command_with_no_credential_never_calls_transport(self):
        import contextlib
        import io
        import os
        from unittest.mock import patch

        from fifth_pick.cli import main
        from fifth_pick.sources.odds_api import API_KEY_ENV_VAR
        from fifth_pick.sources.transport import UrllibTransport

        stderr = io.StringIO()
        with (
            patch.dict(os.environ, {API_KEY_ENV_VAR: ""}),
            patch.object(UrllibTransport, "get", side_effect=AssertionError("network")) as call,
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(main(["board-preflight"]), 1)
        call.assert_not_called()
        self.assertIn("THE_ODDS_API_KEY is not set", stderr.getvalue())

    def test_preflight_reports_only_safe_failure_details(self):
        import contextlib
        import io
        import os
        from unittest.mock import patch

        from fifth_pick.cli import _board_preflight
        from fifth_pick.sources.odds_api import API_KEY_ENV_VAR, events_url
        from fifth_pick.sources.transport import HttpResponse, TransportError, UrllibTransport

        secret = "synthetic-secret"
        headers = {"X-Requests-Remaining": "123", "x-requests-used": "10", "x-requests-last": "0"}
        cases = (
            (TransportError(secret), "transport", None, None),
            (HttpResponse(401, {}, secret.encode()), "authentication", 401, None),
            (HttpResponse(429, headers, secret.encode()), "provider quota or rate limit", 429, 123),
            (HttpResponse(503, {}, secret.encode()), "HTTP response", 503, None),
            (
                HttpResponse(200, dict(headers, **{"x-requests-last": secret}), b"[]"),
                "quota-header validation",
                200,
                123,
            ),
            (HttpResponse(200, {}, b"[]"), "quota-header validation", 200, None),
            (HttpResponse(200, headers, secret.encode()), "event validation", 200, 123),
        )
        for outcome, stage, status, remaining in cases:
            with self.subTest(stage=stage, status=status):
                stderr = io.StringIO()
                with (
                    patch.dict(os.environ, {API_KEY_ENV_VAR: secret}),
                    patch.object(UrllibTransport, "get") as request,
                    contextlib.redirect_stderr(stderr),
                ):
                    if isinstance(outcome, Exception):
                        request.side_effect = outcome
                    else:
                        request.return_value = outcome
                    self.assertEqual(_board_preflight(lambda _: "PREFLIGHT"), 1)
                request.assert_called_once()
                self.assertEqual(request.call_args.args[0], events_url())
                output = stderr.getvalue()
                self.assertIn(f"stage={stage}", output)
                self.assertIn(
                    f"http_status={status if status is not None else 'unavailable'}", output
                )
                if remaining is not None:
                    self.assertIn(f"remaining={remaining}", output)
                if stage == "transport":
                    self.assertIn("transport_category=unknown", output)
                self.assertNotIn(secret, output)

    def test_scoped_snapshot_does_not_mark_unqueried_event_missed(self):
        from dataclasses import replace
        from tempfile import TemporaryDirectory

        from tests.test_snapshots import (
            EVENT_ID,
            NOW,
            RUN_ID,
            TIPOFF,
            MutableClock,
            make_board,
            make_projection,
            make_workflow,
        )

        with TemporaryDirectory() as root:
            clock = MutableClock(NOW)
            workflow = make_workflow(root, clock)
            initial = make_board(NOW, make_projection(NOW))
            original = initial.events[0]
            second = replace(
                original,
                event_id="other",
                projections=(replace(original.projections[0], event_id="other"),),
            )
            workflow.collect(RUN_ID, 1, replace(initial, events=(original, second)))
            clock.current = TIPOFF - timedelta(minutes=79)
            workflow.collect(RUN_ID, 2, make_board(clock.current), event_scope=EVENT_ID)
            self.assertEqual([entry.event_id for entry in workflow.read_missed(RUN_ID)], [EVENT_ID])
