"""Deploy a Fifth Pick wheel to an isolated local environment."""

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def execute(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise ValueError("deployment command failed")
    return result.stdout


def install(root: Path, wheel: Path, expected: str) -> None:
    """Keep a failed candidate isolated from the current environment."""
    candidate = root / "environments" / uuid4().hex
    candidate.parent.mkdir(exist_ok=True)
    try:
        execute("uv", "venv", "--offline", "--python", sys.executable, str(candidate))
        python = candidate / "bin/python"
        execute("uv", "pip", "install", "--offline", "--python", str(python), str(wheel))
        health = json.loads(execute(str(candidate / "bin/fifth-pick"), "health"))
        if health != {"package": "fifth_pick", "status": "ok", "version": expected}:
            raise ValueError("health smoke check failed")
        execute(
            str(python),
            "-c",
            "from fifth_pick.config import load_configs; load_configs()",
        )
        pending = root / ".next"
        pending.unlink(missing_ok=True)
        pending.symlink_to(candidate)
        os.replace(pending, root / "current")
    except BaseException:
        shutil.rmtree(candidate, ignore_errors=True)
        raise


def append_event(root: Path, event: dict) -> None:
    with (root / "release-ledger.jsonl").open("a") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(event, sort_keys=True))


def release(root: Path, source: Path, version: str, commit: str) -> dict:
    sha = digest(source)
    vault = root / "artifacts" / sha
    vault.mkdir(parents=True, exist_ok=True)
    artifact = vault / source.name
    if not artifact.exists():
        with artifact.open("xb") as stream, source.open("rb") as original:
            shutil.copyfileobj(original, stream)
        artifact.chmod(0o444)
    if digest(artifact) != sha:
        raise ValueError("stored release hash mismatch")
    install(root, artifact, version)
    return {"version": version, "sha256": sha, "wheel": source.name, "commit": commit}


def rollback(root: Path, version: str) -> dict:
    ledger = root / "release-ledger.jsonl"
    history = [json.loads(line) for line in ledger.read_text().splitlines()]
    previous = next(
        (
            row
            for row in reversed(history)
            if row["event"] == "release" and row["version"] == version and row["ok"]
        ),
        None,
    )
    if previous is None:
        raise ValueError("no successful release for requested version")
    recorded = {key: previous[key] for key in ("version", "sha256", "wheel", "commit")}
    artifact = root / "artifacts" / recorded["sha256"] / recorded["wheel"]
    if digest(artifact) != recorded["sha256"]:
        raise ValueError("stored release hash mismatch")
    install(root, artifact, version)
    return recorded


def attest(root: Path, version: str) -> dict:
    if not sys.stdin.isatty():
        raise ValueError("attestation requires the operator's terminal")
    ledger = root / "release-ledger.jsonl"
    entries = [json.loads(line) for line in ledger.read_text().splitlines()]
    active = next(
        (
            entry
            for entry in reversed(entries)
            if entry["ok"] and entry["event"] in {"release", "rollback"}
        ),
        None,
    )
    if active is None or active["version"] != version:
        raise ValueError("active release does not match requested version")
    health = json.loads(execute(str(root / "current/bin/fifth-pick"), "health"))
    if health != {"package": "fifth_pick", "status": "ok", "version": version}:
        raise ValueError("health smoke check failed")
    if input(f"Type ATTEST {version} to confirm your release observation: ") != f"ATTEST {version}":
        raise ValueError("attestation was not confirmed")
    return {"version": version, "sha256": active["sha256"], "commit": active["commit"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    commands = parser.add_subparsers(dest="action", required=True)
    candidate = commands.add_parser("release")
    candidate.add_argument("wheel", type=Path)
    candidate.add_argument("--version", required=True)
    candidate.add_argument("--commit", required=True)
    commands.add_parser("rollback").add_argument("--version", required=True)
    commands.add_parser("attest").add_argument("--version", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    event = {"event": args.action, "version": args.version, "ok": False}
    if args.action == "release":
        event.update(wheel=args.wheel.name, commit=args.commit)
    with (root / ".deploy.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            if args.action == "release":
                event["sha256"] = digest(args.wheel)
                result = release(root, args.wheel, args.version, args.commit)
            elif args.action == "rollback":
                result = rollback(root, args.version)
            else:
                result = attest(root, args.version)
            event.update(result, ok=True)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            reasons = {
                "health smoke check failed",
                "stored release hash mismatch",
                "no successful release for requested version",
                "deployment command failed",
            }
            event["error"] = str(exc) if str(exc) in reasons else type(exc).__name__
        event["seconds"] = round(time.monotonic() - started, 6)
        append_event(root, event)
    return 0 if event["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
