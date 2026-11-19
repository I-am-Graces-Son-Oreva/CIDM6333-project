import unittest
from dataclasses import replace
from datetime import UTC, datetime

from fifth_pick.personal_readiness import LiveEventScope
from fifth_pick.sources.alias_crosswalk import BoardIdentity, RosterIdentity, join_event_aliases
from fifth_pick.sources.base import SourceError


class AliasCrosswalkTests(unittest.TestCase):
    def test_links_only_exact_stable_identity_with_both_references(self):
        scope = LiveEventScope(
            "event-1", "Home", "Away", datetime(2026, 11, 19, tzinfo=UTC), ("luka-doncic",)
        )
        roster = RosterIdentity("nba-1", "luka-doncic", "Home", "roster receipt")
        board = BoardIdentity("nba-1", "Observed label", "event-1", "Home", "provider receipt")
        outsider = replace(board, stable_id="nba-2")
        self.assertEqual(
            join_event_aliases(scope, (roster,), (board,)),
            (
                {"Observed label": "luka-doncic"},
                {"Observed label": "roster=roster receipt | board=provider receipt"},
            ),
        )
        self.assertEqual(join_event_aliases(scope, (roster,), (outsider,)), ({}, {}))
        for rows in ((board, outsider), (replace(board, team="Away"),)):
            with self.assertRaises(SourceError):
                join_event_aliases(scope, (roster,), rows)
        conflicting = replace(roster, canonical_id="outside-universe")
        with self.assertRaises(SourceError):
            join_event_aliases(scope, (roster, conflicting), (board,))
