"""Read-only readiness for each event and candidate under existing M5/M7 timing."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fifth_pick.errors import ValidationError
from fifth_pick.slate_manifest import SLATE_TIMEZONE, read_slate_run_context
from fifth_pick.snapshots import (
    SNAPSHOT_2_MINIMUM_SEPARATION,
    SNAPSHOT_2_T20_GAP,
    SNAPSHOT_3_EARLY_WINDOW,
    T20_OFFSET,
    MissedSnapshot,
    SnapshotEvidence,
    read_receipted_snapshot_ledger,
    shared_slate_start,
    snapshot_2_target,
)
from fifth_pick.storage import RunStore
from fifth_pick.t20_review import LIVE_T20_REVIEW_GRACE


def schedule_view(store: RunStore, run_id: str, *, as_of: datetime) -> dict[str, object]:
    """Report due, missed, or late-only observations without closing or filling slots."""

    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValidationError("schedule time must be timezone-aware")
    context = read_slate_run_context(store, run_id)
    events = context.event_boards[0].events
    timezone = ZoneInfo(SLATE_TIMEZONE)
    slate = [
        event
        for event in events
        if event.commence_time.astimezone(timezone).date().isoformat()
        == context.metadata.slate_date
    ]
    ledger = read_receipted_snapshot_ledger(store, run_id)
    slate_start = shared_slate_start(ledger)
    slots = {
        (
            entry.candidate_key,
            entry.snapshot.number if isinstance(entry, SnapshotEvidence) else entry.number,
        ): entry
        for entry in ledger
    }
    candidates = []
    for (key, number), first in slots.items():
        if number != 1 or not isinstance(first, SnapshotEvidence):
            continue
        tipoff = first.window_start
        t20 = tipoff - T20_OFFSET
        latest_second = t20 - SNAPSHOT_2_T20_GAP
        first_at = first.snapshot.observation.retrieved_at
        target = snapshot_2_target(first_at, tipoff)
        second = slots.get((key, 2))
        third = slots.get((key, 3))
        if isinstance(second, SnapshotEvidence):
            status_2 = "RECORDED"
        elif isinstance(second, MissedSnapshot) or target is None or as_of > latest_second:
            status_2 = "MISSED"
        elif latest_second - first_at >= SNAPSHOT_2_MINIMUM_SEPARATION:
            status_2 = (
                "DUE"
                if as_of >= max(target, first_at + SNAPSHOT_2_MINIMUM_SEPARATION)
                else "NOT_DUE"
            )
        else:
            status_2 = "DUE" if as_of > first_at else "NOT_DUE"
        if isinstance(third, SnapshotEvidence):
            status_3 = "RECORDED_LATE" if third.late else "RECORDED"
        elif isinstance(third, MissedSnapshot) or as_of >= tipoff:
            status_3 = "MISSED"
        elif as_of > t20:
            status_3 = "LATE_ONLY"
        elif as_of >= tipoff - SNAPSHOT_3_EARLY_WINDOW:
            status_3 = "DUE"
        else:
            status_3 = "NOT_DUE"
        candidates.append(
            {
                "event_id": first.event_id,
                "candidate_key": key,
                "snapshot_2_target": target.isoformat() if target is not None else None,
                "snapshot_2": status_2,
                "snapshot_3": status_3,
            }
        )
    return {
        "run_id": run_id,
        "mode": context.event_boards[0].evidence_mode.value,
        "as_of": as_of.isoformat(),
        "slate_date": context.metadata.slate_date,
        "events": [
            {
                "event_id": event.event_id,
                "home_team": event.home_team,
                "away_team": event.away_team,
                "tipoff": event.commence_time.isoformat(),
                "snapshot_3_opens_at": (
                    (slate_start or event.commence_time) - SNAPSHOT_3_EARLY_WINDOW
                ).isoformat(),
                "t20_target_at": ((slate_start or event.commence_time) - T20_OFFSET).isoformat(),
                "live_t20_review_closes_at": (
                    (slate_start or event.commence_time) - T20_OFFSET + LIVE_T20_REVIEW_GRACE
                ).isoformat(),
            }
            for event in sorted(slate, key=lambda item: (item.commence_time, item.event_id))
        ],
        "candidates": candidates,
    }
