"""Ingestion tests: CSV bundle, zip bundle, text PDF, and error paths."""

from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from saboot.ingestion import read_bundle, read_pdf
from saboot.schema import SabootError, ValidationError
from tools.make_pdf import _bundle_lines, write_pdf

ROOT = Path(__file__).resolve().parents[1]
G01 = ROOT / "data" / "fixtures" / "golden" / "G01_duplicate" / "statement"


class IngestionTests(unittest.TestCase):
    def test_read_bundle(self) -> None:
        statement = read_bundle(G01)
        self.assertEqual(statement.meta.statement_id, "ST-G01_duplicate")
        self.assertEqual(statement.counts(), {"orders": 1, "earnings": 1, "deductions": 2, "incentives": 0})
        self.assertEqual(statement.orders_by_id["QD-1001"].restaurant_prep_minutes, 12)
        self.assertEqual(statement.source_for("order", "QD-1001"), "orders.csv:2")

    def test_read_zip_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "bundle.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for path in G01.iterdir():
                    archive.write(path, arcname=path.name)
            statement = read_bundle(zip_path)
            self.assertEqual(statement.counts()["orders"], 1)

    def test_missing_meta_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy(G01 / "orders.csv", root / "orders.csv")
            with self.assertRaises(SabootError):
                read_bundle(root)

    def test_duplicate_order_id_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in G01.iterdir():
                shutil.copy(path, root / path.name)
            with (root / "orders.csv").open("a", encoding="utf-8") as handle:
                handle.write(
                    "QD-1001,2026-10-01T18:00:00+05:30,2026-10-01T18:12:00+05:30,"
                    "2026-10-01T18:25:00+05:30,2026-10-01T18:40:00+05:30,12,3.0,"
                    "delivered,42.00,0.00,0.00,42.00\n"
                )
            with self.assertRaises(ValidationError):
                read_bundle(root)

    def test_text_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "g01.pdf"
            write_pdf(_bundle_lines(G01), pdf_path)
            statement = read_pdf(pdf_path)
            self.assertEqual(statement.meta.statement_id, "ST-G01_duplicate")
            self.assertEqual(statement.counts()["deductions"], 2)

    def test_pdf_without_meta_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "bad.pdf"
            write_pdf(["order|order_id=QD-1|accepted_at=2026-10-01T18:00:00+05:30|status=delivered"], pdf_path)
            with self.assertRaises(SabootError):
                read_pdf(pdf_path)

    def test_missing_bundle_path_raises(self) -> None:
        with self.assertRaises(SabootError):
            read_bundle("/tmp/does-not-exist-saboot")


if __name__ == "__main__":
    unittest.main()
