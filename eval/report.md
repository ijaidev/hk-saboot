# Saboot — golden-fixture evaluation

Generated: 2026-11-11T05:15:45.109919+00:00

This is a small, hand-authored regression set, not the planned 200-case benchmark. It covers the five MVP claim types and eight fair/settled statements.

## Aggregate

| Metric | Value |
|---|---:|
| Fixtures | 20 / 20 passed |
| Expected claims | 17 |
| Actual claims | 17 |
| Matched | 17 |
| False positives | 0 |
| False negatives | 0 |
| Precision | 1.00 |
| Recall | 1.00 |
| F1 | 1.00 |
| Verifier pass | 20 / 20 |

## Claim-type coverage

| Claim type | Actual claims |
|---|---:|
| `duplicate_deduction` | 4 |
| `incentive_shortfall` | 3 |
| `missing_earning` | 3 |
| `over_cap_deduction` | 4 |
| `restaurant_delay_penalty` | 3 |

## Fixture results

| Fixture | Expected | Actual | Matched | FP | FN | Expected ₹ | Actual ₹ | Review | Verifier | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| `F01_clean` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 0 | PASS | PASS |
| `F02_legit_late` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 0 | PASS | PASS |
| `F03_legit_cancel` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 0 | PASS | PASS |
| `F04_incentive_full` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 0 | PASS | PASS |
| `F05_valid_late_short_prep` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 0 | PASS | PASS |
| `F06_tips_and_surge` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 0 | PASS | PASS |
| `F07_cancelled_no_earning` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 0 | PASS | PASS |
| `F08_boundary_cap` | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 0 | PASS | PASS |
| `G01_duplicate` | 1 | 1 | 1 | 0 | 0 | 75.00 | 75.00 | 0 | PASS | PASS |
| `G02_over_cap_late` | 1 | 1 | 1 | 0 | 0 | 50.00 | 50.00 | 0 | PASS | PASS |
| `G03_restaurant_delay` | 1 | 1 | 1 | 0 | 0 | 50.00 | 50.00 | 0 | PASS | PASS |
| `G04_incentive_shortfall` | 1 | 1 | 1 | 0 | 0 | 50.00 | 50.00 | 0 | PASS | PASS |
| `G05_missing_earning` | 1 | 1 | 1 | 0 | 0 | 42.00 | 42.00 | 0 | PASS | PASS |
| `G06_duplicate_and_over_cap` | 2 | 2 | 2 | 0 | 0 | 200.00 | 200.00 | 0 | PASS | PASS |
| `G07_delay_and_over_cap` | 2 | 2 | 2 | 0 | 0 | 150.00 | 150.00 | 0 | PASS | PASS |
| `G08_two_incentives` | 1 | 1 | 1 | 0 | 0 | 50.00 | 50.00 | 0 | PASS | PASS |
| `G09_missing_one_of_three` | 1 | 1 | 1 | 0 | 0 | 100.00 | 100.00 | 0 | PASS | PASS |
| `G10_duplicate_cancel` | 1 | 1 | 1 | 0 | 0 | 50.00 | 50.00 | 0 | PASS | PASS |
| `G11_over_cap_cancel` | 1 | 1 | 1 | 0 | 0 | 30.00 | 30.00 | 0 | PASS | PASS |
| `G12_multiple` | 4 | 4 | 4 | 0 | 0 | 217.00 | 217.00 | 0 | PASS | PASS |

## Notes and limitations

- Fixtures are synthetic and hand-authored; the fictional platform is QuickDrop.
- The set is intentionally small. It is a regression baseline, not a claim of real-world accuracy.
- Every expected claim is matched by type, amount, and order IDs; fair fixtures must produce zero claims.
- The verifier must pass for every fixture; a claim that fails verification becomes `needs_review`.
- The next evaluation step (after the UI checkpoint) is a larger generated + hand-audited set with per-type precision/recall.
