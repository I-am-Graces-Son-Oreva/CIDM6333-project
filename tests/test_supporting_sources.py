import hashlib
import json
import unittest
from datetime import UTC, datetime, timedelta

from fifth_pick.evidence import EvidenceKind, validate_evidence_items
from fifth_pick.models import Category
from fifth_pick.sources.availability import resolve_fixture_availability
from fifth_pick.sources.base import EvidenceMode, SourceError, SourceEvent
from fifth_pick.sources.game_lines import parse_game_lines_fixture
from fifth_pick.sources.player_history import parse_history_fixture

NOW = datetime(2026, 11, 18, 17, tzinfo=UTC)
EVENT = SourceEvent("event1", "Dallas", "Boston", NOW + timedelta(hours=2), ())
KEY = "a" * 64


def game_lines_payload():
    return [
        {
            "id": EVENT.event_id,
            "sport_key": "basketball_nba",
            "home_team": EVENT.home_team,
            "away_team": EVENT.away_team,
            "commence_time": EVENT.commence_time.isoformat(),
            "bookmakers": [
                {
                    "key": "fixture-book",
                    "last_update": NOW.isoformat(),
                    "markets": [
                        {
                            "key": "spreads",
                            "outcomes": [
                                {"name": EVENT.home_team, "point": -5.5},
                                {"name": EVENT.away_team, "point": 5.5},
                            ],
                        },
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "point": 212.5},
                                {"name": "Under", "point": 212.5},
                            ],
                        },
                    ],
                }
            ],
        }
    ]


def history_payload():
    return {
        "player_id": "p1",
        "updated_at": (NOW - timedelta(minutes=15)).isoformat(),
        "games": [
            {
                "game_id": f"g{offset}",
                "player_id": "p1",
                "played_at": (NOW - timedelta(days=offset + 1, hours=2)).isoformat(),
                "completed_at": (NOW - timedelta(days=offset + 1)).isoformat(),
                "opponent": "Boston" if offset % 2 == 0 else "Miami",
                "season": "2026-27" if offset < 7 else "2025-26",
                "points": 10 + offset,
                "rebounds": 4,
                "assists": 7,
                "minutes": 23.5,
            }
            for offset in range(10)
        ],
    }


def parse_lines(payload):
    return parse_game_lines_fixture(
        json.dumps(payload).encode(),
        expected_events=(EVENT,),
        retrieved_at=NOW,
        max_age=timedelta(minutes=10),
        bookmaker_keys=frozenset({"fixture-book"}),
    )


def parse_history(payload):
    return parse_history_fixture(
        json.dumps(payload).encode(),
        player_id="p1",
        retrieved_at=NOW,
        max_age=timedelta(hours=1),
    )


