import json
import os
from pathlib import Path

from src.e7_memory.conditions import (
    CONTROL_AGENT_ANSWER,
    LEDGER_SCHEMA,
    MODEL,
    OFFICIAL_LEDGER,
    OFFICIAL_STORE,
    ON_THRESHOLD,
    QUESTION_ABSENT,
    QUESTION_CONTROL,
    QUESTION_RECALL,
    build_off_sandbox,
    build_on_sandbox,
    run_wrapper,
    sha256_file,
    sha256_text,
    snapshot,
    tp5_isolation,
    verify_on_event,
)
from src.e7_memory.fixture import FIXTURE_PATH, claim_text, load_fixture
from src.e7_memory.preflight import run_preflight

REPO_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
}
EXCLUDED_PATHS = {
    REPO_ROOT / "evolution-07" / "fixtures",
    REPO_ROOT / "evolution-07" / "evidence",
}


def repo_text_files():
    for root, dirs, files in os.walk(REPO_ROOT):
        root_path = Path(root)
        dirs[:] = [
            name for name in dirs
            if name not in EXCLUDED_DIR_NAMES
        ]
        if root_path in EXCLUDED_PATHS:
            dirs[:] = []
            continue
        for name in files:
            yield root_path / name


def test_fixture_claim_absent_from_ordinary_sources():
    claim = claim_text()
    offenders = []

    for path in repo_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if claim in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []
    assert claim in FIXTURE_PATH.read_text(encoding="utf-8")


def test_off_sandbox_excludes_answer_and_sources(tmp_path):
    sandbox = tmp_path / "off"
    manifest = build_off_sandbox(sandbox)

    assert manifest["claim_present_in_sandbox"] is False
    assert manifest["model"] == MODEL
    assert manifest["question_recall"] == QUESTION_RECALL
    assert manifest["question_control"] == QUESTION_CONTROL
    assert manifest["control_expected_agent_answer"] == CONTROL_AGENT_ANSWER

    names = {
        path.name for path in sandbox.rglob("*") if path.is_file()
    }
    assert "question-recall.txt" in names
    assert "question-control.txt" in names
    assert "memory.jsonl" not in names
    assert "memory-ledger.jsonl" not in names
    assert "flight-log.md" not in names
    assert "handoff.md" not in names

    claim = claim_text()
    for path in sandbox.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert claim not in text
        assert "PASS after corrective Session B2" not in text


def test_on_sandbox_retriever_event_matches_fixture(tmp_path):
    sandbox = tmp_path / "on"
    private = tmp_path / "private"
    manifest = build_on_sandbox(sandbox, private)
    fixture = load_fixture()

    result = run_wrapper(sandbox, QUESTION_RECALL)

    assert result.returncode == 0
    assert fixture["id"] in result.stdout
    assert fixture["source"] in result.stdout
    assert fixture["expected_answer"] in result.stdout
    assert "Score:" in result.stdout

    assert manifest["claim_present_in_sandbox"] is False
    assert manifest["fixture_store_outside_sandbox"] is True
    assert manifest["retrieval_threshold"] == ON_THRESHOLD
    assert not (sandbox / "fixture-memory.jsonl").exists()

    ledger = private / "fixture-memory-ledger.jsonl"
    matches, event = verify_on_event(
        ledger,
        fixture["id"],
        fixture["source"],
        QUESTION_RECALL,
    )

    assert matches is True
    assert event["schema"] == LEDGER_SCHEMA
    assert event["top_id"] == fixture["id"]
    assert event["top_source"] == fixture["source"]
    assert event["top_score"] > ON_THRESHOLD
    assert event["results"][0]["source"] == fixture["source"]


def test_retriever_control_and_absent_are_not_answers(tmp_path):
    sandbox = tmp_path / "on"
    private = tmp_path / "private"
    build_on_sandbox(sandbox, private)

    control = run_wrapper(sandbox, QUESTION_CONTROL)
    absent = run_wrapper(sandbox, QUESTION_ABSENT)

    assert "Not in memory." in control.stdout
    assert "Not in memory." in absent.stdout

    off_manifest = build_off_sandbox(tmp_path / "off")
    on_manifest = build_on_sandbox(tmp_path / "on2", tmp_path / "private2")

    assert off_manifest["control_expected_agent_answer"] == "4"
    assert on_manifest["control_expected_agent_answer"] == "4"
    assert CONTROL_AGENT_ANSWER == "4"
    assert off_manifest["model"] == on_manifest["model"] == MODEL
    assert (
        off_manifest["question_recall"]
        == on_manifest["question_recall"]
        == QUESTION_RECALL
    )


def test_tp5_temp_eviction_does_not_modify_official_files(tmp_path):
    official_before = snapshot([OFFICIAL_STORE, OFFICIAL_LEDGER])

    data = tp5_isolation(tmp_path / "tp5-isolation.json")

    official_after = snapshot([OFFICIAL_STORE, OFFICIAL_LEDGER])

    assert official_before == official_after
    assert data["official_unchanged"] is True
    assert data["temp_store_changed"] is True
    assert data["temp_ledger_changed"] is True
    assert data["recall_returns_not_in_memory"] is True
    assert any(
        event.get("id") == "m-0003"
        for event in data["eviction_events"]
    )
    assert "m-0003" in data["temp_store_before_ids"]
    assert "m-0003" not in data["temp_store_after_ids"]
    assert (tmp_path / "tp5-isolation.json").exists()


def test_historical_ledger_events_are_preserved_and_prototype_schema():
    baseline = json.loads(
        (
            REPO_ROOT
            / "evolution-07"
            / "fixtures"
            / "historical-baseline.json"
        ).read_text(encoding="utf-8")
    )

    assert sha256_file(OFFICIAL_STORE) == baseline["memory_jsonl_sha256"]

    lines = OFFICIAL_LEDGER.read_text(encoding="utf-8").splitlines()
    count = baseline["historical_ledger_event_count"]
    prefix = "\n".join(lines[:count]) + "\n"
    assert sha256_text(prefix) == baseline["memory_ledger_prefix_sha256"]

    historical = [json.loads(line) for line in lines[:count]]
    assert len(historical) == count
    for event in historical:
        assert "schema" not in event
    assert any(
        event["event"] == "recall"
        and "id" in event
        and "score" in event
        for event in historical
    )

    adr = (
        REPO_ROOT / "evolution-07" / "ADR-2.md"
    ).read_text(encoding="utf-8").lower()
    assert "prototype schema" in adr
    assert "not be represented as official sortie evidence" in adr


def test_preflight_evidence_records_isolation_without_plaintext(tmp_path):
    data, tp5 = run_preflight(tmp_path)

    assert data["isolation"]["off_claim_present"] is False
    assert data["isolation"]["on_claim_present_in_sandbox"] is False
    assert data["isolation"]["on_fixture_store_outside_sandbox"] is True
    assert data["retriever"]["recall_event_matches_fixture"] is True
    assert data["same_model"] is True
    assert data["same_question"] is True
    assert tp5["official_unchanged"] is True
    assert tp5["recall_returns_not_in_memory"] is True

    isolation_path = tmp_path / "preflight-isolation.json"
    tp5_path = tmp_path / "preflight-tp5-isolation.json"
    assert isolation_path.exists()
    assert tp5_path.exists()

    combined = (
        isolation_path.read_text(encoding="utf-8")
        + tp5_path.read_text(encoding="utf-8")
    )
    assert claim_text() not in combined
