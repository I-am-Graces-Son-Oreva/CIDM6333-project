import inspect
import json
import unittest
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fifth_pick.models import Category, Direction, Platform
from fifth_pick.receipts import REDACTION_MARKER, redact_text
from fifth_pick.sources import odds_api
from fifth_pick.sources.base import (
    BudgetExceededError,
    LiveAuthorizationError,
    MalformedPayloadError,
    MissingApiKeyError,
    QuotaExhaustedError,
    SourceBoard,
    SourceError,
    UnauthorizedResponseError,
)
from fifth_pick.sources.fixtures import FIXTURE_LABEL, load_board_fixture
from fifth_pick.sources.normalize import MARKET_TO_CATEGORY, normalize_market
from fifth_pick.sources.odds_api import (
    API_KEY_ENV_VAR,
    APPROVED_BOOKMAKERS,
    APPROVED_MARKETS,
    APPROVED_REGION,
    SOURCE_ID,
    OddsApiClient,
    OddsApiSourceConfig,
    events_url,
    odds_url,
)
from fifth_pick.sources.quota import QuotaBudget, QuotaSnapshot
from fifth_pick.sources.transport import HttpResponse, Transport, TransportError

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "odds_api"
SECRET = "odds-secret-123"
NOW = datetime(2026, 11, 15, 17, 0, tzinfo=UTC)
QUOTA_HEADERS = {
    "x-requests-remaining": "495",
    "x-requests-used": "5",
    "x-requests-last": "5",
}


class FakeTransport:
    """Records requests and returns preloaded responses. It never touches the network."""

    def __init__(self, responses: dict[str, HttpResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, Mapping[str, str]]] = []

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.calls.append((url, dict(headers)))
        if url not in self.responses:
            raise TransportError(f"no fake response for {url}")
        return self.responses[url]


def fixture_responses(config: OddsApiSourceConfig | None = None) -> dict[str, HttpResponse]:
    config = config or OddsApiSourceConfig()
    events_body = (FIXTURE_DIR / "events.json").read_bytes()
    responses = {events_url(): HttpResponse(status=200, headers=QUOTA_HEADERS, body=events_body)}
    for event in json.loads(events_body):
        event_id = event["id"]
        body = (FIXTURE_DIR / f"odds-{event_id}.json").read_bytes()
        responses[odds_url(event_id, config)] = HttpResponse(
            status=200,
            headers=QUOTA_HEADERS,
            body=body,
        )
    return responses


def make_client(
    transport: Transport,
    *,
    environ: dict[str, str] | None = None,
    config: OddsApiSourceConfig | None = None,
) -> OddsApiClient:
    return OddsApiClient(
        transport=transport,
        environ={API_KEY_ENV_VAR: SECRET} if environ is None else environ,
        config=config,
        clock=lambda: NOW,
    )


def fetch_fixture_board(transport: Transport, *, credits: int = 100) -> SourceBoard:
    return make_client(transport).fetch_board(
        live_authorized=True,
        budget=QuotaBudget(credits=credits),
    )


class ApprovedConstantsTests(unittest.TestCase):
    def test_us_dfs_markets_are_exact(self) -> None:
        self.assertEqual(APPROVED_REGION, "us_dfs")
        self.assertEqual(APPROVED_BOOKMAKERS, ("prizepicks", "underdog"))
        self.assertEqual(
            APPROVED_MARKETS,
            (
                "player_points",
                "player_assists",
                "player_rebounds",
                "player_points_rebounds_assists",
                "player_rebounds_assists",
            ),
        )
        self.assertEqual(set(APPROVED_MARKETS), set(MARKET_TO_CATEGORY))
        self.assertEqual(SOURCE_ID, "the-odds-api-us-dfs")

    def test_threes_market_is_rejected(self) -> None:
        self.assertNotIn("player_threes", APPROVED_MARKETS)
        self.assertIsNone(normalize_market("player_threes"))

    def test_events_url_is_documented_endpoint(self) -> None:
        self.assertEqual(
            events_url(),
            "https://api.the-odds-api.com/v4/sports/basketball_nba/events",
        )

    def test_odds_url_uses_bookmakers_and_omits_regions(self) -> None:
        url = odds_url("evt-1", OddsApiSourceConfig())
        query = parse_qs(urlparse(url).query)

        self.assertEqual(
            urlparse(url).path,
            "/v4/sports/basketball_nba/events/evt-1/odds",
        )
        self.assertEqual(query["bookmakers"], ["prizepicks,underdog"])
        self.assertEqual(query["markets"], [",".join(APPROVED_MARKETS)])
        self.assertNotIn("regions", query)
        self.assertNotIn("apiKey", query)
        self.assertNotIn("api_key", query)


