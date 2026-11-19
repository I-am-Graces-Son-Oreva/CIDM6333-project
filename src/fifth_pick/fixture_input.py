"""Decode an explicitly selected offline stage into the existing M4 and M6 inputs."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fifth_pick.evidence import (
    EvidenceEffect,
    EvidenceItem,
    EvidenceKind,
    EvidenceSignificance,
    PerformanceSample,
)
from fifth_pick.methodology import Confidence, MethodologyDisposition, MethodologyJudgment
from fifth_pick.models import Evidence, Provenance
from fifth_pick.receipts import redact_text
from fifth_pick.sources.base import EvidenceMode, SourceBoard
from fifth_pick.sources.fixtures import FIXTURE_LABEL, load_board_fixture
from fifth_pick.sources.odds_api import API_KEY_ENV_VAR, OddsApiClient
from fifth_pick.sources.quota import QuotaBudget


class FixtureError(ValueError):
    """The operator-selected fixture or its persisted workflow is inconsistent."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise FixtureError(f"duplicate fixture JSON field {key!r}")
        obj[key] = value
    return obj


def _reject_constant(value: str) -> None:
    raise FixtureError(f"invalid fixture JSON number {value}")


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_bytes(), object_pairs_hook=_unique_object, parse_constant=_reject_constant
    )
    if not isinstance(value, dict):
        raise FixtureError(f"{path.name} must contain a JSON object")
    return value


def encode(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value: object) -> str:
    return hashlib.sha256(encode(value)).hexdigest()


def fixture_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise FixtureError("fixture timestamp must be an ISO-8601 string")
    timestamp = datetime.fromisoformat(value)
    if timestamp.utcoffset() is None:
        raise FixtureError("fixture timestamp must be timezone-aware")
    return timestamp.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class FixtureInput:
    observed_at: datetime
    aliases: dict[str, list[str]]
    evidence: dict[str, Any]
    board: SourceBoard


def load_fixture(directory: Path) -> FixtureInput:
    directory = directory.resolve()
    descriptor = (directory / "stage.json").resolve()
    if not descriptor.is_relative_to(directory):
        raise FixtureError("stage.json escapes the selected fixture directory")
    data = read_object(descriptor)
    if set(data) != {"mode", "observed_at", "aliases", "evidence"} or data["mode"] != "fixture":
        raise FixtureError("stage.json requires explicit fixture mode, time, aliases and evidence")
    observed_at = fixture_time(data["observed_at"])
    aliases = data["aliases"]
    evidence = data["evidence"]
    if not isinstance(aliases, dict) or any(
        not isinstance(ids, list) or any(not isinstance(item, str) for item in ids)
        for ids in aliases.values()
    ):
        raise FixtureError("fixture aliases must map provider labels to lists of canonical IDs")
    if not isinstance(evidence, dict) or any(
        re.fullmatch("[0-9a-f]{64}", key) is None for key in evidence
    ):
        raise FixtureError("fixture evidence must be keyed by an exact candidate key")
    # This transport has no network implementation and no real credentials.
    board = OddsApiClient(
        transport=load_board_fixture(directory),
        environ={API_KEY_ENV_VAR: FIXTURE_LABEL},
        clock=lambda: observed_at,
    ).fetch_board(live_authorized=True, budget=QuotaBudget(495))
    return FixtureInput(observed_at, aliases, evidence, board)


def _evidence_item(key: str, item: dict[str, Any], observed_at: datetime) -> EvidenceItem:
    if (
        not isinstance(item, dict)
        or not {
            "evidence_id",
            "kind",
            "effect",
            "significance",
            "claim",
            "excerpt",
        }
        <= item.keys()
        or item.keys()
        - {
            "evidence_id",
            "kind",
            "effect",
            "significance",
            "claim",
            "excerpt",
            "samples",
            "facts",
        }
    ):
        raise FixtureError("fixture evidence item has unexpected or missing fields")
    evidence_id = item["evidence_id"]
    claim = redact_text(item["claim"])
    excerpt = redact_text(item["excerpt"])
    samples = tuple(
        PerformanceSample(
            fixture_time(sample["played_at"]), sample["value"], sample["opponent"], sample["season"]
        )
        for sample in item.get("samples", ())
    )
    if any(sample.played_at >= observed_at for sample in samples):
        raise FixtureError("fixture history contains a game at or after its observation time")
    return EvidenceItem(
        evidence_id=evidence_id,
        candidate_key=key,
        kind=EvidenceKind(item["kind"]),
        effect=EvidenceEffect(item["effect"]),
        significance=EvidenceSignificance(item["significance"]),
        evidence_mode=EvidenceMode.FIXTURE,
        samples=samples,
        facts=item.get("facts"),
        evidence=Evidence(
            claim,
            Provenance(
                FIXTURE_LABEL,
                observed_at,
                observed_at,
                FIXTURE_LABEL,
                f"fixture:evidence/{key}/{evidence_id}",
                digest(item),
            ),
            excerpt,
        ),
    )


def decode_assessment(
    key: str, value: object, observed_at: datetime
) -> tuple[tuple[EvidenceItem, ...], MethodologyJudgment | None]:
    if value is None:
        return (), None
    if not isinstance(value, dict) or set(value) != {"items", "judgment"}:
        raise FixtureError("fixture assessment requires items and an explicit judgment or null")
    try:
        rows = value["items"]
        if not isinstance(rows, list):
            raise FixtureError("fixture supporting evidence must be an array")
        items = tuple(_evidence_item(key, item, observed_at) for item in rows)
        fields = value["judgment"]
        if fields is None:
            return items, None
        if not isinstance(fields, dict):
            raise FixtureError("fixture judgment must be an object or null")
        judgment = dict(fields)
        judgment["disposition"] = MethodologyDisposition(judgment["disposition"])
        judgment["confidence"] = Confidence(judgment["confidence"])
        for field in ("supporting_evidence_ids", "meaningful_risk_ids", "senior_lower_support_ids"):
            if field in judgment:
                if not isinstance(judgment[field], list):
                    raise FixtureError(f"{field} must be an array")
                judgment[field] = tuple(judgment[field])
        return items, MethodologyJudgment(**judgment)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise FixtureError(f"invalid fixture assessment for {key}: {exc}") from exc
