"""Deterministic order-level reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .schema import Statement, money_float, quantize_money


@dataclass
class OrderReconciliation:
    order_id: str
    status: str
    expected_pay: Decimal
    actual_pay: Decimal
    delta: Decimal

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "status": self.status,
            "expected_pay": money_float(self.expected_pay),
            "actual_pay": money_float(self.actual_pay),
            "delta": money_float(self.delta),
        }


def build_reconciliation(statement: Statement) -> list[OrderReconciliation]:
    rows: list[OrderReconciliation] = []
    for order in statement.orders:
        expected = quantize_money(order.expected_pay)
        actual = statement.earnings_total(order.order_id)
        delta = quantize_money(actual - expected)
        if not order.is_delivered:
            status = "not_delivered"
        elif expected > 0 and actual == 0:
            status = "unpaid"
        elif delta < Decimal("-0.01"):
            status = "underpaid"
        elif delta > Decimal("0.01"):
            status = "overpaid"
        else:
            status = "paid"
        rows.append(
            OrderReconciliation(
                order_id=order.order_id,
                status=status,
                expected_pay=expected,
                actual_pay=actual,
                delta=delta,
            )
        )
    return rows


def reconciliation_summary(rows: list[OrderReconciliation]) -> dict[str, Any]:
    expected = quantize_money(sum((r.expected_pay for r in rows), Decimal("0")))
    actual = quantize_money(sum((r.actual_pay for r in rows), Decimal("0")))
    return {
        "orders": len(rows),
        "total_expected": money_float(expected),
        "total_actual": money_float(actual),
        "total_delta": money_float(quantize_money(actual - expected)),
        "status_counts": {
            status: sum(1 for r in rows if r.status == status)
            for status in sorted({r.status for r in rows})
        },
    }
