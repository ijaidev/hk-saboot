"""Claim and review-item models used by the audit engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .schema import format_inr, money_float, quantize_money

CLAIM_TYPES = (
    "duplicate_deduction",
    "over_cap_deduction",
    "restaurant_delay_penalty",
    "incentive_shortfall",
    "missing_earning",
)


@dataclass
class Claim:
    claim_id: str
    claim_type: str
    amount: Decimal
    currency: str
    status: str
    confidence: float
    reason: str
    order_ids: list[str] = field(default_factory=list)
    deduction_ids: list[str] = field(default_factory=list)
    earning_ids: list[str] = field(default_factory=list)
    incentive_ids: list[str] = field(default_factory=list)
    components: list[dict[str, Any]] = field(default_factory=list)
    support_limit: Decimal = Decimal("0.00")
    policy_clause_id: str | None = None
    policy_clause: dict[str, Any] | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    verification_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        amount = quantize_money(self.amount)
        return {
            "claim_id": self.claim_id,
            "claim_type": self.claim_type,
            "amount": money_float(amount),
            "amount_display": format_inr(amount),
            "currency": self.currency,
            "status": self.status,
            "confidence": round(float(self.confidence), 4),
            "reason": self.reason,
            "order_ids": self.order_ids,
            "deduction_ids": self.deduction_ids,
            "earning_ids": self.earning_ids,
            "incentive_ids": self.incentive_ids,
            "components": [
                {
                    "label": c.get("label", ""),
                    "amount": money_float(c.get("amount", Decimal("0.00"))),
                    "amount_display": format_inr(c.get("amount", Decimal("0.00"))),
                }
                for c in self.components
            ],
            "support_limit": money_float(self.support_limit),
            "policy_clause_id": self.policy_clause_id,
            "policy_clause": self.policy_clause,
            "evidence": self.evidence,
            "verification": {
                "passed": not self.verification_errors,
                "errors": self.verification_errors,
            },
        }


@dataclass
class ReviewItem:
    review_id: str
    review_type: str
    description: str
    order_ids: list[str] = field(default_factory=list)
    deduction_ids: list[str] = field(default_factory=list)
    incentive_ids: list[str] = field(default_factory=list)
    confidence: float = 0.5
    status: str = "needs_review"
    evidence: dict[str, Any] = field(default_factory=dict)
    policy_clause_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "review_type": self.review_type,
            "description": self.description,
            "order_ids": self.order_ids,
            "deduction_ids": self.deduction_ids,
            "incentive_ids": self.incentive_ids,
            "confidence": round(float(self.confidence), 4),
            "status": self.status,
            "evidence": self.evidence,
            "policy_clause_id": self.policy_clause_id,
        }
