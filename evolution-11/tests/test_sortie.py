import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sortie11 import Recorder  # noqa: E402  # ty: ignore[import-not-found]


class RecorderTests(unittest.TestCase):
    def test_records_refusal_without_exception_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recorder = Recorder(root, "synthetic-commit")
            with self.assertRaises(ValueError), recorder.span("A1", "execute_tool", "proposal"):
                raise ValueError("PRIVATE_TEST_CONTENT")
            line = (root / "traces/spans.jsonl").read_text()
            self.assertNotIn("PRIVATE_TEST_CONTENT", line)
            record = json.loads(line)
            self.assertEqual(record["attributes"]["error.type"], "ValueError")
            self.assertEqual(record["status"], "ERROR")
