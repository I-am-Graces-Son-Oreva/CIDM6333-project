"""Synthetic DunkAPI decoder tests. No provider responses or transports are used."""

import json
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime

from fifth_pick.sources import dunkapi_history as decoder
from fifth_pick.sources.base import MalformedPayloadError

SCOPE = decoder.HistoryScope("101", 2027, date(2026, 10, 1), date(2027, 4, 20), 2, 2)
ROW = {
    "game_id": "901",
    "date": "2026-12-30",
    "season": 2027,
    "season_type": 2,
    "opponent": "BOS",
    "home": True,
    "did_not_play": False,
    "result": "W",
    "pts": 21,
    "reb": 6,
    "ast": 7,
    "minutes": "31:30",
}


def envelope(**data):
    return json.dumps({"data": data}).encode()


def page(*rows, next_offset=None, player_id="101"):
    return envelope(player_id=player_id, count=len(rows), next_offset=next_offset, games=rows)


def box(**changes):
    game = {
        "game_id": "901",
        "season": 2027,
        "date": "2026-12-30",
        "status": "final",
        "home": {"team_id": "201"},
        "away": {"abbrev": "BOS"},
        "starts_at": "2026-12-31T01:00:00Z",
    }
    player = {
        "player_id": "101",
        "team_id": "201",
        **{key: ROW[key] for key in ("did_not_play", "pts", "reb", "ast", "minutes")},
    }
    game.update(changes.get("game", {}))
    player.update(changes.get("player", {}))
    return envelope(game=game, players=[player])


