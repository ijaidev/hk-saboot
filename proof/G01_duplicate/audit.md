# Saboot audit — ST-G01_duplicate

**Platform:** QuickDrop | **Worker:** W-1042 | **Period:** 2026-10-01 to 2026-10-31 | **Jurisdiction:** IN-KA

**Policy:** quickdrop-policy-2026.1 (v2026.1, synthetic) | **Generated:** 2026-11-09T17:50:03.500288+00:00

> **Demo note:** QuickDrop is a fictional platform and this policy pack is synthetic. Statements are synthetic. This is a request-for-review workflow, not legal advice.

## Summary

| Metric | Value |
|---|---:|
| Potential disputed | **₹75.00** |
| Ready for human review | ₹75.00 |
| Needs review | ₹0.00 |
| Claims | 1 |
| Review items | 0 |
| Verifier | PASS |

## Claims

### C-001 — Duplicate Deduction — ₹75.00

- **Status:** Ready for human review  | **Confidence:** 1.00
- **Why:** Order QD-1001 has 2 LATE deductions. The policy allows one deduction per order and reason; 1 duplicate charge is contestable.
- **Orders:** `QD-1001`
- **Deductions:** `D-0001`, `D-0002`
- **Policy:** `QD-DED-001` — One deduction per order and reason ([source](https://quickdrop.example/policy/deductions#QD-DED-001), effective 2026-01-01 to 2026-12-31)
- **Arithmetic:** ₹75.00 in duplicate LATE charges; one charge of ₹75.00 is allowed = ₹75.00 claim
- **Components:**
  - Duplicate LATE charge D-0002: ₹75.00
- **Source rows:** orders:QD-1001 → orders.csv:2; deductions:D-0001 → deductions.csv:2; deductions:D-0002 → deductions.csv:3
- **Timestamps:**
  - `D-0001`: 2026-10-01T19:10:00+05:30
  - `D-0002`: 2026-10-01T19:14:00+05:30

## Review items

No review items.

## Reconciliation

| Order | Status | Expected | Actual | Delta |
|---|---|---:|---:|---:|
| `QD-1001` | paid | ₹42.00 | ₹42.00 | ₹0.00 |

## Verification

PASS — every claim is supported by the statement and an applicable policy clause.

## Policy citations

- **QD-DED-001** — One deduction per order and reason  <https://quickdrop.example/policy/deductions#QD-DED-001>  (effective 2026-01-01 to 2026-12-31)

---

This is a request for review, not legal advice. No claim is sent automatically. A human must review the evidence and approve any appeal.
