// Read-only public smoke check. Run from repository root with Node 24.
import { chromium, expect } from "../../../../frontend/node_modules/@playwright/test/index.mjs";
import { mkdir } from "node:fs/promises";
const base = process.env.FS_ABOUT_URL ?? "https://eip.hugh-d.com";
const output = process.env.FS_ABOUT_OUTPUT ?? "work/about-03-public";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  const apiRequests = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url());
  });
  const response = await page.goto(`${base}/about`);
  expect(response.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "황경호", exact: true })).toBeVisible();
  expect(await page.locator(".about-main").evaluate((el) => el.getBoundingClientRect().width)).toBe(880);
  await expect(page.getByText("4년+", { exact: true })).toBeVisible();
  await page.screenshot({ path: `${output}/desktop.png`, fullPage: true });
  await page.getByRole("button", { name: "자세히 보기 · 실시간 이상 감지 알람 엔진", exact: true }).click();
  await expect(page.getByText("asyncio 알람 엔진 분리, Redis TTL 중복 억제", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "접기 · 실시간 이상 감지 알람 엔진", exact: true }).click();
  await page.getByRole("button", { name: "MES 7", exact: true }).click();
  await expect(page.getByRole("heading", { name: "육가공 MES", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "개인 2", exact: true }).click();
  await page.getByRole("button", { name: "자세히 보기 · 이지스(Aegis) AI 비서", exact: true }).click();
  await expect(page.getByText("시연 요청 시", { exact: true })).toBeVisible();
  await page.getByRole("navigation", { name: "섹션 목차" }).getByRole("link", { name: "기술 스택", exact: true }).click();
  await expect(page.locator('.about-nav [aria-current="location"]')).toHaveText("기술 스택");
  await expect(page.getByRole("heading", { name: "기술 노트", exact: true })).toHaveCount(0);
  expect(await page.locator("body").innerText()).not.toContain("010-");
  expect(apiRequests).toEqual([]);
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto(`${base}/about`);
  await expect(page.locator(".about-nav")).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  await page.screenshot({ path: `${output}/mobile.png`, fullPage: true });
  await page.goto(base);
  await expect(page.getByRole("button", { name: /가입 없이 둘러보기/ })).toBeVisible();
  expect(errors).toEqual([]);
  console.log("PASS: public about desktop/mobile, tabs, expand/collapse, demo notice, anchors, privacy, no about API dependency, existing entry");
} finally {
  await browser.close();
}
