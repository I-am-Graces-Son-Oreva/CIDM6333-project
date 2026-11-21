"""Read-only comparison of pinned DunkAPI archives to a receipt-bound board line."""

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.errors import FifthPickError, ValidationError
from fifth_pick.evidence import history_line_outcome
from fifth_pick.registry import Registry
from fifth_pick.slate_manifest import read_slate_run_context
from fifth_pick.snapshots import SnapshotEvidence, read_receipted_snapshot_ledger
from fifth_pick.sources.base import EvidenceMode
from fifth_pick.sources.dunkapi_evidence_package import (
    EvidencePackageReplay,
    replay_evidence_package,
)
from fifth_pick.sources.dunkapi_history import HistoryScope
from fifth_pick.sources.supporting_fixture import decode_payload, payload_hash
from fifth_pick.storage import application_run_store

_OFFLINE_MAX_AGE = timedelta(minutes=30)


def _read(directory: Path, name: str) -> bytes:
    with (directory / name).open("rb") as file:
        body = file.read(1_048_577)
    if len(body) > 1_048_576:
        raise ValidationError("history archive file exceeds the offline size limit")
    return body


def history_compare(arguments: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="fifth-pick history-compare", allow_abbrev=False)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--candidate-key", required=True)
    parser.add_argument("--snapshot", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument(
        "--archive", nargs=2, action="append", metavar=("DIRECTORY", "SHA256"), required=True
    )
    try:
        args = parser.parse_args(arguments)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2

    try:
        result = compare_archives(args.run_id, args.candidate_key, args.snapshot, args.archive)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (FifthPickError, OSError, TypeError, KeyError, ValueError, RecursionError) as exc:
        detail = str(exc) if isinstance(exc, FifthPickError) else type(exc).__name__
        print(f"History comparison stopped: {detail}", file=sys.stderr)
        return 1


def compare_archives(
    run_id: str,
    candidate_key: str,
    snapshot: int,
    archives: list[list[str]],
    *,
    required_mode: EvidenceMode | None = None,
) -> dict[str, object]:
    """Compare local archives to an exact board observation without writing receipts."""
    if not re.fullmatch(r"[0-9a-f]{64}", candidate_key):
        raise ValidationError("expected an exact candidate key")
    store = application_run_store()
    matches = [
        entry
        for entry in read_receipted_snapshot_ledger(store, run_id)
        if isinstance(entry, SnapshotEvidence)
        and entry.candidate_key == candidate_key
        and entry.snapshot.number == snapshot
        and not entry.late
    ]
    if len(matches) != 1:
        raise ValidationError("comparison requires one timely receipt-bound snapshot")
    (stage,) = matches
    if required_mode is not None and stage.evidence_mode is not required_mode:
        raise ValidationError("the recorded board does not match the required evidence mode")
    line = stage.snapshot.observation
    if not AuthorizationGate().authorize(stage.candidate_id, line.category, line.direction).allowed:
        raise ValidationError("the recorded player, market, and direction are not authorized")
    context = read_slate_run_context(store, run_id)
    events = [event for event in context.event_boards[0].events if event.event_id == stage.event_id]
    if len(events) != 1 or events[0].commence_time != stage.event_start:
        raise ValidationError("the snapshot event does not match the receipt-bound slate")
    (event,) = events
    registry = Registry.from_universe(load_configs().approved_universe)
    provenance = (
        "synthetic" if stage.evidence_mode is EvidenceMode.FIXTURE else "external-unverified"
    )
    replays: dict[str, EvidencePackageReplay] = {}
    provider_ids: set[str] = set()
    for directory_name, digest in archives:
        directory = Path(directory_name)
        manifest = _read(directory, "manifest.json")
        if payload_hash(manifest) != digest:
            raise ValidationError("the manifest bytes differ from the pinned digest")
        package = decode_payload(manifest)
        if not isinstance(package, dict) or package.get("provenance") != provenance:
            raise ValidationError("archive provenance does not match the recorded board mode")
        subject = package["subject"]
        request = dict(subject["request"])
        request["first_date"] = date.fromisoformat(request["first_date"])
        request["last_date"] = date.fromisoformat(request["last_date"])
        scope = HistoryScope(**request)
        page_rows = package["pages"]
        if not isinstance(page_rows, list) or not 1 <= len(page_rows) <= scope.max_pages:
            raise ValidationError("invalid history archive page chain")
        pages = []
        for page in page_rows:
            offset = page["offset"]
            if type(offset) is not int or offset < 0:
                raise ValidationError("invalid history archive page offset")
            pages.append((offset, _read(directory, f"page-{offset}.json")))
        replay = replay_evidence_package(
            manifest,
            identity_body=_read(directory, "identity.json"),
            pages=tuple(pages),
            corroboration_body=_read(directory, "corroboration.json"),
            coverage_body=_read(directory, "coverage.json"),
            correction_body=_read(directory, "correction.json"),
            expected_manifest_sha256=digest,
            previous_manifest_body=(
                _read(directory, "previous-manifest.json")
                if package.get("previous_sha256")
                else None
            ),
            scope=scope,
            registry=registry,
            canonical_player_id=stage.candidate_id,
            event_id=stage.event_id,
            event_teams=(event.home_team, event.away_team),
            game_id=subject["game_id"],
            as_of=line.retrieved_at,
            coverage_max_age=_OFFLINE_MAX_AGE,
            correction_max_age=_OFFLINE_MAX_AGE,
        )
        if replay.game.game_id in replays:
            raise ValidationError("duplicate historical game across archives")
        replays[replay.game.game_id] = replay
        provider_ids.add(scope.player_id)
    if len(provider_ids) != 1:
        raise ValidationError("historical archives disagree on provider player identity")
    if len({replay.game.played_at for replay in replays.values()}) != len(replays):
        raise ValidationError("historical archives contain simultaneous appearances for one player")

    rows = []
    for replay in sorted(
        replays.values(),
        key=lambda item: (item.game.played_at, item.game.game_id),
        reverse=True,
    ):
        sample = replay.game.sample(line.category)
        outcome = history_line_outcome(sample.value, line.projection)
        rows.append(
            {
                "game_id": replay.game.game_id,
                "played_at": sample.played_at.isoformat(),
                "opponent": sample.opponent,
                "season": sample.season,
                "value": sample.value,
                "outcome": outcome,
                "manifest_sha256": replay.manifest_sha256,
            }
        )
    outcomes = [row["outcome"] for row in rows]
    return {
        "status": "ANALYSIS_ONLY",
        "archive_provenance": provenance,
        "event_id": stage.event_id,
        "candidate_key": stage.candidate_key,
        "snapshot": snapshot,
        "player_id": stage.candidate_id,
        "platform": line.platform.value,
        "market": line.category.value,
        "direction": line.direction.value,
        "line": line.projection,
        "observed_at": line.retrieved_at.isoformat(),
        "counts": {outcome: outcomes.count(outcome) for outcome in ("HIGHER", "LOWER", "PUSH")},
        "favorable_count": outcomes.count(line.direction.value),
        "samples": rows,
        "limitations": [
            "Supplied games only. Complete last-eight coverage is unverified.",
            "Replay does not authenticate sources or admit LIVE evidence.",
        ],
    }
