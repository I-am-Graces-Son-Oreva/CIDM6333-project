import unittest
from typing import Any, cast

from fifth_pick.sources.quota import (
    QuotaBudget,
    QuotaError,
    QuotaSnapshot,
    estimate_odds_cost,
    parse_quota_headers,
)


class QuotaBudgetTests(unittest.TestCase):
    def test_positive_budget_is_accepted(self) -> None:
        self.assertEqual(QuotaBudget(credits=5).credits, 5)

    def test_non_positive_budget_fails_closed(self) -> None:
        for credits in (0, -1):
            with self.subTest(credits=credits), self.assertRaises(QuotaError):
                QuotaBudget(credits=credits)

    def test_boolean_budget_fails_closed(self) -> None:
        with self.assertRaises(QuotaError):
            QuotaBudget(credits=True)

    def test_non_integer_budget_fails_closed(self) -> None:
        for credits in (1.5, "5", None):
            with self.subTest(credits=credits), self.assertRaises(QuotaError):
                QuotaBudget(credits=cast(Any, credits))


class EstimateTests(unittest.TestCase):
    def test_estimate_is_markets_times_events(self) -> None:
        self.assertEqual(estimate_odds_cost(event_count=2, market_count=5), 10)
        self.assertEqual(estimate_odds_cost(event_count=0, market_count=5), 0)

    def test_negative_counts_fail_closed(self) -> None:
        with self.assertRaises(QuotaError):
            estimate_odds_cost(event_count=-1, market_count=5)
        with self.assertRaises(QuotaError):
            estimate_odds_cost(event_count=1, market_count=-5)

    def test_boolean_counts_fail_closed(self) -> None:
        with self.assertRaises(QuotaError):
            estimate_odds_cost(event_count=True, market_count=5)


class QuotaHeaderTests(unittest.TestCase):
    def test_headers_are_captured_case_insensitively(self) -> None:
        snapshot = parse_quota_headers(
            {
                "X-Requests-Remaining": "495",
                "x-requests-used": "5",
                "X-REQUESTS-LAST": "5",
            }
        )

        self.assertEqual(snapshot, QuotaSnapshot(remaining=495, used=5, last=5))

    def test_missing_headers_are_none(self) -> None:
        snapshot = parse_quota_headers({"content-type": "application/json"})

        self.assertEqual(snapshot, QuotaSnapshot(remaining=None, used=None, last=None))

    def test_partial_headers_are_captured(self) -> None:
        snapshot = parse_quota_headers({"x-requests-remaining": "12"})

        self.assertEqual(snapshot, QuotaSnapshot(remaining=12, used=None, last=None))

    def test_malformed_quota_header_fails_closed(self) -> None:
        with self.assertRaises(QuotaError):
            parse_quota_headers({"x-requests-remaining": "many"})

    def test_exhausted_only_when_remaining_is_zero(self) -> None:
        self.assertTrue(QuotaSnapshot(remaining=0, used=500, last=5).exhausted)
        self.assertFalse(QuotaSnapshot(remaining=1, used=499, last=5).exhausted)
        self.assertFalse(QuotaSnapshot(remaining=None, used=None, last=None).exhausted)

    def test_has_any_quota_data(self) -> None:
        self.assertTrue(QuotaSnapshot(remaining=None, used=None, last=5).has_any)
        self.assertFalse(QuotaSnapshot(remaining=None, used=None, last=None).has_any)


if __name__ == "__main__":
    unittest.main()
