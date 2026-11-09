import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

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
    SANDBOX_PROFILE,
    SERVICE_CONFIG,
    THIRD_REVIEW_LEAKED_PATHS,
    build_off_sandbox,
    build_on_sandbox,
    connection_probe,
    isolation_probes,
    opencode_config,
    probes_ok,
    run_wrapper,
    service_port,
    service_reachable,
    sha256_file,
    sha256_text,
    sidecar_path,
    snapshot,
    tp5_isolation,
    verify_on_event,
)
from src.e7_memory.capture import capture_evidence
from src.e7_memory.fixture import FIXTURE_PATH, claim_text, load_fixture
from src.e7_memory.preflight import run_preflight
from src.e7_memory.sandbox import probe, sandbox_available

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


def test_off_sandbox_denies_synthetic_private_artifact(tmp_path):
    private = tmp_path / "run" / "private"
    private.mkdir(parents=True)
    store = private / "fixture-memory.jsonl"
    store.write_text(
        json.dumps({"text": claim_text()}) + "\n",
        encoding="utf-8",
    )

    sandbox = tmp_path / "off"
    manifest = build_off_sandbox(sandbox, private_paths=[private])

    denied = {
        str(Path(path).resolve())
        for path in manifest["denied_private_artifacts"]
    }
    assert any(
        str(path) == str(store.resolve())
        or store.resolve().is_relative_to(path)
        for path in denied
    )

    result = probe(
        sandbox / SANDBOX_PROFILE,
        sandbox,
        "synthetic_private_store",
        ["/bin/cat", str(store)],
        "denied",
        redact=claim_text(),
    )
    assert result["denied"] is True
    assert result["leaked"] is False


def test_on_sandbox_denies_unrelated_private_artifact(tmp_path):
    unrelated = tmp_path / "other" / "private"
    unrelated.mkdir(parents=True)
    store = unrelated / "fixture-memory.jsonl"
    store.write_text(
        json.dumps({"text": claim_text()}) + "\n",
        encoding="utf-8",
    )

    sandbox = tmp_path / "on"
    private = tmp_path / "private"
    manifest = build_on_sandbox(
        sandbox,
        private,
        private_paths=[unrelated],
    )

    denied = {
        str(Path(path).resolve())
        for path in manifest["denied_private_artifacts"]
    }
    assert any(
        str(path) == str(store.resolve())
        or store.resolve().is_relative_to(path)
        for path in denied
    )

    result = probe(
        sandbox / SANDBOX_PROFILE,
        sandbox,
        "unrelated_private_store",
        ["/bin/cat", str(store)],
        "denied",
        redact=claim_text(),
    )
    assert result["denied"] is True
    assert result["leaked"] is False


def test_readable_file_fails_denied_probe(tmp_path):
    sandbox = tmp_path / "off"
    build_off_sandbox(sandbox)
    readable = sandbox / "question-recall.txt"

    result = probe(
        sandbox / SANDBOX_PROFILE,
        sandbox,
        "readable_control",
        ["/bin/cat", str(readable)],
        "denied",
        redact=claim_text(),
    )
    assert result["denied"] is False
    assert result["leaked"] is False
    assert probes_ok([result]) is False


def test_off_sandbox_denies_third_review_leaked_paths(tmp_path):
    sandbox = tmp_path / "off"
    build_off_sandbox(sandbox)
    claim = claim_text()

    for name, path in THIRD_REVIEW_LEAKED_PATHS:
        if not path.is_file():
            continue
        result = probe(
            sandbox / SANDBOX_PROFILE,
            sandbox,
            name,
            ["/bin/cat", str(path)],
            "denied",
            redact=claim,
        )
        assert result["denied"] is True, name
        assert result["leaked"] is False, name

    assert probes_ok(
        isolation_probes(sandbox, sandbox / SANDBOX_PROFILE)
    ) is True


