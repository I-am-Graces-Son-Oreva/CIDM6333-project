import unittest

from evals.gate import grade


class GateTests(unittest.TestCase):
    def test_rejects_wrong_or_non_boolean_answer(self):
        self.assertTrue(grade(False, False))
        self.assertFalse(grade(False, True))
        self.assertFalse(grade(False, 0))

    def test_hollow_check_detects_type_only_assertion(self):
        from evals.gate import constant_verdicts

        self.assertEqual(constant_verdicts(False, "equals"), (True, False))
        self.assertEqual(constant_verdicts(False, "boolean"), (True, True))
