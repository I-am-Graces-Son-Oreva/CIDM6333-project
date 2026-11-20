"""The Odds API ``us_dfs`` source adapter for PrizePicks and Underdog.

Only the approved region, bookmakers, and five live markets are ever requested. The two
platforms are kept separate. Retrieval is fail-closed: a missing key, an unauthorized
response, a malformed payload, quota exhaustion, or an over-budget estimate all stop the
run before any further call. Live retrieval requires explicit authorization and a positive
credit budget.
"""

import hashlib
import json
import math
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from fifth_pick.models import Category, Direction, Platform
from fifth_pick.receipts import redact_text
from fifth_pick.sources.base import (
    BoardProvenance,
    BudgetExceededError,
    EvidenceMode,
    LiveAuthorizationError,
    MalformedPayloadError,
    MissingApiKeyError,
    QuotaExhaustedError,
    SourceBoard,
    SourceError,
    SourceEvent,
    SourceProjection,
    UnauthorizedResponseError,
)
from fifth_pick.sources.normalize import normalize_direction, normalize_market
from fifth_pick.sources.quota import (
    QuotaBudget,
    QuotaSnapshot,
    estimate_odds_cost,
    parse_quota_headers,
)
from fifth_pick.sources.transport import HttpResponse, Transport

ProjectionFilter = Callable[[str, str, Category, Direction], bool]


class FreeQuotaVerificationError(SourceError):
    """The response did not establish a valid zero-credit request."""


BASE_URL: Final[str] = "https://api.the-odds-api.com/v4"
SPORT_KEY: Final[str] = "basketball_nba"
APPROVED_REGION: Final[str] = "us_dfs"
APPROVED_BOOKMAKERS: Final[tuple[str, ...]] = ("prizepicks", "underdog")
APPROVED_MARKETS: Final[tuple[str, ...]] = (
    "player_points",
    "player_assists",
    "player_rebounds",
    "player_points_rebounds_assists",
    "player_rebounds_assists",
)
API_KEY_ENV_VAR: Final[str] = "THE_ODDS_API_KEY"
SOURCE_ID: Final[str] = "the-odds-api-us-dfs"

_BOOKMAKER_TO_PLATFORM: Final[Mapping[str, Platform]] = {
    "prizepicks": Platform.PRIZEPICKS,
    "underdog": Platform.UNDERDOG,
}


@dataclass(frozen=True, slots=True)
class OddsApiSourceConfig:
    """The approved request shape. Any deviation fails closed."""

    region: str = APPROVED_REGION
    bookmakers: tuple[str, ...] = APPROVED_BOOKMAKERS
    markets: tuple[str, ...] = APPROVED_MARKETS

    def __post_init__(self) -> None:
        if self.region != APPROVED_REGION:
            raise SourceError(f"region must be {APPROVED_REGION!r}")
        if tuple(self.bookmakers) != APPROVED_BOOKMAKERS:
            raise SourceError("bookmakers must be exactly the approved platforms")
        if tuple(self.markets) != APPROVED_MARKETS:
            raise SourceError("markets must be exactly the approved five markets")


def events_url() -> str:
    """The quota-free events endpoint for the approved sport."""

    return f"{BASE_URL}/sports/{SPORT_KEY}/events"


def _transport_evidence_mode(transport: Transport) -> EvidenceMode:
    """Label only the built-in live and synthetic transports; custom transports stay unknown."""

    from fifth_pick.sources.fixtures import FixtureTransport
    from fifth_pick.sources.transport import UrllibTransport

    if type(transport) is UrllibTransport:
        return EvidenceMode.LIVE
    if type(transport) is FixtureTransport:
        return EvidenceMode.FIXTURE
    return EvidenceMode.UNKNOWN


