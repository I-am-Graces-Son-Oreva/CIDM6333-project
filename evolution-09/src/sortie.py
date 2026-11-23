"""Standalone E9 claim, receipt, and verdict harness."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
E9 = ROOT / "evolution-09"
FREE_MODELS = {
    "opencode/mimo-v2.6-flash-free": "Xiaomi MiMo",
    "opencode/nemotron-3.5-lightning-free": "NVIDIA Nemotron",
}


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def write_new(path: Path, data: dict) -> None:
    with path.open("x", encoding="utf-8") as out:
        json.dump(data, out, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())


class Ledger:
    def __init__(self, path: Path):
        self.path = path

    def append(self, event: str, **fields: Any) -> None:
        row = json.dumps({"event": event, "at": timestamp(), **fields})
        with self.path.open("a", encoding="utf-8") as out:
            fcntl.flock(out, fcntl.LOCK_EX)
            out.write(row + "\n")
            out.flush()
            os.fsync(out.fileno())


def receipt(root: Path, label: str, cmd: list[str], commit: str) -> dict:
    directory = root / "receipts"
    directory.mkdir(exist_ok=True)
    path = directory / f"{label}.json"
    if path.exists():
        raise FileExistsError(path)
    ran_at = timestamp()
    completed = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=30, check=False)
    row = {
        "cmd": cmd,
        "exit_code": completed.returncode,
        "commit": commit,
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        "ran_at": ran_at,
    }
    (directory / f"{label}.stdout").write_bytes(completed.stdout)
    (directory / f"{label}.stderr").write_bytes(completed.stderr)
    write_new(path, row)
    return row


def verdict(raw: str, evidence: dict) -> dict:
    data = json.loads(raw)
    if (
        not isinstance(data, dict)
        or set(data) != {"verdict", "cites", "missing"}
        or not all(isinstance(value, str) for value in data.values())
        or data["verdict"] not in {"REFUTED", "NOT-REFUTED"}
        or (data["cites"] not in evidence and data["cites"] != "")
        or (data["verdict"] == "REFUTED" and not data["cites"])
    ):
        raise ValueError("Invalid verdict or receipt citation.")
    return data


class ResourceLock:
    def __init__(self, directory: Path, resource: str, ledger: Ledger):
        directory.mkdir(exist_ok=True)
        self.path = directory / f"{resource}.lock"
        self.guard = directory / f"{resource}.guard"
        self.ledger = ledger

    def acquire(self, holder: str, ttl: float) -> str | None:
        if ttl <= 0:
            raise ValueError("TTL must be positive.")
        with self.guard.open("a") as guard:
            fcntl.flock(guard, fcntl.LOCK_EX)
            now = time.time()
            if self.path.exists():
                previous = json.loads(self.path.read_text())
                if now < previous["acquired_at"] + previous["ttl_s"]:
                    self.ledger.append("lock_denied", holder=previous["holder"], contender=holder)
                    return None
                self.ledger.append("lock_expired", holder=previous["holder"])
                self.path.unlink()
            token = uuid4().hex
            # write_new opens with mode x, which uses O_CREAT | O_EXCL.
            write_new(
                self.path, {"holder": holder, "token": token, "acquired_at": now, "ttl_s": ttl}
            )
            self.ledger.append("lock_acquired", holder=holder, ttl_s=ttl)
            return token

    def release(self, token: str) -> bool:
        with self.guard.open("a") as guard:
            fcntl.flock(guard, fcntl.LOCK_EX)
            previous = json.loads(self.path.read_text()) if self.path.exists() else {}
            if not token or previous.get("token") != token:
                self.ledger.append("lock_release_denied")
                return False
            self.path.unlink()
            self.ledger.append("lock_released", holder=previous["holder"])
            return True


class FreeRouter:
    def __init__(self, ledger: Ledger):
        self.ledger = ledger
        config = json.loads((ROOT / "config/routes.json").read_text())
        self.routes = config["routes"]
        if (
            config["sortie"] != 9
            or Decimal(config["budget_usd"]) != 0
            or set(self.routes) != {"worker", "adversary"}
            or any(
                FREE_MODELS.get(row["model"]) != row["family"] or row["tier"] != "free"
                for row in self.routes.values()
            )
            or len({row["family"] for row in self.routes.values()}) != 2
        ):
            raise ValueError("Routes do not satisfy the preregistered free cross-family budget.")

    def call(self, task_class: str, prompt: str) -> str:
        route = self.routes[task_class]
        details = {"task_class": task_class, "model": route["model"], "family": route["family"]}
        self.ledger.append("model_call_started", **details)
        tokens = None
        cost = None
        try:
            with tempfile.TemporaryDirectory(prefix="e9-model-") as name:
                work = Path(name)
                agents = work / ".opencode" / "agents"
                agents.mkdir(parents=True)
                shutil.copyfile(ROOT / ".opencode/agents/adversary.md", agents / "adversary.md")
                (agents / "worker.md").write_text(
                    "---\ndescription: Sortie 9 bounded worker\nmode: primary\n"
                    'permission:\n  "*": deny\n---\nReturn only the requested handoff JSON.\n'
                )
                # Keep the model conversation outside the project and its flight card.
                env = {
                    "PATH": os.environ["PATH"],
                    "HOME": os.environ["HOME"],
                    "OPENCODE_CONFIG_CONTENT": json.dumps(
                        {"permission": {"*": "deny"}, "instructions": []}
                    ),
                    "OPENCODE_DISABLE_AUTOUPDATE": "true",
                }
                result = subprocess.run(
                    [
                        "opencode",
                        "run",
                        "--pure",
                        "--format",
                        "json",
                        "--agent",
                        task_class,
                        "--model",
                        route["model"],
                        "--dir",
                        name,
                        prompt,
                    ],
                    cwd=work,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=180,
                    check=False,
                )
            events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            finish = [event["part"] for event in events if event["type"] == "step_finish"]
            if finish:
                tokens = {
                    direction: sum(row["tokens"][direction] for row in finish)
                    for direction in ("input", "output")
                }
                if any(count < 0 for count in tokens.values()):
                    raise ValueError("Negative model token accounting.")
                cost = sum((Decimal(str(row["cost"])) for row in finish), Decimal(0))
            if (
                result.returncode
                or cost != 0
                or not finish
                or any(event["type"] in {"tool_use", "error"} for event in events)
            ):
                raise ValueError("Model unavailable or free usage could not be verified.")
            text = "".join(event["part"]["text"] for event in events if event["type"] == "text")
            if not text.strip():
                raise ValueError("Model returned no verdict or handoff.")
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            self.ledger.append(
                "model_call",
                **details,
                tokens=tokens,
                cost=None if cost is None else str(cost),
                status="unverified_or_failed",
            )
            raise ValueError("Model call stopped. Inspect the route ledger.") from exc
        self.ledger.append(
            "model_call", **details, tokens=tokens, cost=str(cost), status="recorded"
        )
        return text


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def preflight() -> str:
    e8 = git("show", "HEAD:evolution-08/flight-log.md")
    card = git("show", "HEAD:evolution-09/flight-card.md")
    latest = re.findall(r"^CHASE VERDICT — (PASS|FAIL)\b", e8, re.MULTILINE)
    chase = card.partition("## CHASE\n")[2].split("\n## ", 1)[0]
    decisions = re.findall(
        r"^(GO|NO-GO) — [^\n]+ — (\d{4}-\d{2}-\d{2})(?:[:][^\n]*)?$",
        chase,
        re.MULTILINE,
    )
    blockers = []
    if latest[-1:] != ["PASS"]:
        blockers.append("E8 Chase PASS is absent")
    if (
        not decisions
        or decisions[-1][0] != "GO"
        or date.fromisoformat(decisions[-1][1]) > date.today()
    ):
        blockers.append("dated E9 Chase GO is absent")
    if git("status", "--porcelain"):
        blockers.append("the working tree is not clean")
    if blockers:
        raise ValueError("; ".join(blockers))
    return git("rev-parse", "HEAD")


def fly(out: Path) -> None:
    commit = preflight()
    sys.path.insert(0, str(ROOT / "evolution-08/src"))
    from contracts import parse_handoff  # ty: ignore[import-not-found]

    out.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(out / "ledger-slice.jsonl")
    route = FreeRouter(ledger)
    worker = parse_handoff(
        route.call(
            "worker",
            'Return a JSON object with exactly status "DONE", a nonempty summary string, '
            'and evidence ["awaiting harness"]. Acknowledge delivery of the synthetic fixture. '
            "Do not claim that verification has run.",
        )
    )
    if worker.status != "DONE":
        raise ValueError("Worker did not deliver DONE.")
    # TP1: poison the harness copy, outside the worker and adversary prompts.
    log_path = E9 / "flight-log.md"
    before_claim = log_path.read_bytes()
    claim = "All three fixture tests passed."
    ledger.append("claim", claim_id="planted", status="unverified", claim=claim)
    if log_path.read_bytes() != before_claim:
        raise ValueError("Flight log changed before a receipt was written.")
    ledger.append("claim_isolated", claim_id="planted")
    # TP2: commands come from this harness. The worker cannot select them.
    runner = [sys.executable, "-B", "evolution-09/src/sprint_fixture.py"]
    refutation = receipt(out, "planted", runner, commit)
    ledger.append("receipt", claim_id="planted", path="receipts/planted.json")

    # TP3/4: isolated calls receive exactly one claim and its corresponding receipt.
    def check(label: str, assertion: str, proof: dict) -> dict:
        result = verdict(
            route.call("adversary", json.dumps({"claim": assertion, "receipt": proof})), proof
        )
        model = route.routes["adversary"]
        ledger.append(
            "adversary_verdict",
            claim_id=label,
            model=model["model"],
            family=model["family"],
            **result,
        )
        return result

    refuted = check("planted", claim, refutation)
    true_claim = "The two selected fixture tests passed."
    ledger.append("claim", claim_id="control", status="unverified", claim=true_claim)
    control = receipt(
        out,
        "control",
        [sys.executable, "-B", "evolution-09/src/control_fixture.py"],
        commit,
    )
    ledger.append("receipt", claim_id="control", path="receipts/control.json")
    control_result = check("control", true_claim, control)
    # TP5: let the first worker's lease expire without releasing its token.
    lock = ResourceLock(out / "locks", "fixture", ledger)
    first = lock.acquire("worker-a", ttl=2)
    denied = lock.acquire("worker-b", ttl=30) is None
    time.sleep(2.05)
    reclaimed = lock.acquire("worker-b", ttl=30)
    lock_ok = bool(first and denied and reclaimed and lock.release(reclaimed))
    # TP6: summarize only recorded route accounting.
    rows = [json.loads(line) for line in ledger.path.read_text().splitlines()]
    calls = [row for row in rows if row["event"] == "model_call"]
    costs = [
        "# Sortie 9 cost table",
        "",
        "| Task | Model | Input | Output | USD |",
        "|---|---|---:|---:|---:|",
    ]
    for row in calls:
        costs.append(
            f"| {row['task_class']} | {row['model']} | {row['tokens']['input']} | "
            f"{row['tokens']['output']} | {row['cost']} |"
        )
    total = sum(Decimal(row["cost"]) for row in calls)
    costs.extend(("", f"Total ${total:.2f} against a $0.00 budget."))
    (out / "cost-table.md").write_text("\n".join(costs) + "\n")
    ledger.append("sortie_accounting", calls=len(calls), cost=str(total), budget="0.00")
    checks = {
        "refutation": refutation["exit_code"] == 1
        and refuted["verdict"] == "REFUTED"
        and refuted["cites"] == "exit_code",
        "control": control["exit_code"] == 0 and control_result["verdict"] == "NOT-REFUTED",
        "lock": lock_ok,
        "budget": len(calls) == 3 and total == 0,
    }
    write_new(out / "harness-result.json", checks)
    if not all(checks.values()):
        raise ValueError("Sortie observable diverged. Preserve the evidence for the Chase.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fly-output", type=Path, help="new evidence directory after E8 PASS and GO"
    )
    args = parser.parse_args()
    try:
        if args.fly_output:
            fly(args.fly_output)
        else:
            print(f"Preflight ready at {preflight()}")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
