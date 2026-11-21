"""Read a retained provider response without opening a network or decision path."""

import argparse
import hashlib
import json
import sys
from datetime import timedelta
from pathlib import Path

from fifth_pick.authorization import AuthorizationGate
from fifth_pick.board_collection import _digest
from fifth_pick.errors import FifthPickError, ValidationError
from fifth_pick.history_compare_cli import compare_line_history
from fifth_pick.personal_readiness import LiveEventScope
from fifth_pick.sources.alias_crosswalk import BoardIdentity, RosterIdentity, join_event_aliases
from fifth_pick.sources.base import SourceProjection
from fifth_pick.sources.odds_api import (
    APPROVED_BOOKMAKERS,
    APPROVED_MARKETS,
    SOURCE_ID,
    decode_archived_odds,
    validate_event_id,
)
from fifth_pick.sources.supporting_fixture import aware_timestamp
from fifth_pick.storage import RunStore, application_run_store


def inspect_board(
    store: RunStore,
    run_id: str,
    event_id: str,
    slot: int,
    *,
    roster: tuple[RosterIdentity, ...] = (),
    identities: tuple[BoardIdentity, ...] = (),
    archives: list[list[str]] | None = None,
    line_number: int | None = None,
) -> dict[str, object]:
    """Inspect the exact retained bytes and keep all outputs outside run state."""
    validate_event_id(event_id)
    if type(slot) is not int or slot not in (1, 2, 3):
        raise ValidationError("invalid board capture slot")
    prefix = f"dfs-board-{slot}-{event_id}"
    source_rows = [
        row
        for row in store.read_receipts(run_id)
        if row["run_id"] == run_id
        and row["source"] == SOURCE_ID
        and row["subject"] == f"{slot}:{event_id}"
    ]
    receipts = {row["event_key"]: row for row in source_rows}
    if len(receipts) != len(source_rows):
        raise ValidationError("duplicate receipt keys in the capture")
    receipt = receipts.get(f"{prefix}-odds")
    if receipt is None or receipt["event"] != "DFS_HTTP_RESPONSE" or receipt["result"] != "200":
        raise ValidationError("no successful event-odds response receipt for this capture")
    response = json.loads(receipt["reason"] or "")
    path = store.run_directory(run_id) / f"{prefix}-odds.body"
    coverage = response.get("provider_market_coverage")
    reported = {tuple(row) for row in coverage} if isinstance(coverage, list) else None
    report: dict[str, object] = {
        "status": "PRELIMINARY_ONLY",
        "run_id": run_id,
        "event_id": event_id,
        "capture_slot": slot,
        "provider": SOURCE_ID,
        "quota": response["quota"],
        "retrieved_at": response["retrieved_at"],
        "payload_sha256": response["payload_sha256"],
        "requested_bookmakers": APPROVED_BOOKMAKERS,
        "requested_markets": APPROVED_MARKETS,
        "reported_coverage": coverage,
        "unreturned_bookmaker_markets": (
            sorted(
                (book, market)
                for book in APPROVED_BOOKMAKERS
                for market in APPROVED_MARKETS
                if (book, market) not in reported
            )
            if reported is not None
            else None
        ),
        "live_admission": False,
    }
    if not path.exists():
        quarantine = receipts.get(f"{prefix}-quarantine")
        if quarantine:
            binding = json.loads(quarantine["reason"] or "")
            labels = binding["labels"]
            if (
                quarantine["event"] != "DFS_BOARD_LABEL_QUARANTINE"
                or quarantine["result"] != "CAPTURED"
                or binding["odds_response_sha256"] != _digest(receipt)
                or not isinstance(labels, list)
                or any(not isinstance(label, str) or not label.isprintable() for label in labels)
            ):
                raise ValidationError("quarantine receipt does not match the captured response")
            report["quarantined_labels"] = labels
        return {
            **report,
            "lines": [],
            "blockers": ["ORIGINAL_RESPONSE_NOT_RETAINED"],
        }
    with path.open("rb") as handle:
        body = handle.read(8_388_609)
    if len(body) > 8_388_608 or hashlib.sha256(body).hexdigest() != response["payload_sha256"]:
        raise ValidationError("archived event-odds body differs from the capture receipt")
    scope_data = response["event_scope"]
    scope = LiveEventScope(
        scope_data["event_id"],
        scope_data["home_team"],
        scope_data["away_team"],
        aware_timestamp(scope_data["tipoff"]),
        tuple(scope_data["player_ids"]),
    )
    if scope.event_id != event_id:
        raise ValidationError("archived scope does not match the requested event")
    scope.validate()
    retrieved = aware_timestamp(response["retrieved_at"])
    if retrieved < aware_timestamp(response["requested_at"]):
        raise ValidationError("invalid capture chronology")
    labels: set[str] = set()

    def capture_label(_event, label, _category, _direction):
        labels.add(label)
        return False

    def decode(projection_allowed):
        return decode_archived_odds(
            body,
            event_id=event_id,
            home_team=scope.home_team,
            away_team=scope.away_team,
            tipoff=scope.tipoff,
            projection_allowed=projection_allowed,
        )

    decode(capture_label)
    if any(not label.isprintable() for label in labels):
        raise ValidationError("archived board contains unsafe label text")
    if identities and not roster:
        raise ValidationError("independent identity review requires a roster")
    if any(
        row.event_id != event_id
        or row.provider_label not in labels
        or not row.reference.startswith("https://")
        for row in identities
    ) or any(not row.reference.startswith("https://") for row in roster):
        raise ValidationError("identity evidence does not match the captured event or labels")
    aliases, references = join_event_aliases(scope, roster, identities)
    gate = AuthorizationGate()

    def allowed(_event, label, category, direction):
        player = aliases.get(label)
        return player is not None and gate.authorize(player, category, direction).allowed

    lines = []
    projections = []
    seen = set()
    for raw in decode(allowed):
        key = (aliases[raw.provider_player_name], raw.platform, raw.category, raw.direction)
        if key in seen:
            raise ValidationError("duplicate authorized line in the captured board")
        seen.add(key)
        projection = SourceProjection(
            raw.platform,
            raw.provider_player_name,
            raw.category,
            raw.projection,
            raw.direction,
            event_id,
            raw.source_update_time,
            retrieved,
        )
        projections.append(projection)
        lines.append(
            {
                "number": len(lines) + 1,
                "player_id": key[0],
                "provider_label": raw.provider_player_name,
                "platform": raw.platform.value,
                "market": raw.category.value,
                "direction": raw.direction.value,
                "line": raw.projection,
                "updated_at": raw.source_update_time.isoformat(),
                "fresh_at_capture": timedelta()
                <= retrieved - raw.source_update_time
                <= timedelta(minutes=30),
                "identity_reference": references[raw.provider_player_name],
            }
        )
    blockers = []
    if not lines:
        blockers.append(
            "NO_VERIFIED_AUTHORIZED_LINES" if identities else "INDEPENDENT_IDENTITIES_REQUIRED"
        )
    if not archives:
        blockers.append("HISTORY_ARCHIVES_NOT_SUPPLIED")
    report.update(
        lines=lines, quarantined_labels=sorted(labels - aliases.keys()), blockers=blockers
    )
    if archives:
        if line_number is None or not 1 <= line_number <= len(lines):
            raise ValidationError(
                "select a verified line with --line-number before comparing history"
            )
        number = line_number - 1
        report["historical_comparison"] = compare_line_history(
            projections[number],
            str(lines[number]["player_id"]),
            event_id,
            (scope.home_team, scope.away_team),
            archives,
            provenance="external-unverified",
        )
    return report


def board_inspect(arguments: list[str], *, pretty: bool = True) -> int:
    parser = argparse.ArgumentParser(prog="fifth-pick board-inspect", allow_abbrev=False)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--snapshot", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--board-identities", type=Path)
    parser.add_argument("--line-number", type=int)
    parser.add_argument("--archive", nargs=2, action="append", metavar=("DIRECTORY", "SHA256"))
    try:
        args = parser.parse_args(arguments)
        report = inspect_board(
            application_run_store(),
            args.run_id,
            args.event_id,
            args.snapshot,
            roster=tuple(RosterIdentity(**row) for row in json.loads(args.roster.read_bytes()))
            if args.roster
            else (),
            identities=tuple(
                BoardIdentity(**row) for row in json.loads(args.board_identities.read_bytes())
            )
            if args.board_identities
            else (),
            archives=args.archive,
            line_number=args.line_number,
        )
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (
        FifthPickError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
    ) as exc:
        print(
            f"Board inspection stopped ({type(exc).__name__}). "
            "Check the capture and local evidence.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, indent=2 if pretty else None, sort_keys=True))
    return 0
