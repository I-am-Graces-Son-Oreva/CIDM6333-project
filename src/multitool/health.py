import ast
import subprocess
import tomllib
from pathlib import Path
from typing import TypedDict

_GATES = {
    "ruff_check": ("uv", "run", "ruff", "check"),
    "ruff_format": ("uv", "run", "ruff", "format", "--check"),
    "ty": ("uv", "run", "ty", "check"),
    "unittest": ("uv", "run", "python", "-m", "unittest", "discover", "-s", "tests"),
}


class HealthReport(TypedDict):
    checks: dict[str, bool]
    gates: dict[str, int]
    branch_violations: list[str]
    long_functions: list[str]
    analysis_errors: list[str]
    exit_code: int


class _BranchCounter(ast.NodeVisitor):
    def __init__(self, function: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.function = function
        self.count = 0

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(
            node,
            (
                ast.If,
                ast.IfExp,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.Try,
                ast.TryStar,
                ast.With,
                ast.AsyncWith,
            ),
        ):
            self.count += 1
        elif isinstance(node, ast.BoolOp):
            self.count += len(node.values) - 1

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not self.function:
            return
        super().generic_visit(node)


def _project_checks(root: Path) -> dict[str, bool]:
    pyproject = root / "pyproject.toml"
    try:
        config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except OSError, tomllib.TOMLDecodeError:
        config = {}
    tool = config.get("tool", {})
    has_ruff_config = isinstance(tool, dict) and isinstance(tool.get("ruff"), dict)
    has_ruff_config |= any((root / name).is_file() for name in ("ruff.toml", ".ruff.toml"))
    checks = {
        "pyproject.toml": pyproject.is_file(),
        "uv.lock": (root / "uv.lock").is_file(),
        "tests/": (root / "tests").is_dir(),
        "ruff configuration": has_ruff_config,
    }
    return checks


def _run_gates(root: Path) -> dict[str, int]:
    gates: dict[str, int] = {}
    for name, command in _GATES.items():
        try:
            result = subprocess.run(command, cwd=root, capture_output=True, check=False, text=True)
            gates[name] = result.returncode
        except OSError:
            gates[name] = 127
    return gates


def _source_findings(source: Path, root: Path) -> tuple[list[str], list[str], list[str]]:
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return [], [], [f"{source.relative_to(root)}: {exc}"]

    relative_path = source.relative_to(root).as_posix()
    branch_violations = []
    long_functions = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        branch_count = _BranchCounter(node)
        branch_count.visit(node)
        if branch_count.count > 8:
            branch_violations.append(f"{relative_path}:{node.name} ({branch_count.count} branches)")
        line_count = (node.end_lineno or node.lineno) - node.lineno + 1
        if line_count > 50:
            long_functions.append(f"{relative_path}:{node.name} ({line_count} lines)")
    return branch_violations, long_functions, []


def _analyze_source(root: Path) -> tuple[list[str], list[str], list[str]]:
    branch_violations = []
    long_functions = []
    analysis_errors = []
    source_dir = root / "src"
    if source_dir.is_dir():
        for source in sorted(source_dir.rglob("*.py")):
            branches, long, errors = _source_findings(source, root)
            branch_violations.extend(branches)
            long_functions.extend(long)
            analysis_errors.extend(errors)
    return branch_violations, long_functions, analysis_errors


def inspect_project(path: str | Path) -> HealthReport:
    root = Path(path)
    checks = _project_checks(root)
    gates = _run_gates(root)
    branch_violations, long_functions, analysis_errors = _analyze_source(root)

    exit_code = int(
        not all(checks.values())
        or any(gates.values())
        or bool(branch_violations)
        or bool(long_functions)
        or bool(analysis_errors)
    )
    return {
        "checks": checks,
        "gates": gates,
        "branch_violations": branch_violations,
        "long_functions": long_functions,
        "analysis_errors": analysis_errors,
        "exit_code": exit_code,
    }


def format_report(report: HealthReport) -> str:
    lines = [f"{name}: {'OK' if passed else 'FAIL'}" for name, passed in report["checks"].items()]
    lines.extend(f"{name}: {code}" for name, code in report["gates"].items())
    for heading, findings in (
        ("functions with >8 branches", report["branch_violations"]),
        ("functions longer than 50 lines", report["long_functions"]),
        ("analysis errors", report["analysis_errors"]),
    ):
        lines.append(f"{heading}:")
        lines.extend(f"  {finding}" for finding in findings) if findings else lines.append("  none")
    return "\n".join(lines)
