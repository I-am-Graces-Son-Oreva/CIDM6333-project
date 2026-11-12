from pathlib import Path

from contracts import HandoffResult, ReviewResult
from e8_driver import resume_task, start_task, start_tp2


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



class FakeTP2PersonaRunner:
    def __init__(self):
        self.implement_calls = 0
        self.review_with_evidence_calls = 0
        self.requirement = None
        self.implementation_evidence = None

    def implement(self, task):
        self.implement_calls += 1
        return HandoffResult(
            status="DONE",
            summary="Planted implementation reported without repair.",
            evidence=["score_validation.py:1-3"],
        )

    def review_with_evidence(
        self,
        handoff,
        *,
        requirement,
        implementation_evidence,
    ):
        self.review_with_evidence_calls += 1
        self.requirement = requirement
        self.implementation_evidence = implementation_evidence

        return ReviewResult(
            status="FAIL",
            summary="Negative scores are incorrectly accepted.",
            findings=[
                "score_validation.py:3 returns True for negative scores."
            ],
        )


def test_tp2_driver_routes_real_fixture_review_fail_back_to_implement(
    tmp_path,
):
    runner = FakeTP2PersonaRunner()
    merges = []

    state = start_tp2(
        checkpoint_dir=tmp_path,
        persona_runner=runner,
        merger=lambda: merges.append("merged"),
    )

    assert runner.implement_calls == 1
    assert runner.review_with_evidence_calls == 1
    assert "negative applicant scores" in runner.requirement.lower()
    assert "return True" in runner.implementation_evidence
    assert state.review.status == "FAIL"
    assert state.current_node == "implement"
    assert state.awaiting_human is False
    assert state.human_approved is False
    assert state.merge_count == 0
    assert state.checkpoints == ["implement", "review"]
    assert merges == []
