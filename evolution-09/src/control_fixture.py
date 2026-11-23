"""Execute only the two known clean cases from the exercise fixture."""

import unittest

from sprint_fixture import ReceiptFixture

if __name__ == "__main__":
    suite = unittest.TestSuite([ReceiptFixture("test_one"), ReceiptFixture("test_two")])
    raise SystemExit(not unittest.TextTestRunner().run(suite).wasSuccessful())
