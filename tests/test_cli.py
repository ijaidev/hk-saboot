"""CLI integration tests."""

from __future__ import annotations

import contextlib
import csv
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from saboot.cli import main
from tools.make_pdf import _bundle_lines, write_pdf

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "fixtures" / "golden"
POLICY = ROOT / "data" / "policy" / "quickdrop_policy.json"


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class CLITests(unittest.TestCase):
    def test_audit_csv_both_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_cli(
                [
                    "audit",
                    "--bundle",
                    str(GOLDEN / "G01_duplicate" / "statement"),
                    "--policy",
                    str(POLICY),
                    "--out",
                    tmp,
                ]
            )
            self.assertEqual(code, 0, err)
            self.assertIn("Potential: ₹75.00", out)
            data = json.loads((Path(tmp) / "audit.json").read_text())
            self.assertEqual(data["summary"]["claim_count"], 1)
            self.assertTrue((Path(tmp) / "audit.md").exists())

    def test_audit_json_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli(
                [
                    "audit",
                    "--bundle",
                    str(GOLDEN / "F01_clean" / "statement"),
                    "--policy",
                    str(POLICY),
                    "--out",
                    tmp,
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, err)
            self.assertTrue((Path(tmp) / "audit.json").exists())
            self.assertFalse((Path(tmp) / "audit.md").exists())

    def test_strict_fair_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli(
                [
                    "audit",
                    "--bundle",
                    str(GOLDEN / "F01_clean" / "statement"),
                    "--policy",
                    str(POLICY),
                    "--out",
                    tmp,
                    "--strict",
                ]
            )
            self.assertEqual(code, 0, err)

    def test_strict_unknown_code_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            shutil.copytree(GOLDEN / "G01_duplicate" / "statement", bundle)
            deductions = bundle / "deductions.csv"
            with deductions.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["deduction_code"] = "MYSTERY"
            with deductions.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            code, out, err = run_cli(
                [
                    "audit",
                    "--bundle",
                    str(bundle),
                    "--policy",
                    str(POLICY),
                    "--out",
                    str(Path(tmp) / "out"),
                    "--strict",
                ]
            )
            self.assertEqual(code, 1, err)
            self.assertIn("Review items: 1", out)

    def test_audit_text_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "g01.pdf"
            write_pdf(_bundle_lines(GOLDEN / "G01_duplicate" / "statement"), pdf_path)
            code, out, err = run_cli(
                [
                    "audit",
                    "--pdf",
                    str(pdf_path),
                    "--policy",
                    str(POLICY),
                    "--out",
                    str(Path(tmp) / "out"),
                ]
            )
            self.assertEqual(code, 0, err)
            self.assertIn("text_pdf", out)

    def test_missing_bundle_returns_input_error(self) -> None:
        code, _, err = run_cli(
            ["audit", "--bundle", "/tmp/saboot-does-not-exist", "--policy", str(POLICY)]
        )
        self.assertEqual(code, 2)
        self.assertIn("Saboot error", err)


if __name__ == "__main__":
    unittest.main()
