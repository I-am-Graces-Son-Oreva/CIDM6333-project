from pathlib import Path

from contracts import HandoffResult, ReviewResult
from e8_driver import resume_task, start_task


class FakePersonaRunner:
    def __init__(self, review_status="PASS"):
        self.review_status = review_status
        self.implement_calls = 0
        self.review_calls = 0

    def implement(self, task):
        self.implement_calls += 1
        return HandoffResult(
            status="DONE",
            summary="Implementation completed.",
            evidence=["bounded implementation evidence"],
        )

    def review(self, handoff):
        self.review_calls += 1

        if self.review_status == "FAIL":
            return ReviewResult(
                status="FAIL",
                summary="Reviewer found defect.",
                findings=["Planted defect remains."],
            )

        return ReviewResult(
            status="PASS",
            summary="Independent review passed.",
            findings=[],
        )


def test_driver_composes_parsed_runner_to_human_interrupt(tmp_path):
    runner = FakePersonaRunner(review_status="PASS")
    merges = []

    state = start_task(
        "clean task",
        checkpoint_dir=tmp_path,
        persona_runner=runner,
        merger=lambda: merges.append("merged"),
    )

    assert runner.implement_calls == 1
    assert runner.review_calls == 1
    assert state.current_node == "human_approval"
    assert state.awaiting_human is True
    assert state.merge_count == 0
    assert merges == []


def test_driver_stops_after_reviewer_fail_without_loop(tmp_path):
    runner = FakePersonaRunner(review_status="FAIL")
    merges = []

    state = start_task(
        "planted defect task",
        checkpoint_dir=tmp_path,
        persona_runner=runner,
        merger=lambda: merges.append("merged"),
    )

    assert runner.implement_calls == 1
    assert runner.review_calls == 1
    assert state.review.status == "FAIL"
    assert state.current_node == "implement"
    assert state.awaiting_human is False
    assert state.merge_count == 0
    assert merges == []


def test_driver_reloads_checkpoint_and_merges_once(tmp_path):
    runner = FakePersonaRunner(review_status="PASS")
    first_merges = []

    state = start_task(
        "resume task",
        checkpoint_dir=tmp_path,
        persona_runner=runner,
        merger=lambda: first_merges.append("merged"),
    )

    assert state.current_node == "human_approval"
    assert first_merges == []

    checkpoint = tmp_path / "02-review.json"
    assert checkpoint.exists()

    resumed_merges = []

    resumed = resume_task(
        checkpoint,
        approved=True,
        checkpoint_dir=tmp_path,
        persona_runner=runner,
        merger=lambda: resumed_merges.append("merged"),
    )

    assert resumed.current_node == "complete"
    assert resumed.merge_count == 1
    assert resumed_merges == ["merged"]
