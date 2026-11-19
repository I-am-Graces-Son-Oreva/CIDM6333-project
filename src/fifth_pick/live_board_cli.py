"""Terminal entry point for a single owner-approved LIVE board observation."""

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fifth_pick.board_collection import BoardCollector, BoardPolicy, LiveBoardGrant
from fifth_pick.errors import FifthPickError
from fifth_pick.personal_readiness import LiveEventScope
from fifth_pick.slate_manifest import SLATE_TIMEZONE
from fifth_pick.snapshots import SNAPSHOT_2_T20_GAP, SNAPSHOT_3_EARLY_WINDOW, T20_OFFSET
from fifth_pick.sources.alias_crosswalk import BoardIdentity, RosterIdentity, join_event_aliases
from fifth_pick.sources.odds_api import APPROVED_BOOKMAKERS, APPROVED_MARKETS, validate_event_id
from fifth_pick.sources.transport import UrllibTransport
from fifth_pick.storage import RunStore, application_run_store
from fifth_pick.t20_review import LIVE_T20_REVIEW_GRACE

_CREDIT_LIMIT = 5


def preflight_path(store: RunStore, day: date) -> Path:
    return store.root / "preflight" / f"{day.isoformat()}.json"


def show_board_status(store: RunStore, now: datetime, *, day: date | None = None) -> int:
    """Show timing from the saved discovery without opening a connection."""
    chicago = ZoneInfo(SLATE_TIMEZONE)
    day = now.astimezone(chicago).date() if day is None else day
    path = preflight_path(store, day)
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        if (
            report["mode"] != "LIVE_PROVIDER_DISCOVERY_ONLY"
            or report["slate_date"] != day.isoformat()
            or not isinstance(report["quota"], dict)
        ):
            raise ValueError("unexpected preflight date or mode")
        rows = []
        seen = set()
        for event in report["events"]:
            event_id = event["event_id"]
            validate_event_id(event_id)
            if event_id in seen:
                raise ValueError("duplicate event in saved preflight")
            seen.add(event_id)
            tipoff = datetime.fromisoformat(event["tipoff"])
            if tipoff.utcoffset() is None or tipoff.astimezone(chicago).date() != day:
                raise ValueError("unexpected event timestamp")
            local_tipoff = tipoff.astimezone(chicago)
            t20 = local_tipoff - T20_OFFSET
            cutoff = t20 - SNAPSHOT_2_T20_GAP
            if now.astimezone(chicago).date() < day:
                timing = "SNAPSHOT_1_WINDOW_NOT_YET_OPEN"
            elif now >= tipoff:
                timing = "SCHEDULED_TIPOFF_PASSED"
            elif now >= cutoff:
                timing = "SNAPSHOT_1_WINDOW_CLOSED"
            else:
                timing = "SNAPSHOT_1_WINDOW_OPEN"
            rows.append(
                dict(
                    event,
                    timing=timing,
                    snapshot_1_cutoff=cutoff.isoformat(),
                    snapshot_2_latest_at=cutoff.isoformat(),
                    snapshot_3_opens_at=(local_tipoff - SNAPSHOT_3_EARLY_WINDOW).isoformat(),
                    snapshot_3_closes_at=t20.isoformat(),
                    t20_review_opens_at=t20.isoformat(),
                    t20_review_closes_at=(t20 + LIVE_T20_REVIEW_GRACE).isoformat(),
                    decision_before=local_tipoff.isoformat(),
                )
            )
    except FileNotFoundError:
        print("No saved preflight for this Chicago slate. Run board-preflight once.")
        return 1
    except (FifthPickError, OSError, KeyError, TypeError, ValueError):
        print("Saved preflight could not be read or validated.", file=sys.stderr)
        return 1
    expected = report.get("expected_games")
    ceiling = (
        (5 if len(rows) >= 5 else 4)
        if type(expected) is int and 0 < expected == len(rows)
        else None
    )
    print(
        json.dumps(
            {
                "mode": "SAVED_PROVIDER_DISCOVERY_TIMING_ONLY",
                "slate_date": day.isoformat(),
                "checked_at": report.get("checked_at"),
                "quota_at_preflight": report["quota"],
                "manifest_game_count": len(rows),
                "selection_ceiling": ceiling,
                "events": rows,
            },
            sort_keys=True,
        )
    )
    return 0


