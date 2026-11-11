# Data card — Saboot demo

## What is in the repo

- **20 hand-authored golden fixtures** under `data/fixtures/golden/`: 12 unfair and 8 fair statements.
- **1 edge fixture** under `data/fixtures/edge/needs_review/`: an unknown deduction code that must become a review item.
- **Fictional policy pack** `data/policy/quickdrop_policy.json`: 7 clauses with source URLs and effective dates.
- **Synthetic text PDF** `proof/G01_duplicate/statement.pdf`: generated from the G01 bundle.
- **Screenshots, video, and PDF exports** generated locally from the synthetic fixtures.

## What is not in the repo

- No real worker names, phone numbers, account IDs, addresses, or payout statements.
- No real platform data.
- No personal data from the human submitter.
- No API keys or secrets.

## How the data was made

The fixtures are explicit, hand-authored scenarios. `tools/make_fixtures.py` materializes them as CSV so they are reproducible. The policy pack is fictional and labeled as synthetic. The text PDF is generated from a fixture by `tools/make_pdf.py`.

## Coverage

| Claim type | Fixtures |
|---|---|
| Duplicate deduction | G01, G06, G10, G12 |
| Over-cap deduction | G02, G06, G07, G11 |
| Restaurant-delay penalty | G03, G07, G12 |
| Incentive shortfall | G04, G08, G12 |
| Missing earning | G05, G09, G12 |
| Fair / no claim | F01–F08 |
| Needs review | edge/needs_review |

## Limitations

- The set is small and synthetic. It is a regression baseline, not a claim of real-world accuracy.
- Real platform statements vary in layout, codes, and policy terms; adapters are future work.
- The policy pack is fictional; real policy coverage requires versioned, sourced clauses.
- No OCR/scanned-image data is included.
- The demo video uses a local TTS voice; it is synthetic narration, not a human worker.

## Evaluation

See `eval/report.md` and `eval/results.json`:

- 20/20 fixtures passed
- 17/17 expected claims matched
- 0 false positives / 0 false negatives
- Verifier 20/20

## Responsible use

All outputs are requests for review, not legal advice. No claim is auto-sent. The demo is clearly labeled synthetic, and the fictional platform avoids trademark/defamation risk.
