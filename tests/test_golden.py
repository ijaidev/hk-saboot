"""Golden-fixture evaluation tests: 20 hand-authored cases."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from saboot.audit import audit_statement
from saboot.ingestion import read_bundle
from saboot.policy import PolicyBook

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "fixtures" / "golden"
POLICY = PolicyBook.load(ROOT / "data" / "policy" / "quickdrop_policy.json")


class GoldenFixtureTests(unittest.TestCase):
    def test_all_golden_fixtures(self) -> None:
        fixtures = sorted(path for path in GOLDEN.iterdir() if path.is_dir())
        self.assertEqual(len(fixtures), 20)

        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                expected = json.loads((fixture / "expected.json").read_text())
                statement = read_bundle(fixture / "statement")
                result = audit_statement(statement, POLICY)

                self.assertTrue(
                    result.verification["passed"],
                    f"verifier failed: {result.verification['errors']}",
                )
                self.assertEqual(
                    len(result.claims),
                    expected["expected_claim_count"],
                    f"claims: {[(c.claim_type, float(c.amount)) for c in result.claims]}",
                )
                self.assertAlmostEqual(
                    result.summary()["total_potential"],
                    expected["expected_total"],
                    places=2,
                )
                self.assertEqual(
                    len(result.review_items),
                    expected["expected_review_items"],
                    f"review: {[r.review_type for r in result.review_items]}",
                )

                remaining = list(result.claims)
                for expected_claim in expected["expected_claims"]:
                    match = next(
                        (
                            claim
                            for claim in remaining
                            if claim.claim_type == expected_claim["type"]
                            and abs(float(claim.amount) - float(expected_claim["amount"])) < 0.01
                            and set(expected_claim["order_ids"]).issubset(set(claim.order_ids))
                        ),
                        None,
                    )
                    self.assertIsNotNone(
                        match,
                        f"missing expected claim {expected_claim}; actual="
                        f"{[(c.claim_type, float(c.amount), c.order_ids) for c in result.claims]}",
                    )
                    remaining.remove(match)  # type: ignore[arg-type]
                self.assertEqual(remaining, [])


if __name__ == "__main__":
    unittest.main()
