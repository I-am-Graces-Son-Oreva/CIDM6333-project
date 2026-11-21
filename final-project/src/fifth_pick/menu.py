"""Terminal-only navigation for the existing offline fixture workflow."""

import codecs
import io
import json
import os
import select
import sys
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from functools import partial
from pathlib import Path
from shutil import get_terminal_size
from typing import Any, TextIO, cast
from uuid import uuid4

from fifth_pick.errors import FifthPickError
from fifth_pick.finalization import NO_ENTRY_RECOMMENDATION, _manifest_start_board
from fifth_pick.fixture_workflow import audit_view, candidates_view
from fifth_pick.menu_presentation import (
    ascii_borders,
    audit_hint,
    compact,
    console,
    decision,
    details,
    fields,
    label,
    note,
    panel,
    picks,
    platform_name,
    review_assessments,
    selection_fields,
    settlement,
    status_name,
    supporting_evidence,
    table,
    wrapped,
)
from fifth_pick.menu_presentation import (
    safe as _safe,
)
from fifth_pick.menu_presentation import (
    selection as _selection,
)
from fifth_pick.slate_manifest import read_slate_run_context
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
PLATFORM_CODES = {"prizepicks": "PP", "underdog": "UD"}
MARKET_CODES = {
    "POINTS": ("PTS", "Points"),
    "REBOUNDS": ("REB", "Rebounds"),
    "ASSISTS": ("AST", "Assists"),
    "PRA": ("PRA", "Points + Rebounds + Assists"),
    "REBOUNDS_ASSISTS": ("RA", "Rebounds + Assists"),
}
NAVIGATION = "↑ / ↓ Move   Enter Select   Esc Back   Q Quit"
Prompt = Callable[[str], str]
Dispatch = Callable[[Sequence[str], Prompt], int]


class QuitMenu(Exception):
    """Return control to the shell."""


class Back(Exception):
    """Cancel the active prompt before submitting it."""


