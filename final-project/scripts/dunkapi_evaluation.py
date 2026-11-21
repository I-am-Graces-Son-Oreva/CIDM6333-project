"""One-shot DunkAPI history diagnostic, independent of the application.

After separate approval, verify the current *free* balance in the dashboard.
Run from a dedicated free-only account with no wallet funds, paid plan, or
automatic charges, and pause any concurrent usage. The operator attests to
these conditions by passing --authorize-live-free-only FREE_BALANCE.
Only then is DUNKAPI_API_KEY read from this process's environment.
TLS session key logging must be disabled before starting the evaluation.
"""

import argparse
import hashlib
import http.client
import json
import os
import re
import socket
import ssl
import sys
from collections.abc import Callable, Sequence
from contextlib import suppress
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Never

from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.errors import FifthPickError
from fifth_pick.models import Category, Direction
from fifth_pick.registry import Registry

HOST = "mcp.dunkapi.com"
TIMEOUT = 15
BODY_LIMIT = 1_048_576
CALLS = (("search_players", 1), ("get_player_games", 5), ("get_game", 5))
_MACOS_CA_BUNDLE = Path("/etc/ssl/cert.pem")


def emit(**fields: object) -> None:
    print(json.dumps(fields, sort_keys=True), flush=True)


def error_category(exc: Exception) -> str:
    if isinstance(exc, socket.gaierror):
        return "dns"
    if isinstance(exc, ssl.SSLCertVerificationError):
        return "tls_certificate_validation"
    if isinstance(exc, ssl.SSLError):
        return "tls"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, ConnectionError):
        return "connection"
    if isinstance(exc, http.client.IncompleteRead):
        return "incomplete_http_read"
    if isinstance(exc, http.client.HTTPException):
        return "malformed_http"
    if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)):
        return "invalid_json"
    if isinstance(exc, OSError):
        return "transport_io"
    return "unexpected_error"


def _macos_https_context() -> ssl.SSLContext | None:
    """Match the production transport's trust precedence without importing it."""
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
    return ssl.create_default_context(cafile=str(_MACOS_CA_BUNDLE))


def credit_header(response: http.client.HTTPResponse, name: str) -> int | None:
    values = response.headers.get_all(name, [])
    if len(values) == 1 and re.fullmatch(r"[0-9]{1,8}", values[0]):
        return int(values[0])
    return None


