import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from deploy import digest


class ArtifactTests(unittest.TestCase):
    def test_byte_changes_change_artifact_hash(self):
        with TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "artifact.whl"
            wheel.write_bytes(b"first")
            first = digest(wheel)
            wheel.write_bytes(b"second")
            self.assertNotEqual(first, digest(wheel))

    def test_rollback_refuses_changed_bytes_before_installing(self):
        import json
        from unittest.mock import patch

        from deploy import rollback

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            wheel = "fifth_pick-0.1.0-py3-none-any.whl"
            artifact = root / "artifacts" / "original" / wheel
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"different bytes")
            event = dict(
                event="release",
                ok=True,
                version="0.1.0",
                sha256="original",
                wheel=wheel,
                commit="fixture",
            )
            (root / "release-ledger.jsonl").write_text(json.dumps(event) + "\n")
            with (
                patch("deploy.install") as install,
                self.assertRaisesRegex(ValueError, "stored release hash mismatch"),
            ):
                rollback(root, "0.1.0")
            install.assert_not_called()
