"""Terminal-only navigation for the existing offline fixture workflow."""

import codecs
import io
import json
import os
import select
import sys
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from fifth_pick.errors import FifthPickError
from fifth_pick.fixture_workflow import audit_view, candidates_view
from fifth_pick.storage import RunStore

DEMO = Path(__file__).with_name("demo")
OPTIONS = (
    "Analyze NBA Slate",
    "View Candidates and Rankings",
    "Run T-20 Review",
    "View Final Recommendations",
    "Approve / Reject / Modify",
    "Record Results",
    "View Audit and Receipts",
    "Exit",
)
NAVIGATION = "↑ / ↓ Move   Enter Select   Esc Back   Q Quit"
Prompt = Callable[[str], str]
Dispatch = Callable[[Sequence[str], Prompt], int]


class QuitMenu(Exception):
    """Return control to the shell."""


class Back(Exception):
    """Cancel the active prompt before submitting it."""


class Terminal:
    @contextmanager
    def _cbreak(self) -> Generator[int]:
        import termios
        import tty

        fd = sys.stdin.fileno()
        settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd, termios.TCSANOW)
            yield fd
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, settings)

    @staticmethod
    def _read(fd: int) -> str | bytes:
        first = os.read(fd, 1)
        if first in (b"", b"\x04"):
            raise QuitMenu
        if first in (b"\r", b"\n"):
            return "enter"
        if first != b"\x1b":
            return first
        if not select.select([fd], [], [], 0.08)[0]:
            return "escape"
        prefix = os.read(fd, 1)
        if prefix not in (b"[", b"O"):
            return "escape"
        for _ in range(16):
            if not select.select([fd], [], [], 0.08)[0]:
                return "unknown"
            suffix = os.read(fd, 1)
            if not suffix:
                raise QuitMenu
            if b"@" <= suffix <= b"~":
                return {b"A": "up", b"B": "down"}.get(suffix, "unknown")
        return "unknown"

    def key(self) -> str | bytes:
        with self._cbreak() as fd:
            return self._read(fd)

    def screen(self, message: str) -> None:
        print("\033[2J\033[H" + message, flush=True)

    def choose(
        self, heading: str, labels: Sequence[str], *, live_shortcut: bool = False
    ) -> int | None:
        selected = 0
        while True:
            rows = [
                f"{'›' if index == selected else ' '} {label}" for index, label in enumerate(labels)
            ]
            self.screen("\n".join((heading, "", *rows, "", NAVIGATION)))
            key = self.key()
            if key in (b"q", b"Q"):
                raise QuitMenu
            if live_shortcut and key in (b"l", b"L"):
                return len(labels)
            if key == "escape":
                return None
            if key == "enter":
                return selected
            if key == "up":
                selected = (selected - 1) % len(labels)
            if key == "down":
                selected = (selected + 1) % len(labels)

    def prompt(self, message: str) -> str:
        """Read typed input for the existing CLI forms, with Esc cancellation."""
        print(message, end="", flush=True)
        text: list[str] = []
        decoder = codecs.getincrementaldecoder("utf-8")(errors="ignore")
        try:
            with self._cbreak() as fd:
                while True:
                    key = self._read(fd)
                    if key == "escape":
                        raise Back
                    if key == "enter":
                        return "".join(text)
                    if key in (b"\x7f", b"\x08"):
                        if text:
                            text.pop()
                            print("\b \b", end="", flush=True)
                    elif isinstance(key, bytes):
                        for char in decoder.decode(key):
                            if char.isprintable():
                                text.append(char)
                                print(char, end="", flush=True)
        except KeyboardInterrupt as exc:
            raise Back from exc
        finally:
            print()

    def pause(self) -> None:
        print("\nEnter or Esc to return · Q to quit", flush=True)
        while True:
            key = self.key()
            if key in (b"q", b"Q"):
                raise QuitMenu
            if key in ("enter", "escape"):
                return


def _read_state(store: RunStore, run_id: str) -> dict[str, Any]:
    if not store.run_directory(run_id).exists():
        return {"stages": [], "final": None, "results": None, "receipts": ()}
    return audit_view(store, run_id)


