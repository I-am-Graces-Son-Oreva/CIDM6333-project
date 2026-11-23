"""Predetermined exercise fixture. Only the explicit sortie command loads it."""

import unittest


class ReceiptFixture(unittest.TestCase):
    def test_one(self):
        self.assertEqual(1 + 1, 2)

    def test_two(self):
        self.assertEqual(2 + 2, 4)

    def test_three(self):
        self.assertEqual(2 + 3, 4)


if __name__ == "__main__":
    unittest.main()
