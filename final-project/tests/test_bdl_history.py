import json
import unittest

from fifth_pick.sources.base import EvidenceMode, MalformedPayloadError
from fifth_pick.sources.bdl_history import (
    HistoryGameRow,
    HistoryPage,
    complete_history,
    parse_history_page,
    select_history_rows,
)


class HistoryContractTests(unittest.TestCase):
    def test_last_eight_and_same_season_opponent_are_separate(self):
        from datetime import date

        games = tuple(
            HistoryGameRow(12, i, date(2026, 11, i), 2026, 3 if i % 2 else 4, 17, 6, 8, 27)
            for i in range(1, 10)
        )
        old = HistoryGameRow(12, 40, date(2025, 11, 1), 2025, 3, 17, 6, 8, 27)
        last_eight, h2h = select_history_rows(
            (*games, old), provider_player_id=12, season=2026, opponent_id=3
        )
        self.assertEqual([game.game_id for game in last_eight], list(range(9, 1, -1)))
        self.assertEqual([game.game_id for game in h2h], [9, 7, 5, 3, 1])
        with self.assertRaises(MalformedPayloadError):
            select_history_rows(
                (*games, games[0]), provider_player_id=12, season=2026, opponent_id=3
            )

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


class HistoryTransportTests(unittest.TestCase):
    def test_live_transport_stops_before_request_without_verified_binding(self):
        from datetime import date
        from unittest.mock import patch

        from fifth_pick.sources.base import LiveAuthorizationError
        from fifth_pick.sources.bdl_history import BdlHistoryClient
        from fifth_pick.sources.transport import UrllibTransport

        transport = UrllibTransport()
        with patch.object(transport, "get") as request:
            with self.assertRaisesRegex(LiveAuthorizationError, "verified provider identity"):
                BdlHistoryClient(transport, environ={"BALLDONTLIE_API_KEY": "synthetic"}).fetch(
                    canonical_player_id="luka-doncic",
                    identity_reference="unverified caller text",
                    provider_player_id=12,
                    season=2026,
                    before=date(2026, 11, 19),
                    page_limit=1,
                    authorized=True,
                )
            request.assert_not_called()

    def test_adapter_propagates_cursor_without_changing_history_scope(self):
        from datetime import date
        from unittest.mock import Mock
        from urllib.parse import parse_qs, urlsplit

        from fifth_pick.sources.bdl_history import BdlHistoryClient
        from fifth_pick.sources.transport import HttpResponse

        transport = Mock(evidence_mode=EvidenceMode.FIXTURE)
        transport.get.side_effect = [
            HttpResponse(200, {}, b'{"data":[],"meta":{"next_cursor":14}}'),
            HttpResponse(200, {}, b'{"data":[],"meta":{}}'),
        ]
        _, pages = BdlHistoryClient(transport, environ={"BALLDONTLIE_API_KEY": "synthetic"}).fetch(
            canonical_player_id="luka-doncic",
            identity_reference="fixture:verified-crosswalk",
            provider_player_id=12,
            season=2026,
            before=date(2026, 11, 19),
            page_limit=2,
            authorized=True,
        )
        self.assertEqual([page.cursor for page in pages], [None, 14])
        first, second = [
            parse_qs(urlsplit(call.args[0]).query) for call in transport.get.call_args_list
        ]
        self.assertEqual(second.pop("cursor"), ["14"])
        self.assertEqual(first, second)

    def test_adapter_uses_one_scoped_request_without_key_in_url(self):
        from datetime import UTC, date, datetime
        from unittest.mock import Mock
        from urllib.parse import parse_qs, urlsplit

        from fifth_pick.sources.base import LiveAuthorizationError
        from fifth_pick.sources.bdl_history import BdlHistoryClient
        from fifth_pick.sources.transport import HttpResponse

        transport = Mock(evidence_mode=EvidenceMode.FIXTURE)
        transport.get.return_value = HttpResponse(200, {}, b'{"data":[],"meta":{}}')
        client = BdlHistoryClient(
            transport,
            environ={"BALLDONTLIE_API_KEY": "synthetic-secret"},
            clock=lambda: datetime(2026, 11, 18, tzinfo=UTC),
        )

        def fetch(authorized: bool = False, canonical: str = "luka-doncic"):
            return client.fetch(
                canonical_player_id=canonical,
                identity_reference="fixture:verified-crosswalk",
                provider_player_id=12,
                season=2026,
                before=date(2026, 11, 19),
                page_limit=1,
                authorized=authorized,
            )

        with self.assertRaises(LiveAuthorizationError):
            fetch()
        with self.assertRaises(LiveAuthorizationError):
            fetch(True, "outside-the-universe")
        transport.get.assert_not_called()
        games, pages = fetch(True)
        self.assertEqual(games, ())
        self.assertEqual(len(pages), 1)
        transport.get.assert_called_once()
        url, headers = transport.get.call_args.args
        self.assertNotIn("synthetic-secret", url)
        self.assertEqual(headers["Authorization"], "synthetic-secret")
        self.assertIn(("player_ids[]", ["12"]), parse_qs(urlsplit(url).query).items())
        self.assertIn(("end_date", ["2026-11-18"]), parse_qs(urlsplit(url).query).items())

    def test_adapter_stops_at_page_budget_and_on_provider_error(self):
        from datetime import date
        from unittest.mock import Mock

        from fifth_pick.sources.base import SourceError
        from fifth_pick.sources.bdl_history import BdlHistoryClient
        from fifth_pick.sources.transport import HttpResponse

        for response in (
            HttpResponse(200, {}, b'{"data":[],"meta":{"next_cursor":14}}'),
            HttpResponse(429, {}, b"secret-response"),
        ):
            transport = Mock(evidence_mode=EvidenceMode.FIXTURE)
            transport.get.return_value = response
            client = BdlHistoryClient(transport, environ={"BALLDONTLIE_API_KEY": "synthetic"})
            with self.assertRaises(SourceError) as raised:
                client.fetch(
                    canonical_player_id="luka-doncic",
                    identity_reference="fixture:verified-crosswalk",
                    provider_player_id=12,
                    season=2026,
                    before=date(2026, 11, 19),
                    page_limit=1,
                    authorized=True,
                )
            transport.get.assert_called_once()
            self.assertNotIn("secret-response", str(raised.exception))
