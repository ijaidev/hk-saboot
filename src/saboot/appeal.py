"""Template-first appeal generation with an optional, verified LLM rewrite."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from .audit import AuditResult
from .claims import Claim
from .llm import DraftProvider
from .schema import SabootError, format_inr, iso_dt, money_float, quantize_money
from .verifier import scan_text

AMOUNT_RE = re.compile(r"₹\s*([\d,]+(?:\.\d{1,2})?)")
CITATION_RE = re.compile(r"\bQD-[A-Z]+-\d{3}\b")
CLAIM_ID_RE = re.compile(r"\bC-\d{3}\b")


@dataclass
class AppealDraft:
    audit_id: str
    subject: str
    body: str
    claim_ids: list[str]
    total_amount: Decimal
    citations: list[dict[str, Any]]
    verification: dict[str, Any]
    provider: str
    generated_at: datetime
    approved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "subject": self.subject,
            "body": self.body,
            "claim_ids": self.claim_ids,
            "total_amount": money_float(self.total_amount),
            "total_display": format_inr(self.total_amount),
            "citations": self.citations,
            "verification": self.verification,
            "provider": self.provider,
            "generated_at": iso_dt(self.generated_at),
            "approved_at": self.approved_at,
        }


def _claim_title(claim: Claim) -> str:
    return claim.claim_type.replace("_", " ").title()


def _period(audit: AuditResult) -> str:
    return (
        f"{audit.statement.meta.period_start.date().isoformat()} to "
        f"{audit.statement.meta.period_end.date().isoformat()}"
    )


def build_template(audit: AuditResult, claims: list[Claim], approved_at: str | None = None) -> str:
    statement = audit.statement
    total = quantize_money(sum((c.amount for c in claims), Decimal("0")))
    lines = [
        "To: QuickDrop Partner Support",
        "",
        "Dear QuickDrop Partner Support,",
        "",
        (
            f"I am requesting a review of my payout statement for {_period(audit)}. "
            "I compared the deductions below with QuickDrop's published policy."
        ),
        "",
    ]
    for index, claim in enumerate(claims, start=1):
        lines.append(f"{index}. {_claim_title(claim)} — {format_inr(claim.amount)}")
        if claim.order_ids:
            lines.append(f"   Order(s): {', '.join(claim.order_ids)}")
        if claim.deduction_ids:
            lines.append(f"   Deduction(s): {', '.join(claim.deduction_ids)}")
        if claim.incentive_ids:
            lines.append(f"   Incentive(s): {', '.join(claim.incentive_ids)}")
        quote = claim.evidence.get("quote")
        if quote:
            lines.append(f'   Source: "{quote}"')
        if claim.policy_clause:
            clause = claim.policy_clause
            lines.append(
                f"   Policy: {clause.get('id')} — {clause.get('title', '')}"
            )
            lines.append(f"   Source URL: {clause.get('source_url')}")
        lines.append(f"   Why: {claim.reason}")
        if claim.policy_clause and claim.policy_clause.get("remedy"):
            lines.append(f"   Requested action: {claim.policy_clause['remedy']}")
        lines.append("")
    lines.extend(
        [
            f"Total requested for review: {format_inr(total)}.",
            "",
            (
                "Please confirm receipt and respond within the timeline in your "
                "published grievance process. I have kept the order and deduction "
                "references in the attached evidence pack."
            ),
            "",
            "This is a request for review, not legal advice. I have not sent this automatically.",
            "",
            "Sincerely,",
            statement.meta.worker_id,
        ]
    )
    return "\n".join(lines)


def _allowed_amounts(claims: list[Claim], total: Decimal) -> set[Decimal]:
    allowed: set[Decimal] = {quantize_money(total), Decimal("0.00")}
    for claim in claims:
        allowed.add(quantize_money(claim.amount))
        for component in claim.components:
            allowed.add(quantize_money(component["amount"]))
        for text in (
            claim.reason,
            str(claim.evidence.get("quote", "")),
            str(claim.evidence.get("arithmetic", "")),
        ):
            for raw in AMOUNT_RE.findall(text):
                try:
                    allowed.add(quantize_money(Decimal(raw.replace(",", ""))))
                except InvalidOperation:
                    continue
    return allowed


def verify_appeal_text(body: str, claims: list[Claim], audit: AuditResult) -> dict[str, Any]:
    errors: list[str] = []
    if not body.strip():
        return {"passed": False, "errors": ["appeal body is empty"]}

    errors.extend(scan_text(body))

    total = quantize_money(sum((c.amount for c in claims), Decimal("0")))
    allowed_amounts = _allowed_amounts(claims, total)
    for raw in AMOUNT_RE.findall(body):
        try:
            amount = quantize_money(Decimal(raw.replace(",", "")))
        except InvalidOperation:
            errors.append(f"unparseable amount in appeal: ₹{raw}")
            continue
        if amount not in allowed_amounts:
            errors.append(f"unsupported amount in appeal: {format_inr(amount)}")

    allowed_clause_ids = {
        c.policy_clause_id for c in claims if c.policy_clause_id is not None
    }
    for citation in CITATION_RE.findall(body):
        if citation not in allowed_clause_ids:
            errors.append(f"unsupported policy citation in appeal: {citation}")

    allowed_claim_ids = {c.claim_id for c in claims}
    for claim_id in CLAIM_ID_RE.findall(body):
        if claim_id not in allowed_claim_ids:
            errors.append(f"unsupported claim ID in appeal: {claim_id}")

    seen: set[str] = set()
    unique: list[str] = []
    for error in errors:
        if error not in seen:
            unique.append(error)
            seen.add(error)
    return {"passed": not unique, "errors": unique}


def _build_llm_prompt(audit: AuditResult, claims: list[Claim]) -> str:
    template = build_template(audit, claims)
    return (
        "You are helping a gig worker draft a formal request for review of a payout statement. "
        "Use only the facts and citations in the template below. Do not add new amounts, "
        "do not give legal advice, do not promise an outcome, and do not name any real platform. "
        "Keep it concise, polite, and specific. Return only the letter body.\n\n"
        f"{template}"
    )


def generate_appeal(
    audit: AuditResult,
    claim_ids: list[str],
    *,
    audit_id: str = "local",
    provider: DraftProvider | None = None,
    approved_at: str | None = None,
) -> AppealDraft:
    by_id = {claim.claim_id: claim for claim in audit.claims}
    claims = [by_id[cid] for cid in claim_ids if cid in by_id]
    if not claims:
        raise SabootError("No claims selected for the appeal.")
    bad = [c.claim_id for c in claims if c.status != "ready"]
    if bad:
        raise SabootError(
            "Cannot include needs-review claims in an appeal: " + ", ".join(bad)
        )

    total = quantize_money(sum((c.amount for c in claims), Decimal("0")))
    subject = f"Request for review — payout statement {audit.statement.meta.statement_id}"
    template = build_template(audit, claims, approved_at=approved_at)
    body = template
    provider_name = "template"

    if provider is not None and provider.name != "template":
        try:
            generated = provider.draft(_build_llm_prompt(audit, claims))
            candidate = generated.strip()
            candidate_verification = verify_appeal_text(candidate, claims, audit)
            if candidate and candidate_verification["passed"]:
                body = candidate
                provider_name = provider.name
        except Exception:
            # Any provider failure falls back to the deterministic template.
            pass

    verification = verify_appeal_text(body, claims, audit)
    if not verification["passed"] and body != template:
        body = template
        provider_name = "template"
        verification = verify_appeal_text(body, claims, audit)
    if not verification["passed"]:
        raise SabootError(
            "Appeal template failed verification: " + "; ".join(verification["errors"])
        )

    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for claim in claims:
        clause = claim.policy_clause
        if not clause or clause["id"] in seen:
            continue
        seen.add(clause["id"])
        citations.append(
            {
                "id": clause["id"],
                "title": clause.get("title", ""),
                "source_url": clause.get("source_url", ""),
                "effective_from": clause.get("effective_from"),
                "effective_to": clause.get("effective_to"),
            }
        )

    return AppealDraft(
        audit_id=audit_id,
        subject=subject,
        body=body,
        claim_ids=[c.claim_id for c in claims],
        total_amount=total,
        citations=citations,
        verification=verification,
        provider=provider_name,
        generated_at=datetime.now(timezone.utc),
        approved_at=approved_at,
    )
