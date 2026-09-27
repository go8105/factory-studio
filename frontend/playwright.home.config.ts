import { defineConfig, devices } from "@playwright/test";
// Frontend-only home validation: mocked API, no shared ports or database.
export default defineConfig({
  testDir: "./e2e",
  testMatch: "home.spec.ts",
  workers: 1,
  reporter: "list",
  outputDir: "../work/home-browser",
  use: { baseURL: "http://127.0.0.1:5187", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5187",
    url: "http://127.0.0.1:5187",
    reuseExistingServer: false,
  },
});