class Terminal:
    def __init__(self) -> None:
        self._output: TextIO | None = None
        self._clear = ""
        self._heading = ""
        self._buffer: io.StringIO | None = None
        self._form_context: list[str] = []

    @property
    def fullscreen(self) -> bool:
        return self._output is not None

    @staticmethod
    def _screen_codes() -> tuple[str, str, str] | None:
        if not sys.stdout.isatty() or os.environ.get("TERM") in (None, "", "dumb"):
            return None
        try:
            import curses
        except ImportError:
            return None
        try:
            curses.setupterm(fd=sys.stdout.fileno())
            enter, leave, clear = (
                curses.tigetstr(capability) for capability in ("smcup", "rmcup", "clear")
            )
            if enter and leave and clear:
                return enter.decode("ascii"), leave.decode("ascii"), clear.decode("ascii")
        except (curses.error, OSError, ValueError):
            pass
        return None

    @contextmanager
    def session(self) -> Generator[None]:
        codes = self._screen_codes()
        if codes is None:
            yield
            return
        enter, leave, self._clear = codes
        output = sys.stdout
        self._output = output
        try:
            print(enter, end="", file=output, flush=True)
            yield
        finally:
            self._output = None
            print(leave, end="", file=output, flush=True)

    @contextmanager
    def action_output(self) -> Generator[None]:
        if self._output is None:
            yield
            return
        buffer = io.StringIO()
        self._buffer = buffer
        self._form_context.clear()
        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                yield
        finally:
            self._buffer = None

    def _draw(self, message: str) -> None:
        clear = self._clear if self._output is not None else ""
        print(clear + console(message), file=self._output, flush=True)

    def _take_output(self) -> str:
        if self._buffer is None:
            return ""
        text = self._buffer.getvalue().strip("\n")
        self._buffer.seek(0)
        self._buffer.truncate()
        return text

    def _pages(self, body: str, *, before_prompt: bool = False) -> None:
        """Page the active report without writing its overflow to terminal history."""
        lines = wrapped(body, verbatim=True).splitlines()
        page = 0
        while True:
            size = max(1, get_terminal_size().lines - (5 if before_prompt else 4))
            last = max(0, (len(lines) - 1) // size)
            page = min(page, last)
            content = "\n".join(lines[page * size : (page + 1) * size])
            footer = []
            if last:
                footer.append(f"Page {page + 1}/{last + 1}  |  Up/Down to change page")
            if before_prompt:
                step = "continue to input" if page == last else "see the next page"
                footer.append(f"Enter to {step}  |  Esc to cancel  |  Q to quit")
            else:
                footer.append("Enter or Esc to return  |  Q to quit")
            self._draw("\n\n".join((content, wrapped("\n".join(footer)))))
            key = self.key()
            if key in (b"q", b"Q"):
                raise QuitMenu
            if key == "escape":
                if before_prompt:
                    raise Back
                return
            if key == "enter":
                if not before_prompt or page == last:
                    return
                page += 1
            elif key == "up":
                page = max(0, page - 1)
            elif key == "down":
                page = min(last, page + 1)

    @contextmanager
    def _cbreak(self, *, flush_input: bool = False) -> Generator[int]:
        import termios
        import tty

        fd = sys.stdin.fileno()
        settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd, termios.TCSANOW)
            yield fd
        finally:
            mode = termios.TCSAFLUSH if flush_input else termios.TCSADRAIN
            termios.tcsetattr(fd, mode, settings)

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
        self._heading = message
        self._form_context.clear()
        if self._buffer is not None:
            self._buffer.seek(0)
            self._buffer.truncate()
        self._draw(message)

    def choose(
        self,
        heading: str,
        labels: Sequence[str],
        *,
        live_shortcut: bool = False,
        render: Callable[[int], str] | None = None,
    ) -> int | None:
        selected = 0
        marker, navigation = (
            (">", "Up / Down Move   Enter Select   Esc Back   Q Quit")
            if ascii_borders()
            else ("›", NAVIGATION)
        )
        while True:
            if render is not None:
                self.screen(render(selected))
            else:
                rows = []
                for index, item in enumerate(labels):
                    first, *continuation = wrapped(item, margin=2).split("\n")
                    rows.append(f"{marker if index == selected else ' '} {first}")
                    rows.extend(f"  {line}" for line in continuation)
                self.screen("\n".join((wrapped(heading), "", *rows, "", wrapped(navigation))))
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
        text = wrapped(message)
        if self._output is None:
            print(text, flush=True)
            return self._prompt_input()
        latest = self._take_output()
        if latest:
            self._form_context.append(latest)
        body = "\n".join(part for part in (self._heading, *self._form_context) if part)
        remaining = get_terminal_size().lines - len(text.splitlines()) - 2
        revisit = None
        if body and len(wrapped(body, verbatim=True).splitlines()) > remaining:
            text = "\n".join((wrapped("Up to review form details"), text))

            def revisit() -> None:
                self._pages(body, before_prompt=True)
                self._draw(text)

            if latest:
                revisit()
            else:
                self._draw(text)
        else:
            self._draw("\n\n".join(part for part in (body, text) if part))
        with redirect_stdout(self._output):
            return self._prompt_input(revisit)

    def _prompt_input(self, revisit: Callable[[], None] | None = None) -> str:
        print("> ", end="", flush=True)
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
                    if key == "up" and revisit is not None:
                        revisit()
                        print("> " + console("".join(text)), end="", flush=True)
                    elif key in (b"\x7f", b"\x08"):
                        if text:
                            text.pop()
                            print("\b \b", end="", flush=True)
                    elif isinstance(key, bytes):
                        for char in decoder.decode(key):
                            if char.isprintable():
                                text.append(char)
                                print(console(char), end="", flush=True)
        except KeyboardInterrupt as exc:
            raise Back from exc
        finally:
            print()

    def pause(self) -> None:
        if self._output is not None:
            body = "\n".join(part for part in (self._heading, self._take_output()) if part)
            self._pages(body)
            return
        print("\nEnter or Esc to return  |  Q to quit", flush=True)
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