class SourceConfigTests(unittest.TestCase):
    def test_default_config_matches_approved_constants(self) -> None:
        config = OddsApiSourceConfig()

        self.assertEqual(config.region, APPROVED_REGION)
        self.assertEqual(config.bookmakers, APPROVED_BOOKMAKERS)
        self.assertEqual(config.markets, APPROVED_MARKETS)

    def test_non_approved_markets_fail_closed(self) -> None:
        for markets in (
            ("player_points",),
            APPROVED_MARKETS + ("player_threes",),
            ("player_threes",),
        ):
            with self.subTest(markets=markets), self.assertRaises(SourceError):
                OddsApiSourceConfig(markets=markets)

    def test_non_approved_bookmakers_fail_closed(self) -> None:
        with self.assertRaises(SourceError):
            OddsApiSourceConfig(bookmakers=("prizepicks",))

    def test_non_approved_region_fails_closed(self) -> None:
        with self.assertRaises(SourceError):
            OddsApiSourceConfig(region="us")


class LiveAuthorizationTests(unittest.TestCase):
    def test_live_authorization_required(self) -> None:
        transport = FakeTransport(fixture_responses())

        with self.assertRaises(LiveAuthorizationError):
            make_client(transport).fetch_board(
                live_authorized=False,
                budget=QuotaBudget(credits=100),
            )

        self.assertEqual(transport.calls, [])

    def test_live_mode_is_not_used_by_tests(self) -> None:
        signature = inspect.signature(OddsApiClient.__init__)
        transport_parameter = signature.parameters["transport"]

        self.assertIs(transport_parameter.default, inspect.Parameter.empty)
        self.assertFalse(hasattr(odds_api, "DEFAULT_CLIENT"))
        self.assertFalse(hasattr(odds_api, "default_client"))


class ApiKeyTests(unittest.TestCase):
    def test_missing_api_key_fails_without_echo(self) -> None:
        transport = FakeTransport(fixture_responses())

        with self.assertRaises(MissingApiKeyError) as context:
            make_client(transport, environ={}).fetch_board(
                live_authorized=True,
                budget=QuotaBudget(credits=100),
            )

        self.assertEqual(transport.calls, [])
        self.assertNotIn(SECRET, str(context.exception))

    def test_blank_api_key_fails_closed(self) -> None:
        transport = FakeTransport(fixture_responses())

        with self.assertRaises(MissingApiKeyError):
            make_client(transport, environ={API_KEY_ENV_VAR: "   "}).fetch_board(
                live_authorized=True,
                budget=QuotaBudget(credits=100),
            )

        self.assertEqual(transport.calls, [])

    def test_x_api_key_header_is_used(self) -> None:
        transport = FakeTransport(fixture_responses())

        fetch_fixture_board(transport)

        self.assertTrue(transport.calls)
        for _url, headers in transport.calls:
            self.assertEqual(headers.get("x-api-key"), SECRET)

    def test_no_request_url_contains_the_key(self) -> None:
        transport = FakeTransport(fixture_responses())

        fetch_fixture_board(transport)

        for url, _headers in transport.calls:
            self.assertNotIn(SECRET, url)
            self.assertNotIn("apiKey", url)
            self.assertNotIn("api_key", url)

    def test_url_redaction_removes_key(self) -> None:
        url = (
            "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
            f"?apiKey={SECRET}&markets=player_points"
        )

        redacted = redact_text(url, [SECRET])

        self.assertNotIn(SECRET, redacted)
        self.assertIn(REDACTION_MARKER, redacted)

    def test_unauthorized_response_does_not_echo_key(self) -> None:
        transport = FakeTransport(
            {
                events_url(): HttpResponse(
                    status=401,
                    headers={},
                    body=b'{"message":"Invalid API key"}',
                )
            }
        )

        with self.assertRaises(UnauthorizedResponseError) as context:
            fetch_fixture_board(transport)

        self.assertNotIn(SECRET, str(context.exception))


