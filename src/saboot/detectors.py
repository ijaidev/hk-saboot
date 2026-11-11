"""Deterministic claim detectors and evidence construction.

Detector order matters: duplicate -> over-cap -> restaurant-delay -> incentive
-> missing earning. A per-deduction allocation ledger prevents the same rupee
from being claimed twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable

from .claims import Claim, ReviewItem
from .policy import PolicyBook, PolicyClause
from .schema import (
    Deduction,
    Order,
    Statement,
    format_inr,
    iso_dt,
    money_float,
    quantize_money,
)


class Allocation:
    """Tracks how much of each deduction has already been claimed."""

    def __init__(self, statement: Statement):
        self._remaining: dict[str, Decimal] = {
            d.deduction_id: d.amount for d in statement.deductions
        }

    def remaining_for(self, deduction_id: str) -> Decimal:
        return self._remaining.get(deduction_id, Decimal("0.00"))

    def consume(self, deduction_id: str, amount: Decimal) -> Decimal:
        remaining = self.remaining_for(deduction_id)
        consumed = min(remaining, quantize_money(amount))
        self._remaining[deduction_id] = quantize_money(remaining - consumed)
        return consumed

    def snapshot(self) -> dict[str, float]:
        return {key: money_float(value) for key, value in sorted(self._remaining.items())}


def _dt_map(**values: datetime | None) -> dict[str, str]:
    return {key: iso_dt(value) for key, value in values.items() if value is not None}


def _source_rows(
    statement: Statement,
    order_ids: Iterable[str] = (),
    deduction_ids: Iterable[str] = (),
    earning_ids: Iterable[str] = (),
    incentive_ids: Iterable[str] = (),
) -> dict[str, Any]:
    def mapping(kind: str, ids: Iterable[str]) -> dict[str, str]:
        return {
            identifier: statement.source_for(kind, identifier) or "unknown"
            for identifier in ids
        }

    return {
        "orders": mapping("order", order_ids),
        "deductions": mapping("deduction", deduction_ids),
        "earnings": mapping("earning", earning_ids),
        "incentives": mapping("incentive", incentive_ids),
    }


@dataclass
class DetectionContext:
    statement: Statement
    policy: PolicyBook
    allocation: Allocation = field(init=False)
    claims: list[Claim] = field(default_factory=list)
    review_items: list[ReviewItem] = field(default_factory=list)
    _claim_seq: int = 0
    _review_seq: int = 0
    _review_keys: set[tuple[Any, ...]] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.allocation = Allocation(self.statement)

    def add_claim(
        self,
        claim_type: str,
        amount: Decimal,
        reason: str,
        *,
        order_ids: Iterable[str] = (),
        deduction_ids: Iterable[str] = (),
        earning_ids: Iterable[str] = (),
        incentive_ids: Iterable[str] = (),
        components: list[dict[str, Any]] | None = None,
        support_limit: Decimal | None = None,
        confidence: float = 1.0,
        clause: PolicyClause | None = None,
        event_code: str = "*",
        event_date: datetime | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> Claim | None:
        amount = quantize_money(amount)
        if amount <= 0:
            return None
        order_ids = list(order_ids)
        deduction_ids = list(deduction_ids)
        earning_ids = list(earning_ids)
        incentive_ids = list(incentive_ids)

        if clause is None and event_date is not None:
            clause = self.policy.find(
                claim_type, event_code, event_date, self.statement.meta.jurisdiction
            )

        status = "ready"
        if clause is None:
            status = "needs_review"
            reason = (
                f"{reason} No applicable policy clause was found for this claim; "
                "it needs human review."
            )

        self._claim_seq += 1
        claim_id = f"C-{self._claim_seq:03d}"
        support = quantize_money(support_limit if support_limit is not None else amount)
        component_rows = components or [
            {"label": f"{claim_type} component", "amount": amount}
        ]
        evidence_payload = dict(evidence or {})
        evidence_payload.setdefault(
            "source_rows",
            _source_rows(
                self.statement, order_ids, deduction_ids, earning_ids, incentive_ids
            ),
        )
        evidence_payload["policy_clause_id"] = clause.id if clause else None
        evidence_payload["currency"] = self.statement.meta.currency
        if event_date is not None:
            evidence_payload.setdefault("claim_event_at", iso_dt(event_date))

        claim = Claim(
            claim_id=claim_id,
            claim_type=claim_type,
            amount=amount,
            currency=self.statement.meta.currency,
            status=status,
            confidence=confidence,
            reason=reason,
            order_ids=order_ids,
            deduction_ids=deduction_ids,
            earning_ids=earning_ids,
            incentive_ids=incentive_ids,
            components=[
                {"label": row.get("label", ""), "amount": quantize_money(row["amount"])}
                for row in component_rows
            ],
            support_limit=support,
            policy_clause_id=clause.id if clause else None,
            policy_clause=clause.to_dict() if clause else None,
            evidence=evidence_payload,
        )
        self.claims.append(claim)
        return claim

    def add_review(
        self,
        review_type: str,
        description: str,
        *,
        order_ids: Iterable[str] = (),
        deduction_ids: Iterable[str] = (),
        incentive_ids: Iterable[str] = (),
        confidence: float = 0.5,
        evidence: dict[str, Any] | None = None,
    ) -> ReviewItem | None:
        order_ids = list(order_ids)
        deduction_ids = list(deduction_ids)
        incentive_ids = list(incentive_ids)
        key = (review_type, tuple(order_ids), tuple(deduction_ids), tuple(incentive_ids))
        if key in self._review_keys:
            return None
        self._review_keys.add(key)

        self._review_seq += 1
        payload = dict(evidence or {})
        payload.setdefault(
            "source_rows",
            _source_rows(self.statement, order_ids, deduction_ids, (), incentive_ids),
        )
        item = ReviewItem(
            review_id=f"R-{self._review_seq:03d}",
            review_type=review_type,
            description=description,
            order_ids=order_ids,
            deduction_ids=deduction_ids,
            incentive_ids=incentive_ids,
            confidence=confidence,
            evidence=payload,
        )
        self.review_items.append(item)
        return item


def detect_duplicate_deductions(ctx: DetectionContext) -> None:
    groups: dict[tuple[str, str], list[Deduction]] = {}
    for deduction in ctx.statement.deductions:
        if not deduction.order_id:
            continue
        groups.setdefault((deduction.order_id, deduction.code), []).append(deduction)

    for (order_id, code), group in sorted(groups.items()):
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda d: (d.applied_at, d.deduction_id))
        keep = ordered[0]
        extras = ordered[1:]
        amount = quantize_money(sum((d.amount for d in extras), Decimal("0")))
        for deduction in extras:
            ctx.allocation.consume(deduction.deduction_id, deduction.amount)

        arithmetic = (
            f"{' + '.join(format_inr(d.amount) for d in extras)} in duplicate "
            f"{code} charges; one charge of {format_inr(keep.amount)} is allowed = "
            f"{format_inr(amount)} claim"
        )
        times = ", ".join(d.applied_at.strftime("%H:%M") for d in ordered)
        quote = (
            f"Order {order_id}: {len(group)} × {code} deductions at {times}, "
            f"each {format_inr(keep.amount)}."
        )
        extra_word = "charge" if len(extras) == 1 else "charges"
        verb = "is" if len(extras) == 1 else "are"
        ctx.add_claim(
            "duplicate_deduction",
            amount,
            (
                f"Order {order_id} has {len(group)} {code} deductions. "
                f"The policy allows one deduction per order and reason; "
                f"{len(extras)} duplicate {extra_word} {verb} contestable."
            ),
            order_ids=[order_id],
            deduction_ids=[d.deduction_id for d in ordered],
            components=[
                {"label": f"Duplicate {code} charge {d.deduction_id}", "amount": d.amount}
                for d in extras
            ],
            support_limit=amount,
            confidence=1.0,
            event_code=code,
            event_date=keep.applied_at,
            evidence={
                "quote": quote,
                "timestamps": {
                    d.deduction_id: iso_dt(d.applied_at) for d in ordered
                },
                "arithmetic": arithmetic,
                "kept_deduction_id": keep.deduction_id,
                "duplicate_deduction_ids": [d.deduction_id for d in extras],
                "deduction_code": code,
            },
        )


def detect_over_cap_deductions(ctx: DetectionContext) -> None:
    for deduction in ctx.statement.deductions:
        remaining = ctx.allocation.remaining_for(deduction.deduction_id)
        if remaining <= 0:
            continue
        order = ctx.statement.orders_by_id.get(deduction.order_id)
        if order is None:
            ctx.add_review(
                "orphan_deduction",
                f"Deduction {deduction.deduction_id} has no matching order; cannot evaluate the cap.",
                deduction_ids=[deduction.deduction_id],
                confidence=0.4,
            )
            continue
        clause = ctx.policy.find(
            "over_cap_deduction",
            deduction.code,
            deduction.applied_at,
            ctx.statement.meta.jurisdiction,
        )
        if clause is None:
            continue
        cap = ctx.policy.evaluate_cap(clause, order.expected_pay)
        if cap is None:
            continue
        if remaining <= cap + Decimal("0.01"):
            continue
        excess = quantize_money(remaining - cap)
        ctx.allocation.consume(deduction.deduction_id, excess)
        ctx.add_claim(
            "over_cap_deduction",
            excess,
            (
                f"The {deduction.code} deduction of {format_inr(remaining)} on order "
                f"{order.order_id} is above the policy cap of {format_inr(cap)}; "
                f"the excess is contestable."
            ),
            order_ids=[order.order_id],
            deduction_ids=[deduction.deduction_id],
            components=[
                {
                    "label": f"{deduction.code} deduction {deduction.deduction_id} above cap",
                    "amount": excess,
                }
            ],
            support_limit=excess,
            confidence=0.98,
            clause=clause,
            event_code=deduction.code,
            event_date=deduction.applied_at,
            evidence={
                "quote": (
                    f"Order {order.order_id}: {deduction.code} deduction "
                    f"{format_inr(remaining)}; policy cap {format_inr(cap)}."
                ),
                "timestamps": {
                    deduction.deduction_id: iso_dt(deduction.applied_at),
                    **(
                        {"order_delivered_at": iso_dt(order.delivered_at)}
                        if order.delivered_at is not None
                        else {}
                    ),
                },
                "arithmetic": (
                    f"{format_inr(remaining)} - {format_inr(cap)} cap = "
                    f"{format_inr(excess)} claim"
                ),
                "cap": money_float(cap),
                "deduction_remaining_before": money_float(remaining),
                "order_expected_pay": money_float(order.expected_pay),
                "deduction_code": deduction.code,
            },
        )


def detect_restaurant_delay_penalties(ctx: DetectionContext) -> None:
    for deduction in ctx.statement.deductions:
        if deduction.code != "LATE":
            continue
        remaining = ctx.allocation.remaining_for(deduction.deduction_id)
        if remaining <= 0:
            continue
        order = ctx.statement.orders_by_id.get(deduction.order_id)
        if order is None:
            continue
        prep = order.restaurant_prep_minutes
        if prep is None:
            ctx.add_review(
                "missing_prep_time",
                (
                    f"Late penalty {deduction.deduction_id} cannot be evaluated because "
                    "the statement has no restaurant preparation time."
                ),
                order_ids=[order.order_id],
                deduction_ids=[deduction.deduction_id],
                confidence=0.5,
            )
            continue
        if prep <= 20:
            continue
        amount = remaining
        ctx.allocation.consume(deduction.deduction_id, amount)
        ctx.add_claim(
            "restaurant_delay_penalty",
            amount,
            (
                f"Order {order.order_id} had {prep} minutes of restaurant preparation, "
                f"above the 20-minute protection threshold. The remaining late penalty "
                f"of {format_inr(amount)} is contestable."
            ),
            order_ids=[order.order_id],
            deduction_ids=[deduction.deduction_id],
            components=[
                {
                    "label": f"Remaining late penalty {deduction.deduction_id}",
                    "amount": amount,
                }
            ],
            support_limit=amount,
            confidence=0.9,
            event_code="LATE",
            event_date=deduction.applied_at,
            evidence={
                "quote": (
                    f"Order {order.order_id}: restaurant prep {prep} min; "
                    f"LATE penalty {format_inr(remaining)}."
                ),
                "timestamps": _dt_map(
                    accepted_at=order.accepted_at,
                    picked_up_at=order.picked_up_at,
                    delivered_at=order.delivered_at,
                    promised_delivery_at=order.promised_delivery_at,
                    penalty_applied_at=deduction.applied_at,
                ),
                "arithmetic": (
                    f"{format_inr(remaining)} remaining late penalty = "
                    f"{format_inr(amount)} claim"
                ),
                "restaurant_prep_minutes": prep,
                "protection_threshold_minutes": 20,
                "deduction_code": deduction.code,
            },
        )


def detect_incentive_shortfalls(ctx: DetectionContext) -> None:
    for incentive in ctx.statement.incentives:
        if incentive.target_orders <= 0:
            ctx.add_review(
                "ambiguous_incentive_target",
                (
                    f"Incentive {incentive.incentive_id} has no positive order target; "
                    "eligibility cannot be determined deterministically."
                ),
                incentive_ids=[incentive.incentive_id],
                confidence=0.4,
            )
            continue
        if incentive.achieved_orders < incentive.target_orders:
            continue
        if incentive.amount_paid + Decimal("0.01") >= incentive.amount_promised:
            continue
        amount = quantize_money(incentive.amount_promised - incentive.amount_paid)
        ctx.add_claim(
            "incentive_shortfall",
            amount,
            (
                f"Incentive {incentive.incentive_id} ({incentive.name}) had a target of "
                f"{incentive.target_orders} orders and {incentive.achieved_orders} were "
                f"achieved, but the payout is {format_inr(incentive.amount_paid)} against "
                f"a promised {format_inr(incentive.amount_promised)}."
            ),
            incentive_ids=[incentive.incentive_id],
            components=[
                {
                    "label": f"Incentive {incentive.incentive_id} shortfall",
                    "amount": amount,
                }
            ],
            support_limit=amount,
            confidence=1.0,
            event_code="INC",
            event_date=ctx.statement.meta.period_end,
            evidence={
                "quote": (
                    f"Incentive {incentive.incentive_id}: target "
                    f"{incentive.target_orders} orders, achieved "
                    f"{incentive.achieved_orders}, promised "
                    f"{format_inr(incentive.amount_promised)}, paid "
                    f"{format_inr(incentive.amount_paid)}."
                ),
                "arithmetic": (
                    f"{format_inr(incentive.amount_promised)} promised - "
                    f"{format_inr(incentive.amount_paid)} paid = {format_inr(amount)} claim"
                ),
                "target_orders": incentive.target_orders,
                "achieved_orders": incentive.achieved_orders,
                "amount_promised": money_float(incentive.amount_promised),
                "amount_paid": money_float(incentive.amount_paid),
                "qualifying_order_ids": incentive.qualifying_order_ids,
            },
        )


def detect_missing_earnings(ctx: DetectionContext) -> None:
    for order in ctx.statement.orders:
        if not order.is_delivered:
            continue
        expected = quantize_money(order.expected_pay)
        if expected <= 0:
            continue
        actual = ctx.statement.earnings_total(order.order_id)
        if actual == 0:
            ctx.add_claim(
                "missing_earning",
                expected,
                (
                    f"Order {order.order_id} is marked delivered but has no earning "
                    f"entry. The expected order pay is {format_inr(expected)}."
                ),
                order_ids=[order.order_id],
                components=[
                    {"label": f"Missing earnings for {order.order_id}", "amount": expected}
                ],
                support_limit=expected,
                confidence=0.95,
                event_code="EARN",
                event_date=order.delivered_at or order.accepted_at,
                evidence={
                    "quote": (
                        f"Order {order.order_id}: delivered, expected "
                        f"{format_inr(expected)}, recorded ₹0.00."
                    ),
                    "timestamps": _dt_map(
                        accepted_at=order.accepted_at,
                        delivered_at=order.delivered_at,
                    ),
                    "arithmetic": (
                        f"{format_inr(expected)} expected - ₹0.00 recorded = "
                        f"{format_inr(expected)} claim"
                    ),
                    "expected_pay": money_float(expected),
                    "actual_earnings": money_float(actual),
                    "order_status": order.status,
                },
            )
        elif actual + Decimal("0.01") < expected:
            shortfall = quantize_money(expected - actual)
            ctx.add_review(
                "partial_earning",
                (
                    f"Order {order.order_id} is delivered with {format_inr(actual)} "
                    f"recorded against {format_inr(expected)} expected; the "
                    f"{format_inr(shortfall)} shortfall needs review before claiming."
                ),
                order_ids=[order.order_id],
                confidence=0.8,
                evidence={
                    "expected_pay": money_float(expected),
                    "actual_earnings": money_float(actual),
                    "shortfall": money_float(shortfall),
                },
            )


def detect_structural_review_items(ctx: DetectionContext) -> None:
    known_deduction_codes = {"LATE", "CANCEL"}
    for deduction in ctx.statement.deductions:
        if not deduction.order_id:
            ctx.add_review(
                "orphan_deduction",
                (
                    f"Deduction {deduction.deduction_id} ({deduction.code}) has no order "
                    "reference and cannot be matched to an order."
                ),
                deduction_ids=[deduction.deduction_id],
                confidence=0.3,
                evidence={
                    "deduction_code": deduction.code,
                    "amount": money_float(deduction.amount),
                    "applied_at": iso_dt(deduction.applied_at),
                },
            )
            continue
        if deduction.order_id not in ctx.statement.orders_by_id:
            ctx.add_review(
                "unknown_order_reference",
                (
                    f"Deduction {deduction.deduction_id} references order "
                    f"{deduction.order_id!r}, which is not in the statement."
                ),
                deduction_ids=[deduction.deduction_id],
                confidence=0.3,
            )
        if deduction.code not in known_deduction_codes:
            ctx.add_review(
                "unknown_deduction_code",
                (
                    f"Deduction {deduction.deduction_id} uses an unrecognised code "
                    f"{deduction.code!r}. The amount needs human review before any claim."
                ),
                order_ids=[deduction.order_id] if deduction.order_id else [],
                deduction_ids=[deduction.deduction_id],
                confidence=0.4,
                evidence={
                    "deduction_code": deduction.code,
                    "amount": money_float(deduction.amount),
                },
            )
        applied_day = deduction.applied_at.date()
        if not (
            ctx.policy.effective_from <= applied_day <= ctx.policy.effective_to
        ):
            ctx.add_review(
                "policy_not_effective",
                (
                    f"Deduction {deduction.deduction_id} was applied on "
                    f"{applied_day.isoformat()}, outside the policy period "
                    f"{ctx.policy.effective_from.isoformat()} to "
                    f"{ctx.policy.effective_to.isoformat()}."
                ),
                order_ids=[deduction.order_id] if deduction.order_id else [],
                deduction_ids=[deduction.deduction_id],
                confidence=0.4,
            )

    for order in ctx.statement.orders:
        component_total = quantize_money(order.base_pay + order.surge_pay + order.tip)
        if (
            order.total_pay > 0
            and component_total > 0
            and abs(order.total_pay - component_total) > Decimal("0.01")
        ):
            ctx.add_review(
                "order_total_mismatch",
                (
                    f"Order {order.order_id} states {format_inr(order.total_pay)} total "
                    f"but its components sum to {format_inr(component_total)}."
                ),
                order_ids=[order.order_id],
                confidence=0.7,
                evidence={
                    "total_pay": money_float(order.total_pay),
                    "component_total": money_float(component_total),
                },
            )


def run_detectors(statement: Statement, policy: PolicyBook) -> DetectionContext:
    ctx = DetectionContext(statement=statement, policy=policy)
    detect_duplicate_deductions(ctx)
    detect_over_cap_deductions(ctx)
    detect_restaurant_delay_penalties(ctx)
    detect_incentive_shortfalls(ctx)
    detect_missing_earnings(ctx)
    detect_structural_review_items(ctx)
    return ctx
