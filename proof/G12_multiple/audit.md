# Saboot audit — ST-G12_multiple

**Platform:** QuickDrop | **Worker:** W-1042 | **Period:** 2026-10-01 to 2026-10-31 | **Jurisdiction:** IN-KA

**Policy:** quickdrop-policy-2026.1 (v2026.1, synthetic) | **Generated:** 2026-11-09T17:50:04.674271+00:00

> **Demo note:** QuickDrop is a fictional platform and this policy pack is synthetic. Statements are synthetic. This is a request-for-review workflow, not legal advice.

## Summary

| Metric | Value |
|---|---:|
| Potential disputed | **₹217.00** |
| Ready for human review | ₹217.00 |
| Needs review | ₹0.00 |
| Claims | 4 |
| Review items | 0 |
| Verifier | PASS |

## Claims

### C-001 — Duplicate Deduction — ₹75.00

- **Status:** Ready for human review  | **Confidence:** 1.00
- **Why:** Order QD-12001 has 2 LATE deductions. The policy allows one deduction per order and reason; 1 duplicate charge is contestable.
- **Orders:** `QD-12001`
- **Deductions:** `D-0001`, `D-0002`
- **Policy:** `QD-DED-001` — One deduction per order and reason ([source](https://quickdrop.example/policy/deductions#QD-DED-001), effective 2026-01-01 to 2026-12-31)
- **Arithmetic:** ₹75.00 in duplicate LATE charges; one charge of ₹75.00 is allowed = ₹75.00 claim
- **Components:**
  - Duplicate LATE charge D-0002: ₹75.00
- **Source rows:** orders:QD-12001 → orders.csv:2; deductions:D-0001 → deductions.csv:2; deductions:D-0002 → deductions.csv:3
- **Timestamps:**
  - `D-0001`: 2026-10-01T19:10:00+05:30
  - `D-0002`: 2026-10-01T19:14:00+05:30

### C-002 — Restaurant Delay Penalty — ₹50.00

- **Status:** Ready for human review  | **Confidence:** 0.90
- **Why:** Order QD-12002 had 29 minutes of restaurant preparation, above the 20-minute protection threshold. The remaining late penalty of ₹50.00 is contestable.
- **Orders:** `QD-12002`
- **Deductions:** `D-0003`
- **Policy:** `QD-DED-004` — Restaurant delay protection ([source](https://quickdrop.example/policy/deductions#QD-DED-004), effective 2026-01-01 to 2026-12-31)
- **Arithmetic:** ₹50.00 remaining late penalty = ₹50.00 claim
- **Components:**
  - Remaining late penalty D-0003: ₹50.00
- **Source rows:** orders:QD-12002 → orders.csv:3; deductions:D-0003 → deductions.csv:4
- **Timestamps:**
  - `accepted_at`: 2026-10-02T18:00:00+05:30
  - `picked_up_at`: 2026-10-02T18:29:00+05:30
  - `delivered_at`: 2026-10-02T18:42:00+05:30
  - `promised_delivery_at`: 2026-10-02T18:40:00+05:30
  - `penalty_applied_at`: 2026-10-02T19:10:00+05:30

### C-003 — Incentive Shortfall — ₹50.00

- **Status:** Ready for human review  | **Confidence:** 1.00
- **Why:** Incentive INC-0001 (5-order streak) had a target of 5 orders and 5 were achieved, but the payout is ₹450.00 against a promised ₹500.00.
- **Incentives:** `INC-0001`
- **Policy:** `QD-INC-001` — Incentive payment ([source](https://quickdrop.example/policy/incentives#QD-INC-001), effective 2026-01-01 to 2026-12-31)
- **Arithmetic:** ₹500.00 promised - ₹450.00 paid = ₹50.00 claim
- **Components:**
  - Incentive INC-0001 shortfall: ₹50.00
- **Source rows:** incentives:INC-0001 → incentives.csv:2

### C-004 — Missing Earning — ₹42.00

- **Status:** Ready for human review  | **Confidence:** 0.95
- **Why:** Order QD-12003 is marked delivered but has no earning entry. The expected order pay is ₹42.00.
- **Orders:** `QD-12003`
- **Policy:** `QD-EARN-001` — Earnings for delivered orders ([source](https://quickdrop.example/policy/earnings#QD-EARN-001), effective 2026-01-01 to 2026-12-31)
- **Arithmetic:** ₹42.00 expected - ₹0.00 recorded = ₹42.00 claim
- **Components:**
  - Missing earnings for QD-12003: ₹42.00
- **Source rows:** orders:QD-12003 → orders.csv:4
- **Timestamps:**
  - `accepted_at`: 2026-10-03T18:00:00+05:30
  - `delivered_at`: 2026-10-03T18:25:00+05:30

## Review items

No review items.

## Reconciliation

| Order | Status | Expected | Actual | Delta |
|---|---|---:|---:|---:|
| `QD-12001` | paid | ₹42.00 | ₹42.00 | ₹0.00 |
| `QD-12002` | paid | ₹200.00 | ₹200.00 | ₹0.00 |
| `QD-12003` | unpaid | ₹42.00 | ₹0.00 | -₹42.00 |
| `QD-12004` | paid | ₹100.00 | ₹100.00 | ₹0.00 |
| `QD-12005` | paid | ₹100.00 | ₹100.00 | ₹0.00 |

## Verification

PASS — every claim is supported by the statement and an applicable policy clause.

## Policy citations

- **QD-DED-001** — One deduction per order and reason  <https://quickdrop.example/policy/deductions#QD-DED-001>  (effective 2026-01-01 to 2026-12-31)
- **QD-DED-004** — Restaurant delay protection  <https://quickdrop.example/policy/deductions#QD-DED-004>  (effective 2026-01-01 to 2026-12-31)
- **QD-EARN-001** — Earnings for delivered orders  <https://quickdrop.example/policy/earnings#QD-EARN-001>  (effective 2026-01-01 to 2026-12-31)
- **QD-INC-001** — Incentive payment  <https://quickdrop.example/policy/incentives#QD-INC-001>  (effective 2026-01-01 to 2026-12-31)

---

This is a request for review, not legal advice. No claim is sent automatically. A human must review the evidence and approve any appeal.
