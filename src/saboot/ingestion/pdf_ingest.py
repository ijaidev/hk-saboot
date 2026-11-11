"""Text-PDF ingestion for line-oriented QuickDrop exports.

Each record is one line:
  record_type|key=value|key=value|...

This is a text PDF (not a scan). Image PDFs would require OCR, which is a
stretch goal and intentionally not part of the M0-M2 checkpoint.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..schema import SabootError, Statement
from .segment import build_statement

RECORD_TYPES = {"meta", "order", "earning", "deduction", "incentive"}


def _parse_line(line: str, line_no: int) -> tuple[str, dict[str, Any]] | None:
    text = line.replace("\f", "").strip()
    if not text:
        return None
    if "|" not in text:
        # Headers/footers from the PDF layout are ignored.
        return None
    parts = [part.strip() for part in text.split("|")]
    record_type = parts[0].strip().lower()
    if record_type not in RECORD_TYPES:
        # Ignore human-readable headers, but reject malformed data-looking rows.
        if "=" in text:
            raise SabootError(f"PDF line {line_no}: unknown record type {record_type!r}")
        return None
    fields: dict[str, Any] = {}
    for part in parts[1:]:
        if "=" not in part:
            raise SabootError(f"PDF line {line_no}: expected key=value, got {part!r}")
        key, value = part.split("=", 1)
        key = key.strip()
        if not key:
            raise SabootError(f"PDF line {line_no}: empty key")
        fields[key] = value.strip()
    return record_type, fields


def read_pdf(path: str | Path) -> Statement:
    path = Path(path)
    if not path.exists():
        raise SabootError(f"PDF not found: {path}")
    if shutil.which("pdftotext") is None:
        raise SabootError(
            "pdftotext is not installed. Install poppler-utils, or use the CSV bundle path."
        )
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SabootError(f"pdftotext timed out reading {path}") from exc
    if result.returncode != 0:
        raise SabootError(f"pdftotext failed for {path}: {result.stderr.strip()}")

    grouped: dict[str, list[tuple[dict[str, Any], str]]] = {
        key: [] for key in RECORD_TYPES
    }
    for line_no, line in enumerate(result.stdout.splitlines(), start=1):
        parsed = _parse_line(line, line_no)
        if parsed is None:
            continue
        record_type, fields = parsed
        grouped[record_type].append((fields, f"pdf:{line_no}"))

    if not grouped["meta"]:
        raise SabootError(
            f"{path}: no meta record found. The PDF must be a line-oriented QuickDrop text export."
        )
    if not grouped["order"]:
        raise SabootError(f"{path}: no order records found")

    return build_statement(
        meta_rows=grouped["meta"],
        order_rows=grouped["order"],
        earning_rows=grouped["earning"],
        deduction_rows=grouped["deduction"],
        incentive_rows=grouped["incentive"],
    )
