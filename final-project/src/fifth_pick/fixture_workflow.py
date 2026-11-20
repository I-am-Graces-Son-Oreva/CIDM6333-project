"""Operator-invoked, receipt-bound fixture workflow over M4 through M9."""

from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fifth_pick.approval import load_approved_final
from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.finalization import (
    AUDIT_FILENAME,
    FINAL_FILENAME,
    FinalizationState,
    _existing_result,
    _load_t20_reviews,
    finalize_slate,
)
from fifth_pick.fixture_input import (
    FixtureError,
    decode_assessment,
    digest,
    encode,
    fixture_time,
    load_fixture,
    read_object,
)
from fifth_pick.identity import IdentityResolver
from fifth_pick.methodology import CandidateCase
from fifth_pick.ranking import rank_candidates
from fifth_pick.receipts import Receipt, redact_text
from fifth_pick.registry import Registry
from fifth_pick.results import RESULTS_FILENAME, _read_results
from fifth_pick.slate_manifest import read_slate_run_context
from fifth_pick.snapshots import (
    MissedSnapshot,
    SnapshotEvidence,
    SnapshotWorkflow,
    read_receipted_snapshot_ledger,
)
from fifth_pick.sources.base import EvidenceMode
from fifth_pick.sources.fixtures import FIXTURE_LABEL
from fifth_pick.storage import RunStore, _atomic_write, collection_lock
from fifth_pick.t20_review import review_t20

_STAGE_SOURCE = "fixture-workflow"
_STARTED = "FIXTURE_STAGE_STARTED"
_COMPLETED = "FIXTURE_STAGE_COMPLETED"
_STAGE_FIELDS = {
    "run_id",
    "snapshot",
    "mode",
    "observed_at",
    "board_digest",
    "aliases_digest",
    "input_digest",
    "evidence",
    "snapshots_digest",
    "reviews_digest",
    "m6_ranking_digest",
    "m6_ranked_candidate_keys",
}


def _stage_receipt(run_id: str, number: int, observed_at: str, event: str, subject: str) -> Receipt:
    action = "started" if event == _STARTED else "completed"
    return Receipt(
        timestamp=observed_at,
        event=event,
        result=action.upper(),
        subject=subject,
        source=_STAGE_SOURCE,
        reason=f"SNAPSHOT={number}; MODE=FIXTURE",
        run_id=run_id,
        event_key=f"fixture-stage-{number}-{action}",
    )


def _file(directory: Path, name: str) -> Path:
    path = directory / name
    if path.is_symlink():
        raise FixtureError(f"{name} cannot be a symlink")
    return path