class DunkApiHistoryTests(unittest.TestCase):
    def history(self, *rows):
        return decoder.decode_history(((0, page(*rows)),), SCOPE)

    def test_identity_is_provider_scoped_and_unambiguous(self):
        player = {"player_id": "101", "name": "Synthetic Guard", "team": "XYZ"}

        def decode(rows):
            return decoder.decode_identity(
                envelope(players=rows),
                player_id="101",
                name="Synthetic Guard",
                team_labels=("XYZ",),
            )

        self.assertEqual(decode([player]).player_id, "101")
        for rows in ([player, player], [dict(player, player_id="102")], [dict(player, team="BOS")]):
            with self.subTest(rows=rows), self.assertRaises(MalformedPayloadError):
                decode(rows)

    def test_cross_year_history_preserves_stats_and_missing_metadata(self):
        games = self.history(ROW, dict(ROW, game_id="902", date="2027-01-02")).games
        self.assertEqual([g.game_id for g in games], ["902", "901"])
        self.assertEqual(games[0].season, "2026-27")
        self.assertEqual(
            (
                games[0].stats.points,
                games[0].stats.rebounds,
                games[0].stats.assists,
                games[0].stats.minutes,
            ),
            (21, 6, 7, 31.5),
        )
        self.assertIsNone(games[0].metadata.completed_at)
        self.assertIsNone(games[0].metadata.source_updated_at)
        self.assertIsNone(games[0].metadata.revision_id)
        self.assertFalse(hasattr(games[0], "sample"))

    def test_reported_metadata_is_preserved_without_claiming_verification(self):
        changes = {
            "completed_at": "2026-12-31T03:26:00Z",
            "updated_at": "2026-12-31T04:00:00Z",
            "corrected_at": "2027-01-01T12:00:00Z",
            "revision_id": "rev-2",
        }
        row = self.history(ROW | changes).games[0]
        self.assertEqual(row.metadata.completed_at, datetime(2026, 12, 31, 3, 26, tzinfo=UTC))
        self.assertEqual(row.metadata.source_updated_at, datetime(2026, 12, 31, 4, tzinfo=UTC))
        self.assertEqual(row.metadata.corrected_at, datetime(2027, 1, 1, 12, tzinfo=UTC))
        self.assertEqual(row.metadata.revision_id, "rev-2")
        self.assertFalse(row.explicitly_final)
        with self.assertRaises(MalformedPayloadError):
            decoder.verify_box_score(
                box(game={"completed_at": "2026-12-31T03:27:00Z"}), row, team_id="201"
            )

    def test_nonplaying_and_unknown_are_distinct_and_not_stat_samples(self):
        rows = {
            key: val
            for key, val in ROW.items()
            if key not in ("pts", "reb", "ast", "minutes", "did_not_play")
        }
        dnp, unknown = self.history(dict(rows, game_id="902", did_not_play=True), rows).games
        self.assertEqual(dnp.participation.value, "DNP")
        self.assertEqual(unknown.participation.value, "UNKNOWN")
        self.assertIsNone(dnp.stats)
        self.assertIsNone(unknown.stats)
        self.assertEqual(
            self.history(dict(ROW, did_not_play=None)).games[0].participation.value, "UNKNOWN"
        )
        with self.assertRaises(MalformedPayloadError):
            self.history(dict(rows, pts=1))
        with self.assertRaises(MalformedPayloadError):
            self.history(dict(ROW, did_not_play=True))

    def test_invalid_game_fields_fail_closed(self):
        for changes in (
            {"game_id": "0"},
            {"date": "2027-02-30"},
            {"date": "2028-01-01"},
            {"season": 2026},
            {"season_type": "playoffs"},
            {"opponent": "??"},
            {"home": 1},
            {"pts": True},
            {"reb": -1},
            {"ast": None},
            {"minutes": 0},
            {"minutes": "20:60"},
            {"minutes": "NaN"},
            {"did_not_play": "false"},
            {"status": "scheduled"},
            {"league": "wnba"},
            {"updated_at": "2027-01-01"},
        ):
            with self.subTest(changes=changes), self.assertRaises(MalformedPayloadError):
                self.history(ROW | changes)

    def test_malformed_envelope_and_wrong_history_identity(self):
        for body in (
            b"{",
            b'{"data":[]}',
            b'{"data":{},"data":{}}',
            b'{"data":{"unknown":NaN}}',
            page(ROW, player_id="102"),
            envelope(player_id="101", count=1, games=[ROW]),
            envelope(player_id="101", count=0, next_offset=None, games=[ROW]),
        ):
            with self.subTest(body=body), self.assertRaises(MalformedPayloadError):
                decoder.decode_history(((0, body),), SCOPE)

    def test_pagination_requires_bounded_contiguous_terminal_pages(self):
        first = page(ROW, dict(ROW, game_id="903"), next_offset=2)
        second = page(dict(ROW, game_id="902"))
        history = decoder.decode_history(((0, first), (2, second)), SCOPE)
        self.assertEqual(len(history.games), 3)
        self.assertEqual(len(history.payload_sha256), 2)
        for pages, scope in (
            (((0, first),), SCOPE),
            (((0, first), (1, second)), SCOPE),
            (((0, first), (2, page(ROW))), SCOPE),
            (((0, page(ROW, ROW)),), SCOPE),
            (((0, first), (2, second)), replace(SCOPE, max_pages=1)),
            (((0, second), (2, second)), SCOPE),
        ):
            with self.subTest(page_count=len(pages)), self.assertRaises(MalformedPayloadError):
                decoder.decode_history(pages, scope)

    def test_box_score_crosscheck_preserves_start_without_inventing_completion(self):
        row = self.history(ROW).games[0]
        result = decoder.verify_box_score(box(), row, team_id="201")
        self.assertEqual(result.scheduled_start_at, datetime(2026, 12, 31, 1, tzinfo=UTC))
        self.assertIsNone(result.metadata.completed_at)
        for changes in (
            {"game": {"status": "scheduled"}},
            {"game": {"season_type": "playoffs"}},
            {"game": {"game_id": "902"}},
            {"game": {"date": "2026-12-31"}},
            {"game": {"away": {"abbrev": "LAL"}}},
            {"player": {"team_id": "202"}},
            {"player": {"player_id": "102"}},
            {"player": {"pts": 22}},
            {"player": {"did_not_play": True}},
        ):
            with self.subTest(changes=changes), self.assertRaises(MalformedPayloadError):
                decoder.verify_box_score(box(**changes), row, team_id="201")
