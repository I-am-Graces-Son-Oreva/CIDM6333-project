"""Human-readable views of records already validated by the CLI and run store."""

import os
import re
import shutil
import sys
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from itertools import zip_longest
from typing import Any


def safe(text: object) -> str:
    """Keep stored text from issuing terminal control sequences."""
    return "".join(char if char.isprintable() else " " for char in str(text))


def compact(text: object) -> str:
    """Abbreviate long references in the menu without changing stored IDs."""
    return re.sub(r"(?i)\b[0-9a-f]{32,}\b", lambda match: match[0][:10] + "…", safe(text))


def selection_keys(response: str, proposed: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    numbers = {str(index): item["candidate_key"] for index, item in enumerate(proposed, 1)}
    if not response.strip():
        return ()
    keys = []
    for token in response.split(","):
        number = re.sub(r"(?i)^selection\s*", "", token.strip()).removeprefix("#").strip()
        if number not in numbers:
            raise ValueError(
                "Enter the selection numbers shown in this proposal, separated by commas."
            )
        keys.append(numbers[number])
    return tuple(keys)


def label(value: object) -> str:
    return safe(value).replace("_", " ")


def details(value: Any, indent: str = "", *, exact: bool = False) -> None:
    """Display supplemental command details without exposing JSON syntax."""
    if isinstance(value, dict):
        for key, item in value.items():
            heading = label(key).capitalize()
            if isinstance(item, (dict, list)):
                note(f"{indent}{heading}:", verbatim=True)
                details(item, indent + "  ", exact=exact)
            else:
                note(f"{indent}{heading}: {_value(item, exact=exact)}", verbatim=True)
    elif isinstance(value, list):
        if not value:
            note(f"{indent}None", verbatim=True)
        for item in value:
            if isinstance(item, (dict, list)):
                note(f"{indent}-", verbatim=True)
                details(item, indent + "  ", exact=exact)
            else:
                note(f"{indent}- {_value(item, exact=exact)}", verbatim=True)


def _value(value: object, *, exact: bool = False) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return safe(value) if exact else compact(value)


def platform_name(value: str) -> str:
    return {"prizepicks": "PrizePicks", "underdog": "Underdog"}.get(value, safe(value))


def selection(item: dict[str, Any]) -> str:
    return safe(
        f"{item['player']} · {platform_name(item['platform'])} · {label(item['category'])} "
        f"{item['direction']} {item['projection']}"
    )


def _encoding() -> str:
    return sys.stdout.encoding or getattr(sys.__stdout__, "encoding", None) or "utf-8"


def console(text: str) -> str:
    encoding = _encoding()
    return text.encode(encoding, "backslashreplace").decode(encoding)


def _display(text: object) -> str:
    return console(safe(re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(text))))


def _cell_width(char: str) -> int:
    if unicodedata.category(char) in {"Mn", "Me"}:
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1


def _width(text: str) -> int:
    return sum(map(_cell_width, text))


def _wrap(text: str, width: int, *, verbatim: bool = False) -> list[str]:
    """Wrap safely by terminal cells, including unbroken identifiers."""
    lines = []
    line = ""
    words = re.findall(r" +|[^ ]+", text) if verbatim else text.split()
    separator = "" if verbatim else " "
    for word in words:
        if line and _width(line) + len(separator) + _width(word) > width:
            lines.append(line)
            line = ""
        if line:
            line += separator
        for char in word:
            if line and _width(line) + _cell_width(char) > width:
                lines.append(line)
                line = ""
            line += char
    return [*lines, line]


def ascii_borders() -> bool:
    encoding = _encoding()
    return (
        os.environ.get("TERM") == "dumb"
        or "┌─┐│└┘├┤┬┴┼".encode(encoding, "ignore").decode(encoding) != "┌─┐│└┘├┤┬┴┼"
    )


def _columns() -> int:
    return shutil.get_terminal_size((80, 24)).columns


def wrapped(text: object, *, margin: int = 0, verbatim: bool = False) -> str:
    """Wrap plain screen text while retaining explicit paragraph breaks."""
    width = max(2, _columns() - margin)
    return "\n".join(
        part
        for line in str(text).split("\n")
        for part in _wrap(_display(line), width, verbatim=verbatim)
    )


def note(text: object, *, verbatim: bool = False) -> None:
    print(wrapped(text, verbatim=verbatim))


