import contextlib
import io
import json
import unittest
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import fifth_pick.storage as storage
from fifth_pick.cli import main
from fifth_pick.models import Category
from fifth_pick.snapshots import snapshot_2_target
from tests.m6_support import EVENT_ID, TIPOFF, candidate_key, make_case

RUN = "offline-demo"
START = TIPOFF - timedelta(hours=6)
MIDPOINT = snapshot_2_target(START, TIPOFF)
assert MIDPOINT is not None
TIMES = (START, MIDPOINT, TIPOFF - timedelta(minutes=20))


def write_fixtures(root: Path, *, projection: bool = True, supporting: bool = True) -> None:
    case = make_case(category=Category.ASSISTS)
    assert case.judgment is not None
    key = candidate_key("Luka Doncic", category=Category.ASSISTS)
    event = {
        "id": EVENT_ID,
        "sport_key": "basketball_nba",
        "commence_time": TIPOFF.isoformat(),
        "home_team": "Synthetic Home",
        "away_team": "Synthetic Away",
    }
    for number, timestamp in enumerate(TIMES, 1):
        directory = root / str(number)
        directory.mkdir(parents=True)
        (directory / "events.json").write_text(json.dumps([event]), encoding="utf-8")
        outcomes = [
            {"name": name, "description": "Luka Doncic", "point": line, "price": 1.95}
            for name, line in (("Over", 8 + number / 2), ("Under", 8 + number / 2))
        ]
        market = {
            "key": "player_assists",
            "last_update": timestamp.isoformat(),
            "outcomes": outcomes,
        }
        book = {
            "key": "prizepicks",
            "last_update": timestamp.isoformat(),
            "markets": [
                {
                    **market,
                    "outcomes": [
                        *outcomes,
                        {
                            "name": "Over",
                            "description": "Ambiguous Guard",
                            "point": 5.5,
                            "price": 1.95,
                        },
                    ],
                },
                {**market, "key": "player_rebounds_assists"},
            ],
        }
        odds = {**event, "bookmakers": [book] if projection or number != 3 else []}
        (directory / f"odds-{EVENT_ID}.json").write_text(json.dumps(odds), encoding="utf-8")
        items = []
        for item in case.evidence:
            row = item.to_dict()
            items.append(
                {
                    field: row[field]
                    for field in (
                        "evidence_id",
                        "kind",
                        "effect",
                        "significance",
                        "claim",
                        "excerpt",
                        "samples",
                        "facts",
                    )
                }
            )
        items.append(
            {
                "evidence_id": "availability",
                "kind": "AVAILABILITY",
                "effect": "NEUTRAL",
                "significance": "IMPORTANT",
                "claim": "Synthetic fixture lists the player as available.",
                "excerpt": "Luka Doncic available in this simulated observation.",
            }
        )
        bundle = {
            "mode": "fixture",
            "observed_at": timestamp.isoformat(),
            "aliases": {
                "Luka Doncic": ["luka-doncic"],
                "Ambiguous Guard": ["luka-doncic", "jayson-tatum"],
            },
            "evidence": {key: {"items": items, "judgment": asdict(case.judgment)}}
            if supporting and number > 1
            else {},
        }
        (directory / "stage.json").write_text(json.dumps(bundle), encoding="utf-8")


class FixtureCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.fixtures = self.root / "fixture"
        self.store = storage.RunStore(self.root / "state")
        patcher = patch.object(storage, "APPLICATION_STORAGE_ROOT", self.store.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def command(self, *arguments: str, answers: tuple[str, ...] = ()) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            patch("builtins.input", side_effect=answers),
        ):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def stage(self, number: int) -> str:
        cmd = ("analyze", "--snapshot", str(number)) if number < 3 else ("t20",)
        code, output, error = self.command(
            *cmd, "--run-id", RUN, "--fixture", str(self.fixtures / str(number))
        )
        self.assertEqual(code, 0, error)
        return output

    def view(self, command: str) -> str:
        code, output, error = self.command(command, "--run-id", RUN)
        self.assertEqual(code, 0, error)
        return output

    def inventory(self) -> dict[str, bytes]:
        directory = self.store.run_directory(RUN)
        return {
            str(p.relative_to(directory)): p.read_bytes()
            for p in directory.rglob("*")
            if p.is_file()
        }

    def test_complete_workflow(self) -> None:
        write_fixtures(self.fixtures)
        self.stage(1)
        self.stage(2)
        before = self.inventory()
        watchlist = self.view("candidates")
        self.assertIn("PROVISIONAL", watchlist)
        self.assertIn("Luka Doncic", watchlist)
        self.assertNotIn('"QUALIFIED"', watchlist)
        audit = json.loads(self.view("audit"))
        rejected = {
            receipt["result"]
            for receipt in audit["receipts"]
            if receipt["event"] == "SNAPSHOT_REJECTED"
        }
        self.assertTrue({"IDENTITY_UNRESOLVED", "NOT_AUTHORIZED"} <= rejected)
        self.assertEqual(self.inventory(), before)
        stage = json.loads(self.stage(3))
        self.assertEqual(
            stage["m6_ranked_candidate_keys"],
            [candidate_key("Luka Doncic", category=Category.ASSISTS)],
        )
        final = json.loads(self.view("final"))
        self.assertEqual(len(final["proposed"]), 1)
        pick = final["proposed"][0]
        self.assertEqual(pick["projection"], 9.5)
        self.assertEqual(pick["confidence"], "HIGH")
        self.assertEqual(pick["t20_status"], "STILL STRONG")
        self.assertEqual(pick["projection_movement"], [8.5, 9.0, 9.5])
        self.assertTrue(pick["history"])
        self.assertTrue(pick["material_risks"])
        selection_id = pick["candidate_key"]
        args = ("result", "record", "--run-id", RUN, "--selection", selection_id)
        code, _output, error = self.command(*args)
        self.assertEqual(code, 1)
        self.assertIn("receipt-verified", error)
        code, shown, error = self.command("decide", "--run-id", RUN, answers=("APPROVE",))
        self.assertEqual(code, 0, error)
        self.assertIn("STILL STRONG", shown)
        self.assertIn("9.5", shown)
        code, _output, error = self.command(
            *args,
            answers=(
                "HIT",
                "synthetic-fixture",
                TIPOFF.isoformat(),
                f"fixture:results/{selection_id}",
                "Synthetic PrizePicks Luka Doncic Assists Higher 9.5 settled HIT.",
                "YES",
            ),
        )
        self.assertEqual(code, 0, error)
        audit = json.loads(self.view("audit"))
        result = audit["results"]["results"][0]
        self.assertEqual(result["selection"]["candidate_key"], selection_id)
        self.assertEqual(result["t20_projection"], 9.5)
        self.assertTrue(result["fixture"])

    def test_missing_third_observation_never_qualifies(self) -> None:
        write_fixtures(self.fixtures, projection=False)
        self.stage(1)
        self.stage(2)
        code, _, error = self.command("final", "--run-id", RUN)
        self.assertEqual(code, 1)
        self.assertIn("T-20", error)
        self.stage(3)
        self.assertIn("NO ENTRY RECOMMENDED TODAY.", self.view("final"))
        audit = json.loads(self.view("audit"))
        self.assertFalse(any(entry["number"] == 3 for entry in audit["snapshots"]))
        self.assertTrue(audit["t20_reviews"])
        self.assertTrue(
            all(
                entry["conclusion"] == "REMOVE RECOMMENDED"
                and "PROJECTION_OBSERVATION_MISSED" in entry["reason_codes"]
                for entry in audit["t20_reviews"]
            )
        )

    def test_missing_supporting_evidence_is_excluded(self) -> None:
        write_fixtures(self.fixtures, supporting=False)
        for number in (1, 2, 3):
            self.stage(number)
        self.assertIn("NO ENTRY RECOMMENDED TODAY.", self.view("final"))
        audit = json.loads(self.view("audit"))
        self.assertIn(
            "INSUFFICIENT_SUPPORTING_EVIDENCE",
            audit["t20_reviews"][0]["current_audit"]["exclusions"],
        )

    def test_unavailable_t20_refresh_removes_the_previously_ranked_candidate(self) -> None:
        write_fixtures(self.fixtures)
        self.stage(1)
        self.stage(2)
        descriptor = self.fixtures / "3/stage.json"
        bundle = json.loads(descriptor.read_text())
        bundle["evidence"] = {}
        descriptor.write_text(json.dumps(bundle))

        stage = json.loads(self.stage(3))
        self.assertEqual(len(stage["m6_ranked_candidate_keys"]), 1)
        self.assertIn("NO ENTRY RECOMMENDED TODAY.", self.view("final"))
        audit = json.loads(self.view("audit"))
        self.assertTrue(
            any(
                row["prior_status"] == "QUALIFIED"
                and row["current_status"] == "INSUFFICIENT EVIDENCE"
                and row["conclusion"] == "REMOVE RECOMMENDED"
                for row in audit["t20_reviews"]
            )
        )

    def test_stage_replay_is_read_only_and_conflicting_replay_is_rejected(self) -> None:
        write_fixtures(self.fixtures)
        self.stage(1)
        before = self.inventory()
        self.stage(1)
        self.assertEqual(self.inventory(), before)
        descriptor = self.fixtures / "1/stage.json"
        bundle = json.loads(descriptor.read_text())
        bundle["observed_at"] = (START + timedelta(minutes=1)).isoformat()
        descriptor.write_text(json.dumps(bundle))
        code, _, error = self.command(
            "analyze", "--snapshot", "1", "--run-id", RUN, "--fixture", str(descriptor.parent)
        )
        self.assertEqual(code, 1)
        self.assertIn("conflict", error.lower())
        self.assertEqual(self.inventory(), before)

    def test_live_descriptor_and_mixed_settlement_are_rejected(self) -> None:
        write_fixtures(self.fixtures)
        descriptor = self.fixtures / "1/stage.json"
        original = descriptor.read_text()
        descriptor.write_text(original.replace('"fixture"', '"live"', 1))
        code, _, error = self.command(
            "analyze", "--snapshot", "1", "--run-id", RUN, "--fixture", str(descriptor.parent)
        )
        self.assertEqual(code, 1)
        self.assertIn("explicit fixture mode", error)
        self.assertFalse(self.store.run_directory(RUN).exists())
        descriptor.write_text(original)
        for number in (1, 2, 3):
            self.stage(number)
        pick = json.loads(self.view("final"))["proposed"][0]
        self.assertEqual(self.command("decide", "--run-id", RUN, answers=("APPROVE",))[0], 0)
        before = self.inventory()
        code, _, error = self.command(
            "result",
            "record",
            "--run-id",
            RUN,
            "--selection",
            pick["candidate_key"],
            answers=("HIT", "manual-live-source"),
        )
        self.assertEqual(code, 1)
        self.assertIn("synthetic-fixture settlement source", error)
        self.assertEqual(self.inventory(), before)

    def test_repeated_or_tampered_stage_receipt_blocks_views_and_next_stage(self) -> None:
        write_fixtures(self.fixtures)
        self.stage(1)
        path = self.store.receipts_path(RUN)
        raw = path.read_bytes()
        line = next(line for line in raw.splitlines() if b"fixture-stage-1-completed" in line)
        path.write_bytes(raw + line + b"\n")
        before = self.inventory()
        for command in (
            ("candidates", "--run-id", RUN),
            ("audit", "--run-id", RUN),
            ("analyze", "--snapshot", "2", "--run-id", RUN, "--fixture", str(self.fixtures / "2")),
        ):
            code, _, error = self.command(*command)
            self.assertEqual(code, 1)
            self.assertIn("receipt", error)
        self.assertEqual(self.inventory(), before)
