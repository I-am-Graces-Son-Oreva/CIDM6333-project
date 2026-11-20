"""Rehearse the synthetic course demonstration through the standalone CLI."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

FIXTURES = Path(__file__).resolve().parents[1] / "src/fifth_pick/demo"


def cli(run_id: str, command: str, *args: str, expected: int = 0) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "fifth_pick", command, "--run-id", run_id, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != expected:
        raise SystemExit(f"{command} exited {result.returncode}: {result.stderr or result.stdout}")
    if expected:
        print(f"{command} rejected as expected (exit {expected}): {result.stderr.splitlines()[-1]}")
        return {}
    return json.loads(result.stdout)


def rehearse(run_id: str, third_slot: Path) -> tuple[dict, dict]:
    for slot, fixture in enumerate((FIXTURES / "1", FIXTURES / "2", third_slot), 1):
        stage = (
            cli(run_id, "analyze", "--snapshot", str(slot), "--fixture", str(fixture))
            if slot < 3
            else cli(run_id, "t20", "--fixture", str(fixture))
        )
        print(f"Snapshot {slot} at {stage['observed_at']}: {stage['observations']} observations")
    return cli(run_id, "final"), cli(run_id, "audit")


def show_evidence(audit: dict) -> None:
    run_id = audit["run_id"]
    print(f"{len(audit['receipts'])} receipts in var/fifth-pick/runs/{run_id}/")
    print(f"Replay audit: uv run --offline --no-sync fifth-pick audit --run-id {run_id}")


def main() -> None:
    print("SYNTHETIC FIXTURE DEMO. All lines, times, and evidence are simulated.", flush=True)
    demo_id = f"course-{uuid4().hex}"
    cli(demo_id, "analyze", "--snapshot", "4", "--fixture", str(FIXTURES / "1"), expected=2)
    print("\nFixture A: three valid observations")
    final, audit = rehearse(demo_id, FIXTURES / "3")
    rejections = {row["result"] for row in audit["receipts"] if row["event"] == "SNAPSHOT_REJECTED"}
    if not {"IDENTITY_UNRESOLVED", "NOT_AUTHORIZED"} <= rejections:
        raise SystemExit("Expected ambiguous identity and unauthorized market to be excluded.")
    print(f"Excluded rows: {', '.join(sorted(rejections))}")
    if len(final["proposed"]) != 1 or final["slate"]["maximum_selections"] != 4:
        raise SystemExit("Expected one proposal under the four-slot ceiling.")
    (pick,) = final["proposed"]
    if pick["projection_movement"] != [8.5, 9.0, 9.5] or pick["t20_status"] != "STILL STRONG":
        raise SystemExit("Unexpected fixture movement or T-20 conclusion.")
    print(f"{pick['player']} on {pick['platform']}: {pick['projection_movement']}")
    print(f"{pick['confidence']} confidence | {pick['t20_status']} | {final['state']}")
    print(f"One-game slate ceiling: {final['slate']['maximum_selections']}")
    review = cli(demo_id, "review-status")
    print(f"Native review state: {review['state']} (offline replay below uses a test verdict)")
    recovered = cli(demo_id, "review-handoff")
    if (
        recovered["artifact_sha256"] != review["artifact_sha256"]
        or recovered["dispatch_authorized"]
    ):
        raise SystemExit("Fresh-process handoff did not match the review status.")
    print(f"Fresh-process handoff: {recovered['next_step']}, dispatch not authorized")
    show_evidence(audit)

    print("\nFixture B: provider has no line at T-20")
    with TemporaryDirectory() as temporary:
        third_slot = Path(temporary) / "3"
        shutil.copytree(FIXTURES / "3", third_slot)
        (board,) = third_slot.glob("odds-*.json")
        payload = json.loads(board.read_bytes())
        payload["bookmakers"] = []
        board.write_text(json.dumps(payload), encoding="utf-8")
        final, audit = rehearse(f"{demo_id}-empty", third_slot)
    if final["proposed"] or final["recommendation"] != "NO ENTRY RECOMMENDED TODAY.":
        raise SystemExit("Expected an empty proposal after the third observation was missed.")
    print(final["recommendation"])
    show_evidence(audit)

    print("\nRegression replay: review receipt binding, both ceilings, and no refill", flush=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "-v",
            "tests.test_fixture_cli.FixtureCliTests.test_complete_workflow",
            "tests.test_finalization.FinalizationTests."
            "test_authoritative_one_game_slate_is_half_with_ceiling_four",
            "tests.test_finalization.FinalizationTests."
            "test_authoritative_five_game_slate_is_full_with_ceiling_five",
            "tests.test_finalization.FinalizationTests."
            "test_t20_removal_does_not_replace_from_below_the_frozen_ceiling_pool",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
