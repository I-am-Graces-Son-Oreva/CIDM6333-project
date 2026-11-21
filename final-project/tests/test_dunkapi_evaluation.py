"""Offline tests for the isolated DunkAPI evaluation."""

import hashlib
import http.client
import io
import json
import runpy
import socket
import ssl
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

run_evaluation = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/dunkapi_evaluation.py")
)["main"]

SCOPE = [
    "--player-id",
    "jayson-tatum",
    "--team-label",
    "BOS",
    "--identity-reference",
    "synthetic:roster-crosswalk",
    "--expected-provider-id",
    "6099",
    "--market",
    "POINTS",
    "--direction",
    "HIGHER",
    "--season-end-year",
    "2027",
]
SECRET = "credential-canary"
PRIVATE = "provider-private-message"


@dataclass(frozen=True)
class VerifyPaths:
    cafile: str | None = None
    capath: str | None = None
    openssl_cafile_env: str = "SSL_CERT_FILE"
    openssl_capath_env: str = "SSL_CERT_DIR"


MISSING_TRUST_PATHS = VerifyPaths()


def response(data, used, remaining, status=200):
    reply = Mock(status=status)
    reply.headers = http.client.HTTPMessage()
    reply.headers["X-Credits-Used"] = str(used)
    reply.headers["X-Credits-Remaining"] = str(remaining)
    reply.read.return_value = json.dumps({"data": data}).encode()
    return reply


def wire_response(body, *framing_headers):
    head = [
        b"HTTP/1.1 200 OK",
        b"X-Credits-Used: 1",
        b"X-Credits-Remaining: 10",
        *framing_headers,
    ]
    stream = io.BytesIO(b"\r\n".join(head) + b"\r\n\r\n" + body)
    reply = http.client.HTTPResponse(Mock(makefile=Mock(return_value=stream)))
    reply.begin()
    return reply


def identity():
    return {"players": [{"name": "Jayson Tatum", "player_id": "6099", "team": "BOS"}]}


def history():
    return {
        "player_id": "6099",
        "count": 8,
        "next_offset": None,
        "games": [
            {
                "game_id": str(i),
                "date": f"2026-11-{i:02}",
                "season": 2027,
                "season_type": 2,
                "opponent": "LAL",
                "home": True,
                "result": "W",
                "did_not_play": False,
                "pts": 25,
                "reb": 4,
                "ast": 6,
                "minutes": 30,
            }
            for i in range(1, 9)
        ],
    }


def boxscore():
    return {
        "game": {
            "game_id": "8",
            "season": 2027,
            "date": "2026-11-08",
            "status": "final",
            "home": {"team_id": "99"},
            "away": {"abbrev": "LAL"},
            "starts_at": "2026-11-08T19:00:00Z",
        },
        "players": [
            {
                "player_id": "6099",
                "team_id": "99",
                "did_not_play": False,
                "pts": 25,
                "reb": 4,
                "ast": 6,
                "minutes": 30,
            }
        ],
    }


