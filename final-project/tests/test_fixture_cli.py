import contextlib
import io
import json
import unittest
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import fifth_pick.storage as storage
from fifth_pick.cli import main
from fifth_pick.models import Category
from fifth_pick.product_review import review_material, review_status
from fifth_pick.review_bridge import process_request
from fifth_pick.snapshots import snapshot_2_target
from fifth_pick.sources.availability import replay_official_document, replay_official_edition
from fifth_pick.sources.base import EvidenceMode, SourceEvent
from fifth_pick.sources.dunkapi_evidence_package import replay_evidence_package
from fifth_pick.sources.dunkapi_history import HistoryScope
from fifth_pick.sources.game_lines import replay_game_lines_request, verify_game_lines_replay
from fifth_pick.sources.injury_pdf import read_injury_status
from fifth_pick.sources.transport import HttpResponse
from tests.m6_support import EVENT_ID, TIPOFF, candidate_key, make_case
from tests.test_dunkapi_evidence_package import package, seal
from tests.test_dunkapi_replay import REGISTRY, ROW, digest, encoded
from tests.test_supporting_sources import game_lines_payload

RUN = "offline-demo"
START = TIPOFF - timedelta(hours=6)
MIDPOINT = snapshot_2_target(START, TIPOFF)
assert MIDPOINT is not None
TIMES = (START, MIDPOINT, TIPOFF - timedelta(minutes=20))


