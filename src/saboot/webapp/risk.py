"""Presentation-layer risk score for the audit report.

This is not a probability of winning a claim. It is a review-priority score:
how much money is disputed relative to the statement, plus claim volume and
items that need human review.
"""

from __future__ import annotations

from typing import Any


def compute_risk(audit: dict[str, Any]) -> dict[str, Any]:
    summary = audit.get("summary", {})
    recon = audit.get("reconciliation", {}).get("summary", {})
    expected = float(recon.get("total_expected", 0) or 0)
    potential = float(summary.get("total_potential", 0) or 0)
    exposure = potential / expected if expected > 0 else 0.0
    claims = int(summary.get("claim_count", 0) or 0)
    needs_review = int(summary.get("needs_review_count", 0) or 0) + int(
        summary.get("review_item_count", 0) or 0
    )

    score = round(
        65 * min(exposure, 1.0)
        + 8 * claims
        + 8 * needs_review
        + (10 if claims else 0)
    )
    score = max(0, min(100, score))
    if score >= 70:
        band = "high"
        label = "High review priority"
    elif score >= 40:
        band = "medium"
        label = "Medium review priority"
    else:
        band = "low"
        label = "Low review priority"

    return {
        "score": score,
        "band": band,
        "label": label,
        "description": (
            "Estimates how much of this statement needs review. "
            "It is not a prediction of the outcome."
        ),
        "factors": {
            "exposure_ratio": round(exposure, 4),
            "disputed_amount": round(potential, 2),
            "statement_pay": round(expected, 2),
            "claim_count": claims,
            "needs_review_count": needs_review,
        },
    }
