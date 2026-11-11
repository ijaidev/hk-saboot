#!/usr/bin/env node
/**
 * Record the final UI demo against a running local server.
 *
 * Usage:
 *   PYTHONPATH=src python3 -m saboot.webapp --port 8765 &
 *   node tools/record_demo.js
 */

const { chromium } = require("@playwright/test");
const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const DEMO = path.join(ROOT, "proof", "demo");
const RAW = path.join(DEMO, "raw");
const BASE_URL = process.env.SABOOT_BASE_URL || "http://127.0.0.1:8765";
const PDF_INPUT = path.join(ROOT, "proof", "G01_duplicate", "statement.pdf");
const PDF_OUTPUT = path.join(DEMO, "appeal.pdf");
const PDF_PNG = path.join(DEMO, "appeal-page.png");

function readTimeline() {
  return JSON.parse(fs.readFileSync(path.join(DEMO, "timeline.json"), "utf8"));
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, ms)));
}

async function applyAction(page, scene) {
  switch (scene.action) {
    case "upload":
      await page.setInputFiles("#file-input", PDF_INPUT);
      await page.waitForFunction(() => {
        const el = document.querySelector("#file-meta");
        return el && el.textContent.includes("statement.pdf");
      });
      await wait(700);
      break;
    case "upload_and_audit":
      await page.setInputFiles("#file-input", PDF_INPUT);
      await page.waitForFunction(() => {
        const el = document.querySelector("#file-meta");
        return el && el.textContent.includes("statement.pdf");
      });
      await wait(600);
      await page.click("#audit-button");
      await page.waitForSelector("#report-view", { state: "visible", timeout: 30000 });
      await page.waitForFunction(() => {
        const el = document.querySelector("#claims-list");
        return el && el.textContent.includes("₹75.00");
      });
      await wait(700);
      break;
    case "audit":
      await page.click("#audit-button");
      await page.waitForSelector("#report-view", { state: "visible", timeout: 30000 });
      await page.waitForFunction(() => {
        const el = document.querySelector("#claims-list");
        return el && el.textContent.includes("₹75.00");
      });
      await wait(900);
      break;
    case "scroll_claim":
      await page.evaluate(() => window.scrollBy({ top: 110, behavior: "smooth" }));
      await wait(800);
      break;
    case "evidence":
      await page.locator('[data-testid="evidence-toggle"]').first().click();
      await page.waitForSelector('[data-testid="evidence-details"]', { state: "visible" });
      await page.locator('[data-testid="evidence-details"]').first().scrollIntoViewIfNeeded();
      await wait(800);
      break;
    case "approve":
      await page.locator("#review-check").scrollIntoViewIfNeeded();
      await wait(500);
      await page.check("#review-check");
      await wait(800);
      await page.click("#approve-button");
      await page.waitForFunction(() => {
        const el = document.querySelector("#approval-status");
        return el && el.textContent.includes("Approved");
      });
      await wait(800);
      break;
    case "appeal":
      await page.click("#appeal-button");
      await page.waitForSelector("#appeal-view", { state: "visible", timeout: 30000 });
      await wait(900);
      break;
    case "pdf": {
      const downloadPromise = page.waitForEvent("download");
      await page.click("#download-button");
      const download = await downloadPromise;
      await download.saveAs(PDF_OUTPUT);
      await wait(500);
      execFileSync(
        "pdftoppm",
        ["-png", "-r", "150", "-f", "1", "-singlefile", PDF_OUTPUT, path.join(DEMO, "appeal-page")],
        { stdio: "ignore" }
      );
      const topCrop = path.join(DEMO, "appeal-page-top.png");
      const bottomCrop = path.join(DEMO, "appeal-page-bottom.png");
      execFileSync(
        "ffmpeg",
        ["-y", "-loglevel", "error", "-i", PDF_PNG, "-vf", "crop=iw:ih*0.66:0:0", topCrop],
        { stdio: "ignore" }
      );
      execFileSync(
        "ffmpeg",
        ["-y", "-loglevel", "error", "-i", PDF_PNG, "-vf", "crop=iw:ih*0.52:0:ih*0.48", bottomCrop],
        { stdio: "ignore" }
      );
      const showPdf = async (imagePath, label) => {
        const base64 = fs.readFileSync(imagePath).toString("base64");
        await page.setContent(`
          <html>
            <body style="margin:0;background:#141c1a;height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:ui-sans-serif,system-ui,sans-serif;">
              <div style="color:#8fa6a0;font-size:13px;letter-spacing:0.16em;text-transform:uppercase;margin-bottom:14px;">${label}</div>
              <img src="data:image/png;base64,${base64}" style="max-height:91vh;max-width:94vw;box-shadow:0 24px 70px rgba(0,0,0,0.55);background:#fff;" />
              <div style="color:#7ee0cb;font-size:12px;margin-top:10px;">Saboot · exported PDF · page 1</div>
            </body>
          </html>
        `);
      };
      await showPdf(topCrop, "Exported PDF — appeal");
      await wait(7800);
      await showPdf(bottomCrop, "Exported PDF — evidence appendix");
      await wait(4000);
      break;
    }
    case "close":
      await page.setContent(`
        <html>
          <body style="margin:0;background:#0b1220;height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:Georgia,serif;color:#f6f4ec;">
            <div style="font-size:72px;letter-spacing:0.18em;font-weight:700;">SABOOT</div>
            <div style="width:64px;height:3px;background:#7ee0cb;margin:26px 0 24px;"></div>
            <div style="font-size:34px;color:#f6f4ec;">Proof for every rupee.</div>
            <div style="font-family:ui-sans-serif,system-ui,sans-serif;font-size:16px;color:#9fb0ad;margin-top:26px;line-height:1.7;text-align:center;">
              Request for review · evidence-bound · no auto-send<br/>
              Synthetic demo data · fictional QuickDrop policy
            </div>
          </body>
        </html>
      `);
      await wait(700);
      break;
    default:
      break;
  }
}

(async () => {
  fs.rmSync(RAW, { recursive: true, force: true });
  fs.mkdirSync(RAW, { recursive: true });

  const timeline = readTimeline();
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: RAW, size: { width: 1920, height: 1080 } },
  });
  const page = await context.newPage();
  const video = page.video();

  await page.goto(BASE_URL, { waitUntil: "networkidle" });
  await wait(600);

  for (const scene of timeline.scenes) {
    const started = Date.now();
    console.log(`Recording ${scene.id} (${scene.duration_ms}ms)`);
    await applyAction(page, scene);
    const elapsed = Date.now() - started;
    await wait(scene.duration_ms - elapsed);
  }

  await wait(300);
  await context.close();
  const videoPath = await video.path();
  fs.writeFileSync(path.join(DEMO, "raw_video_path.txt"), `${videoPath}\n`);
  console.log(`Video: ${videoPath}`);
  await browser.close();
})();
