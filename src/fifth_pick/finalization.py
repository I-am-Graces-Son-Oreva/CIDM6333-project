"""M8 ranked-slate proposal generation with an authoritative slate boundary."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

from fifth_pick.errors import StorageError
from fifth_pick.methodology import AuditEvidenceMode, CandidateCase
from fifth_pick.models import ReasonCode
from fifth_pick.ranking import NearTieDecision, RankingError, RankingResult, rank_candidates
from fifth_pick.receipts import Receipt
from fifth_pick.slate_manifest import (
    SLATE_TIMEZONE,
    M4EventBoardManifest,
    SlateEvent,
    SlateManifestError,
    SlateRunContext,
    read_slate_run_context,
)
from fifth_pick.sources.base import EvidenceMode
from fifth_pick.sources.odds_api import SOURCE_ID
from fifth_pick.storage import RunStore, _atomic_write, application_run_store

FINAL_FILENAME: Final[str] = "final.json"
AUDIT_FILENAME: Final[str] = "audit.json"
T20_REVIEW_FILENAME: Final[str] = "t20-reviews.jsonl"
HALF_MAXIMUM: Final[int] = 4
FULL_MAXIMUM: Final[int] = 5
NO_ENTRY_RECOMMENDATION: Final[str] = "NO ENTRY RECOMMENDED TODAY."
_POSITIVE_T20_CONCLUSIONS: Final[frozenset[str]] = frozenset({"STILL STRONG", "DOWNGRADED"})


class FinalizationError(ValueError):
    """Raised when M8 cannot safely produce or read a slate proposal."""


class FinalizationState(StrEnum):
    """Result of preparing the slate for Joseph's decision."""

    AWAITING_JOSEPH = "AWAITING_JOSEPH"
    NO_ENTRY = "NO_ENTRY"
    BLOCKED = "BLOCKED"
    APPROVED_BY_JOSEPH = "APPROVED_BY_JOSEPH"
    REJECTED_BY_JOSEPH = "REJECTED_BY_JOSEPH"


@dataclass(frozen=True, slots=True)
class FinalizationResult:
    state: FinalizationState
    final_path: Path
    audit_path: Path


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def proposal_fingerprint(record: dict[str, object]) -> str:
    """Hash only the current versioned proposal, not mutable audit metadata."""

    proposal = {
        "run_id": record.get("run_id"),
        "slate_version": record.get("slate_version"),
        "slate": record.get("slate"),
        "recommendation": record.get("recommendation"),
        "proposed": record.get("proposed"),
    }
    return hashlib.sha256(_canonical_json(proposal).encode("utf-8")).hexdigest()


def proposal_receipt_key(record: dict[str, object]) -> str:
    return f"final-selection-proposed-{record['slate_version']}-{proposal_fingerprint(record)}"


def _write_json(path: Path, record: dict[str, object]) -> None:
    content = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    try:
        _atomic_write(path, content.encode("utf-8"))
    except OSError as exc:
        raise FinalizationError(f"cannot persist {path.name}") from exc


def _candidate_key(case: CandidateCase) -> str:
    if not isinstance(case, CandidateCase) or not case.snapshots:
        raise FinalizationError("M8 requires identifiable M6 CandidateCase inputs")
    return case.snapshots[-1].candidate_key


def _manifest_start_board(context: SlateRunContext) -> M4EventBoardManifest:
    metadata = context.metadata
    matches = tuple(
        board
        for board in context.event_boards
        if board.snapshot_number == 1
        if board.request_timestamp == metadata.started_at
        and board.payload_sha256 == metadata.start_payload_sha256
    )
    if len(matches) != 1:
        raise FinalizationError("authoritative M4 slate-start manifest is missing or ambiguous")
    return matches[0]


