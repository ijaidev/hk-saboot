"""CSV bundle ingestion.

A bundle is a directory (or zip) with:
  meta.csv, orders.csv, earnings.csv, deductions.csv, incentives.csv
"""

from __future__ import annotations

import csv
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from ..schema import SabootError, Statement
from .segment import build_statement

REQUIRED_HEADERS: dict[str, set[str]] = {
    "meta.csv": {"statement_id", "platform", "worker_id", "period_start", "period_end"},
    "orders.csv": {"order_id", "accepted_at", "status"},
    "earnings.csv": {"order_id", "amount"},
    "deductions.csv": {"deduction_code", "amount", "applied_at"},
    "incentives.csv": {"target_orders", "target_amount", "achieved_orders", "amount_promised", "amount_paid"},
}


def _read_csv(path: Path) -> list[tuple[dict[str, Any], str]]:
    if not path.exists():
        raise SabootError(f"Missing required file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SabootError(f"{path}: file has no header row")
        headers = {h.strip() for h in reader.fieldnames if h is not None}
        required = REQUIRED_HEADERS.get(path.name, set())
        missing = required - headers
        if missing:
            raise SabootError(f"{path}: missing required columns: {', '.join(sorted(missing))}")

        rows: list[tuple[dict[str, Any], str]] = []
        for raw in reader:
            if raw is None:
                continue
            row = {
                (key.strip() if isinstance(key, str) else ""): (
                    value.strip() if isinstance(value, str) else value
                )
                for key, value in raw.items()
            }
            if not any(str(value).strip() for value in row.values() if value is not None):
                continue
            rows.append((row, f"{path.name}:{reader.line_num}"))
        return rows


def _find_bundle_root(root: Path) -> Path:
    if (root / "meta.csv").exists():
        return root
    children = [p for p in root.iterdir() if p.is_dir() and (p / "meta.csv").exists()]
    if len(children) == 1:
        return children[0]
    raise SabootError(f"{root}: could not find meta.csv in the bundle")


def _build_from_dir(root: Path) -> Statement:
    root = _find_bundle_root(root)
    required = ["meta.csv", "orders.csv"]
    for name in required:
        if not (root / name).exists():
            raise SabootError(f"{root}: missing required bundle file {name}")

    meta_rows = _read_csv(root / "meta.csv")
    order_rows = _read_csv(root / "orders.csv")
    earning_rows = _read_csv(root / "earnings.csv") if (root / "earnings.csv").exists() else []
    deduction_rows = _read_csv(root / "deductions.csv") if (root / "deductions.csv").exists() else []
    incentive_rows = _read_csv(root / "incentives.csv") if (root / "incentives.csv").exists() else []

    return build_statement(
        meta_rows=meta_rows,
        order_rows=order_rows,
        earning_rows=earning_rows,
        deduction_rows=deduction_rows,
        incentive_rows=incentive_rows,
    )


def read_bundle(path: str | Path) -> Statement:
    path = Path(path)
    if path.is_dir():
        return _build_from_dir(path)
    if path.suffix.lower() == ".zip" and path.is_file():
        with tempfile.TemporaryDirectory(prefix="saboot-bundle-") as tmp:
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    member_path = Path(member.filename)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise SabootError(f"Unsafe zip member path: {member.filename}")
                    archive.extract(member, tmp)
            return _build_from_dir(Path(tmp))
    raise SabootError(
        f"Statement bundle not found or not a directory/zip: {path}"
    )
