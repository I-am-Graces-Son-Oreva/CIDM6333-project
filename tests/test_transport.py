import errno
import socket
import ssl
import unittest
from unittest import mock
from urllib.error import URLError
from urllib.request import Request

from fifth_pick.sources.base import EvidenceMode
from fifth_pick.sources.transport import (
    HttpResponse,
    TransportError,
    UrllibTransport,
    _macos_https_handler,
)


class RedirectHandlingTests(unittest.TestCase):
    def test_macos_fallback_preserves_verification_and_respects_overrides(self) -> None:
        import os

        paths = ssl.DefaultVerifyPaths("", "", "SSL_CERT_FILE", "", "SSL_CERT_DIR", "")
        verified_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with (
            mock.patch("fifth_pick.sources.transport.sys.platform", "darwin"),
            mock.patch("fifth_pick.sources.transport._MACOS_CA_BUNDLE") as bundle,
            mock.patch("ssl.get_default_verify_paths", return_value=paths),
            mock.patch(
                "ssl.create_default_context",
                return_value=verified_context,
            ) as context,
            mock.patch("urllib.request.HTTPSHandler") as https_handler,
            mock.patch.dict(os.environ, clear=True),
        ):
            bundle.is_file.return_value = True
            bundle.__str__.return_value = "/approved/ca.pem"
            self.assertIs(_macos_https_handler(), https_handler.return_value)
            https_handler.assert_called_once_with(context=verified_context)
            self.assertEqual(verified_context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(verified_context.check_hostname)
            context.assert_called_once_with(cafile="/approved/ca.pem")
            with mock.patch.dict(os.environ, {"SSL_CERT_FILE": "/operator/bundle.pem"}):
                self.assertIsNone(_macos_https_handler())

    def test_transport_classifies_wrapped_network_errors_without_details(self) -> None:
        secret = "synthetic-proxy-secret"
        cases = (
            (socket.gaierror(socket.EAI_NONAME, secret), "dns_resolution"),
            (ssl.SSLCertVerificationError(1, secret), "tls_certificate_validation"),
            (ssl.SSLError(1, secret), "tls_error"),
            (TimeoutError(secret), "timeout"),
            (ConnectionRefusedError(secret), "connection_refused"),
            (OSError(errno.ENETUNREACH, secret), "network_unreachable"),
            (OSError(f"Tunnel connection failed: 407 {secret}"), "proxy_tunnel"),
            (secret, "url_error"),
        )
        for reason, category in cases:
            with (
                self.subTest(category=category),
                mock.patch("urllib.request.build_opener") as build_opener,
                self.assertRaises(TransportError) as raised,
            ):
                opener = build_opener.return_value
                opener.open.side_effect = URLError(reason)
                try:
                    UrllibTransport().get("https://api.example.test/events", {})
                finally:
                    opener.open.assert_called_once()
            self.assertEqual(raised.exception.category, category)
            self.assertNotIn(secret, str(raised.exception))

    def test_live_transport_is_marked_live_without_network_access(self) -> None:
        self.assertIs(UrllibTransport.evidence_mode, EvidenceMode.LIVE)

    def test_live_transport_rejects_redirect_without_forwarding_api_key(self) -> None:
        api_key = "test-api-key"
        start_url = "https://api.example.test/events"
        redirect_url = "https://other.example.test/collect"
        response = mock.MagicMock()
        response.status = 302
        response.headers = {"Location": redirect_url}
        response.read.return_value = b""
        response_context = mock.MagicMock()
        response_context.__enter__.return_value = response
        opener = mock.MagicMock()
        opener.open.return_value = response_context

        with (
            mock.patch("urllib.request.urlopen") as urlopen,
            mock.patch("urllib.request.build_opener", return_value=opener) as build_opener,
        ):
            urlopen.return_value = response_context
            result = UrllibTransport().get(start_url, {"x-api-key": api_key})

        self.assertEqual(result, HttpResponse(status=302, headers=response.headers, body=b""))
        urlopen.assert_not_called()
        build_opener.assert_called_once()
        redirect_handler = build_opener.call_args.args[0]
        request = opener.open.call_args.args[0]
        self.assertIsInstance(request, Request)
        self.assertEqual(request.get_header("X-api-key"), api_key)
        redirected_request = redirect_handler.redirect_request(
            request,
            None,
            302,
            "Found",
            response.headers,
            redirect_url,
        )
        self.assertIsNone(redirected_request)


if __name__ == "__main__":
    unittest.main()
