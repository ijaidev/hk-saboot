const { test, expect } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "../..");
const PROOF = path.join(ROOT, "proof", "ui");
const PDF_INPUT = path.join(ROOT, "proof", "G01_duplicate", "statement.pdf");
const consoleLines = [];
const pageErrors = [];
const consoleErrors = [];

fs.mkdirSync(PROOF, { recursive: true });

test.beforeEach(async ({ page }) => {
  page.on("console", (message) => {
    const line = `[${message.type()}] ${message.text()}`;
    consoleLines.push(line);
    if (message.type() === "error") consoleErrors.push(line);
  });
  page.on("pageerror", (error) => {
    const line = `[pageerror] ${error.message}`;
    consoleLines.push(line);
    pageErrors.push(line);
  });
});

test.afterAll(() => {
  fs.writeFileSync(path.join(PROOF, "console.log"), consoleLines.join("\n") + "\n");
});

test("upload PDF -> ₹75 claim -> evidence -> approve -> appeal -> verifier -> PDF", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#upload-view")).toBeVisible();
  await page.screenshot({ path: path.join(PROOF, "01-upload.png"), fullPage: true });

  await page.setInputFiles("#file-input", PDF_INPUT);
  await expect(page.locator("#file-meta")).toContainText("statement.pdf");
  await page.screenshot({ path: path.join(PROOF, "02-file-selected.png"), fullPage: true });

  await page.click("#audit-button");
  await expect(page.locator("#report-view")).toBeVisible();
  await expect(page.locator("#claims-list")).toContainText("Duplicate deduction");
  await expect(page.locator("#claims-list")).toContainText("₹75.00");
  await expect(page.locator("#summary-disputed")).toContainText("₹75.00");
  await expect(page.locator("#summary-verifier")).toContainText("PASS");
  await page.screenshot({ path: path.join(PROOF, "03-report.png"), fullPage: true });

  await page.locator('[data-testid="evidence-toggle"]').first().click();
  await expect(page.locator('[data-testid="evidence-details"]').first()).toBeVisible();
  await expect(page.locator('[data-testid="evidence-quote"]').first()).toContainText("2 × LATE");
  await expect(page.locator('[data-testid="policy-citation"]').first()).toContainText("QD-DED-001");
  await expect(page.locator('[data-testid="policy-citation"]').first()).toContainText("quickdrop.example");
  await page.screenshot({ path: path.join(PROOF, "04-evidence.png"), fullPage: true });

  await page.check("#review-check");
  await expect(page.locator("#approve-button")).toBeEnabled();
  await page.click("#approve-button");
  await expect(page.locator("#approval-status")).toContainText("Approved 1 claim");
  await expect(page.locator("#appeal-button")).toBeEnabled();
  await page.screenshot({ path: path.join(PROOF, "05-approved.png"), fullPage: true });

  await page.click("#appeal-button");
  await expect(page.locator("#appeal-view")).toBeVisible();
  await expect(page.locator("#appeal-verifier")).toContainText("Verifier PASS");
  await expect(page.locator("#appeal-body")).toContainText("request for review");
  await expect(page.locator("#appeal-body")).toContainText("QD-DED-001");
  await expect(page.locator("#appeal-citations")).toContainText("QD-DED-001");
  await page.screenshot({ path: path.join(PROOF, "06-appeal.png"), fullPage: true });

  const downloadPromise = page.waitForEvent("download");
  await page.click("#download-button");
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  await download.saveAs(path.join(PROOF, "appeal.pdf"));

  expect(pageErrors, pageErrors.join("\n")).toEqual([]);
  expect(consoleErrors, consoleErrors.join("\n")).toEqual([]);

  fs.writeFileSync(
    path.join(PROOF, "e2e-summary.json"),
    JSON.stringify(
      {
        flow: "upload PDF -> report -> evidence -> approve -> appeal -> PDF",
        input: "proof/G01_duplicate/statement.pdf",
        claim: "duplicate_deduction ₹75.00",
        source_quote: "Order QD-1001: 2 × LATE deductions at 19:10, 19:14, each ₹75.00.",
        policy_citation: "QD-DED-001",
        verifier: "PASS",
        pdf: "proof/ui/appeal.pdf",
        screenshots: [
          "proof/ui/01-upload.png",
          "proof/ui/02-file-selected.png",
          "proof/ui/03-report.png",
          "proof/ui/04-evidence.png",
          "proof/ui/05-approved.png",
          "proof/ui/06-appeal.png",
        ],
        console_log: "proof/ui/console.log",
        page_errors: pageErrors.length,
        console_errors: consoleErrors.length,
      },
      null,
      2
    ) + "\n"
  );
});