def _heading(run_id: str, state: dict[str, Any]) -> str:
    stages = len(state["stages"])
    final = state.get("final")
    readiness = (
        "Ready for Snapshot 1",
        "Ready for Snapshot 2",
        "Ready for T-20",
        "Ready to create the final proposal",
    )[stages]
    if final:
        status = final["state"]
        readiness = status
        if status == "AWAITING_JOSEPH":
            readiness = "Awaiting Joseph's explicit decision"
        elif status == "APPROVED_BY_JOSEPH":
            count = len((state["results"] or {}).get("results", []))
            total = len(final["approval"]["official_final"])
            readiness = f"Approved by Joseph · results recorded {count}/{total}"
    return (
        "The Fifth Pick · Demo Mode (offline synthetic fixtures)\n"
        f"Run ID: {run_id}    Stage: {stages}/3 snapshots    Readiness: {readiness}"
    )


def _safe(text: str) -> str:
    """Render stored evidence as text without terminal control characters."""
    return "".join(char if char.isprintable() else " " for char in text)


def _capture(dispatch: Dispatch, terminal: Terminal, arguments: list[str]) -> dict[str, Any]:
    output = io.StringIO()
    with redirect_stdout(output):
        code = dispatch(arguments, terminal.prompt)
    raw = output.getvalue()
    if raw:
        return json.loads(raw)
    return {"status": "Command stopped." if code else "Command completed."}


def _show_final(final: dict[str, Any]) -> None:
    print(final.get("recommendation", final.get("status", "")))
    for item in final.get("proposed", ()):
        print(_selection(item))
        movement = " → ".join(str(value) for value in item["projection_movement"])
        print(f"  {item['confidence']} · {item['t20_status']} · {movement}")
        for history in item["history"]:
            print(
                f"  {history['kind']}: {history['favorable_count']}/"
                f"{history['sample_count']} favorable"
            )
        for risk in item["material_risks"]:
            print(f"  Material risk: {_safe(risk)}")


def _selection(item: dict[str, Any]) -> str:
    return _safe(
        f"{item['player']} · {item['platform']} · {item['category']} "
        f"{item['direction']} {item['projection']}"
    )


