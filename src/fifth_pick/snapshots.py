"""M5 projection snapshot collection and integrity."""

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Final

from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.errors import StorageError
from fifth_pick.identity import IdentityResolver
from fifth_pick.models import (
    Category,
    Direction,
    Observation,
    Platform,
    Provenance,
    ReasonCode,
    Snapshot,
)
from fifth_pick.receipts import Receipt
from fifth_pick.registry import Registry, RegistryPlayer, canonical_player_id
from fifth_pick.sources.base import EvidenceMode, SourceBoard, SourceEvent, SourceProjection
from fifth_pick.sources.odds_api import (
    APPROVED_BOOKMAKERS,
    APPROVED_MARKETS,
    APPROVED_REGION,
    SOURCE_ID,
)
from fifth_pick.storage import (
    RUNS_DIRECTORY,
    RunStore,
    _validate_run_id,
    application_run_store,
)

SNAPSHOTS_DIRECTORY: Final[str] = "snapshots"
SNAPSHOTS_FILENAME: Final[str] = "ledger.jsonl"
SNAPSHOT_2_MINIMUM_SEPARATION: Final[timedelta] = timedelta(minutes=60)
SNAPSHOT_2_T20_GAP: Final[timedelta] = timedelta(minutes=60)
SNAPSHOT_3_EARLY_WINDOW: Final[timedelta] = timedelta(minutes=25)
T20_OFFSET: Final[timedelta] = timedelta(minutes=20)
_SHA256_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


class SnapshotError(StorageError):
    """Raised when snapshot input or persisted evidence is invalid."""


@dataclass(frozen=True, slots=True)
class SnapshotEvidence:
    """One canonical, platform-specific snapshot and its source provenance."""

    snapshot: Snapshot
    candidate_id: str
    candidate_key: str
    evidence_mode: EvidenceMode
    event_id: str
    event_start: datetime
    target_at: datetime | None
    late: bool
    provenance: Provenance
    source_excerpt: Mapping[str, str | float]

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, Snapshot):
            raise SnapshotError("snapshot must be a Snapshot")
        if not isinstance(self.provenance, Provenance):
            raise SnapshotError("provenance must be a Provenance")
        if not isinstance(self.candidate_id, str) or not self.candidate_id:
            raise SnapshotError("candidate_id must be non-empty")
        if (
            not isinstance(self.candidate_key, str)
            or _SHA256_PATTERN.fullmatch(self.candidate_key) is None
        ):
            raise SnapshotError("candidate_key must be a SHA-256 digest")
        if not isinstance(self.evidence_mode, EvidenceMode) or self.evidence_mode not in (
            EvidenceMode.LIVE,
            EvidenceMode.FIXTURE,
        ):
            raise SnapshotError("snapshot evidence_mode must be live or fixture")
        observation = self.snapshot.observation
        if observation.event != self.event_id:
            raise SnapshotError("event_id must match the observation")
        if canonical_player_id(observation.player) != self.candidate_id:
            raise SnapshotError("candidate_id must match the canonical observation player")
        if self.candidate_key != _candidate_key(
            event_id=self.event_id,
            platform=observation.platform,
            candidate_id=self.candidate_id,
            category=observation.category,
            direction=observation.direction,
        ):
            raise SnapshotError("candidate_key does not match the observation identity")
        _require_aware(self.event_start, "event_start")
        if self.target_at is not None:
            _require_aware(self.target_at, "target_at")
        if not isinstance(self.late, bool):
            raise SnapshotError("late must be a boolean")
        if not isinstance(self.source_excerpt, Mapping) or not self.source_excerpt:
            raise SnapshotError("source_excerpt must be a non-empty mapping")
        excerpt = dict(self.source_excerpt)
        required_excerpt = {
            "platform",
            "provider_player_name",
            "category",
            "projection",
            "direction",
            "event_id",
            "source_update_time",
            "retrieved_at",
        }
        if set(excerpt) != required_excerpt:
            raise SnapshotError("source_excerpt has unknown or missing fields")
        if any(not isinstance(value, str | float) for value in excerpt.values()):
            raise SnapshotError("source_excerpt contains unsupported values")
        if (
            not isinstance(excerpt["provider_player_name"], str)
            or not excerpt["provider_player_name"].strip()
        ):
            raise SnapshotError("source excerpt provider player name must be non-empty text")
        if (
            excerpt["platform"] != observation.platform.value
            or excerpt["category"] != observation.category.value
            or excerpt["projection"] != observation.projection
            or excerpt["direction"] != observation.direction.value
            or excerpt["event_id"] != observation.event
            or excerpt["source_update_time"] != _timestamp(observation.source_update_time)
            or excerpt["retrieved_at"] != _timestamp(observation.retrieved_at)
        ):
            raise SnapshotError("source_excerpt does not match the recorded observation")
        if self.provenance.source != observation.source:
            raise SnapshotError("provenance source must match the observation")
        expected_access_method = (
            "https-get-x-api-key-header"
            if self.evidence_mode is EvidenceMode.LIVE
            else "synthetic-fixture-transport"
        )
        if self.provenance.access_method != expected_access_method:
            raise SnapshotError("provenance access method must match evidence_mode")
        if self.provenance.retrieved_at != observation.retrieved_at:
            raise SnapshotError("provenance retrieval time must match the observation")
        if self.provenance.source_timestamp != observation.source_update_time:
            raise SnapshotError("provenance source time must match the observation")
        if observation.source_update_time > observation.retrieved_at:
            raise SnapshotError("source update time cannot be later than retrieval")
        if _SHA256_PATTERN.fullmatch(self.provenance.payload_hash) is None:
            raise SnapshotError("provenance payload_hash must be a SHA-256 digest")
        if observation.retrieved_at > self.snapshot.recorded_at:
            raise SnapshotError("observation cannot be retrieved after it is recorded")
        if self.snapshot.number == 1:
            if self.target_at is not None or self.late:
                raise SnapshotError("Snapshot 1 cannot have a target or late flag")
            if (
                observation.retrieved_at >= self.event_start
                or self.snapshot.recorded_at >= self.event_start
            ):
                raise SnapshotError("Snapshot 1 must be recorded before tipoff")
        elif self.snapshot.number == 2:
            latest_at = self.event_start - T20_OFFSET - SNAPSHOT_2_T20_GAP
            if self.target_at is None or self.target_at > latest_at or self.late:
                raise SnapshotError("Snapshot 2 target or late flag is invalid")
            if observation.retrieved_at > latest_at or self.snapshot.recorded_at > latest_at:
                raise SnapshotError("Snapshot 2 must be recorded by its latest target")
        else:
            t20_at = self.event_start - T20_OFFSET
            if self.target_at != t20_at:
                raise SnapshotError("Snapshot 3 target must be T-20")
            if self.snapshot.recorded_at >= self.event_start:
                raise SnapshotError("Snapshot 3 must be recorded before tipoff")
            if (
                not self.event_start - SNAPSHOT_3_EARLY_WINDOW
                <= observation.retrieved_at
                < self.event_start
            ):
                raise SnapshotError(
                    "Snapshot 3 observation must be before tipoff and no earlier than T-25"
                )
            if self.late != (
                self.snapshot.recorded_at > t20_at or observation.retrieved_at > t20_at
            ):
                raise SnapshotError("Snapshot 3 late flag does not match its timestamps")
        object.__setattr__(self, "source_excerpt", MappingProxyType(excerpt))

    def to_dict(self) -> dict[str, object]:
        """Serialize the validated snapshot with its timing and provenance."""

        return _snapshot_entry(self)


