import unittest

from evals.gate import grade


class GateTests(unittest.TestCase):
    def test_rejects_wrong_or_non_boolean_answer(self):
        self.assertTrue(grade(False, False))
        self.assertFalse(grade(False, True))
        self.assertFalse(grade(False, 0))
