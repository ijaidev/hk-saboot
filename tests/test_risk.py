"""Risk-score presentation tests."""

from __future__ import annotations

import unittest

from saboot.webapp.risk import compute_risk


def audit(potential: float, expected: float, claims: int, review: int) -> dict:
    return {
        "summary": {
            "total_potential": potential,
            "claim_count": claims,
            "needs_review_count": 0,
            "review_item_count": review,
        },
        "reconciliation": {"summary": {"total_expected": expected}},
    }


class RiskTests(unittest.TestCase):
    def test_high_risk_for_duplicate_case(self) -> None:
        risk = compute_risk(audit(75, 42, 1, 0))
        self.assertEqual(risk["score"], 83)
        self.assertEqual(risk["band"], "high")

    def test_low_risk_for_clean_case(self) -> None:
        risk = compute_risk(audit(0, 300, 0, 0))
        self.assertEqual(risk["score"], 0)
        self.assertEqual(risk["band"], "low")

    def test_medium_risk(self) -> None:
        risk = compute_risk(audit(300, 1000, 2, 0))
        self.assertEqual(risk["band"], "medium")
        self.assertEqual(risk["score"], 46)

    def test_review_items_raise_priority(self) -> None:
        without = compute_risk(audit(0, 100, 0, 0))
        with_review = compute_risk(audit(0, 100, 0, 2))
        self.assertGreater(with_review["score"], without["score"])


if __name__ == "__main__":
    unittest.main()
