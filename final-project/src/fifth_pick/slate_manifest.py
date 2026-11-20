"""M5 persistence for the application-owned M8 slate boundary."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fifth_pick.errors import StorageError
from fifth_pick.receipts import Receipt, redact_text
from fifth_pick.sources.base import EvidenceMode, SourceBoard
from fifth_pick.sources.odds_api import (
    APPROVED_BOOKMAKERS,
    APPROVED_MARKETS,
    APPROVED_REGION,
    SOURCE_ID,
)
from fifth_pick.storage import RunStore, _atomic_write

RUN_METADATA_FILENAME: Final[str] = "run.json"
M4_EVENT_BOARDS_FILENAME: Final[str] = "m4-event-boards.jsonl"
SLATE_TIMEZONE: Final[str] = "America/Chicago"
_SHA256_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_RUN_METADATA_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "run_id",
        "started_at",
        "slate_date",
        "slate_timezone",
        "start_source",
        "start_payload_sha256",
    }
)
_EVENT_BOARD_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "run_id",
        "snapshot_number",
        "source_id",
        "region",
        "bookmakers",
        "markets",
        "evidence_mode",
        "request_timestamp",
        "retrieved_at",
        "source_update_time",
        "payload_sha256",
        "request_url",
        "quota",
        "events",
        "recorded_at",
        "event_key",
    }
)


class SlateManifestError(StorageError):
    """Raised when application-owned slate metadata is absent or inconsistent."""


@dataclass(frozen=True, slots=True)
class SlateRunMetadata:
    run_id: str
    started_at: datetime
    slate_date: str
    slate_timezone: str
    start_source: str
    start_payload_sha256: str


@dataclass(frozen=True, slots=True)
class SlateEvent:
    event_id: str
    home_team: str
    away_team: str
    commence_time: datetime


@dataclass(frozen=True, slots=True)
class M4EventBoardManifest:
    run_id: str
    snapshot_number: int
    source_id: str
    region: str
    bookmakers: tuple[str, ...]
    markets: tuple[str, ...]
    evidence_mode: EvidenceMode
    request_timestamp: datetime
    retrieved_at: datetime
    source_update_time: datetime | None
    payload_sha256: str
    request_url: str
    quota: dict[str, int | None]
    events: tuple[SlateEvent, ...]
    recorded_at: datetime
    event_key: str


@dataclass(frozen=True, slots=True)
class SlateRunContext:
    metadata: SlateRunMetadata
    event_boards: tuple[M4EventBoardManifest, ...]


def _is_aware(value: datetime) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _timestamp(value: datetime) -> str:
    if not _is_aware(value):
        raise SlateManifestError("manifest timestamps must be timezone-aware")
    return value.isoformat()


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise SlateManifestError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SlateManifestError(f"{field} is not a valid timestamp") from exc
    if not _is_aware(parsed):
        raise SlateManifestError(f"{field} must be timezone-aware")
    return parsed


def _canonical_json(record: dict[str, object]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _append_jsonl(path: Path, record: dict[str, object], event_key: str) -> None:
    try:
        existing = path.read_bytes()
    except FileNotFoundError:
        existing = b""
    except OSError as exc:
        raise SlateManifestError(f"cannot read {path.name}") from exc

    for line_number, line in enumerate(existing.splitlines(), start=1):
        try:
            prior = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SlateManifestError(f"{path.name} has invalid JSON at line {line_number}") from exc
        if not isinstance(prior, dict):
            raise SlateManifestError(f"{path.name} contains a non-object record")
        if prior.get("event_key") == event_key:
            if prior != record:
                raise SlateManifestError(f"{path.name} event key has conflicting content")
            return

    content = existing
    if content and not content.endswith(b"\n"):
        content += b"\n"
    content += f"{_canonical_json(record)}\n".encode()
    try:
        _atomic_write(path, content)
    except OSError as exc:
        raise SlateManifestError(f"cannot persist {path.name}") from exc


def _append_run_receipt(store: RunStore, metadata: SlateRunMetadata) -> None:
    store.append_receipt(
        Receipt(
            timestamp=_timestamp(metadata.started_at),
            event="SLATE_RUN_STARTED",
            result="RECORDED",
            subject=metadata.run_id,
            source=metadata.start_source,
            reason=(f"slate_date={metadata.slate_date};slate_timezone={metadata.slate_timezone}"),
            run_id=metadata.run_id,
            event_key="slate-run-started",
        )
    )


def _load_run_metadata(store: RunStore, run_id: str) -> SlateRunMetadata:
    path = store.run_directory(run_id) / RUN_METADATA_FILENAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SlateManifestError("application-owned slate run metadata is missing") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SlateManifestError("application-owned slate run metadata is unreadable") from exc
    if not isinstance(raw, dict) or set(raw) != _RUN_METADATA_FIELDS:
        raise SlateManifestError("slate run metadata has unknown or missing fields")
    if (
        isinstance(raw["schema_version"], bool)
        or raw["schema_version"] != 1
        or raw["run_id"] != run_id
        or raw["slate_timezone"] != SLATE_TIMEZONE
        or raw["start_source"] != SOURCE_ID
        or not isinstance(raw["slate_date"], str)
        or not isinstance(raw["start_payload_sha256"], str)
        or _SHA256_PATTERN.fullmatch(raw["start_payload_sha256"]) is None
    ):
        raise SlateManifestError("slate run metadata does not match the M8 run contract")
    started_at = _parse_timestamp(raw["started_at"], "started_at")
    try:
        expected_date = started_at.astimezone(ZoneInfo(SLATE_TIMEZONE)).date().isoformat()
    except ZoneInfoNotFoundError as exc:
        raise SlateManifestError("application slate timezone is unavailable") from exc
    if raw["slate_date"] != expected_date:
        raise SlateManifestError("slate_date does not match the application start time")
    return SlateRunMetadata(
        run_id=run_id,
        started_at=started_at,
        slate_date=expected_date,
        slate_timezone=SLATE_TIMEZONE,
        start_source=SOURCE_ID,
        start_payload_sha256=raw["start_payload_sha256"],
    )


def _validate_board_input(
    store: RunStore,
    run_id: str,
    snapshot_number: int,
    board: SourceBoard,
    recorded_at: datetime,
) -> None:
    if type(store) is not RunStore or not isinstance(board, SourceBoard):
        raise SlateManifestError("manifest recording requires an M4 SourceBoard and M2 RunStore")
    if (
        isinstance(snapshot_number, bool)
        or not isinstance(snapshot_number, int)
        or snapshot_number not in (1, 2, 3)
    ):
        raise SlateManifestError("snapshot_number must be 1, 2, or 3")
    if not _is_aware(recorded_at):
        raise SlateManifestError("recorded_at must be timezone-aware")
    provenance = board.provenance
    if (
        provenance.source_id != SOURCE_ID
        or provenance.region != APPROVED_REGION
        or provenance.bookmakers != APPROVED_BOOKMAKERS
        or provenance.markets != APPROVED_MARKETS
        or provenance.evidence_mode not in (EvidenceMode.LIVE, EvidenceMode.FIXTURE)
        or _SHA256_PATTERN.fullmatch(provenance.payload_sha256) is None
        or provenance.request_timestamp > provenance.retrieved_at
        or provenance.retrieved_at > recorded_at
    ):
        raise SlateManifestError("M4 event-board provenance is invalid")
    if any(not _is_aware(event.commence_time) for event in board.events):
        raise SlateManifestError("M4 event commencement timestamps must be timezone-aware")
    store.run_directory(run_id)


def _record_run_metadata(store: RunStore, run_id: str, board: SourceBoard) -> SlateRunMetadata:
    path = store.run_directory(run_id) / RUN_METADATA_FILENAME
    if path.exists():
        metadata = _load_run_metadata(store, run_id)
        _append_run_receipt(store, metadata)
        return metadata

    started_at = board.provenance.request_timestamp
    try:
        slate_date = started_at.astimezone(ZoneInfo(SLATE_TIMEZONE)).date().isoformat()
    except ZoneInfoNotFoundError as exc:
        raise SlateManifestError("application slate timezone is unavailable") from exc
    metadata = SlateRunMetadata(
        run_id=run_id,
        started_at=started_at,
        slate_date=slate_date,
        slate_timezone=SLATE_TIMEZONE,
        start_source=SOURCE_ID,
        start_payload_sha256=board.provenance.payload_sha256,
    )
    record = {
        "schema_version": 1,
        "run_id": metadata.run_id,
        "started_at": _timestamp(metadata.started_at),
        "slate_date": metadata.slate_date,
        "slate_timezone": metadata.slate_timezone,
        "start_source": metadata.start_source,
        "start_payload_sha256": metadata.start_payload_sha256,
    }
    try:
        _atomic_write(path, f"{json.dumps(record, sort_keys=True)}\n".encode())
    except OSError as exc:
        raise SlateManifestError("cannot persist application-owned slate run metadata") from exc
    _append_run_receipt(store, metadata)
    return metadata


def _manifest_record(
    run_id: str,
    snapshot_number: int,
    board: SourceBoard,
    recorded_at: datetime,
) -> dict[str, object]:
    provenance = board.provenance
    record: dict[str, object] = {
        "schema_version": 1,
        "run_id": run_id,
        "snapshot_number": snapshot_number,
        "source_id": provenance.source_id,
        "region": provenance.region,
        "bookmakers": list(provenance.bookmakers),
        "markets": list(provenance.markets),
        "evidence_mode": provenance.evidence_mode.value,
        "request_timestamp": _timestamp(provenance.request_timestamp),
        "retrieved_at": _timestamp(provenance.retrieved_at),
        "source_update_time": (
            None
            if provenance.source_update_time is None
            else _timestamp(provenance.source_update_time)
        ),
        "payload_sha256": provenance.payload_sha256,
        "request_url": redact_text(provenance.request_url),
        "quota": {
            "remaining": provenance.quota.remaining,
            "used": provenance.quota.used,
            "last": provenance.quota.last,
        },
        "events": [
            {
                "event_id": event.event_id,
                "home_team": event.home_team,
                "away_team": event.away_team,
                "commence_time": _timestamp(event.commence_time),
            }
            for event in board.events
        ],
        "recorded_at": _timestamp(recorded_at),
    }
    digest = hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()
    record["event_key"] = f"m4-event-board-{snapshot_number}-{digest}"
    return record


def _record_manifest_receipt(store: RunStore, record: dict[str, object]) -> None:
    store.append_receipt(
        Receipt(
            timestamp=str(record["recorded_at"]),
            event="M4_EVENT_BOARD_RECORDED",
            result="RECORDED",
            subject=str(record["payload_sha256"]),
            source=SOURCE_ID,
            reason=f"SNAPSHOT_{record['snapshot_number']}",
            run_id=str(record["run_id"]),
            event_key=str(record["event_key"]),
        )
    )


def persist_m4_event_board(
    store: RunStore,
    run_id: str,
    snapshot_number: int,
    board: SourceBoard,
    recorded_at: datetime,
) -> None:
    """Persist the run's first slate date and each complete validated M4 board."""

    _validate_board_input(store, run_id, snapshot_number, board, recorded_at)
    _record_run_metadata(store, run_id, board)
    record = _manifest_record(run_id, snapshot_number, board, recorded_at)
    path = store.run_directory(run_id) / M4_EVENT_BOARDS_FILENAME
    _append_jsonl(path, record, str(record["event_key"]))
    _record_manifest_receipt(store, record)


