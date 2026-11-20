import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from fifth_pick.sources.base import EvidenceMode, SourceError
from fifth_pick.sources.quota import QuotaSnapshot
from fifth_pick.sources.transport import HttpResponse
from fifth_pick.storage import RunStore
from tests.test_supporting_sources import EVENT, NOW, game_lines_payload


class GameLinesLiveTests(unittest.TestCase):
    def test_missing_approval_and_interrupted_response_do_not_dispatch_again(self):
        from fifth_pick.sources.game_lines import (
            GameLinesGrant,
            acquire_game_lines,
            read_live_game_lines,
            record_game_lines_grant,
        )

        transport = Mock(evidence_mode=EvidenceMode.LIVE)
        body = json.dumps(game_lines_payload()).encode()
        transport.get.return_value = HttpResponse(
            200,
            {"x-requests-last": "2", "x-requests-used": "12", "x-requests-remaining": "8"},
            body,
        )
        grant = GameLinesGrant("series", EVENT.event_id, "fixture-book", ("analysis",), 2)
        with TemporaryDirectory() as directory:
            store = RunStore(directory)

            def acquire(authorized):
                return acquire_game_lines(
                    store,
                    grant,
                    transport=transport,
                    phase="analysis",
                    event=EVENT,
                    quota_before=QuotaSnapshot(remaining=10, used=10),
                    max_age=timedelta(minutes=10),
                    clock=lambda: NOW,
                    environ={"THE_ODDS_API_KEY": "test-credential"},
                    authorized=authorized,
                )

            with self.assertRaises(SourceError):
                acquire(False)
            with self.assertRaisesRegex(SourceError, "previously recorded"):
                acquire(True)
            transport.get.assert_not_called()
            record_game_lines_grant(store, grant, NOW)
            result = acquire(True)
            self.assertEqual(result.total, 212.5)

            def reopen():
                return read_live_game_lines(
                    store,
                    "series",
                    EVENT,
                    phase="analysis",
                    as_of=NOW,
                    max_age=timedelta(minutes=10),
                )

            reopened = reopen()
            assert reopened is not None
            confirmed, reference = reopened
            self.assertEqual(confirmed.payload_sha256, result.payload_sha256)
            self.assertIn(EVENT.event_id, reference)
            path = store.run_directory("series") / f"game-lines-live-analysis-{EVENT.event_id}.json"
            path.write_bytes(body + b" ")
            with self.assertRaisesRegex(SourceError, "digest"):
                reopen()
            with self.assertRaises(SourceError):
                acquire(True)
            transport.get.assert_called_once()
            self.assertNotIn("test-credential", json.dumps(store.read_receipts("series")))

    def test_cli_writes_exact_grant_only_after_confirmation(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from types import SimpleNamespace
        from unittest.mock import patch

        from fifth_pick.cli import main

        event = replace(EVENT, commence_time=datetime.now(UTC) + timedelta(hours=2))
        context = SimpleNamespace(
            event_boards=(SimpleNamespace(evidence_mode=EvidenceMode.LIVE, events=(event,)),)
        )
        args = [
            "game-lines-grant",
            "--run-id",
            "series",
            "--event-id",
            EVENT.event_id,
            "--bookmaker",
            "owner-book",
            "--phase",
            "analysis",
            "--max-credits",
            "2",
        ]
        with TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            store = RunStore(directory)
            with (
                patch("fifth_pick.cli.application_run_store", return_value=store),
                patch("fifth_pick.cli.read_slate_run_context", return_value=context),
                patch("fifth_pick.board_collection.live_slot_has_bound_aliases") as bound,
            ):
                bound.return_value = False
                self.assertEqual(main(args, prompt=lambda _: "AUTHORIZE GAME LINES"), 1)
                self.assertEqual(store.read_receipts("series"), ())
                bound.return_value = True
                self.assertEqual(main(args, prompt=lambda _: "cancel"), 1)
                self.assertEqual(store.read_receipts("series"), ())
                self.assertEqual(main(args, prompt=lambda _: "AUTHORIZE GAME LINES"), 0)
            (receipt,) = store.read_receipts("series")
            self.assertEqual(receipt["event"], "LIVE_GAME_LINES_GRANT")
            self.assertIn("owner-book", receipt["reason"] or "")
