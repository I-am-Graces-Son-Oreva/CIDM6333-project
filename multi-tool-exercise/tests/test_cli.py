import subprocess
import unittest


class CliTests(unittest.TestCase):
    def test_version_prints_project_version(self) -> None:
        result = subprocess.run(
            ["uv", "run", "mt", "--version"],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "0.1.0")


if __name__ == "__main__":
    unittest.main()