def _box(
    widths: Sequence[int], rows: Iterable[Sequence[str]], *, title: str = "", grid: bool = True
) -> None:
    ascii_only = ascii_borders()
    horizontal, vertical = ("-", "|") if ascii_only else ("─", "│")

    def rule(kind: str, *, joined: bool = False) -> None:
        symbols = {"top": "┌┬┐", "title": "├┬┤", "middle": "├┼┤", "bottom": "└┴┘"}
        left, joint, right = ("+", "+", "+") if ascii_only else symbols[kind]
        lengths = (sum(widths) + 3 * (len(widths) - 1),) if joined else widths
        print(left + joint.join(horizontal * (width + 2) for width in lengths) + right)

    def row(values: Sequence[str], sizes: Sequence[int]) -> None:
        cells = [
            [part for paragraph in value.split("\n") for part in _wrap(paragraph, width)]
            for value, width in zip(values, sizes, strict=True)
        ]
        for line in zip_longest(*cells, fillvalue=""):
            padded = [
                " " + text + " " * (width - _width(text) + 1)
                for width, text in zip(sizes, line, strict=True)
            ]
            print(vertical + vertical.join(padded) + vertical)

    rule("top", joined=bool(title))
    if title:
        inner = sum(widths) + 3 * (len(widths) - 1)
        row((_display(title.upper()),), (inner,))
        rule("title")
    for index, values in enumerate(rows):
        if index and grid:
            rule("middle")
        row(values, widths)
    rule("bottom")


def panel(title: str, lines: Iterable[object], *, grid: bool = False) -> None:
    content = [("\n".join(map(_display, str(line).split("\n"))),) for line in lines]
    width = min(_columns(), 104) - 4
    _box((max(2, width),), content or [("None recorded.",)], title=title, grid=grid)


