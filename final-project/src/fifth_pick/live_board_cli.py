"""Terminal entry point for a single owner-approved LIVE board observation."""

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fifth_pick.board_collection import BoardCollector, BoardPolicy, LiveBoardGrant
from fifth_pick.errors import FifthPickError
from fifth_pick.official_slate import load_official_slate
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


def coverage_path(store: RunStore, day: date) -> Path:
    return store.root / "preflight-coverage" / f"{day.isoformat()}.json"


def _coverage_is_newer(store: RunStore, day: date, manifest: Path) -> bool:
    coverage = coverage_path(store, day)
    return coverage.exists() and (
        not manifest.exists() or coverage.stat().st_mtime_ns > manifest.stat().st_mtime_ns
    )


def show_board_status(store: RunStore, now: datetime, *, day: date | None = None) -> int:
    """Show timing from the saved discovery without opening a connection."""
    chicago = ZoneInfo(SLATE_TIMEZONE)
    day = now.astimezone(chicago).date() if day is None else day
    try:
        official = load_official_slate(day)
        path = preflight_path(store, day)
        if _coverage_is_newer(store, day, path):
            path = coverage_path(store, day)
        report = json.loads(path.read_text(encoding="utf-8"))
        if (
            report["mode"] not in ("LIVE_PROVIDER_DISCOVERY_ONLY", "LIVE_PROVIDER_COVERAGE_ONLY")
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
    if official is not None:
        ceiling = 5 if len(official.games) >= 5 else 4
    print(
        json.dumps(
            {
                "mode": "SAVED_PROVIDER_DISCOVERY_TIMING_ONLY",
                "slate_date": day.isoformat(),
                "checked_at": report.get("checked_at"),
                "quota_at_preflight": report["quota"],
                "manifest_game_count": len(rows),
                "provider_discovered_game_count": len(rows),
                "official_game_count": len(official.games) if official is not None else None,
                "selection_ceiling": ceiling,
                "coverage_only": report["mode"] == "LIVE_PROVIDER_COVERAGE_ONLY",
                "coverage": report.get("coverage"),
                "events": rows,
            },
            sort_keys=True,
        )
    )
    return 0


def collect_live_board(arguments: Sequence[str], read: Callable[[str], str]) -> int:
    parser = argparse.ArgumentParser(prog="fifth-pick board-collect")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scope", type=Path)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--board-identities", type=Path)
    parser.add_argument("--timing-file", type=Path)
    parser.add_argument("--quarantine-labels", action="store_true")
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
        quarantine = options.quarantine_labels
        if (
            (quarantine and (slot != 1 or options.series))
            or (
                quarantine
                and (
                    options.scope is not None
                    or options.roster is None
                    or options.timing_file is None
                )
            )
            or (not quarantine and options.scope is None)
        ):
            raise ValueError("invalid bounded Snapshot 1 options")
        path = options.preflight or preflight_path(store, today)
        if _coverage_is_newer(store, today, path):
            print(
                "LIVE collection stopped. A newer preflight found incomplete coverage.",
                file=sys.stderr,
            )
            return 1
        report = json.loads(path.read_text(encoding="utf-8"))
        timing = (
            json.loads(options.timing_file.read_bytes())
            if options.timing_file is not None
            else None
        )
        roster = ()
        draft: dict[str, Any]
        if quarantine:
            if timing is None:
                raise ValueError("quarantine requires a timing record")
            roster = tuple(RosterIdentity(**row) for row in json.loads(options.roster.read_bytes()))
            draft = {
                "event": timing["event"],
                "slate_game_count": len(report["events"]),
                "player_ids": [player.canonical_id for player in roster],
            }
        else:
            draft = json.loads(options.scope.read_text(encoding="utf-8"))
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
        official_tipoff = None
        timing_reference = None
        if timing is not None:
            official_tipoff = datetime.fromisoformat(timing["official"]["venue_tipoff"])
            timing_reference = timing["official"]["source"]
            if (
                timing["event"] != selected
                or Path(timing["provider"]["source"]).resolve() != path.resolve()
                or timing["provider"]["checked_at"] != report["checked_at"]
                or datetime.fromisoformat(timing["provider"]["chicago_tipoff"]) != tipoff
                or official_tipoff.utcoffset() is None
                or official_tipoff.astimezone(chicago).date() != today
                or datetime.fromisoformat(timing["official"]["chicago_tipoff"]) != official_tipoff
                or not isinstance(timing_reference, str)
                or not timing_reference.startswith("https://")
            ):
                raise ValueError(
                    "timing record does not match the approved event and saved preflight"
                )
            cutoff = min(tipoff, official_tipoff) - T20_OFFSET - SNAPSHOT_2_T20_GAP
            if datetime.fromisoformat(timing["conservative_snapshot_1_cutoff"]) != cutoff:
                raise ValueError("recorded conservative cutoff differs")
        official = load_official_slate(today)
        if options.series:
            if official is not None:
                game = official.game_for(scope.away_team, scope.home_team)
                if game is None or (
                    official_tipoff is not None and official_tipoff != game.scheduled_tipoff
                ):
                    raise ValueError("the independent timing records disagree on this matchup")
                official_tipoff, timing_reference = game.scheduled_tipoff, official.source
            if official_tipoff is None:
                print(
                    "LIVE series stopped. Independent official tipoff is required.", file=sys.stderr
                )
                return 1
            if official_tipoff != tipoff:
                print(
                    "LIVE series stopped before approval. Official and provider tipoffs differ "
                    f"({official_tipoff.astimezone(chicago).isoformat()} vs "
                    f"{tipoff.astimezone(chicago).isoformat()}). "
                    "Find an event with matching, independently verified timing.",
                    file=sys.stderr,
                )
                return 1
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
            or (
                official is not None
                and (
                    len(events) != len(official.games)
                    or not isinstance(report.get("coverage"), dict)
                    or report["coverage"].get("provider_matches_official_slate") is not True
                )
            )
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
        if quarantine:
            if len({row.stable_id for row in roster}) != len(roster) or any(
                not row.stable_id.strip()
                or row.team not in (scope.home_team, scope.away_team)
                or not row.reference.startswith("https://")
                for row in roster
            ):
                raise ValueError("quarantine requires an independently verified event roster")
            aliases, alias_evidence = {}, {}
        elif options.roster is None and options.board_identities is None:
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
            or (not aliases and not quarantine)
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
                    "official_tipoff_differences": (
                        report["coverage"]["provider_tipoff_differences"]
                        if official is not None
                        else []
                    ),
                    "run_id": options.run_id,
                    "snapshot": slot,
                    "authorized_slots": slots,
                    "deadline_central": deadline.astimezone(chicago).isoformat(),
                    **(
                        {
                            "official_tipoff": official_tipoff.isoformat(),
                            "official_timing_reference": timing_reference,
                            "quarantine_provider_labels": quarantine,
                        }
                        if official_tipoff is not None
                        else {}
                    ),
                    "slate_event_ids": slate_ids,
                    "player_ids": player_ids,
                    "players_without_bound_board_labels": sorted(
                        set(player_ids) - set(aliases.values())
                    ),
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
            + hashlib.sha256(
                json.dumps(
                    [asdict(row) for row in roster] if quarantine else alias_evidence,
                    sort_keys=True,
                ).encode()
            ).hexdigest(),
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
            official_tipoff,
            timing_reference,
        )

        def review_labels(labels: tuple[str, ...]) -> tuple[dict[str, str], dict[str, str]]:
            print(json.dumps({"status": "QUARANTINED", "event_id": event_id, "labels": labels}))
            if not labels:
                raise ValueError("the provider returned no eligible market labels to verify")
            path_text = (
                read(
                    "Path to independent board-identity JSON for these labels, or Enter to stop: "
                ).strip()
                if options.board_identities is None
                else str(options.board_identities)
            )
            if not path_text:
                raise ValueError("identity review cancelled")
            records = json.loads(Path(path_text).read_bytes())
            identity_fields = {"stable_id", "provider_label", "event_id", "team", "reference"}
            if not isinstance(records, list) or any(
                not isinstance(row, dict)
                or row.keys() != identity_fields
                or any(not isinstance(value, str) or not value.strip() for value in row.values())
                for row in records
            ):
                raise ValueError("invalid board-identity record shape")
            board_ids = tuple(BoardIdentity(**row) for row in records)
            if any(
                row.event_id != event_id
                or row.provider_label not in labels
                or not row.reference.startswith("https://")
                for row in board_ids
            ):
                raise ValueError("board identities do not match the captured event labels")
            verified, references = join_event_aliases(scope, roster, board_ids)
            if not verified:
                raise ValueError("no corroborated labels match the authorized roster")
            print(
                json.dumps(
                    {"verified_aliases": verified, "alias_evidence": references}, sort_keys=True
                )
            )
            if read("Joseph only. Type VERIFY SNAPSHOT 1 IDENTITIES to admit these matches: ") != (
                "VERIFY SNAPSHOT 1 IDENTITIES"
            ):
                raise ValueError("identity review cancelled")
            return verified, references

        entries = BoardCollector(
            store,
            policy,
            transport=UrllibTransport(),
            live_grant=grant,
            review_quarantined_labels=review_labels if quarantine else None,
        ).collect(options.run_id, slot, event_id, request_authorized=True)
    except (
        FifthPickError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        EOFError,
        KeyboardInterrupt,
    ):
        print(
            "LIVE collection stopped. Inspect its local receipts with fifth-pick audit --run-id.",
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
