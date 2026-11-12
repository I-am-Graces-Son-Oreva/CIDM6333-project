import json

import pytest

from contracts import HandoffResult

from runner import OpenCodeRunnerError, extract_text_events


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
            "--command",
        ]
        assert command[5] == "e8-review"

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
