"""Include the final project in the repository's existing unittest gate."""

from pathlib import Path
from unittest import TestLoader, TestSuite

FIFTH_PICK_TESTS = Path(__file__).resolve().parents[1] / "final-project" / "tests"


def load_tests(loader: TestLoader, _tests: TestSuite, _pattern: str | None) -> TestSuite:
    modules = [f"tests.{path.stem}" for path in sorted(FIFTH_PICK_TESTS.glob("test_*.py"))]
    if not modules:
        raise RuntimeError(f"No Fifth Pick tests found in {FIFTH_PICK_TESTS}")
    return loader.loadTestsFromNames(modules)
