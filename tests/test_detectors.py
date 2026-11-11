"""Detector and allocation tests."""

from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from saboot.audit import audit_statement
from saboot.ingestion import read_bundle
from saboot.policy import PolicyBook

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "fixtures" / "golden"
POLICY = PolicyBook.load(ROOT / "data" / "policy" / "quickdrop_policy.json")


def run(name: str):
    statement = read_bundle(GOLDEN / name / "statement")
    return audit_statement(statement, POLICY)


class DetectorTests(unittest.TestCase):
    def test_duplicate(self) -> None:
        result = run("G01_duplicate")
        self.assertEqual(len(result.claims), 1)
        claim = result.claims[0]
        self.assertEqual(claim.claim_type, "duplicate_deduction")
        self.assertEqual(claim.amount, Decimal("75.00"))
        self.assertEqual(result.allocation_remaining["D-0001"], 75.0)
        self.assertEqual(result.allocation_remaining["D-0002"], 0.0)

    def test_over_cap_late(self) -> None:
        result = run("G02_over_cap_late")
        self.assertEqual([c.claim_type for c in result.claims], ["over_cap_deduction"])
        self.assertEqual(result.claims[0].amount, Decimal("50.00"))
        self.assertEqual(result.allocation_remaining["D-0001"], 100.0)

    def test_restaurant_delay(self) -> None:
        result = run("G03_restaurant_delay")
        self.assertEqual([c.claim_type for c in result.claims], ["restaurant_delay_penalty"])
        self.assertEqual(result.claims[0].amount, Decimal("50.00"))
        self.assertEqual(result.allocation_remaining["D-0001"], 0.0)

    def test_incentive_shortfall(self) -> None:
        result = run("G04_incentive_shortfall")
        self.assertEqual([c.claim_type for c in result.claims], ["incentive_shortfall"])
        self.assertEqual(result.claims[0].amount, Decimal("50.00"))

    def test_missing_earning(self) -> None:
        result = run("G05_missing_earning")
        self.assertEqual([c.claim_type for c in result.claims], ["missing_earning"])
        self.assertEqual(result.claims[0].amount, Decimal("42.00"))

    def test_duplicate_and_over_cap_allocation(self) -> None:
        result = run("G06_duplicate_and_over_cap")
        self.assertEqual(
            [(c.claim_type, c.amount) for c in result.claims],
            [("duplicate_deduction", Decimal("150.00")), ("over_cap_deduction", Decimal("50.00"))],
        )
        self.assertEqual(result.allocation_remaining["D-0001"], 100.0)
        self.assertEqual(result.allocation_remaining["D-0002"], 0.0)

    def test_delay_and_over_cap_allocation(self) -> None:
        result = run("G07_delay_and_over_cap")
        self.assertEqual(
            [(c.claim_type, c.amount) for c in result.claims],
            [("over_cap_deduction", Decimal("50.00")), ("restaurant_delay_penalty", Decimal("100.00"))],
        )
        self.assertEqual(result.allocation_remaining["D-0001"], 0.0)

    def test_multiple_claim_types(self) -> None:
        result = run("G12_multiple")
        self.assertEqual(
            [(c.claim_type, c.amount) for c in result.claims],
            [
                ("duplicate_deduction", Decimal("75.00")),
                ("restaurant_delay_penalty", Decimal("50.00")),
                ("incentive_shortfall", Decimal("50.00")),
                ("missing_earning", Decimal("42.00")),
            ],
        )
        self.assertEqual(result.summary()["total_potential"], 217.0)
        self.assertTrue(result.verification["passed"])

    def test_fair_fixtures_have_no_claims(self) -> None:
        for fixture in sorted(GOLDEN.glob("F*")):
            with self.subTest(fixture=fixture.name):
                result = run(fixture.name)
                self.assertEqual(result.claims, [])
                self.assertEqual(result.review_items, [])
                self.assertEqual(result.summary()["total_potential"], 0.0)


if __name__ == "__main__":
    unittest.main()
