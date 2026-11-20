import json
import unittest
from datetime import UTC, datetime, timedelta
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from fifth_pick.models import Category
from fifth_pick.receipts import Receipt
from fifth_pick.sources.base import SourceError
from fifth_pick.sources.bdl_history import HistoryRetrieval
from fifth_pick.sources.live_history import issue_live_history, read_live_history_items
from fifth_pick.sources.supporting_fixture import payload_hash
from fifth_pick.storage import RunStore

NOW = datetime(2026, 11, 18, 16, tzinfo=UTC)
SUBJECT = "event:luka-doncic:analysis"
KEY = "live-history-analysis-event-luka-doncic"


class LiveHistoryTests(unittest.TestCase):
    def test_history_requires_approval_receipts_and_exact_scope(self):
        for count, wrong_id in ((8, False), (7, False), (8, True)):
            with self.subTest(count=count, wrong_id=wrong_id), TemporaryDirectory() as directory:
                store = RunStore(directory)
                path = store.run_directory("run")
                path.mkdir(parents=True)
                source = SimpleNamespace(
                    source_id="balldontlie-nba-history",
                    access_method="balldontlie:nba:stats",
                    terms_review_status="approved",
                )
                config = SimpleNamespace(approved_sources=SimpleNamespace(sources=(source,)))
                games = []
                timing = []
                for offset in range(count):
                    played = NOW - timedelta(days=offset + 1)
                    row = {
                        "id": offset + 1,
                        "season": 2026,
                        "date": played.date().isoformat(),
                        "status_state": "final",
                        "postponed": False,
                        "home_team_id": 1,
                        "visitor_team_id": 2,
                    }
                    games.append(
                        {
                            "game": row,
                            "player": {"id": 99 if wrong_id else 115},
                            "team": {"id": 1},
                            "pts": 23,
                            "reb": 6,
                            "ast": 8,
                            "min": "30:01",
                        }
                    )
                    timing.append(
                        {
                            "game_id": row["id"],
                            "season": 2026,
                            "game_date": row["date"],
                            "played_at": played.isoformat(),
                            "completed_at": (played + timedelta(hours=2)).isoformat(),
                            "opponent_id": 2,
                            "canonical_opponent": "Boston",
                        }
                    )

                def read(store=store):
                    return read_live_history_items(
                        store,
                        "run",
                        event_id="event",
                        player_id="luka-doncic",
                        candidate_key="a" * 64,
                        category=Category.POINTS,
                        phase="analysis",
                        as_of=NOW,
                        event_teams=("Dallas", "Boston"),
                    )

                request_body: dict[str, object] = {
                    "player_id": "luka-doncic",
                    "event_id": "event",
                    "phase": "analysis",
                    "provider_player_id": 115,
                    "before": NOW.date().isoformat(),
                    "season": 2026,
                    "endpoint": "https://api.balldontlie.io/v1/stats",
                    "full_game": True,
                    "max_age_seconds": 60,
                    "page_limit": 1,
                }
                partial = RunStore(path.parent.parent / "partial")
                partial_receipt = Receipt(
                    NOW.isoformat(),
                    "LIVE_HISTORY_REQUEST",
                    "ATTEMPTED",
                    SUBJECT,
                    source.source_id,
                    "synthetic",
                    "run",
                    f"{KEY}-request",
                )
                partial.append_receipt(partial_receipt)
                with self.assertRaisesRegex(SourceError, "not approved"):
                    read(partial)
                with patch("fifth_pick.sources.live_history.load_configs", return_value=config):
                    with self.assertRaisesRegex(SourceError, "incomplete"):
                        read(partial)
                    page = json.dumps({"data": games, "meta": {}}).encode()
                    proof = {
                        "provider_player_id": 115,
                        "coverage_complete": True,
                        "identity_reference": "https://www.nba.com/player/synthetic-roster",
                        "timing_reference": "https://www.nba.com/game/synthetic-games",
                        "canonical_event_opponent": "Boston",
                        "canonical_player_team": "Dallas",
                        "event_opponent_id": 2,
                        "corrections_checked_at": NOW.isoformat(),
                        "games": timing,
                    }

                    def issue(corroboration, store=store, page=page, request_body=request_body):
                        return issue_live_history(
                            store,
                            "run",
                            event_id="event",
                            player_id="luka-doncic",
                            candidate_key="a" * 64,
                            category=Category.POINTS,
                            phase="analysis",
                            event_teams=("Dallas", "Boston"),
                            request=request_body,
                            pages=((page, HistoryRetrieval(None, NOW, payload_hash(page))),),
                            corroboration=corroboration,
                            requested=NOW,
                            retrieved=NOW,
                            confirmed=NOW,
                            controller_confirmed=True,
                        )

                    with self.assertRaisesRegex(SourceError, "independent"):
                        issue(dict(proof, timing_reference="https://api.balldontlie.io/v1/stats"))
                    if count != 8 or wrong_id:
                        with self.assertRaises(SourceError):
                            issue(proof)
                        self.assertEqual(store.read_receipts("run"), ())
                    else:
                        self.assertEqual(sorted(len(item.samples) for item in issue(proof)), [8, 8])
                        self.assertEqual(sorted(len(item.samples) for item in read()), [8, 8])
                        with self.assertRaisesRegex(SourceError, "archive already exists"):
                            issue(proof)
                        (path / f"{KEY}-response.json").write_bytes(b"{}")
                        with self.assertRaisesRegex(SourceError, "digest"):
                            read()