@dataclass(frozen=True, slots=True)
class MissedSnapshot:
    """One required projection observation recorded as missed."""

    number: int
    candidate_id: str
    candidate_key: str
    event_id: str
    reason: ReasonCode
    recorded_at: datetime

    def __post_init__(self) -> None:
        if (
            isinstance(self.number, bool)
            or not isinstance(self.number, int)
            or self.number not in (1, 2, 3)
        ):
            raise SnapshotError("snapshot number must be 1, 2, or 3")
        if not isinstance(self.candidate_id, str) or not self.candidate_id:
            raise SnapshotError("candidate_id must be non-empty")
        if (
            not isinstance(self.candidate_key, str)
            or _SHA256_PATTERN.fullmatch(self.candidate_key) is None
        ):
            raise SnapshotError("candidate_key must be a SHA-256 digest")
        if not isinstance(self.event_id, str) or not self.event_id:
            raise SnapshotError("event_id must be non-empty")
        if not isinstance(self.reason, ReasonCode):
            raise SnapshotError("reason must be a ReasonCode")
        expected_reason = (
            ReasonCode.SNAPSHOT_2_MISSED
            if self.number == 2
            else ReasonCode.PROJECTION_OBSERVATION_MISSED
        )
        if self.reason is not expected_reason:
            raise SnapshotError("missed snapshot reason does not match its slot")
        _require_aware(self.recorded_at, "recorded_at")

    def to_dict(self) -> dict[str, object]:
        """Serialize the validated missed slot and its recording time."""

        return _missed_entry(self)