def collect_live_board(arguments: Sequence[str], read: Callable[[str], str]) -> int:
    parser = argparse.ArgumentParser(prog="fifth-pick board-collect")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--board-identities", type=Path)
    parser.add_argument("--series", action="store_true")
    parser.add_argument("--snapshot", type=int, choices=(1, 2, 3), default=1)
    options = parser.parse_args(arguments)
    slot = options.snapshot
    if slot != 1 and not options.series:
        print("Later slots require the originally approved series scope.", file=sys.stderr)
        return 1
    slots = (1, 2, 3) if options.series else (1,)
    budget = _CREDIT_LIMIT * len(slots)
    store = application_run_store()
    chicago = ZoneInfo(SLATE_TIMEZONE)
    now = datetime.now(UTC)
    today = now.astimezone(chicago).date()
    try:
        store.run_directory(options.run_id)
        draft = json.loads(options.scope.read_text(encoding="utf-8"))
        path = options.preflight or preflight_path(store, today)
        report = json.loads(path.read_text(encoding="utf-8"))
        selected = draft["event"]
        event_id = selected["event_id"]
        tipoff = datetime.fromisoformat(selected["tipoff"])
        if tipoff.utcoffset() is None:
            raise ValueError("tipoff must be timezone-aware")
        player_ids = draft["player_ids"]
        if (
            not isinstance(player_ids, list)
            or not all(isinstance(p, str) for p in player_ids)
            or len(player_ids) != len(set(player_ids))
        ):
            raise ValueError("invalid player scope")
        scope = LiveEventScope(
            event_id, selected["home_team"], selected["away_team"], tipoff, tuple(player_ids)
        )
        scope.validate()
        t20 = tipoff - T20_OFFSET
        cutoff = t20 - SNAPSHOT_2_T20_GAP
        deadline = t20 if slot == 3 else cutoff
        if (
            now > deadline
            or (slot == 1 and now == deadline)
            or tipoff.astimezone(chicago).date() != today
        ):
            print(
                f"LIVE collection stopped. The Snapshot {slot} window is closed.", file=sys.stderr
            )
            return 1
        events = report["events"]
        slate_ids = tuple(row["event_id"] for row in events)
        for provider_id in slate_ids:
            validate_event_id(provider_id)
        if (
            report["mode"] != "LIVE_PROVIDER_DISCOVERY_ONLY"
            or report["slate_date"] != today.isoformat()
            or type(draft["slate_game_count"]) is not int
            or len(events) != draft["slate_game_count"]
            or len(slate_ids) != len(set(slate_ids))
            or selected not in events
            or any(
                (start := datetime.fromisoformat(row["tipoff"])).utcoffset() is None
                or start.astimezone(chicago).date() != today
                for row in events
            )
            or type(report["quota"]["last"]) is not int
            or report["quota"]["last"] != 0
            or type(report["quota"]["remaining"]) is not int
            or report["quota"]["remaining"] < (budget if slot == 1 else _CREDIT_LIMIT)
        ):
            print(
                "LIVE collection stopped. The complete preflight slate did not match.",
                file=sys.stderr,
            )
            return 1
        if options.roster is None and options.board_identities is None:
            aliases = draft["aliases"]
            alias_evidence = draft.get("alias_evidence")
        elif options.roster is not None and options.board_identities is not None:
            roster = json.loads(options.roster.read_text(encoding="utf-8"))
            board = json.loads(options.board_identities.read_text(encoding="utf-8"))
            aliases, alias_evidence = join_event_aliases(
                scope,
                tuple(RosterIdentity(**row) for row in roster),
                tuple(BoardIdentity(**row) for row in board),
            )
        else:
            raise ValueError("both independently verified identity sources are required")
        if (
            not isinstance(aliases, dict)
            or not aliases
            or not isinstance(alias_evidence, dict)
            or alias_evidence.keys() != aliases.keys()
            or any(
                not isinstance(ref, str) or not ref.strip() or not ref.isprintable()
                for ref in alias_evidence.values()
            )
            or any(
                not label.isprintable() or player_id not in player_ids
                for label, player_id in aliases.items()
            )
        ):
            print(
                "LIVE collection stopped. Verified provider aliases are required.", file=sys.stderr
            )
            return 1
        print(
            json.dumps(
                {
                    "event": selected,
                    "run_id": options.run_id,
                    "snapshot": slot,
                    "authorized_slots": slots,
                    "deadline_central": deadline.astimezone(chicago).isoformat(),
                    "slate_event_ids": slate_ids,
                    "player_ids": player_ids,
                    "provider_aliases": aliases,
                    "alias_evidence": alias_evidence,
                    "maximum_credits": budget,
                    "maximum_current_request_credits": _CREDIT_LIMIT,
                    "bookmakers": APPROVED_BOOKMAKERS,
                    "markets": APPROVED_MARKETS,
                    "retries": 0,
                },
                sort_keys=True,
            )
        )
        slot_label = "SNAPSHOTS 1-3" if options.series else "SNAPSHOT 1"
        confirmation = f"APPROVE {event_id} {slot_label} {budget}"
        if (
            read(f"Joseph only. To approve the displayed scope, type {confirmation}: ")
            != confirmation
        ):
            return 1
        policy = BoardPolicy(
            budget,
            (event_id,),
            timedelta(minutes=30),
            {label: (player_id,) for label, player_id in aliases.items()},
            "Joseph terminal review of provider alias evidence SHA-256 "
            + hashlib.sha256(json.dumps(alias_evidence, sort_keys=True).encode()).hexdigest(),
        )
        grant = LiveBoardGrant(
            options.run_id,
            f"Joseph terminal confirmation: {confirmation}",
            "https://the-odds-api.com/liveapi/guides/v4/#get-event-odds",
            tipoff if options.series else cutoff,
            policy.fingerprint(),
            (scope,),
            slate_ids,
            slots,
        )
        entries = BoardCollector(
            store, policy, transport=UrllibTransport(), live_grant=grant
        ).collect(options.run_id, slot, event_id, request_authorized=True)
    except (FifthPickError, OSError, ValueError, KeyError, TypeError, AttributeError, EOFError):
        print(
            "LIVE collection stopped. Check the scope, credentials, and run receipts.",
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "mode": "LIVE",
                "run_id": options.run_id,
                "event_id": event_id,
                "snapshot": slot,
                "accepted_observations": len(entries),
            },
            sort_keys=True,
        )
    )
    return 0