def _main_menu(
    store: RunStore,
    run_id: str,
    state: dict[str, Any],
    selected: int,
    notice: str,
    *,
    allow_style: bool = True,
) -> str:
    stages = len(state["stages"])
    final = state.get("final") or {}
    status = final.get("state")
    approved = (final.get("approval") or {}).get("official_final") or ()
    settled = len((state.get("results") or {}).get("results") or ())
    problem = state.get("problem")
    awaiting_entry = status == "AWAITING_JOSEPH" and bool(final.get("proposed"))
    if problem:
        guidance = f"Run verification stopped: {compact(problem)} Check the run's audit JSON."
    elif stages < 2:
        guidance = f"Record Snapshot {stages + 1} using Analyze NBA Slate."
    elif stages == 2:
        guidance = "Review provisional candidates, then run T-20 Review."
    elif not final:
        guidance = "Open Final Recommendations to create the proposal."
    elif awaiting_entry:
        guidance = "Joseph can review and submit his decision."
    elif approved and settled < len(approved):
        guidance = "Record results when supported outcomes are available."
    elif not final.get("proposed") and status != "BLOCKED":
        guidance = "No entry recommended. Review the audit and receipts."
    else:
        guidance = "Review the audit and receipts."

    separator = " | " if ascii_borders() else " · "
    slate = "No slate recorded"
    if stages:
        context = read_slate_run_context(store, run_id)
        games = len(_manifest_start_board(context).events)
        slate = f"{context.metadata.slate_date}{separator}{games} game{'s' if games != 1 else ''}"
    summary = wrapped(f"Demo Mode{separator}{'Slate unverified' if problem else slate}")
    decision_status = {
        "AWAITING_JOSEPH": "Awaiting Joseph" if awaiting_entry else "Optional (no entry)",
        "APPROVED_BY_JOSEPH": "Approved",
        "REJECTED_BY_JOSEPH": "Rejected",
        "BLOCKED": "Blocked",
    }.get(status, "Unverified" if problem else "Pending")
    snapshot_status = "Unverified" if problem else f"{stages}/3"
    result_status = "Unverified" if problem else f"{settled}/{len(approved)}"
    progress = wrapped(
        separator.join(
            (
                f"Snapshots: {snapshot_status}",
                f"Decision: {decision_status}",
                f"Results: {result_status}",
            )
        )
    )

    styled = (
        allow_style and sys.stdout.isatty() and not ascii_borders() and "NO_COLOR" not in os.environ
    )
    title, main, next_action = (
        f"\033[1m{heading}\033[0m" if styled else heading
        for heading in ("THE FIFTH PICK", "MAIN MENU", "NEXT ACTION")
    )
    options = []
    for index, name in enumerate(OPTIONS):
        highlighted = index == selected
        marker = ">" if highlighted else " "
        weight = "\033[1;97m" if highlighted else "\033[1m"
        options.append(f"{marker} {weight}{name}\033[0m" if styled else f"{marker} {name}")
    footer = wrapped(
        separator.join(
            (
                "Up / Down Navigate" if ascii_borders() else "↑ ↓ Navigate",
                "Enter Select",
                "Esc Back",
                "Q Quit",
            )
        )
    )
    message = [wrapped(notice.strip())] if notice else []
    spacious = [
        title,
        "",
        summary,
        progress,
        *message,
        "",
        main,
        "",
        "\n\n".join(options),
        "",
        next_action,
        "",
        wrapped(guidance),
        "",
        footer,
        "L Open Live Mode",
    ]
    text = "\n".join(spacious)
    if len(text.splitlines()) < get_terminal_size().lines:
        return text
    return "\n".join(
        (
            title,
            summary,
            progress,
            *message,
            "",
            main,
            *options,
            "",
            next_action,
            wrapped(guidance),
            "",
            footer,
            "L Open Live Mode",
        )
    )


def _capture(
    terminal: Terminal,
    invoke: Callable[[Prompt], int],
    *,
    show_details: bool = False,
    exact_details: bool = False,
) -> dict[str, Any] | None:
    """Present command messages before every prompt and decode its structured output."""
    display = sys.stdout
    output, errors = io.StringIO(), io.StringIO()
    payload = None

    def flush(*, structured: bool) -> None:
        nonlocal payload
        with redirect_stdout(display):
            transcript = output.getvalue()
            for line in transcript.removesuffix("\n").split("\n") if transcript else ():
                try:
                    record = json.loads(line) if line.startswith("{") else None
                except json.JSONDecodeError:
                    record = None
                if not isinstance(record, dict):
                    if line.startswith(("┌", "├", "└", "│", "+", "|")):
                        print(console(_safe(line)))  # Keep box padding.
                    elif line.startswith("Evidence excerpt: "):
                        note(line, verbatim=True)  # Preserve the full excerpt before attestation.
                    else:
                        note(compact(line))
                elif structured:
                    details(record, exact=exact_details)
                else:
                    payload = record
            for line in errors.getvalue().splitlines():
                note(compact(line))
        for buffer in (output, errors):
            buffer.seek(0)
            buffer.truncate()

    def prompt(message: str) -> str:
        flush(structured=True)
        with redirect_stdout(display):
            return terminal.prompt(_safe(message))

    with redirect_stdout(output), redirect_stderr(errors):
        code = invoke(prompt)
    if code:
        print("Action stopped.", file=display)
    flush(structured=show_details or bool(code))
    if code:
        return None
    return payload


