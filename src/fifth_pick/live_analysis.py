"""Receipt-backed LIVE analysis readiness while supporting evidence is unavailable."""

from collections import defaultdict
from datetime import UTC, datetime

from fifth_pick.errors import ValidationError
from fifth_pick.methodology import CandidateCase, evaluate_candidate
from fifth_pick.models import ReasonCode
from fifth_pick.schedule import schedule_view
from fifth_pick.slate_manifest import read_slate_run_context
from fifth_pick.snapshots import MissedSnapshot, SnapshotEvidence, read_receipted_snapshot_ledger
from fifth_pick.sources.base import EvidenceMode
from fifth_pick.storage import RunStore, application_run_store


def live_analysis_view(store: RunStore, run_id: str, *, review: bool) -> dict[str, object]:
    """Validate real board evidence without creating a premature analysis or review."""
    if store.root != application_run_store().root:
        raise ValidationError("LIVE analysis requires the application-owned run store")
    context = read_slate_run_context(store, run_id)
    if not all(board.evidence_mode is EvidenceMode.LIVE for board in context.event_boards):
        raise ValidationError("LIVE analysis requires LIVE board receipts")
    snapshots: dict[str, list[SnapshotEvidence]] = defaultdict(list)
    missed: dict[str, list[MissedSnapshot]] = defaultdict(list)
    for entry in read_receipted_snapshot_ledger(store, run_id):
        if isinstance(entry, SnapshotEvidence):
            if entry.evidence_mode is not EvidenceMode.LIVE:
                raise ValidationError("LIVE analysis cannot use fixture observations")
            snapshots[entry.candidate_key].append(entry)
        else:
            missed[entry.candidate_key].append(entry)
    candidates = []
    for key, rows in snapshots.items():
        audit = evaluate_candidate(
            CandidateCase(tuple(rows), tuple(missed[key]), snapshot_run_id=run_id)
        )
        candidates.append(
            {
                "candidate_key": key,
                "event": audit.candidate.event,
                "status": audit.status.value,
                "reasons": [reason.value for reason in audit.exclusions],
            }
        )
    return {
        "run_id": run_id,
        "mode": "LIVE",
        "status": "BLOCKED",
        "reason": (
            ReasonCode.T20_CHECK_UNAVAILABLE.value
            if review
            else ReasonCode.INSUFFICIENT_SUPPORTING_EVIDENCE.value
        ),
        "detail": (
            "LIVE supporting-evidence ingestion is unavailable. No review or proposal was recorded."
        ),
        "candidates": candidates,
        **({"schedule": schedule_view(store, run_id, as_of=datetime.now(UTC))} if review else {}),
    }