class _Evaluation:
    def __init__(
        self,
        key: str,
        free_balance: int,
        connection_factory: Callable[..., http.client.HTTPSConnection],
        call_count: int,
        retain: bool,
    ) -> None:
        self._headers = {
            "x-api-key": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._connect = connection_factory
        self._calls = CALLS[:call_count]
        self._budget = sum(cost for _, cost in self._calls)
        self._retain = retain
        self.captures: list[tuple[str, dict[str, object], bytes, str, int, int]] = []
        self.attempts = 0
        self.verified_credits = 0
        self.remaining = free_balance

    def stop(self, stage: str, reason: str, *, credit_unverified: bool = False) -> None:
        emit(
            stage=stage,
            error=reason,
            requests_attempted=self.attempts,
            verified_credits=self.verified_credits,
            last_verified_remaining_credits=self.remaining if self.verified_credits else None,
            credit_accounting_unverified=credit_unverified,
        )

    def request(self, endpoint: str, payload: dict[str, object]) -> dict[str, Any] | None:
        if self.attempts >= len(self._calls) or self._calls[self.attempts][0] != endpoint:
            self.stop("preflight", "request_scope_exceeded")
            return None
        cost = self._calls[self.attempts][1]
        if self.verified_credits + cost > self._budget or self.remaining < cost:
            self.stop("preflight", "credit_ceiling")
            return None
        stage = "connection_setup"
        connection = None
        charge_verified = sent = False
        try:
            connection = self._connect(HOST, 443, timeout=TIMEOUT, context=_macos_https_context())
            connection.connect()
            connection.auto_open = 0  # Do not reconnect implicitly during transmission.
            stage = "request_transmission"
            self.attempts += 1
            sent = True
            connection.request(
                "POST", "/v1/" + endpoint, body=json.dumps(payload).encode(), headers=self._headers
            )
            stage = "http_headers"
            response = connection.getresponse()
            status = response.status
            require_http_status = type(status) is int and 100 <= status <= 599
            if require_http_status:
                emit(endpoint=endpoint, stage=stage, http_status=status)
            if not require_http_status or status != 200:
                self.stop(stage, "http_status_rejected", credit_unverified=True)
                return None
            used = credit_header(response, "X-Credits-Used")
            remaining = credit_header(response, "X-Credits-Remaining")
            if used != cost or remaining != self.remaining - cost:
                self.stop(stage, "credit_accounting_unverified", credit_unverified=True)
                return None
            stage = "body_read"
            lengths = response.headers.get_all("Content-Length", [])
            encodings = response.headers.get_all("Transfer-Encoding", [])
            if (
                response.headers.defects
                or len(lengths) > 1
                or (
                    encodings
                    and (lengths or [value.lower().strip() for value in encodings] != ["chunked"])
                )
            ):
                self.stop(stage, "invalid_body_framing", credit_unverified=True)
                return None
            expected_length = None
            if lengths:
                declared = lengths[0].strip(" \t")
                if not re.fullmatch(r"[0-9]+", declared):
                    self.stop(stage, "invalid_body_framing", credit_unverified=True)
                    return None
                digits = declared.lstrip("0") or "0"
                if len(digits) > len(str(BODY_LIMIT)) or int(digits) > BODY_LIMIT:
                    self.stop(stage, "body_too_large", credit_unverified=True)
                    return None
                expected_length = int(digits)
            raw = response.read(BODY_LIMIT + 1)
            retrieved_at = datetime.now(UTC).isoformat() if self._retain else ""
            if expected_length is not None and len(raw) != expected_length:
                self.stop(stage, "body_length_mismatch", credit_unverified=True)
                return None
            if len(raw) > BODY_LIMIT:
                self.stop(stage, "body_too_large", credit_unverified=True)
                return None
            self.verified_credits += cost
            self.remaining -= cost
            charge_verified = True
            emit(endpoint=endpoint, credits_used=cost, remaining_credits=self.remaining)
            stage = "json_parse"
            envelope = json.loads(raw)
            if not isinstance(envelope, dict) or not isinstance(envelope.get("data"), dict):
                self.stop(stage, "unexpected_envelope")
                return None
            if self._retain:
                if self._headers["x-api-key"].encode() in raw:
                    self.stop(stage, "archive_contains_credential_material")
                    return None
                self.captures.append((endpoint, payload, raw, retrieved_at, cost, self.remaining))
            return envelope["data"]
        except Exception as exc:
            self.stop(stage, error_category(exc), credit_unverified=sent and not charge_verified)
            return None
        finally:
            if connection is not None:
                with suppress(Exception):
                    connection.close()


def objects(value: object) -> list[dict[str, Any]] | None:
    if isinstance(value, list) and all(isinstance(row, dict) for row in value):
        return value
    return None


def game_date(value: object) -> date | None:
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        with suppress(ValueError):
            return date.fromisoformat(value)
    return None


def stats(row: dict[str, Any]) -> tuple[int, int, int, Decimal] | None:
    pts, reb, ast = (row.get(k) for k in ("pts", "reb", "ast"))
    if (
        type(pts) is not int
        or type(reb) is not int
        or type(ast) is not int
        or min(pts, reb, ast) < 0
    ):
        return None
    minutes = row.get("minutes")
    if type(minutes) not in (str, int, float):
        return None
    try:
        if isinstance(minutes, str) and re.fullmatch(r"[0-9]{1,3}:[0-5][0-9]", minutes):
            whole, seconds = map(int, minutes.split(":"))
            parsed = Decimal(whole) + Decimal(seconds) / 60
        else:
            parsed = Decimal(str(minutes))
        if parsed.is_finite() and parsed >= 0:
            return pts, reb, ast, parsed
    except InvalidOperation:
        pass
    return None


def verified_search_id(data: dict[str, Any], name: str, team_labels: list[str]) -> str | None:
    players = objects(data.get("players"))
    if players is None or len(players) > 10:
        return None
    matches = [row for row in players if row.get("name") == name]
    if len(matches) != 1 or matches[0].get("team") not in team_labels:
        return None
    player_id = matches[0].get("player_id")
    if (
        not valid_provider_id(player_id)
        or sum(row.get("player_id") == player_id for row in players) != 1
    ):
        return None
    return player_id


def valid_provider_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[0-9]{1,20}", value) is not None
        and int(value) > 0
    )


def select_game(data: dict[str, Any], player_id: str, season: int) -> dict[str, Any] | None:
    rows = objects(data.get("games"))
    if rows is None or len(rows) > 100 or data.get("player_id") != player_id:
        return None
    played = [row for row in rows if row.get("did_not_play") is False]
    dnp = sum(row.get("did_not_play") is True for row in rows)
    valid_stats = sum(stats(row) is not None for row in played)
    next_offset = data.get("next_offset", False)
    emit(
        stage="history",
        records=len(rows),
        played=len(played),
        dnp=dnp,
        participation_unknown=len(rows) - len(played) - dnp,
        complete_stat_rows=valid_stats,
        pagination=("terminal" if next_offset is None else "additional_or_unverified"),
    )
    ids = [row.get("game_id") for row in rows]
    if (
        next_offset is not None
        or type(data.get("count")) is not int
        or data["count"] != len(rows)
        or len(played) + dnp != len(rows)
        or valid_stats != len(played)
        or len(played) < 8
        or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,20}", value) for value in ids
        )
        or len(set(ids)) != len(ids)
        or any(
            type(row.get("season")) is not int
            or row["season"] != season
            or type(row.get("season_type")) not in (int, str)
            or row["season_type"] not in (2, "regular")
            or game_date(row.get("date")) is None
            or type(row.get("home")) is not bool
            or not isinstance(row.get("opponent"), str)
            or not re.fullmatch(r"[A-Z]{2,4}", row["opponent"])
            for row in rows
        )
        or any(
            ("status" in row and row["status"] != "final") or row.get("result") not in ("W", "L")
            for row in played
        )
    ):
        return None
    return max(played, key=lambda row: (row["date"], row["game_id"]))


