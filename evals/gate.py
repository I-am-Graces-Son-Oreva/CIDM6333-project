"""Offline regression gate for The Fifth Pick exact authorization."""

import argparse
import json
from pathlib import Path

from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.models import Category, Direction
from fifth_pick.registry import Registry

EVALS = Path(__file__).resolve().parent


def grade(expected: bool, actual: object) -> bool:
    return type(actual) is bool and expected is actual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=EVALS / "baseline.json")
    parser.add_argument("--output", type=Path, default=EVALS)
    witness = parser.add_mutually_exclusive_group()
    witness.add_argument("--plant-wrong", metavar="CASE_ID")
    witness.add_argument("--hollow", action="store_true")
    args = parser.parse_args()
    cases = [json.loads(line) for line in (EVALS / "golden.jsonl").read_text().splitlines()]
    baseline = json.loads(args.baseline.read_text())
    ids = {case["id"] for case in cases}
    if (
        len(cases) != 12
        or len(ids) != len(cases)
        or ids != set(baseline)
        or any(type(value) is not bool for value in baseline.values())
        or any(type(case["expect"]) is not bool or not case["covers"] for case in cases)
        or sum(case["expect"] is False for case in cases) < 4
    ):
        parser.error("invalid golden cases or baseline")
    if args.plant_wrong is not None and args.plant_wrong not in ids:
        parser.error("unknown planted case ID")

    gate = AuthorizationGate()
    registry = Registry.from_universe(load_configs().approved_universe)
    results = []
    for case in cases:
        expected = case["expect"]
        player = registry.player_by_canonical_name(case["player"])
        decision = gate.authorize(
            player.player_id if player else case["player"],
            Category(case["category"]),
            Direction(case["direction"]),
        )
        actual = not expected if args.plant_wrong == case["id"] else decision.allowed
        row = dict(id=case["id"], expected=expected, actual=actual, passed=grade(expected, actual))
        if args.hollow:
            row["constant_false_passed"] = grade(expected, False)
            row["constant_true_passed"] = grade(expected, True)
            row["passed"] = not (row["constant_false_passed"] and row["constant_true_passed"])
        results.append(row)

    failed = [str(row["id"]) for row in results if not row["passed"]]
    delta = dict(
        regressed_ids=[row["id"] for row in results if baseline[row["id"]] and not row["passed"]],
        new_passes=[row["id"] for row in results if not baseline[row["id"]] and row["passed"]],
        pass_rate=(len(results) - len(failed)) / len(results),
        trial_count=len(results) * (2 if args.hollow else 1),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in (("results.json", results), ("delta.json", delta)):
        (args.output / name).write_text(json.dumps(value, indent=2) + "\n")
    print("RED: " + ", ".join(failed) if failed else "GREEN")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
