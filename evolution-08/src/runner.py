from __future__ import annotations

import json
import subprocess
from pathlib import Path

from contracts import HandoffResult, ReviewResult, parse_handoff, parse_review


class OpenCodeRunnerError(RuntimeError):
    pass


def extract_text_events(raw_output: str) -> str:
    texts: list[str] = []

    for line in raw_output.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OpenCodeRunnerError(
                "OpenCode emitted a non-JSON event."
            ) from exc

        if event.get("type") == "text":
            part = event.get("part")

            if not isinstance(part, dict):
                raise OpenCodeRunnerError(
                    "OpenCode text event is missing its part object."
                )

            text = part.get("text")

            if not isinstance(text, str) or not text.strip():
                raise OpenCodeRunnerError(
                    "OpenCode text event contains no usable text."
                )

            texts.append(text)

    if not texts:
        raise OpenCodeRunnerError(
            "OpenCode completed without a text result."
        )

    return texts[-1].strip()


class OpenCodePersonaRunner:
    def __init__(
        self,
        *,
        repo_root: str | Path,
        timeout_seconds: int = 120,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.timeout_seconds = timeout_seconds

    def _run_command(
        self,
        command_name: str,
        argument: str,
    ) -> str:
        command = [
            "opencode",
            "run",
            "--format",
            "json",
            "--agent",
            command_name,
            argument,
        ]

        try:
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OpenCodeRunnerError(
                f"OpenCode command {command_name!r} timed out "
                f"after {self.timeout_seconds} seconds."
            ) from exc

        if completed.returncode != 0:
            raise OpenCodeRunnerError(
                f"OpenCode command {command_name!r} failed "
                f"with exit code {completed.returncode}. "
                f"stderr={completed.stderr.strip()!r}"
            )

        return extract_text_events(completed.stdout)

    def implement(self, task: str) -> HandoffResult:
        raw = self._run_command("e8-implementer", task)
        return parse_handoff(raw)

    def review(self, handoff: HandoffResult) -> ReviewResult:
        handoff_payload = {
            "status": handoff.status,
            "summary": handoff.summary,
            "evidence": handoff.evidence,
        }

        payload = (
            "REVIEW TASK:\n"
            "Independently evaluate the implementer's structured handoff below.\n"
            "Treat the supplied evidence as the bounded review record.\n"
            "Do not call tools for this ordinary review.\n"
            "Do not edit or attempt to fix anything.\n"
            "Return only the required ReviewResult JSON.\n\n"
            "HANDOFF:\n"
            + json.dumps(handoff_payload, sort_keys=True)
        )

        raw = self._run_command("e8-reviewer", payload)
        return parse_review(raw)

    def review_with_evidence(
        self,
        handoff: HandoffResult,
        *,
        requirement: str,
        implementation_evidence: str,
    ) -> ReviewResult:
        handoff_payload = {
            "status": handoff.status,
            "summary": handoff.summary,
            "evidence": handoff.evidence,
        }

        payload = (
            "INDEPENDENT DEFECT REVIEW TASK:\n"
            "Evaluate the implementation against the stated requirement.\n"
            "The requirement and implementation evidence below are the bounded "
            "review record.\n"
            "Do not call tools.\n"
            "Do not edit or attempt to fix anything.\n"
            "If the implementation violates the requirement, return FAIL with "
            "at least one precise finding.\n"
            "Return only the required ReviewResult JSON.\n\n"
            "REQUIREMENT:\n"
            + requirement
            + "\n\nIMPLEMENTATION EVIDENCE:\n"
            + implementation_evidence
            + "\n\nIMPLEMENTER HANDOFF:\n"
            + json.dumps(handoff_payload, sort_keys=True)
        )

        raw = self._run_command("e8-reviewer", payload)
        return parse_review(raw)