def compare_game(
    data: dict[str, Any],
    selected: dict[str, Any],
    player_id: str,
    team_id: str,
    season: int,
) -> bool:
    game = data.get("game")
    players = objects(data.get("players"))
    if not isinstance(game, dict) or players is None:
        return False
    matches = [row for row in players if row.get("player_id") == player_id]
    own, opponent = ("home", "away") if selected["home"] else ("away", "home")
    own_team, opponent_team = game.get(own), game.get(opponent)
    final = game.get("status") == "final"
    game_matches = (
        game.get("game_id") == selected["game_id"]
        and game.get("season") == season
        and game.get("date") == selected["date"]
    )
    teams_match = (
        len(matches) == 1
        and isinstance(own_team, dict)
        and isinstance(opponent_team, dict)
        and own_team.get("team_id") == matches[0].get("team_id") == team_id
        and opponent_team.get("abbrev") == selected["opponent"]
    )
    participation = len(matches) == 1 and matches[0].get("did_not_play") is False
    stats_match = len(matches) == 1 and stats(matches[0]) == stats(selected)
    records = (data, game, selected, *matches)
    emit(
        stage="box_score",
        final=final,
        game_matches=game_matches,
        unique_player_match=len(matches) == 1,
        teams_match=teams_match,
        participation_matches=participation,
        stats_match=stats_match,
        scheduled_start_field_present=bool(game.get("starts_at")),
        completion_field_present=any(
            row.get(field) is not None
            for row in records
            for field in ("completed_at", "ended_at", "finished_at")
        ),
        update_field_present=any(
            row.get(field) is not None
            for row in records
            for field in ("updated_at", "corrected_at", "source_updated_at", "revision_id")
        ),
        actual_completion_timestamp_verified=False,
    )
    return final and game_matches and teams_match and participation and stats_match


