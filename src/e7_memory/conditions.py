import hashlib
import json
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from .fixture import (
    FIXTURE_PATH,
    build_fixture_store,
    claim_hash,
    claim_text,
    load_fixture,
)
from .sandbox import (
    MODEL_ID,
    OPENCODE_DATA_DIR,
    classify_denied,
    discovered_private_roots,
    private_deny_paths,
    probe,
    protected_paths,
    require_sandbox,
    run_under_sandbox,
    write_launch_script,
    write_profile,
)
from .service import start_service

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
E6_EVIDENCE_FILE = E6_EVIDENCE_DIR / "session-b2-export.json"

QUESTION_RECALL = "What is the E7 private fixture passphrase?"
QUESTION_CONTROL = "What is 2 + 2?"
QUESTION_ABSENT = "What is the secret launch code for Project Orion?"
MODEL = "OpenCode Big Pickle"
CONTROL_AGENT_ANSWER = "4"
ON_THRESHOLD = 0.30
LEDGER_SCHEMA = "e7-memory-v2"
EVIDENCE_LABEL = "PREFLIGHT — NOT OFFICIAL SORTIE EVIDENCE"
OPENCODE_CONFIG = "opencode.json"
SANDBOX_PROFILE = "sandbox.sb"
SERVICE_CONFIG = "service.json"
LAUNCH_SCRIPT = "launch.sh"
SIDECAR_SUFFIX = ".private.json"
GENERATION = {
    "temperature": "provider-default",
    "variant": "default",
}
THIRD_REVIEW_LEAKED_PATHS = [
    (
        "leaked_artifacts_private_store",
        Path("/tmp/e7-artifacts/private/fixture-memory.jsonl"),
    ),
    (
        "leaked_artifacts_private_ledger",
        Path("/tmp/e7-artifacts/private/fixture-memory-ledger.jsonl"),
    ),
    (
        "leaked_artifacts_sidecar",
        Path("/tmp/e7-artifacts/on.private.json"),
    ),
    (
        "leaked_artifacts_service_config",
        Path("/tmp/e7-artifacts/on/service.json"),
    ),
    (
        "leaked_artifacts_on_profile",
        Path("/tmp/e7-artifacts/on/sandbox.sb"),
    ),
    (
        "leaked_demo_private_store",
        Path("/tmp/e7-demo-1cnh/private/fixture-memory.jsonl"),
    ),
    (
        "leaked_demo_private_ledger",
        Path("/tmp/e7-demo-1cnh/private/fixture-memory-ledger.jsonl"),
    ),
]


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


def opencode_config(condition):
    permission = {
        "read": "deny",
        "edit": "deny",
        "glob": "deny",
        "grep": "deny",
        "list": "deny",
        "bash": "deny" if condition == "off" else "allow",
        "task": "deny",
        "skill": "deny",
        "webfetch": "deny",
        "websearch": "deny",
        "external_directory": {"*": "deny"},
        "lsp": "deny",
        "todowrite": "deny",
        "doom_loop": "deny",
    }
    return {
        "$schema": "https://opencode.ai/config.json",
        "permission": permission,
    }


def write_opencode_config(sandbox, condition):
    path = Path(sandbox) / OPENCODE_CONFIG
    write_json(path, opencode_config(condition))
    return path


def sidecar_path(sandbox):
    sandbox = Path(sandbox)
    return sandbox.parent / f"{sandbox.name}{SIDECAR_SUFFIX}"


def write_sidecar(sandbox, private_dir, store, ledger):
    path = sidecar_path(sandbox)
    write_json(
        path,
        {
            "private": str(Path(private_dir).resolve()),
            "store": str(Path(store).resolve()),
            "ledger": str(Path(ledger).resolve()),
        },
    )
    return path


def write_service_config(sandbox, port, today):
    path = Path(sandbox) / SERVICE_CONFIG
    write_json(
        path,
        {
            "port": port,
            "threshold": ON_THRESHOLD,
            "today": today,
        },
    )
    return path


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


