import subprocess
import unittest

from multitool.codec import decode, encode


class CodecTests(unittest.TestCase):
    def test_unicode_round_trips_for_each_scheme(self) -> None:
        for scheme in ("rot13", "base64", "hex"):
            with self.subTest(scheme=scheme):
                encoded = encode(scheme, "café")
                self.assertEqual(decode(scheme, encoded), "café")

    def test_unknown_scheme_exits_two(self) -> None:
        result = subprocess.run(
            ["uv", "run", "mt", "codec", "unknown", "encode", "text"],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 2)

    def test_unknown_direction_exits_two(self) -> None:
        result = subprocess.run(
            ["uv", "run", "mt", "codec", "rot13", "transform", "text"],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 2)
