"""Synthetic archive replay tests. All inputs are local bytes."""

import hashlib
import json
import unittest
from copy import deepcopy
from datetime import date

from fifth_pick.config import load_configs
from fifth_pick.models import Category
from fifth_pick.registry import Registry
from fifth_pick.sources.base import MalformedPayloadError
from fifth_pick.sources.dunkapi_history import HistoryScope
from fifth_pick.sources.dunkapi_replay import replay_dunkapi_history
from fifth_pick.sources.player_history import CompletedPlayerGame

SCOPE = HistoryScope("101", 2027, date(2026, 10, 1), date(2027, 4, 20), 100, 1)
ROW = {
    "game_id": "901",
    "date": "2026-12-30",
    "season": 2027,
    "season_type": 2,
    "opponent": "BOS",
    "home": True,
    "result": "W",
    "did_not_play": False,
    "pts": 21,
    "reb": 6,
    "ast": 7,
    "minutes": "31:30",
}
REGISTRY = Registry.from_universe(load_configs().approved_universe)


def encoded(value):
    return json.dumps(value, sort_keys=True).encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def archives(*rows, next_offset=None):
    identity = encoded(
        {"data": {"players": [{"player_id": "101", "name": "Stephen Curry", "team": "GS"}]}}
    )
    history = encoded(
        {
            "data": {
                "player_id": "101",
                "count": len(rows),
                "games": rows,
                "next_offset": next_offset,
            }
        }
    )
    proof = {
        "provider": "dunkapi",
        "event_id": "synthetic-event",
        "event_teams": ["Golden State Warriors", "Los Angeles Lakers"],
        "request": {
            "player_id": "101",
            "season_end_year": 2027,
            "first_date": "2026-10-01",
            "last_date": "2027-04-20",
            "page_size": 100,
            "max_pages": 1,
        },
        "identity_sha256": digest(identity),
        "pages": [{"offset": 0, "sha256": digest(history)}],
        "retrieved_at": "2027-01-02T00:00:00Z",
        "identity": {
            "provider_player_id": "101",
            "canonical_player_id": "stephen-curry",
            "provider_name": "Stephen Curry",
            "provider_team_labels": ["GS", "GSW"],
            "canonical_team": "Golden State Warriors",
            "reference": "synthetic:roster-crosswalk",
        },
        "games": [
            {
                "game_id": "901",
                "game_date": "2026-12-30",
                "season": "2026-27",
                "canonical_player_id": "stephen-curry",
                "home_team": "Golden State Warriors",
                "away_team": "Boston Celtics",
                "player_team": "Golden State Warriors",
                "provider_opponent": "BOS",
                "actual_played_at": "2026-12-31T01:02:00Z",
                "game_timezone": "America/Los_Angeles",
                "actual_completed_at": "2026-12-31T03:31:00Z",
                "reference": "synthetic:independent-game-record-901",
            }
        ],
    }
    return identity, ((0, history),), proof


