"""JSON and Markdown rendering for audit results."""

from __future__ import annotations

import json
from typing import Any

from .audit import AuditResult
from .claims import Claim
from .schema import format_inr, iso_dt

STATUS_LABEL = {
    "ready": "Ready for human review",
    "needs_review": "Needs review",
}


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def to_json(result: AuditResult) -> str:
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n"


def _claim_section(claim: Claim) -> list[str]:
    lines: list[str] = []
    lines.append(f"### {claim.claim_id} — {claim.claim_type.replace('_', ' ').title()} — {format_inr(claim.amount)}")
    lines.append("")
    lines.append(
        f"- **Status:** {STATUS_LABEL.get(claim.status, claim.status)}  "
        f"| **Confidence:** {claim.confidence:.2f}"
    )
    lines.append(f"- **Why:** {_md(claim.reason)}")
    if claim.order_ids:
        lines.append(f"- **Orders:** {', '.join(f'`{x}`' for x in claim.order_ids)}")
    if claim.deduction_ids:
        lines.append(f"- **Deductions:** {', '.join(f'`{x}`' for x in claim.deduction_ids)}")
    if claim.incentive_ids:
        lines.append(f"- **Incentives:** {', '.join(f'`{x}`' for x in claim.incentive_ids)}")
    if claim.earning_ids:
        lines.append(f"- **Earnings:** {', '.join(f'`{x}`' for x in claim.earning_ids)}")
    if claim.policy_clause:
        clause = claim.policy_clause
        lines.append(
            f"- **Policy:** `{clause.get('id')}` — {_md(clause.get('title', ''))} "
            f"([source]({clause.get('source_url')}), effective "
            f"{clause.get('effective_from')} to {clause.get('effective_to')})"
        )
    else:
        lines.append("- **Policy:** no applicable clause found; human review required")
    quote = claim.evidence.get("quote")
    if quote:
        lines.append(f"- **Source quote:** {_md(quote)}")
    arithmetic = claim.evidence.get("arithmetic")
    if arithmetic:
        lines.append(f"- **Arithmetic:** {_md(arithmetic)}")
    if claim.components:
        lines.append("- **Components:**")
        for component in claim.components:
            lines.append(
                f"  - {_md(component.get('label', ''))}: {format_inr(component['amount'])}"
            )
    source_rows = claim.evidence.get("source_rows", {})
    if source_rows:
        flat: list[str] = []
        for kind, mapping in source_rows.items():
            if isinstance(mapping, dict):
                for identifier, source in mapping.items():
                    flat.append(f"{kind}:{identifier} → {source}")
        if flat:
            lines.append(f"- **Source rows:** {'; '.join(_md(x) for x in flat)}")
    timestamps = claim.evidence.get("timestamps")
    if isinstance(timestamps, dict) and timestamps:
        lines.append("- **Timestamps:**")
        for key, value in timestamps.items():
            lines.append(f"  - `{key}`: {value}")
    if claim.verification_errors:
        lines.append("- **Verifier errors:**")
        for error in claim.verification_errors:
            lines.append(f"  - {_md(error)}")
    lines.append("")
    return lines


def to_markdown(result: AuditResult) -> str:
    summary = result.summary()
    meta = result.statement.meta
    lines: list[str] = []
    lines.append(f"# Saboot audit — {meta.statement_id}")
    lines.append("")
    lines.append(
        f"**Platform:** {meta.platform} | **Worker:** {meta.worker_id} | "
        f"**Period:** {meta.period_start.date().isoformat()} to {meta.period_end.date().isoformat()} | "
        f"**Jurisdiction:** {meta.jurisdiction}"
    )
    lines.append("")
    lines.append(
        f"**Policy:** {result.policy.id} (v{result.policy.version}, "
        f"{'synthetic' if result.policy.synthetic else 'source-backed'}) | "
        f"**Generated:** {iso_dt(result.generated_at)}"
    )
    lines.append("")
    if result.policy.synthetic:
        lines.append(
            "> **Demo note:** QuickDrop is a fictional platform and this policy pack is synthetic. "
            "Statements are synthetic. This is a request-for-review workflow, not legal advice."
        )
        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Potential disputed | **{format_inr(summary['total_potential'])}** |")
    lines.append(f"| Ready for human review | {format_inr(summary['total_ready'])} |")
    lines.append(f"| Needs review | {format_inr(summary['total_needs_review'])} |")
    lines.append(f"| Claims | {summary['claim_count']} |")
    lines.append(f"| Review items | {summary['review_item_count']} |")
    lines.append(
        f"| Verifier | {'PASS' if summary['verification_passed'] else 'FAIL'} |"
    )
    lines.append("")

    lines.append("## Claims")
    lines.append("")
    if not result.claims:
        lines.append("No claims detected.")
        lines.append("")
    else:
        for claim in result.claims:
            lines.extend(_claim_section(claim))

    lines.append("## Review items")
    lines.append("")
    if not result.review_items:
        lines.append("No review items.")
        lines.append("")
    else:
        for item in result.review_items:
            lines.append(
                f"### {item.review_id} — {item.review_type.replace('_', ' ').title()}"
            )
            lines.append("")
            lines.append(f"- **Status:** Needs review | **Confidence:** {item.confidence:.2f}")
            lines.append(f"- **Why:** {_md(item.description)}")
            if item.order_ids:
                lines.append(f"- **Orders:** {', '.join(f'`{x}`' for x in item.order_ids)}")
            if item.deduction_ids:
                lines.append(
                    f"- **Deductions:** {', '.join(f'`{x}`' for x in item.deduction_ids)}"
                )
            if item.incentive_ids:
                lines.append(
                    f"- **Incentives:** {', '.join(f'`{x}`' for x in item.incentive_ids)}"
                )
            lines.append("")

    lines.append("## Reconciliation")
    lines.append("")
    lines.append("| Order | Status | Expected | Actual | Delta |")
    lines.append("|---|---|---:|---:|---:|")
    for row in result.reconciliation:
        lines.append(
            f"| `{row.order_id}` | {row.status} | {format_inr(row.expected_pay)} | "
            f"{format_inr(row.actual_pay)} | {format_inr(row.delta)} |"
        )
    lines.append("")

    lines.append("## Verification")
    lines.append("")
    if result.verification.get("passed"):
        lines.append("PASS — every claim is supported by the statement and an applicable policy clause.")
    else:
        lines.append("FAIL — the following verifier errors were found:")
        lines.append("")
        for error in result.verification.get("errors", []):
            lines.append(f"- {_md(error)}")
    lines.append("")

    used_clauses: dict[str, dict[str, Any]] = {}
    for claim in result.claims:
        if claim.policy_clause:
            used_clauses[claim.policy_clause["id"]] = claim.policy_clause
    if used_clauses:
        lines.append("## Policy citations")
        lines.append("")
        for clause_id, clause in sorted(used_clauses.items()):
            lines.append(
                f"- **{clause_id}** — {_md(clause.get('title', ''))}  "
                f"<{clause.get('source_url')}>  "
                f"(effective {clause.get('effective_from')} to {clause.get('effective_to')})"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "This is a request for review, not legal advice. No claim is sent automatically. "
        "A human must review the evidence and approve any appeal."
    )
    lines.append("")
    return "\n".join(lines)