def _parse_event_board(
    value: object,
    *,
    run_id: str,
    receipts: tuple[dict[str, str | None], ...],
) -> M4EventBoardManifest:
    if not isinstance(value, dict) or set(value) != _EVENT_BOARD_FIELDS:
        raise SlateManifestError("M4 event-board manifest has unknown or missing fields")
    if (
        isinstance(value["schema_version"], bool)
        or value["schema_version"] != 1
        or value["run_id"] != run_id
    ):
        raise SlateManifestError("M4 event-board manifest has a wrong run association")
    if (
        value["source_id"] != SOURCE_ID
        or value["region"] != APPROVED_REGION
        or value["bookmakers"] != list(APPROVED_BOOKMAKERS)
        or value["markets"] != list(APPROVED_MARKETS)
        or not isinstance(value["payload_sha256"], str)
        or _SHA256_PATTERN.fullmatch(value["payload_sha256"]) is None
    ):
        raise SlateManifestError("M4 event-board manifest violates approved source provenance")
    snapshot_number = value["snapshot_number"]
    if (
        isinstance(snapshot_number, bool)
        or not isinstance(snapshot_number, int)
        or snapshot_number not in (1, 2, 3)
    ):
        raise SlateManifestError("M4 event-board manifest snapshot number is invalid")
    try:
        evidence_mode = EvidenceMode(value["evidence_mode"])
    except (TypeError, ValueError) as exc:
        raise SlateManifestError("M4 event-board evidence mode is invalid") from exc
    if evidence_mode not in (EvidenceMode.LIVE, EvidenceMode.FIXTURE):
        raise SlateManifestError("M4 event-board manifest is not LIVE or FIXTURE")
    quota = value["quota"]
    if not isinstance(quota, dict) or set(quota) != {"remaining", "used", "last"}:
        raise SlateManifestError("M4 event-board quota metadata is malformed")
    for counter in quota.values():
        if counter is not None and (isinstance(counter, bool) or not isinstance(counter, int)):
            raise SlateManifestError("M4 event-board quota counters are malformed")
    raw_events = value["events"]
    if not isinstance(raw_events, list):
        raise SlateManifestError("M4 event-board events must be a list")
    events: list[SlateEvent] = []
    for raw_event in raw_events:
        if not isinstance(raw_event, dict) or set(raw_event) != {
            "event_id",
            "home_team",
            "away_team",
            "commence_time",
        }:
            raise SlateManifestError("M4 event-board event is malformed")
        if any(
            not isinstance(raw_event[field], str) or not raw_event[field].strip()
            for field in ("event_id", "home_team", "away_team")
        ):
            raise SlateManifestError("M4 event-board event identity is malformed")
        events.append(
            SlateEvent(
                event_id=raw_event["event_id"],
                home_team=raw_event["home_team"],
                away_team=raw_event["away_team"],
                commence_time=_parse_timestamp(raw_event["commence_time"], "commence_time"),
            )
        )

    request_timestamp = _parse_timestamp(value["request_timestamp"], "request_timestamp")
    retrieved_at = _parse_timestamp(value["retrieved_at"], "retrieved_at")
    source_time_raw = value["source_update_time"]
    source_update_time = (
        None if source_time_raw is None else _parse_timestamp(source_time_raw, "source_update_time")
    )
    recorded_at = _parse_timestamp(value["recorded_at"], "recorded_at")
    if not request_timestamp <= retrieved_at <= recorded_at:
        raise SlateManifestError("M4 event-board timestamps are inconsistent")
    if source_update_time is not None and source_update_time > retrieved_at:
        raise SlateManifestError("M4 source update time is later than retrieval")
    request_url = value["request_url"]
    event_key = value["event_key"]
    if (
        not isinstance(request_url, str)
        or not request_url.strip()
        or redact_text(request_url) != request_url
        or not isinstance(event_key, str)
        or not event_key.strip()
    ):
        raise SlateManifestError("M4 event-board request or event key is malformed")
    base_record = {key: item for key, item in value.items() if key != "event_key"}
    expected_digest = hashlib.sha256(_canonical_json(base_record).encode("utf-8")).hexdigest()
    expected_key = f"m4-event-board-{snapshot_number}-{expected_digest}"
    if event_key != expected_key:
        raise SlateManifestError("M4 event-board manifest content hash does not match")
    expected_receipt = Receipt(
        timestamp=_timestamp(recorded_at),
        event="M4_EVENT_BOARD_RECORDED",
        result="RECORDED",
        subject=value["payload_sha256"],
        source=SOURCE_ID,
        reason=f"SNAPSHOT_{snapshot_number}",
        run_id=run_id,
        event_key=event_key,
    ).to_dict()
    if tuple(receipt for receipt in receipts if receipt.get("event_key") == event_key) != (
        expected_receipt,
    ):
        raise SlateManifestError("M4 event-board manifest has no matching application receipt")
    return M4EventBoardManifest(
        run_id=run_id,
        snapshot_number=snapshot_number,
        source_id=SOURCE_ID,
        region=APPROVED_REGION,
        bookmakers=APPROVED_BOOKMAKERS,
        markets=APPROVED_MARKETS,
        evidence_mode=evidence_mode,
        request_timestamp=request_timestamp,
        retrieved_at=retrieved_at,
        source_update_time=source_update_time,
        payload_sha256=value["payload_sha256"],
        request_url=request_url,
        quota=dict(quota),
        events=tuple(events),
        recorded_at=recorded_at,
        event_key=event_key,
    )


