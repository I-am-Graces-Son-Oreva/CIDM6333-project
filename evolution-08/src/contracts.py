from dataclasses import dataclass
import json


class ContractError(ValueError):
    """Raised when an agent result does not satisfy the E8 contract."""


@dataclass(frozen=True)
class HandoffResult:
    status: str
    summary: str
    evidence: list[str]


@dataclass(frozen=True)
class ReviewResult:
    status: str
    summary: str
    findings: list[str]


def _parse_json_object(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ContractError("Result must be valid JSON.") from exc

    if not isinstance(data, dict):
        raise ContractError("Result must be a JSON object.")

    return data


def parse_handoff(raw: str) -> HandoffResult:
    data = _parse_json_object(raw)

    required = {"status", "summary", "evidence"}
    if set(data) != required:
        raise ContractError("HandoffResult contains missing or unknown fields.")

    if data["status"] not in {"DONE", "BLOCKED"}:
        raise ContractError("Unknown HandoffResult status.")

    if not isinstance(data["summary"], str) or not data["summary"].strip():
        raise ContractError("HandoffResult summary must be non-empty.")

    if not isinstance(data["evidence"], list) or not all(
        isinstance(item, str) and item.strip() for item in data["evidence"]
    ):
        raise ContractError("HandoffResult evidence must be a list of non-empty strings.")

    if data["status"] == "DONE" and not data["evidence"]:
        raise ContractError("DONE requires evidence.")

    return HandoffResult(
        status=data["status"],
        summary=data["summary"],
        evidence=data["evidence"],
    )


def parse_review(raw: str) -> ReviewResult:
    data = _parse_json_object(raw)

    required = {"status", "summary", "findings"}
    if set(data) != required:
        raise ContractError("ReviewResult contains missing or unknown fields.")

    if data["status"] not in {"PASS", "FAIL"}:
        raise ContractError("Unknown ReviewResult status.")

    if not isinstance(data["summary"], str) or not data["summary"].strip():
        raise ContractError("ReviewResult summary must be non-empty.")

    if not isinstance(data["findings"], list) or not all(
        isinstance(item, str) and item.strip() for item in data["findings"]
    ):
        raise ContractError("ReviewResult findings must be a list of non-empty strings.")

    if data["status"] == "FAIL" and not data["findings"]:
        raise ContractError("FAIL requires at least one finding.")

    return ReviewResult(
        status=data["status"],
        summary=data["summary"],
        findings=data["findings"],
    )
