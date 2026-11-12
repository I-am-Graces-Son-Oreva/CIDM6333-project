import subprocess
import json

import pytest

from contracts import HandoffResult

from runner import OpenCodePersonaRunner, OpenCodeRunnerError, extract_text_events


def event_stream(text: str) -> str:
    events = [
        {"type": "step_start", "part": {"type": "step-start"}},
        {
            "type": "text",
            "part": {
                "type": "text",
                "text": text,
            },
        },
        {"type": "step_finish", "part": {"type": "step-finish"}},
    ]
    return "\n".join(json.dumps(event) for event in events)


def test_extract_text_event():
    raw = event_stream(
        '{"status":"PASS","summary":"review passed","findings":[]}'
    )

    result = extract_text_events(raw)

    assert result == (
        '{"status":"PASS","summary":"review passed","findings":[]}'
    )


def test_extract_rejects_no_text_event():
    raw = "\n".join(
        [
            json.dumps(
                {"type": "step_start", "part": {"type": "step-start"}}
            ),
            json.dumps(
                {"type": "step_finish", "part": {"type": "step-finish"}}
            ),
        ]
    )

    with pytest.raises(OpenCodeRunnerError):
        extract_text_events(raw)


def test_extract_rejects_non_json_output():
    with pytest.raises(OpenCodeRunnerError):
        extract_text_events("this is not a JSON event")


def test_extract_rejects_empty_text():
    raw = json.dumps(
        {
            "type": "text",
            "part": {
                "type": "text",
                "text": "",
            },
        }
    )

    with pytest.raises(OpenCodeRunnerError):
        extract_text_events(raw)


def test_persona_runner_run_command_and_review_parsing(monkeypatch, tmp_path):
    import subprocess

    from runner import OpenCodePersonaRunner

    review_json = (
        '{"status":"PASS","summary":"independent review passed",'
        '"findings":[]}'
    )

    stdout = event_stream(review_json)

    def fake_run(command, **kwargs):
        assert command[:5] == [
            "opencode",
            "run",
            "--format",
            "json",
            "--agent",
        ]
        assert command[5] == "e8-reviewer"

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=stdout,
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = OpenCodePersonaRunner(
        repo_root=tmp_path,
        timeout_seconds=5,
    )

    handoff = HandoffResult(
        status="DONE",
        summary="implementation complete",
        evidence=["tests passed"],
    )

    result = runner.review(handoff)

    assert result.status == "PASS"
    assert result.summary == "independent review passed"
    assert result.findings == []


def test_extract_text_events_uses_final_text_result():
    raw = "\n".join(
        [
            '{"type":"text","part":{"text":"I will inspect the file."}}',
            '{"type":"tool_use","part":{"type":"tool","tool":"read"}}',
            '{"type":"text","part":{"text":"{\\"status\\":\\"DONE\\",\\"summary\\":\\"complete\\",\\"evidence\\":[\\"file checked\\"]}"}}',
        ]
    )

    result = extract_text_events(raw)

    assert result == '{"status":"DONE","summary":"complete","evidence":["file checked"]}'


def test_review_sends_bounded_handoff_without_tool_request(monkeypatch, tmp_path):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=(
                '{"type":"text","part":{"text":'
                '"{\\"status\\":\\"PASS\\",'
                '\\"summary\\":\\"Evidence supports the handoff.\\",'
                '\\"findings\\":[]}"}}\n'
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = OpenCodePersonaRunner(
        repo_root=tmp_path,
        timeout_seconds=5,
    )

    handoff = HandoffResult(
        status="DONE",
        summary="Implementation complete.",
        evidence=["file:line evidence", "test passed"],
    )

    result = runner.review(handoff)

    prompt = captured["command"][-1]

    assert captured["command"][5] == "e8-reviewer"
    assert "Do not call tools for this ordinary review." in prompt
    assert "file:line evidence" in prompt
    assert "test passed" in prompt
    assert result.status == "PASS"



def test_review_with_evidence_supplies_requirement_and_implementation(
    monkeypatch,
    tmp_path,
):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=(
                '{"type":"text","part":{"text":'
                '"{\\"status\\":\\"FAIL\\",'
                '\\"summary\\":\\"Negative scores are incorrectly accepted.\\",'
                '\\"findings\\":[\\"score_validation.py:3 returns True '
                'for negative scores, violating the requirement.\\"]}"}}\n'
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = OpenCodePersonaRunner(
        repo_root=tmp_path,
        timeout_seconds=5,
    )

    handoff = HandoffResult(
        status="DONE",
        summary="Score validation implementation supplied.",
        evidence=["score_validation.py:1-3"],
    )

    result = runner.review_with_evidence(
        handoff,
        requirement=(
            "Negative applicant scores must be rejected."
        ),
        implementation_evidence=(
            "score_validation.py:1-3\n"
            "def validate_score(score: int) -> bool:\n"
            '    """Return True when an applicant score is accepted."""\n'
            "    return True"
        ),
    )

    prompt = captured["command"][-1]

    assert captured["command"][5] == "e8-reviewer"
    assert "Negative applicant scores must be rejected." in prompt
    assert "return True" in prompt
    assert "Do not call tools." in prompt
    assert result.status == "FAIL"
    assert result.findings
