import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from contracts import ContractError, parse_handoff, parse_review


def test_valid_done_handoff():
    result = parse_handoff(
        '{"status":"DONE","summary":"Task completed.","evidence":["tests passed"]}'
    )
    assert result.status == "DONE"
    assert result.evidence == ["tests passed"]


def test_valid_blocked_handoff():
    result = parse_handoff(
        '{"status":"BLOCKED","summary":"Required input missing.","evidence":[]}'
    )
    assert result.status == "BLOCKED"


def test_prose_handoff_is_rejected():
    with pytest.raises(ContractError):
        parse_handoff("I finished the task and everything looks good.")


def test_unknown_handoff_status_is_rejected():
    with pytest.raises(ContractError):
        parse_handoff(
            '{"status":"MAYBE","summary":"Unsure.","evidence":["checked"]}'
        )


def test_done_without_evidence_is_rejected():
    with pytest.raises(ContractError):
        parse_handoff(
            '{"status":"DONE","summary":"Task completed.","evidence":[]}'
        )


def test_unknown_handoff_field_is_rejected():
    with pytest.raises(ContractError):
        parse_handoff(
            '{"status":"DONE","summary":"Task completed.",'
            '"evidence":["tests passed"],"extra":"not allowed"}'
        )


def test_valid_pass_review():
    result = parse_review(
        '{"status":"PASS","summary":"Requirements satisfied.","findings":[]}'
    )
    assert result.status == "PASS"


def test_valid_fail_review():
    result = parse_review(
        '{"status":"FAIL","summary":"Defect found.",'
        '"findings":["Expected behavior is missing."]}'
    )
    assert result.status == "FAIL"


def test_prose_review_is_rejected():
    with pytest.raises(ContractError):
        parse_review("Looks good to me. PASS.")


def test_unknown_review_status_is_rejected():
    with pytest.raises(ContractError):
        parse_review(
            '{"status":"APPROVED","summary":"Looks good.","findings":[]}'
        )


def test_fail_without_findings_is_rejected():
    with pytest.raises(ContractError):
        parse_review(
            '{"status":"FAIL","summary":"Something is wrong.","findings":[]}'
        )