class DunkEvaluationTests(unittest.TestCase):
    def run_harness(self, factory, *, args=None, credential=None):
        output, errors = io.StringIO(), io.StringIO()
        lookup = Mock(return_value=SECRET) if credential is None else credential
        with redirect_stdout(output), redirect_stderr(errors):
            code = run_evaluation(
                [*SCOPE, "--authorize-live-free-only", "11", "--cross-check-team-id", "99"]
                if args is None
                else args,
                credential=lookup,
                connection_factory=factory,
            )
        text = output.getvalue()
        self.assertNotIn(SECRET, text)
        self.assertNotIn(PRIVATE, text)
        self.assertEqual(errors.getvalue(), "")
        return code, [json.loads(line) for line in text.splitlines()]

    def test_refuses_unauthorized_run_before_credential_lookup(self):
        for args in ([], [*SCOPE, "--authorize-live-free-only", "5"], [SECRET]):
            with self.subTest(args=len(args)):
                lookup, factory = Mock(), Mock()
                code, _ = self.run_harness(factory, args=args, credential=lookup)
                self.assertEqual(code, 1)
                lookup.assert_not_called()
                factory.assert_not_called()

    def test_missing_credential_stops_before_connection(self):
        factory = Mock()
        code, records = self.run_harness(factory, credential=Mock(return_value=None))
        self.assertEqual(code, 1)
        self.assertEqual(records[-1]["error"], "credential_unavailable")
        factory.assert_not_called()

    def test_two_request_tatum_scope_and_explicit_retention(self):
        conn = Mock()
        reply = response(history(), 5, 0)
        conn.getresponse.side_effect = [response(identity(), 1, 5), reply]
        with TemporaryDirectory() as directory:
            archive = Path(directory) / "capture"
            code, records = self.run_harness(
                Mock(return_value=conn),
                args=[
                    *SCOPE,
                    "--authorize-live-free-only",
                    "6",
                    "--archive-dir",
                    str(archive),
                    "--retention-approval-reference",
                    "synthetic-approval",
                ],
            )
            self.assertEqual(code, 0)
            receipts = json.loads((archive / "capture-receipts.json").read_bytes())["receipts"]
            saved = (archive / "get_player_games.json").read_bytes()
            self.assertEqual(saved, reply.read.return_value)
            self.assertEqual(receipts[1]["sha256"], hashlib.sha256(saved).hexdigest())
            self.assertEqual(receipts[1]["request"]["player_id"], "6099")
            self.assertEqual(archive.stat().st_mode & 0o777, 0o700)
        self.assertEqual(records[-1]["verified_credits"], 6)
        self.assertEqual(conn.request.call_count, 2)

    def test_wrong_grant_and_missing_retention_approval_stop_before_credentials(self):
        for args in (
            ["--market", "ASSISTS"],
            ["--archive-dir", "/unused-test-path"],
        ):
            with self.subTest(args=args):
                connection, lookup = Mock(), Mock()
                code, _ = self.run_harness(
                    connection,
                    args=[*SCOPE, "--authorize-live-free-only", "6", *args],
                    credential=lookup,
                )
                self.assertEqual(code, 1)
                lookup.assert_not_called()
                connection.assert_not_called()

    def test_curry_id_cannot_pass_the_tatum_pin(self):
        changed = identity()
        changed["players"][0]["player_id"] = "3975"
        conn = Mock(getresponse=Mock(return_value=response(changed, 1, 5)))
        code, records = self.run_harness(
            Mock(return_value=conn), args=[*SCOPE, "--authorize-live-free-only", "6"]
        )
        self.assertEqual(code, 1)
        self.assertEqual(records[-1]["error"], "identity_unverified")
        conn.request.assert_called_once()

    def test_unpinned_identity_discovery_stops_after_one_request(self):
        args = SCOPE.copy()
        start = args.index("--expected-provider-id")
        del args[start : start + 2]
        conn = Mock(getresponse=Mock(return_value=response(identity(), 1, 0)))
        code, records = self.run_harness(
            Mock(return_value=conn),
            args=[*args, "--authorize-live-free-only", "1", "--identity-only"],
        )
        self.assertEqual(code, 0)
        self.assertEqual(records[-2]["identity_status"], "discovered_unverified")
        self.assertFalse(records[-1]["archived"])
        conn.request.assert_called_once()

    def test_tls_key_logging_blocks_before_credentials_or_connection(self):
        for value in ("", PRIVATE):
            with self.subTest(configured=bool(value)):
                factory, credential = Mock(), Mock(return_value=SECRET)
                fake_os = Mock(environ={"SSLKEYLOGFILE": value})
                with patch.dict(run_evaluation.__globals__, {"os": fake_os}):
                    code, records = self.run_harness(factory, credential=credential)
                self.assertEqual(code, 1)
                self.assertEqual(records[-1]["error"], "tls_key_logging_configured")
                credential.assert_not_called()
                factory.assert_not_called()

    @unittest.skipUnless(Path("/etc/ssl/cert.pem").is_file(), "local CA bundle unavailable")
    def test_macos_fallback_loads_trusted_roots_and_keeps_verification_enabled(self):
        conn = Mock()
        conn.connect.side_effect = ssl.SSLError(PRIVATE)
        factory = Mock(return_value=conn)
        with (
            patch.dict(
                run_evaluation.__globals__, {"sys": Mock(platform="darwin"), "os": Mock(environ={})}
            ),
            patch.object(ssl, "get_default_verify_paths", return_value=MISSING_TRUST_PATHS),
        ):
            code, records = self.run_harness(factory)
        self.assertEqual(code, 1)
        self.assertEqual(records[-1]["error"], "tls")
        context = factory.call_args.kwargs.get("context")
        assert isinstance(context, ssl.SSLContext)
        self.assertGreater(context.cert_store_stats()["x509_ca"], 0)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertIsNone(context.keylog_filename)
        conn.request.assert_not_called()

    def test_existing_trust_configuration_keeps_precedence(self):
        cases = (
            ("darwin", {"SSL_CERT_FILE": PRIVATE}, MISSING_TRUST_PATHS),
            ("darwin", {"SSL_CERT_DIR": ""}, MISSING_TRUST_PATHS),
            ("darwin", {}, replace(MISSING_TRUST_PATHS, cafile="/existing/cert.pem")),
            ("darwin", {}, replace(MISSING_TRUST_PATHS, capath="/existing/certs")),
            ("linux", {}, MISSING_TRUST_PATHS),
        )
        for platform, environ, paths in cases:
            with self.subTest(platform=platform, overrides=list(environ)):
                conn = Mock()
                conn.connect.side_effect = ssl.SSLError(PRIVATE)
                factory = Mock(return_value=conn)
                with (
                    patch.dict(
                        run_evaluation.__globals__,
                        {"sys": Mock(platform=platform), "os": Mock(environ=environ)},
                    ),
                    patch.object(ssl, "get_default_verify_paths", return_value=paths),
                ):
                    code, records = self.run_harness(factory)
                self.assertEqual(code, 1)
                self.assertEqual(records[-1]["error"], "tls")
                self.assertIsNone(factory.call_args.kwargs.get("context"))
                conn.request.assert_not_called()

    def assert_body_failure(self, reply, category):
        self.addCleanup(reply.close)
        conn = Mock(getresponse=Mock(return_value=reply))
        factory = Mock(return_value=conn)
        code, records = self.run_harness(factory)
        self.assertEqual(code, 1)
        self.assertEqual((records[-1]["stage"], records[-1]["error"]), ("body_read", category))
        self.assertEqual(records[-1]["verified_credits"], 0)
        self.assertTrue(records[-1]["credit_accounting_unverified"])
        self.assertFalse(any("credits_used" in record for record in records))
        factory.assert_called_once()
        conn.request.assert_called_once()
        conn.close.assert_called_once()

    def test_truncated_body_stops_before_json_parsing_or_identity(self):
        for body in (json.dumps({"data": identity()}).encode(), PRIVATE.encode()):
            with self.subTest(size=len(body)):
                length = f"Content-Length: {len(body) + 12}".encode()
                self.assert_body_failure(wire_response(body, length), "body_length_mismatch")

    def test_invalid_or_conflicting_content_length_stops(self):
        body = json.dumps({"data": identity()}).encode()
        length = f"Content-Length: {len(body)}".encode()
        for headers in (
            (b"Content-Length: " + PRIVATE.encode(),),
            (b"Content-Length: -1",),
            (b"Content-Length: +1",),
            (b"Content-Length: 12, 13",),
            (length, b"Content-Length: 1"),
            (length, length),
            (length, b"Transfer-Encoding: chunked"),
        ):
            with self.subTest(header_count=len(headers)):
                self.assert_body_failure(wire_response(body, *headers), "invalid_body_framing")

    def test_reader_returning_more_than_declared_stops(self):
        reply = response(identity(), 1, 10)
        reply.headers["Content-Length"] = "1"
        self.assert_body_failure(reply, "body_length_mismatch")

    def test_incomplete_http_read_stops_with_sanitized_error(self):
        reply = response(identity(), 1, 10)
        reply.read.side_effect = http.client.IncompleteRead(PRIVATE.encode(), 5)
        self.assert_body_failure(reply, "incomplete_http_read")

    def test_stage_errors_are_classified_without_exception_text_or_retry(self):
        cases = (
            ("connect", socket.gaierror(PRIVATE), "connection_setup", "dns"),
            (
                "connect",
                ssl.SSLCertVerificationError(PRIVATE),
                "connection_setup",
                "tls_certificate_validation",
            ),
            ("connect", ssl.SSLError(PRIVATE), "connection_setup", "tls"),
            ("connect", ConnectionRefusedError(PRIVATE), "connection_setup", "connection"),
            ("request", TimeoutError(PRIVATE), "request_transmission", "timeout"),
            ("getresponse", http.client.BadStatusLine(PRIVATE), "http_headers", "malformed_http"),
            ("read", TimeoutError(PRIVATE), "body_read", "timeout"),
        )
        for method, error, stage, category in cases:
            with self.subTest(stage=stage, category=category):
                conn = Mock()
                reply = response(identity(), 1, 10)
                conn.getresponse.return_value = reply
                getattr(reply if method == "read" else conn, method).side_effect = error
                factory = Mock(return_value=conn)
                code, records = self.run_harness(factory)
                self.assertEqual(code, 1)
                self.assertEqual((records[-1]["stage"], records[-1]["error"]), (stage, category))
                factory.assert_called_once()
                conn.close.assert_called_once()

    def test_invalid_json_after_verified_charge_stops(self):
        conn = Mock()
        reply = response(identity(), 1, 10)
        reply.read.return_value = PRIVATE.encode()
        conn.getresponse.return_value = reply
        factory = Mock(return_value=conn)
        code, records = self.run_harness(factory)
        self.assertEqual(code, 1)
        self.assertEqual(records[-1]["stage"], "json_parse")
        self.assertEqual(records[-1]["error"], "invalid_json")
        self.assertEqual(records[-1]["verified_credits"], 1)
        factory.assert_called_once()

    def test_non_success_or_unverified_credit_accounting_stops(self):
        for reply in (
            response(identity(), 1, 10, 302),
            response(identity(), 2, 9),
            response(identity(), 1, 5),
            response(identity(), PRIVATE, 10),
        ):
            with self.subTest(status=reply.status):
                conn = Mock()
                conn.getresponse.return_value = reply
                factory = Mock(return_value=conn)
                code, records = self.run_harness(factory)
                self.assertEqual(code, 1)
                self.assertEqual(records[-1]["verified_credits"], 0)
                self.assertTrue(records[-1]["credit_accounting_unverified"])
                factory.assert_called_once()
                reply.read.assert_not_called()

    def test_stops_after_ambiguous_identity_or_additional_page(self):
        conn = Mock()
        factory = Mock(return_value=conn)
        result = identity()
        result["players"] *= 2
        conn.getresponse.return_value = response(result, 1, 10)
        code, records = self.run_harness(factory)
        self.assertEqual(code, 1)
        self.assertEqual(records[-1]["error"], "identity_unverified")
        factory.assert_called_once()

        conn.reset_mock()
        factory.reset_mock()
        alias = identity()
        alias["players"].append({"name": PRIVATE, "player_id": "6099", "team": "BOS"})
        conn.getresponse.return_value = response(alias, 1, 10)
        code, records = self.run_harness(factory)
        self.assertEqual(code, 1)
        self.assertEqual(records[-1]["error"], "identity_unverified")
        factory.assert_called_once()

        conn.reset_mock()
        factory.reset_mock()
        page = history()
        page["next_offset"] = 8
        conn.getresponse.side_effect = [response(identity(), 1, 10), response(page, 5, 5)]
        code, records = self.run_harness(factory)
        self.assertEqual(code, 1)
        self.assertEqual(records[-1]["error"], "history_incomplete")
        self.assertEqual(factory.call_count, 2)

    def test_mismatched_box_score_never_claims_verification_or_retries(self):
        conn = Mock()
        altered = boxscore()
        altered["players"][0]["pts"] = 26
        conn.getresponse.side_effect = [
            response(identity(), 1, 10),
            response(history(), 5, 5),
            response(altered, 5, 0),
        ]
        factory = Mock(return_value=conn)
        code, records = self.run_harness(factory)
        self.assertEqual(code, 1)
        self.assertEqual(records[-1]["error"], "box_score_unverified")
        self.assertEqual(records[-1]["verified_credits"], 11)
        self.assertEqual(factory.call_count, 3)

    def test_exact_sequence_and_credit_ceiling(self):
        conn = Mock()
        body = json.dumps({"data": identity()}).encode()
        first_reply = wire_response(body, f"Content-Length: {len(body)}".encode())
        self.addCleanup(first_reply.close)
        conn.getresponse.side_effect = [
            first_reply,
            response(history(), 5, 5),
            response(boxscore(), 5, 0),
        ]
        factory = Mock(return_value=conn)
        code, records = self.run_harness(factory)
        self.assertEqual(code, 0)
        self.assertEqual(records[-1]["verified_credits"], 11)
        self.assertEqual(records[-1]["remaining_credits"], 0)
        self.assertFalse(records[-1]["actual_completion_timestamp_verified"])
        self.assertEqual(
            [item.args for item in factory.call_args_list], [("mcp.dunkapi.com", 443)] * 3
        )
        self.assertEqual([item.kwargs["timeout"] for item in factory.call_args_list], [15] * 3)
        self.assertEqual(conn.connect.call_count, 3)
        calls = conn.request.call_args_list
        self.assertEqual(
            [call.args for call in calls],
            [
                ("POST", "/v1/search_players"),
                ("POST", "/v1/get_player_games"),
                ("POST", "/v1/get_game"),
            ],
        )
        self.assertEqual(
            json.loads(calls[0].kwargs["body"]),
            {
                "name": "Jayson Tatum",
                "league": "nba",
                "limit": 10,
            },
        )
        self.assertEqual(
            json.loads(calls[1].kwargs["body"]),
            {
                "player_id": "6099",
                "league": "nba",
                "season": 2027,
                "season_type": "regular",
                "limit": 100,
                "offset": 0,
            },
        )
        self.assertEqual(json.loads(calls[2].kwargs["body"]), {"game_id": "8", "league": "nba"})
        self.assertFalse(conn.auto_open)
