import unittest
from datetime import date, datetime

from fifth_pick.official_slate import load_official_slate, reconcile_coverage
from fifth_pick.sources.base import SourceEvent


class OfficialSlateCoverageTests(unittest.TestCase):
    def test_partial_with_off_date_match_keeps_four_official_games(self):
        day = date(2026, 11, 19)
        official = load_official_slate(day)
        assert official is not None
        events = (
            SourceEvent(
                "only-covered",
                "San Antonio Spurs",
                "Los Angeles Clippers",
                datetime.fromisoformat("2026-11-20T01:10:00+00:00"),
                (),
            ),
            SourceEvent(
                "wrong-date",
                "Memphis Grizzlies",
                "Golden State Warriors",
                datetime.fromisoformat("2026-11-20T06:10:00+00:00"),
                (),
            ),
        )
        report = reconcile_coverage(official, events, day=day)
        self.assertEqual(report["official_game_count"], 4)
        self.assertEqual(report["selection_ceiling"], 4)
        self.assertFalse(report["provider_matches_official_slate"])
        self.assertEqual(len(report["unavailable_from_provider"]), 3)
        self.assertEqual(
            report["official_matchups_on_other_provider_dates"][0]["chicago_date"], "2026-11-20"
        )
        self.assertEqual(report["provider_covered_authorized_player_events"], [])
        self.assertEqual(
            report["provider_tipoff_differences"][0]["official_scheduled_tipoff"],
            "2026-11-19T19:00:00-06:00",
        )
