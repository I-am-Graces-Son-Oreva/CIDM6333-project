"""Shared unittest namespace for root coursework and moved Fifth Pick tests."""

from pathlib import Path

FIFTH_PICK_TESTS = Path(__file__).resolve().parents[1] / "final-project" / "tests"
__path__.append(str(FIFTH_PICK_TESTS))
