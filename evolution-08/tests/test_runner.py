import json

import pytest

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