def validate_event_id(event_id: str) -> None:
    if not isinstance(event_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", event_id) is None:
        raise SourceError("invalid provider event ID")


def odds_url(event_id: str, config: OddsApiSourceConfig) -> str:
    """The per-event odds endpoint. Bookmakers are explicit; regions are omitted."""

    validate_event_id(event_id)
    markets = ",".join(config.markets)
    bookmakers = ",".join(config.bookmakers)
    return (
        f"{BASE_URL}/sports/{SPORT_KEY}/events/{event_id}/odds"
        f"?markets={markets}&bookmakers={bookmakers}"
    )


@dataclass(frozen=True, slots=True)
class _EventHeader:
    event_id: str
    home_team: str
    away_team: str
    commence_time: datetime


@dataclass(frozen=True, slots=True)
class _RawOutcome:
    platform: Platform
    provider_player_name: str
    category: Category
    projection: float
    direction: Direction
    source_update_time: datetime


def _parse_datetime(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise MalformedPayloadError(f"{field} must be an ISO-8601 timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MalformedPayloadError(f"{field} is not a valid timestamp") from exc


def _parse_point(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MalformedPayloadError(f"{field} must be a finite number")
    if not math.isfinite(value):
        raise MalformedPayloadError(f"{field} must be a finite number")
    return float(value)


def _parse_json(response: HttpResponse, label: str) -> object:
    try:
        text = response.body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MalformedPayloadError(f"{label} payload is not valid UTF-8") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise MalformedPayloadError(f"{label} payload is not valid JSON") from exc


class OddsApiClient:
    """Fetch the approved board. Requires an injected transport and explicit live opt-in."""

    def __init__(
        self,
        *,
        transport: Transport,
        environ: Mapping[str, str] | None = None,
        config: OddsApiSourceConfig | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if transport is None:
            raise SourceError("an explicit transport is required")
        self._transport = transport
        self._environ: Mapping[str, str] = os.environ if environ is None else environ
        self._config = OddsApiSourceConfig() if config is None else config
        self._clock: Callable[[], datetime] = (
            (lambda: datetime.now(UTC)) if clock is None else clock
        )
        self._evidence_mode = _transport_evidence_mode(transport)

    @property
    def evidence_mode(self) -> EvidenceMode:
        return self._evidence_mode

    def fetch_board(
        self,
        *,
        live_authorized: bool,
        budget: QuotaBudget,
        event_id: str | None = None,
        retain_schedule: bool = False,
        select_event: Callable[[tuple[SourceEvent, ...]], str] | None = None,
        observe_response: Callable[[str, datetime, datetime, HttpResponse], None] | None = None,
        observe_request: Callable[[str, datetime], None] | None = None,
        projection_allowed: ProjectionFilter | None = None,
    ) -> SourceBoard:
        """Retrieve the board, or fail closed before spending credits."""

        if live_authorized is not True:
            raise LiveAuthorizationError("live retrieval requires explicit authorization")
        if not isinstance(budget, QuotaBudget):
            raise SourceError("budget must be a QuotaBudget")

        api_key = self._read_api_key()
        request_timestamp = self._clock()

        if select_event is not None and event_id is not None:
            raise SourceError("specify a fixed event or select one from discovery")
        if event_id is not None:
            validate_event_id(event_id)
        events_response, events_retrieved_at = self._get(
            events_url(), api_key, observe_response, observe_request
        )
        events_payload = _parse_json(events_response, "events")
        schedule = self._parse_event_headers(events_payload)
        if len({header.event_id for header in schedule}) != len(schedule):
            raise MalformedPayloadError("the event list contains duplicate identifiers")
        quota = parse_quota_headers(events_response.headers)
        if quota.exhausted:
            raise QuotaExhaustedError("the source reports no remaining quota")
        if select_event is not None:
            if quota.remaining is None or quota.remaining < len(self._config.markets):
                raise QuotaExhaustedError("discovery lacks quota for one selected event")
            if budget.credits < len(self._config.markets):
                raise BudgetExceededError("selected event is outside the credit budget")
            event_id = select_event(
                tuple(
                    SourceEvent(
                        header.event_id,
                        header.home_team,
                        header.away_team,
                        header.commence_time,
                        (),
                    )
                    for header in schedule
                )
            )
            validate_event_id(event_id)
        headers = tuple(header for header in schedule if event_id in (None, header.event_id))
        if event_id is not None and not headers:
            raise SourceError("the requested event is missing from the provider schedule")

        estimate = estimate_odds_cost(
            event_count=len(headers),
            market_count=len(self._config.markets),
        )
        if quota.remaining is not None and quota.remaining < estimate:
            raise QuotaExhaustedError(
                "the source reports insufficient remaining quota for the estimated board cost"
            )
        if estimate > budget.credits:
            raise BudgetExceededError(
                f"estimated {estimate} credits exceeds the authorized budget of {budget.credits}"
            )

        raw_bodies: list[tuple[str, bytes]] = [(events_url(), events_response.body)]
        events: list[SourceEvent] = []
        source_updates: list[datetime] = []
        retrieved_at = events_retrieved_at

        for index, header in enumerate(headers):
            remaining_events = len(headers) - index
            if quota.remaining is not None and quota.remaining < (
                remaining_events * len(self._config.markets)
            ):
                raise QuotaExhaustedError(
                    "the source reports insufficient remaining quota for the remaining events"
                )
            url = odds_url(header.event_id, self._config)
            response, retrieved_at = self._get(url, api_key, observe_response, observe_request)
            raw_bodies.append((header.event_id, response.body))
            latest = parse_quota_headers(response.headers)
            if latest.has_any:
                quota = latest
            outcomes = self._parse_odds(
                response,
                header.event_id,
                event_header=header if event_id is not None else None,
                projection_allowed=projection_allowed,
            )
            source_updates.extend(outcome.source_update_time for outcome in outcomes)
            events.append(
                SourceEvent(
                    event_id=header.event_id,
                    home_team=header.home_team,
                    away_team=header.away_team,
                    commence_time=header.commence_time,
                    projections=tuple(
                        SourceProjection(
                            platform=outcome.platform,
                            provider_player_name=outcome.provider_player_name,
                            category=outcome.category,
                            projection=outcome.projection,
                            direction=outcome.direction,
                            event_id=header.event_id,
                            source_update_time=outcome.source_update_time,
                            retrieved_at=retrieved_at,
                        )
                        for outcome in outcomes
                    ),
                )
            )

        if retain_schedule and event_id is not None:
            selected = events[0]
            events = [
                selected
                if header.event_id == selected.event_id
                else SourceEvent(
                    event_id=header.event_id,
                    home_team=header.home_team,
                    away_team=header.away_team,
                    commence_time=header.commence_time,
                    projections=(),
                )
                for header in schedule
            ]

        provenance = BoardProvenance(
            source_id=SOURCE_ID,
            region=self._config.region,
            bookmakers=self._config.bookmakers,
            markets=self._config.markets,
            request_timestamp=request_timestamp,
            retrieved_at=retrieved_at,
            source_update_time=max(source_updates) if source_updates else None,
            payload_sha256=self._hash_payload(raw_bodies),
            request_url=redact_text(events_url()),
            quota=quota,
        )
        object.__setattr__(provenance, "_evidence_mode", self._evidence_mode)
        return SourceBoard(provenance=provenance, events=tuple(events))

    def check_free_quota(self, *, authorized: bool = False) -> QuotaSnapshot:
        """Read quota headers from the documented quota-free events request."""
        _, quota = self.discover_free_events(authorized=authorized)
        return quota

    def discover_free_events(
        self,
        *,
        authorized: bool = False,
        observe_response: Callable[[str, datetime, datetime, HttpResponse], None] | None = None,
    ) -> tuple[tuple[SourceEvent, ...], QuotaSnapshot]:
        """Fetch only the free list and verify the provider recorded no charge."""
        if authorized is not True:
            raise LiveAuthorizationError("quota check requires explicit authorization")
        credential = self._read_api_key()
        response, _ = self._get(events_url(), credential, observe_response, None)
        quota = parse_quota_headers(response.headers)
        if quota.last != 0 or quota.remaining is None or quota.used is None:
            raise FreeQuotaVerificationError("provider response did not verify a free quota check")
        if quota.remaining < 0 or quota.used < 0:
            raise FreeQuotaVerificationError("provider returned invalid quota counters")
        headers = self._parse_event_headers(_parse_json(response, "events"))
        if len({item.event_id for item in headers}) != len(headers):
            raise MalformedPayloadError("duplicate event in free discovery")
        events = tuple(
            SourceEvent(item.event_id, item.home_team, item.away_team, item.commence_time, ())
            for item in headers
        )
        if any(
            not value.isprintable() or credential in value
            for event in events
            for value in (event.event_id, event.home_team, event.away_team)
        ):
            raise MalformedPayloadError("unsafe text in free discovery")
        return events, quota

    def require_credentials(self) -> None:
        """Check credential availability without exposing the key."""
        self._read_api_key()

    def _read_api_key(self) -> str:
        value = self._environ.get(API_KEY_ENV_VAR)
        if not isinstance(value, str) or not value.strip():
            raise MissingApiKeyError(f"{API_KEY_ENV_VAR} is not set in the environment")
        return value

    def _get(
        self,
        url: str,
        api_key: str,
        observe_response: Callable[[str, datetime, datetime, HttpResponse], None] | None,
        observe_request: Callable[[str, datetime], None] | None,
    ) -> tuple[HttpResponse, datetime]:
        requested_at = self._clock() if observe_response or observe_request else None
        if observe_request is not None and requested_at is not None:
            observe_request(url, requested_at)
        response = self._transport.get(url, {"x-api-key": api_key, "Accept": "application/json"})
        retrieved_at = self._clock()
        if observe_response is not None and requested_at is not None:
            observe_response(url, requested_at, retrieved_at, response)
        self._raise_for_status(response)
        return response, retrieved_at

    def _raise_for_status(self, response: HttpResponse) -> None:
        if response.status == 200:
            return
        message = f"the source returned HTTP {response.status}"
        if response.status in (401, 403):
            raise UnauthorizedResponseError(message)
        if response.status in (402, 429):
            raise QuotaExhaustedError(message)
        raise SourceError(message)

    def _parse_event_headers(self, payload: object) -> tuple[_EventHeader, ...]:
        if not isinstance(payload, list):
            raise MalformedPayloadError("events payload must be a JSON array")
        headers: list[_EventHeader] = []
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                raise MalformedPayloadError(f"event {index} must be a JSON object")
            event_id = item.get("id")
            home_team = item.get("home_team")
            away_team = item.get("away_team")
            if not isinstance(event_id, str):
                raise MalformedPayloadError(f"event {index} is missing a valid id")
            try:
                validate_event_id(event_id)
            except SourceError as exc:
                raise MalformedPayloadError(f"event {index} is missing a valid id") from exc
            if not isinstance(home_team, str) or not home_team.strip():
                raise MalformedPayloadError(f"event {event_id} is missing a valid home_team")
            if not isinstance(away_team, str) or not away_team.strip():
                raise MalformedPayloadError(f"event {event_id} is missing a valid away_team")
            headers.append(
                _EventHeader(
                    event_id=event_id,
                    home_team=home_team,
                    away_team=away_team,
                    commence_time=_parse_datetime(
                        item.get("commence_time"), f"event {event_id} commence_time"
                    ),
                )
            )
        return tuple(headers)

    def _parse_odds(
        self,
        response: HttpResponse,
        event_id: str,
        *,
        event_header: _EventHeader | None,
        projection_allowed: ProjectionFilter | None,
    ) -> tuple[_RawOutcome, ...]:
        payload = _parse_json(response, f"odds for {event_id}")
        if not isinstance(payload, dict):
            raise MalformedPayloadError(f"odds payload for {event_id} must be a JSON object")
        if event_header is not None and (
            payload.get("id") != event_id
            or _parse_datetime(payload.get("commence_time"), "odds event tipoff")
            != event_header.commence_time
            or payload.get("home_team") != event_header.home_team
            or payload.get("away_team") != event_header.away_team
        ):
            raise MalformedPayloadError("odds response identity differs from the selected event")
        bookmakers = payload.get("bookmakers")
        if not isinstance(bookmakers, list):
            raise MalformedPayloadError(
                f"odds payload for {event_id} must contain a bookmakers array"
            )

        outcomes: list[_RawOutcome] = []
        for bookmaker in bookmakers:
            if not isinstance(bookmaker, dict):
                raise MalformedPayloadError(
                    f"odds payload for {event_id} has a malformed bookmaker"
                )
            platform = _platform_for_bookmaker(bookmaker.get("key"))
            if platform is None:
                continue
            markets = bookmaker.get("markets")
            if not isinstance(markets, list):
                raise MalformedPayloadError(
                    f"bookmaker {bookmaker.get('key')!r} in {event_id} must contain a markets array"
                )
            for market in markets:
                outcomes.extend(self._parse_market(market, platform, event_id, projection_allowed))
        return tuple(outcomes)

    def _parse_market(
        self,
        market: object,
        platform: Platform,
        event_id: str,
        projection_allowed: ProjectionFilter | None,
    ) -> tuple[_RawOutcome, ...]:
        if not isinstance(market, dict):
            raise MalformedPayloadError(f"odds payload for {event_id} has a malformed market")
        market_key = market.get("key")
        category = normalize_market(market_key) if isinstance(market_key, str) else None
        if category is None:
            return ()
        last_update = None
        if projection_allowed is None:
            last_update = _parse_datetime(
                market.get("last_update"), f"market {market_key} last_update"
            )
        market_outcomes = market.get("outcomes")
        if not isinstance(market_outcomes, list):
            raise MalformedPayloadError(
                f"market {market_key} in {event_id} must contain an outcomes array"
            )
        parsed: list[_RawOutcome] = []
        for outcome in market_outcomes:
            if not isinstance(outcome, dict):
                raise MalformedPayloadError(f"market {market_key} has a malformed outcome")
            name = outcome.get("name")
            direction = normalize_direction(name) if isinstance(name, str) else None
            if direction is None:
                continue
            description = outcome.get("description")
            if not isinstance(description, str) or not description.strip():
                raise MalformedPayloadError(
                    f"market {market_key} outcome is missing a player description"
                )
            if projection_allowed is not None and not projection_allowed(
                event_id, description, category, direction
            ):
                continue
            if last_update is None:
                last_update = _parse_datetime(
                    market.get("last_update"), f"market {market_key} last_update"
                )
            parsed.append(
                _RawOutcome(
                    platform=platform,
                    provider_player_name=description,
                    category=category,
                    projection=_parse_point(outcome.get("point"), f"{description} point"),
                    direction=direction,
                    source_update_time=last_update,
                )
            )
        return tuple(parsed)

    @staticmethod
    def _hash_payload(raw_bodies: list[tuple[str, bytes]]) -> str:
        hasher = hashlib.sha256()
        for key, body in sorted(raw_bodies, key=lambda item: item[0]):
            hasher.update(key.encode("utf-8"))
            hasher.update(b"\n")
            hasher.update(body)
            hasher.update(b"\n")
        return hasher.hexdigest()


def _platform_for_bookmaker(key: object) -> Platform | None:
    if not isinstance(key, str):
        return None
    return _BOOKMAKER_TO_PLATFORM.get(key)
