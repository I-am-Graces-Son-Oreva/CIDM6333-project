import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from multitool.health import inspect_project


class HealthTests(unittest.TestCase):
    def _make_project(self, root: Path) -> tuple[Path, Path]:
        (root / "src").mkdir()
        (root / "src" / "sample.py").write_text("def ordinary():\n    return 1\n")
        (root / "tests").mkdir()
        (root / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
        (root / "uv.lock").write_text("version = 1\n")
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        trace = root / "uv-commands.txt"
        fake_uv = fake_bin / "uv"
        fake_uv.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$*" >> "$MT_HEALTH_TRACE"\n'
            'if [ "$*" = "run ty check" ] && [ "${MT_HEALTH_FAIL:-}" = "ty" ]; then\n'
            "  exit 5\n"
            "fi\n"
            "exit 0\n"
        )
        fake_uv.chmod(0o755)
        return fake_bin, trace

    def _environment(self, fake_bin: Path, trace: Path, fail: str = "") -> dict[str, str]:
        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
        env["MT_HEALTH_TRACE"] = str(trace)
        env["MT_HEALTH_FAIL"] = fail
        return env

    def test_healthy_project_reports_artifacts_and_gate_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin, trace = self._make_project(root)
            with patch.dict(os.environ, self._environment(fake_bin, trace)):
                report = inspect_project(root)

            self.assertEqual(
                report["checks"],
                {
                    "pyproject.toml": True,
                    "uv.lock": True,
                    "tests/": True,
                    "ruff configuration": True,
                },
            )
            self.assertEqual(
                report["gates"],
                {"ruff_check": 0, "ruff_format": 0, "ty": 0, "unittest": 0},
            )
            self.assertEqual(report["exit_code"], 0)
            self.assertEqual(
                trace.read_text().splitlines(),
                [
                    "run ruff check",
                    "run ruff format --check",
                    "run ty check",
                    "run python -m unittest discover -s tests",
                ],
            )

    def test_missing_configuration_and_failed_gate_return_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin, trace = self._make_project(root)
            (root / "uv.lock").unlink()
            (root / "pyproject.toml").write_text("[project]\nname = 'fixture'\n")
            with patch.dict(os.environ, self._environment(fake_bin, trace, "ty")):
                report = inspect_project(root)

        self.assertFalse(report["checks"]["uv.lock"])
        self.assertFalse(report["checks"]["ruff configuration"])
        self.assertEqual(report["gates"]["ty"], 5)
        self.assertEqual(report["exit_code"], 1)

    def test_ast_report_finds_complex_and_long_functions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin, trace = self._make_project(root)
            source = ["def too_complex():"]
            for _ in range(9):
                source.extend(("    if True:", "        pass"))
            source.extend(("", "def too_long():"))
            source.extend("    value = 1" for _ in range(50))
            (root / "src" / "sample.py").write_text("\n".join(source) + "\n")
            with patch.dict(os.environ, self._environment(fake_bin, trace)):
                report = inspect_project(root)

        self.assertEqual(
            report["branch_violations"],
            ["src/sample.py:too_complex (9 branches)"],
        )
        self.assertEqual(report["long_functions"], ["src/sample.py:too_long (51 lines)"])
        self.assertEqual(report["exit_code"], 1)

    def test_cli_exits_one_when_a_gate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin, trace = self._make_project(root)
            uv = shutil.which("uv")
            if uv is None:
                raise RuntimeError("uv executable not found")
            result = subprocess.run(
                [uv, "run", "mt", "health", str(root)],
                capture_output=True,
                check=False,
                cwd=Path(__file__).resolve().parents[1],
                env=self._environment(fake_bin, trace, "ty"),
                text=True,
            )

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("ty: 5", result.stdout)


if __name__ == "__main__":
    unittest.main()