class _Options(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise ValueError("invalid evaluation options")


def main(
    argv: Sequence[str] | None = None,
    *,
    credential: Callable[[], str | None] = lambda: os.environ.get("DUNKAPI_API_KEY"),
    connection_factory: Callable[..., http.client.HTTPSConnection] = http.client.HTTPSConnection,
) -> int:
    parser = _Options(allow_abbrev=False)
    parser.add_argument("--authorize-live-free-only")
    parser.add_argument("--player-id")
    parser.add_argument("--team-label", action="append", default=[])
    parser.add_argument("--identity-reference")
    parser.add_argument("--expected-provider-id")
    parser.add_argument("--market", choices=[category.value for category in Category])
    parser.add_argument("--direction", choices=[direction.value for direction in Direction])
    parser.add_argument("--season-end-year", type=int)
    parser.add_argument("--archive-dir", type=Path)
    parser.add_argument("--retention-approval-reference")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--identity-only", action="store_true")
    mode.add_argument("--cross-check-team-id")
    try:
        args, unknown = parser.parse_known_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    except ValueError:
        emit(stage="preflight", error="invalid_evaluation_options")
        return 1
    call_count = 1 if args.identity_only else 3 if args.cross_check_team_id else 2
    budget = sum(cost for _, cost in CALLS[:call_count])
    balance = args.authorize_live_free_only
    if (
        not isinstance(balance, str)
        or not re.fullmatch(r"[0-9]{1,8}", balance)
        or int(balance) < budget
    ):
        emit(stage="preflight", error="explicit_free_only_authorization_required")
        return 1
    try:
        if (
            unknown
            or not args.player_id
            or not args.team_label
            or any(not label.isprintable() or not label.strip() for label in args.team_label)
            or not args.identity_reference
            or not args.identity_reference.strip()
            or not args.season_end_year
            or not 1947 <= args.season_end_year <= 9999
            or (not args.identity_only and not valid_provider_id(args.expected_provider_id))
            or (
                args.expected_provider_id is not None
                and not valid_provider_id(args.expected_provider_id)
            )
            or (
                args.cross_check_team_id is not None
                and not valid_provider_id(args.cross_check_team_id)
            )
        ):
            raise ValueError
        player = Registry.from_universe(load_configs().approved_universe).player_by_id(
            args.player_id
        )
        if (
            player is None
            or not AuthorizationGate()
            .authorize(player.player_id, Category(args.market), Direction(args.direction))
            .allowed
        ):
            raise ValueError
    except (ValueError, FifthPickError):
        emit(stage="preflight", error="invalid_player_scope_or_frozen_grant")
        return 1
    archive: Path | None = None
    try:
        if args.archive_dir is not None or args.retention_approval_reference is not None:
            if (
                args.archive_dir is None
                or not args.retention_approval_reference
                or not re.fullmatch(r"[a-zA-Z0-9._-]{1,128}", args.retention_approval_reference)
            ):
                raise ValueError
            archive = args.archive_dir.resolve()
            repository = Path(__file__).resolve().parents[2]
            if (
                archive.is_relative_to(repository)
                or archive.exists()
                or not archive.parent.is_dir()
            ):
                raise ValueError
    except (OSError, ValueError, RuntimeError):
        emit(stage="preflight", error="invalid_retention_scope")
        return 1
    if "SSLKEYLOGFILE" in os.environ:
        emit(stage="preflight", error="tls_key_logging_configured")
        return 1
    try:
        key = credential()
    except Exception:
        key = None
    if (
        not isinstance(key, str)
        or not key
        or not key.isascii()
        or not key.isprintable()
        or any(character.isspace() for character in key)
    ):
        emit(stage="preflight", error="credential_unavailable")
        return 1

    evaluation = _Evaluation(key, int(balance), connection_factory, call_count, archive is not None)
    identity = evaluation.request(
        "search_players", {"name": player.canonical_name, "league": "nba", "limit": 10}
    )
    if identity is None:
        return 1
    player_id = verified_search_id(identity, player.canonical_name, args.team_label)
    if (
        player_id is None
        or player_id == key
        or (args.expected_provider_id is not None and player_id != args.expected_provider_id)
    ):
        evaluation.stop("identity", "identity_unverified")
        return 1
    emit(
        stage="identity",
        provider_player_id=player_id,
        identity_status="discovered_unverified"
        if args.expected_provider_id is None
        else "matched_operator_pin",
    )
    archive_scope = {
        "canonical_player_id": player.player_id,
        "expected_provider_id": args.expected_provider_id,
        "identity_reference": args.identity_reference,
        "team_labels": args.team_label,
        "market": args.market,
        "direction": args.direction,
        "season_end_year": args.season_end_year,
        "retention_approval_reference": args.retention_approval_reference,
    }
    if archive is not None and key in json.dumps(archive_scope):
        evaluation.stop("archive", "archive_contains_credential_material")
        return 1
    if args.identity_only:
        return _complete(evaluation, archive, archive_scope)
    history = evaluation.request(
        "get_player_games",
        {
            "player_id": player_id,
            "league": "nba",
            "season": args.season_end_year,
            "season_type": "regular",
            "limit": 100,
            "offset": 0,
        },
    )
    if history is None:
        return 1
    selected = select_game(history, player_id, args.season_end_year)
    if selected is None:
        evaluation.stop("history", "history_incomplete")
        return 1
    if args.cross_check_team_id is None:
        return _complete(evaluation, archive, archive_scope)
    box = evaluation.request("get_game", {"game_id": selected["game_id"], "league": "nba"})
    if box is None:
        return 1
    if not compare_game(box, selected, player_id, args.cross_check_team_id, args.season_end_year):
        evaluation.stop("box_score", "box_score_unverified")
        return 1
    return _complete(evaluation, archive, archive_scope)


def _complete(evaluation: _Evaluation, archive: Path | None, scope: dict[str, object]) -> int:
    if archive is not None:
        try:
            archive.mkdir(mode=0o700)
            receipts = []
            for endpoint, request, body, at, cost, remaining in evaluation.captures:
                filename = f"{endpoint}.json"
                (archive / filename).write_bytes(body)
                receipts.append(
                    {
                        "endpoint": f"/v1/{endpoint}",
                        "request": request,
                        "file": filename,
                        "retrieved_at": at,
                        "http_status": 200,
                        "sha256": hashlib.sha256(body).hexdigest(),
                        "credits_used": cost,
                        "remaining_credits": remaining,
                    }
                )
            (archive / "capture-receipts.json").write_text(
                json.dumps(
                    {"scope": scope, "receipts": receipts},
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        except OSError:
            evaluation.stop("archive", "archive_write_failed")
            return 1
    emit(
        stage="complete",
        requests_attempted=evaluation.attempts,
        verified_credits=evaluation.verified_credits,
        remaining_credits=evaluation.remaining,
        actual_completion_timestamp_verified=False,
        archived=archive is not None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