class DunkApiReplayTests(unittest.TestCase):
    def replay(self, identity, pages, proof, *, expected_hash=None, player_id="stephen-curry"):
        body = encoded(proof)
        return replay_dunkapi_history(
            identity,
            pages,
            body,
            expected_corroboration_sha256=expected_hash or digest(body),
            scope=SCOPE,
            registry=REGISTRY,
            canonical_player_id=player_id,
            event_id="synthetic-event",
            event_teams=("Golden State Warriors", "Los Angeles Lakers"),
        )

    def test_replay_is_deterministic_and_reuses_completed_game_semantics(self):
        args = archives(ROW)
        first = self.replay(*args)
        self.assertEqual(first, self.replay(*args))
        (game,) = first
        self.assertIsInstance(game, CompletedPlayerGame)
        self.assertEqual(
            (game.game_id, game.season, game.opponent), ("901", "2026-27", "Boston Celtics")
        )
        self.assertEqual(game.sample(Category.PRA).value, 34)
        self.assertEqual(game.sample(Category.REBOUNDS_ASSISTS).value, 13)
        self.assertEqual(game.completed_at.isoformat(), "2026-12-31T03:31:00+00:00")

    def test_missing_naive_conflicting_or_out_of_order_timing_fails(self):
        identity, pages, proof = archives(ROW)
        for changes in (
            {"actual_completed_at": None},
            {"actual_completed_at": "2026-12-31T03:31:00"},
            {"actual_played_at": "2026-12-31T01:02:00"},
            {"actual_completed_at": "2027-01-02T00:00:00Z"},
            {"actual_completed_at": "2026-12-31T01:01:59Z"},
            {"game_timezone": "UTC"},
            {"game_timezone": "No/Such_Zone"},
            {"reference": "https://mcp.dunkapi.com/v1/get_game"},
            {"reference": ""},
        ):
            with self.subTest(changes=changes), self.assertRaises(MalformedPayloadError):
                self.replay(identity, pages, proof | {"games": [proof["games"][0] | changes]})
        with self.assertRaises(MalformedPayloadError):
            self.replay(*archives(dict(ROW, completed_at="2026-12-31T03:32:00Z")))
        with self.assertRaises(MalformedPayloadError):
            self.replay(identity, pages, proof | {"retrieved_at": "2027-01-02T00:00:00"})

    def test_replay_orders_multiple_games_by_actual_start(self):
        second_row = ROW | {"game_id": "902", "date": "2026-12-29"}
        identity, pages, proof = archives(second_row, ROW)
        older = proof["games"][0] | {
            "game_id": "902",
            "game_date": "2026-12-29",
            "actual_played_at": "2026-12-29T17:02:00-08:00",
            "actual_completed_at": "2026-12-29T19:31:00-08:00",
        }
        games = self.replay(identity, pages, proof | {"games": [older, *proof["games"]]})
        self.assertEqual([game.game_id for game in games], ["901", "902"])
        self.assertEqual(games[1].played_at.isoformat(), "2026-12-30T01:02:00+00:00")
        self.assertEqual(
            games, self.replay(identity, pages, proof | {"games": [*proof["games"], older]})
        )

    def test_exact_player_event_team_and_season_bindings(self):
        identity, pages, proof = archives(ROW)
        for field, value in (
            ("canonical_player_id", "luka-doncic"),
            ("season", "2025-26"),
            ("game_date", "2026-12-29"),
            ("provider_opponent", "LAL"),
            ("player_team", "Boston Celtics"),
            ("away_team", "Golden State Warriors"),
            ("game_id", "902"),
        ):
            with self.subTest(field=field), self.assertRaises(MalformedPayloadError):
                self.replay(
                    identity, pages, proof | {"games": [proof["games"][0] | {field: value}]}
                )
        for changes in (
            {"canonical_player_id": "luka-doncic"},
            {"provider_player_id": "102"},
            {"canonical_team": "Boston Celtics"},
            {"provider_name": "Another Player"},
        ):
            with self.subTest(changes=changes), self.assertRaises(MalformedPayloadError):
                self.replay(identity, pages, proof | {"identity": proof["identity"] | changes})
        with self.assertRaises(MalformedPayloadError):
            self.replay(identity, pages, proof | {"event_id": "different-event"})

    def test_archive_hashes_and_scope_are_pinned(self):
        identity, pages, proof = archives(ROW)
        anchor = digest(encoded(proof))
        with self.assertRaises(MalformedPayloadError):
            self.replay(
                identity,
                pages,
                proof | {"retrieved_at": "2027-01-03T00:00:00Z"},
                expected_hash=anchor,
            )
        for changed_identity, changed_pages in (
            (identity + b" ", pages),
            (identity, ((0, pages[0][1] + b" "),)),
            (identity, ()),
        ):
            with self.subTest(pages=len(changed_pages)), self.assertRaises(MalformedPayloadError):
                self.replay(changed_identity, changed_pages, proof)
        amended = deepcopy(proof)
        amended["request"]["season_end_year"] = 2026
        with self.assertRaises(MalformedPayloadError):
            self.replay(identity, pages, amended)

    def test_no_duplicates_missing_corrob_or_incomplete_pages(self):
        identity, pages, proof = archives(ROW)
        for records in ([], proof["games"] * 2):
            with self.subTest(records=len(records)), self.assertRaises(MalformedPayloadError):
                self.replay(identity, pages, proof | {"games": records})
        with self.assertRaises(MalformedPayloadError):
            self.replay(*archives(ROW, ROW))
        with self.assertRaises(MalformedPayloadError):
            self.replay(*archives(ROW, next_offset=1))

    def test_dnp_is_not_an_appearance_and_unknown_fails_closed(self):
        row = {
            key: value for key, value in ROW.items() if key not in ("pts", "reb", "ast", "minutes")
        }
        self.assertEqual(self.replay(*archives(row | {"did_not_play": True})), ())
        with self.assertRaises(MalformedPayloadError):
            self.replay(*archives(row | {"did_not_play": None}))
