"""HTTP transport boundary for the source adapter.

The client depends only on the ``Transport`` protocol. Tests inject a fake transport and
never touch the network. ``UrllibTransport`` exists for explicit live use and is never
constructed by default.
"""

import errno
import os
import socket
import ssl
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from fifth_pick.sources.base import EvidenceMode, SourceError

DEFAULT_TIMEOUT_SECONDS: Final[float] = 10.0
_MACOS_CA_BUNDLE = Path("/etc/ssl/cert.pem")


def _macos_https_handler() -> urllib.request.HTTPSHandler | None:
    """Use macOS roots when framework Python lacks a default trust path."""
    if sys.platform != "darwin" or not _MACOS_CA_BUNDLE.is_file():
        return None
    paths = ssl.get_default_verify_paths()
    if (
        paths.cafile
        or paths.capath
        or paths.openssl_cafile_env in os.environ
        or paths.openssl_capath_env in os.environ
    ):
        return None
    return urllib.request.HTTPSHandler(
        context=ssl.create_default_context(cafile=str(_MACOS_CA_BUNDLE))
    )


class TransportError(SourceError):
    """Raised when a transport cannot complete a request."""

    @property
    def category(self) -> str:
        """Classify the chained exception using only fixed, safe labels."""
        cause = self.__cause__
        if isinstance(cause, urllib.error.URLError):
            cause = cause.reason
        if isinstance(cause, socket.gaierror):
            return "dns_resolution"
        if isinstance(cause, ssl.SSLCertVerificationError):
            return "tls_certificate_validation"
        if isinstance(cause, ssl.SSLError):
            return "tls_error"
        if isinstance(cause, TimeoutError):
            return "timeout"
        if isinstance(cause, ConnectionRefusedError):
            return "connection_refused"
        if isinstance(cause, ConnectionResetError):
            return "connection_reset"
        if isinstance(cause, OSError):
            if cause.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH):
                return "network_unreachable"
            # http.client signals an unsuccessful HTTP CONNECT via a plain OSError.
            if str(cause).startswith("Tunnel connection failed:"):
                return "proxy_tunnel"
            return "os_error"
        return "url_error" if isinstance(self.__cause__, urllib.error.URLError) else "unknown"


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

    evidence_mode = EvidenceMode.LIVE

    def __init__(self, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise TransportError("timeout must be a positive number")
        self._timeout = float(timeout)

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        try:
            https_handler = _macos_https_handler() if url.startswith("https://") else None
            redirects = _NoRedirectHandler()
            opener = urllib.request.build_opener(
                *((redirects,) if https_handler is None else (redirects, https_handler))
            )
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
