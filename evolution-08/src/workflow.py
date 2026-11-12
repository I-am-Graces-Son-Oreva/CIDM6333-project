import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from contracts import HandoffResult, ReviewResult


@dataclass
class WorkflowState:
    task: str
    handoff: HandoffResult | None = None
    review: ReviewResult | None = None
    current_node: str = "implement"
    checkpoints: list[str] = field(default_factory=list)
    awaiting_human: bool = False
    human_approved: bool = False
    merge_count: int = 0


class WorkflowError(RuntimeError):
    pass


class E8Workflow:
    def __init__(
        self,
        implementer: Callable[[str], HandoffResult],
        reviewer: Callable[[HandoffResult], ReviewResult],
        merger: Callable[[], None],
        checkpoint_dir: str | Path | None = None,
    ):
        self.implementer = implementer
        self.reviewer = reviewer
        self.merger = merger
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else None

        if self.checkpoint_dir:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def checkpoint(self, state: WorkflowState, node: str) -> None:
        state.checkpoints.append(node)

        if not self.checkpoint_dir:
            return

        number = len(state.checkpoints)
        path = self.checkpoint_dir / f"{number:02d}-{node}.json"

        if path.exists():
            raise WorkflowError(f"Refusing to overwrite checkpoint: {path}")

        payload = asdict(state)
        payload["checkpoint_node"] = node

        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def implement(self, state: WorkflowState) -> None:
        state.handoff = self.implementer(state.task)
        self.checkpoint(state, "implement")

        if state.handoff.status != "DONE":
            raise WorkflowError(
                f"Implementer did not return DONE: {state.handoff.status}"
            )

        state.current_node = "review"

    def review(self, state: WorkflowState) -> None:
        if state.handoff is None:
            raise WorkflowError("Review requires an implementation handoff.")

        state.review = self.reviewer(state.handoff)
        self.checkpoint(state, "review")

        if state.review.status == "FAIL":
            state.current_node = "implement"
            return

        if state.review.status == "PASS":
            state.awaiting_human = True
            state.current_node = "human_approval"
            return

        raise WorkflowError(f"Unknown review status: {state.review.status}")

    def approve(self, state: WorkflowState, approved: bool) -> None:
        if not state.awaiting_human:
            raise WorkflowError("Workflow is not waiting for human approval.")

        state.human_approved = approved
        state.awaiting_human = False
        self.checkpoint(state, "human_approval")

        if approved:
            state.current_node = "merge"
        else:
            state.current_node = "stopped"

    def merge(self, state: WorkflowState) -> None:
        if not state.human_approved:
            raise WorkflowError("Merge requires explicit human approval.")

        if state.review is None or state.review.status != "PASS":
            raise WorkflowError("Merge requires reviewer PASS.")

        if state.merge_count != 0:
            raise WorkflowError("Merge may execute exactly once.")

        self.merger()
        state.merge_count += 1
        self.checkpoint(state, "merge")
        state.current_node = "complete"

    def run_until_interrupt(self, state: WorkflowState) -> WorkflowState:
        while state.current_node not in {"human_approval", "stopped", "complete"}:
            if state.current_node == "implement":
                self.implement(state)
            elif state.current_node == "review":
                self.review(state)
            else:
                raise WorkflowError(f"Unknown node: {state.current_node}")

        return state

    def resume_after_approval(
        self,
        state: WorkflowState,
        approved: bool,
    ) -> WorkflowState:
        self.approve(state, approved)

        if state.current_node == "merge":
            self.merge(state)

        return state
