from collections.abc import Callable
from pathlib import Path

from contracts import (
    ContractError,
    HandoffResult,
    ReviewResult,
    parse_handoff,
    parse_review,
)
from workflow import E8Workflow, WorkflowState


class ControllerError(RuntimeError):
    pass


class E8Controller:
    def __init__(
        self,
        implementer_call: Callable[[str], str],
        reviewer_call: Callable[[HandoffResult], str],
        merger: Callable[[], None],
        checkpoint_dir: str | Path | None = None,
    ):
        self.implementer_call = implementer_call
        self.reviewer_call = reviewer_call

        self.workflow = E8Workflow(
            implementer=self._call_implementer,
            reviewer=self._call_reviewer,
            merger=merger,
            checkpoint_dir=checkpoint_dir,
        )

    def _call_implementer(self, task: str) -> HandoffResult:
        raw = self.implementer_call(task)

        try:
            return parse_handoff(raw)
        except ContractError as exc:
            raise ControllerError(
                f"Implementer result rejected: {exc}"
            ) from exc

    def _call_reviewer(self, handoff: HandoffResult) -> ReviewResult:
        raw = self.reviewer_call(handoff)

        try:
            return parse_review(raw)
        except ContractError as exc:
            raise ControllerError(
                f"Reviewer result rejected: {exc}"
            ) from exc

    def start(self, task: str) -> WorkflowState:
        state = WorkflowState(task=task)
        return self.workflow.run_until_interrupt(
            state,
            stop_on_review_fail=True,
        )

    def resume(
        self,
        state: WorkflowState,
        approved: bool,
    ) -> WorkflowState:
        return self.workflow.resume_after_approval(
            state,
            approved=approved,
        )
