import hashlib
import json
from pathlib import Path


BUDGET = 8000
THRESHOLD = int(BUDGET * 0.80)

KEEP = [
    "Complete Sortie 6 and prove that a fresh session can resume from the handoff without loss of intent.",
    "Open test point.",
    "Exact next action.",
    "AGENTS.md",
    "evolution-06/flight-card.md",
    "README.md",
    "evolution-06/runtime-ledger.jsonl",
    "L2 ledger outranks L1 canon.",
    "L1 canon outranks L3 derived views.",
    "A stale L3 view cannot block or override the ledger.",
]


class RuntimeLedger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event):
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")


def record_turn_budget(
    ledger,
    session,
    turn,
    prompt_tokens,
    completion_tokens,
    action="nothing",
):
    total = prompt_tokens + completion_tokens

    record = {
        "event": "turn_budget",
        "session": session,
        "turn": turn,
        "in": prompt_tokens,
        "out": completion_tokens,
        "total": total,
        "budget": BUDGET,
        "pct": round(100 * total / BUDGET),
        "action": action,
    }

    ledger.append(record)
    return record


def compact(history, ledger, before_tokens, keep=None):
    keep = KEEP if keep is None else keep

    summary = [
        "COMPACTED SESSION",
        "Older disposable conversation and tool detail removed.",
        "Declared keep list follows verbatim:",
    ]

    summary.extend(keep)
    compacted = "\n".join(summary)

    after_tokens = max(1, len(compacted) // 4)

    ledger.append(
        {
            "event": "compaction",
            "before": before_tokens,
            "after": after_tokens,
            "kept": keep,
        }
    )

    return compacted


def should_compact(total_tokens):
    return total_tokens > THRESHOLD


def write_handoff(path, ledger, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    sections = [
        ("Current state", data["current_state"]),
        ("Important context", data["important_context"]),
        ("Decisions with attribution", data["decisions"]),
        ("Next steps", data["next_steps"]),
        ("Pending work", data["pending_work"]),
        ("Verification checklist", data["verification"]),
        ("Evidence", data["evidence"]),
    ]

    text = "# Evolution 6 Handoff\n\n"

    for title, body in sections:
        text += f"## {title}\n\n{body}\n\n"

    path.write_text(text, encoding="utf-8")

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

    ledger.append(
        {
            "event": "handoff_written",
            "path": str(path),
            "sha256": digest,
        }
    )

    return digest


def load_resume(handoff_path, canon_paths, ledger_path):
    handoff = Path(handoff_path).read_text(encoding="utf-8")

    canon = {}
    for path in canon_paths:
        p = Path(path)
        if p.exists():
            canon[str(p)] = p.read_text(encoding="utf-8")

    ledger_events = []
    p = Path(ledger_path)

    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ledger_events.append(json.loads(line))

    return {
        "handoff": handoff,
        "canon": canon,
        "ledger": ledger_events,
    }


def resolve_layer_conflict(ledger, l2_value, l3_value):
    winner = l2_value

    ledger.append(
        {
            "event": "layer_conflict",
            "l2": l2_value,
            "l3": l3_value,
            "winner": "L2",
            "rule": "L2 > L1 > L3",
        }
    )

    return winner