def _show_final(final: dict[str, Any], state: dict[str, Any]) -> None:
    overview = []
    if final.get("state"):
        overview.append(("Status", status_name(final["state"])))
    if slate := final.get("slate"):
        overview.extend(
            (
                ("Slate date", slate["slate_date"]),
                ("Games", slate["game_count"]),
                ("Selection limit", f"maximum {slate['maximum_selections']} selections"),
            )
        )
    if recommendation := final.get("recommendation"):
        overview.append(("Recommendation", recommendation))
    fields("Final recommendations", overview)
    items = final.get("proposed", ())
    if not items:
        note("No selections in this proposal.")
        return
    print()
    picks(items, supporting=True, assessments=review_assessments(state["t20_reviews"]))
    print()
    note("Confidence reflects the available evidence. No outcome is guaranteed.")
    if final.get("state") == "AWAITING_JOSEPH":
        note("Next: Joseph can review the proposal in Approve / Reject / Modify.")


def _show_final_recommendations(final: dict[str, Any], state: dict[str, Any]) -> None:
    separator = " | " if ascii_borders() else " · "
    status = final["state"]
    approval = (state.get("final") or {}).get("approval") or {}
    modified = status == "AWAITING_JOSEPH" and approval.get("action") == "MODIFY"
    decision_status = (
        "Modified by Joseph (awaiting a new decision)"
        if modified
        else {"AWAITING_JOSEPH": "Awaiting Joseph", "NO_ENTRY": "Optional (no entry)"}.get(
            status, status_name(status)
        )
    )
    note(f"THE FIFTH PICK{separator}FINAL RECOMMENDATIONS")
    print()
    slate = final["slate"]
    games = slate["game_count"]
    note(
        separator.join(
            ("Demo Mode", slate["slate_date"], f"{games} game{'s' if games != 1 else ''}")
        )
    )
    note(f"Decision: {decision_status}{separator}Limit: {slate['maximum_selections']} selections")
    print()
    items = final["proposed"]
    if not items:
        if status == "REJECTED_BY_JOSEPH":
            note("No selections remain. Joseph rejected the proposal.")
        elif modified:
            note("No entry. The revised proposal is empty.")
        elif final.get("recommendation") != NO_ENTRY_RECOMMENDATION:
            note("No entry. No selections in this proposal.")
        if final.get("recommendation") == NO_ENTRY_RECOMMENDATION:
            note(NO_ENTRY_RECOMMENDATION)
        print()
        note("NEXT ACTION")
        note("View Audit and Receipts")
        return

    note(
        "REVISED PROPOSAL"
        if modified
        else {
            "APPROVED_BY_JOSEPH": "APPROVED FINAL SLATE",
            "REJECTED_BY_JOSEPH": "REJECTED PROPOSAL",
        }.get(status, "RECOMMENDED FINAL SLATE")
    )
    print()
    legend = {}
    rows = []
    risks = []
    evidence_lines = []
    gaps = []
    reviews = {review["event_key"]: review for review in state["t20_reviews"]}
    for number, item in enumerate(items, 1):
        name = f"#{number} {item['player']}"
        platform = PLATFORM_CODES.get(item["platform"])
        if platform:
            legend[platform] = platform_name(item["platform"])
        market = MARKET_CODES.get(item["category"])
        if market:
            legend[market[0]] = market[1]
        recorded_t20 = item.get("t20_status") or "Pending"
        t20 = {"STILL STRONG": "Strong", "REMOVE RECOMMENDED": "Remove"}.get(
            recorded_t20, label(recorded_t20).capitalize()
        )
        if t20 != recorded_t20.capitalize():
            legend[t20] = f"{recorded_t20.title()} at T-20"
        rows.append(
            (
                number,
                item["player"],
                platform or platform_name(item["platform"]),
                market[0] if market else label(item["category"]),
                item["direction"].title(),
                item["projection"],
                (item.get("confidence") or "Pending").title(),
                t20,
            )
        )

        review = reviews.get(item.get("t20_event_key"), {})
        assessment = review.get("current_audit") or {}
        recorded_risks = {claim: claim for claim in item.get("material_risks", ())}
        for entry in assessment.get("evidence", ()):
            if entry.get("effect") == "CONFLICT" and entry.get("significance") != "MINOR":
                claim = entry["claim"]
                recorded_risks[claim] = f"Contradictory evidence: {claim}"
        risks.append(
            (name, separator.join(recorded_risks.values()) or "No material risks recorded.")
        )
        supporting = supporting_evidence(item, {**assessment, "gaps": ()})
        evidence_lines.append(
            (name, separator.join(supporting) or "No supporting details recorded.")
        )
        limitations = dict.fromkeys(
            (
                *review.get("readiness_gaps", ()),
                *(gap["detail"] for gap in assessment.get("gaps", ())),
            )
        )
        if limitations:
            gaps.append((name, separator.join(limitations)))

    table(("#", "Player", "Plat", "Market", "Pick", "Line", "Confidence", "T-20"), rows)
    if legend:
        print()
        note(separator.join(f"{code} = {meaning}" for code, meaning in legend.items()))
    for title, entries in (
        ("KEY RISKS", risks),
        ("SUPPORTING EVIDENCE", evidence_lines),
        ("EVIDENCE GAPS", gaps),
    ):
        if entries:
            print()
            note(title)
            print()
            for name, content in entries:
                first, *continuation = wrapped(f"{name}{separator}{content}", margin=2).split("\n")
                print(first)
                for line in continuation:
                    print(f"  {line}")
    print()
    note("Confidence reflects available evidence. No outcome is guaranteed.")
    print()
    note("NEXT ACTION")
    if status == "AWAITING_JOSEPH":
        note("Approve / Reject / Modify")
    elif status == "APPROVED_BY_JOSEPH" and len(
        (state.get("results") or {}).get("results", ())
    ) < len(items):
        note("Record results when supported outcomes are available.")
    else:
        note("View Audit and Receipts")


