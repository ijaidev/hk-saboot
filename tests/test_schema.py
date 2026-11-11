"""Schema parsing tests."""

from __future__ import annotations

import unittest
from datetime import timezone
from decimal import Decimal

from saboot.schema import format_inr, parse_datetime, parse_money


class SchemaTests(unittest.TestCase):
    def test_parse_money_variants(self) -> None:
        self.assertEqual(parse_money("₹1,240.50", "amount"), Decimal("1240.50"))
        self.assertEqual(parse_money("1,240", "amount"), Decimal("1240.00"))
        self.assertEqual(parse_money("INR 75", "amount"), Decimal("75.00"))
        self.assertEqual(parse_money("", "amount"), Decimal("0.00"))

    def test_parse_datetime_ist_and_z(self) -> None:
        ist = parse_datetime("2026-10-01T18:00:00+05:30", "when")
        self.assertIsNotNone(ist)
        self.assertEqual(ist.utcoffset().total_seconds(), 5.5 * 3600)  # type: ignore[union-attr]
        zulu = parse_datetime("2026-10-01T12:30:00Z", "when")
        self.assertEqual(zulu.tzinfo, timezone.utc)  # type: ignore[arg-type]

    def test_parse_datetime_naive_gets_ist(self) -> None:
        parsed = parse_datetime("2026-10-01 18:00:00", "when")
        self.assertEqual(parsed.utcoffset().total_seconds(), 5.5 * 3600)  # type: ignore[union-attr]

    def test_format_inr(self) -> None:
        self.assertEqual(format_inr(Decimal("75")), "₹75.00")
        self.assertEqual(format_inr(Decimal("1240.5")), "₹1,240.50")


if __name__ == "__main__":
    unittest.main()