class SupportingSourceTests(unittest.TestCase):
    def test_game_lines_bind_bookmaker_event_and_fixture_receipt_material(self):
        body = json.dumps(game_lines_payload()).encode()
        (lines,) = parse_lines(game_lines_payload())
        self.assertEqual(lines.event_id, EVENT.event_id)
        self.assertEqual(lines.bookmaker_key, "fixture-book")
        self.assertEqual(lines.total, 212.5)
        self.assertEqual(lines.home_spread, -5.5)
        self.assertEqual(lines.payload_sha256, hashlib.sha256(body).hexdigest())
        items = validate_evidence_items(lines.evidence(candidate_key=KEY), candidate_key=KEY)
        self.assertEqual(
            {item.kind for item in items}, {EvidenceKind.GAME_TOTAL, EvidenceKind.POINT_SPREAD}
        )
        self.assertTrue(all(item.evidence_mode is EvidenceMode.FIXTURE for item in items))

    def test_game_lines_reject_stale_wrong_event_or_inconsistent_sides(self):
        for change in ("stale", "stale_market", "different_team", "inconsistent_spread"):
            with self.subTest(change=change), self.assertRaises(SourceError):
                payload = game_lines_payload()
                event = payload[0]
                book = event["bookmakers"][0]
                if change == "stale":
                    book["last_update"] = (NOW - timedelta(minutes=11)).isoformat()
                if change == "stale_market":
                    book["markets"][0]["last_update"] = (NOW - timedelta(minutes=11)).isoformat()
                if change == "different_team":
                    event["away_team"] = "Toronto"
                if change == "inconsistent_spread":
                    book["markets"][0]["outcomes"][1]["point"] = 6.5
                parse_lines(payload)

    def test_game_lines_absence_remains_absence_and_duplicate_event_is_rejected(self):
        self.assertEqual(parse_lines([]), ())
        with self.assertRaises(SourceError):
            parse_lines(game_lines_payload() * 2)

    def test_history_reuses_m6_sample_type_and_generates_scoped_combination_stats(self):
        history = parse_history(history_payload())
        self.assertEqual(history.games[0].minutes, 23.5)
        items = validate_evidence_items(
            history.evidence(
                candidate_key=KEY,
                category=Category.PRA,
                opponent="Boston",
                season="2026-27",
            ),
            candidate_key=KEY,
        )
        last, head = items
        self.assertEqual(len(last.samples), 8)
        self.assertEqual(sorted(item.value for item in last.samples), list(range(21, 29)))
        self.assertEqual({item.value for item in head.samples}, {21, 23, 25, 27})
        self.assertTrue(all(item.evidence_mode is EvidenceMode.FIXTURE for item in items))

    def test_history_rejects_future_mixed_identity_or_duplicate_game(self):
        for change in ("future", "other_player", "duplicate"):
            with self.subTest(change=change), self.assertRaises(SourceError):
                payload = history_payload()
                if change == "future":
                    payload["games"][0]["completed_at"] = (NOW + timedelta(days=1)).isoformat()
                if change == "other_player":
                    payload["games"][0]["player_id"] = "p2"
                if change == "duplicate":
                    payload["games"].append(payload["games"][0])
                parse_history(payload)

    def test_incomplete_history_and_missing_h2h_are_not_fabricated(self):
        payload = history_payload()
        payload["games"] = payload["games"][:1]
        items = parse_history(payload).evidence(
            candidate_key=KEY,
            category=Category.REBOUNDS_ASSISTS,
            opponent="Utah",
            season="2026-27",
        )
        self.assertEqual([item.kind for item in items], [EvidenceKind.LAST_8])
        self.assertEqual([item.value for item in items[0].samples], [11])

    def test_availability_prefers_newer_official_report_over_editorial(self):
        observations = [
            ("official-nba-injury-report", "QUESTIONABLE", 9),
            ("nba-com", "OUT", 4),
            ("sports-illustrated-nba", "AVAILABLE", 1),
        ]
        resolved = self.resolve_availability(observations)
        self.assertIsNotNone(resolved.selected)
        assert resolved.selected is not None
        self.assertEqual(resolved.selected.status, "OUT")
        self.assertTrue(resolved.conflict)
        items = validate_evidence_items(
            resolved.evidence(candidate_key=KEY, kind=EvidenceKind.TEAMMATE_ABSENCE),
            candidate_key=KEY,
        )
        self.assertEqual((items[0].facts or {})["status"], "OUT")
        self.assertTrue((items[0].facts or {})["reported_conflict"])

    def test_availability_blocks_tied_official_conflict_and_editorial_only(self):
        for observations in (
            [("nba-com", "AVAILABLE", 1), ("official-nba-injury-report", "OUT", 1)],
            [("sports-illustrated-nba", "AVAILABLE", 1)],
        ):
            with self.subTest(observations=observations):
                resolved = self.resolve_availability(observations)
                self.assertIsNone(resolved.selected)
                self.assertEqual(
                    resolved.evidence(candidate_key=KEY, kind=EvidenceKind.AVAILABILITY), ()
                )

    def test_availability_rejects_stale_or_unapproved_source_rows(self):
        for observations in (
            [("official-nba-injury-report", "OUT", 31)],
            [("other-provider", "AVAILABLE", 1)],
        ):
            with self.subTest(observations=observations), self.assertRaises(SourceError):
                self.resolve_availability(observations)

    @staticmethod
    def resolve_availability(observations):
        body = [
            {
                "role": role,
                "status": status,
                "player_id": "p1",
                "event_id": EVENT.event_id,
                "last_update": (NOW - timedelta(minutes=minutes)).isoformat(),
            }
            for role, status, minutes in observations
        ]
        return resolve_fixture_availability(
            json.dumps(body).encode(),
            player_id="p1",
            event_id=EVENT.event_id,
            retrieved_at=NOW,
            max_age=timedelta(minutes=30),
        )
