# Demo shot list — 2:30

**Use:** final demo video (not the Playwright proof video). Record the local UI at 1920×1080, Chrome, clean profile, 100% zoom. Preload the G01 PDF. Keep the ₹75 number on screen.

**Recorded version:** `proof/demo/saboot-demo.mp4` — **2:31**, TTS narration + burned-in captions.

| Time | Shot | On screen | Voiceover |
|---|---|---|---|
| 0:00–0:10 | Hook | Payout summary: `212 deliveries · ₹17,160 paid · ₹18,400 expected`; lower-third “Illustrative case; synthetic data.” | “Ravi delivered 212 orders last month. The app paid him ₹1,240 less than his own records.” |
| 0:10–0:22 | Problem | Wall of deduction codes; support-chat canned reply; stat “12M gig workers in India.” | “Gig pay is calculated by algorithms. Deductions are cryptic. Appeals are a black box.” |
| 0:22–0:35 | Upload | Saboot landing; choose `proof/G01_duplicate/statement.pdf`; click Audit statement. | “Saboot is the audit layer. Upload the payout statement.” |
| 0:35–0:50 | Processing → report | Processing steps; report appears: `₹75.00`, risk 83, verifier PASS. | “It reads every order, every deduction, and the platform’s own policy.” |
| 0:50–1:10 | Claim | Duplicate deduction card; source quote; `QD-DED-001`; confidence 1.00. | “Two identical LATE charges on one order. The policy allows one. That’s ₹75.” |
| 1:10–1:25 | Evidence | Open “View evidence”; arithmetic, source rows, verifier PASS. | “Every rupee is traceable to an order, a deduction, a timestamp, and a clause.” |
| 1:25–1:40 | Human approval | Check “I reviewed…”; click Approve selected claims; Approved chip. | “A human reviews the evidence. Nothing is sent automatically.” |
| 1:40–2:05 | Appeal | Generate appeal; show subject/body; Verifier PASS; citation card. | “Saboot drafts the request for review, with the evidence and the citation.” |
| 2:05–2:20 | PDF | Click Download PDF; show the PDF opening with appeal + evidence appendix. | “Export the appeal and the evidence pack as a PDF.” |
| 2:20–2:30 | Close | End card: “Saboot — Proof for every rupee.” | “₹75 is not a rounding error. It’s a week of rent. Saboot makes algorithmic pay contestable.” |

## Capture notes

- Use the template draft (no API key). Do not show a provider setup screen.
- Keep the toast visible only if it helps; otherwise wait 4 seconds before the screenshot.
- Show the ₹75 number at least three times: report, claim, appeal.
- Do not claim a platform response or a recovery outcome. Say “request for review.”
- Add captions; if using TTS, disclose “AI-generated voiceover” in the video description.
- Save the final video as `proof/demo/saboot-demo.mp4` after supervisor approval.
