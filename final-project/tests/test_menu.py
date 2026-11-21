import io
import unittest
from contextlib import nullcontext
from typing import Any
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

    def test_compact_main_menu_keeps_all_actions_visible(self) -> None:
        from pathlib import Path

        from fifth_pick.menu import OPTIONS, _main_menu
        from fifth_pick.storage import RunStore

        store = RunStore(Path("unused"))
        for columns, height in ((80, 24), (100, 30)):
            with (
                self.subTest(columns=columns, height=height),
                patch.dict(
                    "os.environ", {"COLUMNS": str(columns), "LINES": str(height), "TERM": "dumb"}
                ),
            ):
                output = _main_menu(store, "demo-test", {"stages": []}, 7, "")
                lines = output.splitlines()
                self.assertLess(len(lines), height)
                self.assertEqual(
                    [line[2:] for line in lines if line.startswith(("  ", "> "))], list(OPTIONS)
                )
                self.assertEqual(output.count("\n> "), 1)
                self.assertEqual("\n\n  View Candidates" in output, height == 30)
                self.assertIn("> Exit", output)
                self.assertIn("NEXT ACTION", output)
                self.assertNotIn("[NEXT]", output)
                self.assertNotIn("demo-test", output)
                self.assertNotIn("┌", output)

    def test_screen_management_releases_buffer_after_interrupt(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu import Terminal

        terminal = Terminal()
        output = io.StringIO()
        with (
            redirect_stdout(output),
            patch.object(
                terminal, "_screen_codes", return_value=("ENTER", "LEAVE", "CLEAR"), create=True
            ),
            self.assertRaises(KeyboardInterrupt),
            terminal.session(),
        ):
            terminal.screen("Action")
            raise KeyboardInterrupt
        self.assertEqual(output.getvalue(), "ENTERCLEARAction\nLEAVE")

    def test_fullscreen_reports_page_overflow_and_discard_replaced_content(self) -> None:
        from contextlib import redirect_stdout
        from os import terminal_size

        from fifth_pick.menu import Terminal

        terminal = Terminal()
        output = io.StringIO()
        with (
            redirect_stdout(output),
            patch.object(terminal, "_screen_codes", return_value=("ENTER", "LEAVE", "CLEAR")),
            patch("fifth_pick.menu.get_terminal_size", return_value=terminal_size((80, 8))),
            patch.object(terminal, "key", side_effect=["down", "escape"]),
            terminal.session(),
            terminal.action_output(),
        ):
            print("Old buffered report")
            terminal.screen("New report")
            for index in range(7):
                print(f"Report line {index}")
            terminal.pause()
        text = output.getvalue()
        self.assertNotIn("Old buffered report", text)
        self.assertIn("Page 1/2", text)
        second_page = text.split("CLEAR")[-1]
        self.assertIn("Report line 6", second_page)
        self.assertNotIn("Report line 0", second_page)
        self.assertTrue(text.endswith("LEAVE"))

    def test_followup_prompt_keeps_numbered_proposal_in_the_active_form(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu import Terminal

        terminal = Terminal()
        output = io.StringIO()
        with (
            redirect_stdout(output),
            patch.object(terminal, "_screen_codes", return_value=("ENTER", "LEAVE", "CLEAR")),
            patch.object(terminal, "_prompt_input", side_effect=["MODIFY", "1"]),
            terminal.session(),
            terminal.action_output(),
        ):
            terminal.screen("Decision form")
            print("Selection #1: Luka Doncic")
            self.assertEqual(terminal.prompt("Action"), "MODIFY")
            self.assertEqual(terminal.prompt("Selection numbers to retain"), "1")
        latest = output.getvalue().split("CLEAR")[-1]
        self.assertIn("Selection #1: Luka Doncic", latest)
        self.assertIn("Selection numbers to retain", latest)

    def test_screen_fallback_emits_no_terminal_controls(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu import Terminal

        terminal = Terminal()
        output = io.StringIO()
        with redirect_stdout(output), terminal.session():
            terminal.screen("Readable output")
        self.assertEqual(output.getvalue(), "Readable output\n")

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
                "  approve  ",
                "HIT",
                "synthetic-fixture",
                TIPOFF.isoformat(),
                "FIXTURE",
                "Synthetic PrizePicks Luka Doncic Assists Higher 9.5 settled HIT.",
                "YES",
            ),
        )
        for expected in (
            "Demo Mode",
            "Snapshots: 2/3",
            "Review provisional candidates, then run T-20 Review.",
            "Open Final Recommendations to create the proposal.",
            "KEY RISKS",
            "RECOMMENDED FINAL SLATE",
            "DECISION SUBMITTED",
            "Provisional watchlist",
            "STILL STRONG",
            "ASSISTS HIGHER 9.5",
            "Settlement blocked",
            "Cancelled before submitting the action",
            "Results: 1/3",
            "verified audit and receipts",
            "Board records",
            "Snapshot history",
            "T-20 Result",
            "EVIDENCE GAPS & REVIEW REASONS",
            "T-20 REVIEW",
            "Excluded from final proposal",
            "RESULT RECORDED",
            "Decision status",
            "Approved by Joseph",
            "Decision authority",
            "Joseph Edafiadhe (Governance Zero)",
            "Decision timestamp",
            "Decision receipt",
            "Recorded outcome",
            "HIT",
            "Full audit JSON:",
        ):
            self.assertIn(expected, output)
        self.assertNotIn('{"approval":', output)
        self.assertNotIn('{"artifact":', output)
        self.assertNotIn(key, output)
        self.assertIn("SELECTION #1", output)
        audit = self.store.run_directory("demo-test") / "final.json"
        self.assertIn(key, audit.read_text())
        self.assertIn(
            f"fixture:results/{key}",
            (self.store.run_directory("demo-test") / "results.json").read_text(),
        )
        receipts = self.store.read_receipts("demo-test")
        self.assertEqual(sum(r["event"] == "JOSEPH_APPROVED" for r in receipts), 1)
        self.assertEqual(sum(r["event"] == "RESULT_RECORDED" for r in receipts), 1)

    def prepare_proposal(self, run_id: str, *, zero_picks: bool = False) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu import DEMO
        from tests.test_fixture_cli import write_fixtures

        fixtures = DEMO
        if zero_picks:
            fixtures = self.store.root.parent / "empty-fixture"
            write_fixtures(fixtures, projection=False)
        with redirect_stdout(io.StringIO()):
            for number in (1, 2, 3):
                args = ["t20"] if number == 3 else ["analyze", "--snapshot", str(number)]
                self.assertEqual(
                    main([*args, "--run-id", run_id, "--fixture", str(fixtures / str(number))]),
                    0,
                )
            self.assertEqual(main(["final", "--run-id", run_id]), 0)

    def test_menu_resumes_original_bundled_demo(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu import LEGACY_DEMO

        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                main(
                    [
                        "analyze",
                        "--run-id",
                        "demo-test",
                        "--snapshot",
                        "1",
                        "--fixture",
                        str(LEGACY_DEMO / "1"),
                    ]
                ),
                0,
            )
        output = self.run_menu(
            [
                "enter",
                "down",
                "enter",
                "escape",
                "down",
                "down",
                "enter",
                "down",
                "enter",
                "escape",
                b"q",
            ]
        )
        self.assertIn("T-20 REVIEW", output)
        self.assertIn("Luka Doncic", output)
        self.assertNotIn("Jayson Tatum", output)

    def test_default_classroom_slate_screens_twelve_players_and_leaves_one_slot_open(self) -> None:
        from fifth_pick.fixture_workflow import candidates_view, final_view

        self.prepare_proposal("demo-test")
        candidates = candidates_view(self.store, "demo-test")["candidates"]
        assert isinstance(candidates, list)
        self.assertEqual(len({row["player"] for row in candidates}), 12)
        self.assertEqual({row["platform"] for row in candidates}, {"prizepicks", "underdog"})
        self.assertEqual(
            {row["category"] for row in candidates},
            {"POINTS", "REBOUNDS", "ASSISTS", "PRA", "REBOUNDS_ASSISTS"},
        )
        self.assertEqual({row["direction"] for row in candidates}, {"HIGHER", "LOWER"})
        durant = next(row for row in candidates if row["player"] == "Kevin Durant")
        self.assertEqual(durant["snapshots"], [1, 2])
        self.assertEqual(durant["status"], "REMOVE RECOMMENDED")
        final, blocked = final_view(self.store, "demo-test")
        self.assertFalse(blocked)
        self.assertEqual(final["state"], "AWAITING_JOSEPH")
        slate = final["slate"]
        picks = final["proposed"]
        assert isinstance(slate, dict) and isinstance(picks, list)
        self.assertEqual(slate["game_count"], 4)
        self.assertEqual(slate["maximum_selections"], 4)
        self.assertEqual(
            {row["player"] for row in picks},
            {"Luka Doncic", "Jayson Tatum", "Joel Embiid"},
        )
        for row in picks:
            self.assertEqual(row["t20_status"], "STILL STRONG")

    def test_compares_provisional_candidates_in_one_table(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu import DEMO, _read_state, _show_candidates

        output = io.StringIO()
        with redirect_stdout(io.StringIO()):
            for number in (1, 2):
                self.assertEqual(
                    main(
                        [
                            "analyze",
                            "--run-id",
                            "demo-test",
                            "--snapshot",
                            str(number),
                            "--fixture",
                            str(DEMO / str(number)),
                        ]
                    ),
                    0,
                )
        with redirect_stdout(output), patch.dict("os.environ", {"COLUMNS": "80", "TERM": "xterm"}):
            _show_candidates(self.store, "demo-test", _read_state(self.store, "demo-test"))
        screen = output.getvalue()
        self.assertEqual(screen.count("┌"), 1)
        self.assertIn("Pending", screen)
        self.assertIn("LeBron James", screen)
        self.assertIn("Kevin Durant", screen)
        statuses = [line.split("│")[-2].strip() for line in screen.splitlines() if "│" in line]
        self.assertIn("Evidence gap", " ".join(statuses))
        self.assertNotIn("Still strong", screen)
        self.assertIn("PP = PrizePicks", screen)
        self.assertIn("AST = Assists", screen)
        self.assertIn("UD = Underdog", screen)
        self.assertTrue(all(len(line) <= 80 for line in screen.splitlines()))
        header = next(line for line in screen.splitlines() if "Confidence" in line)
        self.assertEqual(
            [cell.strip() for cell in header.strip("│").split("│")],
            ["#", "Player", "Plat", "Market", "Pick", "Line", "Confidence", "Status"],
        )

    def test_t20_report_handles_empty_reviews_and_missing_current_projection(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu import _show_t20_report

        self.prepare_proposal("demo-test")
        state: dict[str, Any] = {"snapshots": [], "t20_reviews": []}
        output = io.StringIO()
        with redirect_stdout(output):
            _show_t20_report(self.store, "demo-test", state)
        self.assertIn("No candidate reviews recorded.", output.getvalue())
        self.assertIn("0 observations accepted", output.getvalue())

        state["t20_reviews"] = [
            {
                "current_audit": None,
                "previous_audit": {
                    "candidate": {
                        "player": "A Player With A Long Registered Name",
                        "category": "REBOUNDS",
                        "platform": "underdog",
                        "direction": "HIGHER",
                        "projection": 8.5,
                    },
                    "methodology_rationale": "Saved supporting details.",
                },
                "projection": {"before": 8.5, "at_t20": None},
                "reason_codes": ["NOT_AUTHORIZED"],
                "readiness_gaps": ["Snapshot 3 evidence was unavailable."],
                "conclusion": "REMOVE RECOMMENDED",
            }
        ]
        output = io.StringIO()
        with redirect_stdout(output), patch.dict("os.environ", {"COLUMNS": "80", "TERM": "xterm"}):
            _show_t20_report(self.store, "demo-test", state)
        display = output.getvalue()
        self.assertEqual(display.count("┌"), 1)
        self.assertIn("UD = Underdog", display)
        self.assertIn("NOT AUTHORIZED", display)
        self.assertIn("Snapshot 3 evidence was unavailable.", display)
        self.assertIn("prior assessment", display)
        self.assertNotIn("8.5", display)
        self.assertTrue(all(len(line) <= 80 for line in display.splitlines()))

    def test_reviewed_candidates_use_saved_rank_confidence_and_status(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu import _read_state, _show_candidates

        self.prepare_proposal("demo-test")
        output = io.StringIO()
        with redirect_stdout(output), patch.dict("os.environ", {"COLUMNS": "100", "TERM": "xterm"}):
            _show_candidates(self.store, "demo-test", _read_state(self.store, "demo-test"))
        rows = [line for line in output.getvalue().splitlines() if "Luka Doncic" in line]
        self.assertEqual(len(rows), 3)
        self.assertIn("Higher", rows[0])
        self.assertIn("High", rows[0])
        self.assertIn("Still strong", rows[0])
        self.assertIn("Remove recommended", rows[1])
        self.assertIn("Pending", rows[1])

    def test_comparison_legend_and_narrow_fallback_preserve_all_rows(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu import _show_candidates

        state = {"stages": [{}, {"m6_ranked_candidate_keys": []}], "t20_reviews": []}
        rows = [
            {
                "candidate_key": f"{index:064x}",
                "player": "An Exceptionally Long Player Name" if index == 0 else f"Player {index}",
                "platform": "prizepicks" if index % 2 == 0 else "underdog",
                "category": market,
                "direction": "LOWER",
                "projection": 10.5,
            }
            for index, market in enumerate(
                ("POINTS", "REBOUNDS", "ASSISTS", "PRA", "REBOUNDS_ASSISTS")
            )
        ]
        for columns, visible in ((42, rows), (80, rows), (120, rows[:1]), (100, [])):
            with (
                self.subTest(columns=columns),
                patch("fifth_pick.menu.candidates_view", return_value={"candidates": visible}),
                patch.dict("os.environ", {"COLUMNS": str(columns), "TERM": "dumb"}),
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    _show_candidates(self.store, "demo-test", state)
                text = output.getvalue()
                self.assertTrue(all(len(line) <= columns for line in text.splitlines()))
                self.assertNotIn("┌", text)
                if not visible:
                    self.assertIn("No candidates recorded", text)
                    continue
                self.assertEqual(text.count("10.5"), len(visible))
                self.assertEqual(text.count("Pending"), 2 * len(visible))
                self.assertIn("PP = PrizePicks", text)
                self.assertIn("PTS = Points", text)
                if len(visible) > 1:
                    for code in ("UD", "REB", "AST", "PRA", "RA"):
                        self.assertIn(f"{code} =", text)
                else:
                    self.assertNotIn("UD =", text)

    def test_reject_identifies_previously_proposed_selection_and_reason(self) -> None:
        self.prepare_proposal("demo-test")
        output = self.run_menu(
            ["down"] * 4 + ["enter", "down", "enter", "escape", b"q"],
            (" r ", "Fixture evidence was too limited."),
        )
        self.assertRegex(output, r"Decision status\s+│ Rejected by Joseph")
        self.assertIn("Rejected selections", output)
        self.assertIn("Luka Doncic", output)
        self.assertRegex(output, r"Reason\s+│ Fixture evidence was too limited\.")
        self.assertIn("No approved selections.", output)
        self.assertNotIn("key=", output)

    def test_modify_uses_numbers_and_keeps_exact_key_in_audit(self) -> None:
        import json

        from fifth_pick.models import Category
        from tests.m6_support import candidate_key

        self.prepare_proposal("demo-test")
        choice = ["down"] * 4 + ["enter", "down", "enter", "escape"]
        output = self.run_menu(choice + choice + [b"q"], ("MoDiFy", "9", " m ", "Selection #1"))
        self.assertIn("Enter the selection numbers shown in this proposal", output)
        self.assertIn("Modified by Joseph", output)
        self.assertIn("awaiting a new decision", output)
        self.assertIn("Retained in the revised proposal", output)
        self.assertIn("Joseph must decide on the revised proposal before any settlement.", output)
        key = candidate_key("Luka Doncic", category=Category.ASSISTS)
        self.assertNotIn(key, output)
        path = self.store.run_directory("demo-test") / "final.json"
        approval = json.loads(path.read_text())["approval"]
        self.assertEqual(approval["decision_selection"], [key])
        self.assertIsNone(approval["official_final"])
        self.assertEqual(
            sum(r["event"] == "JOSEPH_MODIFIED" for r in self.store.read_receipts("demo-test")),
            1,
        )

    def test_invalid_decision_leaves_pending_proposal_and_receipts_unchanged(self) -> None:
        self.prepare_proposal("demo-test")
        path = self.store.run_directory("demo-test") / "final.json"
        before = path.read_bytes()
        receipts = self.store.read_receipts("demo-test")
        choice = ["down"] * 4 + ["enter", "down", "enter", "escape"]
        output = self.run_menu(choice + [b"q"], ("app",))
        self.assertIn("Invalid decision.", output)
        self.assertIn("Shortcuts: A, R, M.", output)
        self.assertNotIn("DECISION SUBMITTED", output)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.store.read_receipts("demo-test"), receipts)

    def test_unverified_checkpoint_has_no_completion_indicator(self) -> None:
        self.prepare_proposal("demo-test")
        path = self.store.run_directory("demo-test") / "fixture-stage-3.json"
        path.write_text("{}")
        receipts = self.store.read_receipts("demo-test")
        output = self.run_menu(["enter", "escape", b"q"])
        self.assertIn("Run verification stopped:", output)
        self.assertIn("No action was recorded.", output)
        self.assertNotIn("Open Final Recommendations to create the proposal.", output)
        self.assertEqual(path.read_text(), "{}")
        self.assertEqual(self.store.read_receipts("demo-test"), receipts)

    def test_empty_proposal_remains_zero_picks_when_approved(self) -> None:
        self.prepare_proposal("demo-test", zero_picks=True)
        output = self.run_menu(
            ["down"] * 3
            + ["enter", "escape"]
            + ["down"] * 4
            + ["enter", "down", "enter", "escape", b"q"],
            (" a ",),
        )
        self.assertIn("No entry recommended. Review the audit and receipts.", output)
        self.assertIn("Decision: Optional (no entry)", output)
        self.assertIn("NO ENTRY RECOMMENDED TODAY.", output)
        self.assertRegex(output, r"Decision status\s+│ Approved by Joseph")
        self.assertIn("No approved selections.", output)


class FinalRecommendationsPresentationTests(unittest.TestCase):
    def render(self, proposal, state, columns=80, term="xterm") -> str:
        from contextlib import redirect_stdout

        from fifth_pick.menu import _show_final_recommendations

        output = io.StringIO()
        with (
            redirect_stdout(output),
            patch.dict("os.environ", {"COLUMNS": str(columns), "TERM": term}),
        ):
            _show_final_recommendations(proposal, state)
        display = output.getvalue()
        self.assertTrue(all(len(line) <= columns for line in display.splitlines()))
        return display

    def test_full_slate_preserves_rows_risks_and_evidence_at_supported_widths(self) -> None:
        rows: list[dict[str, Any]] = [
            {
                "player": f"Demonstration Player {number}",
                "platform": "prizepicks" if number % 2 else "underdog",
                "category": category,
                "direction": "HIGHER" if number % 2 else "LOWER",
                "projection": number + 8.5,
                "confidence": "MEDIUM" if number < 5 else None,
                "t20_status": "STILL STRONG" if number < 5 else "DOWNGRADED",
                "candidate_key": f"{number:064x}",
                "material_risks": [
                    f"Recorded concern {number}.",
                    "Extended risk text " * 5 + f"ends {number}.",
                ],
                "projection_movement": [8.5, 9.0, 9.5],
                "history": [{"kind": "LAST_8", "favorable_count": 5, "sample_count": 8}],
                "t20_event_key": f"review-{number}",
            }
            for number, category in enumerate(
                ("POINTS", "ASSISTS", "REBOUNDS", "PRA", "REBOUNDS_ASSISTS"), 1
            )
        ]
        rows[1]["material_risks"].append("The latest report contradicts the role estimate.")
        state = {
            "t20_reviews": [
                {
                    "event_key": "review-2",
                    "readiness_gaps": [],
                    "current_audit": {
                        "gaps": [{"detail": "Only a partial history is available."}],
                        "evidence": [
                            {
                                "evidence_id": "conflict",
                                "effect": "CONFLICT",
                                "significance": "IMPORTANT",
                                "claim": "The latest report contradicts the role estimate.",
                            }
                        ],
                    },
                },
            ],
        }
        for columns, count in ((80, 4), (80, 5), (100, 5), (120, 5)):
            with self.subTest(columns=columns, count=count):
                proposal = {
                    "state": "AWAITING_JOSEPH",
                    "slate": {
                        "slate_date": "2026-11-15",
                        "game_count": count,
                        "maximum_selections": count,
                    },
                    "proposed": rows[:count],
                }
                display = self.render(proposal, state, columns)
                self.assertEqual(display.count("┌"), 1)
                self.assertEqual(display.count("├"), count)
                heading, rest = display.split("KEY RISKS", 1)
                risks, rest = rest.split("SUPPORTING EVIDENCE", 1)
                evidence, gaps = rest.split("EVIDENCE GAPS", 1)
                rendered_rows = [
                    [
                        " ".join(word for word in cell if word)
                        for cell in zip(
                            *(
                                tuple(part.strip() for part in line.strip("│").split("│"))
                                for line in group.splitlines()
                                if line.startswith("│")
                            ),
                            strict=True,
                        )
                    ]
                    for group in heading.split("├")[1:]
                ]
                expected_codes = ("PTS", "AST", "REB", "PRA", "RA")
                for number, (rendered, row) in enumerate(
                    zip(rendered_rows, rows[:count], strict=True), 1
                ):
                    self.assertEqual(
                        rendered,
                        [
                            str(number),
                            row["player"],
                            "PP" if number % 2 else "UD",
                            expected_codes[number - 1],
                            row["direction"].title(),
                            str(row["projection"]),
                            "Medium" if number < 5 else "Pending",
                            "Strong" if number < 5 else "Downgraded",
                        ],
                    )
                self.assertIn("UD = Underdog", heading)
                self.assertEqual("RA = Rebounds + Assists" in " ".join(heading.split()), count == 5)
                self.assertEqual("Pending" in heading, count == 5)
                self.assertIn("Contradictory evidence:", risks)
                self.assertEqual(
                    " ".join(risks.split()).count(
                        "The latest report contradicts the role estimate."
                    ),
                    1,
                )
                self.assertIn("Last 8: 5/8 favorable", " ".join(evidence.split()))
                self.assertIn("#2 Demonstration Player 2", gaps)
                self.assertIn("Only a partial history is available.", " ".join(gaps.split()))
                for number in range(1, count + 1):
                    self.assertIn(f"#{number} Demonstration Player {number}", risks)
                    self.assertIn(f"ends {number}.", risks)
                    self.assertNotIn(rows[number - 1]["candidate_key"], display)

    def test_decision_status_and_empty_states_do_not_suggest_a_new_approval(self) -> None:
        pick = {
            "player": "Fixture Player",
            "platform": "prizepicks",
            "category": "ASSISTS",
            "direction": "HIGHER",
            "projection": 9.5,
        }
        slate = {"slate_date": "2026-11-15", "game_count": 1, "maximum_selections": 4}
        for status, action, items, expected in (
            ("APPROVED_BY_JOSEPH", "APPROVE", [pick], "APPROVED FINAL SLATE"),
            ("REJECTED_BY_JOSEPH", "REJECT", [pick], "REJECTED PROPOSAL"),
            ("AWAITING_JOSEPH", "MODIFY", [pick], "REVISED PROPOSAL"),
            ("AWAITING_JOSEPH", "MODIFY", [], "The revised proposal is empty."),
            ("NO_ENTRY", None, [], "NO ENTRY RECOMMENDED TODAY."),
            ("APPROVED_BY_JOSEPH", "APPROVE", [], "NO ENTRY RECOMMENDED TODAY."),
            ("REJECTED_BY_JOSEPH", "REJECT", [], "NO ENTRY RECOMMENDED TODAY."),
        ):
            with self.subTest(status=status, action=action, items=bool(items)):
                display = self.render(
                    {
                        "state": status,
                        "slate": slate,
                        "proposed": items,
                        "recommendation": "NO ENTRY RECOMMENDED TODAY.",
                    },
                    {"t20_reviews": [], "final": {"approval": {"action": action}}},
                )
                self.assertIn(expected, display)
                self.assertEqual(
                    "Approve / Reject / Modify" in display, action == "MODIFY" and bool(items)
                )
                self.assertEqual("┌" in display, bool(items))
                if items:
                    self.assertIn("No material risks recorded.", display)
                    self.assertIn("No supporting details recorded.", display)
                    fallback = self.render(
                        {
                            "state": status,
                            "slate": slate,
                            "proposed": items,
                        },
                        {"t20_reviews": []},
                        columns=42,
                        term="dumb",
                    )
                    self.assertIn("Fixture Player", fallback)
                    self.assertNotIn("┌", fallback)


class MenuOutputTests(unittest.TestCase):
    def test_blocked_structured_response_is_readable_and_yields_no_success(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu import Terminal, _capture

        def blocked(_read) -> int:
            print('{"status":"BLOCKED","reason":"T20_CHECK_UNAVAILABLE"}')
            return 1

        output = io.StringIO()
        with redirect_stdout(output):
            self.assertIsNone(_capture(Terminal(), blocked))
        self.assertIn("Action stopped.", output.getvalue())
        self.assertIn("Status: BLOCKED", output.getvalue())
        self.assertIn("T20_CHECK_UNAVAILABLE", output.getvalue())
        self.assertNotIn('{"status":', output.getvalue())

    def test_live_style_command_details_render_before_prompt(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu import Terminal, _capture

        output = io.StringIO()

        def present(read) -> int:
            print('{"mode":"SAVED_PROVIDER_DISCOVERY_TIMING_ONLY","events":[]}')
            self.assertEqual(read("Confirm? "), "NO")
            return 1

        def respond(message: str) -> str:
            self.assertIn("Mode: SAVED_PROVIDER_DISCOVERY_TIMING_ONLY", output.getvalue())
            self.assertEqual(message, "Confirm? ")
            return "NO"

        terminal = Terminal()
        with redirect_stdout(output), patch.object(terminal, "prompt", side_effect=respond):
            self.assertIsNone(_capture(terminal, present, show_details=True))
        self.assertNotIn('{"mode":', output.getvalue())

    def test_unicode_separator_in_command_json_keeps_the_record_intact(self) -> None:
        import json
        from contextlib import redirect_stdout

        from fifth_pick.menu import Terminal, _capture

        record = {"reason": "First reason\u2028Second reason."}

        def command(_read) -> int:
            print(json.dumps(record, ensure_ascii=False))
            return 0

        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(_capture(Terminal(), command), record)
        self.assertEqual(output.getvalue(), "")

    def test_settlement_excerpt_is_visible_in_full_before_attestation(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu import Terminal, _capture

        output = io.StringIO()
        excerpt = "Source supplied  a digest: " + "a1" * 32

        def command(read) -> int:
            print(f"Evidence excerpt: {excerpt}")
            read("Confirm this source? ")
            return 1

        def respond(_message: str) -> str:
            self.assertIn(excerpt, output.getvalue().replace("\n", ""))
            return "NO"

        terminal = Terminal()
        with redirect_stdout(output), patch.object(terminal, "prompt", side_effect=respond):
            self.assertIsNone(_capture(terminal, command))


class BorderedTableTests(unittest.TestCase):
    def test_table_has_connected_borders_and_aligned_columns(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu_presentation import table

        output = io.StringIO()
        with redirect_stdout(output), patch.dict("os.environ", {"COLUMNS": "80", "TERM": "xterm"}):
            table(("Player", "Market"), (("Luka Doncic", "Assists"), ("Ming", "Rebounds")))
        lines = output.getvalue().splitlines()
        self.assertTrue(lines[0].startswith("┌"))
        self.assertTrue(lines[-1].endswith("┘"))
        self.assertEqual(len({len(line) for line in lines}), 1)
        dividers = [
            [i for i, char in enumerate(line) if char == "│"] for line in lines if "│" in line
        ]
        self.assertEqual(sum("┼" in line for line in lines), 2)
        self.assertEqual(len(dividers), 3)
        self.assertTrue(all(divider == dividers[0] for divider in dividers))

    def test_visible_width_counts_wide_and_combining_text_and_ignores_ansi(self) -> None:
        import unicodedata
        from contextlib import redirect_stdout

        from fifth_pick.menu_presentation import table

        def cells(text: str) -> int:
            return len(text) + sum(
                (unicodedata.east_asian_width(char) in {"F", "W"})
                - (unicodedata.category(char) in {"Mn", "Me"})
                for char in text
            )

        output = io.StringIO()
        with redirect_stdout(output), patch.dict("os.environ", {"COLUMNS": "80", "TERM": "xterm"}):
            table(("Player", "Market"), (("\033[31m李 e\u0301\033[0m", "Assists"),))
        lines = output.getvalue().splitlines()
        self.assertNotIn("\033", output.getvalue())
        self.assertIn("李 e\u0301", output.getvalue())
        self.assertEqual(len({cells(line) for line in lines}), 1)
        self.assertEqual(
            {cells(line.split("│")[1]) for line in lines if line.startswith("│")},
            {8},
        )

    def test_two_selection_cards_keep_risks_and_evidence_separate_at_each_width(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu_presentation import picks

        first_name = "A Player With an Exceptionally Long Full Name That Wraps Anywhere It Needs To"
        risk = "Travel may change minutes " * 7 + "last-risk-word"
        first = {
            "player": first_name,
            "platform": "prizepicks",
            "category": "ASSISTS",
            "direction": "HIGHER",
            "projection": 9.5,
            "confidence": "HIGH",
            "t20_status": "STILL STRONG",
            "candidate_key": "f" * 64,
            "material_risks": [risk, "Second concern."],
            "projection_movement": [8.5, 9.0, 9.5],
            "t20_rationale": "Cited synthetic evidence.",
        }
        second = {
            **first,
            "player": "Second Player",
            "material_risks": [],
            "projection_movement": [],
            "t20_rationale": "",
        }
        for width in (80, 100, 120):
            with self.subTest(width=width):
                output = io.StringIO()
                with (
                    redirect_stdout(output),
                    patch.dict("os.environ", {"COLUMNS": str(width), "TERM": "xterm"}),
                ):
                    picks([first, second], supporting=True)
                display = output.getvalue()
                self.assertTrue(all(len(line) <= width for line in display.splitlines()))
                self.assertEqual(display.count("MATERIAL RISKS"), 2)
                self.assertEqual(display.count("SUPPORTING EVIDENCE"), 2)
                card, second_card = display.split("SELECTION #2", 1)
                self.assertEqual(card.count("A Player With"), 1)
                self.assertIn("last-risk-word", card)
                self.assertIn("Second concern.", card)
                self.assertIn("8.5 → 9.0 → 9.5", card)
                self.assertIn("None recorded.", second_card)
                self.assertNotIn("last-risk-word", second_card)
                self.assertNotIn(first["candidate_key"], display)

    def test_ascii_narrow_table_uses_bordered_cards(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu_presentation import table

        output = io.StringIO()
        with redirect_stdout(output), patch.dict("os.environ", {"COLUMNS": "28", "TERM": "dumb"}):
            table(
                ("Selection", "Evidence status", "Projection"),
                (("#1", "Supporting evidence is unavailable", "9.5"),),
            )
        lines = output.getvalue().splitlines()
        self.assertTrue(all(len(line) <= 28 for line in lines))
        self.assertTrue(lines[0].startswith("+"))
        self.assertNotIn("│", output.getvalue())
        self.assertIn("SELECTION #1", output.getvalue())
        self.assertIn("unavailable", output.getvalue())

    def test_ascii_output_can_render_unicode_evidence_without_encoding_error(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu_presentation import details, panel

        buffer = io.BytesIO()
        with io.TextIOWrapper(buffer, encoding="ascii") as output, redirect_stdout(output):
            details({"records": ["Café"]})
            panel("Warnings", ("Unavailable",))
            output.flush()
            rendered = buffer.getvalue().decode("ascii")
        self.assertIn(r"- Caf\xe9", rendered)
        self.assertIn("+", rendered)
        self.assertIn("WARNINGS", rendered)

    def test_modify_labels_revised_and_original_numbering_separately(self) -> None:
        from contextlib import redirect_stdout

        from fifth_pick.menu_presentation import decision

        first = {
            "player": "First Candidate",
            "platform": "prizepicks",
            "category": "ASSISTS",
            "direction": "HIGHER",
            "projection": 9.5,
            "confidence": "HIGH",
            "t20_status": "STILL STRONG",
            "candidate_key": "first",
            "material_risks": [],
        }
        second = {**first, "player": "Second Candidate", "candidate_key": "second"}
        final = {
            "run_id": "demo-test",
            "proposed": [second],
            "approval": {
                "action": "MODIFY",
                "actor": "Joseph",
                "decision_recorded_at": "2026-11-15T19:55:00+00:00",
                "decision_receipt_key": "decision-key",
                "decision_selection": ["second"],
                "official_final": None,
                "reason": "",
            },
        }
        audit = {
            "finalization_audit": {
                "joseph_decisions": [
                    {
                        "receipt_event_key": "decision-key",
                        "displayed_proposal": {"proposed": [first, second]},
                    }
                ]
            }
        }
        output = io.StringIO()
        with redirect_stdout(output), patch.dict("os.environ", {"COLUMNS": "80", "TERM": "xterm"}):
            decision(final, audit)
        revised, removed = output.getvalue().split(
            "Removed from the proposal (original selection numbers)"
        )
        self.assertIn("SELECTION #1", revised)
        self.assertIn("Second Candidate", revised)
        self.assertNotIn("SELECTION #2", revised)
        self.assertIn("SELECTION #1", removed)
        self.assertIn("First Candidate", removed)
