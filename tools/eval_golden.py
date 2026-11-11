#!/usr/bin/env python3
"""Run the 20 hand-authored golden fixtures and write a small evaluation report."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from saboot.audit import audit_statement
from saboot.ingestion import read_bundle
from saboot.policy import PolicyBook

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "fixtures" / "golden"
POLICY_PATH = ROOT / "data" / "policy" / "quickdrop_policy.json"
OUT = ROOT / "eval"


def match_claims(expected: list[dict[str, Any]], actual: list[Any]) -> tuple[list[tuple[dict, Any]], list[Any], list[dict]]:
    remaining = list(actual)
    matched: list[tuple[dict, Any]] = []
    for expected_claim in expected:
        found = None
        for claim in remaining:
            if (
                claim.claim_type == expected_claim["type"]
                and abs(float(claim.amount) - float(expected_claim["amount"])) < 0.01
                and set(expected_claim.get("order_ids", [])).issubset(set(claim.order_ids))
            ):
                found = claim
                break
        if found is not None:
            matched.append((expected_claim, found))
            remaining.remove(found)
    false_negatives = [
        item for item in expected if not any(item is pair[0] for pair in matched)
    ]
    return matched, remaining, false_negatives


def main() -> int:
    policy = PolicyBook.load(POLICY_PATH)
    fixtures = sorted(path for path in GOLDEN.iterdir() if path.is_dir())
    rows: list[dict[str, Any]] = []
    total_expected = total_actual = total_matched = 0
    total_fp = total_fn = 0
    verifier_pass = 0
    type_counts: dict[str, int] = {}

    for fixture in fixtures:
        expected = json.loads((fixture / "expected.json").read_text())
        statement = read_bundle(fixture / "statement")
        result = audit_statement(statement, policy)
        matched, false_positives, false_negatives = match_claims(
            expected["expected_claims"], result.claims
        )
        total_expected += len(expected["expected_claims"])
        total_actual += len(result.claims)
        total_matched += len(matched)
        total_fp += len(false_positives)
        total_fn += len(false_negatives)
        if result.verification["passed"]:
            verifier_pass += 1
        for claim in result.claims:
            type_counts[claim.claim_type] = type_counts.get(claim.claim_type, 0) + 1

        passed = (
            not false_positives
            and not false_negatives
            and abs(result.summary()["total_potential"] - expected["expected_total"]) < 0.01
            and len(result.review_items) == expected["expected_review_items"]
            and result.verification["passed"]
        )
        rows.append(
            {
                "fixture": fixture.name,
                "description": expected["description"],
                "expected_claims": expected["expected_claim_count"],
                "actual_claims": len(result.claims),
                "matched": len(matched),
                "false_positives": len(false_positives),
                "false_negatives": len(false_negatives),
                "expected_total": expected["expected_total"],
                "actual_total": result.summary()["total_potential"],
                "review_items": len(result.review_items),
                "verifier_passed": result.verification["passed"],
                "passed": passed,
                "actual": [
                    {
                        "type": claim.claim_type,
                        "amount": float(claim.amount),
                        "status": claim.status,
                        "order_ids": claim.order_ids,
                    }
                    for claim in result.claims
                ],
                "false_positive_detail": [
                    {
                        "type": claim.claim_type,
                        "amount": float(claim.amount),
                        "order_ids": claim.order_ids,
                    }
                    for claim in false_positives
                ],
                "false_negative_detail": false_negatives,
            }
        )

    precision = total_matched / (total_matched + total_fp) if (total_matched + total_fp) else 1.0
    recall = total_matched / (total_matched + total_fn) if (total_matched + total_fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    passed_count = sum(1 for row in rows if row["passed"])
    aggregate = {
        "fixtures_total": len(rows),
        "fixtures_passed": passed_count,
        "expected_claims": total_expected,
        "actual_claims": total_actual,
        "matched_claims": total_matched,
        "false_positives": total_fp,
        "false_negatives": total_fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "verifier_pass": verifier_pass,
        "claim_type_counts": dict(sorted(type_counts.items())),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(
        json.dumps({"aggregate": aggregate, "fixtures": rows}, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Saboot — golden-fixture evaluation",
        "",
        f"Generated: {aggregate['generated_at']}",
        "",
        "This is a small, hand-authored regression set, not the planned 200-case benchmark. "
        "It covers the five MVP claim types and eight fair/settled statements.",
        "",
        "## Aggregate",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Fixtures | {aggregate['fixtures_passed']} / {aggregate['fixtures_total']} passed |",
        f"| Expected claims | {aggregate['expected_claims']} |",
        f"| Actual claims | {aggregate['actual_claims']} |",
        f"| Matched | {aggregate['matched_claims']} |",
        f"| False positives | {aggregate['false_positives']} |",
        f"| False negatives | {aggregate['false_negatives']} |",
        f"| Precision | {aggregate['precision']:.2f} |",
        f"| Recall | {aggregate['recall']:.2f} |",
        f"| F1 | {aggregate['f1']:.2f} |",
        f"| Verifier pass | {aggregate['verifier_pass']} / {aggregate['fixtures_total']} |",
        "",
        "## Claim-type coverage",
        "",
        "| Claim type | Actual claims |",
        "|---|---:|",
    ]
    for claim_type, count in aggregate["claim_type_counts"].items():
        lines.append(f"| `{claim_type}` | {count} |")
    lines.extend(
        [
            "",
            "## Fixture results",
            "",
            "| Fixture | Expected | Actual | Matched | FP | FN | Expected ₹ | Actual ₹ | Review | Verifier | Result |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row['fixture']}` | {row['expected_claims']} | {row['actual_claims']} | "
            f"{row['matched']} | {row['false_positives']} | {row['false_negatives']} | "
            f"{row['expected_total']:.2f} | {row['actual_total']:.2f} | "
            f"{row['review_items']} | {'PASS' if row['verifier_passed'] else 'FAIL'} | "
            f"{'PASS' if row['passed'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## Notes and limitations",
            "",
            "- Fixtures are synthetic and hand-authored; the fictional platform is QuickDrop.",
            "- The set is intentionally small. It is a regression baseline, not a claim of real-world accuracy.",
            "- Every expected claim is matched by type, amount, and order IDs; fair fixtures must produce zero claims.",
            "- The verifier must pass for every fixture; a claim that fails verification becomes `needs_review`.",
            "- The next evaluation step (after the UI checkpoint) is a larger generated + hand-audited set with per-type precision/recall.",
            "",
        ]
    )
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")

    print(
        f"{aggregate['fixtures_passed']}/{aggregate['fixtures_total']} fixtures passed | "
        f"precision {aggregate['precision']:.2f} | recall {aggregate['recall']:.2f} | "
        f"FP {aggregate['false_positives']} | FN {aggregate['false_negatives']} | "
        f"verifier {aggregate['verifier_pass']}/{aggregate['fixtures_total']}"
    )
    print(f"Wrote {OUT / 'report.md'}")
    print(f"Wrote {OUT / 'results.json'}")
    return 0 if passed_count == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
