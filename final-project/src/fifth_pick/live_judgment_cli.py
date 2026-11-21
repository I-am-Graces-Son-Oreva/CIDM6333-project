"""Human Controller terminal submission of receipt-bound LIVE assessments."""

import argparse
import json
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from fifth_pick.errors import FifthPickError, ValidationError
from fifth_pick.evidence import EvidenceKind, _validate_evidence_items
from fifth_pick.live_analysis import read_live_supporting_items
from fifth_pick.live_judgment import _scope, parse_live_judgment, record_live_judgment
from fifth_pick.methodology import MethodologyDisposition, _validate_judgment_evidence
from fifth_pick.snapshots import T20_OFFSET, SnapshotEvidence, read_receipted_snapshot_ledger
from fifth_pick.sources.base import EvidenceMode
from fifth_pick.sources.odds_api import validate_event_id
from fifth_pick.sources.supporting_fixture import decode_payload
from fifth_pick.storage import application_run_store
from fifth_pick.t20_review import t20_cited_source_gaps, t20_source_gaps


def controller_assess(arguments: list[str], read: Callable[[str], str] | None) -> int:
    parser = argparse.ArgumentParser(prog="fifth-pick controller-assess", allow_abbrev=False)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--candidate-key", required=True)
    parser.add_argument("--snapshot", required=True, type=int, choices=(2, 3))
    parser.add_argument("--judgment-file", type=Path)
    try:
        args = parser.parse_args(arguments)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2

    try:
        validate_event_id(args.event_id)
        if not re.fullmatch(r"[0-9a-f]{64}", args.candidate_key):
            raise ValidationError("expected an exact candidate key")
        store = application_run_store()

        def inspect(at: datetime):
            rows = [
                row
                for row in read_receipted_snapshot_ledger(store, args.run_id)
                if isinstance(row, SnapshotEvidence)
                and row.candidate_key == args.candidate_key
                and row.event_id == args.event_id
                and row.snapshot.number <= args.snapshot
            ]
            if sorted(row.snapshot.number for row in rows) != list(
                range(1, args.snapshot + 1)
            ) or any(row.late or row.evidence_mode is not EvidenceMode.LIVE for row in rows):
                raise ValidationError("the candidate lacks the exact timely LIVE snapshot sequence")
            stage = max(rows, key=lambda row: row.snapshot.number)
            target = stage.window_start - T20_OFFSET
            evidence = read_live_supporting_items(
                args.run_id,
                stage.candidate_key,
                stage.event_id,
                slot=args.snapshot,
                as_of=at,
                player_id=stage.candidate_id,
                category=stage.snapshot.observation.category,
            )
            if args.snapshot == 3:
                gaps = t20_source_gaps(evidence, target_at=target, reviewed_at=at)
                if gaps:
                    raise ValidationError(" ".join(gaps))
            binding = _scope(stage, evidence, at)
            if binding is None or any(
                item.evidence.provenance.retrieved_at < stage.snapshot.observation.retrieved_at
                for item in evidence
            ):
                raise ValidationError("assessment window or phase evidence is missing or stale")
            statuses = {
                item.facts.get("status")
                for item in evidence
                if item.kind is EvidenceKind.AVAILABILITY and item.facts is not None
            }
            if len(statuses) > 1:
                raise ValidationError("availability records contradict one another")
            checked = _validate_evidence_items(
                evidence,
                candidate_key=stage.candidate_key,
                verified_live=evidence,
            )
            return stage, evidence, checked, binding

        observed_at = datetime.now(UTC)
        stage, evidence, checked, (key, digest) = inspect(observed_at)
        if args.judgment_file is None:
            print(
                json.dumps(
                    {
                        "run_id": args.run_id,
                        "event_id": args.event_id,
                        "candidate_key": args.candidate_key,
                        "snapshot": args.snapshot,
                        "scope_sha256": digest,
                        "supporting_evidence": [item.to_dict() for item in checked],
                    },
                    sort_keys=True,
                )
            )
            return 0
        if read is None:
            raise ValidationError(
                "Controller submission requires interactive terminal confirmation"
            )
        with args.judgment_file.open("rb") as file:
            body = file.read(65_537)
        if len(body) > 65_536:
            raise ValidationError("Controller judgment file exceeds 64 KiB")
        submission = decode_payload(body)
        if (
            not isinstance(submission, dict)
            or submission.keys() != {"run_id", "scope_sha256", "judgment"}
            or submission["run_id"] != args.run_id
            or submission["scope_sha256"] != digest
        ):
            raise ValidationError("Controller submission does not match the current preview digest")
        judgment = parse_live_judgment(submission["judgment"])
        if judgment.disposition is MethodologyDisposition.QUALIFY and not (
            judgment.sufficient_evidence
        ):
            raise ValidationError("a qualifying assessment cannot declare insufficient evidence")
        _validate_judgment_evidence(judgment, checked, ())
        if args.snapshot == 3:
            cited = set(judgment.supporting_evidence_ids)
            cited.update(judgment.meaningful_risk_ids, judgment.senior_lower_support_ids)
            gaps = t20_cited_source_gaps(
                checked, cited, target_at=stage.window_start - T20_OFFSET, reviewed_at=observed_at
            )
            if gaps:
                raise ValidationError(" ".join(gaps))
        if read(f"Controller only. Type RECORD CONTROLLER ASSESSMENT {digest}: ") != (
            f"RECORD CONTROLLER ASSESSMENT {digest}"
        ):
            return 1

        observed_at = datetime.now(UTC)
        stage, evidence, _, current = inspect(observed_at)
        if current != (key, digest):
            raise ValidationError("source evidence changed after the Controller preview")

        def check_current() -> None:
            if inspect(datetime.now(UTC))[3] != (key, digest):
                raise ValidationError("source evidence changed before recording the assessment")

        record_live_judgment(
            store,
            args.run_id,
            stage,
            evidence,
            judgment,
            observed_at=observed_at,
            controller_confirmed=True,
            check_current=check_current,
        )
        print(json.dumps({"status": "RECORDED", "receipt_key": key, "scope_sha256": digest}))
        return 0
    except (FifthPickError, ValueError, OSError, EOFError, RecursionError) as exc:
        detail = str(exc) if isinstance(exc, (FifthPickError, ValueError)) else type(exc).__name__
        print(f"Controller assessment stopped: {detail}", file=sys.stderr)
        return 1
