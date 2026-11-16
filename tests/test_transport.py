import unittest
from unittest import mock
from urllib.request import Request

from fifth_pick.sources.transport import HttpResponse, UrllibTransport


class RedirectHandlingTests(unittest.TestCase):
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
