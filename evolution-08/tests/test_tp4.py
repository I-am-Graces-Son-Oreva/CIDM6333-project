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


def test_tp4_two_stage_denial_then_fresh_verdict(
    tmp_path,
    monkeypatch,
):
    runner = OpenCodePersonaRunner(
        repo_root=tmp_path,
        timeout_seconds=5,
    )

    stage_a = "\n".join(
        [
            event("step_start", session_id="ses_stage_a"),
            event(
                "tool_use",
                session_id="ses_stage_a",
                type="tool",
                tool="edit",
                state={
                    "status": "error",
                    "output": "permission denied by reviewer policy",
                },
            ),
        ]
    )

    verdict = json.dumps(
        {
            "status": "FAIL",
            "summary": "Implementation violates the negative-score requirement.",
            "findings": [
                "score_validation.py:3 accepts negative scores."
            ],
        }
    )

    stage_b = "\n".join(
        [
            event("step_start", session_id="ses_stage_b"),
            event(
                "text",
                session_id="ses_stage_b",
                type="text",
                text=verdict,
            ),
        ]
    )

    calls = []

    def fake_run(command, env_overrides=None):
        calls.append((command, env_overrides))

        if len(calls) == 1:
            return stage_a, False

        return stage_b, False

    monkeypatch.setattr(runner, "_run_tp4_process", fake_run)

    stage_a_capture = tmp_path / "stage-a.jsonl"
    stage_b_capture = tmp_path / "stage-b.jsonl"

    result = runner.review_tp4(
        requirement="Negative scores must be rejected.",
        fixture_path="evolution-08/evidence/tp4-fixture/score_validation.py",
        implementation_evidence=(
            "def validate_score(score: int) -> bool:\n"
            "    return True\n"
        ),
        stage_a_capture_path=stage_a_capture,
        stage_b_capture_path=stage_b_capture,
    )

    assert isinstance(result, ReviewResult)
    assert result.status == "FAIL"
    assert len(calls) == 2

    assert calls[0][0][:6] == [
        "opencode",
        "run",
        "--format",
        "json",
        "--agent",
        "e8-reviewer-tp4",
    ]

    assert calls[1][0][:6] == [
        "opencode",
        "run",
        "--format",
        "json",
        "--agent",
        "e8-reviewer-tp4",
    ]

    assert calls[0][1] == {"E8_TP4_GATE": "1"}
    assert calls[1][1] is None

    assert "--session" not in calls[1][0]

    assert "TP4 STAGE A" in calls[0][0][-1]
    assert "FIX IT YOURSELF" in calls[0][0][-1]

    assert "TP4 STAGE B" in calls[1][0][-1]
    assert "Do not call tools" in calls[1][0][-1]

    captured_a = stage_a_capture.read_text()
    captured_b = stage_b_capture.read_text()

    assert '"tool":"edit"' in captured_a.replace(" ", "")
    assert "permission denied" in captured_a

    stage_b_events = [
        json.loads(line)
        for line in captured_b.splitlines()
        if line.strip()
    ]
    stage_b_text = [
        item["part"]["text"]
        for item in stage_b_events
        if item.get("type") == "text"
    ]

    assert verdict in stage_b_text


def test_tp4_stage_a_without_denial_fails_closed(
    tmp_path,
    monkeypatch,
):
    runner = OpenCodePersonaRunner(
        repo_root=tmp_path,
        timeout_seconds=5,
    )

    stage_a_without_denial = event(
        "tool_use",
        session_id="ses_stage_a",
        type="tool",
        tool="read",
        state={
            "status": "completed",
            "output": "fixture contents",
        },
    )

    calls = []

    def fake_run(command, env_overrides=None):
        calls.append(command)
        return stage_a_without_denial, False

    monkeypatch.setattr(runner, "_run_tp4_process", fake_run)

    with pytest.raises(
        OpenCodeRunnerError,
        match="no real denied edit/write event",
    ):
        runner.review_tp4(
            requirement="Negative scores must be rejected.",
            fixture_path="fixture.py",
            implementation_evidence="return True",
            stage_a_capture_path=tmp_path / "stage-a.jsonl",
            stage_b_capture_path=tmp_path / "stage-b.jsonl",
        )

    assert len(calls) == 1
    assert (tmp_path / "stage-a.jsonl").exists()
    assert not (tmp_path / "stage-b.jsonl").exists()


def test_tp4_invalid_stage_b_fails_closed(
    tmp_path,
    monkeypatch,
):
    runner = OpenCodePersonaRunner(
        repo_root=tmp_path,
        timeout_seconds=5,
    )

    stage_a = event(
        "tool_use",
        session_id="ses_stage_a",
        type="tool",
        tool="edit",
        state={
            "status": "error",
            "output": "permission denied",
        },
    )

    stage_b = event(
        "text",
        session_id="ses_stage_b",
        type="text",
        text="Looks bad to me.",
    )

    outputs = [
        (stage_a, False),
        (stage_b, False),
    ]

    monkeypatch.setattr(
        runner,
        "_run_tp4_process",
        lambda command, env_overrides=None: outputs.pop(0),
    )

    with pytest.raises(Exception):
        runner.review_tp4(
            requirement="Negative scores must be rejected.",
            fixture_path="fixture.py",
            implementation_evidence="return True",
            stage_a_capture_path=tmp_path / "stage-a.jsonl",
            stage_b_capture_path=tmp_path / "stage-b.jsonl",
        )

    assert (tmp_path / "stage-a.jsonl").exists()
    assert (tmp_path / "stage-b.jsonl").exists()


def test_tp4_denial_detector_rejects_mock_success_event():
    raw = event(
        "tool_use",
        type="tool",
        tool="edit",
        state={
            "status": "completed",
            "output": "file changed",
        },
    )

    assert not OpenCodePersonaRunner._tp4_has_denied_edit(raw)
