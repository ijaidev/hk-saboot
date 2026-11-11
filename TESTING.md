# TESTING.md — Saboot final delivery

All commands below were run from the `saboot/` repository root on **2026-11-10**.

## Environment

```text
Python 3.12.3
pdftotext 24.02.0 (poppler-utils)
Node 26.13.0
Playwright 1.65.0 (Chrome channel)
ElevenLabs TTS (George, eleven_multilingual_v2)
ffmpeg 6.x
Linux, no GPU
```

No third-party Python packages are required. CSV ingestion, the audit engine, the web server, and the PDF writer use the standard library. Text-PDF ingestion requires `pdftotext`. Playwright is only needed for the UI E2E.

## 1. Full test suite

Command:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result:

```text
Ran 57 tests in 5.260s

OK
exit_code=0
```

Full log: `proof/test_suite.txt`.

Coverage by file:

- `tests/test_schema.py` — money, datetime, INR formatting.
- `tests/test_ingestion.py` — CSV bundle, zip bundle, text PDF, missing files, duplicate IDs.
- `tests/test_detectors.py` — all five detectors, allocation ledger, fair fixtures.
- `tests/test_verifier.py` — fake amount, fake order, fake deduction, fake timestamp, fake clause, legal advice, outcome promise, real brand, missing clause.
- `tests/test_cli.py` — CSV/PDF CLI, JSON/Markdown output, strict mode, input errors.
- `tests/test_golden.py` — all 20 fixtures.
- `tests/test_appeal.py` — template appeal, needs-review refusal, bad-provider fallback, unsupported amount/citation, no-key default.
- `tests/test_pdf_export.py` — appeal/evidence PDF is extractable.
- `tests/test_webapp.py` — health, demo, PDF/ZIP upload, approve, appeal, export, error paths.
- `tests/test_risk.py` — risk-score bands and factors.

## 2. Golden-fixture evaluation

Command:

```bash
PYTHONPATH=src python3 tools/eval_golden.py
```

Result:

```text
20/20 fixtures passed | precision 1.00 | recall 1.00 | FP 0 | FN 0 | verifier 20/20
```

Full log: `proof/eval_stdout.txt`.
Report: `eval/report.md`.
Machine-readable: `eval/results.json`.

Hand-authored regression set: **17 expected claims**, **17 matched**, **0 false positives**, **0 false negatives**, **20/20 verifier passes**. This is not the planned 200-case benchmark.

## 3. CLI proof runs

### 3.1 Unfair — G01 duplicate deduction

```bash
PYTHONPATH=src python3 -m saboot audit \
  --bundle data/fixtures/golden/G01_duplicate/statement \
  --policy data/policy/quickdrop_policy.json \
  --out proof/G01_duplicate \
  --format both
```

```text
Saboot audit: ST-G01_duplicate (csv_bundle)
Claims: 1 | Potential: ₹75.00 | Ready: ₹75.00 | Needs review: ₹0.00
Review items: 0 | Verifier: PASS
Wrote: proof/G01_duplicate/audit.json
Wrote: proof/G01_duplicate/audit.md
exit_code=0
```

### 3.2 Unfair — G03 restaurant-delay penalty

```bash
PYTHONPATH=src python3 -m saboot audit \
  --bundle data/fixtures/golden/G03_restaurant_delay/statement \
  --policy data/policy/quickdrop_policy.json \
  --out proof/G03_restaurant_delay \
  --format both
```

```text
Saboot audit: ST-G03_restaurant_delay (csv_bundle)
Claims: 1 | Potential: ₹50.00 | Ready: ₹50.00 | Needs review: ₹0.00
Review items: 0 | Verifier: PASS
Wrote: proof/G03_restaurant_delay/audit.json
Wrote: proof/G03_restaurant_delay/audit.md
exit_code=0
```

### 3.3 Unfair — G12 multiple claim types

```bash
PYTHONPATH=src python3 -m saboot audit \
  --bundle data/fixtures/golden/G12_multiple/statement \
  --policy data/policy/quickdrop_policy.json \
  --out proof/G12_multiple \
  --format both
```

