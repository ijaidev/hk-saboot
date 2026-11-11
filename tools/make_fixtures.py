#!/usr/bin/env python3
"""Materialize the 20 hand-authored golden fixtures.

The scenarios are explicit and deterministic. This script only writes them to
CSV/JSON so the fixtures are reproducible and reviewable.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "fixtures" / "golden"
IST = "+05:30"

META_HEADERS = [
    "statement_id",
    "platform",
    "worker_id",
    "period_start",
    "period_end",
    "currency",
    "jurisdiction",
]
ORDER_HEADERS = [
    "order_id",
    "accepted_at",
    "picked_up_at",
    "delivered_at",
    "promised_delivery_at",
    "restaurant_prep_minutes",
    "distance_km",
    "status",
    "base_pay",
    "surge_pay",
    "tip",
    "total_pay",
]
EARNING_HEADERS = ["earning_id", "order_id", "earning_type", "amount", "description"]
DEDUCTION_HEADERS = [
    "deduction_id",
    "order_id",
    "deduction_code",
    "description",
    "amount",
    "applied_at",
]
INCENTIVE_HEADERS = [
    "incentive_id",
    "name",
    "target_orders",
    "target_amount",
    "achieved_orders",
    "amount_promised",
    "amount_paid",
    "qualifying_order_ids",
]


def _iso(day: int, hour: int, minute: int) -> str:
    return f"2026-10-{day:02d}T{hour:02d}:{minute:02d}:00{IST}"


def make_order(
    order_id: str,
    total: int | float,
    *,
    prep: int = 10,
    status: str = "delivered",
    day: int = 1,
    hour: int = 18,
    minute: int = 0,
    delivery_minutes: int = 13,
    promise_minutes: int = 40,
    base: int | float | None = None,
    surge: int = 0,
    tip: int = 0,
    distance: float = 3.0,
) -> dict[str, str]:
    accepted = datetime(2026, 10, day, hour, minute)
    picked_up = accepted + timedelta(minutes=prep)
    delivered = picked_up + timedelta(minutes=delivery_minutes)
    promised = accepted + timedelta(minutes=promise_minutes)
    total_dec = Decimal(str(total))
    base_dec = (
        Decimal(str(base))
        if base is not None
        else total_dec - Decimal(str(surge)) - Decimal(str(tip))
    )
    return {
        "order_id": order_id,
        "accepted_at": _iso(day, hour, minute),
        "picked_up_at": picked_up.strftime(f"2026-10-%dT%H:%M:00{IST}"),
        "delivered_at": (
            delivered.strftime(f"2026-10-%dT%H:%M:00{IST}")
            if status == "delivered"
            else ""
        ),
        "promised_delivery_at": promised.strftime(f"2026-10-%dT%H:%M:00{IST}"),
        "restaurant_prep_minutes": str(prep),
        "distance_km": f"{distance:.1f}",
        "status": status,
        "base_pay": f"{base_dec:.2f}",
        "surge_pay": f"{Decimal(str(surge)):.2f}",
        "tip": f"{Decimal(str(tip)):.2f}",
        "total_pay": f"{total_dec:.2f}",
    }


def make_earning(
    earning_id: str,
    order_id: str,
    amount: int | float,
    *,
    earning_type: str = "base",
    description: str = "Base pay",
) -> dict[str, str]:
    return {
        "earning_id": earning_id,
        "order_id": order_id,
        "earning_type": earning_type,
        "amount": f"{Decimal(str(amount)):.2f}",
        "description": description,
    }


def make_deduction(
    deduction_id: str,
    order_id: str,
    code: str,
    amount: int | float,
    *,
    day: int = 1,
    hour: int = 19,
    minute: int = 10,
    description: str | None = None,
) -> dict[str, str]:
    labels = {
        "LATE": "Late delivery penalty",
        "CANCEL": "Cancellation penalty",
    }
    return {
        "deduction_id": deduction_id,
        "order_id": order_id,
        "deduction_code": code,
        "description": description or labels.get(code, "Platform deduction"),
        "amount": f"{Decimal(str(amount)):.2f}",
        "applied_at": _iso(day, hour, minute),
    }


def make_incentive(
    incentive_id: str,
    name: str,
    target_orders: int,
    promised: int | float,
    paid: int | float,
    *,
    achieved: int | None = None,
) -> dict[str, str]:
    return {
        "incentive_id": incentive_id,
        "name": name,
        "target_orders": str(target_orders),
        "target_amount": "0.00",
        "achieved_orders": str(target_orders if achieved is None else achieved),
        "amount_promised": f"{Decimal(str(promised)):.2f}",
        "amount_paid": f"{Decimal(str(paid)):.2f}",
        "qualifying_order_ids": "",
    }


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def _claim(claim_type: str, amount: int | float, order_ids: list[str]) -> dict[str, Any]:
    return {
        "type": claim_type,
        "amount": float(amount),
        "order_ids": order_ids,
        "status": "ready",
    }


def write_fixture(
    fixture_id: str,
    description: str,
    *,
    orders: list[dict[str, str]],
    earnings: list[dict[str, str]],
    deductions: list[dict[str, str]] | None = None,
    incentives: list[dict[str, str]] | None = None,
    expected_claims: list[dict[str, Any]] | None = None,
) -> None:
    root = GOLDEN / fixture_id
    statement = root / "statement"
    meta = {
        "statement_id": f"ST-{fixture_id}",
        "platform": "QuickDrop",
        "worker_id": "W-1042",
        "period_start": f"2026-10-01T00:00:00{IST}",
        "period_end": f"2026-10-31T23:59:59{IST}",
        "currency": "INR",
        "jurisdiction": "IN-KA",
    }
    _write_csv(statement / "meta.csv", META_HEADERS, [meta])
    _write_csv(statement / "orders.csv", ORDER_HEADERS, orders)
    _write_csv(statement / "earnings.csv", EARNING_HEADERS, earnings)
    _write_csv(statement / "deductions.csv", DEDUCTION_HEADERS, deductions or [])
    _write_csv(statement / "incentives.csv", INCENTIVE_HEADERS, incentives or [])

    claims = expected_claims or []
    expected = {
        "fixture_id": fixture_id,
        "description": description,
        "expected_claims": claims,
        "expected_claim_count": len(claims),
        "expected_total": round(sum(float(c["amount"]) for c in claims), 2),
        "expected_review_items": 0,
    }
    (root / "expected.json").write_text(
        json.dumps(expected, indent=2) + "\n", encoding="utf-8"
    )
    lines = [f"# {fixture_id}", "", description, "", "## Expected claims", ""]
    if not claims:
        lines.append("None. This is a fair/settled statement.")
    else:
        for claim in claims:
            lines.append(
                f"- `{claim['type']}` — ₹{claim['amount']:.2f} — "
                f"orders: {', '.join(claim['order_ids'])}"
            )
    lines.append("")
    (root / "notes.md").write_text("\n".join(lines), encoding="utf-8")


def build_all() -> None:
    # G01 — duplicate late penalty
    o = make_order("QD-1001", 42, prep=12)
    write_fixture(
        "G01_duplicate",
        "Two identical LATE deductions on one order. One is legitimate; the second is a duplicate.",
        orders=[o],
        earnings=[make_earning("E-0001", "QD-1001", 42)],
        deductions=[
            make_deduction("D-0001", "QD-1001", "LATE", 75, hour=19, minute=10),
            make_deduction("D-0002", "QD-1001", "LATE", 75, hour=19, minute=14),
        ],
        expected_claims=[_claim("duplicate_deduction", 75, ["QD-1001"])],
    )

    # G02 — over-cap late penalty
    write_fixture(
        "G02_over_cap_late",
        "A ₹150 late penalty on a ₹42 order exceeds the policy cap (greater of ₹100 or 25%).",
        orders=[make_order("QD-2001", 42, prep=12)],
        earnings=[make_earning("E-0001", "QD-2001", 42)],
        deductions=[make_deduction("D-0001", "QD-2001", "LATE", 150)],
        expected_claims=[_claim("over_cap_deduction", 50, ["QD-2001"])],
    )

    # G03 — restaurant-delay protection
    write_fixture(
        "G03_restaurant_delay",
        "A late penalty on an order with 29 minutes of restaurant preparation; the policy protects the worker.",
        orders=[make_order("QD-3001", 200, prep=29)],
        earnings=[make_earning("E-0001", "QD-3001", 200)],
        deductions=[make_deduction("D-0001", "QD-3001", "LATE", 50)],
        expected_claims=[_claim("restaurant_delay_penalty", 50, ["QD-3001"])],
    )

    # G04 — incentive shortfall
    orders4 = [make_order(f"QD-40{i:02d}", 100) for i in range(1, 6)]
    earnings4 = [make_earning(f"E-{i:04d}", f"QD-40{i:02d}", 100) for i in range(1, 6)]
    write_fixture(
        "G04_incentive_shortfall",
        "A 5-order incentive was achieved but paid ₹50 short.",
        orders=orders4,
        earnings=earnings4,
        incentives=[make_incentive("INC-0001", "5-order streak", 5, 500, 450)],
        expected_claims=[_claim("incentive_shortfall", 50, [])],
    )

    # G05 — missing earning
    write_fixture(
        "G05_missing_earning",
        "A delivered order has no earning entry at all.",
        orders=[make_order("QD-5001", 42, prep=12)],
        earnings=[],
        expected_claims=[_claim("missing_earning", 42, ["QD-5001"])],
    )

    # G06 — duplicate + over-cap on one order
    write_fixture(
        "G06_duplicate_and_over_cap",
        "Two ₹150 LATE deductions on a ₹42 order: one duplicate ₹150 plus ₹50 over the cap.",
        orders=[make_order("QD-6001", 42, prep=12)],
        earnings=[make_earning("E-0001", "QD-6001", 42)],
        deductions=[
            make_deduction("D-0001", "QD-6001", "LATE", 150, hour=19, minute=10),
            make_deduction("D-0002", "QD-6001", "LATE", 150, hour=19, minute=14),
        ],
        expected_claims=[
            _claim("duplicate_deduction", 150, ["QD-6001"]),
            _claim("over_cap_deduction", 50, ["QD-6001"]),
        ],
    )

    # G07 — delay + over-cap
    write_fixture(
        "G07_delay_and_over_cap",
        "A ₹150 late penalty on a 29-minute restaurant prep order: ₹50 over cap plus ₹100 protected by the delay clause.",
        orders=[make_order("QD-7001", 200, prep=29)],
        earnings=[make_earning("E-0001", "QD-7001", 200)],
        deductions=[make_deduction("D-0001", "QD-7001", "LATE", 150)],
        expected_claims=[
            _claim("over_cap_deduction", 50, ["QD-7001"]),
            _claim("restaurant_delay_penalty", 100, ["QD-7001"]),
        ],
    )

    # G08 — two incentives, one short
    orders8 = [make_order(f"QD-80{i:02d}", 100) for i in range(1, 6)]
    earnings8 = [make_earning(f"E-{i:04d}", f"QD-80{i:02d}", 100) for i in range(1, 6)]
    write_fixture(
        "G08_two_incentives",
        "Two incentives: one paid ₹50 short, one paid in full.",
        orders=orders8,
        earnings=earnings8,
        incentives=[
            make_incentive("INC-0001", "5-order streak", 5, 500, 450),
            make_incentive("INC-0002", "Weekend bonus", 5, 200, 200),
        ],
        expected_claims=[_claim("incentive_shortfall", 50, [])],
    )

    # G09 — missing one of three
    write_fixture(
        "G09_missing_one_of_three",
        "Three delivered orders; one has no earning line.",
        orders=[
            make_order("QD-9001", 100),
            make_order("QD-9002", 100),
            make_order("QD-9003", 100),
        ],
        earnings=[
            make_earning("E-0001", "QD-9001", 100),
            make_earning("E-0002", "QD-9002", 100),
        ],
        expected_claims=[_claim("missing_earning", 100, ["QD-9003"])],
    )

    # G10 — duplicate cancellation penalty
    write_fixture(
        "G10_duplicate_cancel",
        "Two identical CANCEL deductions on one order; one is a duplicate.",
        orders=[make_order("QD-10001", 100)],
        earnings=[make_earning("E-0001", "QD-10001", 100)],
        deductions=[
            make_deduction("D-0001", "QD-10001", "CANCEL", 50, hour=19, minute=10),
            make_deduction("D-0002", "QD-10001", "CANCEL", 50, hour=19, minute=14),
        ],
        expected_claims=[_claim("duplicate_deduction", 50, ["QD-10001"])],
    )

    # G11 — over-cap cancellation penalty
    write_fixture(
        "G11_over_cap_cancel",
        "An ₹80 cancellation penalty on a ₹100 order exceeds the ₹50 cap.",
        orders=[make_order("QD-11001", 100)],
        earnings=[make_earning("E-0001", "QD-11001", 100)],
        deductions=[make_deduction("D-0001", "QD-11001", "CANCEL", 80)],
        expected_claims=[_claim("over_cap_deduction", 30, ["QD-11001"])],
    )

    # G12 — multiple claim types
    orders12 = [
        make_order("QD-12001", 42, prep=12),
        make_order("QD-12002", 200, prep=29, day=2),
        make_order("QD-12003", 42, prep=12, day=3),
        make_order("QD-12004", 100, prep=10, day=3),
        make_order("QD-12005", 100, prep=10, day=3),
    ]
    earnings12 = [
        make_earning("E-0001", "QD-12001", 42),
        make_earning("E-0002", "QD-12002", 200),
        make_earning("E-0003", "QD-12004", 100),
        make_earning("E-0004", "QD-12005", 100),
    ]
    write_fixture(
        "G12_multiple",
        "A mixed statement: duplicate, restaurant-delay, incentive shortfall, and missing earning.",
        orders=orders12,
        earnings=earnings12,
        deductions=[
            make_deduction("D-0001", "QD-12001", "LATE", 75, hour=19, minute=10),
            make_deduction("D-0002", "QD-12001", "LATE", 75, hour=19, minute=14),
            make_deduction("D-0003", "QD-12002", "LATE", 50, day=2, hour=19, minute=10),
        ],
        incentives=[make_incentive("INC-0001", "5-order streak", 5, 500, 450)],
        expected_claims=[
            _claim("duplicate_deduction", 75, ["QD-12001"]),
            _claim("restaurant_delay_penalty", 50, ["QD-12002"]),
            _claim("incentive_shortfall", 50, []),
            _claim("missing_earning", 42, ["QD-12003"]),
        ],
    )

    # F01 — clean
    write_fixture(
        "F01_clean",
        "Three delivered orders, all paid in full, no deductions or incentives.",
        orders=[
            make_order("QD-13001", 100),
            make_order("QD-13002", 100, day=2),
            make_order("QD-13003", 100, day=3),
        ],
        earnings=[
            make_earning("E-0001", "QD-13001", 100),
            make_earning("E-0002", "QD-13002", 100),
            make_earning("E-0003", "QD-13003", 100),
        ],
    )

    # F02 — legitimate late penalty below cap
    write_fixture(
        "F02_legit_late",
        "A ₹50 late penalty on a ₹200 order is below the ₹100 cap and the prep time is normal.",
        orders=[make_order("QD-14001", 200, prep=10)],
        earnings=[make_earning("E-0001", "QD-14001", 200)],
        deductions=[make_deduction("D-0001", "QD-14001", "LATE", 50)],
    )

    # F03 — legitimate cancellation penalty below cap
    write_fixture(
        "F03_legit_cancel",
        "A ₹30 cancellation penalty on a ₹100 order is below the ₹50 cap.",
        orders=[make_order("QD-15001", 100)],
        earnings=[make_earning("E-0001", "QD-15001", 100)],
        deductions=[make_deduction("D-0001", "QD-15001", "CANCEL", 30)],
    )

    # F04 — incentive paid in full
    orders16 = [make_order(f"QD-16{i:02d}", 100) for i in range(1, 6)]
    earnings16 = [make_earning(f"E-{i:04d}", f"QD-16{i:02d}", 100) for i in range(1, 6)]
    write_fixture(
        "F04_incentive_full",
        "A 5-order incentive was achieved and paid in full.",
        orders=orders16,
        earnings=earnings16,
        incentives=[make_incentive("INC-0001", "5-order streak", 5, 500, 500)],
    )

    # F05 — valid late penalty with short prep
    write_fixture(
        "F05_valid_late_short_prep",
        "An ₹80 late penalty on a ₹200 order with 10 minutes of restaurant prep is below cap and not protected.",
        orders=[make_order("QD-17001", 200, prep=10)],
        earnings=[make_earning("E-0001", "QD-17001", 200)],
        deductions=[make_deduction("D-0001", "QD-17001", "LATE", 80)],
    )

    # F06 — tips and surge
    write_fixture(
        "F06_tips_and_surge",
        "A ₹150 order made up of ₹100 base, ₹30 surge, and ₹20 tip, all paid.",
        orders=[make_order("QD-18001", 150, base=100, surge=30, tip=20)],
        earnings=[make_earning("E-0001", "QD-18001", 150)],
    )

    # F07 — cancelled order without earning
    write_fixture(
        "F07_cancelled_no_earning",
        "A cancelled order has no earning entry; this is not a missing-earning claim because it was not delivered.",
        orders=[make_order("QD-19001", 100, status="cancelled")],
        earnings=[],
    )

    # F08 — boundary cap
    write_fixture(
        "F08_boundary_cap",
        "A ₹100 late penalty on a ₹200 order is exactly at the cap and is not over-cap.",
        orders=[make_order("QD-20001", 200, prep=10)],
        earnings=[make_earning("E-0001", "QD-20001", 200)],
        deductions=[make_deduction("D-0001", "QD-20001", "LATE", 100)],
    )


if __name__ == "__main__":
    build_all()
    count = len([p for p in GOLDEN.iterdir() if p.is_dir()])
    print(f"Wrote {count} fixtures under {GOLDEN}")
