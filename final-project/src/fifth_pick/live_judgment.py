"""Bind explicit Controller-supplied assessments to the exact LIVE source state."""

import json
from dataclasses import asdict
from datetime import datetime, timedelta

from fifth_pick.errors import ValidationError
from fifth_pick.evidence import EvidenceItem
from fifth_pick.methodology import Confidence, MethodologyDisposition, MethodologyJudgment
from fifth_pick.receipts import Receipt
from fifth_pick.snapshots import SnapshotEvidence
from fifth_pick.sources.base import EvidenceMode
from fifth_pick.sources.supporting_fixture import aware_timestamp, payload_hash
from fifth_pick.storage import RunStore, collection_lock


def live_judgment_time(store: RunStore, run_id: str, snapshot: SnapshotEvidence) -> datetime | None:
    """Locate the recorded assessment clock; the replay still checks the full receipt."""
    key = f"live-judgment-{snapshot.snapshot.number}-{snapshot.candidate_key}"
    rows = [row for row in store.read_receipts(run_id) if row["event_key"] == key]
    if len(rows) > 1:
        raise ValidationError("LIVE methodology assessment receipt is ambiguous")
    return aware_timestamp(rows[0]["timestamp"]) if rows else None


def _scope(
    snapshot: SnapshotEvidence, evidence: tuple[EvidenceItem, ...], at: datetime
) -> tuple[str, str] | None:
    slot = snapshot.snapshot.number
    if (
        slot not in (2, 3)
        or snapshot.evidence_mode is not EvidenceMode.LIVE
        or snapshot.late
        or at.utcoffset() is None
        or at < snapshot.snapshot.observation.retrieved_at
    ):
        return None
    target = snapshot.event_start - timedelta(minutes=20)
    if (slot == 2 and at >= target) or (
        slot == 3 and not target <= at <= target + timedelta(minutes=5)
    ):
        return None
    if not evidence or any(
        item.evidence_mode is not EvidenceMode.LIVE
        or item.candidate_key != snapshot.candidate_key
        or item.evidence.provenance.retrieved_at > at
        for item in evidence
    ):
        return None
    scope = {
        "slot": slot,
        "event": snapshot.event_id,
        "snapshot": snapshot.to_dict(),
        "evidence": [item.to_dict() for item in sorted(evidence, key=lambda row: row.evidence_id)],
    }
    digest = payload_hash(json.dumps(scope, sort_keys=True, separators=(",", ":")).encode())
    return f"live-judgment-{slot}-{snapshot.candidate_key}", digest


def record_live_judgment(
    store: RunStore,
    run_id: str,
    snapshot: SnapshotEvidence,
    evidence: tuple[EvidenceItem, ...],
    judgment: MethodologyJudgment,
    *,
    observed_at: datetime,
    controller_confirmed: bool = False,
) -> None:
    """Record an explicit assessment input. M6 alone decides qualification."""
    if controller_confirmed is not True:
        raise ValidationError("LIVE methodology assessment requires Controller confirmation")
    scope = _scope(snapshot, evidence, observed_at)
    if scope is None:
        raise ValidationError("LIVE methodology assessment does not match its stage or evidence")
    key, digest = scope
    receipt = Receipt(
        observed_at.isoformat(),
        "LIVE_METHODOLOGY_JUDGMENT",
        "RECORDED",
        snapshot.candidate_key,
        "fifth-pick-controller",
        json.dumps({"scope_sha256": digest, "judgment": asdict(judgment)}, sort_keys=True),
        run_id,
        key,
    )
    with collection_lock(store, run_id):
        store.append_receipt(receipt)


def read_live_judgment(
    store: RunStore,
    run_id: str,
    snapshot: SnapshotEvidence,
    evidence: tuple[EvidenceItem, ...],
    *,
    as_of: datetime,
) -> MethodologyJudgment | None:
    """Reproduce an explicit judgment only for the receipt's original source-state digest."""
    key = f"live-judgment-{snapshot.snapshot.number}-{snapshot.candidate_key}"
    rows = [row for row in store.read_receipts(run_id) if row["event_key"] == key]
    if not rows:
        return None
    if len(rows) != 1:
        raise ValidationError("LIVE methodology assessment receipt is ambiguous")
    row = rows[0]
    observed_at = aware_timestamp(row["timestamp"])
    scope = _scope(snapshot, evidence, observed_at)
    if scope is None or as_of.utcoffset() is None or observed_at > as_of:
        raise ValidationError("LIVE methodology assessment is from another phase or time")
    try:
        reason = json.loads(row["reason"] or "")
        if (
            row
            != Receipt(
                observed_at.isoformat(),
                "LIVE_METHODOLOGY_JUDGMENT",
                "RECORDED",
                snapshot.candidate_key,
                "fifth-pick-controller",
                json.dumps(reason, sort_keys=True),
                run_id,
                scope[0],
            ).to_dict()
            or reason["scope_sha256"] != scope[1]
        ):
            raise ValueError
        fields = dict(reason["judgment"])
        fields["disposition"] = MethodologyDisposition(fields["disposition"])
        fields["confidence"] = Confidence(fields["confidence"])
        for attr in ("supporting_evidence_ids", "meaningful_risk_ids", "senior_lower_support_ids"):
            values = fields[attr]
            if not isinstance(values, list):
                raise ValueError
            fields[attr] = tuple(values)
        return MethodologyJudgment(**fields)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(
            "LIVE methodology assessment does not match the source state"
        ) from exc