@pytest.mark.skipif(
    not sandbox_available(),
    reason="sandbox-exec is not available on this host",
)
def test_off_cannot_reach_on_service_when_not_running(tmp_path):
    on = tmp_path / "on"
    private = tmp_path / "private"
    build_on_sandbox(on, private)

    off = tmp_path / "off"
    build_off_sandbox(
        off,
        private_paths=[on, private, sidecar_path(on)],
    )

    port = service_port(on)
    assert service_reachable(port) is False
    attempt = connection_probe(off / SANDBOX_PROFILE, off, port)
    assert attempt["reachable"] is False


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
    assert data["isolation"]["off_probes_ok"] is True
    assert data["isolation"]["on_probes_ok"] is True
    assert data["retriever"]["recall_event_matches_fixture"] is True
    assert data["same_model"] is True
    assert data["same_question"] is True
    assert data["same_generation"] is True
    assert data["fixture"]["source"].endswith("#text")
    assert tp5["official_unchanged"] is True
    assert tp5["recall_returns_not_in_memory"] is True

    network = data["network_isolation"]
    assert network["on_service_reachable_during_off"] is False
    assert network["off_connection_attempt"]["reachable"] is False
    assert network["off_launch_starts_service"] is False
    assert data["conditions"]["memory-off"]["denied_private_artifacts"]
    assert data["conditions"]["memory-on"]["denied_private_artifacts"]

    for item in (
        data["isolation"]["off_negative_probes"]
        + data["isolation"]["on_negative_probes"]
    ):
        if item["expected"] == "denied":
            assert (
                item["denied"]
                or (item["absent"] and item["allow_absent"])
            ), item["name"]

    leaked = [
        item
        for item in data["isolation"]["off_negative_probes"]
        if item["name"].startswith("leaked_")
    ]
    assert leaked
    for item in leaked:
        assert (
            item["denied"]
            or (item["absent"] and item["allow_absent"])
        ), item["name"]

    off_probe_names = {
        probe["name"]
        for probe in data["isolation"]["off_negative_probes"]
        if probe["denied"]
    }
    on_probe_names = {
        probe["name"]
        for probe in data["isolation"]["on_negative_probes"]
        if probe["denied"]
    }
    required = {
        "private_fixture",
        "official_store",
        "official_ledger",
        "e6_flight_log",
        "opencode_real_log",
        "shell_escape_private_fixture",
        "python_escape_private_fixture",
        "repository_search",
    }
    assert required <= off_probe_names
    assert required <= on_probe_names
    assert {
        "private_store",
        "private_ledger",
        "private_sidecar",
    } <= on_probe_names

    isolation_path = tmp_path / "preflight-isolation.json"
    tp5_path = tmp_path / "preflight-tp5-isolation.json"
    assert isolation_path.exists()
    assert tp5_path.exists()

    combined = (
        isolation_path.read_text(encoding="utf-8")
        + tp5_path.read_text(encoding="utf-8")
    )
    assert claim_text() not in combined


@pytest.mark.skipif(
    not sandbox_available(),
    reason="sandbox-exec is not available on this host",
)
def test_off_sandbox_really_denies_protected_reads(tmp_path):
    sandbox = tmp_path / "off"
    build_off_sandbox(sandbox)

    probes = isolation_probes(sandbox, sandbox / "sandbox.sb")

    assert probes_ok(probes) is True
    assert all(probe["leaked"] is False for probe in probes)
    by_name = {probe["name"]: probe for probe in probes}
    for name in (
        "private_fixture",
        "official_store",
        "official_ledger",
        "e6_flight_log",
        "e6_evidence",
        "opencode_real_log",
        "opencode_real_db",
        "shell_escape_private_fixture",
        "python_escape_private_fixture",
        "repository_search",
    ):
        assert by_name[name]["denied"] is True, name
        assert by_name[name]["stderr"] != ""
    assert by_name["allowed_question_read"]["returncode"] == 0


@pytest.mark.skipif(
    not sandbox_available(),
    reason="sandbox-exec is not available on this host",
)
def test_on_sandbox_really_denies_private_store_and_sidecar(tmp_path):
    sandbox = tmp_path / "on"
    private = tmp_path / "private"
    manifest = build_on_sandbox(sandbox, private)

    run_wrapper(sandbox, QUESTION_RECALL)

    probes = isolation_probes(
        sandbox,
        sandbox / "sandbox.sb",
        extra_denied=[
            ("private_store", manifest["fixture_store"]),
            ("private_ledger", manifest["fixture_ledger"]),
            ("private_sidecar", manifest["sidecar"]),
        ],
    )

    assert probes_ok(probes) is True
    assert all(probe["leaked"] is False for probe in probes)
    by_name = {probe["name"]: probe for probe in probes}
    for name in (
        "private_fixture",
        "official_store",
        "official_ledger",
        "opencode_real_log",
        "shell_escape_private_fixture",
        "python_escape_private_fixture",
        "repository_search",
        "private_store",
        "private_ledger",
        "private_sidecar",
    ):
        assert by_name[name]["denied"] is True, name
    assert by_name["allowed_question_read"]["returncode"] == 0


