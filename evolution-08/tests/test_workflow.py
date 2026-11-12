import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from contracts import HandoffResult, ReviewResult
from workflow import E8Workflow, WorkflowError, WorkflowState


def done_handoff(task):
    return HandoffResult(
        status="DONE",
        summary="Implementation complete.",
        evidence=["tests passed"],
    )


def pass_review(handoff):
    return ReviewResult(
        status="PASS",
        summary="Implementation satisfies requirements.",
        findings=[],
    )


def fail_review(handoff):
    return ReviewResult(
        status="FAIL",
        summary="Defect found.",
        findings=["Planted defect detected."],
    )


def test_pass_stops_at_human_interrupt_before_merge():
    merges = []

    workflow = E8Workflow(
        implementer=done_handoff,
        reviewer=pass_review,
        merger=lambda: merges.append("merged"),
    )

    state = WorkflowState(task="clean task")
    workflow.run_until_interrupt(state)

    assert state.current_node == "human_approval"
    assert state.awaiting_human is True
    assert state.merge_count == 0
    assert merges == []
    assert state.checkpoints == ["implement", "review"]


def test_human_approval_causes_exactly_one_merge():
    merges = []

    workflow = E8Workflow(
        implementer=done_handoff,
        reviewer=pass_review,
        merger=lambda: merges.append("merged"),
    )

    state = WorkflowState(task="clean task")
    workflow.run_until_interrupt(state)
    workflow.resume_after_approval(state, True)

    assert state.current_node == "complete"
    assert state.merge_count == 1
    assert merges == ["merged"]
    assert state.checkpoints == [
        "implement",
        "review",
        "human_approval",
        "merge",
    ]


def test_human_rejection_prevents_merge():
    merges = []

    workflow = E8Workflow(
        implementer=done_handoff,
        reviewer=pass_review,
        merger=lambda: merges.append("merged"),
    )

    state = WorkflowState(task="clean task")
    workflow.run_until_interrupt(state)
    workflow.resume_after_approval(state, False)

    assert state.current_node == "stopped"
    assert state.merge_count == 0
    assert merges == []


def test_failed_review_routes_back_to_implement():
    workflow = E8Workflow(
        implementer=done_handoff,
        reviewer=fail_review,
        merger=lambda: None,
    )

    state = WorkflowState(task="task with planted defect")

    workflow.implement(state)
    workflow.review(state)

    assert state.review.status == "FAIL"
    assert state.current_node == "implement"
    assert state.merge_count == 0
    assert state.checkpoints == ["implement", "review"]


def test_merge_without_human_approval_is_denied():
    workflow = E8Workflow(
        implementer=done_handoff,
        reviewer=pass_review,
        merger=lambda: None,
    )

    state = WorkflowState(task="clean task")

    with pytest.raises(WorkflowError):
        workflow.merge(state)


def test_second_merge_is_denied():
    workflow = E8Workflow(
        implementer=done_handoff,
        reviewer=pass_review,
        merger=lambda: None,
    )

    state = WorkflowState(task="clean task")
    workflow.run_until_interrupt(state)
    workflow.resume_after_approval(state, True)

    with pytest.raises(WorkflowError):
        workflow.merge(state)


def test_json_checkpoint_written_after_each_completed_node(tmp_path):
    handoff = HandoffResult(
        status="DONE",
        summary="Implementation completed.",
        evidence=["tests passed"],
    )
    review = ReviewResult(
        status="PASS",
        summary="Requirements satisfied.",
        findings=[],
    )

    merges = []

    workflow = E8Workflow(
        implementer=lambda task: handoff,
        reviewer=lambda result: review,
        merger=lambda: merges.append("merged"),
        checkpoint_dir=tmp_path,
    )

    state = WorkflowState(task="bounded checkpoint test")

    workflow.run_until_interrupt(state)

    implement_file = tmp_path / "01-implement.json"
    review_file = tmp_path / "02-review.json"

    assert implement_file.exists()
    assert review_file.exists()
    assert not (tmp_path / "03-merge.json").exists()

    workflow.resume_after_approval(state, approved=True)

    approval_file = tmp_path / "03-human_approval.json"
    merge_file = tmp_path / "04-merge.json"

    assert approval_file.exists()
    assert merge_file.exists()

    import json

    implement_data = json.loads(implement_file.read_text())
    review_data = json.loads(review_file.read_text())
    approval_data = json.loads(approval_file.read_text())
    merge_data = json.loads(merge_file.read_text())

    assert implement_data["checkpoint_node"] == "implement"
    assert review_data["checkpoint_node"] == "review"
    assert approval_data["checkpoint_node"] == "human_approval"
    assert approval_data["human_approved"] is True
    assert merge_data["checkpoint_node"] == "merge"
    assert merge_data["merge_count"] == 1
    assert merges == ["merged"]
