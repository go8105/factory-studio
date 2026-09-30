import { defineConfig, devices } from "@playwright/test";
// Real local API :8000, isolated seeded test DB. No shared/production data.
export default defineConfig({
  testDir: "./e2e",
  testMatch: ["wms.spec.ts", "wms-extension.spec.ts"],
  workers: 1,
  timeout: 45000,
  reporter: "list",
  outputDir: "../work/fs026/browser-results",
  use: { baseURL: "http://localhost:5173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
