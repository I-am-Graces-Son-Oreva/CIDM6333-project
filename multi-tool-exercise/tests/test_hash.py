import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from multitool.hash import hash_file, hash_text


class HashTests(unittest.TestCase):
    def test_sha256_hashes_utf8_text(self) -> None:
        self.assertEqual(
            hash_text("sha256", "café"),
            hashlib.sha256("café".encode("utf-8")).hexdigest(),
        )

    def test_md5_hashes_text(self) -> None:
        self.assertEqual(
            hash_text("md5", "hello"),
            hashlib.md5(b"hello", usedforsecurity=False).hexdigest(),
        )

    def test_hash_file_uses_file_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.bin"
            path.write_bytes(b"hello\x00world")

            self.assertEqual(
                hash_file("sha256", path),
                hashlib.sha256(b"hello\x00world").hexdigest(),
            )

    def test_cli_hashes_file_and_verifies_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.txt"
            path.write_text("hello", encoding="utf-8")
            digest = hashlib.sha256(b"hello").hexdigest()
            result = subprocess.run(
                ["uv", "run", "mt", "hash", "sha256", "--file", str(path), "--verify", digest],
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), digest)

    def test_cli_exits_one_when_digest_does_not_match(self) -> None:
        result = subprocess.run(
            ["uv", "run", "mt", "hash", "sha256", "hello", "--verify", "0" * 64],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 1)

    def test_cli_rejects_missing_or_multiple_input_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.txt"
            path.write_text("hello", encoding="utf-8")
            commands = (
                ["uv", "run", "mt", "hash", "sha256"],
                ["uv", "run", "mt", "hash", "sha256", "hello", "--file", str(path)],
            )

            for command in commands:
                with self.subTest(command=command):
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        check=False,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)

    def test_cli_rejects_unknown_algorithm(self) -> None:
        result = subprocess.run(
            ["uv", "run", "mt", "hash", "sha1", "hello"],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 2)

    def test_cli_keeps_existing_codec_command_working(self) -> None:
        result = subprocess.run(
            ["uv", "run", "mt", "codec", "hex", "encode", "hello"],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "68656c6c6f")

    def test_cli_reports_missing_file_as_invalid_input(self) -> None:
        result = subprocess.run(
            ["uv", "run", "mt", "hash", "sha256", "--file", "missing-hash-input"],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
