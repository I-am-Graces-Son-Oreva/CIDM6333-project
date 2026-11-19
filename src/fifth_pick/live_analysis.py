"""Receipt-backed LIVE board and supporting-source analysis."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fifth_pick.errors import ValidationError
from fifth_pick.evidence import EvidenceError, EvidenceItem
from fifth_pick.finalization import (
    FinalizationState,
    _existing_result,
    _load_t20_reviews,
    _review_for_candidate,
    finalize_slate,
)
from fifth_pick.live_judgment import live_judgment_time, read_live_judgment
from fifth_pick.methodology import CandidateCase, EvaluationStatus, evaluate_candidate
from fifth_pick.models import Category, ReasonCode
from fifth_pick.schedule import schedule_view
from fifth_pick.slate_manifest import read_slate_run_context
from fifth_pick.snapshots import MissedSnapshot, SnapshotEvidence, read_receipted_snapshot_ledger
from fifth_pick.sources.base import EvidenceMode, SourceError, SourceEvent
from fifth_pick.sources.game_lines import live_game_line_items
from fifth_pick.sources.injury_pdf import live_injury_items
from fifth_pick.sources.live_history import read_live_history_items
from fifth_pick.storage import RunStore, application_run_store, collection_lock
from fifth_pick.t20_review import review_t20, review_window_allows


def read_live_supporting_items(
    run_id: str,
    candidate_key: str,
    event_id: str,
    *,
    slot: int,
    as_of: datetime,
    player_id: str | None = None,
    category: Category | None = None,
) -> tuple[EvidenceItem, ...]:
    """Derive supported LIVE facts from the application ledger, never from fixture inputs."""
    if slot == 1:
        return ()
    if slot not in (2, 3) or as_of.utcoffset() is None:
        raise EvidenceError("invalid LIVE supporting evidence stage or timestamp")
    store = application_run_store()
    context = read_slate_run_context(store, run_id)
    if not context.event_boards or any(
        board.evidence_mode is not EvidenceMode.LIVE for board in context.event_boards
    ):
        raise EvidenceError("supporting evidence requires a LIVE board manifest")
    events = [event for event in context.event_boards[0].events if event.event_id == event_id]
    if len(events) != 1:
        raise EvidenceError("supporting evidence event is outside the receipt-bound slate")
    game = events[0]
    source_event = SourceEvent(
        game.event_id, game.home_team, game.away_team, game.commence_time, ()
    )
    phase = "analysis" if slot == 2 else "t20"
    try:
        lines = live_game_line_items(
            store,
            run_id,
            event=source_event,
            candidate_key=candidate_key,
            phase=phase,
            as_of=as_of,
        )
        if player_id is None:
            return lines
        history = (
            read_live_history_items(
                store,
                run_id,
                event_id=event_id,
                player_id=player_id,
                candidate_key=candidate_key,
                category=category,
                phase=phase,
                as_of=as_of,
                event_teams=(game.home_team, game.away_team),
            )
            if category is not None
            else ()
        )
        return (
            *lines,
            *history,
            *live_injury_items(
                store,
                run_id,
                event=source_event,
                player_id=player_id,
                candidate_key=candidate_key,
                phase=phase,
                as_of=as_of,
            ),
        )
    except SourceError as exc:
        raise EvidenceError(str(exc)) from exc


def live_analysis_view(
    store: RunStore,
    run_id: str,
    *,
    review: bool,
    snapshot: int | None = None,
    as_of: datetime | None = None,
) -> dict[str, object]:
    """Validate real board evidence without creating a premature analysis or review."""
    if store.root != application_run_store().root:
        raise ValidationError("LIVE analysis requires the application-owned run store")
    if (review and snapshot is not None) or (
        snapshot is not None and (type(snapshot) is not int or snapshot not in (1, 2))
    ):
        raise ValidationError("invalid LIVE analysis snapshot scope")
    slot = 3 if review else snapshot or 2
    now = datetime.now(UTC) if as_of is None else as_of
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
        scoped = [row for row in rows if row.snapshot.number <= slot]
        if not scoped:
            continue
        timely = sorted(row.snapshot.number for row in scoped if not row.late)
        selected_stage = next((row for row in scoped if row.snapshot.number == slot), None)
        assessment_at = (
            live_judgment_time(store, run_id, selected_stage)
            if selected_stage is not None and slot in (2, 3)
            else None
        )
        evidence_at = now if assessment_at is None else assessment_at
        supporting = (
            read_live_supporting_items(
                run_id,
                key,
                scoped[0].event_id,
                slot=slot,
                as_of=evidence_at,
                player_id=scoped[0].candidate_id,
                category=scoped[0].snapshot.observation.category,
            )
            if any(row.snapshot.number == slot for row in scoped)
            else ()
        )
        judgment = (
            read_live_judgment(store, run_id, selected_stage, supporting, as_of=now)
            if selected_stage is not None and slot in (2, 3)
            else None
        )
        audit = evaluate_candidate(
            CandidateCase(
                tuple(rows),
                tuple(missed[key]),
                supporting,
                judgment=judgment,
                snapshot_run_id=run_id,
                supporting_slot=slot,
                supporting_as_of=evidence_at,
            )
        )
        scoped_missed = sorted(row.number for row in missed[key] if row.number <= slot)
        retrospective = len(scoped) != len(rows) or len(scoped_missed) != len(missed[key])
        candidates.append(
            {
                "candidate_key": key,
                "event": audit.candidate.event,
                "status": "PROVISIONAL" if retrospective else audit.status.value,
                "reasons": [] if retrospective else [reason.value for reason in audit.exclusions],
                "timely_snapshot_slots": timely,
                "late_snapshot_slots": sorted(row.snapshot.number for row in scoped if row.late),
                "missed_snapshot_slots": scoped_missed,
                "board_sequence_complete": timely == [1, 2, 3],
                "supporting_evidence": [item.to_dict() for item in supporting],
                "judgment_recorded": judgment is not None,
            }
        )
    proposal = _advance_live_review(store, run_id, snapshots, missed, now) if review else None
    return {
        "run_id": run_id,
        "mode": "LIVE",
        "snapshot_scope": slot,
        "status": "BLOCKED" if proposal is None else proposal,
        "reason": (
            None
            if proposal is not None
            else ReasonCode.T20_CHECK_UNAVAILABLE.value
            if review
            else ReasonCode.INSUFFICIENT_SUPPORTING_EVIDENCE.value
        ),
        "detail": (
            "Review and finalization used both recorded assessment phases."
            if proposal is not None
            else "No proposal was released. Required source or assessment evidence is incomplete."
        ),
        "candidates": candidates,
        **({"schedule": schedule_view(store, run_id, as_of=now)} if review else {}),
    }


def _replay_live_case(
    store: RunStore,
    run_id: str,
    rows: list[SnapshotEvidence],
    missed: list[MissedSnapshot],
    slot: int,
    now: datetime,
) -> CandidateCase | None:
    stage = next((row for row in rows if row.snapshot.number == slot and not row.late), None)
    if stage is None:
        return None
    observed_at = live_judgment_time(store, run_id, stage)
    if observed_at is None or observed_at > now:
        return None
    evidence = read_live_supporting_items(
        run_id,
        stage.candidate_key,
        stage.event_id,
        slot=slot,
        as_of=observed_at,
        player_id=stage.candidate_id,
        category=stage.snapshot.observation.category,
    )
    judgment = read_live_judgment(store, run_id, stage, evidence, as_of=now)
    if judgment is None:
        return None
    return CandidateCase(
        tuple(rows),
        tuple(missed),
        evidence,
        judgment=judgment,
        snapshot_run_id=run_id,
        supporting_slot=slot,
        supporting_as_of=observed_at,
    )


def _advance_live_review(
    store: RunStore,
    run_id: str,
    snapshots: dict[str, list[SnapshotEvidence]],
    missed: dict[str, list[MissedSnapshot]],
    now: datetime,
) -> str | None:
    """Replay both assessments, keep each event's review window, then finalize once."""
    with collection_lock(store, run_id):
        existing = _existing_result(store, run_id)
        if existing is not None:
            return None if existing.state is FinalizationState.BLOCKED else existing.state.value
        # Reopen under the collection lock before any write.
        locked = read_receipted_snapshot_ledger(store, run_id)
        captured: list[SnapshotEvidence | MissedSnapshot] = [
            row for rows in snapshots.values() for row in rows
        ]
        captured.extend(row for rows in missed.values() for row in rows)
        if len(locked) != len(captured) or any(row not in captured for row in locked):
            raise ValidationError("LIVE snapshots changed before review; reopen the run")
        prior_cases = []
        pairs = []
        waiting = False
        reviews = _load_t20_reviews(store, run_id)
        for key, rows in snapshots.items():
            if {row.snapshot.number for row in rows if not row.late} != {1, 2, 3}:
                waiting = True
                continue
            prior = _replay_live_case(store, run_id, rows, missed.get(key, []), 2, now)
            current = _replay_live_case(store, run_id, rows, missed.get(key, []), 3, now)
            if prior is None or current is None:
                waiting = True
                continue
            prior_audit = evaluate_candidate(prior)
            current_audit = evaluate_candidate(current)
            if prior_audit.status is not EvaluationStatus.QUALIFIED:
                # An explicit, sufficient, nonqualifying prior assessment never joins the pool.
                if not prior_audit.methodology_sufficient_evidence:
                    waiting = True
                else:
                    prior_cases.append(prior)
                continue
            if not current_audit.methodology_sufficient_evidence:
                waiting = True
                continue
            prior_cases.append(prior)
            pairs.append((prior, current))
            matching = [row for row in reviews if row["candidate_key"] == key]
            if matching:
                if (
                    _review_for_candidate(
                        key=key, prior_case=prior, current_case=current, reviews=reviews
                    )
                    is None
                ):
                    raise ValidationError("existing LIVE T-20 review differs from assessment state")
                continue
            target = rows[0].event_start - timedelta(minutes=20)
            if not review_window_allows(target, now, live=True):
                waiting = True
                continue
            stage = next(row for row in rows if row.snapshot.number == 3)
            refreshed = read_live_supporting_items(
                run_id,
                key,
                stage.event_id,
                slot=3,
                as_of=now,
                player_id=stage.candidate_id,
                category=stage.snapshot.observation.category,
            )
            if refreshed != current.evidence:
                raise ValidationError("LIVE supporting evidence changed after the T-20 assessment")
            review_t20(prior, current, run_id=run_id, store=store, reviewed_at=now)
        if waiting or not prior_cases:
            return None
        result = finalize_slate(tuple(prior_cases), tuple(pairs), run_id=run_id, store=store)
        return None if result.state is FinalizationState.BLOCKED else result.state.value
