"""Deterministic run storage with atomic, idempotent receipt writes."""

import json
import os
import re
import stat
import tempfile
from collections.abc import Generator, Iterable
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from fifth_pick.errors import ReceiptConflictError, StorageError, UnsafeRunIdError
from fifth_pick.receipts import Receipt

RUNS_DIRECTORY: Final[str] = "runs"
RECEIPTS_FILENAME: Final[str] = "receipts.jsonl"
APPLICATION_STORAGE_ROOT: Final[Path] = Path(__file__).resolve().parents[3] / "var" / "fifth-pick"
_RUN_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True, slots=True)
class AppendResult:
    """The stored receipt and whether this call created a new line."""

    receipt: dict[str, str | None]
    created: bool


def _validate_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or _RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise UnsafeRunIdError(f"unsafe run id: {run_id!r}")


def _parse_receipts(raw: bytes, path: Path) -> tuple[dict[str, str | None], ...]:
    if not raw:
        return ()

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StorageError(f"{path} is not valid UTF-8") from exc

    receipts: list[dict[str, str | None]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise StorageError(f"{path} has a blank line at {line_number}")
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StorageError(f"{path} has invalid JSON at line {line_number}") from exc
        if not isinstance(data, dict):
            raise StorageError(f"{path} line {line_number} is not a JSON object")

        record: dict[str, str | None] = {}
        for key, value in data.items():
            if not isinstance(key, str) or (value is not None and not isinstance(value, str)):
                raise StorageError(f"{path} line {line_number} has an unsupported value")
            record[key] = value
        receipts.append(record)

    return tuple(receipts)


def _logical_record(record: dict[str, str | None]) -> str:
    return json.dumps(
        {key: value for key, value in record.items() if key != "timestamp"},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        with suppress(OSError):
            temporary_path.unlink(missing_ok=True)
        raise


class RunStore:
    """Run storage rooted at an injected directory."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def run_directory(self, run_id: str) -> Path:
        _validate_run_id(run_id)
        run_directory = (self._root / RUNS_DIRECTORY / run_id).resolve()
        if not run_directory.is_relative_to(self._root):
            raise UnsafeRunIdError(f"run id escapes storage root: {run_id!r}")
        return run_directory

    def receipts_path(self, run_id: str) -> Path:
        return self.run_directory(run_id) / RECEIPTS_FILENAME

    def read_receipts(self, run_id: str) -> tuple[dict[str, str | None], ...]:
        path = self.receipts_path(run_id)
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            return ()
        except OSError as exc:
            raise StorageError(f"cannot read {path}") from exc
        return _parse_receipts(raw, path)

    def append_receipt(
        self,
        receipt: Receipt,
        *,
        secrets: Iterable[str] = (),
    ) -> AppendResult:
        if not isinstance(receipt, Receipt):
            raise StorageError("receipt must be a Receipt")

        path = self.receipts_path(receipt.run_id)
        try:
            existing_raw = path.read_bytes()
        except FileNotFoundError:
            existing_raw = b""
        except OSError as exc:
            raise StorageError(f"cannot read {path}") from exc

        existing_receipts = _parse_receipts(existing_raw, path)
        new_record = receipt.redacted(secrets).to_dict()

        for existing in existing_receipts:
            if existing.get("event_key") != new_record["event_key"]:
                continue
            if existing.get("run_id") != new_record["run_id"]:
                raise StorageError(f"receipt run mismatch in {path}")
            if _logical_record(existing) == _logical_record(new_record):
                return AppendResult(receipt=dict(existing), created=False)
            raise ReceiptConflictError(
                f"event key {new_record['event_key']!r} already exists with different content"
            )

        line = json.dumps(
            new_record,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        content = existing_raw
        if content and not content.endswith(b"\n"):
            content += b"\n"
        content += (line + "\n").encode("utf-8")
        _atomic_write(path, content)

        return AppendResult(receipt=dict(new_record), created=True)


def application_run_store() -> RunStore:
    """Construct the application-owned operational store for `var/fifth-pick`."""

    return RunStore(APPLICATION_STORAGE_ROOT)


@contextmanager
def collection_lock(store: RunStore, run_id: str) -> Generator[None]:
    try:
        import fcntl
    except ImportError as exc:
        raise StorageError("safe collection locking is unavailable") from exc
    store.run_directory(run_id)
    directory = store.root / ".fixture-locks"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise StorageError("fixture lock directory must be private")
    with os.fdopen(
        os.open(directory / f"{run_id}.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600),
        "rb+",
    ) as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise StorageError("fixture lock must be a private regular file")
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
