# Saboot audit — ST-G03_restaurant_delay

**Platform:** QuickDrop | **Worker:** W-1042 | **Period:** 2026-10-01 to 2026-10-31 | **Jurisdiction:** IN-KA

**Policy:** quickdrop-policy-2026.1 (v2026.1, synthetic) | **Generated:** 2026-11-09T17:50:04.333676+00:00

> **Demo note:** QuickDrop is a fictional platform and this policy pack is synthetic. Statements are synthetic. This is a request-for-review workflow, not legal advice.

## Summary

| Metric | Value |
|---|---:|
| Potential disputed | **₹50.00** |
| Ready for human review | ₹50.00 |
| Needs review | ₹0.00 |
| Claims | 1 |
| Review items | 0 |
| Verifier | PASS |

## Claims

### C-001 — Restaurant Delay Penalty — ₹50.00

- **Status:** Ready for human review  | **Confidence:** 0.90
- **Why:** Order QD-3001 had 29 minutes of restaurant preparation, above the 20-minute protection threshold. The remaining late penalty of ₹50.00 is contestable.
- **Orders:** `QD-3001`
- **Deductions:** `D-0001`
- **Policy:** `QD-DED-004` — Restaurant delay protection ([source](https://quickdrop.example/policy/deductions#QD-DED-004), effective 2026-01-01 to 2026-12-31)
- **Arithmetic:** ₹50.00 remaining late penalty = ₹50.00 claim
- **Components:**
  - Remaining late penalty D-0001: ₹50.00
- **Source rows:** orders:QD-3001 → orders.csv:2; deductions:D-0001 → deductions.csv:2
- **Timestamps:**
  - `accepted_at`: 2026-10-01T18:00:00+05:30
  - `picked_up_at`: 2026-10-01T18:29:00+05:30
  - `delivered_at`: 2026-10-01T18:42:00+05:30
  - `promised_delivery_at`: 2026-10-01T18:40:00+05:30
  - `penalty_applied_at`: 2026-10-01T19:10:00+05:30

## Review items

No review items.

## Reconciliation

| Order | Status | Expected | Actual | Delta |
|---|---|---:|---:|---:|
| `QD-3001` | paid | ₹200.00 | ₹200.00 | ₹0.00 |

## Verification

PASS — every claim is supported by the statement and an applicable policy clause.

## Policy citations

- **QD-DED-004** — Restaurant delay protection  <https://quickdrop.example/policy/deductions#QD-DED-004>  (effective 2026-01-01 to 2026-12-31)

---

This is a request for review, not legal advice. No claim is sent automatically. A human must review the evidence and approve any appeal.