class BoardRetrievalTests(unittest.TestCase):
    def test_fixture_board_is_retrieved_offline(self) -> None:
        transport = FakeTransport(fixture_responses())

        board = fetch_fixture_board(transport)

        self.assertEqual(len(board.events), 2)
        self.assertEqual(len(transport.calls), 3)
        self.assertEqual(transport.calls[0][0], events_url())

    def test_provenance_has_required_fields(self) -> None:
        board = fetch_fixture_board(FakeTransport(fixture_responses()))
        provenance = board.provenance

        self.assertEqual(provenance.source_id, SOURCE_ID)
        self.assertEqual(provenance.region, APPROVED_REGION)
        self.assertEqual(provenance.bookmakers, APPROVED_BOOKMAKERS)
        self.assertEqual(provenance.markets, APPROVED_MARKETS)
        self.assertEqual(provenance.request_timestamp, NOW)
        self.assertEqual(provenance.retrieved_at, NOW)
        self.assertEqual(provenance.source_update_time, datetime(2026, 11, 15, 17, 5, tzinfo=UTC))
        self.assertEqual(len(provenance.payload_sha256), 64)
        int(provenance.payload_sha256, 16)
        self.assertNotIn("apiKey", provenance.request_url)

    def test_platform_observations_remain_separate(self) -> None:
        board = fetch_fixture_board(FakeTransport(fixture_responses()))
        projections = board.projections

        self.assertTrue(any(p.platform is Platform.PRIZEPICKS for p in projections))
        self.assertTrue(any(p.platform is Platform.UNDERDOG for p in projections))

        luka_assists = [
            projection
            for projection in projections
            if projection.provider_player_name == "Luka Doncic"
            and projection.category is Category.ASSISTS
            and projection.direction is Direction.HIGHER
        ]
        self.assertEqual(len(luka_assists), 2)
        self.assertEqual(
            {projection.platform for projection in luka_assists},
            {Platform.PRIZEPICKS, Platform.UNDERDOG},
        )
        self.assertEqual(sorted(projection.projection for projection in luka_assists), [8.5, 9.0])

    def test_alternate_markets_are_not_requested(self) -> None:
        transport = FakeTransport(fixture_responses())

        fetch_fixture_board(transport)

        odds_calls = [url for url, _headers in transport.calls if url != events_url()]
        self.assertEqual(len(odds_calls), 2)
        for url in odds_calls:
            query = parse_qs(urlparse(url).query)
            requested = query["markets"][0].split(",")
            self.assertEqual(requested, list(APPROVED_MARKETS))
            for forbidden in ("player_threes", "player_points_rebounds", "player_steals"):
                self.assertNotIn(forbidden, requested)

    def test_unapproved_market_in_payload_is_not_projected(self) -> None:
        board = fetch_fixture_board(FakeTransport(fixture_responses()))

        self.assertNotIn(
            Category.THREE_POINT_ATTEMPTS,
            {projection.category for projection in board.projections},
        )

    def test_over_and_under_map_to_directions(self) -> None:
        board = fetch_fixture_board(FakeTransport(fixture_responses()))

        directions = {projection.direction for projection in board.projections}
        self.assertEqual(directions, {Direction.HIGHER, Direction.LOWER})

    def test_empty_events_board_costs_nothing(self) -> None:
        transport = FakeTransport(
            {events_url(): HttpResponse(status=200, headers=QUOTA_HEADERS, body=b"[]")}
        )

        board = fetch_fixture_board(transport, credits=1)

        self.assertEqual(board.events, ())
        self.assertEqual(len(transport.calls), 1)