def replay_demo_history(root: Path, slot: int) -> tuple[list[dict], list[str]]:
    """Build clearly synthetic archives and replay them at the fixture slot clock."""
    at = TIMES[slot - 1]
    samples, arguments = [], []
    for number in range(1, 9):
        played = TIPOFF - timedelta(days=number)
        game_date = played.date()
        game_id = str(900 + number)
        row = {**ROW, "game_id": game_id, "date": game_date.isoformat(), "ast": 10 + number}
        _, pages, timing_bytes, coverage, correction, manifest = package(row)
        identity = encoded(
            {"data": {"players": [{"player_id": "101", "name": "Luka Doncic", "team": "GS"}]}}
        )
        timing = json.loads(timing_bytes)
        scope = HistoryScope("101", 2027, game_date, game_date, 100, 1)
        request = asdict(scope) | {
            "first_date": game_date.isoformat(),
            "last_date": game_date.isoformat(),
        }
        teams = ("Synthetic Home", "Synthetic Away")
        prior_team = "Synthetic Away" if number == 1 else "Synthetic Historical Opponent"
        timing.update(
            event_id=EVENT_ID,
            event_teams=list(teams),
            request=request,
            retrieved_at=(at - timedelta(minutes=4)).isoformat(),
            identity_sha256=digest(identity),
        )
        timing["identity"].update(
            canonical_player_id="luka-doncic",
            provider_name="Luka Doncic",
            canonical_team=teams[0],
        )
        timing["games"][0].update(
            game_id=game_id,
            game_date=game_date.isoformat(),
            canonical_player_id="luka-doncic",
            home_team=teams[0],
            away_team=prior_team,
            player_team=teams[0],
            game_timezone="UTC",
            actual_played_at=played.isoformat(),
            actual_completed_at=(played + timedelta(hours=2)).isoformat(),
        )
        timing_bytes = encoded(timing)
        subject = {
            "event_id": EVENT_ID,
            "event_teams": list(teams),
            "canonical_player_id": "luka-doncic",
            "game_id": game_id,
            "request": request,
        }
        coverage.update(
            subject=subject,
            game_ids=[game_id],
            observed_at=(at - timedelta(minutes=3)).isoformat(),
        )
        correction.update(subject=subject, observed_at=(at - timedelta(minutes=2)).isoformat())
        correction["stats"]["assists"] = row["ast"]
        manifest.update(
            subject=subject,
            corroboration_sha256=digest(timing_bytes),
            sealed_at=(at - timedelta(minutes=1)).isoformat(),
            pages=[timing["pages"][0] | {"retrieved_at": timing["retrieved_at"]}],
        )
        manifest_bytes = seal(coverage, correction, manifest)
        pin = digest(manifest_bytes)
        replay = replay_evidence_package(
            manifest_bytes,
            identity_body=identity,
            pages=pages,
            corroboration_body=timing_bytes,
            coverage_body=encoded(coverage),
            correction_body=encoded(correction),
            expected_manifest_sha256=pin,
            scope=scope,
            registry=REGISTRY,
            canonical_player_id="luka-doncic",
            event_id=EVENT_ID,
            event_teams=teams,
            game_id=game_id,
            as_of=at,
            coverage_max_age=timedelta(minutes=30),
            correction_max_age=timedelta(minutes=30),
        )
        sample = replay.game.sample(Category.ASSISTS)
        samples.append(asdict(sample) | {"played_at": sample.played_at.isoformat()})
        directory = root / f"history-{slot}-{game_id}"
        directory.mkdir()
        for name, body in {
            "manifest.json": manifest_bytes,
            "identity.json": identity,
            "page-0.json": pages[0][1],
            "corroboration.json": timing_bytes,
            "coverage.json": encoded(coverage),
            "correction.json": encoded(correction),
        }.items():
            (directory / name).write_bytes(body)
        arguments.extend(("--archive", str(directory), pin))
    return samples, arguments


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

    def attach_replayed_sources(self, slot: int) -> tuple[str, str]:
        observed_at = TIMES[slot - 1]
        event = SourceEvent(EVENT_ID, "Synthetic Home", "Synthetic Away", TIPOFF, ())
        phase = "analysis" if slot == 2 else "t20"
        (payload,) = game_lines_payload()
        payload.update(
            id=event.event_id,
            commence_time=TIPOFF.isoformat(),
            home_team=event.home_team,
            away_team=event.away_team,
        )
        book = payload["bookmakers"][0]
        book["last_update"] = observed_at.isoformat()
        for outcome, team in zip(
            book["markets"][0]["outcomes"], (event.home_team, event.away_team), strict=True
        ):
            outcome["name"] = team
        body = json.dumps([payload]).encode()
        transport = Mock(evidence_mode=EvidenceMode.FIXTURE)
        transport.get.return_value = HttpResponse(200, {}, body)
        lines = replay_game_lines_request(
            self.store,
            RUN,
            transport=transport,
            event=event,
            phase=phase,
            bookmaker="fixture-book",
            observed_at=observed_at,
            max_age=timedelta(minutes=10),
        )
        self.assertEqual(
            lines,
            verify_game_lines_replay(
                self.store,
                RUN,
                body,
                event=event,
                phase=phase,
                bookmaker="fixture-book",
                as_of=observed_at,
                max_age=timedelta(minutes=10),
            ),
        )
        stamp = observed_at.astimezone(ZoneInfo("America/New_York"))
        reference = (
            "https://ak-static.cms.nba.com/referee/injury/"
            f"Injury-Report_{stamp:%Y-%m-%d_%I_%M%p}.pdf"
        )
        transport.get.return_value = HttpResponse(
            200,
            {"Content-Type": "application/pdf"},
            f"%PDF-1.7\nfixture-{slot}\n%%EOF".encode(),
        )
        document = replay_official_document(
            transport,
            reference=reference,
            published_at=observed_at,
            retrieved_at=observed_at,
            max_age=timedelta(minutes=10),
        )
        tipoff = TIPOFF.astimezone(ZoneInfo("America/New_York"))
        status = read_injury_status(
            document,
            tipoff=TIPOFF,
            matchup="AWY@HME",
            team=event.home_team,
            verified_label="Doncic, Luka",
            extract=lambda _body: (
                f"Injury Report: {stamp:%m/%d/%y %I:%M %p}\n"
                f"{tipoff:%m/%d/%Y}  {tipoff:%I:%M} (ET)  AWY@HME  "
                f"{event.home_team}  Doncic, Luka  Available  Synthetic\n"
            ),
        )
        availability = replay_official_edition(
            json.dumps(
                [
                    {
                        "player_id": "luka-doncic",
                        "event_id": EVENT_ID,
                        "status": status,
                        "role": "official-nba-injury-report",
                        "last_update": observed_at.isoformat(),
                    }
                ]
            ).encode(),
            reference=document.reference,
            published_at=document.published_at,
            retrieved_at=document.retrieved_at,
            max_age=timedelta(minutes=10),
            player_id="luka-doncic",
            event_id=EVENT_ID,
        )
        assert availability.selected is not None
        path = self.fixtures / str(slot) / "stage.json"
        checkpoint = json.loads(path.read_bytes())
        (candidate,) = checkpoint["evidence"].values()
        for item in candidate["items"]:
            if item["kind"] == "AVAILABILITY":
                item["facts"] = {
                    "status": availability.selected.status,
                    "synthetic_document_sha256": document.payload_sha256,
                }
            if item["kind"] == "GAME_TOTAL":
                item["facts"] = {
                    "total": lines.total,
                    "synthetic_response_sha256": lines.payload_sha256,
                }
            if item["kind"] == "POINT_SPREAD":
                item["facts"] = {
                    "spread": lines.home_spread,
                    "synthetic_response_sha256": lines.payload_sha256,
                }
        path.write_text(json.dumps(checkpoint), encoding="utf-8")
        return document.payload_sha256, lines.payload_sha256

    def test_complete_workflow(self) -> None:
        write_fixtures(self.fixtures)
        self.stage(1)
        self.attach_replayed_sources(2)
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
        source_digests = self.attach_replayed_sources(3)
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
        store = storage.application_run_store()
        bundle = review_material(store, RUN)
        for source_digest in source_digests:
            self.assertIn(source_digest, str(bundle["review_material"]))
        request = {key: value for key, value in bundle.items() if key != "review_material"}
        request.update(
            kind="VERDICT",
            verdict_json=json.dumps(
                {"status": "PASS", "summary": "Synthetic offline verdict", "findings": []}
            ),
        )
        review = process_request(json.dumps(request), store, TIMES[2])
        self.assertEqual(review.exit_code, 0, review.response)
        self.assertEqual(review_status(store, RUN)["state"], "REVIEWED_FOR_JOSEPH")
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
        self.assertIsInstance(json.loads(self.view("evaluate")), dict)

    def test_revised_history_pipeline_offline(self) -> None:
        write_fixtures(self.fixtures)
        key = candidate_key("Luka Doncic", category=Category.ASSISTS)
        self.stage(1)
        for slot in (2, 3):
            samples, archives = replay_demo_history(self.root, slot)
            stage_file = self.fixtures / str(slot) / "stage.json"
            stage = json.loads(stage_file.read_bytes())
            assessment = stage["evidence"][key]
            assessment["items"] = [
                item
                for item in assessment["items"]
                if item["kind"]
                not in {
                    "AVAILABILITY",
                    "ROLE_MINUTES",
                    "TEAMMATE_ABSENCE",
                    "SAME_SEASON_H2H",
                }
            ]
            last8 = next(item for item in assessment["items"] if item["kind"] == "LAST_8")
            last8["samples"] = samples
            assessment["judgment"].update(
                confidence="MEDIUM",
                supporting_evidence_ids=["last8"],
                meaningful_risk_ids=["blowout-risk"],
                rationale="Synthetic Controller assessment of replayed history and disclosed risk.",
            )
            stage_file.write_text(json.dumps(stage))
            self.stage(slot)
            before = self.inventory()
            command = (
                "history-compare",
                "--run-id",
                RUN,
                "--candidate-key",
                key,
                "--snapshot",
                str(slot),
            )
            code, output, errors = self.command(*command, *archives)
            self.assertEqual(code, 0, errors)
            result = json.loads(output)
            self.assertEqual((result["status"], result["line"]), ("ANALYSIS_ONLY", 8 + slot / 2))
            self.assertEqual(result["archive_provenance"], "synthetic")
            self.assertEqual(result["counts"], {"HIGHER": 8, "LOWER": 0, "PUSH": 0})
            self.assertEqual(self.command(*command, *archives, *archives[:3])[0], 1)
            self.assertEqual(self.command(*command, *archives[:2], "0" * 64)[0], 1)
            self.assertEqual(self.inventory(), before)

        final = json.loads(self.view("final"))
        (pick,) = final["proposed"]
        self.assertEqual(
            (pick["confidence"], pick["projection"], pick["t20_status"]),
            ("MEDIUM", 9.5, "STILL STRONG"),
        )
        bundle = review_material(self.store, RUN)
        request = {name: value for name, value in bundle.items() if name != "review_material"}
        request.update(
            kind="VERDICT",
            verdict_json=json.dumps(
                {"status": "PASS", "summary": "Synthetic reviewer", "findings": []}
            ),
        )
        review = process_request(json.dumps(request), self.store, TIMES[2])
        self.assertEqual(review.exit_code, 0, review.response)
        self.assertEqual(review_status(self.store, RUN)["state"], "REVIEWED_FOR_JOSEPH")
        code, _, errors = self.command("decide", "--run-id", RUN, answers=("APPROVE",))
        self.assertEqual(code, 0, errors)
        self.assertTrue(
            any(row["event"] == "JOSEPH_APPROVED" for row in self.store.read_receipts(RUN))
        )

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
