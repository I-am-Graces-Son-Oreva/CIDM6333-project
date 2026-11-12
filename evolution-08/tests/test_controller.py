import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from controller import ControllerError, E8Controller


def valid_handoff():
    return (
        '{"status":"DONE",'
        '"summary":"Implementation completed.",'
        '"evidence":["tests passed"]}'
    )


def valid_review():
    return (
        '{"status":"PASS",'
        '"summary":"Requirements satisfied.",'
        '"findings":[]}'
    )


def test_valid_results_reach_human_interrupt(tmp_path):
    reviews = []
    merges = []

    controller = E8Controller(
        implementer_call=lambda task: valid_handoff(),
        reviewer_call=lambda handoff: (
            reviews.append(handoff) or valid_review()
        ),
        merger=lambda: merges.append("merged"),
        checkpoint_dir=tmp_path,
    )

    state = controller.start("clean task")

    assert state.current_node == "human_approval"
    assert state.awaiting_human is True
    assert len(reviews) == 1
    assert merges == []


@pytest.mark.parametrize(
    "bad_output",
    [
        "DONE. Everything worked.",
        '{"status":"MAYBE","summary":"done","evidence":["x"]}',
        '{"status":"DONE","summary":"done","evidence":[]}',
    ],
)
def test_bad_handoff_rejected_before_reviewer_or_merge(
    tmp_path,
    bad_output,
):
    reviews = []
    merges = []

    controller = E8Controller(
        implementer_call=lambda task: bad_output,
        reviewer_call=lambda handoff: (
            reviews.append(handoff) or valid_review()
        ),
        merger=lambda: merges.append("merged"),
        checkpoint_dir=tmp_path,
    )

    with pytest.raises(ControllerError):
        controller.start("malformed handoff test")

    assert reviews == []
    assert merges == []


def test_bad_review_rejected_before_human_or_merge(tmp_path):
    merges = []

    controller = E8Controller(
        implementer_call=lambda task: valid_handoff(),
        reviewer_call=lambda handoff: "PASS. Looks good.",
        merger=lambda: merges.append("merged"),
        checkpoint_dir=tmp_path,
    )

    with pytest.raises(ControllerError):
        controller.start("malformed review test")

    assert merges == []


def test_approval_after_valid_results_merges_exactly_once(tmp_path):
    merges = []

    controller = E8Controller(
        implementer_call=lambda task: valid_handoff(),
        reviewer_call=lambda handoff: valid_review(),
        merger=lambda: merges.append("merged"),
        checkpoint_dir=tmp_path,
    )

    state = controller.start("clean task")

    assert merges == []

    controller.resume(state, approved=True)

    assert merges == ["merged"]
    assert state.merge_count == 1
    assert state.current_node == "complete"
