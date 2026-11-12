import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from contracts import ReviewResult
from runner import OpenCodePersonaRunner, OpenCodeRunnerError


def event(event_type, session_id="ses_tp4_test", **part):
    payload = {
        "type": event_type,
        "sessionID": session_id,
    }
    if part:
        payload["part"] = part
    return json.dumps(payload)


def test_tp4_extracts_session_id():
    raw = event("step_start", session_id="ses_abc123")

    assert (
        OpenCodePersonaRunner._extract_tp4_session_id(raw)
        == "ses_abc123"
    )


def test_tp4_same_session_continuation_and_raw_capture(
    tmp_path,
    monkeypatch,
):
    runner = OpenCodePersonaRunner(
        repo_root=tmp_path,
        timeout_seconds=5,
    )

    first = "\n".join(
        [
            event("step_start", session_id="ses_tp4_live"),
            event(
                "tool_use",
                session_id="ses_tp4_live",
                type="tool",
                tool="edit",
                state={
                    "status": "error",
                    "output": "permission denied",
                },
            ),
        ]
    )

    verdict = json.dumps(
        {
            "status": "FAIL",
            "summary": "Implementation violates the requirement.",
            "findings": [
                "score_validation.py:3 accepts negative scores."
            ],
        }
    )

    second = "\n".join(
        [
            event("step_start", session_id="ses_tp4_live"),
            event(
                "text",
                session_id="ses_tp4_live",
                type="text",
                text=verdict,
            ),
        ]
    )

    calls = []

    def fake_run(command):
        calls.append(command)
        if len(calls) == 1:
            return first, True
        return second, False

    monkeypatch.setattr(runner, "_run_tp4_process", fake_run)

    capture = tmp_path / "tp4.jsonl"

    result = runner.review_tp4(
        requirement="Negative scores must be rejected.",
        fixture_path="evolution-08/evidence/tp4-fixture/score_validation.py",
        capture_path=capture,
    )

    assert isinstance(result, ReviewResult)
    assert result.status == "FAIL"
    assert len(calls) == 2

    assert calls[0][:6] == [
        "opencode",
        "run",
        "--format",
        "json",
        "--agent",
        "e8-reviewer-tp4",
    ]

    assert "--session" in calls[1]
    session_index = calls[1].index("--session")
    assert calls[1][session_index + 1] == "ses_tp4_live"

    captured = capture.read_text()
    assert '"tool":"edit"' in captured.replace(" ", "")
    assert "permission denied" in captured
    captured_events = [
        json.loads(line)
        for line in captured.splitlines()
        if line.strip()
    ]
    text_events = [
        item["part"]["text"]
        for item in captured_events
        if item.get("type") == "text"
    ]

    assert verdict in text_events


def test_tp4_no_session_fails_closed(tmp_path, monkeypatch):
    runner = OpenCodePersonaRunner(
        repo_root=tmp_path,
        timeout_seconds=5,
    )

    monkeypatch.setattr(
        runner,
        "_run_tp4_process",
        lambda command: ("", True),
    )

    with pytest.raises(
        OpenCodeRunnerError,
        match="produced no session ID",
    ):
        runner.review_tp4(
            requirement="Negative scores must be rejected.",
            fixture_path="fixture.py",
            capture_path=tmp_path / "capture.jsonl",
        )
