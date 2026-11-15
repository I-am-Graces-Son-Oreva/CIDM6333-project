import json
import unittest

from fifth_pick.errors import ReceiptError
from fifth_pick.receipts import REDACTION_MARKER, Receipt, redact_text

SECRET = "odds-secret-123"
SECRET_URL = (
    "https://api.the-odds-api.com/v4/sports/us_dfs/odds/"
    f"?apiKey={SECRET}&regions=us_dfs&markets=player_points"
)


def make_receipt(
    *,
    timestamp: str = "2026-11-15T17:00:00+00:00",
    event: str = "BOARD_RETRIEVED",
    result: str = "OK",
    subject: str = "nba:2026-11-15:lal-dal",
    source: str = "the-odds-api:us_dfs",
    reason: str | None = None,
    run_id: str = "run-20261115",
    event_key: str = "board-retrieved-1",
) -> Receipt:
    return Receipt(
        timestamp=timestamp,
        event=event,
        result=result,
        subject=subject,
        source=source,
        reason=reason,
        run_id=run_id,
        event_key=event_key,
    )


class ReceiptTests(unittest.TestCase):
    def test_receipt_requires_core_fields(self) -> None:
        with self.assertRaises(ReceiptError):
            make_receipt(timestamp="")
        with self.assertRaises(ReceiptError):
            make_receipt(event="")
        with self.assertRaises(ReceiptError):
            make_receipt(result="")
        with self.assertRaises(ReceiptError):
            make_receipt(subject="")
        with self.assertRaises(ReceiptError):
            make_receipt(source="")
        with self.assertRaises(ReceiptError):
            make_receipt(run_id="")
        with self.assertRaises(ReceiptError):
            make_receipt(event_key="")
        with self.assertRaises(ReceiptError):
            make_receipt(reason="")

    def test_receipt_serializes_core_fields_and_event_key(self) -> None:
        record = make_receipt(reason="PLAYER_IDENTITY_UNRESOLVED").to_dict()

        self.assertEqual(
            set(record),
            {
                "timestamp",
                "event",
                "result",
                "subject",
                "source",
                "reason",
                "run_id",
                "event_key",
            },
        )
        self.assertEqual(record["event_key"], "board-retrieved-1")
        self.assertEqual(record["reason"], "PLAYER_IDENTITY_UNRESOLVED")

    def test_receipt_redacts_api_key_and_url_query(self) -> None:
        receipt = make_receipt(source=SECRET_URL, subject=f"board for {SECRET}")

        redacted = receipt.redacted([SECRET])
        record = redacted.to_dict()
        serialized = json.dumps(record)

        self.assertNotIn(SECRET, serialized)
        self.assertIn(REDACTION_MARKER, redacted.source)
        self.assertIn("apiKey=" + REDACTION_MARKER, redacted.source)
        self.assertIn("regions=us_dfs", redacted.source)
        self.assertIn("markets=player_points", redacted.source)
        self.assertIn(REDACTION_MARKER, redacted.subject)
        self.assertEqual(receipt.source, SECRET_URL)
        self.assertEqual(receipt.subject, f"board for {SECRET}")

    def test_receipt_redaction_accepts_iterable_secrets_once(self) -> None:
        receipt = make_receipt(
            source=SECRET_URL,
            subject=f"board for {SECRET}",
            result=SECRET,
        )

        redacted = receipt.redacted(secret for secret in [SECRET])

        self.assertNotIn(SECRET, json.dumps(redacted.to_dict()))

    def test_url_query_sensitive_values_are_redacted_without_explicit_secret(self) -> None:
        text = "https://example.test/path?token=unlisted&region=us_dfs"

        self.assertEqual(
            redact_text(text),
            "https://example.test/path?token=" + REDACTION_MARKER + "&region=us_dfs",
        )

    def test_redact_text_replaces_exact_supplied_secret(self) -> None:
        self.assertEqual(
            redact_text(f"prefix {SECRET} suffix", [SECRET]),
            f"prefix {REDACTION_MARKER} suffix",
        )
