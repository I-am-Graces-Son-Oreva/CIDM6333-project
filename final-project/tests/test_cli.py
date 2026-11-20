import contextlib
import io
import json
import os
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from fifth_pick.cli import main

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HEALTH = {
    "package": "fifth_pick",
    "status": "ok",
    "version": "0.1.0",
}
API_KEY = "THE_ODDS_API_KEY"


class GuardedEnvironment:
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def _guard(self, key: object) -> None:
        if key == API_KEY:
            raise AssertionError("THE_ODDS_API_KEY was read")

    def __getitem__(self, key: str) -> str:
        self._guard(key)
        return self._values[key]

    def get(self, key: str, default: str | None = None) -> str | None:
        self._guard(key)
        return self._values.get(key, default)

    def __contains__(self, key: object) -> bool:
        self._guard(key)
        return key in self._values


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "fifth_pick", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class CliTests(unittest.TestCase):
    def test_health_returns_structured_json_and_exit_zero(self) -> None:
        result = run_cli("health")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), EXPECTED_HEALTH)

    def test_unknown_command_returns_usage_exit_code(self) -> None:
        result = run_cli("not-a-command")

        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr.lower())
        self.assertEqual(result.stdout, "")

    def test_health_does_not_read_api_key_or_network(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        sentinel = "do-not-expose-this-key"
        values = dict(os.environ)
        values[API_KEY] = sentinel
        environment = GuardedEnvironment(values)

        with (
            mock.patch("os.environ", environment),
            mock.patch("socket.create_connection", side_effect=AssertionError("network")),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = main(["health"])

        self.assertEqual(exit_code, 0, stderr.getvalue())
        self.assertNotIn(sentinel, stdout.getvalue())
        self.assertNotIn(sentinel, stderr.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_console_entry_point_is_declared(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(
            pyproject["project"]["scripts"]["fifth-pick"],
            "fifth_pick.cli:main",
        )
