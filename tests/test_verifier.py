"""Verifier negative tests: every unsupported claim must be rejected."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from saboot.audit import audit_statement
from saboot.ingestion import read_bundle
from saboot.policy import PolicyBook
from saboot.verifier import verify_claim, verify_claims

ROOT = Path(__file__).resolve().parents[1]
POLICY = PolicyBook.load(ROOT / "data" / "policy" / "quickdrop_policy.json")
STATEMENT = read_bundle(ROOT / "data" / "fixtures" / "golden" / "G01_duplicate" / "statement")
RESULT = audit_statement(STATEMENT, POLICY)


class VerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.claim = copy.deepcopy(RESULT.claims[0])

    def assert_rejected(self, claim, needle: str) -> None:
        errors = verify_claim(claim, STATEMENT, POLICY)
        self.assertTrue(errors, "expected verifier errors")
        self.assertTrue(
            any(needle.lower() in error.lower() for error in errors),
            f"expected {needle!r} in {errors}",
        )

    def test_valid_claim_passes(self) -> None:
        self.assertEqual(verify_claim(self.claim, STATEMENT, POLICY), [])

    def test_rejects_unsupported_amount(self) -> None:
        self.claim.amount = self.claim.amount + 1
        self.assert_rejected(self.claim, "components sum")

    def test_rejects_fake_order_id(self) -> None:
        self.claim.order_ids.append("QD-FAKE")
        self.assert_rejected(self.claim, "does not exist")

    def test_rejects_fake_deduction_id(self) -> None:
        self.claim.deduction_ids.append("D-FAKE")
        self.assert_rejected(self.claim, "does not exist")

    def test_rejects_fabricated_timestamp(self) -> None:
        self.claim.evidence["timestamps"]["D-0001"] = "2026-10-01T23:59:00+05:30"
        self.assert_rejected(self.claim, "not present in the statement")

    def test_rejects_unknown_policy_clause(self) -> None:
        self.claim.policy_clause_id = "QD-FAKE"
        self.claim.policy_clause = None
        self.assert_rejected(self.claim, "does not exist")

    def test_rejects_legal_advice(self) -> None:
        self.claim.reason = "You should sue the platform and go to court."
        self.assert_rejected(self.claim, "legal-advice")

    def test_rejects_outcome_promise(self) -> None:
        self.claim.reason = "The platform will refund you within seven days."
        self.assert_rejected(self.claim, "outcome promise")

    def test_rejects_real_brand_name(self) -> None:
        self.claim.reason = "This Swiggy statement has a duplicate charge."
        self.assert_rejected(self.claim, "real platform brand")

    def test_rejects_missing_clause(self) -> None:
        self.claim.policy_clause_id = None
        self.claim.policy_clause = None
        self.assert_rejected(self.claim, "no policy clause")

    def test_verify_claims_marks_failure_as_needs_review(self) -> None:
        self.claim.amount = self.claim.amount + 1
        report = verify_claims([self.claim], STATEMENT, POLICY)
        self.assertFalse(report["passed"])
        self.assertEqual(self.claim.status, "needs_review")
        self.assertTrue(self.claim.verification_errors)


if __name__ == "__main__":
    unittest.main()
