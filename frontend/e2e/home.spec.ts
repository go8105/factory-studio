import { test, expect } from "@playwright/test";
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", (route) =>
    route.fulfill({
      json: {
        data: route.request().url().endsWith("/sessions/current")
          ? {
              actorKind: "GUEST",
              workspaceId: 10,
              generationId: 20,
              roles: ["GUEST"],
              csrfToken: "preview",
              expiresAt: "2026-09-28T00:00:00+09:00",
            }
          : ["mes", "erp", "fems", "qms", "wms"].map((moduleKey) => ({
              moduleKey,
              enabled: true,
              updatedAt: null,
            })),
      },
    }),
  );
  await page.goto("/home");
  await expect(
    page.getByRole("link", { name: "MES 생산관리", exact: true }),
  ).toBeVisible();
});
test("홈 기본 화면은 아이콘·이름·분류만 표시한다", async ({ page }) => {
  await expect(
    page.getByRole("link", { name: "QMS 품질관리", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".launcher-detail:visible")).toHaveCount(0);
  await page.screenshot({ path: "../work/home-desktop.png", fullPage: true });
});
test("마우스 호버로 상태와 설명을 연다", async ({ page }) => {
  await page.getByRole("link", { name: "MES 생산관리", exact: true }).hover();
  await expect(page.locator("#launcher-description-mes")).toBeVisible();
  await page.screenshot({ path: "../work/home-hover.png", fullPage: true });
});
test("키보드 포커스로 상태와 설명을 연다", async ({ page }) => {
  await page.getByRole("link", { name: "ERP 경영관리", exact: true }).focus();
  await expect(page.locator("#launcher-description-erp")).toBeVisible();
});
test("Escape는 포커스를 유지하며 안내를 닫는다", async ({ page }) => {
  const link = page.getByRole("link", { name: "ERP 경영관리", exact: true });
  await link.focus();
  await page.keyboard.press("Escape");
  await expect(page.locator("#launcher-description-erp")).toBeHidden();
});
test("포인터가 안내로 이동해도 설명을 읽을 수 있다", async ({ page }) => {
  await page.getByRole("link", { name: "MES 생산관리", exact: true }).hover();
  await page.locator("#launcher-description-mes").hover();
  await expect(page.locator("#launcher-description-mes")).toBeVisible();
});
test("흰색 헤더와 로고를 표시한다", async ({ page }) => {
  await expect(page.locator(".site-header")).toHaveCSS(
    "background-color",
    "rgb(255, 255, 255)",
  );
  await expect(page.locator(".brand-mark")).toBeVisible();
});
test("360px에서 안내를 열어도 가로 스크롤이 없다", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 900 });
  for (const key of ["FEMS", "QMS"]) {
    await page.getByRole("button", { name: `${key} 상세 안내` }).focus();
    await page.keyboard.press("Enter");
    await expect(
      page.locator(`#launcher-description-${key.toLowerCase()}`),
    ).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBe(360);
  }
  await page.screenshot({ path: "../work/home-mobile.png", fullPage: true });
});
test("모바일 터치로 안내를 열고 닫을 수 있다", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  const touch = await context.newPage();
  await touch.route("**/api/**", (route) =>
    route.fulfill({
      json: {
        data: route.request().url().endsWith("/sessions/current")
          ? {
              actorKind: "GUEST",
              workspaceId: 10,
              generationId: 20,
              roles: [],
              csrfToken: "preview",
            }
          : ["mes", "erp", "fems", "qms", "wms"].map((moduleKey) => ({
              moduleKey,
              enabled: true,
            })),
      },
    }),
  );
  await touch.goto("/home");
  await touch.getByRole("button", { name: "MES 상세 안내" }).tap();
  await expect(touch.locator("#launcher-description-mes")).toBeVisible();
  await touch.getByRole("button", { name: "MES 상세 안내" }).tap();
  await expect(touch.locator("#launcher-description-mes")).toBeHidden();
  await context.close();
});
