"""Appeal generation and verification tests."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from saboot.appeal import generate_appeal, verify_appeal_text
from saboot.audit import audit_statement
from saboot.ingestion import read_bundle
from saboot.llm import LLMError, TemplateProvider, provider_from_env
from saboot.policy import PolicyBook
from saboot.schema import SabootError

ROOT = Path(__file__).resolve().parents[1]
POLICY = PolicyBook.load(ROOT / "data" / "policy" / "quickdrop_policy.json")
STATEMENT = read_bundle(ROOT / "data" / "fixtures" / "golden" / "G01_duplicate" / "statement")
RESULT = audit_statement(STATEMENT, POLICY)


class BadProvider:
    name = "bad-provider"

    def draft(self, prompt: str) -> str:
        return "You should sue the platform. The platform will refund ₹999.00. Swiggy owes you."


class AppealTests(unittest.TestCase):
    def test_template_appeal_passes_verifier(self) -> None:
        draft = generate_appeal(RESULT, ["C-001"], audit_id="test")
        self.assertEqual(draft.provider, "template")
        self.assertTrue(draft.verification["passed"], draft.verification["errors"])
        self.assertIn("QD-DED-001", draft.body)
        self.assertIn("₹75.00", draft.body)
        self.assertIn("request for review", draft.body)
        self.assertEqual(draft.total_amount, 75)
        self.assertEqual(len(draft.citations), 1)

    def test_no_claims_raises(self) -> None:
        with self.assertRaises(SabootError):
            generate_appeal(RESULT, [], audit_id="test")

    def test_needs_review_claim_cannot_be_appealed(self) -> None:
        result = copy.deepcopy(RESULT)
        result.claims[0].status = "needs_review"
        with self.assertRaises(SabootError):
            generate_appeal(result, ["C-001"], audit_id="test")

    def test_bad_provider_falls_back_to_template(self) -> None:
        draft = generate_appeal(RESULT, ["C-001"], audit_id="test", provider=BadProvider())
        self.assertEqual(draft.provider, "template")
        self.assertTrue(draft.verification["passed"])
        self.assertNotIn("sue", draft.body.lower())
        self.assertNotIn("999", draft.body)

    def test_unsupported_amount_rejected(self) -> None:
        report = verify_appeal_text("Please review ₹999.00 for claim C-001.", RESULT.claims, RESULT)
        self.assertFalse(report["passed"])
        self.assertTrue(any("unsupported amount" in error for error in report["errors"]))

    def test_unsupported_citation_rejected(self) -> None:
        report = verify_appeal_text("Policy QD-FAKE-999 supports this.", RESULT.claims, RESULT)
        self.assertFalse(report["passed"])
        self.assertTrue(any("unsupported policy citation" in error for error in report["errors"]))

    def test_template_provider_is_default_without_key(self) -> None:
        provider = provider_from_env()
        self.assertEqual(provider.name, "template")
        with self.assertRaises(LLMError):
            TemplateProvider().draft("hello")


if __name__ == "__main__":
    unittest.main()