def fields(title: str, values: Iterable[tuple[str, object]]) -> None:
    rows = [(name, _display(value)) for name, value in values]
    width = min(_columns(), 104) - 7
    if width < 20:
        panel(title, (f"{name}: {value}" for name, value in rows), grid=True)
        return
    left = min(max((_width(name) for name, _ in rows), default=10), width // 3)
    _box((left, width - left), rows or [("Status", "None recorded.")], title=title)


def table(headings: Sequence[str], values: Iterable[Sequence[object]]) -> None:
    rows = [tuple(map(_display, row)) for row in values]
    if not rows:
        panel("Records", ("None recorded.",))
        return
    natural = [max(map(_width, column)) for column in zip(headings, *rows, strict=True)]
    widths = list(map(_width, headings))
    available = _columns() - 3 * len(widths) - 1
    if sum(widths) <= available:
        spare = min(available, sum(natural)) - sum(widths)
        while spare:
            for index, size in enumerate(natural):
                if widths[index] < size:
                    widths[index] += 1
                    spare -= 1
                    if not spare:
                        break
        _box(widths, (headings, *rows))
        return
    for index, row in enumerate(rows, 1):
        if index > 1:
            print()
        if headings[0] in {"Selection", "Candidate"}:
            fields(f"{headings[0]} {row[0]}", zip(headings[1:], row[1:], strict=True))
        else:
            fields(f"Record #{index}", zip(headings, row, strict=True))


def status_name(value: str) -> str:
    return {
        "AWAITING_JOSEPH": "Awaiting Joseph's Decision",
        "APPROVED_BY_JOSEPH": "Approved by Joseph",
        "REJECTED_BY_JOSEPH": "Rejected by Joseph",
        "BLOCKED": "Blocked",
    }.get(value, label(value))


def selection_fields(item: dict[str, Any]) -> list[tuple[str, object]]:
    return [
        ("Player", item["player"]),
        ("Platform", platform_name(item["platform"])),
        ("Market", label(item["category"])),
        ("Direction", item["direction"]),
        ("Projection", item["projection"]),
    ]


def review_assessments(reviews: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        review["event_key"]: review["current_audit"]
        for review in reviews
        if review["current_audit"]
    }


def supporting_evidence(
    item: dict[str, Any], assessment: dict[str, Any] | None = None
) -> list[str]:
    assessment = assessment or {}
    lines = []
    movement = item.get("projection_movement") or [
        snapshot["observation"]["projection"] for snapshot in assessment.get("snapshots", ())
    ]
    if movement:
        lines.append(f"Projection movement: {' → '.join(map(str, movement))}")
    for history in item.get("history", assessment.get("history", ())):
        kind = {"LAST_8": "Last 8", "SAME_SEASON_H2H": "Same-season head-to-head"}.get(
            history["kind"], label(history["kind"])
        )
        count = f"{history['favorable_count']}/{history['sample_count']} favorable"
        if history.get("incomplete"):
            count += " (incomplete sample)"
        lines.append(f"{kind}: {count}")
    ids = set(assessment.get("supporting_evidence_ids", ()))
    for evidence in assessment.get("evidence", ()):
        if evidence["evidence_id"] in ids:
            lines.append(f"Supporting signal: {evidence['claim']}")
    for gap in assessment.get("gaps", ()):
        lines.append(f"Evidence limitation: {gap['detail']}")
    if rationale := item.get("t20_rationale"):
        lines.append(f"Review rationale: {rationale}")
    return lines


def picks(
    items: Sequence[dict[str, Any]],
    *,
    supporting: bool = False,
    numbers: Sequence[int] = (),
    assessments: Mapping[str, dict[str, Any]] | None = None,
) -> None:
    assessments = assessments or {}
    if not items:
        panel("Selections", ("None.",))
    for index, item in enumerate(items, 1):
        if index > 1:
            print()
        number = numbers[index - 1] if numbers else index
        fields(
            f"Selection #{number}",
            (
                *selection_fields(item),
                ("Confidence", item["confidence"]),
                ("T-20 status", item["t20_status"]),
            ),
        )
        print()
        panel("Material risks", item["material_risks"])
        if supporting:
            print()
            panel(
                "Supporting evidence",
                supporting_evidence(item, assessments.get(item.get("t20_event_key", ""))),
            )


def audit_hint(run_id: str) -> None:
    note(f"Full audit JSON: uv run --offline --no-sync fifth-pick audit --run-id {safe(run_id)}")


def decision(final: dict[str, Any], audit: dict[str, Any]) -> None:
    approval = final["approval"]
    action = approval["action"]
    status = {
        "APPROVE": "Approved by Joseph",
        "REJECT": "Rejected by Joseph",
        "MODIFY": "Modified by Joseph · awaiting a new decision",
    }[action]
    overview = [
        ("Decision status", status),
        ("Decision authority", safe(approval["actor"])),
        ("Decision timestamp", safe(approval["decision_recorded_at"])),
        ("Decision receipt", compact(approval["decision_receipt_key"])),
    ]
    if approval["reason"]:
        overview.append(("Reason", compact(approval["reason"])))
    fields("Official decision", overview)

    original = next(
        (
            row["displayed_proposal"]["proposed"]
            for row in audit["finalization_audit"]["joseph_decisions"]
            if row["receipt_event_key"] == approval["decision_receipt_key"]
        ),
        None,
    )
    if original is None:
        print("Decision details unavailable. Inspect View Audit and Receipts.")
        audit_hint(final["run_id"])
        return
    if action == "APPROVE":
        print("\nApproved selections")
        picks(approval["official_final"])
    elif action == "REJECT":
        print("\nRejected selections")
        picks(original)
    else:
        selected = set(approval["decision_selection"])
        removed = [
            (i, item) for i, item in enumerate(original, 1) if item["candidate_key"] not in selected
        ]
        print("\nRetained in the revised proposal")
        picks(final["proposed"])
        print("\nRemoved from the proposal (original selection numbers)")
        picks([item for _, item in removed], numbers=[i for i, _ in removed])
        print("Joseph must decide on the revised proposal before any settlement.")
    if not (approval["official_final"] or final["proposed"]) or action == "REJECT":
        print("No approved selections." if action != "MODIFY" else "The revised proposal is empty.")
    print("\nAudit record: available in View Audit and Receipts.")
    audit_hint(final["run_id"])


def settlement(record: dict[str, Any], run_id: str) -> None:
    result = record["result"]
    fields(
        "Settlement recorded",
        (
            *selection_fields(record["selection"]),
            ("Recorded outcome", result["outcome"]),
            ("Evidence source", result["source"]),
            ("Recorded at", result["recorded_at"]),
            ("Result receipt", compact(record["result_receipt_event_key"])),
            ("Audit record", "Available in View Audit and Receipts"),
        ),
    )
    print()
    audit_hint(run_id)
