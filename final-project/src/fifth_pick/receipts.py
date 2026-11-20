"""Appendable receipts and centralized secret redaction."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from fifth_pick.errors import ReceiptError

REDACTION_MARKER: Final[str] = "[REDACTED]"
SENSITIVE_QUERY_PARAMETERS: Final[frozenset[str]] = frozenset(
    {
        "access_token",
        "api-key",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "client_secret",
        "key",
        "password",
        "secret",
        "sig",
        "signature",
        "token",
    }
)
_URL_PATTERN: Final[re.Pattern[str]] = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def _normalize_secrets(secrets: Iterable[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for secret in secrets:
        if not isinstance(secret, str):
            raise ReceiptError("secrets must be strings")
        if secret:
            normalized.add(secret)
    return tuple(sorted(normalized, key=len, reverse=True))


def _redact_url(url: str) -> str:
    before_fragment, has_fragment, fragment = url.partition("#")
    base, has_query, query = before_fragment.partition("?")
    if not has_query:
        return url

    redacted_pairs: list[str] = []
    for pair in query.split("&"):
        name, has_value, _value = pair.partition("=")
        if has_value and name.lower() in SENSITIVE_QUERY_PARAMETERS:
            redacted_pairs.append(f"{name}={REDACTION_MARKER}")
        else:
            redacted_pairs.append(pair)

    redacted = f"{base}?{'&'.join(redacted_pairs)}"
    if has_fragment:
        redacted = f"{redacted}#{fragment}"
    return redacted


def redact_text(value: str, secrets: Iterable[str] = ()) -> str:
    """Redact supplied exact secrets and sensitive URL query values."""

    if not isinstance(value, str):
        raise ReceiptError("receipt values must be strings")

    redacted = _URL_PATTERN.sub(lambda match: _redact_url(match.group(0)), value)
    for secret in _normalize_secrets(secrets):
        redacted = redacted.replace(secret, REDACTION_MARKER)
    return redacted


def _require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ReceiptError(f"{field} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class Receipt:
    """One JSON Lines receipt with an explicit idempotency key."""

    timestamp: str
    event: str
    result: str
    subject: str
    source: str
    reason: str | None
    run_id: str
    event_key: str

    def __post_init__(self) -> None:
        for field in ("timestamp", "event", "result", "subject", "source", "run_id", "event_key"):
            _require_text(getattr(self, field), field)
        if self.reason is not None:
            _require_text(self.reason, "reason")

    def to_dict(self) -> dict[str, str | None]:
        return {
            "timestamp": self.timestamp,
            "event": self.event,
            "result": self.result,
            "subject": self.subject,
            "source": self.source,
            "reason": self.reason,
            "run_id": self.run_id,
            "event_key": self.event_key,
        }

    def redacted(self, secrets: Iterable[str] = ()) -> "Receipt":
        normalized_secrets = _normalize_secrets(secrets)
        return Receipt(
            timestamp=redact_text(self.timestamp, normalized_secrets),
            event=redact_text(self.event, normalized_secrets),
            result=redact_text(self.result, normalized_secrets),
            subject=redact_text(self.subject, normalized_secrets),
            source=redact_text(self.source, normalized_secrets),
            reason=(None if self.reason is None else redact_text(self.reason, normalized_secrets)),
            run_id=redact_text(self.run_id, normalized_secrets),
            event_key=redact_text(self.event_key, normalized_secrets),
        )
