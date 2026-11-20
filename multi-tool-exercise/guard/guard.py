import json
import os
import re
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _is_test_path(value: str, root: Path) -> bool:
    path = Path(value)
    root_path = Path(os.path.abspath(root))
    candidate = path if path.is_absolute() else root_path / path
    tests_path = root_path / "tests"
    normalized_candidate = Path(os.path.abspath(candidate))
    if normalized_candidate.is_relative_to(tests_path):
        return True
    try:
        return candidate.resolve().is_relative_to(tests_path.resolve())
    except OSError, RuntimeError:
        return normalized_candidate.is_relative_to(tests_path)


def _target_paths(tool: str, args: dict[str, Any]) -> list[str]:
    paths = [
        args[key]
        for key in ("filePath", "file_path", "path", "target", "targetPath")
        if isinstance(args.get(key), str)
    ]
    if tool in {"patch", "apply_patch"}:
        patch_text = args.get("patchText", args.get("patch"))
        if isinstance(patch_text, str):
            paths.extend(
                re.findall(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$", patch_text, re.MULTILINE)
            )
    return paths


def _test_redirection(tokens: list[str], root: Path) -> bool:
    for index, token in enumerate(tokens):
        if re.fullmatch(r"\d*(?:&>>|&>|>{1,2}|>\|)", token) and index + 1 < len(tokens):
            if _is_test_path(tokens[index + 1], root):
                return True
        redirect = re.match(r"\d*(?:&>>|&>|>{1,2}|>\|)(.+)", token)
        if redirect and _is_test_path(redirect.group(1), root):
            return True
    return False


def _tee_writes_to_tests(tokens: list[str], root: Path) -> bool:
    for index, token in enumerate(tokens):
        if Path(token).name != "tee":
            continue
        for target in tokens[index + 1 :]:
            if target in {"|", "||", "&&", ";"}:
                break
            if not target.startswith("-") and _is_test_path(target, root):
                return True
    return False


def _in_place_write(name: str, args: list[str], root: Path) -> bool:
    if name not in {"sed", "perl"}:
        return False
    if not any(arg == "-i" or arg.startswith("-i") for arg in args):
        return False
    return any(_is_test_path(arg, root) for arg in args if not arg.startswith("-i"))


def _direct_write(name: str, args: list[str], root: Path) -> bool:
    if name in {"touch", "rm", "truncate"}:
        return any(_is_test_path(arg, root) for arg in args if not arg.startswith("-"))
    if name in {"cp", "mv", "install"} and args:
        return _is_test_path(args[-1], root)
    return False


def _formatter_write(name: str, args: list[str], root: Path) -> bool:
    if name == "ruff" and args[:1] == ["format"]:
        args = args[1:]
    elif name not in {"black", "autopep8"}:
        return False
    if "--check" in args or "--diff" in args:
        return False
    return any(_is_test_path(arg, root) for arg in args if not arg.startswith("-"))


def _test_command_write(tokens: list[str], root: Path) -> bool:
    for index, token in enumerate(tokens):
        name = Path(token).name
        args = tokens[index + 1 :]
        if _in_place_write(name, args, root):
            return True
        if _direct_write(name, args, root) or _formatter_write(name, args, root):
            return True
    return False


def _python_writes_to_tests(command: str) -> bool:
    writes_file = any(marker in command for marker in (".write_text(", ".write_bytes(", ".unlink("))
    open_mode = r"['\"][^'\"]*[wax+][^'\"]*['\"]"
    writes_file |= bool(re.search(rf"\bopen\([^)]*,\s*{open_mode}", command))
    writes_file |= bool(re.search(rf"\bopen\([^)]*\bmode\s*=\s*{open_mode}", command))
    return writes_file and bool(re.search(r"(?:^|[/'\"=])tests(?:/|['\"])", command))


def _shell_writes_to_tests(command: str, root: Path) -> bool:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return _python_writes_to_tests(command) or bool(
            re.search(r"tests/.*(?:>|\btee\b|\s-i\b)", command)
        )
    return (
        _test_redirection(tokens, root)
        or _tee_writes_to_tests(tokens, root)
        or _test_command_write(tokens, root)
        or _python_writes_to_tests(command)
    )


def _decide(tool: str, args: dict[str, Any], root: Path) -> tuple[str, str | None, str | None]:
    paths = _target_paths(tool, args)
    if tool in {"edit", "write", "patch", "apply_patch"}:
        for path in paths:
            if _is_test_path(path, root):
                return "block", f"blocked write to tests path: {path}", path

    if tool in {"bash", "shell"}:
        command = args.get("command", args.get("cmd", ""))
        if isinstance(command, str) and _shell_writes_to_tests(command, root):
            return "block", "blocked shell write into tests/", None
        return "allow", None, None

    return "allow", None, paths[0] if paths else None


def _append_receipt(root: Path, receipt: dict[str, Any]) -> None:
    receipts = root / ".receipts"
    receipts.mkdir(exist_ok=True)
    with (receipts / "tool-calls.jsonl").open("a", encoding="utf-8") as output:
        output.write(json.dumps(receipt, sort_keys=True) + "\n")


def _read_call() -> tuple[str, dict[str, Any], str | None]:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return "unknown", {}, "blocked invalid guard input"
    if not isinstance(payload, dict):
        return "unknown", {}, "blocked invalid guard input"
    tool = payload.get("tool", "unknown")
    args = payload.get("args", {})
    if not isinstance(tool, str) or not isinstance(args, dict):
        return "unknown", {}, "blocked invalid guard input"
    return tool, args, None


def _make_receipt(
    tool: str, args: dict[str, Any], decision: str, reason: str | None, path: str | None
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "time": datetime.now(UTC).isoformat(),
        "tool": tool,
        "decision": decision,
    }
    if path is not None:
        receipt["path"] = path
    command = args.get("command", args.get("cmd"))
    if isinstance(command, str):
        receipt["command"] = command
    if reason is not None:
        receipt["reason"] = reason
    return receipt


def main() -> int:
    root = Path.cwd()
    tool, args, reason = _read_call()
    decision, path = "block", None
    if reason is None:
        decision, reason, path = _decide(tool, args, root)
    receipt = _make_receipt(tool, args, decision, reason, path)
    try:
        _append_receipt(root, receipt)
    except OSError as exc:
        print(f"blocked: cannot write guard receipt: {exc}")
        return 2

    if reason is not None:
        print(reason.replace("\n", " "))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