def _slate_fields(store: RunStore, run_id: str, stages: int) -> list[tuple[str, object]]:
    context = read_slate_run_context(store, run_id)
    return [
        ("Mode", "Demo Mode · Offline synthetic fixtures"),
        ("Run", run_id),
        ("Slate date", context.metadata.slate_date),
        ("Games", len(_manifest_start_board(context).events)),
        ("Snapshot stage", f"{stages}/3"),
    ]


def _show_reviews(state: dict[str, Any]) -> None:
    if not state["t20_reviews"]:
        panel("T-20 review", ("No candidate reviews recorded.",))
    for index, review in enumerate(state["t20_reviews"], 1):
        if index > 1:
            print()
        current = review["current_audit"] or {}
        prior = review["previous_audit"] or {}
        candidate = current.get("candidate") or prior.get("candidate")
        data = selection_fields(candidate) if candidate else []
        data.extend(
            (
                ("Conclusion", review["conclusion"]),
                (
                    "Snapshot 3",
                    review["snapshot_3_recorded_at"] or "Unavailable for this candidate",
                ),
            )
        )
        fields(f"T-20 review · Candidate #{index}", data)
        assessed = current or prior
        print()
        panel(
            "Material risks",
            (
                item["claim"]
                for item in assessed.get("evidence", ())
                if item["evidence_id"] in assessed["meaningful_risk_ids"]
            ),
        )
        if assessed:
            print()
            title = "Supporting evidence" if current else "Supporting evidence · Prior assessment"
            lines = supporting_evidence(
                {"t20_rationale": assessed.get("methodology_rationale")},
                {**assessed, "gaps": []},
            )
            panel(title, lines)
        gaps = [
            *map(label, review["reason_codes"]),
            *review["readiness_gaps"],
            *(gap["detail"] for gap in assessed.get("gaps", ())),
        ]
        if gaps:
            print()
            panel("Evidence gaps and review reasons", dict.fromkeys(gaps))


