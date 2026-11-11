"""Audit orchestration and result model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from . import __version__
from .claims import Claim, ReviewItem
from .detectors import run_detectors
from .policy import PolicyBook
from .reconciliation import OrderReconciliation, build_reconciliation, reconciliation_summary
from .schema import Statement, iso_dt, money_float, quantize_money
from .verifier import verify_claims


@dataclass
class AuditResult:
    statement: Statement
    policy: PolicyBook
    reconciliation: list[OrderReconciliation]
    claims: list[Claim]
    review_items: list[ReviewItem]
    verification: dict[str, Any]
    allocation_remaining: dict[str, float]
    generated_at: datetime
    engine: str = "deterministic-v1"

    def summary(self) -> dict[str, Any]:
        total_potential = quantize_money(sum((c.amount for c in self.claims), Decimal("0")))
        total_ready = quantize_money(
            sum((c.amount for c in self.claims if c.status == "ready"), Decimal("0"))
        )
        total_needs_review = quantize_money(
            sum(
                (c.amount for c in self.claims if c.status == "needs_review"),
                Decimal("0"),
            )
        )
        type_counts: dict[str, int] = {}
        for claim in self.claims:
            type_counts[claim.claim_type] = type_counts.get(claim.claim_type, 0) + 1
        return {
            "currency": self.statement.meta.currency,
            "total_potential": money_float(total_potential),
            "total_ready": money_float(total_ready),
            "total_needs_review": money_float(total_needs_review),
            "claim_count": len(self.claims),
            "ready_count": sum(1 for c in self.claims if c.status == "ready"),
            "needs_review_count": sum(1 for c in self.claims if c.status == "needs_review"),
            "review_item_count": len(self.review_items),
            "claim_type_counts": dict(sorted(type_counts.items())),
            "verification_passed": bool(self.verification.get("passed")),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_version": __version__,
            "engine": self.engine,
            "generated_at": iso_dt(self.generated_at),
            "statement": self.statement.to_dict(),
            "policy": self.policy.to_dict(),
            "reconciliation": {
                "orders": [row.to_dict() for row in self.reconciliation],
                "summary": reconciliation_summary(self.reconciliation),
            },
            "summary": self.summary(),
            "claims": [claim.to_dict() for claim in self.claims],
            "review_items": [item.to_dict() for item in self.review_items],
            "verification": self.verification,
            "allocation_remaining": self.allocation_remaining,
            "warnings": self.statement.warnings,
        }


def audit_statement(statement: Statement, policy: PolicyBook) -> AuditResult:
    ctx = run_detectors(statement, policy)
    verification = verify_claims(ctx.claims, statement, policy)
    return AuditResult(
        statement=statement,
        policy=policy,
        reconciliation=build_reconciliation(statement),
        claims=ctx.claims,
        review_items=ctx.review_items,
        verification=verification,
        allocation_remaining=ctx.allocation.snapshot(),
        generated_at=datetime.now(timezone.utc),
    )
