const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests/ui",
  fullyParallel: false,
  workers: 1,
  timeout: 120000,
  expect: { timeout: 15000 },
  reporter: [["line"]],
  use: {
    baseURL: process.env.SABOOT_BASE_URL || "http://127.0.0.1:8765",
    headless: true,
    channel: "chrome",
    viewport: { width: 1440, height: 1000 },
    video: "on",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  outputDir: "test-results",
});