```text
Saboot audit: ST-G12_multiple (csv_bundle)
Claims: 4 | Potential: ₹217.00 | Ready: ₹217.00 | Needs review: ₹0.00
Review items: 0 | Verifier: PASS
Wrote: proof/G12_multiple/audit.json
Wrote: proof/G12_multiple/audit.md
exit_code=0
```

Claims: duplicate ₹75 + restaurant-delay ₹50 + incentive shortfall ₹50 + missing earning ₹42 = **₹217**.

### 3.4 Fair — F01 clean statement

```bash
PYTHONPATH=src python3 -m saboot audit \
  --bundle data/fixtures/golden/F01_clean/statement \
  --policy data/policy/quickdrop_policy.json \
  --out proof/F01_clean \
  --format both
```

```text
Saboot audit: ST-F01_clean (csv_bundle)
Claims: 0 | Potential: ₹0.00 | Ready: ₹0.00 | Needs review: ₹0.00
Review items: 0 | Verifier: PASS
Wrote: proof/F01_clean/audit.json
Wrote: proof/F01_clean/audit.md
exit_code=0
```

### 3.5 Fair — F08 boundary cap

```bash
PYTHONPATH=src python3 -m saboot audit \
  --bundle data/fixtures/golden/F08_boundary_cap/statement \
  --policy data/policy/quickdrop_policy.json \
  --out proof/F08_boundary_cap \
  --format both
```

```text
Saboot audit: ST-F08_boundary_cap (csv_bundle)
Claims: 0 | Potential: ₹0.00 | Ready: ₹0.00 | Needs review: ₹0.00
Review items: 0 | Verifier: PASS
Wrote: proof/F08_boundary_cap/audit.json
Wrote: proof/F08_boundary_cap/audit.md
exit_code=0
```

### 3.6 Needs-review state and strict mode

```bash
PYTHONPATH=src python3 -m saboot audit \
  --bundle data/fixtures/edge/needs_review/statement \
  --policy data/policy/quickdrop_policy.json \
  --out proof/needs_review \
  --format both \
  --strict
```

```text
Saboot audit: ST-G01_duplicate (csv_bundle)
Claims: 0 | Potential: ₹0.00 | Ready: ₹0.00 | Needs review: ₹0.00
Review items: 1 | Verifier: PASS
Wrote: proof/needs_review/audit.json
Wrote: proof/needs_review/audit.md
exit_code=1
```

`R-001 — Unknown Deduction Code` is a review item, not a claim. The strict mode exit code is 1 because a human must resolve it.

## 4. Text-PDF proof

```bash
python3 tools/make_pdf.py \
  data/fixtures/golden/G01_duplicate/statement \
  proof/G01_duplicate/statement.pdf

PYTHONPATH=src python3 -m saboot audit \
  --pdf proof/G01_duplicate/statement.pdf \
  --policy data/policy/quickdrop_policy.json \
  --out proof/G01_duplicate_pdf \
  --format both
```

```text
Saboot audit: ST-G01_duplicate (text_pdf)
Claims: 1 | Potential: ₹75.00 | Ready: ₹75.00 | Needs review: ₹0.00
Review items: 0 | Verifier: PASS
Wrote: proof/G01_duplicate_pdf/audit.json
Wrote: proof/G01_duplicate_pdf/audit.md
exit_code=0
```

## 5. Verifier negative tests

The verifier tests mutate a valid claim and assert rejection:

| Mutation | Expected rejection |
|---|---|
| claim amount + ₹1 | component sum / support limit |
| fake order ID | unknown order ID |
| fake deduction ID | unknown deduction ID |
| fabricated timestamp | timestamp not in statement |
| unknown policy clause | clause does not exist |
| legal advice | legal-advice language |
| outcome promise | outcome promise |
| real platform brand | real platform brand |
| missing clause | no policy clause |

All nine negative cases pass. A failed claim moves to `needs_review` with errors attached.

