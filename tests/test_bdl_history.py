import json
import unittest

from fifth_pick.sources.base import MalformedPayloadError
from fifth_pick.sources.bdl_history import HistoryPage, complete_history, parse_history_page


class HistoryContractTests(unittest.TestCase):
    def test_requires_complete_bounded_cursor_chain(self):
        first = HistoryPage((), 42, "test-first")
        last = HistoryPage((), None, "test-last")
        self.assertEqual(complete_history(((None, first), (42, last)), max_pages=2), ())
        for sequence in (((None, first),), ((None, first), (41, last))):
            with self.assertRaises(MalformedPayloadError):
                complete_history(sequence, max_pages=2)
        with self.assertRaises(MalformedPayloadError):
            complete_history(((None, first), (42, last)), max_pages=1)

    def test_exact_id_final_status_minutes_and_opponent(self):
        row = {
            "player": {"id": 12},
            "team": {"id": 3},
            "game": {
                "id": 1,
                "date": "2026-11-17",
                "season": 2026,
                "status_state": "final",
                "postponed": False,
                "home_team_id": 3,
                "visitor_team_id": 4,
            },
            "pts": 9,
            "reb": 5,
            "ast": 3,
            "min": "21:30",
        }

        def parse(rows, **meta):
            return parse_history_page(json.dumps({"data": rows, "meta": meta}).encode(), {12})

        page = parse([row], next_cursor=42)
        self.assertEqual(page.next_cursor, 42)
        (game,) = page.games
        self.assertEqual((game.opponent_id, game.minutes, game.points), (4, 21.5, 9))
        for bad in (
            dict(row, player={"id": 99}),
            dict(row, game=dict(row["game"], status_state="live")),
            dict(row, min="21:61"),
            dict(row, min="0"),
        ):
            with self.assertRaises(MalformedPayloadError):
                parse([bad])
        with self.assertRaises(MalformedPayloadError):
            parse([row, row])