def read_slate_run_context(store: RunStore, run_id: str) -> SlateRunContext:
    """Read run-pinned Chicago slate date and receipt-bound M4 event boards."""

    if type(store) is not RunStore:
        raise SlateManifestError("slate context requires the M2 RunStore")
    metadata = _load_run_metadata(store, run_id)
    receipts = store.read_receipts(run_id)
    expected_start_receipt = Receipt(
        timestamp=_timestamp(metadata.started_at),
        event="SLATE_RUN_STARTED",
        result="RECORDED",
        subject=run_id,
        source=SOURCE_ID,
        reason=f"slate_date={metadata.slate_date};slate_timezone={SLATE_TIMEZONE}",
        run_id=run_id,
        event_key="slate-run-started",
    ).to_dict()
    start_matches = tuple(
        receipt for receipt in receipts if receipt.get("event_key") == "slate-run-started"
    )
    if start_matches != (expected_start_receipt,):
        raise SlateManifestError("slate run metadata has no matching application receipt")

    path = store.run_directory(run_id) / M4_EVENT_BOARDS_FILENAME
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise SlateManifestError("complete M4 event-board manifest is missing") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise SlateManifestError("complete M4 event-board manifest is unreadable") from exc
    manifests: list[M4EventBoardManifest] = []
    seen: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise SlateManifestError(f"M4 event-board manifest has a blank line at {line_number}")
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SlateManifestError(
                f"M4 event-board manifest has invalid JSON at line {line_number}"
            ) from exc
        manifest = _parse_event_board(raw, run_id=run_id, receipts=receipts)
        if manifest.event_key in seen:
            raise SlateManifestError("M4 event-board manifest repeats an event key")
        seen.add(manifest.event_key)
        manifests.append(manifest)
    if not manifests:
        raise SlateManifestError("complete M4 event-board manifest is empty")
    if not any(
        item.request_timestamp == metadata.started_at
        and item.payload_sha256 == metadata.start_payload_sha256
        for item in manifests
    ):
        raise SlateManifestError("run start is not bound to its first M4 event-board manifest")
    return SlateRunContext(metadata=metadata, event_boards=tuple(manifests))
