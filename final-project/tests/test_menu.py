import io
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from fifth_pick.cli import main


class MenuEntryTests(unittest.TestCase):
    def test_menu_requires_an_interactive_terminal(self) -> None:
        with patch("sys.stdin", io.StringIO()), patch("sys.stderr", io.StringIO()) as stderr:
            self.assertEqual(main(["menu"]), 1)
        self.assertIn("interactive terminal", stderr.getvalue())


class TerminalNavigationTests(unittest.TestCase):
    def test_arrows_wrap_and_enter_selects(self) -> None:
        from fifth_pick.menu import Terminal

        terminal = Terminal()
        with patch.object(terminal, "key", side_effect=["up", "enter"]):
            self.assertEqual(terminal.choose("Menu", ("First", "Last")), 1)
        with patch.object(terminal, "key", side_effect=["down", "enter"]):
            self.assertEqual(terminal.choose("Menu", ("First", "Last")), 1)

    def test_escape_cancels_and_q_quits(self) -> None:
        from fifth_pick.menu import QuitMenu, Terminal

        terminal = Terminal()
        with patch.object(terminal, "key", return_value="escape"):
            self.assertIsNone(terminal.choose("Confirm", ("Cancel", "Continue")))
        with patch.object(terminal, "key", return_value=b"q"), self.assertRaises(QuitMenu):
            terminal.choose("Menu", ("First", "Last"))


class MenuWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        import fifth_pick.storage as storage

        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = storage.RunStore(Path(temporary.name) / "state")
        patcher = patch.object(storage, "APPLICATION_STORAGE_ROOT", self.store.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_menu(self, keys: list[str | bytes], answers: tuple[object, ...] = ()) -> str:
        from contextlib import redirect_stdout

        from fifth_pick.menu import Terminal

        stdout = io.StringIO()
        with (
            redirect_stdout(stdout),
            patch("sys.stdin.isatty", return_value=True),
            patch.object(stdout, "isatty", return_value=True),
            patch.object(Terminal, "_cbreak", return_value=nullcontext(0)),
            patch.object(Terminal, "key", side_effect=keys),
            patch.object(Terminal, "prompt", side_effect=answers),
        ):
            code = main(["menu", "--run-id", "demo-test"])
        self.assertEqual(code, 0)
        return stdout.getvalue()

    def test_default_cancel_and_escape_leave_run_untouched(self) -> None:
        output = self.run_menu(["enter", "enter", "enter", "escape", b"q"])
        self.assertIn("Cancelled before submitting the action", output)
        self.assertFalse(self.store.run_directory("demo-test").exists())

    def test_menu_delegates_fixture_actions_and_blocks_early_settlement(self) -> None:
        from fifth_pick.menu import Back
        from fifth_pick.models import Category
        from tests.m6_support import TIPOFF, candidate_key

        approve = ["down"] * 4 + ["enter", "down", "enter"]
        result = ["up"] * 3 + ["enter"]
        keys: list[str | bytes] = [
            "enter",
            "down",
            "enter",
            "escape",  # Snapshot 1
            "enter",
            "down",
            "enter",
            "escape",  # Snapshot 2
            "down",
            "enter",
            "escape",  # Provisional watchlist
            "down",
            "down",
            "enter",
            "down",
            "enter",
            "escape",  # T-20
            "down",
            "down",
            "down",
            "enter",
            "down",
            "enter",
            "escape",  # Final
            *result,
            "escape",  # No approval yet
            *approve,  # Cancel first decision form
            *approve,
            "escape",  # Explicitly approve on the second form
            *result,
            "enter",
            "down",
            "enter",
            "escape",  # Record synthetic result
            "up",
            "up",
            "enter",
            "escape",
            b"Q",  # Audit and quit
        ]
        key = candidate_key("Luka Doncic", category=Category.ASSISTS)
        output = self.run_menu(
            keys,
            (
                Back(),
                "APPROVE",
                "HIT",
                "synthetic-fixture",
                TIPOFF.isoformat(),
                f"fixture:results/{key}",
                "Synthetic PrizePicks Luka Doncic Assists Higher 9.5 settled HIT.",
                "YES",
            ),
        )
        for expected in (
            "Demo Mode",
            "Stage: 2/3 snapshots",
            "PROVISIONAL EVIDENCE WATCHLIST",
            "STILL STRONG",
            "ASSISTS HIGHER 9.5",
            "Settlement blocked",
            "Cancelled before submitting the action",
            "results recorded 1/1",
            "verified audit and receipts",
            "M4 boards: 3",
            "T-20 audit",
            "M8 exclusion",
            "RESULT_RECORDED",
        ):
            self.assertIn(expected, output)
        receipts = self.store.read_receipts("demo-test")
        self.assertEqual(sum(r["event"] == "JOSEPH_APPROVED" for r in receipts), 1)
        self.assertEqual(sum(r["event"] == "RESULT_RECORDED" for r in receipts), 1)
