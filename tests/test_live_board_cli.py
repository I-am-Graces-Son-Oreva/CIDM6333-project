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
