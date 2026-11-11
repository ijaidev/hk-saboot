"""PDF export test: verify the appeal and evidence pack are extractable."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from saboot.appeal import generate_appeal
from saboot.audit import audit_statement
from saboot.ingestion import read_bundle
from saboot.pdf_export import export_appeal_pdf
from saboot.policy import PolicyBook

ROOT = Path(__file__).resolve().parents[1]
POLICY = PolicyBook.load(ROOT / "data" / "policy" / "quickdrop_policy.json")
STATEMENT = read_bundle(ROOT / "data" / "fixtures" / "golden" / "G01_duplicate" / "statement")
RESULT = audit_statement(STATEMENT, POLICY)


@unittest.skipUnless(shutil.which("pdftotext"), "pdftotext is required for PDF extraction tests")
class PdfExportTests(unittest.TestCase):
    def test_appeal_pdf_contains_claim_and_citation(self) -> None:
        draft = generate_appeal(RESULT, ["C-001"], audit_id="test")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "appeal.pdf"
            export_appeal_pdf(draft, RESULT, path)
            self.assertTrue(path.read_bytes().startswith(b"%PDF-1.4"))
            text = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        self.assertIn("SABOOT - REQUEST FOR REVIEW", text)
        self.assertIn("Rs. 75.00", text)
        self.assertIn("QD-DED-001", text)
        self.assertIn("Verifier: PASS", text)
        self.assertIn("Subject: Request for review", text)
        self.assertIn("Source quote", text)


if __name__ == "__main__":
    unittest.main()
