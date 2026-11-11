# Video review — Saboot final demo

**Reviewer:** Antigravity / `gemini-3.8-flash`, `thinking_level: high` (native video + audio review)
**File reviewed:** `proof/demo/saboot-demo.mp4`
**Date:** 2026-11-10

---

## Round 1 — original cut (2:55)

**Verdict:** NOT SUBMISSION-READY — 0 critical, 3 major.

**Major issues:**

1. **Robotic eSpeak NG narration** (00:00–02:55). The formant synthesizer sounded mechanical, and spelled-out acronyms (`P D F`, `A P I`, `Q D D E D`) made it worse.
2. **Caption drift / orphan words** (00:00–02:40). Captions were timed by character count rather than speech; single words like `key.`, `status.`, and `apart.` flashed for under a second.
3. **Unreadable PDF body text** (02:21–02:40). The full letter page was scaled to 86vh, making 10pt body text ~7–8px tall.

**Minor issues:** static screens / sluggish inter-scene pacing; ~1.4s dead-air padding; phonetic acronym artifacts.

**Specific focus:** all six items PASS (₹75 claim, source quote, `QD-DED-001`, human approval, appeal, verifier PASS), but production quality was not submission-ready.

---

## Fixes applied

- Replaced eSpeak NG with **ElevenLabs neural TTS** (`George`, `eleven_multilingual_v2`, speed 0.8).
- Generated **forced-alignment word timings** from ElevenLabs; rebuilt captions from actual word start/end times.
- Enforced a minimum of 3 words and 1.2s per caption cue; no single-word flash cards.
- Replaced the full-page PDF shot with **two zoomed crops**: the appeal page and the evidence appendix.
- Moved the audit click into the upload scene so the report appears earlier; removed the appeal scroll that hid the title and verifier badge.
- Kept the template appeal path with **no API key**.

---

## Round 2 — revision 2 (2:31)

**Verdict:** **SUBMISSION-READY — 0 critical, 0 major.**

### Scores

| Criterion | Score /10 | Notes |
|---|---:|---|
| Hook and clarity | 9 | Immediate, authoritative opening; synthetic/fictional disclosure upfront. |
| Problem / solution | 9 | Opaque deductions → reconciliation → policy citation → actionable request. |
| Demo completeness | 10 | Upload → audit → claim → evidence → approval → appeal → PDF → clean close. |
| Technical credibility | 10 | Deterministic local engine, zero-key template path, arithmetic trace, source row IDs, verifier PASS. |
| Visual legibility | 9.5 | 1080p, high contrast, sharp numbers/IDs/citations. |
| Audio quality | 9.5 | Natural neural voice; mean −16.7 dB, peak −1.3 dB; no clipping/noise. |
| Captions | 10 | Forced-alignment timing; high-contrast; no drift or orphan words. |
| Pacing | 9.5 | 2:30.88; ~1.2s scene padding; no sluggish static stretch. |
| Submission fit | 10 | Under 3:00; synthetic data; no auto-send; request-for-review framing. |

### Critical issues

None.

### Major issues

None.

### Minor issues

1. **00:20–00:21 — brief blank transition** when the audit button is clicked and the report mounts (~0.6s). Does not interrupt comprehension.
2. **02:08–02:17 — PDF preview shows page 1 only.** The narration mentions the human approval record; that block is on page 2 of the PDF. The human approval is already explicitly demonstrated in the UI at 01:32–01:43. Does not disqualify the video.

### Specific focus checklist

| Focus item | Status | Timestamp(s) | Verification |
|---|---|---|---|
| ₹75 duplicate claim | PASS | 00:22, 00:45, 01:05, 01:44, 02:05 | Large stat card, claim card, appeal, PDF total. |
| Source quote | PASS | 00:57–01:17, 01:48, 02:05 | `Order QD-1001: 2 × LATE deductions at 19:10, 19:14, each ₹75.00.` |
| Policy citation `QD-DED-001` | PASS | 01:07, 01:23, 01:46, 02:05 | Clause title, URL, effective window. |
| Human approval | PASS | 01:32–01:43 | Checkbox, approve click, “Approved 1 claim. Nothing has been sent.” toast, Approved chip. |
| Appeal draft | PASS | 01:44–02:00 | Full request for review; template draft, no API key. |
| Verifier PASS | PASS | 00:22, 00:45, 01:22, 01:48, 02:03 | Report, evidence drawer, appeal badge, PDF header. |

### Audio, captions, pacing

- **Audio:** AAC 48kHz mono; mean −16.7 dB, max −1.3 dB; no clipping. Natural ElevenLabs voice; no robotic artifacts.
- **Captions:** burned in from forced word alignment; no drift; no sub-second single-word cues.
- **Pacing/duration:** 150.88s (2:30.88), comfortably under 3:00. Clean end card.
- **Claims vs. screen:** every narration claim is visually supported; no unsupported recovery/outcome claim.

### Final recommendation

**Proceed to submit.** The video passed the quality gate with **zero critical and zero major issues**.

---

## Final file status

```text
File: proof/demo/saboot-demo.mp4
Duration: 150.88s (2:30.88)
Video: H.264, 1920×1080
Audio: AAC, 48kHz, mono, mean −16.7 dB, max −1.3 dB
Size: ~5.6 MB
Captions: burned in (forced alignment)
Template appeal path: no API key
```
