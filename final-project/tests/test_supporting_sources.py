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
    def test_history_join_demands_independent_completed_game_timing(self):
        from dataclasses import replace

        from fifth_pick.sources.bdl_history import HistoryGameRow
        from fifth_pick.sources.player_history import HistoryGameTiming, reconcile_history_timing

        played = NOW - timedelta(days=1, hours=2)
        completed = NOW - timedelta(days=1)
        row = HistoryGameRow(12, 9, played.date(), 2026, 4, 11, 5, 7, 28)
        timing = HistoryGameTiming(played.date(), played, completed, 2026, 4, "Boston")

        def reconcile(timings):
            return reconcile_history_timing(
                (row,), timings, provider_player_id=12, retrieved_at=NOW
            )

        (game,) = reconcile({9: timing})
        self.assertEqual((game.played_at, game.completed_at, game.assists), (played, completed, 7))
        for timings in (
            {},
            {9: replace(timing, opponent_id=7)},
            {9: replace(timing, completed_at=NOW)},
        ):
            with self.assertRaises(SourceError):
                reconcile(timings)

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

    def test_official_edition_matches_eastern_timestamp_and_freshness(self):
        from fifth_pick.sources.availability import check_official_edition

        url = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-18_12_00PM.pdf"
        age = timedelta(minutes=30)
        check_official_edition(url, NOW, NOW + timedelta(minutes=10), age)
        for ref, published, retrieved in (
            (url.replace("nba.com", "example.com"), NOW, NOW),
            (url, NOW - timedelta(minutes=1), NOW),
            (url, NOW, NOW + timedelta(minutes=31)),
            (url, NOW.replace(tzinfo=None), NOW),
        ):
            with self.assertRaises(SourceError):
                check_official_edition(ref, published, retrieved, age)

    def test_game_lines_replay_binds_request_and_digest_and_refuses_duplicate(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import Mock

        from fifth_pick.sources.game_lines import (
            replay_game_lines_request,
            verify_game_lines_replay,
        )
        from fifth_pick.sources.transport import HttpResponse
        from fifth_pick.storage import RunStore

        body = json.dumps(game_lines_payload()).encode()
        transport = Mock(evidence_mode=EvidenceMode.FIXTURE)
        transport.get.return_value = HttpResponse(200, {}, body)
        with TemporaryDirectory() as temp:
            store = RunStore(Path(temp))

            def replay(source):
                return replay_game_lines_request(
                    store,
                    "replay",
                    transport=source,
                    event=EVENT,
                    phase="analysis",
                    bookmaker="fixture-book",
                    observed_at=NOW,
                    max_age=timedelta(minutes=10),
                )

            result = replay(transport)
            with self.assertRaises(SourceError):
                replay(transport)
            with self.assertRaises(SourceError):
                replay(Mock(evidence_mode=EvidenceMode.LIVE))
            transport.get.assert_called_once()
            self.assertEqual(result.payload_sha256, hashlib.sha256(body).hexdigest())
            self.assertEqual(len(store.read_receipts("replay")), 2)

            def verify(payload, bookmaker="fixture-book", as_of=NOW):
                return verify_game_lines_replay(
                    store,
                    "replay",
                    payload,
                    event=EVENT,
                    phase="analysis",
                    bookmaker=bookmaker,
                    max_age=timedelta(minutes=10),
                    as_of=as_of,
                )

            self.assertEqual(verify(body), result)
            for payload, bookmaker in ((body + b" ", "fixture-book"), (body, "other")):
                with self.assertRaises(SourceError):
                    verify(payload, bookmaker)
            with self.assertRaises(SourceError):
                verify(body, as_of=NOW + timedelta(minutes=11))

    def test_exact_game_lines_acquisition_rejects_an_extra_event_or_bookmaker(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import Mock

        from fifth_pick.sources.game_lines import replay_game_lines_request
        from fifth_pick.sources.transport import HttpResponse
        from fifth_pick.storage import RunStore

        for extra in ("event", "bookmaker"):
            with self.subTest(extra=extra), TemporaryDirectory() as directory:
                payload = game_lines_payload()
                if extra == "event":
                    payload.append(dict(payload[0], id="outside"))
                else:
                    book = payload[0]["bookmakers"][0]
                    payload[0]["bookmakers"].append(dict(book, key="outside"))
                transport = Mock(evidence_mode=EvidenceMode.FIXTURE)
                transport.get.return_value = HttpResponse(200, {}, json.dumps(payload).encode())
                store = RunStore(directory)
                with self.assertRaises(SourceError):
                    replay_game_lines_request(
                        store,
                        "scope",
                        transport=transport,
                        event=EVENT,
                        phase="analysis",
                        bookmaker="fixture-book",
                        observed_at=NOW,
                        max_age=timedelta(minutes=10),
                    )
                self.assertEqual(
                    [row["result"] for row in store.read_receipts("scope")], ["ATTEMPTED"]
                )

    def test_official_edition_replay_requires_exact_player_event_and_publication(self):
        from fifth_pick.sources.availability import replay_official_edition

        def replay(row):
            return replay_official_edition(
                json.dumps([row]).encode(),
                reference="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-18_12_00PM.pdf",
                published_at=NOW,
                retrieved_at=NOW + timedelta(minutes=10),
                max_age=timedelta(minutes=20),
                player_id="p1",
                event_id=EVENT.event_id,
            )

        row = dict(
            player_id="p1",
            event_id=EVENT.event_id,
            role="official-nba-injury-report",
            last_update=NOW.isoformat(),
            status="OUT",
        )
        self.assertIsNotNone(replay(row).selected)
        for change in (
            {"player_id": "p2"},
            {"event_id": "other"},
            {"role": "nba-com"},
            {"last_update": (NOW - timedelta(minutes=1)).isoformat()},
        ):
            with self.assertRaises(SourceError):
                replay(row | change)

    def test_injury_edition_acquisition_checks_origin_and_pdf_shape(self):
        from unittest.mock import Mock

        from fifth_pick.sources.availability import replay_official_document
        from fifth_pick.sources.transport import HttpResponse

        url = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-18_12_00PM.pdf"
        body = b"%PDF-1.7\nsynthetic test bytes\n%%EOF"
        transport = Mock(evidence_mode=EvidenceMode.FIXTURE)
        transport.get.return_value = HttpResponse(200, {"Content-Type": "application/pdf"}, body)

        def replay(ref, source=transport):
            return replay_official_document(
                source,
                reference=ref,
                published_at=NOW,
                retrieved_at=NOW,
                max_age=timedelta(minutes=15),
            )

        with self.assertRaises(SourceError):
            replay(url.replace("nba.com", "example.com"))
        transport.get.assert_not_called()
        self.assertEqual(replay(url).payload_sha256, hashlib.sha256(body).hexdigest())
        transport.get.assert_called_once_with(url, {"Accept": "application/pdf"})
        transport.get.return_value = HttpResponse(200, {"Content-Type": "application/pdf"}, b"html")
        with self.assertRaises(SourceError):
            replay(url)
        live = Mock(evidence_mode=EvidenceMode.LIVE)
        with self.assertRaises(SourceError):
            replay(url, live)
        live.get.assert_not_called()
