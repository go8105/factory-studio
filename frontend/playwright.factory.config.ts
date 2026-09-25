import { defineConfig, devices } from "@playwright/test";
// Standalone frontend validation: mocked API, no backend or shared smoke DB.
export default defineConfig({
  testDir: "./e2e",
  testMatch: "factory.spec.ts",
  workers: 1,
  reporter: "list",
  outputDir: "../work/factory-browser",
  use: { baseURL: "http://127.0.0.1:5186", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5186",
    url: "http://127.0.0.1:5186",
    reuseExistingServer: false,
  },
});
