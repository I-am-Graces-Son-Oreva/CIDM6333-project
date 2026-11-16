"""Synthetic offline fixtures for M4 tests. Never touches the network.

These fixtures are hand-written and deterministic. They are not captured live evidence and
must never be presented as such.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from fifth_pick.sources.base import MalformedPayloadError, SourceError
from fifth_pick.sources.odds_api import (
    OddsApiSourceConfig,
    events_url,
    odds_url,
)
from fifth_pick.sources.transport import HttpResponse, TransportError

FIXTURE_LABEL: Final[str] = "synthetic-fixture"
_EVENTS_FILENAME: Final[str] = "events.json"
_ODDS_PREFIX: Final[str] = "odds-"
DEFAULT_QUOTA_HEADERS: Final[Mapping[str, str]] = {
    "x-requests-remaining": "495",
    "x-requests-used": "5",
    "x-requests-last": "5",
}


class FixtureTransport:
    """Serve the two approved endpoints from synthetic bodies. Never network."""

    def __init__(
        self,
        *,
        events_body: bytes,
        odds_bodies: Mapping[str, bytes],
        config: OddsApiSourceConfig | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._config = OddsApiSourceConfig() if config is None else config
        self._events_body = events_body
        self._odds_bodies = dict(odds_bodies)
        self._headers = dict(DEFAULT_QUOTA_HEADERS if headers is None else headers)

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        if url == events_url():
            return HttpResponse(status=200, headers=self._headers, body=self._events_body)
        for event_id, body in self._odds_bodies.items():
            if url == odds_url(event_id, self._config):
                return HttpResponse(status=200, headers=self._headers, body=body)
        raise TransportError("no synthetic fixture matches the requested URL")


def load_board_fixture(directory: str | Path) -> FixtureTransport:
    """Load ``events.json`` and per-event ``odds-<id>.json`` bodies from a directory."""

    root = Path(directory)
    events_path = root / _EVENTS_FILENAME
    try:
        events_body = events_path.read_bytes()
    except FileNotFoundError as exc:
        raise SourceError(f"missing fixture: {events_path}") from exc
    try:
        events = json.loads(events_body)
    except json.JSONDecodeError as exc:
        raise MalformedPayloadError(f"{events_path} is not valid JSON") from exc
    if not isinstance(events, list):
        raise MalformedPayloadError(f"{events_path} must be a JSON array")

    odds_bodies: dict[str, bytes] = {}
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("id"), str):
            raise MalformedPayloadError(f"{events_path} has an event without a valid id")
        event_id = event["id"]
        odds_path = root / f"{_ODDS_PREFIX}{event_id}.json"
        try:
            odds_bodies[event_id] = odds_path.read_bytes()
        except FileNotFoundError as exc:
            raise SourceError(f"missing fixture: {odds_path}") from exc

    return FixtureTransport(events_body=events_body, odds_bodies=odds_bodies)
