"""Shared segmentation: turn per-record dictionaries into a canonical Statement."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from ..schema import (
    Deduction,
    Earning,
    Incentive,
    Meta,
    Order,
    Statement,
    ValidationError,
    parse_datetime,
    parse_int,
    parse_money,
    parse_optional_datetime,
    parse_optional_money,
    quantize_money,
)


def _require(row: dict[str, Any], key: str, ref: str) -> str:
    value = row.get(key)
    if value is None or str(value).strip() == "":
        raise ValidationError(f"{ref}: missing required field {key!r}")
    return str(value).strip()


def _optional(row: dict[str, Any], key: str, default: str = "") -> str:
    value = row.get(key)
    if value is None:
        return default
    return str(value).strip()


def build_statement(
    meta_rows: list[tuple[dict[str, Any], str]],
    order_rows: list[tuple[dict[str, Any], str]],
    earning_rows: list[tuple[dict[str, Any], str]],
    deduction_rows: list[tuple[dict[str, Any], str]],
    incentive_rows: list[tuple[dict[str, Any], str]],
) -> Statement:
    if len(meta_rows) != 1:
        raise ValidationError(f"Expected exactly one meta record, found {len(meta_rows)}")

    meta_row, meta_ref = meta_rows[0]
    meta = Meta(
        statement_id=_require(meta_row, "statement_id", meta_ref),
        platform=_require(meta_row, "platform", meta_ref),
        worker_id=_require(meta_row, "worker_id", meta_ref),
        period_start=parse_datetime(
            _require(meta_row, "period_start", meta_ref), "period_start", meta_ref
        ),
        period_end=parse_datetime(
            _require(meta_row, "period_end", meta_ref), "period_end", meta_ref
        ),
        currency=_optional(meta_row, "currency", "INR") or "INR",
        jurisdiction=_optional(meta_row, "jurisdiction", "IN-KA") or "IN-KA",
    )
    if meta.period_end < meta.period_start:
        raise ValidationError(f"{meta_ref}: period_end is before period_start")

    source_map: dict[str, str] = {"meta": meta_ref}
    warnings: list[str] = []

    orders: list[Order] = []
    seen_orders: set[str] = set()
    for row, ref in order_rows:
        order_id = _require(row, "order_id", ref)
        if order_id in seen_orders:
            raise ValidationError(f"{ref}: duplicate order_id {order_id!r}")
        seen_orders.add(order_id)

        accepted_at = parse_datetime(_require(row, "accepted_at", ref), "accepted_at", ref)
        picked_up_at = parse_optional_datetime(row.get("picked_up_at"), "picked_up_at", ref)
        delivered_at = parse_optional_datetime(row.get("delivered_at"), "delivered_at", ref)
        promised_delivery_at = parse_optional_datetime(
            row.get("promised_delivery_at"), "promised_delivery_at", ref
        )
        prep_minutes = parse_int(row.get("restaurant_prep_minutes"), "restaurant_prep_minutes", ref)
        if prep_minutes is None and picked_up_at is not None:
            prep_minutes = max(0, int((picked_up_at - accepted_at).total_seconds() // 60))
        if prep_minutes is not None and prep_minutes < 0:
            raise ValidationError(f"{ref}: restaurant_prep_minutes cannot be negative")

        base_pay = parse_money(row.get("base_pay"), "base_pay", ref)
        surge_pay = parse_money(row.get("surge_pay"), "surge_pay", ref)
        tip = parse_money(row.get("tip"), "tip", ref)
        total_pay = parse_money(row.get("total_pay"), "total_pay", ref)
        component_total = quantize_money(base_pay + surge_pay + tip)
        if total_pay == 0 and component_total > 0:
            total_pay = component_total
        if total_pay > 0 and component_total > 0 and abs(total_pay - component_total) > Decimal("0.01"):
            warnings.append(
                f"{ref}: total_pay {total_pay} differs from base+surge+tip {component_total}"
            )

        status = _require(row, "status", ref)
        if picked_up_at is not None and picked_up_at < accepted_at:
            warnings.append(f"{ref}: picked_up_at is before accepted_at")
        if delivered_at is not None and delivered_at < accepted_at:
            warnings.append(f"{ref}: delivered_at is before accepted_at")

        orders.append(
            Order(
                order_id=order_id,
                accepted_at=accepted_at,
                picked_up_at=picked_up_at,
                delivered_at=delivered_at,
                promised_delivery_at=promised_delivery_at,
                restaurant_prep_minutes=prep_minutes,
                distance_km=parse_optional_money(row.get("distance_km"), "distance_km", ref),
                status=status,
                base_pay=base_pay,
                surge_pay=surge_pay,
                tip=tip,
                total_pay=total_pay,
            )
        )
        source_map[f"order:{order_id}"] = ref

    earnings: list[Earning] = []
    seen_earnings: set[str] = set()
    for index, (row, ref) in enumerate(earning_rows, start=1):
        earning_id = _optional(row, "earning_id") or f"E-{index:04d}"
        if earning_id in seen_earnings:
            raise ValidationError(f"{ref}: duplicate earning_id {earning_id!r}")
        seen_earnings.add(earning_id)
        order_id = _require(row, "order_id", ref)
        if order_id not in seen_orders:
            raise ValidationError(f"{ref}: earning references unknown order_id {order_id!r}")
        earnings.append(
            Earning(
                earning_id=earning_id,
                order_id=order_id,
                earning_type=_optional(row, "earning_type", "base") or "base",
                amount=parse_money(row.get("amount"), "amount", ref),
                description=_optional(row, "description"),
            )
        )
        source_map[f"earning:{earning_id}"] = ref

    deductions: list[Deduction] = []
    seen_deductions: set[str] = set()
    for index, (row, ref) in enumerate(deduction_rows, start=1):
        deduction_id = _optional(row, "deduction_id") or f"D-{index:04d}"
        if deduction_id in seen_deductions:
            raise ValidationError(f"{ref}: duplicate deduction_id {deduction_id!r}")
        seen_deductions.add(deduction_id)
        amount = parse_money(row.get("amount"), "amount", ref)
        if amount <= 0:
            raise ValidationError(f"{ref}: deduction amount must be positive")
        order_id = _optional(row, "order_id")
        if order_id and order_id not in seen_orders:
            warnings.append(f"{ref}: deduction references unknown order_id {order_id!r}")
        deductions.append(
            Deduction(
                deduction_id=deduction_id,
                order_id=order_id,
                code=(_optional(row, "deduction_code") or "UNKNOWN").upper(),
                description=_optional(row, "description"),
                amount=amount,
                applied_at=parse_datetime(
                    _require(row, "applied_at", ref), "applied_at", ref
                ),
            )
        )
        source_map[f"deduction:{deduction_id}"] = ref

    incentives: list[Incentive] = []
    seen_incentives: set[str] = set()
    for index, (row, ref) in enumerate(incentive_rows, start=1):
        incentive_id = _optional(row, "incentive_id") or f"INC-{index:04d}"
        if incentive_id in seen_incentives:
            raise ValidationError(f"{ref}: duplicate incentive_id {incentive_id!r}")
        seen_incentives.add(incentive_id)
        qualifying_raw = _optional(row, "qualifying_order_ids")
        qualifying = [
            part.strip()
            for part in qualifying_raw.replace(",", ";").split(";")
            if part.strip()
        ]
        incentives.append(
            Incentive(
                incentive_id=incentive_id,
                name=_optional(row, "name", "Incentive") or "Incentive",
                target_orders=parse_int(row.get("target_orders"), "target_orders", ref) or 0,
                target_amount=parse_money(row.get("target_amount"), "target_amount", ref),
                achieved_orders=parse_int(row.get("achieved_orders"), "achieved_orders", ref) or 0,
                amount_promised=parse_money(
                    row.get("amount_promised"), "amount_promised", ref
                ),
                amount_paid=parse_money(row.get("amount_paid"), "amount_paid", ref),
                qualifying_order_ids=qualifying,
            )
        )
        source_map[f"incentive:{incentive_id}"] = ref

    if meta.platform.strip().lower() != "quickdrop":
        warnings.append(
            f"Platform is {meta.platform!r}; the bundled policy is written for QuickDrop"
        )

    return Statement(
        meta=meta,
        orders=orders,
        earnings=earnings,
        deductions=deductions,
        incentives=incentives,
        source_map=source_map,
        warnings=warnings,
    )
