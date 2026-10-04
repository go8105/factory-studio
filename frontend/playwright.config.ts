import { defineConfig, devices } from "@playwright/test";
const baseURL = `http://localhost:${process.env.FS_SMOKE_WEB_PORT ?? 5173}`;
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  outputDir: "../work/fs017/playwright-results",
  use: { baseURL, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    url: baseURL,
    reuseExistingServer: false,
    timeout: 30000,
  },
});