def _show_t20_report(store: RunStore, run_id: str, state: dict[str, Any]) -> None:
    separator = " | " if ascii_borders() else " · "
    context = read_slate_run_context(store, run_id)
    game_count = len(_manifest_start_board(context).events)
    note(
        separator.join(
            (
                "Demo Mode",
                context.metadata.slate_date,
                f"{game_count} game{'s' if game_count != 1 else ''}",
            )
        )
    )
    accepted = sum(
        entry["kind"] == "snapshot" and entry["number"] == 3 for entry in state["snapshots"]
    )
    observations = "observation" if accepted == 1 else "observations"
    note(f"Snapshot 3 recorded{separator}{accepted} {observations} accepted")
    print()

    legend = {}
    rows = []
    risks = []
    evidence = []
    gaps = []
    for number, review in enumerate(state["t20_reviews"], 1):
        current = review.get("current_audit") or {}
        prior = review.get("previous_audit") or {}
        candidate = current.get("candidate") or prior.get("candidate") or {}
        player = candidate.get("player") or "Unavailable"
        platform = candidate.get("platform")
        platform_code = PLATFORM_CODES.get(platform)
        if platform and platform_code:
            legend[platform_code] = platform_name(platform)
        category = candidate.get("category")
        market = MARKET_CODES.get(category)
        if market:
            legend[market[0]] = market[1]
        pending = "-" if ascii_borders() else "—"
        conclusion = review.get("conclusion") or "Unavailable"
        display_result = {
            "STILL STRONG": "Still Strong",
            "REMOVE RECOMMENDED": "Remove",
        }.get(conclusion, label(conclusion).capitalize())
        if conclusion == "REMOVE RECOMMENDED":
            legend["Remove"] = "Remove Recommended"
        line = (review.get("projection") or {}).get("at_t20")
        direction = candidate.get("direction")
        rows.append(
            (
                number,
                player,
                platform_code or (platform_name(platform) if platform else pending),
                market[0] if market else label(category) if category else pending,
                direction.title() if direction else pending,
                line if line is not None else pending,
                display_result,
            )
        )

        assessed = current or prior
        risk_ids = set(assessed.get("meaningful_risk_ids", ()))
        recorded_risks = [
            item["claim"]
            for item in assessed.get("evidence", ())
            if item["evidence_id"] in risk_ids
        ]
        if disclosure := assessed.get("senior_lower_disclosure"):
            recorded_risks.append(disclosure)
        if recorded_risks:
            source = " (prior assessment)" if not current else ""
            risks.append((f"#{number} {player}{source}", recorded_risks))
        supporting = supporting_evidence(
            {"t20_rationale": assessed.get("methodology_rationale")},
            {**assessed, "gaps": ()},
        )
        if supporting:
            scope = " (prior assessment)" if not current else ""
            evidence.append((f"#{number}{scope}", supporting))
        reasons = dict.fromkeys(
            (
                *map(label, review.get("reason_codes", ())),
                *review.get("readiness_gaps", ()),
                *(gap["detail"] for gap in assessed.get("gaps", ())),
                *review.get("audit_reasons", ()),
            )
        )
        if reasons:
            gaps.append((f"#{number}", tuple(reasons)))

    if rows:
        table(("#", "Player", "Plat", "Market", "Pick", "Line", "T-20 Result"), rows)
        if legend:
            print()
            note(separator.join(f"{code} = {text}" for code, text in legend.items()))
    else:
        note("No candidate reviews recorded.")
    for title, entries, empty in (
        ("MATERIAL RISKS", risks, "No material risks recorded."),
        ("SUPPORTING EVIDENCE", evidence, "No supporting details recorded."),
        ("EVIDENCE GAPS & REVIEW REASONS", gaps, "No evidence gaps or review reasons recorded."),
    ):
        print()
        note(title)
        if not entries:
            note(empty)
        for name, content in entries:
            first, *continuation = wrapped(
                f"{name}{separator}{separator.join(content)}", margin=2
            ).split("\n")
            print(first)
            for line in continuation:
                print(f"  {line}")
    print()
    note("T-20 conclusions are recommendations for Joseph’s review.")
    print()
    note("NEXT ACTION")
    note("View Final Recommendations")


def _show_candidates(store: RunStore, run_id: str, state: dict[str, Any]) -> None:
    view = cast(dict[str, Any], candidates_view(store, run_id))
    ranks = {
        key: index for index, key in enumerate(state["stages"][-1]["m6_ranked_candidate_keys"], 1)
    }
    stage = len(state["stages"])
    separator = " | " if ascii_borders() else " · "
    phase = "Provisional watchlist" if stage < 3 else "T-20 reviewed"
    note(separator.join(("Demo Mode", f"Snapshot {stage}/3", phase)))
    print()

    rows = sorted(
        view["candidates"], key=lambda row: ranks.get(row["candidate_key"], len(ranks) + 1)
    )
    confidence = {
        review["candidate_key"]: review["current_confidence"] for review in state["t20_reviews"]
    }
    legend = {}
    comparison = []
    for index, row in enumerate(rows, 1):
        key = row["candidate_key"]
        platform = PLATFORM_CODES.get(row["platform"])
        if platform:
            legend[platform] = platform_name(row["platform"])
        market = MARKET_CODES.get(row["category"])
        if market:
            legend[market[0]] = market[1]
        status = row.get("status")
        if status == "PROVISIONAL":
            status = {
                "PROVIDED": "Provided",
                "UNAVAILABLE": "Evidence gap",
            }.get(row.get("supporting_evidence"), "Pending")
        comparison.append(
            (
                index if stage < 3 else ranks.get(key, "-"),
                row["player"],
                platform or platform_name(row["platform"]),
                market[0] if market else label(row["category"]),
                row["direction"].title(),
                row["projection"],
                (confidence.get(key) or "Pending").title(),
                status.capitalize() if status else "Pending",
            )
        )
    if comparison:
        table(("#", "Player", "Plat", "Market", "Pick", "Line", "Confidence", "Status"), comparison)
        if legend:
            print()
            note(separator.join(f"{code} = {meaning}" for code, meaning in legend.items()))
    else:
        note("No candidates recorded for this snapshot.")
    print()
    if stage == 1:
        note("Next: Record Snapshot 2 using Analyze NBA Slate.")
    elif stage == 2:
        note("Next: Run T-20 Review.")
    else:
        note("Next: View Final Recommendations.")