class QuotaControlTests(unittest.TestCase):
    def test_quota_headers_are_recorded(self) -> None:
        board = fetch_fixture_board(FakeTransport(fixture_responses()))

        self.assertEqual(board.provenance.quota, QuotaSnapshot(remaining=495, used=5, last=5))

    def test_quota_budget_exhaustion_blocks_request(self) -> None:
        transport = FakeTransport(fixture_responses())

        with self.assertRaises(BudgetExceededError):
            fetch_fixture_board(transport, credits=9)

        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0][0], events_url())

    def test_budget_equal_to_estimate_is_allowed(self) -> None:
        transport = FakeTransport(fixture_responses())

        board = fetch_fixture_board(transport, credits=10)

        self.assertEqual(len(board.events), 2)
        self.assertEqual(len(transport.calls), 3)

    def test_quota_exhaustion_fails_closed_before_odds(self) -> None:
        events_body = (FIXTURE_DIR / "events.json").read_bytes()
        transport = FakeTransport(
            {
                events_url(): HttpResponse(
                    status=200,
                    headers={
                        "x-requests-remaining": "0",
                        "x-requests-used": "500",
                        "x-requests-last": "0",
                    },
                    body=events_body,
                )
            }
        )

        with self.assertRaises(QuotaExhaustedError):
            fetch_fixture_board(transport, credits=100)

        self.assertEqual(len(transport.calls), 1)

    def test_reported_remaining_below_estimate_fails_closed_before_odds(self) -> None:
        config = OddsApiSourceConfig()
        responses = fixture_responses(config)
        events_response = responses[events_url()]
        responses[events_url()] = HttpResponse(
            status=events_response.status,
            headers={
                **events_response.headers,
                "x-requests-remaining": "1",
                "x-requests-used": "499",
                "x-requests-last": "0",
            },
            body=events_response.body,
        )
        transport = FakeTransport(responses)

        with self.assertRaises(QuotaExhaustedError):
            fetch_fixture_board(transport, credits=10)

        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0][0], events_url())

    def test_reported_remaining_below_next_event_fails_closed_before_odds(self) -> None:
        config = OddsApiSourceConfig()
        responses = fixture_responses(config)
        events_body = responses[events_url()].body
        event_ids = [event["id"] for event in json.loads(events_body)]
        self.assertEqual(len(event_ids), 2)
        first_event = event_ids[0]
        first_odds_response = responses[odds_url(first_event, config)]
        responses[odds_url(first_event, config)] = HttpResponse(
            status=first_odds_response.status,
            headers={
                **first_odds_response.headers,
                "x-requests-remaining": "1",
                "x-requests-used": "499",
                "x-requests-last": "5",
            },
            body=first_odds_response.body,
        )
        transport = FakeTransport(responses)

        with self.assertRaises(QuotaExhaustedError):
            fetch_fixture_board(transport, credits=10)

        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(transport.calls[0][0], events_url())
        self.assertEqual(transport.calls[1][0], odds_url(first_event, config))


class MalformedPayloadTests(unittest.TestCase):
    def test_non_list_events_payload_fails_closed(self) -> None:
        transport = FakeTransport(
            {events_url(): HttpResponse(status=200, headers=QUOTA_HEADERS, body=b'{"nope": true}')}
        )

        with self.assertRaises(MalformedPayloadError):
            fetch_fixture_board(transport)

    def test_event_without_id_fails_closed(self) -> None:
        body = json.dumps([{"sport_key": "basketball_nba"}]).encode("utf-8")
        transport = FakeTransport(
            {events_url(): HttpResponse(status=200, headers=QUOTA_HEADERS, body=body)}
        )

        with self.assertRaises(MalformedPayloadError):
            fetch_fixture_board(transport)

    def test_non_list_bookmakers_fails_closed(self) -> None:
        events_body = (FIXTURE_DIR / "events.json").read_bytes()
        responses = {
            events_url(): HttpResponse(status=200, headers=QUOTA_HEADERS, body=events_body)
        }
        for event in json.loads(events_body):
            responses[odds_url(event["id"], OddsApiSourceConfig())] = HttpResponse(
                status=200,
                headers=QUOTA_HEADERS,
                body=b'{"bookmakers": "nope"}',
            )
        transport = FakeTransport(responses)

        with self.assertRaises(MalformedPayloadError):
            fetch_fixture_board(transport)

    def test_non_json_odds_body_fails_closed(self) -> None:
        events_body = (FIXTURE_DIR / "events.json").read_bytes()
        responses = {
            events_url(): HttpResponse(status=200, headers=QUOTA_HEADERS, body=events_body)
        }
        for event in json.loads(events_body):
            responses[odds_url(event["id"], OddsApiSourceConfig())] = HttpResponse(
                status=200,
                headers=QUOTA_HEADERS,
                body=b"not json",
            )
        transport = FakeTransport(responses)

        with self.assertRaises(MalformedPayloadError):
            fetch_fixture_board(transport)


class FixtureTransportTests(unittest.TestCase):
    def test_fixture_label_is_synthetic(self) -> None:
        self.assertEqual(FIXTURE_LABEL, "synthetic-fixture")

    def test_fixture_transport_serves_the_board(self) -> None:
        transport = load_board_fixture(FIXTURE_DIR)

        board = fetch_fixture_board(transport)

        self.assertEqual(len(board.events), 2)

    def test_fixture_transport_never_hits_the_network(self) -> None:
        transport = load_board_fixture(FIXTURE_DIR)

        with self.assertRaises(TransportError):
            transport.get("https://example.test/not-a-fixture", {})


if __name__ == "__main__":
    unittest.main()
