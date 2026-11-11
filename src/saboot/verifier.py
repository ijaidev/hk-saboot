"""Claim verifier: the hard gate between generated text and the audit output.

The verifier rejects unsupported amounts, unknown IDs, fabricated dates,
inapplicable citations, legal advice, outcome promises, and real-brand names.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from .claims import CLAIM_TYPES, Claim
from .policy import PolicyBook
from .schema import Statement, parse_datetime, quantize_money

LEGAL_PATTERNS = [
    r"\bsue\b",
    r"\blawsuit\b",
    r"\bcourt\b",
    r"\battorney\b",
    r"\blawyer\b",
    r"\blegal action\b",
    r"(?<!not )\blegal advice\b",
]
OUTCOME_PATTERNS = [
    r"\bwill refund\b",
    r"\bguaranteed\b",
    r"\bwill win\b",
    r"\byou will receive\b",
    r"\bmust pay\b",
    r"\bwill be paid\b",
    r"\bpromises? to pay\b",
]
REAL_BRANDS = [
    "swiggy",
    "zomato",
    "uber",
    "ola",
    "zepto",
    "blinkit",
    "amazon",
    "flipkart",
    "instamart",
]


def scan_text(text: str) -> list[str]:
    errors: list[str] = []
    lowered = text.lower()
    for pattern in LEGAL_PATTERNS:
        if re.search(pattern, lowered):
            errors.append(f"contains legal-advice language: {pattern}")
    for pattern in OUTCOME_PATTERNS:
        if re.search(pattern, lowered):
            errors.append(f"contains an outcome promise: {pattern}")
    for brand in REAL_BRANDS:
        if re.search(rf"\b{re.escape(brand)}\b", lowered):
            errors.append(f"contains a real platform brand name: {brand}")
    return errors


def _parse_event_date(claim: Claim, statement: Statement) -> date | None:
    raw = claim.evidence.get("claim_event_at")
    if isinstance(raw, str) and raw:
        try:
            return parse_datetime(raw, "claim_event_at").date()  # type: ignore[union-attr]
        except Exception:
            return None
    if claim.deduction_ids:
        deduction = statement.deduction_by_id.get(claim.deduction_ids[0])
        if deduction:
            return deduction.applied_at.date()
    if claim.order_ids:
        order = statement.orders_by_id.get(claim.order_ids[0])
        if order:
            event = order.delivered_at or order.accepted_at
            return event.date()
    return statement.meta.period_end.date()


def _check_policy(claim: Claim, statement: Statement, policy: PolicyBook) -> list[str]:
    errors: list[str] = []
    if not claim.policy_clause_id:
        return ["no policy_clause_id"]
    clause = policy.clause(claim.policy_clause_id)
    if clause is None:
        return [f"policy clause {claim.policy_clause_id!r} does not exist"]
    if claim.claim_type not in clause.applies_to:
        errors.append(
            f"policy clause {clause.id} does not apply to {claim.claim_type}"
        )
    if clause.jurisdiction not in ("*", statement.meta.jurisdiction):
        errors.append(
            f"policy clause {clause.id} jurisdiction {clause.jurisdiction} "
            f"does not match {statement.meta.jurisdiction}"
        )
    event_date = _parse_event_date(claim, statement)
    if event_date is not None and not (clause.effective_from <= event_date <= clause.effective_to):
        errors.append(
            f"policy clause {clause.id} is not effective on {event_date.isoformat()}"
        )
    if not clause.source_url.startswith(("https://", "http://")):
        errors.append(f"policy clause {clause.id} has no http(s) source_url")
    if claim.policy_clause:
        if claim.policy_clause.get("id") != clause.id:
            errors.append("embedded policy clause does not match policy_clause_id")
        if claim.policy_clause.get("source_url") != clause.source_url:
            errors.append("embedded policy clause source_url does not match the policy book")
    return errors


def _check_timestamps(claim: Claim, statement: Statement) -> list[str]:
    errors: list[str] = []
    known = statement.all_datetimes()
    for key, value in claim.evidence.get("timestamps", {}).items():
        if value is None:
            continue
        try:
            parsed = parse_datetime(value, key)
        except Exception:
            errors.append(f"timestamp {key} is not parseable: {value!r}")
            continue
        if parsed not in known:
            errors.append(f"timestamp {key}={value!r} is not present in the statement")
    event_raw = claim.evidence.get("claim_event_at")
    if isinstance(event_raw, str) and event_raw:
        try:
            event_dt = parse_datetime(event_raw, "claim_event_at")
        except Exception:
            errors.append(f"claim_event_at is not parseable: {event_raw!r}")
        else:
            if event_dt not in known:
                errors.append(
                    f"claim_event_at={event_raw!r} is not present in the statement"
                )
    if claim.evidence.get("policy_clause_id") not in (None, claim.policy_clause_id):
        errors.append("evidence policy_clause_id does not match claim.policy_clause_id")
    return errors


def _check_arithmetic(claim: Claim) -> list[str]:
    errors: list[str] = []
    component_total = quantize_money(
        sum((c.get("amount", Decimal("0")) for c in claim.components), Decimal("0"))
    )
    if abs(component_total - claim.amount) > Decimal("0.01"):
        errors.append(
            f"components sum to {component_total} but claim amount is {claim.amount}"
        )
    if claim.support_limit < claim.amount - Decimal("0.01"):
        errors.append(
            f"claim amount {claim.amount} exceeds the evidence support limit "
            f"{claim.support_limit}"
        )
    return errors


def _check_type_specific(claim: Claim, statement: Statement, policy: PolicyBook) -> list[str]:
    errors: list[str] = []
    if claim.claim_type == "duplicate_deduction":
        if len(set(claim.deduction_ids)) < 2:
            errors.append("duplicate claim needs at least two deduction IDs")
        deductions = [
            statement.deduction_by_id[d]
            for d in claim.deduction_ids
            if d in statement.deduction_by_id
        ]
        if len({(d.order_id, d.code) for d in deductions}) > 1:
            errors.append("duplicate claim spans more than one order/code group")
    elif claim.claim_type == "over_cap_deduction":
        if not claim.deduction_ids:
            errors.append("over-cap claim has no deduction ID")
        for deduction_id in claim.deduction_ids:
            deduction = statement.deduction_by_id.get(deduction_id)
            if deduction is None:
                continue
            clause = policy.clause(claim.policy_clause_id) if claim.policy_clause_id else None
            order = statement.orders_by_id.get(deduction.order_id)
            if clause is None or order is None:
                continue
            cap = policy.evaluate_cap(clause, order.expected_pay)
            if cap is None:
                errors.append(f"clause {clause.id} has no evaluable cap")
            elif claim.amount > deduction.amount - cap + Decimal("0.01"):
                errors.append(
                    f"over-cap claim {claim.amount} exceeds deduction "
                    f"{deduction.amount} minus cap {cap}"
                )
    elif claim.claim_type == "restaurant_delay_penalty":
        if not claim.order_ids:
            errors.append("delay claim has no order ID")
        for order_id in claim.order_ids:
            order = statement.orders_by_id.get(order_id)
            if order is None:
                continue
            if order.restaurant_prep_minutes is None:
                errors.append(f"order {order_id} has no restaurant prep time")
            elif order.restaurant_prep_minutes <= 20:
                errors.append(
                    f"order {order_id} prep time {order.restaurant_prep_minutes} "
                    "does not exceed the 20-minute protection threshold"
                )
    elif claim.claim_type == "incentive_shortfall":
        if not claim.incentive_ids:
            errors.append("incentive claim has no incentive ID")
        for incentive_id in claim.incentive_ids:
            incentive = statement.incentive_by_id.get(incentive_id)
            if incentive is None:
                continue
            if incentive.target_orders <= 0:
                errors.append(f"incentive {incentive_id} has no positive target")
            if incentive.achieved_orders < incentive.target_orders:
                errors.append(f"incentive {incentive_id} target was not met")
            shortfall = incentive.amount_promised - incentive.amount_paid
            if claim.amount > shortfall + Decimal("0.01"):
                errors.append(
                    f"incentive claim {claim.amount} exceeds shortfall {shortfall}"
                )
    elif claim.claim_type == "missing_earning":
        if not claim.order_ids:
            errors.append("missing-earning claim has no order ID")
        for order_id in claim.order_ids:
            order = statement.orders_by_id.get(order_id)
            if order is None:
                continue
            if not order.is_delivered:
                errors.append(f"order {order_id} is not delivered")
            if statement.earnings_total(order_id) != 0:
                errors.append(f"order {order_id} already has earnings")
            if claim.amount > order.expected_pay + Decimal("0.01"):
                errors.append(
                    f"missing-earning claim {claim.amount} exceeds expected pay "
                    f"{order.expected_pay}"
                )
    else:
        errors.append(f"unknown claim type {claim.claim_type!r}")
    return errors


def verify_claim(claim: Claim, statement: Statement, policy: PolicyBook) -> list[str]:
    errors: list[str] = []
    if claim.claim_type not in CLAIM_TYPES:
        errors.append(f"unknown claim type {claim.claim_type!r}")
    if claim.amount <= Decimal("0"):
        errors.append("claim amount must be positive")
    if claim.currency != statement.meta.currency:
        errors.append(f"claim currency {claim.currency} does not match statement")
    if not (0.0 <= claim.confidence <= 1.0):
        errors.append(f"confidence {claim.confidence} is outside 0..1")
    if claim.status not in ("ready", "needs_review"):
        errors.append(f"invalid claim status {claim.status!r}")

    if claim.policy_clause_id is None:
        errors.append("claim has no policy clause")
    else:
        errors.extend(_check_policy(claim, statement, policy))

    for order_id in claim.order_ids:
        if order_id not in statement.orders_by_id:
            errors.append(f"order ID {order_id!r} does not exist")
    for deduction_id in claim.deduction_ids:
        if deduction_id not in statement.deduction_by_id:
            errors.append(f"deduction ID {deduction_id!r} does not exist")
    for earning_id in claim.earning_ids:
        if earning_id not in statement.earning_by_id:
            errors.append(f"earning ID {earning_id!r} does not exist")
    for incentive_id in claim.incentive_ids:
        if incentive_id not in statement.incentive_by_id:
            errors.append(f"incentive ID {incentive_id!r} does not exist")

    if not (claim.order_ids or claim.deduction_ids or claim.earning_ids or claim.incentive_ids):
        errors.append("claim has no evidence references")

    errors.extend(_check_arithmetic(claim))
    errors.extend(_check_timestamps(claim, statement))
    errors.extend(_check_type_specific(claim, statement, policy))

    text = " ".join(
        [
            claim.reason,
            str(claim.evidence.get("arithmetic", "")),
            " ".join(str(c.get("label", "")) for c in claim.components),
        ]
    )
    errors.extend(scan_text(text))

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for error in errors:
        if error not in seen:
            unique.append(error)
            seen.add(error)
    return unique


def verify_claims(claims: list[Claim], statement: Statement, policy: PolicyBook) -> dict[str, Any]:
    errors: list[str] = []
    seen_claim_ids: set[str] = set()
    for claim in claims:
        if claim.claim_id in seen_claim_ids:
            errors.append(f"duplicate claim ID {claim.claim_id!r}")
        seen_claim_ids.add(claim.claim_id)
        claim_errors = verify_claim(claim, statement, policy)
        claim.verification_errors = claim_errors
        if claim_errors:
            claim.status = "needs_review"
            errors.extend(f"{claim.claim_id}: {err}" for err in claim_errors)
    return {"passed": not errors, "errors": errors}
