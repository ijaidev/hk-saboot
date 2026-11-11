const { test, expect } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "../..");
const PROOF = path.join(ROOT, "proof", "mobile");
const PDF_INPUT = path.join(ROOT, "proof", "G01_duplicate", "statement.pdf");

fs.mkdirSync(PROOF, { recursive: true });

test.use({ viewport: { width: 390, height: 844 }, video: "off" });

test("mobile upload and report at 390x844", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#upload-view")).toBeVisible();
  await expect(page.locator("#dropzone")).toBeVisible();
  await page.screenshot({
    path: path.join(PROOF, "01-upload-390x844.png"),
    fullPage: true,
  });

  const uploadOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth
  );
  expect(uploadOverflow).toBeLessThanOrEqual(1);

  await page.setInputFiles("#file-input", PDF_INPUT);
  await page.click("#audit-button");
  await expect(page.locator("#report-view")).toBeVisible();
  await expect(page.locator("#claims-list")).toContainText("₹75.00");
  await page.screenshot({
    path: path.join(PROOF, "02-report-390x844.png"),
    fullPage: true,
  });

  const reportOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth
  );
  expect(reportOverflow).toBeLessThanOrEqual(1);

  fs.writeFileSync(
    path.join(PROOF, "mobile-check.json"),
    JSON.stringify(
      {
        viewport: "390x844",
        screens: ["proof/mobile/01-upload-390x844.png", "proof/mobile/02-report-390x844.png"],
        upload_horizontal_overflow_px: uploadOverflow,
        report_horizontal_overflow_px: reportOverflow,
        claim: "₹75.00",
      },
      null,
      2
    ) + "\n"
  );
});
