"""Offline supporting-source decoding and provenance helpers."""

import hashlib
import json
from datetime import datetime, timedelta

from fifth_pick.evidence import (
    EvidenceEffect,
    EvidenceItem,
    EvidenceKind,
    EvidenceSignificance,
    PerformanceSample,
)
from fifth_pick.models import Evidence, Provenance
from fifth_pick.sources.base import EvidenceMode, MalformedPayloadError
from fifth_pick.sources.fixtures import FIXTURE_LABEL


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MalformedPayloadError("duplicate supporting fixture field")
        result[key] = value
    return result


def decode_payload(body: bytes) -> object:
    try:
        return json.loads(body, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, ValueError) as exc:
        raise MalformedPayloadError("invalid supporting fixture JSON") from exc


def aware_timestamp(value: object) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            pass
        else:
            if parsed.utcoffset() is not None:
                return parsed
    raise MalformedPayloadError("supporting evidence requires a timezone-aware timestamp")


def require_fresh(updated_at: datetime, retrieved_at: datetime, max_age: timedelta) -> None:
    if (
        not isinstance(retrieved_at, datetime)
        or retrieved_at.utcoffset() is None
        or not isinstance(max_age, timedelta)
        or max_age <= timedelta()
        or not timedelta() <= retrieved_at - updated_at <= max_age
    ):
        raise MalformedPayloadError("supporting evidence timestamp is stale or invalid")


def payload_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def fixture_evidence(
    candidate_key: str,
    *,
    kind: EvidenceKind,
    provenance: Provenance,
    excerpt: str,
    facts: dict[str, str | int | float | bool] | None = None,
    samples: tuple[PerformanceSample, ...] = (),
) -> EvidenceItem:
    """Construct neutral fixture facts; M6 supplies methodology judgment."""
    return EvidenceItem(
        evidence_id=f"{provenance.reference}-{kind.value}",
        candidate_key=candidate_key,
        kind=kind,
        evidence=Evidence(claim=excerpt, provenance=provenance, excerpt=excerpt),
        evidence_mode=EvidenceMode.FIXTURE,
        effect=EvidenceEffect.NEUTRAL,
        significance=EvidenceSignificance.MINOR,
        facts=facts,
        samples=samples,
    )


def fixture_provenance(
    fixture: str, retrieved_at: datetime, updated_at: datetime, digest: str
) -> Provenance:
    return Provenance(
        source=FIXTURE_LABEL,
        retrieved_at=retrieved_at,
        source_timestamp=updated_at,
        access_method=FIXTURE_LABEL,
        reference=f"fixture:{fixture}/{digest}",
        payload_hash=digest,
    )