## 6. UI E2E proof (M4)

Command:

```bash
bash scripts/run_e2e.sh
```

The script starts the local server, runs:

```bash
SABOOT_BASE_URL=http://127.0.0.1:8765 \
  npx playwright test tests/ui/saboot.spec.js --reporter=line
```

and captures screenshots, video, console log, server log, and the exported PDF.

Result:

```text
Running 1 test using 1 worker

[1/1] tests/ui/saboot.spec.js:31:1 › upload PDF -> ₹75 claim -> evidence -> approve -> appeal -> verifier -> PDF
  1 passed (35.2s)

exit_code=0
```

The E2E asserts:

- upload `proof/G01_duplicate/statement.pdf`
- report shows **Duplicate deduction** and **₹75.00**
- summary disputed amount is **₹75.00**
- verifier summary is **PASS**
- “View evidence” exposes the source quote containing **2 × LATE**
- policy citation contains **QD-DED-001** and **quickdrop.example**
- human review checkbox enables approval
- approval status says **Approved 1 claim**
- appeal screen shows **Verifier PASS**
- appeal body contains **request for review** and **QD-DED-001**
- citations panel contains **QD-DED-001**
- PDF download saves `proof/ui/appeal.pdf`
- zero page errors and zero console errors

### UI proof artifacts

| Artifact | Path | Size |
|---|---|---|
| Upload screen | `proof/ui/01-upload.png` | ~279 KB |
| File selected | `proof/ui/02-file-selected.png` | ~285 KB |
| Report + risk score | `proof/ui/03-report.png` | ~245 KB |
| Evidence expanded | `proof/ui/04-evidence.png` | ~267 KB |
| Approved state | `proof/ui/05-approved.png` | ~255 KB |
| Appeal + citations | `proof/ui/06-appeal.png` | ~266 KB |
| E2E video | `proof/ui/e2e.mp4` | ~0.6 MB |
| Console log | `proof/ui/console.log` | 6 info lines, 0 errors |
| Server log | `proof/ui/server.log` | requests + 200/400/404 statuses |
| E2E command log | `proof/ui/e2e.log` | Playwright output + exit code |
| E2E summary | `proof/ui/e2e-summary.json` | flow, claim, quote, citation, verifier |
| Exported PDF | `proof/ui/appeal.pdf` | ~3.5 KB |

PDF extraction check:

```bash
pdftotext -layout proof/ui/appeal.pdf - | head -12
```

```text
SABOOT - REQUEST FOR REVIEW
Proof for every rupee.

Statement: ST-G01_duplicate
Worker: W-1042
Platform: QuickDrop (fictional demo platform)
Period: 2026-10-01 to 2026-10-31
Generated: ...
Draft provider: template
Total requested for review: Rs. 75.00
Verifier: PASS
```

## 6.1 Mobile 390×844 check

Command:

```bash
bash scripts/run_mobile_check.sh
```

Result:

```text
Running 1 test using 1 worker

[1/1] tests/ui/mobile.spec.js:13:1 › mobile upload and report at 390x844
  1 passed (13.4s)

exit_code=0
```

`proof/mobile/mobile-check.json`:

```json
{
  "viewport": "390x844",
  "screens": [
    "proof/mobile/01-upload-390x844.png",
    "proof/mobile/02-report-390x844.png"
  ],
  "upload_horizontal_overflow_px": 0,
  "report_horizontal_overflow_px": 0,
  "claim": "₹75.00"
}
```

No CSS changes were needed; the existing responsive rules held at 390×844.

## 6.2 Final narrated demo

The final demo follows `docs/demo-shot-list.md` and the 9-scene script in `proof/demo/scenes.json`.

Build commands:

```bash
# terminal 1
PYTHONPATH=src python3 -m saboot.webapp --port 8765

# terminal 2
PYTHONPATH=src python3 tools/build_demo_audio_eleven.py
node tools/record_demo.js
bash scripts/build_demo_video.sh
```

Result:

