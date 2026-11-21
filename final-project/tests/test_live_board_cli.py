import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fifth_pick.cli import main

TIPOFF = "2026-11-19T03:10:00+00:00"
EVENT = "2adabff2dca8b2ed4b39540a6a25ffb2"


class LiveBoardCliTests(unittest.TestCase):
    def test_live_menu_opens_saved_board_without_entering_network_discovery(self):
        from contextlib import redirect_stdout
        from io import StringIO

        from fifth_pick.cli import _live_board_menu

        answers = iter(("3", "board-run", EVENT, "", "", ""))
        with (
            redirect_stdout(StringIO()),
            patch("fifth_pick.cli._board_preflight") as discover,
            patch("fifth_pick.board_inspect_cli.board_inspect", return_value=0) as inspect,
        ):
            self.assertEqual(_live_board_menu(lambda _: next(answers)), 0)
        discover.assert_not_called()
        inspect.assert_called_once_with(
            ["--run-id", "board-run", "--event-id", EVENT, "--snapshot", "1"], pretty=False
        )

    def test_live_menu_preserves_explicit_collection_and_decision_gates(self):
        from contextlib import redirect_stdout
        from io import StringIO

        from fifth_pick.cli import _live_board_menu

        collect = iter(("4", "board-run", "2", "scope file.json", "", ""))
        decide = iter(("9", "board-run"))
        with (
            redirect_stdout(StringIO()),
            patch("fifth_pick.cli.main", return_value=0) as dispatch,
        ):
            self.assertEqual(_live_board_menu(lambda _: next(collect)), 0)
            self.assertEqual(_live_board_menu(lambda _: next(decide)), 0)
        self.assertEqual(
            dispatch.call_args_list[0].args[0],
            [
                "board-collect",
                "--run-id",
                "board-run",
                "--snapshot",
                "2",
                "--scope",
                "scope file.json",
                "--series",
            ],
        )
        self.assertTrue(callable(dispatch.call_args_list[0].kwargs["prompt"]))
        self.assertEqual(dispatch.call_args_list[1].args[0], ["decide", "--run-id", "board-run"])
        self.assertTrue(dispatch.call_args_list[1].kwargs["_menu_form"])

    def test_live_menu_rejects_demo_run_before_decision_dispatch(self):
        from fifth_pick.cli import _live_board_menu

        answers = iter(("9", "demo-capture"))
        with (
            patch("fifth_pick.cli.is_fixture_workflow", return_value=True),
            patch("fifth_pick.cli.main") as dispatch,
        ):
            self.assertEqual(_live_board_menu(lambda _: next(answers)), 1)
        dispatch.assert_not_called()

    def test_live_series_uses_crosswalk_without_prompting_for_one_slot_override(self):
        from fifth_pick.cli import _live_board_menu

        answers = iter(
            ("4", "board-run", "1", "scope.json", "", "SERIES", "roster.json", "crosswalk.json")
        )
        with patch("fifth_pick.cli.main", return_value=0) as dispatch:
            self.assertEqual(_live_board_menu(lambda _: next(answers)), 0)
        self.assertEqual(
            dispatch.call_args.args[0],
            [
                "board-collect",
                "--run-id",
                "board-run",
                "--snapshot",
                "1",
                "--scope",
                "scope.json",
                "--series",
                "--roster",
                "roster.json",
                "--board-identities",
                "crosswalk.json",
            ],
        )

    def test_quarantine_cli_binds_earlier_cutoff_and_verified_roster(self):
        from contextlib import redirect_stdout
        from io import StringIO

        event = {
            "event_id": EVENT,
            "home_team": "Los Angeles Lakers",
            "away_team": "Utah Jazz",
            "tipoff": TIPOFF,
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("fifth_pick.live_board_cli.datetime", wraps=datetime) as clock,
            patch("fifth_pick.live_board_cli.BoardCollector") as collector,
            redirect_stdout(StringIO()),
        ):
            root = Path(directory)
            preflight = root / "preflight.json"
            roster = root / "roster.json"
            board = root / "board.json"
            timing = root / "timing.json"
            checked = "2026-11-18T10:00:00-06:00"
            raw = json.dumps(
                {
                    "mode": "LIVE_PROVIDER_DISCOVERY_ONLY",
                    "slate_date": "2026-11-18",
                    "checked_at": checked,
                    "quota": {"last": 0, "remaining": 491},
                    "events": [event],
                }
            )
            preflight.write_text(raw)
            roster.write_text(
                json.dumps(
                    [
                        {
                            "stable_id": "1629029",
                            "canonical_id": "luka-doncic",
                            "team": event["home_team"],
                            "reference": "https://example.test/roster",
                        }
                    ]
                )
            )
            board.write_text(
                json.dumps(
                    [
                        {
                            "stable_id": "1629029",
                            "provider_label": "Luka Doncic",
                            "event_id": EVENT,
                            "team": event["home_team"],
                            "reference": "https://example.test/independent-identity",
                        }
                    ]
                )
            )
            cutoff = "2026-11-18T19:40:00-06:00"
            timing.write_text(
                json.dumps(
                    {
                        "event": event,
                        "official": {
                            "venue_tipoff": "2026-11-18T19:00:00-08:00",
                            "chicago_tipoff": "2026-11-18T21:00:00-06:00",
                            "source": "https://example.test/official",
                        },
                        "provider": {
                            "chicago_tipoff": "2026-11-18T21:10:00-06:00",
                            "source": str(preflight),
                            "checked_at": checked,
                        },
                        "conservative_snapshot_1_cutoff": cutoff,
                    }
                )
            )
            args = [
                "board-collect",
                "--run-id",
                "timed-quarantine",
                "--snapshot",
                "1",
                "--quarantine-labels",
                "--preflight",
                str(preflight),
                "--timing-file",
                str(timing),
                "--roster",
                str(roster),
            ]
            clock.now.return_value = datetime.fromisoformat(cutoff)
            self.assertEqual(main(args, prompt=lambda _: self.fail("expired approval")), 1)
            collector.assert_not_called()
            clock.now.return_value = datetime.fromisoformat("2026-11-18T19:39:00-06:00")
            answers = iter(
                (f"APPROVE {EVENT} SNAPSHOT 1 5", str(board), "VERIFY SNAPSHOT 1 IDENTITIES")
            )
            collector.return_value.collect.return_value = ()
            self.assertEqual(main(args, prompt=lambda _: next(answers)), 0)
            kwargs = collector.call_args.kwargs
            self.assertEqual(kwargs["live_grant"].expires_at, datetime.fromisoformat(cutoff))
            self.assertEqual(kwargs["live_grant"].events[0].tipoff.isoformat(), TIPOFF)
            self.assertEqual(
                kwargs["review_quarantined_labels"](("Luka Doncic", "Unknown"))[0],
                {"Luka Doncic": "luka-doncic"},
            )
            self.assertEqual(preflight.read_text(), raw)

    def test_partial_provider_discovery_saves_diagnostics_only(self):
        import io
        import os
        from contextlib import redirect_stderr, redirect_stdout

        from fifth_pick.sources.odds_api import events_url
        from fifth_pick.sources.transport import HttpResponse, UrllibTransport
        from fifth_pick.storage import RunStore

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("fifth_pick.cli.application_run_store", return_value=RunStore(directory)),
            patch("fifth_pick.cli.datetime", wraps=datetime) as clock,
            patch.dict("os.environ", {"THE_ODDS_API_KEY": "test-key"}),
            patch.object(UrllibTransport, "get") as request,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            clock.now.return_value = datetime.fromisoformat("2026-11-18T20:30:00-06:00")
            request.return_value = HttpResponse(
                200,
                {"x-requests-last": "0", "x-requests-remaining": "491", "x-requests-used": "9"},
                json.dumps(
                    [
                        {
                            "id": "provider-only-one",
                            "away_team": "Portland Trail Blazers",
                            "home_team": "Milwaukee Bucks",
                            "commence_time": "2026-11-20T01:00:00+00:00",
                        }
                    ]
                ).encode(),
            )
            args = ["board-preflight", "--date", "2026-11-19", "--expected-games", "4"]
            self.assertEqual(main(args, prompt=lambda _: "PREFLIGHT"), 1)
            request.assert_called_once()
            self.assertEqual(request.call_args.args[0], events_url())
            root = Path(directory)
            self.assertFalse((root / "preflight/2026-11-19.json").exists())
            saved = json.loads((root / "preflight-coverage/2026-11-19.json").read_text())
            self.assertEqual(saved["mode"], "LIVE_PROVIDER_COVERAGE_ONLY")
            self.assertEqual(saved["events"][0]["event_id"], "provider-only-one")
            self.assertNotIn("test-key", stdout.getvalue())
            self.assertEqual(saved["coverage"]["official_game_count"], 4)
            self.assertEqual(len(saved["coverage"]["unavailable_from_provider"]), 3)
            self.assertEqual(main(["board-status", "--date", "2026-11-19"]), 0)
            status = json.loads(stdout.getvalue().splitlines()[-1])
            self.assertEqual(status["selection_ceiling"], 4)
            self.assertEqual(status["provider_discovered_game_count"], 1)
            old = root / "preflight/2026-11-19.json"
            old.parent.mkdir()
            old.write_text("{}")
            os.utime(old, (0, 0))
            scope = root / "scope.json"
            scope.write_text("{}")
            clock.now.return_value = datetime.fromisoformat("2026-11-19T15:00:00-06:00")
            with (
                patch(
                    "fifth_pick.live_board_cli.application_run_store", return_value=RunStore(root)
                ),
                patch("fifth_pick.live_board_cli.datetime", new=clock),
                redirect_stderr(io.StringIO()) as stderr,
            ):
                self.assertEqual(
                    main(
                        ["board-collect", "--run-id", "stale", "--scope", str(scope)],
                        prompt=lambda _: self.fail("stale manifest must not request approval"),
                    ),
                    1,
                )
            self.assertIn("A newer preflight found incomplete coverage", stderr.getvalue())
            request.assert_called_once()

    def test_future_preflight_saves_only_requested_complete_chicago_date(self):
        import io
        from contextlib import redirect_stdout

        from fifth_pick.sources.transport import HttpResponse, UrllibTransport
        from fifth_pick.storage import RunStore

        events = [
            {
                "id": f"tomorrow-{index}",
                "home_team": f"Home {index}",
                "away_team": f"Away {index}",
                "commence_time": "2026-11-20T01:00:00+00:00",
            }
            for index in range(4)
        ]
        events.append(dict(events[0], id="today", commence_time=TIPOFF))
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("fifth_pick.live_board_cli.load_official_slate", return_value=None),
            patch("fifth_pick.official_slate.load_official_slate", return_value=None),
            patch("fifth_pick.cli.application_run_store", return_value=RunStore(directory)),
            patch("fifth_pick.cli.datetime", wraps=datetime) as clock,
            patch.dict("os.environ", {"THE_ODDS_API_KEY": "test-key"}),
            patch.object(UrllibTransport, "get") as request,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            clock.now.return_value = datetime.fromisoformat("2026-11-18T20:30:00-06:00")
            request.return_value = HttpResponse(
                200,
                {"x-requests-last": "0", "x-requests-remaining": "491", "x-requests-used": "9"},
                json.dumps(events).encode(),
            )
            args = ["board-preflight", "--date", "2026-11-19", "--expected-games"]
            future = Path(directory) / "preflight" / "2026-11-19.json"
            self.assertEqual(main([*args, "5"], prompt=lambda _: "PREFLIGHT"), 1)
            self.assertFalse(future.exists())
            self.assertEqual(main([*args, "4"], prompt=lambda _: "PREFLIGHT"), 0)
            saved = json.loads(future.read_text())
            self.assertEqual(
                [row["event_id"] for row in saved["events"]], [f"tomorrow-{i}" for i in range(4)]
            )
            self.assertEqual(main(["board-status", "--date", "2026-11-19"]), 0)
            self.assertEqual(request.call_count, 2)
            status = json.loads(stdout.getvalue().splitlines()[-1])
            self.assertEqual(status["selection_ceiling"], 4)
            self.assertEqual(status["events"][0]["timing"], "SNAPSHOT_1_WINDOW_NOT_YET_OPEN")
            self.assertEqual(status["events"][0]["snapshot_1_cutoff"], "2026-11-19T17:40:00-06:00")
            self.assertEqual(
                status["events"][0]["t20_review_closes_at"], "2026-11-19T18:45:00-06:00"
            )
            saved["events"][1]["event_id"] = saved["events"][0]["event_id"]
            future.write_text(json.dumps(saved))
            self.assertEqual(main(["board-status", "--date", "2026-11-19"]), 1)
            self.assertEqual(request.call_count, 2)

    def test_requires_confirmed_scope_and_passes_only_slot_one(self):
        event = {
            "event_id": EVENT,
            "home_team": "Los Angeles Lakers",
            "away_team": "Utah Jazz",
            "tipoff": TIPOFF,
        }
        scope = {
            "event": event,
            "player_ids": ["luka-doncic"],
            "aliases": {"Luka Doncic": "luka-doncic"},
            "alias_evidence": {"Luka Doncic": "fixture: roster-linked provider label"},
            "slate_game_count": 2,
        }
        preflight = {
            "mode": "LIVE_PROVIDER_DISCOVERY_ONLY",
            "slate_date": "2026-11-18",
            "quota": {"used": 9, "remaining": 491, "last": 0},
            "events": [
                event,
                dict(event, event_id="other-event", home_team="Boston", away_team="Denver"),
            ],
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("fifth_pick.live_board_cli.datetime", wraps=datetime) as clock,
            patch("fifth_pick.live_board_cli.BoardCollector") as collector,
        ):
            clock.now.return_value = datetime.fromisoformat("2026-11-19T00:50:00+00:00")
            root = Path(directory)
            (root / "scope.json").write_text(json.dumps(scope))
            (root / "preflight.json").write_text(json.dumps(preflight))
            args = [
                "board-collect",
                "--run-id",
                "cli-live-test",
                "--scope",
                str(root / "scope.json"),
                "--preflight",
                str(root / "preflight.json"),
            ]
            self.assertEqual(main(args, prompt=lambda _: ""), 1)
            collector.assert_not_called()
            preflight["events"].pop()
            (root / "preflight.json").write_text(json.dumps(preflight))
            self.assertEqual(main(args, prompt=lambda _: f"APPROVE {EVENT} SNAPSHOT 1 5"), 1)
            collector.assert_not_called()
            preflight["events"].append(
                dict(event, event_id="other-event", home_team="Boston", away_team="Denver")
            )
            (root / "preflight.json").write_text(json.dumps(preflight))
            (root / "scope.json").write_text(json.dumps(dict(scope, aliases={})))
            self.assertEqual(main(args, prompt=lambda _: self.fail("unverified scope prompted")), 1)
            (root / "scope.json").write_text(json.dumps(scope))
            clock.now.return_value = datetime.fromisoformat("2026-11-19T01:50:00+00:00")
            self.assertEqual(main(args, prompt=lambda _: self.fail("expired scope prompted")), 1)
            collector.assert_not_called()
            clock.now.return_value = datetime.fromisoformat("2026-11-19T00:50:00+00:00")
            collector.return_value.collect.return_value = ()
            self.assertEqual(main(args, prompt=lambda _: f"APPROVE {EVENT} SNAPSHOT 1 5"), 0)
            grant = collector.call_args.kwargs["live_grant"]
            self.assertEqual(grant.slots, (1,))
            self.assertEqual(grant.slate_event_ids, (EVENT, "other-event"))
            self.assertEqual(grant.expires_at.isoformat(), "2026-11-19T01:50:00+00:00")
            self.assertEqual(collector.call_args.args[1].credit_limit, 5)
            collector.return_value.collect.assert_called_once_with(
                "cli-live-test", 1, EVENT, request_authorized=True
            )
            collector.reset_mock()
            confirmation = f"APPROVE {EVENT} SNAPSHOTS 1-3 15"
            self.assertEqual(
                main([*args, "--series", "--snapshot", "1"], prompt=lambda _: confirmation), 0
            )
            first_grant = collector.call_args.kwargs["live_grant"]
            clock.now.return_value = datetime.fromisoformat("2026-11-19T01:49:00+00:00")
            self.assertEqual(
                main([*args, "--series", "--snapshot", "2"], prompt=lambda _: confirmation), 0
            )
            self.assertEqual(collector.call_args.kwargs["live_grant"], first_grant)
            self.assertEqual(first_grant.slots, (1, 2, 3))
            self.assertEqual(collector.call_args.args[1].credit_limit, 15)
            collector.return_value.collect.assert_called_with(
                "cli-live-test", 2, EVENT, request_authorized=True
            )

    def test_preflight_persists_manifest_and_status_needs_no_network(self):
        import io
        from contextlib import redirect_stdout

        from fifth_pick.sources.transport import HttpResponse, UrllibTransport
        from fifth_pick.storage import RunStore

        event = {
            "id": EVENT,
            "home_team": "Los Angeles Lakers",
            "away_team": "Utah Jazz",
            "commence_time": TIPOFF,
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("fifth_pick.cli.application_run_store", return_value=RunStore(directory)),
            patch("fifth_pick.cli.datetime", wraps=datetime) as clock,
            patch.dict("os.environ", {"THE_ODDS_API_KEY": "test-key"}),
            patch.object(UrllibTransport, "get") as request,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            clock.now.return_value = datetime.fromisoformat("2026-11-18T19:10:00-06:00")
            request.return_value = HttpResponse(
                200,
                {"x-requests-last": "0", "x-requests-remaining": "491", "x-requests-used": "9"},
                json.dumps([event]).encode(),
            )
            self.assertEqual(main(["board-preflight"], prompt=lambda _: "PREFLIGHT"), 0)
            artifact = Path(directory) / "preflight" / "2026-11-18.json"
            self.assertEqual(json.loads(artifact.read_text())["events"][0]["event_id"], EVENT)
            self.assertEqual(main(["board-status"]), 0)
            request.assert_called_once()
            self.assertIn("2026-11-18T19:50:00-06:00", stdout.getvalue())
