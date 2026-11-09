import json
import subprocess
from pathlib import Path


def _sha256(path):
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _snapshot(paths):
    return {
        str(Path(path).resolve()): _sha256(path)
        for path in paths
        if Path(path).is_file()
    }


def _events(raw):
    events = []
    for number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"OpenCode JSON event line {number} is invalid"
            ) from exc
        if not isinstance(event, dict):
            raise ValueError(
                f"OpenCode JSON event line {number} is not an object"
            )
        events.append(event)
    return events


def _part(event):
    value = event.get("part")
    return value if isinstance(value, dict) else {}


def capture_evidence(output_dir, *, condition, test_point, command,
                     recall_ledger=None, hash_paths=()):
    """Run one capture command and preserve its evidence without overwrite."""
    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(
            f"evidence target already exists: {output_dir}"
        ) from exc

    command = [str(part) for part in command]
    tracked = [Path(path) for path in hash_paths]
    hashes_before = _snapshot(tracked)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    hashes_after = _snapshot(tracked)

    raw_path = output_dir / "opencode-events.jsonl"
    stderr_path = output_dir / "opencode-stderr.txt"
    raw_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")

    events = _events(result.stdout)
    answer_parts = [
        _part(event)["text"]
        for event in events
        if event.get("type") == "text"
        and isinstance(_part(event).get("text"), str)
    ]
    tool_events = [
        event for event in events
        if str(event.get("type", "")).startswith("tool")
    ]

    answer_path = output_dir / "verbatim-answer.txt"
    answer_path.write_text(
        "\n".join(answer_parts) + ("\n" if answer_parts else ""),
        encoding="utf-8",
    )
    trace_path = output_dir / "tool-trace.jsonl"
    trace_path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n"
                for event in tool_events),
        encoding="utf-8",
    )

    if recall_ledger is not None:
        recall_path = Path(recall_ledger)
        if not recall_path.is_file():
            raise FileNotFoundError(
                f"recall ledger does not exist: {recall_path}"
            )
        (output_dir / "recall-events.jsonl").write_bytes(
            recall_path.read_bytes()
        )

    artifacts = [path for path in output_dir.iterdir() if path.is_file()]
    manifest = {
        "condition": condition,
        "test_point": test_point,
        "command": command,
        "returncode": result.returncode,
        "hashes_before": hashes_before,
        "hashes_after": hashes_after,
        "artifact_sha256": {
            path.name: _sha256(path) for path in sorted(artifacts)
        },
    }
    (output_dir / "capture-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
