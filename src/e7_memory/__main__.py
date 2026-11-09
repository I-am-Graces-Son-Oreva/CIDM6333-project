import argparse
import json
import sys
from pathlib import Path

from .capture import capture_evidence
from .conditions import (
    QUESTION_RECALL,
    build_off_sandbox,
    build_on_sandbox,
    isolation_probes,
    probes_ok,
    run_wrapper,
    serve_on,
    sidecar_path,
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
    off.add_argument("--deny", action="append", default=[])

    on = subparsers.add_parser("build-on")
    on.add_argument("--sandbox", required=True)
    on.add_argument("--private", required=True)
    on.add_argument("--manifest")
    on.add_argument("--today", default="2026-11-08")
    on.add_argument("--deny", action="append", default=[])

    ask = subparsers.add_parser("ask")
    ask.add_argument("--sandbox", required=True)
    ask.add_argument("--question", required=True)

    serve = subparsers.add_parser("serve-on")
    serve.add_argument("--sandbox", required=True)

    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("--sandbox", required=True)
    probe_parser.add_argument(
        "--condition",
        choices=["off", "on"],
        default="off",
    )

    verify = subparsers.add_parser("verify-on")
    verify.add_argument("--ledger", required=True)
    verify.add_argument("--question", default=QUESTION_RECALL)

    tp5 = subparsers.add_parser("tp5-isolation")
    tp5.add_argument("--evidence", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--evidence-dir", required=True)

    capture = subparsers.add_parser("capture")
    capture.add_argument("--output", required=True)
    capture.add_argument("--condition", required=True)
    capture.add_argument("--test-point", required=True)
    capture.add_argument("--recall-ledger")
    capture.add_argument("--hash", action="append", default=[])
    capture.add_argument("capture_command", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)

    if args.command == "build-off":
        manifest = build_off_sandbox(
            args.sandbox,
            args.manifest,
            private_paths=args.deny,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "build-on":
        manifest = build_on_sandbox(
            args.sandbox,
            args.private,
            args.manifest,
            args.today,
            private_paths=args.deny,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "ask":
        result = run_wrapper(args.sandbox, args.question)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode

    if args.command == "serve-on":
        serve_on(args.sandbox)
        return 0

    if args.command == "probe":
        sandbox = Path(args.sandbox)
        extra_denied = []
        if args.condition == "on":
            sidecar = json.loads(
                sidecar_path(sandbox).read_text(encoding="utf-8")
            )
            extra_denied = [
                ("private_store", sidecar["store"]),
                ("private_ledger", sidecar["ledger"]),
                ("private_sidecar", str(sidecar_path(sandbox))),
            ]
        probes = isolation_probes(
            sandbox,
            sandbox / "sandbox.sb",
            extra_denied=extra_denied,
        )
        print(json.dumps(probes, indent=2, sort_keys=True))
        return 0 if probes_ok(probes) else 1

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
            and data["same_generation"]
            and data["isolation"]["off_probes_ok"]
            and data["isolation"]["on_probes_ok"]
            and data["network_isolation"][
                "on_service_reachable_during_off"
            ] is False
            and data["network_isolation"]["off_connection_attempt"][
                "reachable"
            ] is False
            and data["network_isolation"][
                "off_launch_starts_service"
            ] is False
            and tp5_data["official_unchanged"]
            and tp5_data["recall_returns_not_in_memory"]
        )
        return 0 if checks else 1

    if args.command == "capture":
        command = args.capture_command
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            parser.error("capture requires a command after --")
        manifest = capture_evidence(
            args.output,
            condition=args.condition,
            test_point=args.test_point,
            command=command,
            recall_ledger=args.recall_ledger,
            hash_paths=args.hash,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return manifest["returncode"]

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
