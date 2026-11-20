"""Quota budget, header capture, and request-cost estimation for The Odds API."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from fifth_pick.errors import ValidationError

REMAINING_HEADER: Final[str] = "x-requests-remaining"
USED_HEADER: Final[str] = "x-requests-used"
LAST_HEADER: Final[str] = "x-requests-last"


class QuotaError(ValidationError):
    """Raised when quota headers or a budget are malformed."""


def header_value(headers: Mapping[str, str], name: str) -> str | None:
    """Return a case-insensitive header value, or None when absent."""

    lowered = name.lower()
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == lowered:
            return value
    return None


def _parse_header_int(headers: Mapping[str, str], name: str) -> int | None:
    value = header_value(headers, name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise QuotaError(f"{name} header must be a string")
    try:
        return int(value.strip())
    except ValueError as exc:
        raise QuotaError(f"{name} header is not an integer") from exc


@dataclass(frozen=True, slots=True)
class QuotaBudget:
    """An explicit, positive credit ceiling for one live retrieval."""

    credits: int

    def __post_init__(self) -> None:
        if isinstance(self.credits, bool) or not isinstance(self.credits, int):
            raise QuotaError("credits must be a positive integer")
        if self.credits <= 0:
            raise QuotaError("credits must be a positive integer")


@dataclass(frozen=True, slots=True)
class QuotaSnapshot:
    """The quota counters reported by The Odds API response headers."""

    remaining: int | None = None
    used: int | None = None
    last: int | None = None

    def __post_init__(self) -> None:
        for field in ("remaining", "used", "last"):
            value = getattr(self, field)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                raise QuotaError(f"{field} must be an integer or None")

    @property
    def has_any(self) -> bool:
        """True when at least one quota counter was reported."""

        return self.remaining is not None or self.used is not None or self.last is not None

    @property
    def exhausted(self) -> bool:
        """True only when the reported remaining credit count is zero."""

        return self.remaining == 0


def parse_quota_headers(headers: Mapping[str, str]) -> QuotaSnapshot:
    """Read the three documented quota counters from response headers."""

    if not isinstance(headers, Mapping):
        raise QuotaError("headers must be a mapping")
    return QuotaSnapshot(
        remaining=_parse_header_int(headers, REMAINING_HEADER),
        used=_parse_header_int(headers, USED_HEADER),
        last=_parse_header_int(headers, LAST_HEADER),
    )


def estimate_odds_cost(*, event_count: int, market_count: int) -> int:
    """Estimate odds-endpoint credits as one request per market per event.

    The Odds API charges one credit per market per event for the odds endpoint. The
    events endpoint is quota-free. The estimate is used to block a run before any
    odds call is made.
    """

    for field, value in (("event_count", event_count), ("market_count", market_count)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise QuotaError(f"{field} must be a non-negative integer")
    return event_count * market_count