def _read_authoritative_slate(
    store: RunStore,
    run_id: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, SlateEvent], EvidenceMode]:
    context = read_slate_run_context(store, run_id)
    board = _manifest_start_board(context)
    if any(item.evidence_mode is not board.evidence_mode for item in context.event_boards):
        raise FinalizationError("M4 event-board manifest mixes LIVE and FIXTURE evidence")
    if board.evidence_mode is EvidenceMode.LIVE and store.root != application_run_store().root:
        raise FinalizationError("LIVE finalization requires the application-owned RunStore")
    slate_day = context.metadata.slate_date
    timezone = ZoneInfo(SLATE_TIMEZONE)
    events_by_id = {}
    for event in board.events:
        prior = events_by_id.get(event.event_id)
        if prior is not None and prior != event:
            raise FinalizationError("authoritative M4 manifest repeats an event ID inconsistently")
        events_by_id[event.event_id] = event
    slate_events = {
        event_id: event
        for event_id, event in events_by_id.items()
        if event.commence_time.astimezone(timezone).date().isoformat() == slate_day
    }
    slate = {
        "slate_date": slate_day,
        "slate_timezone": SLATE_TIMEZONE,
        "game_count": len(slate_events),
        "classification": (
            "NO_GAMES"
            if not slate_events
            else "HALF"
            if len(slate_events) <= HALF_MAXIMUM
            else "FULL"
        ),
        "maximum_selections": (
            0
            if not slate_events
            else HALF_MAXIMUM
            if len(slate_events) <= HALF_MAXIMUM
            else FULL_MAXIMUM
        ),
    }
    audit = {
        "run_id": run_id,
        "slate_date": slate_day,
        "slate_timezone": SLATE_TIMEZONE,
        "authoritative_board": {
            "snapshot_number": board.snapshot_number,
            "evidence_mode": board.evidence_mode.value,
            "event_key": board.event_key,
            "payload_sha256": board.payload_sha256,
            "request_timestamp": board.request_timestamp.isoformat(),
            "events": [
                {
                    "event_id": event.event_id,
                    "home_team": event.home_team,
                    "away_team": event.away_team,
                    "commence_time": event.commence_time.isoformat(),
                }
                for event in sorted(events_by_id.values(), key=lambda item: item.event_id)
            ],
        },
    }
    return slate, audit, slate_events, board.evidence_mode