def _require_aware(value: datetime, field: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise SnapshotError(f"{field} must be a timezone-aware datetime")


def snapshot_2_target(snapshot_1_at: datetime, tipoff_at: datetime) -> datetime | None:
    """Calculate the midpoint target, capped at 60 minutes before the T-20 review."""

    _require_aware(snapshot_1_at, "snapshot_1_at")
    _require_aware(tipoff_at, "tipoff_at")
    t20_at = tipoff_at - T20_OFFSET
    latest_at = t20_at - SNAPSHOT_2_T20_GAP
    midpoint = snapshot_1_at + (t20_at - snapshot_1_at) / 2
    target = min(midpoint, latest_at)
    return target if target > snapshot_1_at else None


def _candidate_key(
    *,
    event_id: str,
    platform: Platform,
    candidate_id: str,
    category: Category,
    direction: Direction,
) -> str:
    identity = json.dumps(
        [event_id, platform.value, candidate_id, category.value, direction.value],
        separators=(",", ":"),
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _timestamp(value: datetime) -> str:
    return value.isoformat()


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise SnapshotError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SnapshotError(f"{field} is not a valid timestamp") from exc
    _require_aware(parsed, field)
    return parsed


def _observation_dict(observation: Observation) -> dict[str, object]:
    return {
        "platform": observation.platform.value,
        "player": observation.player,
        "category": observation.category.value,
        "projection": observation.projection,
        "direction": observation.direction.value,
        "event": observation.event,
        "source_update_time": _timestamp(observation.source_update_time),
        "retrieved_at": _timestamp(observation.retrieved_at),
        "snapshot_number": observation.snapshot_number,
        "source": observation.source,
        "multiplier": observation.multiplier,
    }


def _snapshot_entry(record: SnapshotEvidence) -> dict[str, object]:
    return {
        "kind": "snapshot",
        "number": record.snapshot.number,
        "candidate_id": record.candidate_id,
        "candidate_key": record.candidate_key,
        "evidence_mode": record.evidence_mode.value,
        "event_id": record.event_id,
        "event_start": _timestamp(record.event_start),
        "target_at": None if record.target_at is None else _timestamp(record.target_at),
        "late": record.late,
        "recorded_at": _timestamp(record.snapshot.recorded_at),
        "observation": _observation_dict(record.snapshot.observation),
        "provenance": {
            "source": record.provenance.source,
            "retrieved_at": _timestamp(record.provenance.retrieved_at),
            "source_timestamp": _timestamp(record.provenance.source_timestamp),
            "access_method": record.provenance.access_method,
            "reference": record.provenance.reference,
            "payload_hash": record.provenance.payload_hash,
        },
        "source_excerpt": dict(record.source_excerpt),
    }


def _missed_entry(missed: MissedSnapshot) -> dict[str, object]:
    return {
        "kind": "missed",
        "number": missed.number,
        "candidate_id": missed.candidate_id,
        "candidate_key": missed.candidate_key,
        "event_id": missed.event_id,
        "reason": missed.reason.value,
        "recorded_at": _timestamp(missed.recorded_at),
    }


def _decode_snapshot(entry: Mapping[str, object]) -> SnapshotEvidence:
    expected = {
        "kind",
        "number",
        "candidate_id",
        "candidate_key",
        "evidence_mode",
        "event_id",
        "event_start",
        "target_at",
        "late",
        "recorded_at",
        "observation",
        "provenance",
        "source_excerpt",
    }
    if set(entry) != expected:
        raise SnapshotError("snapshot ledger entry has unknown or missing fields")
    observation_data = entry["observation"]
    provenance_data = entry["provenance"]
    excerpt = entry["source_excerpt"]
    if not isinstance(observation_data, dict) or not isinstance(provenance_data, dict):
        raise SnapshotError("snapshot observation or provenance is malformed")
    if not isinstance(excerpt, dict):
        raise SnapshotError("snapshot source excerpt is malformed")
    if set(observation_data) != {
        "platform",
        "player",
        "category",
        "projection",
        "direction",
        "event",
        "source_update_time",
        "retrieved_at",
        "snapshot_number",
        "source",
        "multiplier",
    }:
        raise SnapshotError("snapshot observation has unknown or missing fields")
    if set(provenance_data) != {
        "source",
        "retrieved_at",
        "source_timestamp",
        "access_method",
        "reference",
        "payload_hash",
    }:
        raise SnapshotError("snapshot provenance has unknown or missing fields")
    number = entry["number"]
    candidate_id = entry["candidate_id"]
    candidate_key = entry["candidate_key"]
    evidence_mode_value = entry["evidence_mode"]
    event_id = entry["event_id"]
    late = entry["late"]
    target_at = entry["target_at"]
    if isinstance(number, bool) or not isinstance(number, int):
        raise SnapshotError("snapshot number must be an integer")
    if not isinstance(candidate_id, str) or not isinstance(candidate_key, str):
        raise SnapshotError("snapshot ledger candidate identity is malformed")
    try:
        evidence_mode = EvidenceMode(evidence_mode_value)
    except (TypeError, ValueError) as exc:
        raise SnapshotError("snapshot evidence mode is invalid") from exc
    if evidence_mode not in (EvidenceMode.LIVE, EvidenceMode.FIXTURE):
        raise SnapshotError("snapshot evidence mode is not identified as live or fixture")
    if not isinstance(event_id, str) or not isinstance(late, bool):
        raise SnapshotError("snapshot ledger event or late flag is malformed")
    if target_at is not None and not isinstance(target_at, str):
        raise SnapshotError("snapshot target_at is malformed")
    try:
        observation = Observation(
            platform=Platform(observation_data["platform"]),
            player=observation_data["player"],
            category=Category(observation_data["category"]),
            projection=observation_data["projection"],
            direction=Direction(observation_data["direction"]),
            event=observation_data["event"],
            source_update_time=_parse_timestamp(
                observation_data["source_update_time"], "source_update_time"
            ),
            retrieved_at=_parse_timestamp(observation_data["retrieved_at"], "retrieved_at"),
            snapshot_number=observation_data["snapshot_number"],
            source=observation_data["source"],
            multiplier=observation_data["multiplier"],
        )
        snapshot = Snapshot(
            number=number,
            observation=observation,
            recorded_at=_parse_timestamp(entry["recorded_at"], "recorded_at"),
        )
        provenance = Provenance(
            source=provenance_data["source"],
            retrieved_at=_parse_timestamp(
                provenance_data["retrieved_at"], "provenance.retrieved_at"
            ),
            source_timestamp=_parse_timestamp(
                provenance_data["source_timestamp"], "provenance.source_timestamp"
            ),
            access_method=provenance_data["access_method"],
            reference=provenance_data["reference"],
            payload_hash=provenance_data["payload_hash"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SnapshotError("snapshot ledger entry contains invalid typed values") from exc
    if any(
        not isinstance(key, str) or not isinstance(value, (str, float, int))
        for key, value in excerpt.items()
    ):
        raise SnapshotError("snapshot source excerpt contains unsupported values")
    return SnapshotEvidence(
        snapshot=snapshot,
        candidate_id=candidate_id,
        candidate_key=candidate_key,
        evidence_mode=evidence_mode,
        event_id=event_id,
        event_start=_parse_timestamp(entry["event_start"], "event_start"),
        target_at=(None if target_at is None else _parse_timestamp(target_at, "target_at")),
        late=late,
        provenance=provenance,
        source_excerpt=excerpt,
    )


def _decode_missed(entry: Mapping[str, object]) -> MissedSnapshot:
    if set(entry) != {
        "kind",
        "number",
        "candidate_id",
        "candidate_key",
        "event_id",
        "reason",
        "recorded_at",
    }:
        raise SnapshotError("missed snapshot ledger entry has unknown or missing fields")
    try:
        reason = ReasonCode(entry["reason"])
    except (TypeError, ValueError) as exc:
        raise SnapshotError("missed snapshot reason is invalid") from exc
    number = entry["number"]
    candidate_id = entry["candidate_id"]
    candidate_key = entry["candidate_key"]
    event_id = entry["event_id"]
    if isinstance(number, bool) or not isinstance(number, int):
        raise SnapshotError("missed snapshot number must be an integer")
    if not isinstance(candidate_id, str):
        raise SnapshotError("missed snapshot candidate_id is malformed")
    if not isinstance(candidate_key, str):
        raise SnapshotError("missed snapshot candidate_key is malformed")
    if not isinstance(event_id, str):
        raise SnapshotError("missed snapshot identity is malformed")
    return MissedSnapshot(
        number=number,
        candidate_id=candidate_id,
        candidate_key=candidate_key,
        event_id=event_id,
        reason=reason,
        recorded_at=_parse_timestamp(entry["recorded_at"], "recorded_at"),
    )


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        with suppress(OSError):
            temporary_path.unlink(missing_ok=True)
        raise


def _snapshot_ledger_path(store: RunStore, run_id: str) -> Path:
    _validate_run_id(run_id)
    root = store.root
    run_directory = (root / RUNS_DIRECTORY / run_id).resolve()
    if not run_directory.is_relative_to(root):
        raise SnapshotError("snapshot run directory escapes the storage root")
    path = run_directory / SNAPSHOTS_DIRECTORY / SNAPSHOTS_FILENAME
    if not path.resolve().is_relative_to(run_directory):
        raise SnapshotError("snapshot ledger path escapes the run directory")
    return path


def read_snapshot_ledger(
    store: RunStore,
    run_id: str,
) -> tuple[SnapshotEvidence | MissedSnapshot, ...]:
    """Read and validate one M5 ledger without dispatching through a workflow instance."""

    if type(store) is not RunStore:
        raise SnapshotError("snapshot ledger access requires the M5 RunStore")
    path = _snapshot_ledger_path(store, run_id)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return ()
    except OSError as exc:
        raise SnapshotError(f"cannot read snapshot ledger for run {run_id!r}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SnapshotError("snapshot ledger is not valid UTF-8") from exc
    entries: list[SnapshotEvidence | MissedSnapshot] = []
    seen: set[tuple[int, str]] = set()
    event_starts: dict[str, datetime] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise SnapshotError(f"snapshot ledger has a blank line at {line_number}")
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SnapshotError(f"snapshot ledger has invalid JSON at line {line_number}") from exc
        if not isinstance(item, dict):
            raise SnapshotError(f"snapshot ledger line {line_number} is not an object")
        decoded = _decode_entry(item)
        number = (
            decoded.snapshot.number if isinstance(decoded, SnapshotEvidence) else decoded.number
        )
        entry_identity = (number, decoded.candidate_key)
        if entry_identity in seen:
            raise SnapshotError("snapshot ledger contains a duplicate slot and candidate key")
        if isinstance(decoded, SnapshotEvidence):
            known_start = event_starts.get(decoded.event_id)
            if known_start is not None and decoded.event_start != known_start:
                raise SnapshotError("snapshot ledger event tipoff changed between slots")
            event_starts[decoded.event_id] = decoded.event_start
        seen.add(entry_identity)
        entries.append(decoded)
    _validate_ledger_order(entries)
    return tuple(entries)


def _expected_snapshot_receipt(
    run_id: str,
    entry: SnapshotEvidence | MissedSnapshot,
) -> dict[str, str | None]:
    if isinstance(entry, SnapshotEvidence):
        number = entry.snapshot.number
        timestamp = _timestamp(entry.snapshot.recorded_at)
        event = "SNAPSHOT_LATE" if entry.late else "SNAPSHOT_ACCEPTED"
        result = "RECORDED"
        source = entry.provenance.source
        reason = None
        event_key = f"snapshot-accepted-{number}-{entry.candidate_key}"
    else:
        number = entry.number
        timestamp = _timestamp(entry.recorded_at)
        event = "SNAPSHOT_MISSED"
        result = "MISSED"
        source = SOURCE_ID
        reason = entry.reason.value
        event_key = f"snapshot-missed-{number}-{entry.candidate_key}"
    return Receipt(
        timestamp=timestamp,
        event=event,
        result=result,
        subject=entry.candidate_key,
        source=source,
        reason=reason,
        run_id=run_id,
        event_key=event_key,
    ).to_dict()


def read_application_snapshot_ledger(
    run_id: str,
) -> tuple[SnapshotEvidence | MissedSnapshot, ...]:
    """Read LIVE evidence from the configured M5 store and require its receipts."""

    store = application_run_store()
    entries = read_snapshot_ledger(store, run_id)
    receipts = store.read_receipts(run_id)
    for entry in entries:
        expected = _expected_snapshot_receipt(run_id, entry)
        matches = tuple(
            receipt for receipt in receipts if receipt.get("event_key") == expected["event_key"]
        )
        if matches != (expected,):
            raise SnapshotError("M5 snapshot ledger record has no matching run receipt")
    return entries


class SnapshotWorkflow:
    """Collect authorized source-board observations into an append-only snapshot ledger."""

    def __init__(
        self,
        store: RunStore,
        resolver: IdentityResolver,
        authorization: AuthorizationGate,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(store, RunStore):
            raise SnapshotError("store must be a RunStore")
        if not isinstance(resolver, IdentityResolver):
            raise SnapshotError("resolver must be an IdentityResolver")
        if not isinstance(authorization, AuthorizationGate):
            raise SnapshotError("authorization must be an AuthorizationGate")
        self._store = store
        self._resolver = resolver
        self._authorization = authorization
        self._registry = Registry.from_universe(load_configs().approved_universe)
        self._clock = (lambda: datetime.now(UTC)) if clock is None else clock

    def collect(self, run_id: str, number: int, board: SourceBoard) -> tuple[SnapshotEvidence, ...]:
        """Persist a slot from one legitimate M4 board; never overwrite a prior slot."""

        if isinstance(number, bool) or not isinstance(number, int) or number not in (1, 2, 3):
            raise SnapshotError("snapshot number must be 1, 2, or 3")
        if not isinstance(board, SourceBoard):
            raise SnapshotError("snapshot collection requires a SourceBoard")
        now = self._clock()
        _require_aware(now, "clock")
        self._validate_board(board, now)
        entries = self._read_entries(run_id)
        events = {event.event_id: event for event in board.events}
        if not board.projections:
            self._reject(run_id, number, "no-projections", now, result="PROJECTION_UNAVAILABLE")
            if number in (2, 3):
                self._record_absent_candidates(run_id, number, now, events, entries, set())
            return ()

        collected: list[SnapshotEvidence] = []
        seen_keys: set[str] = set()
        for projection in board.projections:
            event = events[projection.event_id]
            resolved = self._resolver.resolve_provider(projection.provider_player_name)
            if not resolved.resolved or resolved.player is None:
                rejected_key = _candidate_key(
                    event_id=projection.event_id,
                    platform=projection.platform,
                    candidate_id=hashlib.sha256(
                        projection.provider_player_name.encode("utf-8")
                    ).hexdigest(),
                    category=projection.category,
                    direction=projection.direction,
                )
                self._reject(
                    run_id,
                    number,
                    rejected_key,
                    now,
                    result="IDENTITY_UNRESOLVED",
                    reason=ReasonCode.PLAYER_IDENTITY_UNRESOLVED,
                )
                continue

            player = resolved.player
            approved_player = self._registry.player_by_id(player.player_id)
            if approved_player is None or player != approved_player:
                rejected_key = _candidate_key(
                    event_id=projection.event_id,
                    platform=projection.platform,
                    candidate_id=hashlib.sha256(player.player_id.encode("utf-8")).hexdigest(),
                    category=projection.category,
                    direction=projection.direction,
                )
                self._reject(
                    run_id,
                    number,
                    rejected_key,
                    now,
                    result="IDENTITY_UNRESOLVED",
                    reason=ReasonCode.PLAYER_IDENTITY_UNRESOLVED,
                )
                continue
            player = approved_player
            decision = self._authorization.authorize(
                player.player_id,
                projection.category,
                projection.direction,
            )
            if not decision.allowed:
                key = _candidate_key(
                    event_id=projection.event_id,
                    platform=projection.platform,
                    candidate_id=player.player_id,
                    category=projection.category,
                    direction=projection.direction,
                )
                self._reject(
                    run_id,
                    number,
                    key,
                    now,
                    result="NOT_AUTHORIZED",
                    reason=decision.reason,
                )
                continue

            key = _candidate_key(
                event_id=projection.event_id,
                platform=projection.platform,
                candidate_id=player.player_id,
                category=projection.category,
                direction=projection.direction,
            )
            previous_event_start = next(
                (
                    item.event_start
                    for item in entries
                    if isinstance(item, SnapshotEvidence) and item.event_id == projection.event_id
                ),
                None,
            )
            if previous_event_start is not None and previous_event_start != event.commence_time:
                self._reject(
                    run_id,
                    number,
                    key,
                    now,
                    result="EVENT_TIPOFF_CHANGED",
                    reason=ReasonCode.SOURCE_CONFLICT_UNRESOLVED,
                )
                continue
            seen_keys.add(key)
            current = self._find_snapshot(entries, number, key)
            missed = self._find_missed(entries, number, key)
            if current is not None:
                if current.event_start != event.commence_time:
                    self._reject(
                        run_id,
                        number,
                        key,
                        now,
                        result="EVENT_TIPOFF_CHANGED",
                        reason=ReasonCode.SOURCE_CONFLICT_UNRESOLVED,
                    )
                    continue
                self._ensure_recorded_receipt(run_id, current)
                self._duplicate_receipt(run_id, number, key, now)
                collected.append(current)
                continue
            if missed is not None:
                self._missed_receipt(run_id, missed)
                self._reject(
                    run_id,
                    number,
                    key,
                    now,
                    result="MISSED_NOT_BACKFILLED",
                    reason=ReasonCode.PROJECTION_OBSERVATION_MISSED,
                )
                continue

            first = self._find_snapshot(entries, 1, key)
            if number > 1 and first is None:
                self._reject(run_id, number, key, now, result="OUT_OF_ORDER")
                continue
            if first is not None and first.event_start != event.commence_time:
                self._reject(
                    run_id,
                    number,
                    key,
                    now,
                    result="EVENT_TIPOFF_CHANGED",
                    reason=ReasonCode.SOURCE_CONFLICT_UNRESOLVED,
                )
                continue

            target_at: datetime | None = None
            late = False
            if number == 1 and (
                now >= event.commence_time or projection.retrieved_at >= event.commence_time
            ):
                missed_entry = self._record_missed(
                    run_id,
                    1,
                    player.player_id,
                    key,
                    projection.event_id,
                    ReasonCode.PROJECTION_OBSERVATION_MISSED,
                    now,
                    entries,
                )
                entries.append(missed_entry)
                continue
            if number == 2:
                assert first is not None
                if now < first.snapshot.recorded_at:
                    self._reject(run_id, number, key, now, result="OUT_OF_ORDER")
                    continue
                latest_at = first.event_start - T20_OFFSET - SNAPSHOT_2_T20_GAP
                target_at = snapshot_2_target(
                    first.snapshot.observation.retrieved_at,
                    first.event_start,
                )
                if target_at is None:
                    missed_entry = self._record_missed(
                        run_id,
                        2,
                        first.candidate_id,
                        key,
                        first.event_id,
                        ReasonCode.SNAPSHOT_2_MISSED,
                        now,
                        entries,
                    )
                    entries.append(missed_entry)
                    continue
                if now > latest_at:
                    missed_entry = self._record_missed(
                        run_id,
                        2,
                        first.candidate_id,
                        key,
                        first.event_id,
                        ReasonCode.SNAPSHOT_2_MISSED,
                        now,
                        entries,
                    )
                    entries.append(missed_entry)
                    continue
                if projection.retrieved_at <= first.snapshot.observation.retrieved_at:
                    self._reject(run_id, number, key, now, result="OUT_OF_ORDER")
                    continue
                minimum_elapsed = projection.retrieved_at - first.snapshot.observation.retrieved_at
                minimum_is_possible = (
                    latest_at - first.snapshot.observation.retrieved_at
                    >= SNAPSHOT_2_MINIMUM_SEPARATION
                )
                if minimum_is_possible and projection.retrieved_at < target_at:
                    self._reject(run_id, number, key, now, result="NOT_DUE")
                    continue
                if projection.retrieved_at > latest_at:
                    missed_entry = self._record_missed(
                        run_id,
                        2,
                        first.candidate_id,
                        key,
                        first.event_id,
                        ReasonCode.SNAPSHOT_2_MISSED,
                        now,
                        entries,
                    )
                    entries.append(missed_entry)
                    continue
                if minimum_is_possible and minimum_elapsed < SNAPSHOT_2_MINIMUM_SEPARATION:
                    self._reject(run_id, number, key, now, result="NOT_DUE")
                    continue
            elif number == 3:
                assert first is not None
                second = self._find_snapshot(entries, 2, key)
                second_missed = self._find_missed(entries, 2, key)
                second_recorded_at = (
                    second.snapshot.recorded_at
                    if second is not None
                    else (None if second_missed is None else second_missed.recorded_at)
                )
                if second_recorded_at is not None and now < second_recorded_at:
                    self._reject(run_id, number, key, now, result="OUT_OF_ORDER")
                    continue
                latest_at = first.event_start - T20_OFFSET - SNAPSHOT_2_T20_GAP
                if second is None and second_missed is None:
                    if now >= latest_at:
                        missed_entry = self._record_missed(
                            run_id,
                            2,
                            first.candidate_id,
                            key,
                            first.event_id,
                            ReasonCode.SNAPSHOT_2_MISSED,
                            now,
                            entries,
                        )
                        entries.append(missed_entry)
                    else:
                        self._reject(run_id, number, key, now, result="OUT_OF_ORDER")
                        continue
                target_at = first.event_start - T20_OFFSET
                window_start = first.event_start - SNAPSHOT_3_EARLY_WINDOW
                if now >= first.event_start or projection.retrieved_at >= first.event_start:
                    missed_entry = self._record_missed(
                        run_id,
                        3,
                        first.candidate_id,
                        key,
                        first.event_id,
                        ReasonCode.PROJECTION_OBSERVATION_MISSED,
                        now,
                        entries,
                    )
                    entries.append(missed_entry)
                    continue
                if projection.retrieved_at <= first.snapshot.observation.retrieved_at:
                    self._reject(run_id, number, key, now, result="OUT_OF_ORDER")
                    continue
                if (
                    second is not None
                    and projection.retrieved_at <= second.snapshot.observation.retrieved_at
                ):
                    self._reject(run_id, number, key, now, result="OUT_OF_ORDER")
                    continue
                if now < window_start or projection.retrieved_at < window_start:
                    self._reject(run_id, number, key, now, result="NOT_DUE")
                    continue
                late = now > target_at or projection.retrieved_at > target_at

            record = self._build_evidence(
                number=number,
                key=key,
                player=player,
                projection=projection,
                event_start=event.commence_time,
                board=board,
                now=now,
                target_at=target_at,
                late=late,
            )
            self._append_entry(run_id, _snapshot_entry(record), entries)
            entries.append(record)
            self._accepted_receipt(run_id, record)
            collected.append(record)

            if (
                number == 1
                and snapshot_2_target(projection.retrieved_at, event.commence_time) is None
            ):
                missed_entry = self._record_missed(
                    run_id,
                    2,
                    player.player_id,
                    key,
                    projection.event_id,
                    ReasonCode.SNAPSHOT_2_MISSED,
                    now,
                    entries,
                )
                entries.append(missed_entry)

        if number in (2, 3):
            self._record_absent_candidates(
                run_id,
                number,
                now,
                events,
                entries,
                seen_keys,
            )
        return tuple(collected)

    def mark_snapshot_2_missed(self, run_id: str, event_id: str) -> tuple[MissedSnapshot, ...]:
        """Record expired Snapshot 2 slots for all Snapshot 1 lines in one event."""

        now = self._clock()
        _require_aware(now, "clock")
        entries = self._read_entries(run_id)
        missed_records: list[MissedSnapshot] = []
        for first in tuple(
            item
            for item in entries
            if isinstance(item, SnapshotEvidence)
            and item.snapshot.number == 1
            and item.event_id == event_id
        ):
            if self._find_snapshot(entries, 2, first.candidate_key) is not None:
                continue
            existing_missed = self._find_missed(entries, 2, first.candidate_key)
            if existing_missed is not None:
                self._missed_receipt(run_id, existing_missed)
                continue
            latest_at = first.event_start - T20_OFFSET - SNAPSHOT_2_T20_GAP
            if (
                snapshot_2_target(first.snapshot.observation.retrieved_at, first.event_start)
                is not None
                and now < latest_at
            ):
                self._reject(run_id, 2, first.candidate_key, now, result="NOT_MISSED_YET")
                continue
            missed_entry = self._record_missed(
                run_id,
                2,
                first.candidate_id,
                first.candidate_key,
                first.event_id,
                ReasonCode.SNAPSHOT_2_MISSED,
                now,
                entries,
            )
            entries.append(missed_entry)
            missed_records.append(missed_entry)
        return tuple(missed_records)

    def read(self, run_id: str) -> tuple[SnapshotEvidence, ...]:
        """Return persisted observations in append order."""

        return tuple(
            item for item in self._read_entries(run_id) if isinstance(item, SnapshotEvidence)
        )

    def read_missed(self, run_id: str) -> tuple[MissedSnapshot, ...]:
        """Return persisted missed-slot records in append order."""

        return tuple(
            item for item in self._read_entries(run_id) if isinstance(item, MissedSnapshot)
        )

    def _validate_board(self, board: SourceBoard, now: datetime) -> None:
        provenance = board.provenance
        if (
            provenance.source_id != SOURCE_ID
            or provenance.region != APPROVED_REGION
            or provenance.bookmakers != APPROVED_BOOKMAKERS
            or provenance.markets != APPROVED_MARKETS
        ):
            raise SnapshotError("board does not match the approved M4 source configuration")
        if not isinstance(
            provenance.evidence_mode, EvidenceMode
        ) or provenance.evidence_mode not in (
            EvidenceMode.LIVE,
            EvidenceMode.FIXTURE,
        ):
            raise SnapshotError("board evidence mode is not identified as live or fixture")
        if _SHA256_PATTERN.fullmatch(provenance.payload_sha256) is None:
            raise SnapshotError("board payload_sha256 is invalid")
        _require_aware(provenance.request_timestamp, "request_timestamp")
        _require_aware(provenance.retrieved_at, "board retrieved_at")
        if provenance.request_timestamp > provenance.retrieved_at or provenance.retrieved_at > now:
            raise SnapshotError("board timestamps are inconsistent with collection time")
        for event in board.events:
            _require_aware(event.commence_time, "event commence_time")
            for projection in event.projections:
                _require_aware(projection.retrieved_at, "projection retrieved_at")
                _require_aware(projection.source_update_time, "projection source_update_time")
                if projection.source_update_time > projection.retrieved_at:
                    raise SnapshotError("source update time cannot be later than its retrieval")
                if (
                    projection.retrieved_at > provenance.retrieved_at
                    or projection.retrieved_at > now
                    or projection.retrieved_at < provenance.request_timestamp
                ):
                    raise SnapshotError("projection retrieval time is inconsistent with the board")

    def _build_evidence(
        self,
        *,
        number: int,
        key: str,
        player: RegistryPlayer,
        projection: SourceProjection,
        event_start: datetime,
        board: SourceBoard,
        now: datetime,
        target_at: datetime | None,
        late: bool,
    ) -> SnapshotEvidence:
        observation = Observation(
            platform=projection.platform,
            player=player.canonical_name,
            category=projection.category,
            projection=projection.projection,
            direction=projection.direction,
            event=projection.event_id,
            source_update_time=projection.source_update_time,
            retrieved_at=projection.retrieved_at,
            snapshot_number=number,
            source=board.provenance.source_id,
        )
        snapshot = Snapshot(number=number, observation=observation, recorded_at=now)
        provenance = Provenance(
            source=board.provenance.source_id,
            retrieved_at=projection.retrieved_at,
            source_timestamp=projection.source_update_time,
            access_method=(
                "https-get-x-api-key-header"
                if board.provenance.evidence_mode is EvidenceMode.LIVE
                else "synthetic-fixture-transport"
            ),
            reference=f"{board.provenance.source_id}:event:{projection.event_id}",
            payload_hash=board.provenance.payload_sha256,
        )
        excerpt: Mapping[str, str | float] = {
            "platform": projection.platform.value,
            "provider_player_name": projection.provider_player_name,
            "category": projection.category.value,
            "projection": projection.projection,
            "direction": projection.direction.value,
            "event_id": projection.event_id,
            "source_update_time": _timestamp(projection.source_update_time),
            "retrieved_at": _timestamp(projection.retrieved_at),
        }
        return SnapshotEvidence(
            snapshot=snapshot,
            candidate_id=player.player_id,
            candidate_key=key,
            evidence_mode=board.provenance.evidence_mode,
            event_id=projection.event_id,
            event_start=event_start,
            target_at=target_at,
            late=late,
            provenance=provenance,
            source_excerpt=excerpt,
        )

    def _record_absent_candidates(
        self,
        run_id: str,
        number: int,
        now: datetime,
        events: Mapping[str, SourceEvent],
        entries: list[SnapshotEvidence | MissedSnapshot],
        seen_keys: set[str],
    ) -> None:
        for first in tuple(
            item
            for item in entries
            if isinstance(item, SnapshotEvidence)
            and item.snapshot.number == 1
            and item.candidate_key not in seen_keys
        ):
            if self._find_snapshot(entries, number, first.candidate_key) is not None:
                continue
            if self._find_missed(entries, number, first.candidate_key) is not None:
                continue
            event = events.get(first.event_id)
            if event is not None and event.commence_time != first.event_start:
                self._reject(
                    run_id,
                    number,
                    first.candidate_key,
                    now,
                    result="EVENT_TIPOFF_CHANGED",
                    reason=ReasonCode.SOURCE_CONFLICT_UNRESOLVED,
                )
                continue
            if (
                number == 3
                and self._find_snapshot(entries, 2, first.candidate_key) is None
                and self._find_missed(entries, 2, first.candidate_key) is None
            ):
                latest_second = first.event_start - T20_OFFSET - SNAPSHOT_2_T20_GAP
                if (
                    snapshot_2_target(first.snapshot.observation.retrieved_at, first.event_start)
                    is None
                    or now >= latest_second
                ):
                    missed_second = self._record_missed(
                        run_id,
                        2,
                        first.candidate_id,
                        first.candidate_key,
                        first.event_id,
                        ReasonCode.SNAPSHOT_2_MISSED,
                        now,
                        entries,
                    )
                    entries.append(missed_second)
            if number == 2:
                target_at = snapshot_2_target(
                    first.snapshot.observation.retrieved_at, first.event_start
                )
                latest_at = first.event_start - T20_OFFSET - SNAPSHOT_2_T20_GAP
                if target_at is not None and now < latest_at:
                    self._reject(
                        run_id,
                        number,
                        first.candidate_key,
                        now,
                        result="PROJECTION_UNAVAILABLE",
                        reason=ReasonCode.PROJECTION_UNAVAILABLE,
                    )
                    continue
                reason = ReasonCode.SNAPSHOT_2_MISSED
            else:
                if now < first.event_start - SNAPSHOT_3_EARLY_WINDOW:
                    continue
                if now < first.event_start:
                    self._reject(
                        run_id,
                        number,
                        first.candidate_key,
                        now,
                        result="PROJECTION_UNAVAILABLE",
                        reason=ReasonCode.PROJECTION_UNAVAILABLE,
                    )
                    continue
                reason = ReasonCode.PROJECTION_OBSERVATION_MISSED
            missed_entry = self._record_missed(
                run_id,
                number,
                first.candidate_id,
                first.candidate_key,
                first.event_id,
                reason,
                now,
                entries,
            )
            entries.append(missed_entry)

    def _record_missed(
        self,
        run_id: str,
        number: int,
        candidate_id: str,
        key: str,
        event_id: str,
        reason: ReasonCode,
        now: datetime,
        entries: list[SnapshotEvidence | MissedSnapshot],
    ) -> MissedSnapshot:
        existing = self._find_missed(entries, number, key)
        if existing is not None:
            self._missed_receipt(run_id, existing)
            return existing
        missed = MissedSnapshot(
            number=number,
            candidate_id=candidate_id,
            candidate_key=key,
            event_id=event_id,
            reason=reason,
            recorded_at=now,
        )
        self._append_entry(run_id, _missed_entry(missed), entries)
        self._missed_receipt(run_id, missed)
        return missed

    def _append_entry(
        self,
        run_id: str,
        entry: dict[str, object],
        existing: list[SnapshotEvidence | MissedSnapshot],
    ) -> None:
        path = self._ledger_path(run_id)
        updated_entries = [*existing, _decode_entry(entry)]
        _validate_ledger_order(updated_entries)
        content = "".join(
            json.dumps(_entry_dict(item), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in updated_entries
        )
        try:
            _atomic_write(path, content.encode("utf-8"))
        except OSError as exc:
            raise SnapshotError(f"cannot write snapshot ledger for run {run_id!r}") from exc

    def _read_entries(self, run_id: str) -> list[SnapshotEvidence | MissedSnapshot]:
        return list(read_snapshot_ledger(self._store, run_id))

    def _ledger_path(self, run_id: str) -> Path:
        return _snapshot_ledger_path(self._store, run_id)

    def _accepted_receipt(self, run_id: str, record: SnapshotEvidence) -> None:
        event = "SNAPSHOT_LATE" if record.late else "SNAPSHOT_ACCEPTED"
        self._append_receipt(
            Receipt(
                timestamp=_timestamp(record.snapshot.recorded_at),
                event=event,
                result="RECORDED",
                subject=record.candidate_key,
                source=record.provenance.source,
                reason=None,
                run_id=run_id,
                event_key=f"snapshot-accepted-{record.snapshot.number}-{record.candidate_key}",
            )
        )

    def _ensure_recorded_receipt(self, run_id: str, record: SnapshotEvidence) -> None:
        self._accepted_receipt(run_id, record)

    def _duplicate_receipt(self, run_id: str, number: int, key: str, now: datetime) -> None:
        attempt = hashlib.sha256(_timestamp(now).encode("utf-8")).hexdigest()[:16]
        self._append_receipt(
            Receipt(
                timestamp=_timestamp(now),
                event="SNAPSHOT_DUPLICATE",
                result="EXISTING",
                subject=key,
                source=SOURCE_ID,
                reason=None,
                run_id=run_id,
                event_key=f"snapshot-duplicate-{number}-{key}-{attempt}",
            )
        )

    def _missed_receipt(self, run_id: str, missed: MissedSnapshot) -> None:
        self._append_receipt(
            Receipt(
                timestamp=_timestamp(missed.recorded_at),
                event="SNAPSHOT_MISSED",
                result="MISSED",
                subject=missed.candidate_key,
                source=SOURCE_ID,
                reason=missed.reason.value,
                run_id=run_id,
                event_key=f"snapshot-missed-{missed.number}-{missed.candidate_key}",
            )
        )

    def _reject(
        self,
        run_id: str,
        number: int,
        key: str,
        now: datetime,
        *,
        result: str,
        reason: ReasonCode | None = None,
    ) -> None:
        reason_text = "" if reason is None else reason.value
        attempt = hashlib.sha256(
            f"{number}|{key}|{result}|{reason_text}|{_timestamp(now)}".encode()
        ).hexdigest()[:16]
        self._append_receipt(
            Receipt(
                timestamp=_timestamp(now),
                event="SNAPSHOT_REJECTED",
                result=result,
                subject=key,
                source=SOURCE_ID,
                reason=None if reason is None else reason.value,
                run_id=run_id,
                event_key=f"snapshot-rejected-{number}-{attempt}",
            )
        )

    def _append_receipt(self, receipt: Receipt) -> None:
        self._store.append_receipt(receipt)

    @staticmethod
    def _find_snapshot(
        entries: list[SnapshotEvidence | MissedSnapshot], number: int, key: str
    ) -> SnapshotEvidence | None:
        return next(
            (
                item
                for item in entries
                if isinstance(item, SnapshotEvidence)
                and item.snapshot.number == number
                and item.candidate_key == key
            ),
            None,
        )

    @staticmethod
    def _find_missed(
        entries: list[SnapshotEvidence | MissedSnapshot], number: int, key: str
    ) -> MissedSnapshot | None:
        return next(
            (
                item
                for item in entries
                if isinstance(item, MissedSnapshot)
                and item.number == number
                and item.candidate_key == key
            ),
            None,
        )


def _decode_entry(entry: Mapping[str, object]) -> SnapshotEvidence | MissedSnapshot:
    if entry.get("kind") == "snapshot":
        return _decode_snapshot(entry)
    if entry.get("kind") == "missed":
        return _decode_missed(entry)
    raise SnapshotError("snapshot ledger entry has an unknown kind")


def _validate_ledger_order(entries: list[SnapshotEvidence | MissedSnapshot]) -> None:
    states: dict[str, dict[int, SnapshotEvidence | MissedSnapshot]] = {}
    for entry in entries:
        key = entry.candidate_key
        number = entry.snapshot.number if isinstance(entry, SnapshotEvidence) else entry.number
        state = states.setdefault(key, {})
        if number in state:
            raise SnapshotError("snapshot ledger repeats a candidate slot")

        if number == 1:
            if state:
                raise SnapshotError("Snapshot 1 must precede all other slots")
            state[1] = entry
            continue

        first = state.get(1)
        if not isinstance(first, SnapshotEvidence):
            raise SnapshotError("snapshot ledger slot has no accepted Snapshot 1")
        if entry.candidate_id != first.candidate_id or entry.event_id != first.event_id:
            raise SnapshotError("snapshot ledger candidate or event changed between slots")

        if number == 2:
            if isinstance(entry, SnapshotEvidence):
                first_at = first.snapshot.observation.retrieved_at
                observed_at = entry.snapshot.observation.retrieved_at
                latest_at = first.event_start - T20_OFFSET - SNAPSHOT_2_T20_GAP
                target_at = snapshot_2_target(first_at, first.event_start)
                minimum_is_possible = latest_at - first_at >= SNAPSHOT_2_MINIMUM_SEPARATION
                if (
                    target_at is None
                    or entry.target_at != target_at
                    or observed_at <= first_at
                    or observed_at > latest_at
                    or entry.snapshot.recorded_at < first.snapshot.recorded_at
                    or (
                        minimum_is_possible
                        and (
                            observed_at < target_at
                            or observed_at - first_at < SNAPSHOT_2_MINIMUM_SEPARATION
                        )
                    )
                ):
                    raise SnapshotError("persisted Snapshot 2 violates its schedule")
            else:
                latest_at = first.event_start - T20_OFFSET - SNAPSHOT_2_T20_GAP
                if entry.recorded_at < first.snapshot.recorded_at or (
                    snapshot_2_target(
                        first.snapshot.observation.retrieved_at,
                        first.event_start,
                    )
                    is not None
                    and entry.recorded_at < latest_at
                ):
                    raise SnapshotError("persisted missed Snapshot 2 precedes its deadline")
            state[2] = entry
            continue

        second = state.get(2)
        if not isinstance(second, (SnapshotEvidence, MissedSnapshot)):
            raise SnapshotError("persisted Snapshot 3 has no Snapshot 2 state")
        second_recorded_at = (
            second.snapshot.recorded_at
            if isinstance(second, SnapshotEvidence)
            else second.recorded_at
        )
        if isinstance(entry, SnapshotEvidence):
            observed_at = entry.snapshot.observation.retrieved_at
            if (
                observed_at <= first.snapshot.observation.retrieved_at
                or entry.snapshot.recorded_at < second_recorded_at
            ):
                raise SnapshotError("persisted Snapshot 3 is out of order")
            if (
                isinstance(second, SnapshotEvidence)
                and observed_at <= second.snapshot.observation.retrieved_at
            ):
                raise SnapshotError("Snapshot 3 observation must follow Snapshot 2")
        elif entry.recorded_at < second_recorded_at or entry.recorded_at < first.event_start:
            raise SnapshotError("persisted missed Snapshot 3 is out of order")
        state[3] = entry


def validate_snapshot_sequence(
    snapshots: tuple[SnapshotEvidence, ...],
    missed: tuple[MissedSnapshot, ...],
) -> tuple[SnapshotEvidence | MissedSnapshot, ...]:
    """Validate and order one candidate's records under the persisted M5 contract."""

    if not isinstance(snapshots, tuple) or any(
        not isinstance(item, SnapshotEvidence) for item in snapshots
    ):
        raise SnapshotError("snapshots must contain SnapshotEvidence records")
    if not isinstance(missed, tuple) or any(
        not isinstance(item, MissedSnapshot) for item in missed
    ):
        raise SnapshotError("missed must contain MissedSnapshot records")
    event_starts = {item.event_start for item in snapshots}
    if len(event_starts) > 1:
        raise SnapshotError("snapshot event start changed between slots")
    for item in snapshots:
        observation = item.snapshot.observation
        if (
            observation.source != SOURCE_ID
            or item.provenance.source != SOURCE_ID
            or item.provenance.reference != f"{SOURCE_ID}:event:{item.event_id}"
        ):
            raise SnapshotError("snapshot provenance does not match the approved M5 board source")

    entries = tuple(
        sorted(
            (*snapshots, *missed),
            key=lambda item: (
                item.snapshot.number if isinstance(item, SnapshotEvidence) else item.number,
                item.snapshot.recorded_at
                if isinstance(item, SnapshotEvidence)
                else item.recorded_at,
            ),
        )
    )
    _validate_ledger_order(list(entries))
    return entries


def _entry_dict(entry: SnapshotEvidence | MissedSnapshot) -> dict[str, object]:
    if isinstance(entry, SnapshotEvidence):
        return _snapshot_entry(entry)
    return _missed_entry(entry)
