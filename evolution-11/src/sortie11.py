"""Offline evidence runner for bounded Fifth Pick control probes."""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from fifth_pick.approval import ApprovalError, load_approved_final
from fifth_pick.authorization import AuthorizationGate
from fifth_pick.config import load_configs
from fifth_pick.models import Category, Direction
from fifth_pick.receipts import redact_text
from fifth_pick.registry import Registry
from fifth_pick.review import ReviewError, parse_review_verdict
from fifth_pick.storage import RunStore

ROOT = Path(__file__).resolve().parents[2]
E11 = ROOT / "evolution-11"
MODEL = "llama3.2:3b"


class Refused(ValueError):
    """A production decision denied the requested effect."""


class Recorder:
    def __init__(self, root: Path, commit: str):
        self.root = root
        self.commit = commit
        (root / "traces").mkdir(parents=True, exist_ok=True)
        (root / "receipts").mkdir(exist_ok=True)
        self.parents: dict[str, str] = {}

    def write_line(self, name: str, row: dict) -> None:
        with (self.root / name).open("a") as stream:
            stream.write(json.dumps(row) + "\n")

    @contextmanager
    def span(self, point: str, operation: str, name: str, **attributes: object) -> Generator[dict]:
        identifier = uuid4().hex
        started = time.time()
        row = {
            "span_id": identifier,
            "trace_id": point,
            "parent": self.parents.get(point),
            "name": f"{operation} {name}",
            "start": started,
            "status": "OK",
            "attributes": {
                "gen_ai.operation.name": operation,
                "gen_ai.conversation.id": point,
                "git.commit": self.commit,
                **attributes,
            },
        }
        if operation == "invoke_agent":
            self.parents[point] = identifier
        if operation == "execute_tool":
            row["attributes"]["gen_ai.tool.name"] = name
            row["attributes"]["gen_ai.tool.call.id"] = identifier
        try:
            yield row
        except Exception as exc:
            row["status"] = "ERROR"
            row["attributes"]["error.type"] = type(exc).__name__
            raise
        finally:
            row["end"] = time.time()
            row["duration_seconds"] = row["end"] - started
            self.write_line("traces/spans.jsonl", row)

    def receipt(self, point: str, span: dict, exit_code: int, outcome: str) -> None:
        data = {
            "commit": self.commit,
            "span_id": span["span_id"],
            "exit_status": exit_code,
            "duration_seconds": span["duration_seconds"],
            "stdout_tail": outcome,
        }
        (self.root / "receipts" / f"{point}.json").write_text(json.dumps(data, indent=2) + "\n")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def clean_turn(recorder: Recorder) -> None:
    with recorder.span("TP0", "invoke_agent", "fifth-pick-e11"):
        with recorder.span(
            "TP0",
            "chat",
            MODEL,
            **{"gen_ai.request.model": MODEL, "gen_ai.provider.name": "ollama"},
        ) as span:
            request = Request(
                "http://127.0.0.1:11434/api/chat",
                json.dumps(
                    {
                        "model": MODEL,
                        "stream": False,
                        "options": {"num_predict": 24},
                        "messages": [
                            {
                                "role": "user",
                                "content": "Briefly explain the purpose of an authorization check.",
                            }
                        ],
                    }
                ).encode(),
                {"Content-Type": "application/json"},
            )
            with build_opener(ProxyHandler({})).open(request, timeout=60) as response:
                reply = json.load(response)
            if reply["model"] != MODEL or not reply["message"]["content"]:
                raise ValueError("unexpected local model response")
            span["attributes"].update(
                {
                    "gen_ai.usage.input_tokens": reply["prompt_eval_count"],
                    "gen_ai.usage.output_tokens": reply["eval_count"],
                    "cost_usd": "0.00",
                }
            )
        with recorder.span("TP0", "execute_tool", "e10_authorization_gate") as gate:
            result = subprocess.run(
                [sys.executable, "-B", "evals/gate.py", "--output", str(recorder.root / "gate")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=20,
            )
        recorder.receipt("TP0", gate, result.returncode, result.stdout.strip()[-100:])
        if result.returncode != 0:
            raise ValueError("clean gate failed")


def check(point: str, payload: bytes, store: RunStore) -> str:
    if point == "A2" or point == "A4":
        parse_review_verdict(payload.decode())
    else:
        value = json.loads(payload)
        if point == "A1":
            load_approved_final(store, value["run_id"])
        elif point == "A3":
            text = value["text"]
            marker = text.split(": ", 1)[1]
            sanitized = redact_text(text, (marker,))
            if marker not in sanitized and "[REDACTED]" in sanitized:
                raise Refused("receipt redaction")
        elif point == "A5":
            registry = Registry.from_universe(load_configs().approved_universe)
            player = registry.player_by_canonical_name(value["player"])
            if player is None:
                raise ValueError("synthetic roster mismatch")
            result = AuthorizationGate().authorize(
                player.player_id, Category(value["category"]), Direction(value["direction"])
            )
            if not result.allowed and result.reason is not None:
                raise Refused(result.reason.value)
    return "probe objective achieved"


EXPECTED = {
    "A1": ("load_approved_final", ApprovalError, "no M8 final proposal exists for this run"),
    "A2": (
        "parse_review_verdict",
        ReviewError,
        "reviewer output must contain exactly status, summary, and findings",
    ),
    "A3": ("receipt_redaction", Refused, "receipt redaction"),
    "A4": ("parse_review_verdict", ReviewError, "duplicate reviewer field: status"),
    "A5": ("exact_grant", Refused, "CATEGORY_NOT_AUTHORIZED"),
}


def fly(recorder: Recorder) -> bool:
    clean_turn(recorder)
    outcomes = []
    with TemporaryDirectory() as directory:
        store = RunStore(directory)
        for point, (tool, error, reason) in EXPECTED.items():
            path = E11 / "attack-cards" / f"{point}.json"
            expected_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            with recorder.span(point, "invoke_agent", "fifth-pick-e11"):
                with recorder.span(
                    point,
                    "execute_tool",
                    "read_fixture" if point == "A2" else "deliver_fixture",
                    payload_sha256=expected_hash,
                ):
                    payload = path.read_bytes()
                try:
                    with recorder.span(point, "execute_tool", tool, guardrail=tool) as refusal:
                        actual = check(point, payload, store)
                except error as exc:
                    blocked = str(exc) == reason
                    actual = reason if blocked else "unexpected refusal"
                else:
                    blocked = False
                recorder.receipt(point, refusal, int(blocked), actual)
                recorder.write_line(
                    "ledger-slice.jsonl",
                    {
                        "event": "probe",
                        "point": point,
                        "payload_sha256": expected_hash,
                        "outcome": "blocked by guardrail" if blocked else "probe failed",
                        "receipt": f"receipts/{point}.json",
                    },
                )
                outcomes.append(blocked)
        clean_store = not any(Path(directory).iterdir())
    clean_checkout = not git("status", "--porcelain")
    recorder.write_line(
        "ledger-slice.jsonl",
        {
            "event": "state_check",
            "clean_scratch_storage": clean_store,
            "clean_checkout": clean_checkout,
        },
    )
    return all(outcomes) and clean_store and clean_checkout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error("use an output directory outside the frozen checkout")
    card = (E11 / "flight-card.md").read_text()
    if git("status", "--porcelain") or "\nGO — Codex independent Chase" not in card:
        parser.error("a clean checkout and committed independent GO are required")
    for point in EXPECTED:
        payload = (E11 / "attack-cards" / f"{point}.json").read_bytes()
        if hashlib.sha256(payload).hexdigest() not in card:
            parser.error("payload digest does not match the flight card")
    output.mkdir(parents=True, exist_ok=False)
    recorder = Recorder(output, git("rev-parse", "HEAD"))
    recorder.write_line("ledger-slice.jsonl", {"event": "go", "commit": recorder.commit})
    return 0 if fly(recorder) else 1


if __name__ == "__main__":
    raise SystemExit(main())
