"""Canonical schema and parsing helpers for Saboot.

All money is stored as Decimal. All timestamps are timezone-aware.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

MONEY_QUANT = Decimal("0.01")
DEFAULT_TZ = timezone(timedelta(hours=5, minutes=30))  # Asia/Kolkata


class SabootError(Exception):
    """Base error for expected, user-facing failures."""


class ValidationError(SabootError):
    """Input data did not match the canonical schema."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def parse_money(value: Any, field_name: str, row_ref: str = "") -> Decimal:
    """Parse INR-style money strings into Decimal. Blank becomes 0."""
    if value is None or str(value).strip() == "":
        return Decimal("0.00")
    text = str(value).strip()
    for token in ("₹", "Rs.", "Rs", "INR", ",", " "):
        text = text.replace(token, "")
    text = text.replace("−", "-")
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValidationError(f"{row_ref}: {field_name} is not a valid amount: {value!r}") from exc
    return quantize_money(amount)


def parse_optional_money(value: Any, field_name: str, row_ref: str = "") -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return parse_money(value, field_name, row_ref)


def parse_datetime(value: Any, field_name: str, row_ref: str = "", required: bool = True) -> datetime | None:
    if value is None or str(value).strip() == "":
        if required:
            raise ValidationError(f"{row_ref}: {field_name} is required")
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError(f"{row_ref}: {field_name} is not a valid ISO datetime: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=DEFAULT_TZ)
    return parsed


def parse_optional_datetime(value: Any, field_name: str, row_ref: str = "") -> datetime | None:
    return parse_datetime(value, field_name, row_ref, required=False)


def parse_int(value: Any, field_name: str, row_ref: str = "", required: bool = False) -> int | None:
    if value is None or str(value).strip() == "":
        if required:
            raise ValidationError(f"{row_ref}: {field_name} is required")
        return None
    try:
        return int(str(value).strip())
    except ValueError as exc:
        raise ValidationError(f"{row_ref}: {field_name} is not an integer: {value!r}") from exc


def parse_date(value: Any, field_name: str, row_ref: str = "") -> date:
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"{row_ref}: {field_name} is not a valid date: {value!r}") from exc


def iso_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def money_float(value: Decimal) -> float:
    return float(quantize_money(value))


def format_inr(value: Decimal | float) -> str:
    amount = value if isinstance(value, Decimal) else Decimal(str(value))
    amount = quantize_money(amount)
    if amount < 0:
        return f"-₹{abs(amount):,.2f}"
    return f"₹{amount:,.2f}"


@dataclass(frozen=True)
class Meta:
    statement_id: str
    platform: str
    worker_id: str
    period_start: datetime
    period_end: datetime
    currency: str = "INR"
    jurisdiction: str = "IN-KA"


@dataclass
class Order:
    order_id: str
    accepted_at: datetime
    picked_up_at: datetime | None
    delivered_at: datetime | None
    promised_delivery_at: datetime | None
    restaurant_prep_minutes: int | None
    distance_km: Decimal | None
    status: str
    base_pay: Decimal
    surge_pay: Decimal
    tip: Decimal
    total_pay: Decimal

    @property
    def expected_pay(self) -> Decimal:
        if self.total_pay > 0:
            return quantize_money(self.total_pay)
        return quantize_money(self.base_pay + self.surge_pay + self.tip)

    @property
    def is_delivered(self) -> bool:
        return self.status.strip().lower() == "delivered"

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "accepted_at": iso_dt(self.accepted_at),
            "picked_up_at": iso_dt(self.picked_up_at),
            "delivered_at": iso_dt(self.delivered_at),
            "promised_delivery_at": iso_dt(self.promised_delivery_at),
            "restaurant_prep_minutes": self.restaurant_prep_minutes,
            "distance_km": float(self.distance_km) if self.distance_km is not None else None,
            "status": self.status,
            "base_pay": money_float(self.base_pay),
            "surge_pay": money_float(self.surge_pay),
            "tip": money_float(self.tip),
            "total_pay": money_float(self.total_pay),
            "expected_pay": money_float(self.expected_pay),
        }