def test_verify_on_rejects_scores_below_threshold(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    event = {
        "event": "recall",
        "schema": LEDGER_SCHEMA,
        "question": QUESTION_RECALL,
        "results": [
            {
                "id": "m-9001",
                "source": "private-claim.json#text",
                "score": ON_THRESHOLD - 0.01,
            }
        ],
        "top_id": "m-9001",
        "top_source": "private-claim.json#text",
        "top_score": ON_THRESHOLD - 0.01,
    }
    ledger.write_text(json.dumps(event) + "\n", encoding="utf-8")

    matches, _ = verify_on_event(
        ledger,
        "m-9001",
        "private-claim.json#text",
        QUESTION_RECALL,
    )
    assert matches is False

    event["results"][0]["score"] = ON_THRESHOLD + 0.01
    event["top_score"] = ON_THRESHOLD + 0.01
    ledger.write_text(json.dumps(event) + "\n", encoding="utf-8")

    matches, _ = verify_on_event(
        ledger,
        "m-9001",
        "private-claim.json#text",
        QUESTION_RECALL,
    )
    assert matches is True


def test_generated_opencode_config_is_supported_by_installed_binary(
    tmp_path,
):
    if shutil.which("opencode") is None:
        pytest.skip("opencode is not installed on this host")

    config = opencode_config("off")
    (tmp_path / "opencode.json").write_text(
        json.dumps(config), encoding="utf-8"
    )

    env = os.environ.copy()
    env["XDG_DATA_HOME"] = str(tmp_path / "data")
    env["OPENCODE_DB"] = str(tmp_path / "data" / "opencode.db")

    result = subprocess.run(
        ["opencode", "debug", "config"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    resolved = json.loads(result.stdout)

    assert resolved["permission"] == config["permission"]
    assert "permissions" not in resolved


def test_launch_scripts_use_fresh_data_dir_and_sandbox(tmp_path):
    build_off_sandbox(tmp_path / "off")
    build_on_sandbox(tmp_path / "on", tmp_path / "private")

    off_script = (tmp_path / "off" / "launch.sh").read_text(
        encoding="utf-8"
    )
    on_script = (tmp_path / "on" / "launch.sh").read_text(
        encoding="utf-8"
    )

    for script in (off_script, on_script):
        assert 'XDG_DATA_HOME="$HERE/data"' in script
        assert 'OPENCODE_DB="$XDG_DATA_HOME/opencode.db"' in script
        assert "sandbox-exec -f" in script
        assert "--model opencode/big-pickle" in script

    assert "serve-on" in on_script
    assert "serve-on" not in off_script

    on_profile = (tmp_path / "on" / "sandbox.sb").read_text(
        encoding="utf-8"
    )
    assert str(Path.home() / ".local" / "share" / "opencode") in on_profile
    assert str((tmp_path / "private").resolve()) in on_profile
    assert str((tmp_path / "on.private.json").resolve()) in on_profile


def test_off_builder_fails_closed_when_sandbox_exists(tmp_path):
    sandbox = tmp_path / "off"
    sandbox.mkdir()
    marker = sandbox / "prior-session.txt"
    marker.write_text("preserve me", encoding="utf-8")

    with pytest.raises(FileExistsError, match="sandbox target already exists"):
        build_off_sandbox(sandbox)

    assert marker.read_text(encoding="utf-8") == "preserve me"
    assert sorted(path.name for path in sandbox.iterdir()) == [
        "prior-session.txt"
    ]


def test_on_builder_preserves_existing_private_ledger(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    ledger = private / "fixture-memory-ledger.jsonl"
    original = '{"event":"recall","evidence":"prior"}\n'
    ledger.write_text(original, encoding="utf-8")

    with pytest.raises(FileExistsError, match="private target already exists"):
        build_on_sandbox(tmp_path / "on", private)

    assert ledger.read_text(encoding="utf-8") == original
    assert not (tmp_path / "on").exists()


def test_launch_script_rejects_preexisting_data_directory(tmp_path):
    sandbox = tmp_path / "off"
    build_off_sandbox(sandbox)
    data = sandbox / "data"
    data.mkdir()
    marker = data / "prior.db"
    marker.write_text("prior session", encoding="utf-8")

    result = subprocess.run(
        [str(sandbox / "launch.sh"), "synthetic prompt"],
        cwd=sandbox,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Refusing to reuse OpenCode data directory" in result.stderr
    assert marker.read_text(encoding="utf-8") == "prior session"


def test_synthetic_capture_records_complete_immutable_evidence(tmp_path):
    synthetic = tmp_path / "synthetic.py"
    synthetic.write_text(
        "import json\n"
        "print(json.dumps({'type': 'tool_use', 'part': "
        "{'tool': 'bash', 'state': {'input': {'command': 'synthetic'}}}}))\n"
        "print(json.dumps({'type': 'text', 'part': "
        "{'text': 'Not in memory.'}}))\n",
        encoding="utf-8",
    )
    ledger = tmp_path / "recall-ledger.jsonl"
    ledger.write_text(
        '{"event":"recall","schema":"e7-memory-v2"}\n',
        encoding="utf-8",
    )
    store = tmp_path / "store.jsonl"
    store.write_text('{"id":"m-synthetic"}\n', encoding="utf-8")
    output = tmp_path / "capture-tp1"

    manifest = capture_evidence(
        output,
        condition="memory-off",
        test_point="TP1-synthetic",
        command=[sys.executable, str(synthetic)],
        recall_ledger=ledger,
        hash_paths=[store, ledger],
    )

    assert (output / "opencode-events.jsonl").read_text(
        encoding="utf-8"
    ).count("\n") == 2
    assert (output / "verbatim-answer.txt").read_text(
        encoding="utf-8"
    ) == "Not in memory.\n"
    tool_events = (output / "tool-trace.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(tool_events) == 1
    assert json.loads(tool_events[0])["type"] == "tool_use"
    assert (output / "recall-events.jsonl").read_bytes() == ledger.read_bytes()
    assert manifest["command"][0] == sys.executable
    assert manifest["condition"] == "memory-off"
    assert manifest["test_point"] == "TP1-synthetic"
    assert manifest["returncode"] == 0
    assert manifest["hashes_before"] == manifest["hashes_after"]
    assert set(manifest["artifact_sha256"]) >= {
        "opencode-events.jsonl",
        "verbatim-answer.txt",
        "tool-trace.jsonl",
        "recall-events.jsonl",
    }

    with pytest.raises(FileExistsError, match="evidence target already exists"):
        capture_evidence(
            output,
            condition="memory-off",
            test_point="TP1-synthetic",
            command=[sys.executable, str(synthetic)],
        )


def test_capture_cli_uses_synthetic_command_without_opencode(tmp_path):
    synthetic = tmp_path / "emit.py"
    synthetic.write_text(
        "import json\n"
        "print(json.dumps({'type': 'text', 'part': {'text': '4'}}))\n",
        encoding="utf-8",
    )
    output = tmp_path / "tp3-off"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.e7_memory",
            "capture",
            "--output",
            str(output),
            "--condition",
            "memory-off",
            "--test-point",
            "TP3-OFF-synthetic",
            "--",
            sys.executable,
            str(synthetic),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (output / "verbatim-answer.txt").read_text(
        encoding="utf-8"
    ) == "4\n"
    manifest = json.loads(result.stdout)
    assert manifest["test_point"] == "TP3-OFF-synthetic"


def test_fixture_source_matches_private_location():
    fixture = load_fixture()

    assert fixture["source"] == (
        "~/CIDM6333-private-e7/private-claim.json#text"
    )
    assert FIXTURE_PATH == (
        Path.home() / "CIDM6333-private-e7" / "private-claim.json"
    )


@pytest.mark.skipif(
    not sandbox_available(),
    reason="sandbox-exec is not available on this host",
)
def test_serve_on_cli_and_sandboxed_client(tmp_path):
    sandbox = tmp_path / "on"
    private = tmp_path / "private"
    build_on_sandbox(sandbox, private)

    service_config = json.loads(
        (sandbox / "service.json").read_text(encoding="utf-8")
    )
    service = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "src.e7_memory",
            "serve-on",
            "--sandbox",
            str(sandbox),
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        for _ in range(50):
            try:
                with socket.create_connection(
                    ("127.0.0.1", service_config["port"]),
                    timeout=0.2,
                ):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("serve-on did not start the localhost service")

        result = subprocess.run(
            [
                "/usr/bin/sandbox-exec",
                "-f",
                str(sandbox / "sandbox.sb"),
                "/usr/bin/python3",
                str(sandbox / "ask_memory.py"),
                QUESTION_RECALL,
            ],
            cwd=sandbox,
            capture_output=True,
            text=True,
            check=False,
        )

        fixture = load_fixture()
        assert result.returncode == 0
        assert fixture["id"] in result.stdout
        assert fixture["source"] in result.stdout
        assert fixture["expected_answer"] in result.stdout
        assert (private / "fixture-memory-ledger.jsonl").exists()
    finally:
        service.terminate()
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.kill()
            service.wait(timeout=5)
