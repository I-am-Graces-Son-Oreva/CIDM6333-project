"""The E5 description pin observes the declaration attached to the tool."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SORTIE = Path(__file__).resolve().parents[1] / "evolution-05/sortie-05"


class DescriptionPinTests(unittest.TestCase):
    def test_same_scope_different_description_is_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("scopes.py", "server.py", "pin.py", "tool-pins.json"):
                (root / name).write_bytes((SORTIE / name).read_bytes())
            manifest = root / "server.py"
            text = manifest.read_text()
            self.assertIn('description="Write a note.', text)
            manifest.write_text(
                text.replace('description="Write a note.', 'description="Store a note.')
            )
            result = subprocess.run(
                [sys.executable, "-B", "pin.py"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("write_note", result.stdout)
