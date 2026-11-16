"""HTTP transport boundary for the source adapter.

The client depends only on the ``Transport`` protocol. Tests inject a fake transport and
never touch the network. ``UrllibTransport`` exists for explicit live use and is never
constructed by default.
"""

import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from fifth_pick.sources.base import SourceError

DEFAULT_TIMEOUT_SECONDS: Final[float] = 10.0


class TransportError(SourceError):
    """Raised when a transport cannot complete a request."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so credential headers stay on the original request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """A raw HTTP response: status, headers, and body bytes."""

    status: int
    headers: Mapping[str, str]
    body: bytes


class Transport(Protocol):
    """The minimal HTTP boundary the source client depends on."""

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        """Perform a GET request and return the raw response."""


class UrllibTransport:
    """Live HTTP transport using the standard library.

    Construct this explicitly and only with separate live authorization. It performs a
    real network request and must never be a default.
    """

    def __init__(self, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise TransportError("timeout must be a positive number")
        self._timeout = float(timeout)

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        try:
            opener = urllib.request.build_opener(_NoRedirectHandler())
            with opener.open(request, timeout=self._timeout) as response:
                return HttpResponse(
                    status=int(response.status),
                    headers=dict(response.headers),
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            return HttpResponse(
                status=int(exc.code),
                headers=dict(exc.headers or {}),
                body=exc.read(),
            )
        except (urllib.error.URLError, OSError) as exc:
            raise TransportError(f"transport failure: {type(exc).__name__}") from exc
