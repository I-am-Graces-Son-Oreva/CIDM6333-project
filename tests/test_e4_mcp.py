from pathlib import Path

from src.grad_mcp.server import DATA_DIR, LOG_FILE, read_triage_note, write_triage_note


def test_read_triage_note_returns_existing_note():
    path = DATA_DIR / "pytest-read.txt"
    path.write_text("read test")

    result = read_triage_note("pytest-read", "pytest")

    assert result == "read test"


def test_write_triage_note_writes_note_and_logs_call():
    path = DATA_DIR / "pytest-write.txt"

    if path.exists():
        path.unlink()

    result = write_triage_note(
        "pytest-write",
        "write test",
        "pytest",
    )

    assert result == "Wrote triage note pytest-write."
    assert path.read_text() == "write test"

    log_text = LOG_FILE.read_text()
    assert '"client": "pytest"' in log_text
    assert '"tool": "write_triage_note"' in log_text