def _load_t20_reviews(store: RunStore, run_id: str) -> tuple[dict[str, object], ...]:
    path = store.run_directory(run_id) / T20_REVIEW_FILENAME
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ()
    except (OSError, UnicodeDecodeError) as exc:
        raise FinalizationError("M7 T-20 review ledger is unreadable") from exc

    receipts = store.read_receipts(run_id)
    reviews = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise FinalizationError(f"M7 T-20 review ledger has a blank line at {line_number}")
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FinalizationError(
                f"M7 T-20 review ledger has invalid JSON at line {line_number}"
            ) from exc
        if not isinstance(raw, dict):
            raise FinalizationError("M7 T-20 review ledger contains a non-object record")
        record = dict(raw)
        event_key = record.pop("event_key", None)
        if (
            record.get("run_id") != run_id
            or not isinstance(record.get("candidate_key"), str)
            or not isinstance(event_key, str)
            or event_key
            != f"t20-review-{hashlib.sha256(_canonical_json(record).encode('utf-8')).hexdigest()}"
        ):
            raise FinalizationError("M7 T-20 review ledger has invalid identity or content hash")
        try:
            reviewed_at = datetime.fromisoformat(record["reviewed_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise FinalizationError("M7 T-20 review timestamp is malformed") from exc
        if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
            raise FinalizationError("M7 T-20 review timestamp must be timezone-aware")
        reason_codes = record.get("reason_codes")
        audit_reasons = record.get("audit_reasons")
        if (
            not isinstance(reason_codes, list)
            or any(not isinstance(item, str) for item in reason_codes)
            or not isinstance(audit_reasons, list)
            or any(not isinstance(item, str) for item in audit_reasons)
            or not isinstance(record.get("conclusion"), str)
        ):
            raise FinalizationError("M7 T-20 review record is malformed")
        expected_receipt = Receipt(
            timestamp=reviewed_at.isoformat(),
            event="T20_REVIEW",
            result=record["conclusion"],
            subject=record["candidate_key"],
            source=SOURCE_ID,
            reason="; ".join((*reason_codes, *audit_reasons)),
            run_id=run_id,
            event_key=event_key,
        ).to_dict()
        if tuple(item for item in receipts if item.get("event_key") == event_key) != (
            expected_receipt,
        ):
            raise FinalizationError("M7 T-20 review has no matching application receipt")
        record["event_key"] = event_key
        reviews.append(record)
    return tuple(reviews)


def _case_audit(case: CandidateCase) -> dict[str, object]:
    try:
        result = rank_candidates((case,))
    except (RankingError, StorageError, ValueError) as exc:
        raise FinalizationError("M6 candidate case could not be re-evaluated") from exc
    return result.audits[0].to_dict()


def _review_for_candidate(
    *,
    key: str,
    prior_case: CandidateCase,
    current_case: CandidateCase | None,
    reviews: tuple[dict[str, object], ...],
) -> dict[str, object] | None:
    matching = tuple(item for item in reviews if item.get("candidate_key") == key)
    if len(matching) != 1 or current_case is None:
        return None
    if _candidate_key(prior_case) != key or _candidate_key(current_case) != key:
        return None
    review = matching[0]
    if review.get("previous_audit") != _case_audit(prior_case) or review.get(
        "current_audit"
    ) != _case_audit(current_case):
        return None
    return review


def _review_matches_evidence_mode(
    review: dict[str, object],
    expected_mode: AuditEvidenceMode,
) -> bool:
    for field in ("previous_audit", "current_audit"):
        audit = review.get(field)
        if audit is None:
            continue
        if not isinstance(audit, dict) or audit.get("evidence_mode") != expected_mode.value:
            return False
    return True


def _case_matches_slate(case: CandidateCase, slate_events: dict[str, SlateEvent]) -> bool:
    for snapshot in case.snapshots:
        event = slate_events.get(snapshot.event_id)
        if event is None or event.commence_time != snapshot.event_start:
            return False
    return True


def _append_proposal_receipt(
    store: RunStore,
    record: dict[str, object],
    *,
    result: str,
) -> str:
    fingerprint = proposal_fingerprint(record)
    persisted = store.append_receipt(
        Receipt(
            timestamp=str(record["proposal_recorded_at"]),
            event="FINAL_SELECTION_PROPOSED",
            result=result,
            subject=fingerprint,
            source=SOURCE_ID,
            reason=f"SLATE_VERSION={record['slate_version']}",
            run_id=str(record["run_id"]),
            event_key=proposal_receipt_key(record),
        )
    )
    timestamp = persisted.receipt.get("timestamp")
    if not isinstance(timestamp, str):
        raise FinalizationError("persisted proposal receipt has no timestamp")
    record["proposal_recorded_at"] = timestamp
    return timestamp


def _existing_result(store: RunStore, run_id: str) -> FinalizationResult | None:
    run_directory = store.run_directory(run_id)
    final_path = run_directory / FINAL_FILENAME
    audit_path = run_directory / AUDIT_FILENAME
    try:
        record = json.loads(final_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FinalizationError("existing final.json is unreadable; refusing to overwrite") from exc
    if not isinstance(record, dict) or record.get("run_id") != run_id:
        raise FinalizationError("existing final.json has an invalid run binding")
    try:
        state = FinalizationState(record["state"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FinalizationError("existing final.json has an unknown state") from exc
    if state is FinalizationState.BLOCKED:
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FinalizationError(
                "blocked M8 audit is unreadable; refusing to overwrite"
            ) from exc
        blocking_reasons = audit.get("blocking_reasons") if isinstance(audit, dict) else None
        if (
            not isinstance(blocking_reasons, list)
            or not blocking_reasons
            or any(not isinstance(item, str) for item in blocking_reasons)
        ):
            raise FinalizationError("blocked M8 state has no detailed audit reason")
        expected = Receipt(
            timestamp=str(record.get("proposal_recorded_at")),
            event="FINALIZATION_BLOCKED",
            result="BLOCKED",
            subject=run_id,
            source=SOURCE_ID,
            reason="; ".join(blocking_reasons),
            run_id=run_id,
            event_key=f"finalization-blocked-{proposal_fingerprint(record)}",
        ).to_dict()
        if tuple(
            item
            for item in store.read_receipts(run_id)
            if item.get("event_key") == expected["event_key"]
        ) != (expected,):
            raise FinalizationError("blocked M8 state has no matching application receipt")
    else:
        try:
            from fifth_pick.approval import ApprovalError, _read_final

            _read_final(store, run_id)
        except (ApprovalError, StorageError) as exc:
            raise FinalizationError("existing final.json has no valid decision trail") from exc

    if state in (
        FinalizationState.APPROVED_BY_JOSEPH,
        FinalizationState.REJECTED_BY_JOSEPH,
        FinalizationState.BLOCKED,
    ):
        result_state = state
    elif record.get("recommendation") == NO_ENTRY_RECOMMENDATION:
        result_state = FinalizationState.NO_ENTRY
    else:
        result_state = FinalizationState.AWAITING_JOSEPH
    return FinalizationResult(result_state, final_path, audit_path)


def finalize_slate(
    cases: tuple[CandidateCase, ...],
    current_cases: tuple[tuple[CandidateCase, CandidateCase], ...],
    *,
    run_id: str,
    store: RunStore,
    tie_breaks: tuple[NearTieDecision, ...] = (),
) -> FinalizationResult:
    """Create one auditable proposal; never treat it as Joseph's official decision."""

    if type(store) is not RunStore:
        raise FinalizationError("finalization requires the M2 RunStore")
    if not isinstance(run_id, str) or not run_id.strip():
        raise FinalizationError("run_id must be non-empty")
    if not isinstance(cases, tuple) or any(not isinstance(case, CandidateCase) for case in cases):
        raise TypeError("finalization accepts only a tuple of M6 CandidateCase records")
    if not isinstance(current_cases, tuple):
        raise TypeError("current_cases must be a tuple of prior/current CandidateCase pairs")
    current_by_key: dict[str, CandidateCase] = {}
    for pair in current_cases:
        if (
            not isinstance(pair, tuple)
            or len(pair) != 2
            or any(not isinstance(case, CandidateCase) for case in pair)
        ):
            raise TypeError("current_cases must contain prior/current CandidateCase pairs")
        prior, current = pair
        key = _candidate_key(prior)
        if key in current_by_key:
            raise FinalizationError("current M7 cases repeat an M6 candidate key")
        current_by_key[key] = current

    try:
        ranking: RankingResult = rank_candidates(cases, tie_breaks=tie_breaks)
    except (RankingError, StorageError, ValueError) as exc:
        raise FinalizationError("M6 ranking could not be reproduced") from exc

    run_directory = store.run_directory(run_id)
    final_path = run_directory / FINAL_FILENAME
    audit_path = run_directory / AUDIT_FILENAME
    if not final_path.resolve().is_relative_to(run_directory):
        raise FinalizationError("final artifact path escapes the run directory")
    if not audit_path.resolve().is_relative_to(run_directory):
        raise FinalizationError("audit artifact path escapes the run directory")
    existing = _existing_result(store, run_id)
    if existing is not None:
        return existing

    exclusions: list[dict[str, object]] = []
    blocking_reasons: list[str] = []
    slate_events: dict[str, SlateEvent] = {}
    slate_evidence_mode: EvidenceMode | None = None
    try:
        slate, slate_audit, slate_events, slate_evidence_mode = _read_authoritative_slate(
            store,
            run_id,
        )
    except (SlateManifestError, StorageError, OSError, ValueError) as exc:
        slate = {
            "slate_date": None,
            "slate_timezone": SLATE_TIMEZONE,
            "game_count": None,
            "classification": None,
            "maximum_selections": None,
        }
        slate_audit = {"run_id": run_id, "manifest_error": str(exc)}
        blocking_reasons.append(f"Authoritative M4 slate manifest unavailable: {exc}")

    proposed: list[dict[str, object]] = []
    valid_m7_count = 0
    has_manifest = slate["game_count"] is not None
    game_count = slate["game_count"]
    maximum = slate["maximum_selections"]
    evidence_mode_blocked = False
    if slate_evidence_mode is not None:
        expected_audit_mode = (
            AuditEvidenceMode.LIVE
            if slate_evidence_mode is EvidenceMode.LIVE
            else AuditEvidenceMode.FIXTURE
        )
        for audit in ranking.audits:
            if audit.evidence_mode is not expected_audit_mode:
                blocking_reasons.append(
                    f"M6 candidate {audit.candidate_key} evidence mode "
                    f"{audit.evidence_mode.value} does not match the M4 "
                    f"{slate_evidence_mode.value} run mode."
                )
                evidence_mode_blocked = True
        for pair in current_cases:
            for case in pair:
                try:
                    current_audit = rank_candidates((case,)).audits[0]
                except (RankingError, StorageError, ValueError) as exc:
                    raise FinalizationError("M7 candidate case could not be re-evaluated") from exc
                if current_audit.evidence_mode is not expected_audit_mode:
                    blocking_reasons.append(
                        f"M7 candidate {current_audit.candidate_key} evidence mode "
                        f"{current_audit.evidence_mode.value} does not match the M4 "
                        f"{slate_evidence_mode.value} run mode."
                    )
                    evidence_mode_blocked = True
    ranked_keys = {item.audit.candidate_key for item in ranking.ranked}
    for audit in ranking.audits:
        if audit.candidate_key not in ranked_keys:
            reasons = [reason.value for reason in audit.exclusions]
            if audit.status.value not in reasons:
                reasons.insert(0, audit.status.value)
            exclusions.append(
                {
                    "stage": "M6",
                    "candidate_key": audit.candidate_key,
                    "player": audit.candidate.player,
                    "reasons": reasons,
                }
            )
    frozen_pool = (
        ranking.ranked[:maximum]
        if (
            has_manifest
            and isinstance(maximum, int)
            and game_count != 0
            and not evidence_mode_blocked
        )
        else ()
    )
    frozen_keys = {item.audit.candidate_key for item in frozen_pool}
    m7_reviews_required = False
    for ranked in frozen_pool:
        candidate_case = next(
            case for case in cases if _candidate_key(case) == ranked.audit.candidate_key
        )
        if _case_matches_slate(candidate_case, slate_events):
            m7_reviews_required = True
            break
    reviews: tuple[dict[str, object], ...] = ()
    if m7_reviews_required:
        try:
            reviews = _load_t20_reviews(store, run_id)
        except (StorageError, OSError, ValueError) as exc:
            blocking_reasons.append(f"Authoritative M7 T-20 review ledger unavailable: {exc}")
        if slate_evidence_mode is not None:
            expected_review_mode = (
                AuditEvidenceMode.LIVE
                if slate_evidence_mode is EvidenceMode.LIVE
                else AuditEvidenceMode.FIXTURE
            )
            if any(
                not _review_matches_evidence_mode(review, expected_review_mode)
                for review in reviews
            ):
                blocking_reasons.append(
                    "M7 T-20 review evidence mode mixes LIVE and FIXTURE records."
                )
                evidence_mode_blocked = True
                frozen_pool = ()
                frozen_keys.clear()

    for item in ranking.ranked:
        audit = item.audit
        if audit.candidate_key not in frozen_keys:
            exclusions.append(
                {
                    "candidate_key": audit.candidate_key,
                    "player": audit.candidate.player,
                    "reasons": ["OUTSIDE_FROZEN_CEILING_POOL"],
                }
            )

    if has_manifest and game_count != 0:
        for ranked in frozen_pool:
            candidate_audit = ranked.audit
            case = next(
                case for case in cases if _candidate_key(case) == candidate_audit.candidate_key
            )
            if not _case_matches_slate(case, slate_events):
                exclusions.append(
                    {
                        "candidate_key": candidate_audit.candidate_key,
                        "player": candidate_audit.candidate.player,
                        "reasons": ["CANDIDATE_EVENT_NOT_IN_AUTHORITATIVE_SLATE"],
                    }
                )
                continue
            review = _review_for_candidate(
                key=candidate_audit.candidate_key,
                prior_case=case,
                current_case=current_by_key.get(candidate_audit.candidate_key),
                reviews=reviews,
            )
            if review is None:
                exclusions.append(
                    {
                        "candidate_key": candidate_audit.candidate_key,
                        "player": candidate_audit.candidate.player,
                        "reasons": [ReasonCode.T20_CHECK_UNAVAILABLE.value],
                    }
                )
                continue
            valid_m7_count += 1
            if (
                review.get("conclusion") not in _POSITIVE_T20_CONCLUSIONS
                or review.get("readiness_passed") is not True
                or review.get("blocked") is not False
            ):
                reasons = review.get("reason_codes")
                exclusions.append(
                    {
                        "candidate_key": candidate_audit.candidate_key,
                        "player": candidate_audit.candidate.player,
                        "reasons": (
                            list(reasons)
                            if isinstance(reasons, list) and reasons
                            else ["T20_REVIEW_DID_NOT_RETAIN_CANDIDATE"]
                        ),
                    }
                )
                continue
            if candidate_audit.candidate_id in {
                entry["player_id"] for entry in proposed if isinstance(entry.get("player_id"), str)
            }:
                exclusions.append(
                    {
                        "candidate_key": candidate_audit.candidate_key,
                        "player": candidate_audit.candidate.player,
                        "reasons": ["PLAYER_ALREADY_OCCUPIES_A_FINAL_SLOT"],
                    }
                )
                continue
            proposed.append(
                {
                    "rank": ranked.rank,
                    "candidate_key": candidate_audit.candidate_key,
                    "player_id": candidate_audit.candidate_id,
                    "player": candidate_audit.candidate.player,
                    "platform": candidate_audit.candidate.platform.value,
                    "category": candidate_audit.candidate.category.value,
                    "direction": candidate_audit.candidate.direction.value,
                    "event": candidate_audit.candidate.event,
                    "projection": candidate_audit.candidate.projection,
                    "confidence": (
                        None
                        if candidate_audit.confidence is None
                        else candidate_audit.confidence.value
                    ),
                    "reason": ranked.reason,
                }
            )

        if m7_reviews_required and frozen_pool and valid_m7_count == 0:
            blocking_reasons.append(
                "No receipt-bound M7 T-20 review matches the frozen M6 ceiling pool."
            )

    if not blocking_reasons and not proposed:
        recommendation = NO_ENTRY_RECOMMENDATION
        result_state = FinalizationState.NO_ENTRY
    elif blocking_reasons:
        recommendation = "FINALIZATION BLOCKED."
        result_state = FinalizationState.BLOCKED
    else:
        recommendation = "RECOMMENDED FINAL SLATE FOR JOSEPH'S REVIEW."
        result_state = FinalizationState.AWAITING_JOSEPH

    now = datetime.now(UTC).isoformat()
    final_record: dict[str, object] = {
        "schema_version": 1,
        "run_id": run_id,
        "state": (
            FinalizationState.BLOCKED.value
            if blocking_reasons
            else FinalizationState.AWAITING_JOSEPH.value
        ),
        "slate_version": 1,
        "proposal_recorded_at": now,
        "recommendation": recommendation,
        "slate": slate,
        "proposed": proposed,
        "approval": {
            "action": None,
            "actor": None,
            "reason": None,
            "official_final": None,
            "decision_receipt_key": None,
            "decision_slate_version": None,
            "decision_recorded_at": None,
            "decision_selection": None,
        },
        "audit_file": AUDIT_FILENAME,
    }
    audit_record: dict[str, object] = {
        "schema_version": 1,
        "run_id": run_id,
        "slate": slate_audit,
        "m6_ranking": ranking.to_dict(),
        "m7_reviews": list(reviews),
        "m7_reviews_required": m7_reviews_required,
        "exclusions": exclusions,
        "blocking_reasons": blocking_reasons,
        "stop_reason": recommendation,
        "joseph_decisions": [],
    }
    _write_json(audit_path, audit_record)
    if blocking_reasons:
        persisted = store.append_receipt(
            Receipt(
                timestamp=now,
                event="FINALIZATION_BLOCKED",
                result="BLOCKED",
                subject=run_id,
                source=SOURCE_ID,
                reason="; ".join(blocking_reasons),
                run_id=run_id,
                event_key=f"finalization-blocked-{proposal_fingerprint(final_record)}",
            )
        )
        persisted_timestamp = persisted.receipt.get("timestamp")
        if not isinstance(persisted_timestamp, str):
            raise FinalizationError("persisted blocked-finalization receipt has no timestamp")
        final_record["proposal_recorded_at"] = persisted_timestamp
    else:
        _append_proposal_receipt(
            store,
            final_record,
            result=result_state.value,
        )
    _write_json(final_path, final_record)
    return FinalizationResult(result_state, final_path, audit_path)
