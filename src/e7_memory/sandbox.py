import subprocess
from pathlib import Path

from .fixture import FIXTURE_PATH

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENCODE_DATA_DIR = Path.home() / ".local" / "share" / "opencode"
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
MODEL_ID = "opencode/big-pickle"


def sandbox_available():
    return Path(SANDBOX_EXEC).exists()


def require_sandbox():
    if not sandbox_available():
        raise RuntimeError(
            "sandbox-exec is required for real memory isolation but was not "
            "found at /usr/bin/sandbox-exec"
        )


ARTIFACT_ROOT = Path("/tmp/e7-artifacts")


def protected_paths():
    return [REPO_ROOT, FIXTURE_PATH.parent, OPENCODE_DATA_DIR]


def discovered_private_roots(sandbox):
    sandbox = Path(sandbox).resolve()
    candidates = {ARTIFACT_ROOT.resolve()}
    for base in (Path("/tmp"), Path("/private/tmp")):
        if base.exists():
            for path in base.glob("e7-*"):
                candidates.add(path.resolve())
    roots = []
    for candidate in candidates:
        if candidate == sandbox or sandbox in candidate.parents:
            continue
        roots.append(candidate)
    return sorted(roots)


def private_deny_paths(sandbox, extra_paths=()):
    sandbox = Path(sandbox).resolve()
    candidates = set(discovered_private_roots(sandbox))
    for path in extra_paths:
        if path is None:
            continue
        candidates.add(Path(path).resolve())

    denied = set()
    for candidate in candidates:
        if candidate == sandbox:
            continue
        if candidate in sandbox.parents:
            if candidate.exists() and candidate.is_dir():
                for child in candidate.iterdir():
                    child = child.resolve()
                    if child == sandbox or child in sandbox.parents:
                        continue
                    denied.add(child)
            else:
                denied.add(candidate / "private")
                denied.add(candidate / "on.private.json")
            continue
        denied.add(candidate)

    return sorted(
        path for path in denied
        if path != sandbox and path not in sandbox.parents
    )


def classify_denied(paths):
    directories = []
    files = []
    for path in paths:
        path = Path(path)
        if path.exists():
            if path.is_file():
                files.append(path)
            else:
                directories.append(path)
        elif path.suffix:
            files.append(path)
        else:
            directories.append(path)
    return directories, files


def _subpath(path):
    value = str(Path(path).resolve())
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _literal(path):
    value = str(Path(path).resolve())
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_profile(protected=(), denied_files=()):
    lines = ["(version 1)", "(allow default)"]
    for path in protected:
        value = _subpath(path)
        lines.append(f'(deny file-read* (subpath "{value}"))')
        lines.append(f'(deny file-write* (subpath "{value}"))')
    for path in denied_files:
        value = _literal(path)
        lines.append(f'(deny file-read* (literal "{value}"))')
        lines.append(f'(deny file-write* (literal "{value}"))')
    return "\n".join(lines) + "\n"


def write_profile(path, protected=(), denied_files=()):
    path = Path(path)
    path.write_text(
        build_profile(protected, denied_files),
        encoding="utf-8",
    )
    return path


def write_launch_script(path, sandbox, serve=False):
    path = Path(path)
    sandbox = Path(sandbox).resolve()
    lines = [
        "#!/bin/sh",
        "set -eu",
        f'HERE="{sandbox}"',
        'export XDG_DATA_HOME="$HERE/data"',
        'export OPENCODE_DB="$XDG_DATA_HOME/opencode.db"',
        'mkdir -p "$XDG_DATA_HOME"',
    ]

    if serve:
        lines.extend(
            [
                f'cd "{REPO_ROOT}"',
                (
                    'python3 -m src.e7_memory serve-on --sandbox "$HERE" '
                    '> "$HERE/service.log" 2>&1 &'
                ),
                "SERVICE_PID=$!",
                (
                    "cleanup() { kill \"$SERVICE_PID\" 2>/dev/null || true; }"
                ),
                "trap cleanup EXIT INT TERM",
                'cd "$HERE"',
                (
                    'sandbox-exec -f "$HERE/sandbox.sb" opencode run '
                    '--dir "$HERE" --model '
                    f'{MODEL_ID} "$@"'
                ),
            ]
        )
    else:
        lines.extend(
            [
                'cd "$HERE"',
                (
                    'exec sandbox-exec -f "$HERE/sandbox.sb" opencode run '
                    '--dir "$HERE" --model '
                    f'{MODEL_ID} "$@"'
                ),
            ]
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def run_under_sandbox(profile, command, cwd):
    return subprocess.run(
        [SANDBOX_EXEC, "-f", str(profile), *command],
        cwd=Path(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def probe(profile, cwd, name, command, expected, redact=None,
          allow_absent=False):
    result = run_under_sandbox(profile, command, cwd)
    denied = result.returncode != 0 and (
        "Operation not permitted" in result.stderr
        or "Permission denied" in result.stderr
    )
    absent = result.returncode != 0 and (
        "No such file or directory" in result.stdout
        or "No such file or directory" in result.stderr
    )
    leaked = bool(
        redact
        and (redact in result.stdout or redact in result.stderr)
    )

    def clean(value):
        if redact and redact in value:
            value = value.replace(redact, "[REDACTED]")
        return value[:4000]

    return {
        "name": name,
        "command": [str(part) for part in command],
        "expected": expected,
        "returncode": result.returncode,
        "denied": denied and not leaked,
        "leaked": leaked,
        "absent": absent,
        "allow_absent": allow_absent,
        "stdout": clean(result.stdout),
        "stderr": clean(result.stderr),
    }