def _text_fields(value: Any) -> Any:
    """Keep the durable copy free of credentials in free-text fixture fields."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [_text_fields(item) for item in value]
    if isinstance(value, dict):
        return {key: _text_fields(item) for key, item in value.items()}
    return value


@dataclass(frozen=True, slots=True)
class _Run:
    stages: list[dict[str, Any]]
    snapshots: tuple[SnapshotEvidence | MissedSnapshot, ...]
    reviews: tuple[dict[str, object], ...]
    receipts: tuple[dict[str, str | None], ...]


def is_fixture_workflow(store: RunStore, run_id: str) -> bool:
    """Distinguish the new fixture command workflow from existing M8/M9 runs."""
    directory = store.run_directory(run_id)
    return any(directory.glob("fixture-stage-*.json")) or any(
        receipt.get("event") in (_STARTED, _COMPLETED) for receipt in store.read_receipts(run_id)
    )


def _read_run(store: RunStore, run_id: str, *, allow_new: bool = False) -> _Run:
    directory = store.run_directory(run_id)
    receipts = store.read_receipts(run_id)
    receipt_keys = [receipt.get("event_key") for receipt in receipts]
    if len(receipt_keys) != len(set(receipt_keys)) or None in receipt_keys:
        raise FixtureError("duplicate or missing fixture run receipt identity")
    stage_receipts = {
        receipt["event_key"]: receipt
        for receipt in receipts
        if receipt["event"] in (_STARTED, _COMPLETED)
    }
    stages = []
    for number in (1, 2, 3):
        begun = stage_receipts.pop(f"fixture-stage-{number}-started", None)
        done = stage_receipts.pop(f"fixture-stage-{number}-completed", None)
        path = _file(directory, f"fixture-stage-{number}.json")
        if begun is None and done is None and not path.exists():
            continue
        if begun is None or done is None or not path.exists() or number != len(stages) + 1:
            raise FixtureError("fixture stage is incomplete or out of sequence; preserve the run")
        stage = read_object(path)
        if (
            set(stage) != _STAGE_FIELDS
            or type(stage.get("snapshot")) is not int
            or stage.get("snapshot") != number
            or not isinstance(stage.get("evidence"), dict)
            or any(
                not isinstance(stage.get(field), str)
                for field in (
                    "observed_at",
                    "board_digest",
                    "aliases_digest",
                    "input_digest",
                    "snapshots_digest",
                    "reviews_digest",
                )
            )
            or stage.get("run_id") != run_id
            or stage.get("mode") != FIXTURE_LABEL
            or begun
            != _stage_receipt(
                run_id, number, stage["observed_at"], _STARTED, stage["input_digest"]
            ).to_dict()
            or done
            != _stage_receipt(
                run_id, number, stage["observed_at"], _COMPLETED, digest(stage)
            ).to_dict()
        ):
            raise FixtureError("fixture checkpoint does not match its stage receipts")
        stages.append(stage)
    if stage_receipts:
        raise FixtureError("unexpected fixture stage receipts")
    if not stages:
        if allow_new and not receipts and (not directory.exists() or not any(directory.iterdir())):
            return _Run([], (), (), ())
        raise FixtureError("run has no verified fixture workflow")

    context = read_slate_run_context(store, run_id)
    if len(context.event_boards) != len(stages):
        raise FixtureError("fixture checkpoints do not match the number of M4 boards")
    for stage, board in zip(stages, context.event_boards, strict=True):
        if (
            board.evidence_mode is not EvidenceMode.FIXTURE
            or board.snapshot_number != stage["snapshot"]
            or board.payload_sha256 != stage["board_digest"]
            or board.recorded_at != fixture_time(stage["observed_at"])
        ):
            raise FixtureError("fixture checkpoint does not match the receipt-bound M4 board")

    snapshots = read_receipted_snapshot_ledger(store, run_id)
    reviews = _load_t20_reviews(store, run_id)
    if any(
        entry.evidence_mode is not EvidenceMode.FIXTURE
        for entry in snapshots
        if isinstance(entry, SnapshotEvidence)
    ):
        raise FixtureError("fixture workflow contains non-fixture snapshot evidence")
    if stages[-1]["snapshots_digest"] != digest([entry.to_dict() for entry in snapshots]) or stages[
        -1
    ]["reviews_digest"] != digest(reviews):
        raise FixtureError("fixture ledgers do not match the completed checkpoint")
    if _file(directory, FINAL_FILENAME).exists():
        audit = read_object(_file(directory, AUDIT_FILENAME))
        if len(stages) != 3 or digest(audit.get("m6_ranking")) != stages[-1]["m6_ranking_digest"]:
            raise FixtureError("final audit does not match the persisted M6 ranking")
    return _Run(stages, snapshots, reviews, receipts)


def require_complete_fixture(store: RunStore, run_id: str) -> _Run:
    run = _read_run(store, run_id)
    if len(run.stages) != 3:
        raise FixtureError("complete the explicit T-20 fixture stage before finalization")
    return run


def _cases(
    entries: tuple[SnapshotEvidence | MissedSnapshot, ...],
    stage: dict[str, Any],
) -> tuple[CandidateCase, ...]:
    snapshots: dict[str, list[SnapshotEvidence]] = defaultdict(list)
    missed: dict[str, list[MissedSnapshot]] = defaultdict(list)
    for entry in entries:
        if isinstance(entry, SnapshotEvidence):
            snapshots[entry.candidate_key].append(entry)
        else:
            missed[entry.candidate_key].append(entry)
    cases = []
    for key, observations in snapshots.items():
        evidence, judgment = decode_assessment(
            key, stage["evidence"].get(key), fixture_time(stage["observed_at"])
        )
        cases.append(CandidateCase(tuple(observations), tuple(missed[key]), evidence, (), judgment))
    return tuple(cases)


def _case_pairs(
    snapshots: tuple[SnapshotEvidence | MissedSnapshot, ...],
    prior: dict[str, Any],
    current: dict[str, Any],
) -> tuple[tuple[CandidateCase, CandidateCase], ...]:
    # Both M6 evaluations use legitimate M5 observations, including the third.
    # The prior supporting evidence was collected at analyze; the refresh is from T-20.
    return tuple(zip(_cases(snapshots, prior), _cases(snapshots, current), strict=True))


def collect_fixture_stage(
    store: RunStore, run_id: str, number: int, fixture: Path
) -> dict[str, object]:
    supplied = load_fixture(fixture)
    observed_at = supplied.observed_at.isoformat()
    aliases_digest = digest(supplied.aliases)
    board_digest = supplied.board.provenance.payload_sha256
    input_digest = digest([observed_at, aliases_digest, board_digest, supplied.evidence])
    evidence = _text_fields(supplied.evidence)
    for key, assessment in evidence.items():
        decode_assessment(key, assessment, supplied.observed_at)
    if number == 1 and evidence:
        raise FixtureError("collect supporting watchlist evidence at analyze --snapshot 2")

    with collection_lock(store, run_id):
        run = _read_run(store, run_id, allow_new=number == 1)
        if number <= len(run.stages):
            stage = run.stages[number - 1]
            if stage["input_digest"] != input_digest:
                raise FixtureError(f"conflicting replay for fixture Snapshot {number}")
            return _stage_view(stage, run, replay=True)
        if number != len(run.stages) + 1:
            raise FixtureError("fixture stages must run in order")
        if run.stages and (
            aliases_digest != run.stages[0]["aliases_digest"]
            or supplied.observed_at <= fixture_time(run.stages[-1]["observed_at"])
        ):
            raise FixtureError("fixture stage needs the same aliases and a later observation time")

        known_keys = {
            entry.candidate_key
            for entry in run.snapshots
            if isinstance(entry, SnapshotEvidence) and entry.snapshot.number == 1
        }
        if not evidence.keys() <= known_keys:
            raise FixtureError("supporting evidence names a candidate outside the run watchlist")
        resolver = IdentityResolver(
            Registry.from_universe(load_configs().approved_universe), supplied.aliases
        )
        workflow = SnapshotWorkflow(
            store, resolver, AuthorizationGate(), clock=lambda: supplied.observed_at
        )
        store.append_receipt(_stage_receipt(run_id, number, observed_at, _STARTED, input_digest))
        workflow.collect(run_id, number, supplied.board)
        snapshots = read_receipted_snapshot_ledger(store, run_id)
        stage = {
            "run_id": run_id,
            "snapshot": number,
            "mode": FIXTURE_LABEL,
            "observed_at": observed_at,
            "board_digest": board_digest,
            "aliases_digest": aliases_digest,
            "input_digest": input_digest,
            "evidence": evidence,
            "snapshots_digest": digest([entry.to_dict() for entry in snapshots]),
            "m6_ranking_digest": None,
            "m6_ranked_candidate_keys": [],
        }
        if number == 3:
            pairs = _case_pairs(snapshots, run.stages[1], stage)
            ranking = rank_candidates(tuple(prior for prior, _ in pairs))
            stage["m6_ranking_digest"] = digest(ranking.to_dict())
            stage["m6_ranked_candidate_keys"] = [
                item.audit.candidate_key for item in ranking.ranked
            ]
            for prior, current in pairs:
                review_t20(
                    prior, current, reviewed_at=supplied.observed_at, run_id=run_id, store=store
                )
        reviews = _load_t20_reviews(store, run_id)
        stage["reviews_digest"] = digest(reviews)
        directory = store.run_directory(run_id)
        _atomic_write(_file(directory, f"fixture-stage-{number}.json"), encode(stage) + b"\n")
        store.append_receipt(_stage_receipt(run_id, number, observed_at, _COMPLETED, digest(stage)))
        return _stage_view(stage, _read_run(store, run_id), replay=False)


def _stage_view(stage: dict[str, Any], run: _Run, *, replay: bool) -> dict[str, object]:
    number = stage["snapshot"]
    return {
        "run_id": stage["run_id"],
        "mode": FIXTURE_LABEL,
        "snapshot": number,
        "observed_at": stage["observed_at"],
        "m6_ranked_candidate_keys": stage["m6_ranked_candidate_keys"],
        "status": "ALREADY RECORDED" if replay else "RECORDED",
        "observations": sum(
            isinstance(entry, SnapshotEvidence) and entry.snapshot.number == number
            for entry in run.snapshots
        ),
        "reviews": [
            {"candidate_key": entry["candidate_key"], "status": entry["conclusion"]}
            for entry in run.reviews
        ]
        if number == 3
        else [],
    }


def candidates_view(store: RunStore, run_id: str) -> dict[str, object]:
    run = _read_run(store, run_id)
    reviews = {review["candidate_key"]: review for review in run.reviews}
    candidates = []
    for case in _cases(run.snapshots, run.stages[-1]):
        latest = case.snapshots[-1]
        observation = latest.snapshot.observation
        review = reviews.get(latest.candidate_key)
        candidates.append(
            {
                "candidate_key": latest.candidate_key,
                "player": observation.player,
                "platform": observation.platform.value,
                "category": observation.category.value,
                "direction": observation.direction.value,
                "projection": observation.projection,
                "snapshots": [entry.snapshot.number for entry in case.snapshots],
                "supporting_evidence": "PROVIDED" if case.evidence else "UNAVAILABLE",
                "status": "PROVISIONAL" if review is None else review["conclusion"],
            }
        )
    return {
        "run_id": run_id,
        "mode": FIXTURE_LABEL,
        "status": "PROVISIONAL EVIDENCE WATCHLIST" if len(run.stages) < 3 else "T-20 REVIEWED",
        "candidates": candidates,
    }


def final_view(store: RunStore, run_id: str) -> tuple[dict[str, object], bool]:
    with collection_lock(store, run_id):
        run = require_complete_fixture(store, run_id)
        pairs = _case_pairs(run.snapshots, run.stages[1], run.stages[2])
        outcome = finalize_slate(
            tuple(prior for prior, _ in pairs),
            pairs,
            run_id=run_id,
            store=store,
            expected_ranking_digest=run.stages[2]["m6_ranking_digest"],
        )
        final = read_object(outcome.final_path)
        reviews = {review["event_key"]: review for review in run.reviews}
        proposed = []
        for item in final["proposed"]:
            current = reviews[item["t20_event_key"]]["current_audit"]
            assert isinstance(current, dict)
            snapshots = current["snapshots"]
            proposed.append(
                {
                    **item,
                    "movement": current["movement"],
                    "projection_movement": [
                        snapshot["observation"]["projection"] for snapshot in snapshots
                    ],
                    "history": current["history"],
                }
            )
        return (
            {
                "run_id": run_id,
                "mode": FIXTURE_LABEL,
                "state": outcome.state.value,
                "recommendation": final["recommendation"],
                "slate": final["slate"],
                "proposed": proposed,
            },
            outcome.state is FinalizationState.BLOCKED,
        )


def audit_view(store: RunStore, run_id: str) -> dict[str, object]:
    run = _read_run(store, run_id)
    directory = store.run_directory(run_id)
    final_path = _file(directory, FINAL_FILENAME)
    audit_path = _file(directory, AUDIT_FILENAME)
    result_path = _file(directory, RESULTS_FILENAME)
    results = None
    final = None
    audit = None
    if final_path.exists():
        _existing_result(store, run_id)
        final = read_object(final_path)
        audit = read_object(audit_path)
        if audit.get("run_id") != run_id:
            raise FixtureError("finalization audit has the wrong run ID")
    if result_path.exists():
        results, _ = _read_results(store, run_id, load_approved_final(store, run_id))
    context = read_slate_run_context(store, run_id)
    return {
        "run_id": run_id,
        "mode": FIXTURE_LABEL,
        "stages": run.stages,
        "board_manifests": [asdict(board) for board in context.event_boards],
        "snapshots": [entry.to_dict() for entry in run.snapshots],
        "t20_reviews": run.reviews,
        "final": final,
        "finalization_audit": audit,
        "results": results,
        "receipts": run.receipts,
    }