def _show_audit(store: RunStore, run_id: str, state: dict[str, Any]) -> None:
    from fifth_pick.evaluation import evaluation_view

    stages = len(state["stages"])
    final = state["final"]
    note(f"Run {run_id} · verified audit and receipts")
    fields(
        "Run summary",
        (
            *_slate_fields(store, run_id, stages),
            ("Board records", len(state["board_manifests"])),
            ("Snapshot records", len(state["snapshots"])),
        ),
    )
    print("\nSnapshot history")
    table(
        ("Snapshot", "Observed at"),
        ((stage["snapshot"], stage["observed_at"]) for stage in state["stages"]),
    )
    print("\nCandidate reviews")
    _show_reviews(state)
    final_audit = state["finalization_audit"] or {}
    for item in final_audit.get("exclusions", []):
        reasons = ", ".join(item["reasons"])
        note(compact(f"Excluded from final proposal · {item['player']} · {label(reasons)}"))
    if final:
        print("\nFinal proposal")
        _show_final(final, state)
    print("\nHuman decisions")
    table(
        ("Decision", "Authority", "Recorded at", "Receipt"),
        (
            (row["action"], row["actor"], row["recorded_at"], compact(row["receipt_event_key"]))
            for row in final_audit.get("joseph_decisions", ())
        ),
    )
    print("\nRecorded results")
    table(
        ("Pick", "Outcome", "Recorded at"),
        (
            (_selection(row["selection"]), row["result"]["outcome"], row["result"]["recorded_at"])
            for row in (state["results"] or {}).get("results", ())
        ),
    )
    print("\nReceipt trail")
    table(
        ("Timestamp", "Event", "Result", "Receipt"),
        (
            (
                receipt["timestamp"],
                label(receipt["event"]),
                label(receipt["result"]),
                compact(receipt["event_key"]),
            )
            for receipt in state["receipts"]
        ),
    )
    evaluation = evaluation_view(store, run_id)
    process = evaluation["process"]
    outcomes = evaluation["outcomes"]
    independent = process["independent_review"]["status"]
    counts = ", ".join(
        f"{outcome} {count}" for outcome, count in outcomes["status_counts"].items() if count
    )
    print(f"Independent product review: {independent}")
    print(f"Recorded outcomes: {counts or 'none'}")
    audit_hint(run_id)
    note(f"Process and outcomes: fifth-pick evaluate --run-id {run_id}")


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

    def run(*args: str) -> dict[str, Any] | None:
        return _capture(terminal, lambda read: dispatch(args, read))

    def confirm(message: str) -> None:
        if terminal.choose(message, ("Cancel", "Continue")) != 1:
            raise Back
        if terminal.fullscreen:
            terminal.screen("")

    if action == 0:
        if stages >= 2:
            fields(
                "Slate status",
                (
                    *_slate_fields(store, run_id, stages),
                    ("Status", "Snapshots 1 and 2 already recorded"),
                    (
                        "Next action",
                        "Run T-20 Review" if stages == 2 else "View Final Recommendations",
                    ),
                ),
            )
            return
        number = stages + 1
        confirm(f"Record Snapshot {number} using the bundled offline fixture?")
        row = run("analyze", *base, "--snapshot", str(number), "--fixture", str(DEMO / str(number)))
        if row:
            fields(
                "Snapshot recorded",
                (
                    *_slate_fields(store, run_id, number),
                    ("Status", label(row["status"])),
                    ("Observed at", row["observed_at"]),
                    ("Accepted observations", row["observations"]),
                    (
                        "Next action",
                        "Analyze NBA Slate for Snapshot 2"
                        if number == 1
                        else "Run T-20 Review for Snapshot 3",
                    ),
                ),
            )
    elif action == 1:
        if not stages:
            print("Use Analyze NBA Slate to create a provisional watchlist.")
            return
        _show_candidates(store, run_id, state)
    elif action == 2:
        if stages < 2:
            print("Finish Snapshots 1 and 2 first.")
            return
        if stages == 2:
            confirm("Record Snapshot 3 and run the offline T-20 review?")
            if not run("t20", *base, "--fixture", str(DEMO / "3")):
                return
            state = _read_state(store, run_id)
        separator = " | " if ascii_borders() else " · "
        terminal.screen(f"THE FIFTH PICK{separator}T-20 REVIEW")
        _show_t20_report(store, run_id, state)
    elif action == 3:
        if stages != 3:
            print("Complete the T-20 review before final recommendations.")
            return
        if not final:
            confirm("Create and save a final proposal for Joseph's review?")
        proposal = run("final", *base)
        if proposal:
            terminal.screen("")
            _show_final_recommendations(proposal, _read_state(store, run_id))
    elif action == 4:
        if not final or final["state"] != "AWAITING_JOSEPH":
            print("A pending final proposal is required for a decision.")
            return
        confirm("Open Joseph's decision form? The typed action will be recorded.")
        print("Only Joseph may enter APPROVE, REJECT, or MODIFY. Esc cancels.")
        recorded = run("decide", *base)
        if recorded:
            print()
            decision(recorded, _read_state(store, run_id))
    elif action == 5:
        if not final or final["state"] != "APPROVED_BY_JOSEPH":
            print("Settlement blocked. Joseph's receipt-verified approval is required.")
            return
        selections = final["approval"]["official_final"]
        if not selections:
            print("No approved selections to settle.")
            return
        index = terminal.choose(
            "Select an approved pick to settle",
            tuple(f"Selection #{i}: {_selection(item)}" for i, item in enumerate(selections, 1)),
        )
        if index is None:
            raise Back
        item = selections[index]
        confirm(f"Open the synthetic settlement form for Selection #{index + 1}?")
        print("Use source synthetic-fixture. At the reference prompt, type FIXTURE.")
        print("Enter the synthetic result and verify its excerpt. Esc cancels.")
        recorded = run("result", "record", *base, "--selection", item["candidate_key"])
        if recorded:
            results = _read_state(store, run_id)["results"]["results"]
            match = next(
                entry for entry in results if entry["selection_id"] == recorded["selection_id"]
            )
            settlement(match, run_id)
    elif action == 6:
        if not stages:
            print("No audit or receipts yet.")
            return
        _show_audit(store, run_id, state)


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
        with terminal.session(), terminal._cbreak(flush_input=True):
            while True:
                try:
                    state = _read_state(store, run_id)
                except (FifthPickError, ValueError, OSError, TypeError, KeyError) as exc:
                    state = {"stages": [], "problem": str(exc) or type(exc).__name__}
                action = terminal.choose(
                    "",
                    OPTIONS,
                    live_shortcut=True,
                    render=partial(
                        _main_menu,
                        store,
                        run_id,
                        state,
                        notice=notice,
                        allow_style=terminal.fullscreen,
                    ),
                )
                notice = ""
                if action is None or action == len(OPTIONS) - 1:
                    return 0
                with terminal.action_output():
                    try:
                        if action == len(OPTIONS):
                            terminal.screen(
                                "The Fifth Pick · Live Mode · slate status and collection"
                            )
                            if live_action is not None:
                                _capture(
                                    terminal, live_action, show_details=True, exact_details=True
                                )
                            else:
                                print("LIVE disabled. A separate owner grant is required.")
                        else:
                            if action == 1:
                                separator = " | " if ascii_borders() else " · "
                                heading = f"THE FIFTH PICK{separator}CANDIDATES & RANKINGS"
                            else:
                                heading = f"The Fifth Pick · Demo Mode\n{OPTIONS[action]}"
                            terminal.screen(heading)
                            if state.get("problem"):
                                note("Stored run could not be verified. No action was recorded.")
                                audit_hint(run_id)
                            else:
                                _perform(action, terminal, dispatch, store, run_id, state)
                    except Back:
                        notice = "\nCancelled before submitting the action."
                        continue
                    except (KeyError, TypeError) as exc:
                        note(
                            "Stored data could not be displayed. "
                            f"See audit JSON for details ({compact(exc)})."
                        )
                    except (FifthPickError, ValueError, OSError) as exc:
                        note(f"Stopped: {compact(exc)}")
                    terminal.pause()
    except (QuitMenu, KeyboardInterrupt):
        return 0
    except (FifthPickError, ValueError, OSError) as exc:
        print(wrapped(f"Menu stopped: {compact(exc)}"), file=sys.stderr)
        return 1
