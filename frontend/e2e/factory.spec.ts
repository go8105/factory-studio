import { test, expect } from "@playwright/test";
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", (route) => route.fulfill({ json: { data: { actorKind: "GUEST", workspaceId: 10, generationId: 20, roles: [], csrfToken: "factory-preview", expiresAt: "2026-09-27T00:00:00+09:00" } } }));
  await page.goto("/factory");
  await expect(page.locator("canvas")).toBeVisible();
  await expect(page.getByText("2F 사무실 · 직원 2명", { exact: true })).toBeAttached();
});
test("공장 장면은 브라우저 오류 없이 렌더링된다", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.reload();
  await expect(page.getByText("2F 사무실 · 직원 2명", { exact: true })).toBeAttached();
  expect(errors).toEqual([]);
});
test("앱 런처 바로 다음 메뉴로 3D 공장에 진입한다", async ({ page }) => {
  const links = page.getByRole("navigation", { name: "주 메뉴" }).getByRole("link");
  await expect(links.nth(1)).toHaveText("3D 공장");
});
test("걷기 입력은 3인칭 화면을 이동시킨다", async ({ page }) => {
  await page.getByRole("button", { name: "시연 일시정지" }).click();
  await page.getByRole("button", { name: "걸어서 둘러보기" }).click();
  // Let the follow camera settle so only movement changes the next capture.
  await page.waitForTimeout(1600);
  const before = await page.locator("canvas").screenshot();
  await page.getByRole("region", { name: "3D 공장 탐색" }).focus();
  await page.keyboard.down("ArrowRight");
  await page.waitForTimeout(600);
  await page.keyboard.up("ArrowRight");
  await page.waitForTimeout(500);
  expect((await page.locator("canvas").screenshot()).equals(before)).toBe(false);
});
test("2층 사무실을 선택하면 해당 시점으로 이동한다", async ({ page }) => {
  await page.getByRole("button", { name: "2층 사무실", exact: true }).click();
  await expect(page.getByRole("button", { name: "2층 사무실", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({ path: "../work/factory-office-check.png", fullPage: true });
});
test("비전검사 공정 설명을 선택할 수 있다", async ({ page }) => {
  await page.getByRole("button", { name: /02 비전검사/ }).click();
  await expect(page.getByText(/카메라와 조명으로 제품의 외관을 검사/)).toBeVisible();
});
test("360px에서 가로 스크롤 없이 공장 화면을 표시한다", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 900 });
  await expect(page.getByRole("button", { name: "걸어서 둘러보기" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(360);
  await page.screenshot({ path: "../work/factory-mobile-check.png", fullPage: true });
});
test("그래픽 연결 손실은 재시도 안내로 대체한다", async ({ page }) => {
  await page.locator("canvas").evaluate((canvas) => canvas.dispatchEvent(new Event("webglcontextlost", { cancelable: true })));
  await expect(page.getByRole("button", { name: "3D 다시 열기" })).toBeVisible();
});