```text
Total timeline: 150.9s (2.52 min)
codec_name=h264
width=1920
height=1080
codec_name=aac
duration=150.880000
size=5639917
```

- Final video: `proof/demo/saboot-demo.mp4` — **2:31**, 1920×1080, H.264/AAC, 5.6 MB.
- Narration: ElevenLabs neural TTS (George, eleven_multilingual_v2, speed 0.8).
- Captions: burned in from `proof/demo/captions.ass`; SRT also saved.
- Thumbnail: `proof/demo/thumbnail.png` — 1200×800.
- Script: `proof/demo/voiceover.txt`; timeline: `proof/demo/timeline.json`.
- Audio: AAC 48kHz mono; mean -16.7 dB, max -1.3 dB; no clipping.
- The video uses the **template appeal path with no API key**.
- Flow shown: upload → ₹75 duplicate claim → source quote → `QD-DED-001` → human approval → appeal → `Verifier PASS` → exported PDF → close.

## 7. How to reproduce from scratch

```bash
cd saboot
PYTHONPATH=src python3 tools/make_fixtures.py   # regenerate the 20 fixtures
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 tools/eval_golden.py
./bin/saboot audit --bundle data/fixtures/golden/G12_multiple/statement
npm install
bash scripts/run_e2e.sh
bash scripts/run_mobile_check.sh

# final demo (server must be running on :8765)
PYTHONPATH=src python3 tools/build_demo_audio_eleven.py
node tools/record_demo.js
bash scripts/build_demo_video.sh
```

To use the UI manually:

```bash
PYTHONPATH=src python3 -m saboot.webapp --port 8765
# open http://127.0.0.1:8765
```

## 8. Known limitations and remaining gaps

- The 20 fixtures are synthetic and hand-authored; the evaluation is a regression baseline, not a claim of real-world accuracy.
- CSV and text-PDF inputs use a canonical QuickDrop layout. Real platform exports will need adapters.
- No OCR/scanned-image support.
- No Hindi output yet.
- No deployment or case tracker; the local app is the artifact. The 2:31 narrated demo is `proof/demo/saboot-demo.mp4`.
- The default demo uses the template appeal path; the optional Gemini provider is implemented behind `DraftProvider` but is not exercised in the video. This is a deliberate reliability/zero-cost choice.
- The UI E2E runs on desktop Chrome (1440×1000). A separate 390×844 mobile check covers upload/report only, not the full approval flow.
- The in-memory `CaseStore` is single-process and resets when the server restarts. That is acceptable for the local demo.
- PDF export is dependency-free but uses a basic text layout; it is not a designed PDF template.

## 9. Proof artifact index

| Path | What it proves |
|---|---|
| `proof/G01_duplicate/` | Duplicate deduction CLI run; command, stdout, JSON, Markdown, PDF |
| `proof/G03_restaurant_delay/` | Restaurant-delay protection CLI run |
| `proof/G12_multiple/` | Four claim types in one CLI audit; ₹217 total |
| `proof/F01_clean/` | Clean statement produces zero claims |
| `proof/F08_boundary_cap/` | Penalty exactly at cap is not over-cap |
| `proof/needs_review/` | Unknown code becomes a review item; strict mode exits 1 |
| `proof/G01_duplicate_pdf/` | Text-PDF ingestion produces the same claim |
| `proof/test_suite.txt` | Full 57-test log |
| `proof/eval_stdout.txt` | Full golden evaluation log |
| `proof/ui/` | Playwright screenshots, video, console/server logs, summary, exported PDF |
| `proof/mobile/` | 390×844 upload/report screenshots, mobile log, zero-overflow JSON |
| `proof/demo/` | Final 2:31 narrated demo, thumbnail, captions, voiceover script, timeline, exported PDF, ffprobe/audio check |
| `proof/video-review.md` | Gemini 3.8 Flash quality gate: 0 critical, 0 major, SUBMISSION-READY |
| `eval/report.md` | Human-readable evaluation report |
| `eval/results.json` | Machine-readable results |
