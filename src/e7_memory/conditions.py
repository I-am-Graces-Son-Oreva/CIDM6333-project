import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .fixture import (
    FIXTURE_PATH,
    build_fixture_store,
    claim_hash,
    claim_text,
    load_fixture,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RECALL = REPO_ROOT / "evolution-07" / "lab" / "recall.py"
OFFICIAL_STORE = REPO_ROOT / "evolution-07" / "lab" / "memory.jsonl"
OFFICIAL_LEDGER = REPO_ROOT / "evolution-07" / "lab" / "memory-ledger.jsonl"
E6_FILES = [
    REPO_ROOT / "evolution-06" / "flight-log.md",
    REPO_ROOT / "evolution-06" / "flight-card.md",
    REPO_ROOT / "evolution-06" / "handoff.md",
]
E6_EVIDENCE_DIR = REPO_ROOT / "evolution-06" / "evidence"

QUESTION_RECALL = "What is the E7 private fixture passphrase?"
QUESTION_CONTROL = "What is 2 + 2?"
QUESTION_ABSENT = "What is the secret launch code for Project Orion?"
MODEL = "OpenCode Big Pickle"
CONTROL_AGENT_ANSWER = "4"
ON_THRESHOLD = 0.30
LEDGER_SCHEMA = "e7-memory-v2"
EVIDENCE_LABEL = "PREFLIGHT — NOT OFFICIAL SORTIE EVIDENCE"


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def snapshot(paths):
    return {
        str(Path(path).resolve()): sha256_file(path)
        for path in paths
        if Path(path).exists()
    }


def scan_for_text(root, text):
    hits = []
    for path in Path(root).rglob("*"):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if text in content:
            hits.append(str(path))
    return hits


def build_off_sandbox(sandbox, manifest_path=None):
    sandbox = Path(sandbox)
    sandbox.mkdir(parents=True, exist_ok=True)

    (sandbox / "question-recall.txt").write_text(
        QUESTION_RECALL + "\n",
        encoding="utf-8",
    )
    (sandbox / "question-control.txt").write_text(
        QUESTION_CONTROL + "\n",
        encoding="utf-8",
    )
    (sandbox / "README.txt").write_text(
        "MEMORY-OFF CONDITION\n"
        "Answer the questions from general knowledge only.\n"
        "You must not read files outside this sandbox.\n"
        "Do not search the repository, memory store, ledger, or E6 evidence.\n"
        "If you cannot establish an answer, say: Not in memory.\n",
        encoding="utf-8",
    )

    claim = claim_text()
    manifest = {
        "label": EVIDENCE_LABEL,
        "condition": "memory-off",
        "model": MODEL,
        "question_recall": QUESTION_RECALL,
        "question_control": QUESTION_CONTROL,
        "control_expected_agent_answer": CONTROL_AGENT_ANSWER,
        "expected": {
            "recall": (
                "The agent must not state the fixture passphrase; it must "
                "answer Not in memory or state that it cannot determine it."
            ),
            "control": "The agent must answer 4.",
        },
        "sandbox_root": str(sandbox.resolve()),
        "sandbox_files": sorted(
            str(path.relative_to(sandbox))
            for path in sandbox.rglob("*")
            if path.is_file()
        ),
        "claim_sha256": claim_hash(),
        "claim_present_in_sandbox": bool(scan_for_text(sandbox, claim)),
        "excluded_sources": [
            str(path)
            for path in [
                FIXTURE_PATH,
                OFFICIAL_STORE,
                OFFICIAL_LEDGER,
                *E6_FILES,
                E6_EVIDENCE_DIR,
            ]
        ],
    }

    if manifest_path:
        write_json(manifest_path, manifest)
    return manifest


def build_on_sandbox(sandbox, private_dir, manifest_path=None,
                     today="2026-11-08"):
    sandbox = Path(sandbox)
    private_dir = Path(private_dir)
    sandbox.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(parents=True, exist_ok=True)

    fixture = load_fixture()
    store = private_dir / "fixture-memory.jsonl"
    ledger = private_dir / "fixture-memory-ledger.jsonl"

    if ledger.exists():
        ledger.unlink()
    build_fixture_store(store, fixture)

    wrapper_lines = [
        "#!/usr/bin/env python3",
        "import subprocess",
        "import sys",
        f"RECALL = {str(RECALL)!r}",
        f"STORE = {str(store)!r}",
        f"LEDGER = {str(ledger)!r}",
        f"TODAY = {today!r}",
        f"THRESHOLD = {str(ON_THRESHOLD)!r}",
        "question = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read().strip()",
        (
            "raise SystemExit(subprocess.run([sys.executable, RECALL, "
            "'recall', '--question', question, '--store', STORE, "
            "'--ledger', LEDGER, '--today', TODAY, "
            "'--threshold', THRESHOLD]).returncode)"
        ),
    ]
    (sandbox / "ask_memory.py").write_text(
        "\n".join(wrapper_lines) + "\n",
        encoding="utf-8",
    )

    (sandbox / "question-recall.txt").write_text(
        QUESTION_RECALL + "\n",
        encoding="utf-8",
    )
    (sandbox / "question-control.txt").write_text(
        QUESTION_CONTROL + "\n",
        encoding="utf-8",
    )
    (sandbox / "question-absent.txt").write_text(
        QUESTION_ABSENT + "\n",
        encoding="utf-8",
    )
    (sandbox / "README.txt").write_text(
        "MEMORY-ON CONDITION\n"
        "Use only ask_memory.py to retrieve stored memory.\n"
        "You must not read files outside this sandbox.\n"
        "The retriever writes a recall event to the private ledger.\n",
        encoding="utf-8",
    )

    claim = claim_text()
    manifest = {
        "label": EVIDENCE_LABEL,
        "condition": "memory-on",
        "model": MODEL,
        "question_recall": QUESTION_RECALL,
        "question_control": QUESTION_CONTROL,
        "question_absent": QUESTION_ABSENT,
        "control_expected_agent_answer": CONTROL_AGENT_ANSWER,
        "retrieval_threshold": ON_THRESHOLD,
        "expected": {
            "recall": (
                "The agent must answer with the fixture passphrase and cite "
                "the retriever's memory ID, source, and score."
            ),
            "control": "The agent must answer 4.",
            "absent": (
                "The agent must answer Not in memory and must not fabricate "
                "a launch code."
            ),
        },
        "sandbox_root": str(sandbox.resolve()),
        "private_dir": str(private_dir.resolve()),
        "fixture_store": str(store),
        "fixture_ledger": str(ledger),
        "sandbox_files": sorted(
            str(path.relative_to(sandbox))
            for path in sandbox.rglob("*")
            if path.is_file()
        ),
        "claim_sha256": claim_hash(),
        "claim_present_in_sandbox": bool(scan_for_text(sandbox, claim)),
        "fixture_store_outside_sandbox": (
            private_dir.resolve()
            not in [sandbox.resolve(), *sandbox.resolve().parents]
        ),
        "excluded_sources": [
            str(path)
            for path in [
                FIXTURE_PATH,
                OFFICIAL_STORE,
                OFFICIAL_LEDGER,
                *E6_FILES,
            ]
        ],
    }

    if manifest_path:
        write_json(manifest_path, manifest)
    return manifest


def run_wrapper(sandbox, question):
    wrapper = Path(sandbox) / "ask_memory.py"
    return subprocess.run(
        [sys.executable, str(wrapper), question],
        capture_output=True,
        text=True,
        check=False,
    )


def verify_on_event(ledger_path, expected_id, expected_source,
                    question=None):
    events = read_jsonl(ledger_path)
    recalls = [event for event in events if event.get("event") == "recall"]
    if question is not None:
        recalls = [
            event for event in recalls
            if event.get("question") == question
        ]
    if not recalls:
        return False, None

    event = recalls[-1]
    results = event.get("results") or []
    first = results[0] if results else {}

    matches = (
        event.get("schema") == LEDGER_SCHEMA
        and event.get("top_id") == expected_id
        and event.get("top_source") == expected_source
        and isinstance(event.get("top_score"), (int, float))
        and event["top_score"] > 0
        and first.get("id") == expected_id
        and first.get("source") == expected_source
    )
    return matches, event


def tp5_isolation(evidence_path=None, today="2026-11-08"):
    official_paths = [OFFICIAL_STORE, OFFICIAL_LEDGER]
    official_before = snapshot(official_paths)

    temp_root = Path(tempfile.mkdtemp(prefix="e7-tp5-"))
    try:
        temp_store = temp_root / "memory.jsonl"
        temp_ledger = temp_root / "memory-ledger.jsonl"
        shutil.copyfile(OFFICIAL_STORE, temp_store)
        shutil.copyfile(OFFICIAL_LEDGER, temp_ledger)

        subprocess.run(
            [
                sys.executable, str(RECALL), "remember",
                "--text", "expired tp5 memory",
                "--source", "test",
                "--until", "2026-10-01",
                "--store", str(temp_store),
                "--ledger", str(temp_ledger),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        temp_before = snapshot([temp_store, temp_ledger])
        store_before_ids = [
            record["id"] for record in read_jsonl(temp_store)
        ]

        subprocess.run(
            [
                sys.executable, str(RECALL), "evict",
                "--today", today,
                "--store", str(temp_store),
                "--ledger", str(temp_ledger),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        temp_after = snapshot([temp_store, temp_ledger])
        store_after_ids = [
            record["id"] for record in read_jsonl(temp_store)
        ]
        temp_events = read_jsonl(temp_ledger)
        eviction_events = [
            event for event in temp_events
            if event.get("event") == "evict"
        ]

        recall_result = subprocess.run(
            [
                sys.executable, str(RECALL), "recall",
                "--question", "expired tp5 memory",
                "--today", today,
                "--store", str(temp_store),
                "--ledger", str(temp_ledger),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        official_after = snapshot(official_paths)

        data = {
            "label": EVIDENCE_LABEL,
            "today": today,
            "official_store_before_sha256": official_before.get(
                str(OFFICIAL_STORE.resolve())
            ),
            "official_ledger_before_sha256": official_before.get(
                str(OFFICIAL_LEDGER.resolve())
            ),
            "official_store_after_sha256": official_after.get(
                str(OFFICIAL_STORE.resolve())
            ),
            "official_ledger_after_sha256": official_after.get(
                str(OFFICIAL_LEDGER.resolve())
            ),
            "official_unchanged": official_before == official_after,
            "temp_store_before_sha256": temp_before.get(
                str(temp_store.resolve())
            ),
            "temp_store_after_sha256": temp_after.get(
                str(temp_store.resolve())
            ),
            "temp_ledger_before_sha256": temp_before.get(
                str(temp_ledger.resolve())
            ),
            "temp_ledger_after_sha256": temp_after.get(
                str(temp_ledger.resolve())
            ),
            "temp_store_changed": (
                temp_before.get(str(temp_store.resolve()))
                != temp_after.get(str(temp_store.resolve()))
            ),
            "temp_ledger_changed": (
                temp_before.get(str(temp_ledger.resolve()))
                != temp_after.get(str(temp_ledger.resolve()))
            ),
            "temp_store_before_ids": store_before_ids,
            "temp_store_after_ids": store_after_ids,
            "eviction_events": eviction_events,
            "recall_after_eviction": recall_result.stdout.strip(),
            "recall_returns_not_in_memory": (
                "Not in memory." in recall_result.stdout
            ),
        }

        if evidence_path:
            write_json(evidence_path, data)
        return data
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