CLIENT_SOURCE = '''#!/usr/bin/python3
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def main():
    config = json.loads(
        Path(__file__).with_name("service.json").read_text(encoding="utf-8")
    )
    question = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read().strip()
    url = "http://127.0.0.1:%d/recall?question=%s" % (
        config["port"],
        urllib.parse.quote(question),
    )
    last_error = None
    for _ in range(30):
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            break
        except (urllib.error.URLError, ConnectionError) as exc:
            last_error = exc
            time.sleep(0.1)
    else:
        print("Retriever unavailable: %s" % last_error)
        return 2

    if not data.get("results"):
        print("Not in memory.")
        return 0

    for item in data["results"]:
        print("Memory ID: %s" % item["id"])
        print("Source: %s" % item["source"])
        print("Date: %s" % item["date"])
        print("Score: %.4f" % item["score"])
        print("Memory: %s" % item["text"])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def artifact_probe_targets(sandbox):
    sandbox = Path(sandbox).resolve()
    targets = []
    seen = set()

    for name, path in THIRD_REVIEW_LEAKED_PATHS:
        key = str(Path(path).resolve())
        if key in seen:
            continue
        seen.add(key)
        targets.append((name, Path(path), True))

    for root in discovered_private_roots(sandbox):
        if root == sandbox or sandbox in root.parents:
            continue
        if root.exists() and root.is_file():
            files = [root]
        elif root.exists() and root.is_dir():
            files = [path for path in root.rglob("*") if path.is_file()]
        else:
            files = []
        for path in files:
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            targets.append(
                (f"private_artifact_{len(targets):02d}", path, False)
            )

    return targets


def service_port(sandbox):
    config = json.loads(
        (Path(sandbox) / SERVICE_CONFIG).read_text(encoding="utf-8")
    )
    return config["port"]


def service_reachable(port, host="127.0.0.1", timeout=0.2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def connection_probe(profile, cwd, port):
    python = (
        "/usr/bin/python3"
        if Path("/usr/bin/python3").exists()
        else sys.executable
    )
    command = [
        python,
        "-c",
        (
            "import socket; "
            f"socket.create_connection(('127.0.0.1', {port}), timeout=1)"
        ),
    ]
    result = run_under_sandbox(profile, command, cwd)
    return {
        "command": [str(part) for part in command],
        "port": port,
        "reachable": result.returncode == 0,
        "returncode": result.returncode,
        "stderr": result.stderr[:1000],
    }


def isolation_probes(sandbox, profile, extra_denied=()):
    sandbox = Path(sandbox)
    claim = claim_text()
    probes = []
    targets = [
        ("private_fixture", FIXTURE_PATH),
        ("official_store", OFFICIAL_STORE),
        ("official_ledger", OFFICIAL_LEDGER),
        ("e6_flight_log", E6_FILES[0]),
        ("e6_evidence", E6_EVIDENCE_FILE),
        ("opencode_real_log", OPENCODE_DATA_DIR / "log" / "opencode.log"),
        ("opencode_real_db", OPENCODE_DATA_DIR / "opencode.db"),
    ]

    for name, path in targets:
        if Path(path).is_file():
            probes.append(
                probe(
                    profile,
                    sandbox,
                    name,
                    ["/bin/cat", str(path)],
                    "denied",
                    redact=claim,
                )
            )

    probes.append(
        probe(
            profile,
            sandbox,
            "shell_escape_private_fixture",
            ["/bin/sh", "-c", f"cat {shlex.quote(str(FIXTURE_PATH))}"],
            "denied",
            redact=claim,
        )
    )
    probes.append(
        probe(
            profile,
            sandbox,
            "python_escape_private_fixture",
            [
                "/usr/bin/python3",
                "-c",
                f"print(open({str(FIXTURE_PATH)!r}).read())",
            ],
            "denied",
            redact=claim,
        )
    )
    probes.append(
        probe(
            profile,
            sandbox,
            "repository_search",
            ["/usr/bin/grep", "-r", "m-0001", str(REPO_ROOT)],
            "denied",
            redact=claim,
        )
    )
    probes.append(
        probe(
            profile,
            sandbox,
            "allowed_question_read",
            ["/bin/cat", str(sandbox / "question-recall.txt")],
            "allowed",
            redact=claim,
        )
    )

    for name, path, allow_absent in artifact_probe_targets(sandbox):
        probes.append(
            probe(
                profile,
                sandbox,
                name,
                ["/bin/cat", str(path)],
                "denied",
                redact=claim,
                allow_absent=allow_absent,
            )
        )

    for name, path in extra_denied:
        probes.append(
            probe(
                profile,
                sandbox,
                name,
                ["/bin/cat", str(path)],
                "denied",
                redact=claim,
                allow_absent=True,
            )
        )

    return probes


def probe_ok(item):
    if item["expected"] == "allowed":
        return (
            not item["denied"]
            and not item.get("leaked", False)
            and item["returncode"] == 0
        )
    if item["denied"] and not item.get("leaked", False):
        return True
    return bool(item.get("absent")) and bool(item.get("allow_absent"))


def probes_ok(probes):
    return all(probe_ok(item) for item in probes)


def build_off_sandbox(sandbox, manifest_path=None, private_paths=()):
    require_sandbox()
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
        "This session runs under a macOS seatbelt sandbox that denies reads "
        "of the repository, the private fixture, and OpenCode's real data "
        "directory.\n"
        "If you cannot establish an answer, say: Not in memory.\n",
        encoding="utf-8",
    )

    config_path = write_opencode_config(sandbox, "off")
    denied = private_deny_paths(sandbox, private_paths)
    denied_dirs, denied_files = classify_denied(denied)
    profile_path = write_profile(
        sandbox / SANDBOX_PROFILE,
        [*protected_paths(), *denied_dirs],
        denied_files=denied_files,
    )
    launch_path = write_launch_script(
        sandbox / LAUNCH_SCRIPT,
        sandbox,
        serve=False,
    )

    claim = claim_text()
    manifest = {
        "label": EVIDENCE_LABEL,
        "condition": "memory-off",
        "model": MODEL,
        "model_id": MODEL_ID,
        "generation": GENERATION,
        "isolation_mode": (
            "macos-seatbelt + opencode-v1-permission-deny"
        ),
        "sandbox_profile": str(profile_path.resolve()),
        "opencode_config": str(config_path.resolve()),
        "opencode_permission": opencode_config("off")["permission"],
        "launch_script": str(launch_path.resolve()),
        "data_dir": str((sandbox / "data").resolve()),
        "protected_paths": [
            str(path.resolve()) for path in protected_paths()
        ],
        "denied_private_artifacts": [
            str(path.resolve()) for path in denied
        ],
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
                OPENCODE_DATA_DIR,
            ]
        ],
    }

    if manifest_path:
        write_json(manifest_path, manifest)
    return manifest


def build_on_sandbox(sandbox, private_dir, manifest_path=None,
                     today="2026-11-08", private_paths=()):
    require_sandbox()
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

    port = free_port()
    service_path = write_service_config(sandbox, port, today)
    sidecar = write_sidecar(sandbox, private_dir, store, ledger)

    (sandbox / "ask_memory.py").write_text(
        CLIENT_SOURCE,
        encoding="utf-8",
    )
    (sandbox / "ask_memory.py").chmod(0o755)

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
        "Use only ask_memory.py to retrieve stored memory. The retrieval "
        "service runs outside this sandbox on localhost.\n"
        "The private fixture store, ledger, and repository are outside the "
        "sandbox and are denied by the seatbelt profile.\n"
        "The retriever writes a recall event to the private ledger.\n",
        encoding="utf-8",
    )

    config_path = write_opencode_config(sandbox, "on")
    denied = private_deny_paths(
        sandbox,
        [private_dir, sidecar, *private_paths],
    )
    denied_dirs, denied_files = classify_denied(denied)
    profile_path = write_profile(
        sandbox / SANDBOX_PROFILE,
        [*protected_paths(), *denied_dirs],
        denied_files=denied_files,
    )
    launch_path = write_launch_script(
        sandbox / LAUNCH_SCRIPT,
        sandbox,
        serve=True,
    )

    claim = claim_text()
    manifest = {
        "label": EVIDENCE_LABEL,
        "condition": "memory-on",
        "model": MODEL,
        "model_id": MODEL_ID,
        "generation": GENERATION,
        "isolation_mode": (
            "macos-seatbelt + localhost-retriever + "
            "opencode-v1-permission-deny-read"
        ),
        "sandbox_profile": str(profile_path.resolve()),
        "opencode_config": str(config_path.resolve()),
        "opencode_permission": opencode_config("on")["permission"],
        "service_config": str(service_path.resolve()),
        "launch_script": str(launch_path.resolve()),
        "data_dir": str((sandbox / "data").resolve()),
        "retrieval_interface": f"http://127.0.0.1:{port}/recall",
        "retrieval_service_outside_sandbox": True,
        "sidecar": str(sidecar.resolve()),
        "sidecar_denied": True,
        "protected_paths": [
            str(path.resolve())
            for path in [*protected_paths(), private_dir]
        ],
        "denied_private_artifacts": [
            str(path.resolve()) for path in denied
        ],
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
                E6_EVIDENCE_DIR,
                OPENCODE_DATA_DIR,
            ]
        ],
    }

    if manifest_path:
        write_json(manifest_path, manifest)
    return manifest


def run_wrapper(sandbox, question):
    require_sandbox()
    sandbox = Path(sandbox)
    service_config = json.loads(
        (sandbox / SERVICE_CONFIG).read_text(encoding="utf-8")
    )
    sidecar = json.loads(
        sidecar_path(sandbox).read_text(encoding="utf-8")
    )
    server = start_service(
        sidecar["private"],
        port=service_config["port"],
        threshold=service_config.get("threshold", ON_THRESHOLD),
        today=service_config.get("today"),
    )
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()
    try:
        wrapper = sandbox / "ask_memory.py"
        python = (
            "/usr/bin/python3"
            if Path("/usr/bin/python3").exists()
            else sys.executable
        )
        return run_under_sandbox(
            sandbox / SANDBOX_PROFILE,
            [python, str(wrapper), question],
            sandbox,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def serve_on(sandbox):
    require_sandbox()
    sandbox = Path(sandbox)
    service_config = json.loads(
        (sandbox / SERVICE_CONFIG).read_text(encoding="utf-8")
    )
    sidecar = json.loads(
        sidecar_path(sandbox).read_text(encoding="utf-8")
    )
    server = start_service(
        sidecar["private"],
        port=service_config["port"],
        threshold=service_config.get("threshold", ON_THRESHOLD),
        today=service_config.get("today"),
    )
    print(
        f"Serving on http://127.0.0.1:{server.server_address[1]}/recall",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


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
        and event["top_score"] >= ON_THRESHOLD
        and first.get("id") == expected_id
        and first.get("source") == expected_source
        and isinstance(first.get("score"), (int, float))
        and first["score"] >= ON_THRESHOLD
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
