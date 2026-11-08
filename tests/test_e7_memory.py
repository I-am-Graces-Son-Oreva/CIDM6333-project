import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "evolution-07"
    / "lab"
    / "recall.py"
)


def run_memory(tmp_path, *args):
    """Run a private copy so real memories are untouched."""
    script = tmp_path / "recall.py"
    if not script.exists():
        script.write_text(SCRIPT.read_text())

    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=True
    )


def test_remember_and_recall(tmp_path):
    run_memory(
        tmp_path, "remember",
        "--text", "Sortie 6 Chase verdict PASS",
        "--source", "evolution-06/flight-log.md",
        "--until", "2026-12-15"
    )

    result = run_memory(
        tmp_path, "recall",
        "--question", "Sortie 6 verdict"
    )

    assert "m-0001" in result.stdout
    assert "PASS" in result.stdout


def test_eviction(tmp_path):
    run_memory(
        tmp_path, "remember",
        "--text", "purple elephant expired memory",
        "--source", "test",
        "--until", "2026-10-01"
    )

    run_memory(
        tmp_path, "evict",
        "--today", "2026-11-08"
    )

    result = run_memory(
        tmp_path, "recall",
        "--question", "purple elephant"
    )

    assert "Not in memory." in result.stdout

    ledger = [
        json.loads(line)
        for line in (tmp_path / "memory-ledger.jsonl").read_text().splitlines()
    ]

    assert any(event["event"] == "evict" for event in ledger)


def test_forget(tmp_path):
    run_memory(
        tmp_path, "remember",
        "--text", "temporary memory for forgetting",
        "--source", "test",
        "--until", "2026-12-15"
    )

    run_memory(
        tmp_path, "forget",
        "--id", "m-0001",
        "--reason", "user_requested"
    )

    result = run_memory(
        tmp_path, "recall",
        "--question", "temporary memory"
    )

    assert "Not in memory." in result.stdout


def test_ids_never_reused(tmp_path):
    run_memory(
        tmp_path, "remember",
        "--text", "first memory",
        "--source", "test",
        "--until", "2026-12-15"
    )

    run_memory(
        tmp_path, "forget",
        "--id", "m-0001",
        "--reason", "test deletion"
    )

    result = run_memory(
        tmp_path, "remember",
        "--text", "second memory",
        "--source", "test",
        "--until", "2026-12-15"
    )

    assert "m-0002" in result.stdout


def test_expired_memory_not_recalled(tmp_path):
    run_memory(
        tmp_path, "remember",
        "--text", "purple elephant",
        "--source", "test",
        "--until", "2026-10-01"
    )

    result = run_memory(
        tmp_path, "recall",
        "--question", "purple elephant",
        "--today", "2026-11-08"
    )

    assert "Not in memory." in result.stdout


def test_supersession(tmp_path):
    run_memory(
        tmp_path, "remember",
        "--text", "Project status is FAIL",
        "--source", "old-report",
        "--until", "2026-12-15"
    )

    run_memory(
        tmp_path, "remember",
        "--text", "Project status is PASS",
        "--source", "new-report",
        "--until", "2026-12-15",
        "--supersedes", "m-0001"
    )

    result = run_memory(
        tmp_path, "recall",
        "--question", "Project status",
        "--today", "2026-11-08"
    )

    assert "Project status is PASS" in result.stdout
    assert "Project status is FAIL" not in result.stdout


def test_top_k_and_threshold(tmp_path):
    for text in [
        "painting canvas colors",
        "painting brushes acrylic",
        "painting studio exhibition"
    ]:
        run_memory(
            tmp_path, "remember",
            "--text", text,
            "--source", "test",
            "--until", "2026-12-15"
        )

    result = run_memory(
        tmp_path, "recall",
        "--question", "painting",
        "--top-k", "2",
        "--threshold", "0.05",
        "--today", "2026-11-08"
    )

    assert result.stdout.count("Memory ID:") == 2

    blocked = run_memory(
        tmp_path, "recall",
        "--question", "painting",
        "--threshold", "1.0",
        "--today", "2026-11-08"
    )

    assert "Not in memory." in blocked.stdout
