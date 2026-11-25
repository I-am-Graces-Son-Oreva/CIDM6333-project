"""Rehearse the synthetic course demonstration through the standalone CLI."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fifth_pick.menu_presentation import fields, slate_table, table

FIXTURES = Path(__file__).resolve().parents[1] / "src/fifth_pick/demo/classroom"


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
        fields(
            "Input guard check",
            (
                ("Result", f"Rejected as expected (exit {expected})"),
                ("Details", result.stderr.splitlines()[-1]),
            ),
        )
        return {}
    return json.loads(result.stdout)


def rehearse(run_id: str, third_slot: Path) -> tuple[dict, dict]:
    stages = []
    for slot, fixture in enumerate((FIXTURES / "1", FIXTURES / "2", third_slot), 1):
        stage = (
            cli(run_id, "analyze", "--snapshot", str(slot), "--fixture", str(fixture))
            if slot < 3
            else cli(run_id, "t20", "--fixture", str(fixture))
        )
        stages.append((slot, stage["observed_at"], stage["observations"]))
    table(("Snapshot", "Observed at (UTC)", "Observations"), stages)
    return cli(run_id, "final"), cli(run_id, "audit")


def show_evidence(audit: dict) -> None:
    run_id = audit["run_id"]
    fields("Audit", (("Receipts", len(audit["receipts"])), ("Run ID", run_id)))
    print(f"Replay audit: uv run --offline --no-sync fifth-pick audit --run-id {run_id}")


def main() -> None:
    print("SYNTHETIC FIXTURE DEMO. All lines, times, and evidence are simulated.", flush=True)
    demo_id = f"course-{uuid4().hex}"
    cli(demo_id, "analyze", "--snapshot", "4", "--fixture", str(FIXTURES / "1"), expected=2)
    print("\nFixture A: 12 players, four games, and three snapshot stages")
    final, audit = rehearse(demo_id, FIXTURES / "3")
    rejections = {row["result"] for row in audit["receipts"] if row["event"] == "SNAPSHOT_REJECTED"}
    if not {"IDENTITY_UNRESOLVED", "NOT_AUTHORIZED"} <= rejections:
        raise SystemExit("Expected ambiguous identity and unauthorized market to be excluded.")
    picks = final["proposed"]
    if (
        {pick["player"] for pick in picks}
        != {"Luka Doncic", "Jayson Tatum", "Joel Embiid", "Anthony Davis"}
        or len(picks) != 4
        or final["slate"]["maximum_selections"] != 4
        or final["state"] != "AWAITING_JOSEPH"
    ):
        raise SystemExit("Expected four proposals awaiting Joseph under the four-slot ceiling.")
    for pick in picks:
        if pick["t20_status"] != "STILL STRONG":
            raise SystemExit("Unexpected T-20 conclusion.")
        if pick["player"] == "Luka Doncic" and pick["projection_movement"] != [8.5, 9.0, 9.5]:
            raise SystemExit("Unexpected assists projection movement.")
    print("\nPROPOSED SELECTIONS")
    slate_table(picks)
    print("\nSUPPORTING EVIDENCE")
    table(
        ("Player", "Snapshot lines", "T-20 rationale"),
        (
            (
                pick["player"],
                " → ".join(map(str, pick["projection_movement"])),
                pick["t20_rationale"],
            )
            for pick in picks
        ),
    )
    review = cli(demo_id, "review-status")
    recovered = cli(demo_id, "review-handoff")
    if (
        recovered["artifact_sha256"] != review["artifact_sha256"]
        or recovered["dispatch_authorized"]
    ):
        raise SystemExit("Fresh-process handoff did not match the review status.")
    fields(
        "Proposal status",
        (
            ("Proposal", "4 of 4 selections proposed. Awaiting Joseph."),
            ("Excluded rows", ", ".join(sorted(rejections))),
            ("Native review", f"{review['state']} (regression replay uses a test verdict)"),
            ("Handoff", recovered["next_step"]),
            ("Dispatch", "Not authorized"),
        ),
    )
    show_evidence(audit)

    print("\nFixture B: provider has no line at T-20")
    with TemporaryDirectory() as temporary:
        third_slot = Path(temporary) / "3"
        shutil.copytree(FIXTURES / "3", third_slot)
        for board in third_slot.glob("odds-*.json"):
            payload = json.loads(board.read_bytes())
            payload["bookmakers"] = []
            board.write_text(json.dumps(payload), encoding="utf-8")
        final, audit = rehearse(f"{demo_id}-empty", third_slot)
    if final["proposed"] or final["recommendation"] != "NO ENTRY RECOMMENDED TODAY.":
        raise SystemExit("Expected an empty proposal after the third observation was missed.")
    fields(
        "Slate outcome",
        (("Decision", final["recommendation"]), ("Reason", "No provider lines at T-20.")),
    )
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
