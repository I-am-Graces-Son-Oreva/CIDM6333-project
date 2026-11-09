import argparse
import json
import sys

from .conditions import (
    QUESTION_RECALL,
    build_off_sandbox,
    build_on_sandbox,
    run_wrapper,
    tp5_isolation,
    verify_on_event,
)
from .fixture import load_fixture
from .preflight import run_preflight


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m src.e7_memory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    off = subparsers.add_parser("build-off")
    off.add_argument("--sandbox", required=True)
    off.add_argument("--manifest")

    on = subparsers.add_parser("build-on")
    on.add_argument("--sandbox", required=True)
    on.add_argument("--private", required=True)
    on.add_argument("--manifest")
    on.add_argument("--today", default="2026-11-08")

    ask = subparsers.add_parser("ask")
    ask.add_argument("--sandbox", required=True)
    ask.add_argument("--question", required=True)

    verify = subparsers.add_parser("verify-on")
    verify.add_argument("--ledger", required=True)
    verify.add_argument("--question", default=QUESTION_RECALL)

    tp5 = subparsers.add_parser("tp5-isolation")
    tp5.add_argument("--evidence", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--evidence-dir", required=True)

    args = parser.parse_args(argv)

    if args.command == "build-off":
        manifest = build_off_sandbox(args.sandbox, args.manifest)
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "build-on":
        manifest = build_on_sandbox(
            args.sandbox,
            args.private,
            args.manifest,
            args.today,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "ask":
        result = run_wrapper(args.sandbox, args.question)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode

    if args.command == "verify-on":
        fixture = load_fixture()
        matches, event = verify_on_event(
            args.ledger,
            fixture["id"],
            fixture["source"],
            args.question,
        )
        print(json.dumps(
            {"matches": matches, "event": event},
            indent=2,
            sort_keys=True,
        ))
        return 0 if matches else 1

    if args.command == "tp5-isolation":
        data = tp5_isolation(args.evidence)
        print(json.dumps(data, indent=2, sort_keys=True))
        checks = (
            data["official_unchanged"]
            and data["recall_returns_not_in_memory"]
            and data["temp_store_changed"]
            and data["temp_ledger_changed"]
            and bool(data["eviction_events"])
        )
        return 0 if checks else 1

    if args.command == "preflight":
        data, tp5_data = run_preflight(args.evidence_dir)
        print(json.dumps(
            {"isolation": data, "tp5": tp5_data},
            indent=2,
            sort_keys=True,
        ))
        checks = (
            data["isolation"]["off_claim_present"] is False
            and data["isolation"]["on_claim_present_in_sandbox"] is False
            and data["isolation"]["on_fixture_store_outside_sandbox"]
            and data["retriever"]["recall_event_matches_fixture"]
            and data["same_model"]
            and data["same_question"]
            and tp5_data["official_unchanged"]
            and tp5_data["recall_returns_not_in_memory"]
        )
        return 0 if checks else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
