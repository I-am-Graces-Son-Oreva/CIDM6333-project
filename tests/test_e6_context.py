import json

from src.e6_context.context_engine import (
    BUDGET,
    KEEP,
    RuntimeLedger,
    compact,
    load_resume,
    record_turn_budget,
    resolve_layer_conflict,
    should_compact,
    write_handoff,
)


def read_events(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_one_turn_budget_record_per_model_call(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = RuntimeLedger(ledger_path)

    calls = [
        (900, 100),
        (1100, 120),
        (1300, 140),
        (1500, 160),
        (1700, 180),
        (5900, 700),
    ]

    for turn, (prompt_tokens, completion_tokens) in enumerate(calls, 1):
        total = prompt_tokens + completion_tokens
        action = "compact" if should_compact(total) else "nothing"

        record_turn_budget(
            ledger,
            "A",
            turn,
            prompt_tokens,
            completion_tokens,
            action,
        )

    events = read_events(ledger_path)
    budget_events = [e for e in events if e["event"] == "turn_budget"]

    assert len(budget_events) == len(calls)

    for event in budget_events:
        assert event["budget"] == BUDGET
        assert event["total"] == event["in"] + event["out"]
        assert "pct" in event
        assert "action" in event


def test_keep_list_survives_compaction_word_for_word(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = RuntimeLedger(ledger_path)

    compacted = compact(
        "large disposable history",
        ledger,
        before_tokens=6600,
    )

    for item in KEEP:
        assert item in compacted

    events = read_events(ledger_path)
    event = events[-1]

    assert event["event"] == "compaction"
    assert event["before"] == 6600
    assert event["after"] < event["before"]
    assert event["kept"] == KEEP


def test_handoff_has_seven_sections_and_hash(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = RuntimeLedger(ledger_path)
    handoff_path = tmp_path / "handoff.md"

    digest = write_handoff(
        handoff_path,
        ledger,
        {
            "current_state": "Session A completed the bounded task.",
            "important_context": "Resume without Session A transcript.",
            "decisions": "Joseph declared L2 > L1 > L3 in Flight Card 6.",
            "next_steps": "1. Read the runtime ledger and verify the latest event.",
            "pending_work": "Run fresh Session B.",
            "verification": "Run pytest and inspect the ledger.",
            "evidence": "evolution-06/runtime-ledger.jsonl",
        },
    )

    text = handoff_path.read_text(encoding="utf-8")

    required = [
        "## Current state",
        "## Important context",
        "## Decisions with attribution",
        "## Next steps",
        "## Pending work",
        "## Verification checklist",
        "## Evidence",
    ]

    for heading in required:
        assert heading in text

    assert len(digest) == 64

    events = read_events(ledger_path)
    assert events[-1]["event"] == "handoff_written"
    assert events[-1]["sha256"] == digest


def test_resume_loader_uses_files_not_old_transcript(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = RuntimeLedger(ledger_path)

    ledger.append(
        {
            "event": "turn_budget",
            "session": "A",
            "turn": 1,
            "total": 1000,
        }
    )

    handoff = tmp_path / "handoff.md"
    handoff.write_text(
        "NEXT STEP 1: Read the runtime ledger.",
        encoding="utf-8",
    )

    canon = tmp_path / "canon.md"
    canon.write_text(
        "L2 > L1 > L3",
        encoding="utf-8",
    )

    state = load_resume(
        handoff,
        [canon],
        ledger_path,
    )

    assert "NEXT STEP 1: Read the runtime ledger." in state["handoff"]
    assert state["canon"][str(canon)] == "L2 > L1 > L3"
    assert state["ledger"][0]["session"] == "A"
    assert "transcript" not in state


def test_stale_l3_loses_to_l2(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = RuntimeLedger(ledger_path)

    result = resolve_layer_conflict(
        ledger,
        l2_value="Sortie status: GO",
        l3_value="Sortie status: NO-GO",
    )

    assert result == "Sortie status: GO"

    events = read_events(ledger_path)
    conflict = events[-1]

    assert conflict["event"] == "layer_conflict"
    assert conflict["winner"] == "L2"
    assert conflict["rule"] == "L2 > L1 > L3"