@dataclass
class Earning:
    earning_id: str
    order_id: str
    earning_type: str
    amount: Decimal
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "earning_id": self.earning_id,
            "order_id": self.order_id,
            "earning_type": self.earning_type,
            "amount": money_float(self.amount),
            "description": self.description,
        }


@dataclass
class Deduction:
    deduction_id: str
    order_id: str
    code: str
    description: str
    amount: Decimal
    applied_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "deduction_id": self.deduction_id,
            "order_id": self.order_id,
            "deduction_code": self.code,
            "description": self.description,
            "amount": money_float(self.amount),
            "applied_at": iso_dt(self.applied_at),
        }


@dataclass
class Incentive:
    incentive_id: str
    name: str
    target_orders: int
    target_amount: Decimal
    achieved_orders: int
    amount_promised: Decimal
    amount_paid: Decimal
    qualifying_order_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "incentive_id": self.incentive_id,
            "name": self.name,
            "target_orders": self.target_orders,
            "target_amount": money_float(self.target_amount),
            "achieved_orders": self.achieved_orders,
            "amount_promised": money_float(self.amount_promised),
            "amount_paid": money_float(self.amount_paid),
            "qualifying_order_ids": self.qualifying_order_ids,
        }


@dataclass
class Statement:
    meta: Meta
    orders: list[Order]
    earnings: list[Earning]
    deductions: list[Deduction]
    incentives: list[Incentive]
    source_map: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    orders_by_id: dict[str, Order] = field(init=False, repr=False)
    earnings_by_order: dict[str, list[Earning]] = field(init=False, repr=False)
    deductions_by_order: dict[str, list[Deduction]] = field(init=False, repr=False)
    earning_by_id: dict[str, Earning] = field(init=False, repr=False)
    deduction_by_id: dict[str, Deduction] = field(init=False, repr=False)
    incentive_by_id: dict[str, Incentive] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.orders_by_id = {o.order_id: o for o in self.orders}
        self.earning_by_id = {e.earning_id: e for e in self.earnings}
        self.deduction_by_id = {d.deduction_id: d for d in self.deductions}
        self.incentive_by_id = {i.incentive_id: i for i in self.incentives}
        self.earnings_by_order = {}
        for earning in self.earnings:
            self.earnings_by_order.setdefault(earning.order_id, []).append(earning)
        self.deductions_by_order = {}
        for deduction in self.deductions:
            self.deductions_by_order.setdefault(deduction.order_id, []).append(deduction)

    def source_for(self, kind: str, identifier: str) -> str | None:
        return self.source_map.get(f"{kind}:{identifier}")

    def earnings_total(self, order_id: str) -> Decimal:
        return quantize_money(sum((e.amount for e in self.earnings_by_order.get(order_id, [])), Decimal("0")))

    def all_datetimes(self) -> set[datetime]:
        values: set[datetime] = {self.meta.period_start, self.meta.period_end}
        for order in self.orders:
            for dt in (order.accepted_at, order.picked_up_at, order.delivered_at, order.promised_delivery_at):
                if dt is not None:
                    values.add(dt)
        for deduction in self.deductions:
            values.add(deduction.applied_at)
        return values

    def counts(self) -> dict[str, int]:
        return {
            "orders": len(self.orders),
            "earnings": len(self.earnings),
            "deductions": len(self.deductions),
            "incentives": len(self.incentives),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "statement_id": self.meta.statement_id,
                "platform": self.meta.platform,
                "worker_id": self.meta.worker_id,
                "period_start": iso_dt(self.meta.period_start),
                "period_end": iso_dt(self.meta.period_end),
                "currency": self.meta.currency,
                "jurisdiction": self.meta.jurisdiction,
            },
            "counts": self.counts(),
            "warnings": self.warnings,
            "orders": [o.to_dict() for o in self.orders],
            "earnings": [e.to_dict() for e in self.earnings],
            "deductions": [d.to_dict() for d in self.deductions],
            "incentives": [i.to_dict() for i in self.incentives],
        }
