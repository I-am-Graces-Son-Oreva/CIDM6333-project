import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

GUARD_SCRIPT = Path(__file__).resolve().parents[1] / "guard" / "guard.py"


class GuardTests(unittest.TestCase):
    def _run_guard(
        self, root: Path, tool: str, args: Mapping[str, object]
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(GUARD_SCRIPT)],
            capture_output=True,
            check=False,
            cwd=root,
            input=json.dumps({"tool": tool, "args": dict(args)}),
            text=True,
        )

    def test_blocks_test_file_tools_and_writes_one_utc_receipt_each(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            calls = (
                ("edit", {"filePath": "tests/test_units.py"}),
                ("write", {"filePath": "tests/test_units.py"}),
                ("patch", {"patchText": "*** Update File: tests/test_units.py\n"}),
            )
            for tool, args in calls:
                result = self._run_guard(root, tool, args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("tests/", result.stdout)

            receipts = [
                json.loads(line)
                for line in (root / ".receipts" / "tool-calls.jsonl").read_text().splitlines()
            ]

        self.assertEqual(len(receipts), len(calls))
        for receipt in receipts:
            timestamp = datetime.fromisoformat(receipt["time"])
            self.assertEqual(timestamp.utcoffset(), UTC.utcoffset(None))
            self.assertEqual(receipt["decision"], "block")

    def test_blocks_test_paths_that_resolve_outside_through_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (tests_dir / "alias").symlink_to(outside, target_is_directory=True)

            result = self._run_guard(root, "write", {"filePath": "tests/alias/new_test.py"})

        self.assertEqual(result.returncode, 2, result.stderr)

    def test_blocks_shell_redirection_in_place_edits_and_tee(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            commands = (
                "printf 'bad' > tests/test_units.py",
                "printf 'bad' &> tests/test_units.py",
                "printf 'bad' &>> tests/test_units.py",
                "printf 'bad' >| tests/test_units.py",
                "python -c \"open('tests/test_units.py', 'w').write('bad')\"",
                "sed -i '' 's/273.15/273.2/' tests/test_units.py",
                "printf 'bad' | tee tests/test_units.py",
            )

            for command in commands:
                with self.subTest(command=command):
                    result = self._run_guard(root, "bash", {"command": command})
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("tests/", result.stdout)

    def test_allows_source_writes_test_reads_and_unrelated_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            calls = (
                ("write", {"filePath": "src/module.py"}),
                ("read", {"filePath": "tests/test_units.py"}),
                ("bash", {"command": "cat tests/test_units.py"}),
                ("bash", {"command": "python -c \"open('tests/test_units.py').read()\""}),
                ("bash", {"command": "uv run ruff format --check tests/test_units.py"}),
                ("bash", {"command": "printf 'log' > tests_backup/output.txt"}),
            )

            for tool, args in calls:
                result = self._run_guard(root, tool, args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")

            receipts = [
                json.loads(line)
                for line in (root / ".receipts" / "tool-calls.jsonl").read_text().splitlines()
            ]

        self.assertEqual([receipt["decision"] for receipt in receipts], ["allow"] * len(calls))
        self.assertEqual(receipts[0]["path"], "src/module.py")
        self.assertEqual(receipts[1]["path"], "tests/test_units.py")


if __name__ == "__main__":
    unittest.main()
