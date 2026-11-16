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
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from fifth_pick.models import Category, Direction, Platform
from fifth_pick.receipts import redact_text
from fifth_pick.sources.base import (
    BoardProvenance,
    BudgetExceededError,
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
    estimate_odds_cost,
    parse_quota_headers,
)
from fifth_pick.sources.transport import HttpResponse, Transport

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


def odds_url(event_id: str, config: OddsApiSourceConfig) -> str:
    """The per-event odds endpoint. Bookmakers are explicit; regions are omitted."""

    if not isinstance(event_id, str) or not event_id.strip():
        raise SourceError("event_id must be a non-empty string")
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

    def fetch_board(self, *, live_authorized: bool, budget: QuotaBudget) -> SourceBoard:
        """Retrieve the board, or fail closed before spending credits."""

        if live_authorized is not True:
            raise LiveAuthorizationError("live retrieval requires explicit authorization")
        if not isinstance(budget, QuotaBudget):
            raise SourceError("budget must be a QuotaBudget")

        api_key = self._read_api_key()
        request_timestamp = self._clock()

        events_response = self._get(events_url(), api_key)
        events_payload = _parse_json(events_response, "events")
        headers = self._parse_event_headers(events_payload)
        quota = parse_quota_headers(events_response.headers)

        if quota.exhausted:
            raise QuotaExhaustedError("the source reports no remaining quota")

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
        retrieved_at = request_timestamp

        for index, header in enumerate(headers):
            remaining_events = len(headers) - index
            if quota.remaining is not None and quota.remaining < (
                remaining_events * len(self._config.markets)
            ):
                raise QuotaExhaustedError(
                    "the source reports insufficient remaining quota for the remaining events"
                )
            url = odds_url(header.event_id, self._config)
            response = self._get(url, api_key)
            retrieved_at = self._clock()
            raw_bodies.append((header.event_id, response.body))
            latest = parse_quota_headers(response.headers)
            if latest.has_any:
                quota = latest
            outcomes = self._parse_odds(response, header.event_id)
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
        return SourceBoard(provenance=provenance, events=tuple(events))

    def _read_api_key(self) -> str:
        value = self._environ.get(API_KEY_ENV_VAR)
        if not isinstance(value, str) or not value.strip():
            raise MissingApiKeyError(f"{API_KEY_ENV_VAR} is not set in the environment")
        return value

    def _get(self, url: str, api_key: str) -> HttpResponse:
        response = self._transport.get(url, {"x-api-key": api_key, "Accept": "application/json"})
        self._raise_for_status(response)
        return response

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
            if not isinstance(event_id, str) or not event_id.strip():
                raise MalformedPayloadError(f"event {index} is missing a valid id")
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

    def _parse_odds(self, response: HttpResponse, event_id: str) -> tuple[_RawOutcome, ...]:
        payload = _parse_json(response, f"odds for {event_id}")
        if not isinstance(payload, dict):
            raise MalformedPayloadError(f"odds payload for {event_id} must be a JSON object")
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
                outcomes.extend(self._parse_market(market, platform, event_id))
        return tuple(outcomes)

    def _parse_market(
        self, market: object, platform: Platform, event_id: str
    ) -> tuple[_RawOutcome, ...]:
        if not isinstance(market, dict):
            raise MalformedPayloadError(f"odds payload for {event_id} has a malformed market")
        market_key = market.get("key")
        category = normalize_market(market_key) if isinstance(market_key, str) else None
        if category is None:
            return ()
        last_update = _parse_datetime(market.get("last_update"), f"market {market_key} last_update")
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
