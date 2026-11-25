"""Run the preregistered E6/E7 local-model controls."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from src.e6_context.context_engine import RuntimeLedger, compact, record_turn_budget

MODEL = "llama3.2:3b"
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "evolution-07/lab/recall.py"


def ask(messages: list[dict[str, str]]) -> dict:
    data = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "format": {"type": "object", "properties": {"answer": {"type": "string"}},
                   "required": ["answer"]},
        "options": {"temperature": 0, "num_predict": 48},
    }
    request = Request(
        "http://127.0.0.1:11434/api/chat",
        json.dumps(data).encode(), {"Content-Type": "application/json"},
    )
    with build_opener(ProxyHandler({})).open(request, timeout=90) as response:
        result = json.load(response)
    if result["model"] != MODEL or result["done_reason"] != "stop":
        raise ValueError("model response did not finish normally")
    return {
        "answer": json.loads(result["message"]["content"])["answer"],
        "input": result["prompt_eval_count"],
        "output": result["eval_count"],
    }


def item(text: str) -> dict[str, str]:
    return {"role": "user", "content": text}


def run(output: Path) -> None:
    card = Path(__file__).with_name("flight-card.md").read_text()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)
    if "\nGO — Codex independent Chase" not in card or status:
        raise ValueError("committed GO and a clean checkout are required")
    output.mkdir()
    ledger = RuntimeLedger(output / "run.jsonl")
    action = "VERIFY_AMBER"
    session = uuid4().hex
    disposable = "The synthetic museum opened on Monday. " * 125
    keep = f"The exact next action is {action}. Return that exact action when asked."
    before = ask([item(disposable), item(f"{keep} Acknowledge with READY as your answer.")])
    meter = record_turn_budget(ledger, session, 1, before["input"], before["output"])
    retained = compact([disposable], ledger, meter["total"], keep=[keep])
    after = ask([item(retained), item("Return the exact next action.")])
    record_turn_budget(ledger, session, 2, after["input"], after["output"])
    continued = before["answer"] == "READY" and after["answer"] == action and (
        after["input"] < before["input"]
    )
    ledger.append(dict(event="continuation", session=session, before=before, after=after,
                       passed=continued))

    spec = importlib.util.spec_from_file_location("e7_recall", SOURCE)
    assert spec is not None and spec.loader is not None
    recall = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recall)
    store = output / "scratch-store.jsonl"
    memory_ledger = output / "recall.jsonl"
    code = uuid4().hex[:10].upper()
    recall.remember(
        f"museum access identifier: {code}", "synthetic museum fixture", "2026-11-30",
        store_path=store, ledger_path=memory_ledger,
    )
    question = "What is the museum access identifier?"
    outcomes = []
    for stage, query, expect in (
        ("off", question, "UNKNOWN"),
        ("on", question, code),
        ("absent", "What is the orchid greenhouse temperature?", "UNKNOWN"),
        ("evicted", question, "UNKNOWN"),
    ):
        if stage == "evicted":
            recall.evict("2026-12-01", store_path=store, ledger_path=memory_ledger)
        hits = [] if stage == "off" else recall.query(
            query, threshold=0.15, today="2026-11-24" if stage != "evicted" else "2026-12-01",
            store_path=store, ledger_path=memory_ledger,
        )["results"]
        context = "\n".join(row["text"] for row in hits) or "(empty)"
        answer = ask([item(
            "Return the exact identifier supported by these records, or UNKNOWN if unsupported. "
            f"Use the JSON answer field.\nRecords: {context}\nQuestion: {query}"
        )])
        passed = answer["answer"] == expect and bool(hits) == (stage == "on")
        ledger.append(dict(event="memory_answer", condition=stage, answer=answer,
                           memory_ids=[row["id"] for row in hits], expected=expect, passed=passed))
        outcomes.append(passed)
    store.unlink()
    if not continued or not all(outcomes):
        raise ValueError("one or more preregistered observables failed")


if __name__ == "__main__":
    run(Path(sys.argv[1]))
