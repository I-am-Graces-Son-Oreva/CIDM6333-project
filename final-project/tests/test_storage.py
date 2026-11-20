import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from fifth_pick.errors import ReceiptConflictError, StorageError, UnsafeRunIdError
from fifth_pick.receipts import REDACTION_MARKER, Receipt
from fifth_pick.storage import RECEIPTS_FILENAME, RUNS_DIRECTORY, RunStore

SECRET = "odds-secret-123"


def make_receipt(
    *,
    timestamp: str = "2026-11-15T17:00:00+00:00",
    event: str = "BOARD_RETRIEVED",
    result: str = "OK",
    subject: str = "nba:2026-11-15:lal-dal",
    source: str = "the-odds-api:us_dfs",
    reason: str | None = None,
    run_id: str = "run-20261115",
    event_key: str = "board-retrieved-1",
) -> Receipt:
    return Receipt(
        timestamp=timestamp,
        event=event,
        result=result,
        subject=subject,
        source=source,
        reason=reason,
        run_id=run_id,
        event_key=event_key,
    )


class RunStoreTests(unittest.TestCase):
    def test_run_directory_layout_is_deterministic(self) -> None:
        with TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            store = RunStore(root)
            run_directory = store.run_directory("run-20261115")

            self.assertEqual(run_directory, root.resolve() / RUNS_DIRECTORY / "run-20261115")
            self.assertEqual(
                store.receipts_path("run-20261115"),
                run_directory / RECEIPTS_FILENAME,
            )
            self.assertFalse(run_directory.exists())

    def test_run_id_cannot_escape_injected_root(self) -> None:
        with TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            store = RunStore(root)

            for run_id in ("", ".", "..", "../escape", "nested/run", "/absolute", "a\\b"):
                with self.subTest(run_id=run_id), self.assertRaises(UnsafeRunIdError):
                    store.run_directory(run_id)

    def test_resolved_run_path_must_stay_under_injected_root(self) -> None:
        with TemporaryDirectory() as temporary_root, TemporaryDirectory() as outside_root:
            root = Path(temporary_root)
            runs_directory = root / RUNS_DIRECTORY
            runs_directory.mkdir()
            (runs_directory / "escape").symlink_to(Path(outside_root), target_is_directory=True)

            store = RunStore(root)

            with self.assertRaises(UnsafeRunIdError):
                store.run_directory("escape")

    def test_duplicate_event_is_idempotent(self) -> None:
        with TemporaryDirectory() as temporary_root:
            store = RunStore(temporary_root)
            first = store.append_receipt(make_receipt())
            receipts_path = store.receipts_path("run-20261115")
            original_bytes = receipts_path.read_bytes()

            duplicate = make_receipt(timestamp="2026-11-15T17:05:00+00:00")
            second = store.append_receipt(duplicate)

            self.assertTrue(first.created)
            self.assertFalse(second.created)
            self.assertEqual(second.receipt, first.receipt)
            self.assertEqual(receipts_path.read_bytes(), original_bytes)
            self.assertEqual(len(store.read_receipts("run-20261115")), 1)

    def test_same_event_key_with_different_content_fails_closed(self) -> None:
        with TemporaryDirectory() as temporary_root:
            store = RunStore(temporary_root)
            store.append_receipt(make_receipt())
            receipts_path = store.receipts_path("run-20261115")
            original_bytes = receipts_path.read_bytes()

            with self.assertRaises(ReceiptConflictError):
                store.append_receipt(make_receipt(result="DIFFERENT"))

            self.assertEqual(receipts_path.read_bytes(), original_bytes)
            self.assertEqual(len(store.read_receipts("run-20261115")), 1)

    def test_different_event_keys_append(self) -> None:
        with TemporaryDirectory() as temporary_root:
            store = RunStore(temporary_root)
            store.append_receipt(make_receipt())
            result = store.append_receipt(
                make_receipt(event="PROJECTION_SNAPSHOT", event_key="snapshot-1")
            )

            self.assertTrue(result.created)
            self.assertEqual(len(store.read_receipts("run-20261115")), 2)

    def test_atomic_write_leaves_no_partial_file(self) -> None:
        with TemporaryDirectory() as temporary_root:
            store = RunStore(temporary_root)
            store.append_receipt(make_receipt())
            receipts_path = store.receipts_path("run-20261115")
            original_bytes = receipts_path.read_bytes()

            for failure_target in ("fifth_pick.storage.os.fsync", "fifth_pick.storage.os.replace"):
                with (
                    self.subTest(failure_target=failure_target),
                    mock.patch(failure_target, side_effect=OSError("injected failure")),
                    self.assertRaises(OSError),
                ):
                    store.append_receipt(
                        make_receipt(
                            event="PROJECTION_SNAPSHOT",
                            event_key="snapshot-1",
                        )
                    )

                    self.assertEqual(receipts_path.read_bytes(), original_bytes)
                    self.assertEqual(list(receipts_path.parent.glob(".*.tmp")), [])

    def test_appended_receipt_is_redacted(self) -> None:
        with TemporaryDirectory() as temporary_root:
            store = RunStore(temporary_root)
            source = f"https://api.test/odds?apiKey={SECRET}&regions=us_dfs"

            store.append_receipt(make_receipt(source=source), secrets=[SECRET])
            raw_receipts = store.receipts_path("run-20261115").read_text(encoding="utf-8")

            self.assertNotIn(SECRET, raw_receipts)
            self.assertIn(REDACTION_MARKER, raw_receipts)

    def test_malformed_receipt_log_fails_closed(self) -> None:
        with TemporaryDirectory() as temporary_root:
            store = RunStore(temporary_root)
            receipts_path = store.receipts_path("run-20261115")
            receipts_path.parent.mkdir(parents=True)
            receipts_path.write_text("{not-json}\n", encoding="utf-8")

            with self.assertRaises(StorageError):
                store.read_receipts("run-20261115")
            with self.assertRaises(StorageError):
                store.append_receipt(make_receipt())
