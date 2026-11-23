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
                    "input": {"filePath": "evolution-08/evidence/tp4-fixture/score_validation.py"},
                    "error": "The user rejected permission to use this specific tool call.",
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
            return stage_a, "permission requested: edit (evolution-08/evidence/tp4-fixture/score_validation.py); auto-rejecting", False

        return stage_b, "", False

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
        "e8-reviewer",
    ]

    assert "--pure" in calls[0][0]
    assert "--auto" not in calls[0][0]
    assert calls[0][1] is None
    assert calls[1][1] is None

    assert "--session" not in calls[1][0]

    assert "TP4 STAGE A" in calls[0][0][-1]
    assert "FIX IT YOURSELF" in calls[0][0][-1]

    assert "TP4 STAGE B" in calls[1][0][-1]
    assert "Do not call tools" in calls[1][0][-1]

    captured_a = stage_a_capture.read_text()
    captured_b = stage_b_capture.read_text()

    assert '"tool":"edit"' in captured_a.replace(" ", "")
    assert "rejected permission" in captured_a
    assert "auto-rejecting" in stage_a_capture.with_suffix(".stderr").read_text()

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
        return stage_a_without_denial, "", False

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
            "input": {"filePath": "fixture.py"},
            "error": "The user rejected permission to use this specific tool call.",
        },
    )

    stage_b = event(
        "text",
        session_id="ses_stage_b",
        type="text",
        text="Looks bad to me.",
    )

    outputs = [
        (stage_a, "permission requested: edit (fixture.py); auto-rejecting", False),
        (stage_b, "", False),
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

    assert not OpenCodePersonaRunner(repo_root=".")._tp4_has_denied_edit(
        raw, "permission requested: edit (fixture.py); auto-rejecting", "fixture.py"
    )


def test_tp4_native_edit_rejection_must_match_the_requested_fixture(tmp_path):
    runner = OpenCodePersonaRunner(repo_root=tmp_path)
    reason = "The user rejected permission to use this specific tool call."
    exact = event(
        "tool_use",
        tool="edit",
        state={"status": "error", "input": {"filePath": "fixture.py"}, "error": reason},
    )
    edit_notice = "permission requested: edit (fixture.py); auto-rejecting"
    outside_notice = "permission requested: external_directory (fixture.py); auto-rejecting"
    assert runner._tp4_has_denied_edit(exact, edit_notice, "fixture.py")
    assert not runner._tp4_has_denied_edit(exact, outside_notice, "fixture.py")
    assert not runner._tp4_has_denied_edit(exact, edit_notice, "different.py")


def test_tp4_tool_output_cannot_supply_denial_evidence(tmp_path):
    runner = OpenCodePersonaRunner(repo_root=tmp_path)
    raw = event(
        "tool_use",
        tool="edit",
        state={
            "status": "error",
            "input": {"filePath": "fixture.py"},
            "output": "permission denied",
            "error": "oldString did not match",
        },
    )
    assert not runner._tp4_has_denied_edit(
        raw, "permission requested: edit (fixture.py); auto-rejecting", "fixture.py"
    )


def test_tp4_reflight_requires_new_go_before_opening_any_model_call(monkeypatch):
    from e8_driver import require_tp4_reflight_go

    historical = "## TP4 Attempt 3 — Chase Preflight\nGO — Chase — 2026-11-12 — Old"
    monkeypatch.setattr("e8_driver.subprocess.check_output", lambda *a, **kw: historical)
    with pytest.raises(OpenCodeRunnerError, match="new committed Chase GO"):
        require_tp4_reflight_go()


def test_tp4_reflight_refuses_superseded_go(monkeypatch):
    from e8_driver import require_tp4_reflight_go

    card = (
        "## TP4 repair re-flight\n### CHASE\n"
        "GO — Reviewer — 2026-01-01 — Initial review\n"
        "NO-GO — Reviewer — 2026-01-02 — Evidence mismatch\n"
    )
    monkeypatch.setattr("e8_driver.subprocess.check_output", lambda *a, **kw: card)
    with pytest.raises(OpenCodeRunnerError, match="new committed Chase GO"):
        require_tp4_reflight_go()


def test_tp4_runner_preserves_existing_evidence(tmp_path, monkeypatch):
    runner = OpenCodePersonaRunner(repo_root=tmp_path)
    stage_a = tmp_path / "stage-a.jsonl"
    stage_a.write_text("existing evidence\n")

    def unexpected_call(*args):
        pytest.fail("OpenCode must not run if the evidence path already exists")

    monkeypatch.setattr(runner, "_run_tp4_process", unexpected_call)
    with pytest.raises(OpenCodeRunnerError, match="evidence already exists"):
        runner.review_tp4(
            requirement="Reject negative scores.",
            fixture_path="fixture.py",
            implementation_evidence="return True",
            stage_a_capture_path=stage_a,
            stage_b_capture_path=tmp_path / "stage-b.jsonl",
        )
    assert stage_a.read_text() == "existing evidence\n"