def _perform(
    action: int,
    terminal: Terminal,
    dispatch: Dispatch,
    store: RunStore,
    run_id: str,
    state: dict[str, Any],
) -> None:
    stages = len(state["stages"])
    final = state["final"]
    base = ["--run-id", run_id]

    def confirm(message: str) -> None:
        if terminal.choose(message, ("Cancel", "Continue")) != 1:
            raise Back

    if action == 0:
        if stages >= 2:
            print("Snapshots 1 and 2 already recorded. Use Run T-20 Review when ready.")
            return
        number = stages + 1
        confirm(f"Record Snapshot {number} using the bundled offline fixture?")
        row = _capture(
            dispatch,
            terminal,
            ["analyze", *base, "--snapshot", str(number), "--fixture", str(DEMO / str(number))],
        )
        print(f"Snapshot {number}: {row['status']}")
    elif action == 1:
        if not stages:
            print("Use Analyze NBA Slate to create a provisional watchlist.")
            return
        view = cast(dict[str, Any], candidates_view(store, run_id))
        ranked = state["stages"][-1]["m6_ranked_candidate_keys"]
        print(view["status"])
        if not ranked:
            print("Rankings are available when M6 has sufficient evidence and all three snapshots.")
        for candidate in sorted(
            view["candidates"],
            key=lambda row: (
                ranked.index(row["candidate_key"])
                if row["candidate_key"] in ranked
                else len(ranked)
            ),
        ):
            key = candidate["candidate_key"]
            rank = f"M6 rank {ranked.index(key) + 1} · " if key in ranked else ""
            print(
                f"{rank}{_selection(candidate)} · {candidate['status']} · "
                f"supporting evidence {candidate['supporting_evidence']}"
            )
    elif action == 2:
        if stages != 2:
            print("Finish Snapshots 1 and 2 first." if stages < 2 else "T-20 already recorded.")
            return
        confirm("Record Snapshot 3 and run the offline T-20 review?")
        row = _capture(dispatch, terminal, ["t20", *base, "--fixture", str(DEMO / "3")])
        print(f"T-20: {row['status']}")
        for review in row.get("reviews", ()):
            print(f"  {review['status']}")
    elif action == 3:
        if stages != 3:
            print("Complete the T-20 review before final recommendations.")
            return
        if not final:
            confirm("Create and save a final proposal for Joseph's review?")
        _show_final(_capture(dispatch, terminal, ["final", *base]))
    elif action == 4:
        if not final or final["state"] != "AWAITING_JOSEPH":
            print("A pending final proposal is required for a decision.")
            return
        confirm("Open Joseph's decision form? The typed action will be recorded.")
        print("Only Joseph may enter APPROVE, REJECT, or MODIFY. Esc cancels.")
        dispatch(["decide", *base], terminal.prompt)
    elif action == 5:
        if not final or final["state"] != "APPROVED_BY_JOSEPH":
            print("Settlement blocked. Joseph's receipt-verified approval is required.")
            return
        selections = final["approval"]["official_final"]
        if not selections:
            print("No approved selections to settle.")
            return
        index = terminal.choose(
            "Select an approved pick to settle", tuple(map(_selection, selections))
        )
        if index is None:
            raise Back
        item = selections[index]
        confirm(f"Open the synthetic settlement form for {_selection(item)}?")
        print("Use source synthetic-fixture and a fixture: reference containing the selection key.")
        print("Enter the synthetic result and verify its excerpt. Esc cancels.")
        dispatch(
            ["result", "record", *base, "--selection", item["candidate_key"]],
            terminal.prompt,
        )
    elif action == 6:
        if not stages:
            print("No audit or receipts yet.")
            return
        print(f"Run {run_id} · verified audit and receipts")
        print(
            f"M4 boards: {len(state['board_manifests'])} · "
            f"M5 ledger entries: {len(state['snapshots'])}"
        )
        for review in state["t20_reviews"]:
            candidate = (review["current_audit"] or {}).get("candidate")
            label = _selection(candidate) if candidate else review["candidate_key"]
            print(_safe(f"T-20 audit · {label} · {review['conclusion']}"))
            for gap in review["readiness_gaps"]:
                print(f"  {_safe(gap)}")
        final_audit = state["finalization_audit"] or {}
        for item in final_audit.get("exclusions", []):
            reasons = ", ".join(item["reasons"])
            print(_safe(f"M8 exclusion · {item['player']} · {reasons}"))
        print("Receipt trail")
        for receipt in state["receipts"]:
            print(_safe(f"{receipt['event']} · {receipt['result']} · {receipt['event_key']}"))
        from fifth_pick.evaluation import evaluation_view

        evaluation = evaluation_view(store, run_id)
        process = evaluation["process"]
        outcomes = evaluation["outcomes"]
        independent = process["independent_review"]["status"]
        counts = ", ".join(
            f"{outcome} {count}" for outcome, count in outcomes["status_counts"].items() if count
        )
        print(f"Independent product review: {independent}")
        print(f"Recorded outcomes: {counts or 'none'}")
        print(f"Full evidence: fifth-pick audit --run-id {run_id}")
        print(f"Process and outcomes: fifth-pick evaluate --run-id {run_id}")


def run_menu(
    store: RunStore,
    dispatch: Dispatch,
    run_id: str | None = None,
    *,
    live_action: Callable[[Prompt], int] | None = None,
) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty() or os.name != "posix":
        print("Demo Mode requires an interactive terminal on macOS or Linux.", file=sys.stderr)
        return 1
    run_id = f"demo-{uuid4().hex[:12]}" if run_id is None else run_id
    terminal = Terminal()
    notice = ""
    try:
        with terminal._cbreak():
            while True:
                state = _read_state(store, run_id)
                action = terminal.choose(
                    _heading(run_id, state) + notice + "\nL Open Live Mode",
                    OPTIONS,
                    live_shortcut=True,
                )
                notice = ""
                if action is None or action == len(OPTIONS) - 1:
                    return 0
                try:
                    if action == len(OPTIONS):
                        terminal.screen("The Fifth Pick · Live Mode · slate status and collection")
                        if live_action is not None:
                            live_action(terminal.prompt)
                        else:
                            print("LIVE disabled. A separate owner grant is required.")
                    else:
                        terminal.screen(f"The Fifth Pick · Demo Mode\n{OPTIONS[action]}")
                        _perform(action, terminal, dispatch, store, run_id, state)
                except Back:
                    notice = "\nCancelled before submitting the action."
                    continue
                except (FifthPickError, ValueError, OSError) as exc:
                    print(f"Stopped: {exc}")
                terminal.pause()
    except (QuitMenu, KeyboardInterrupt):
        return 0
    except (FifthPickError, ValueError, OSError) as exc:
        print(f"Menu stopped: {exc}", file=sys.stderr)
        return 1
