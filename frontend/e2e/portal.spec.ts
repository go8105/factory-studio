import { test, expect } from "@playwright/test";
// 실제 FS-016 API와 *_test DB를 사용한다. 네트워크 응답을 모킹하지 않는다.
test("게스트 진입 → 시드 공간 앱 런처", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
  await expect(page.getByText(/공간 \d+ · 데이터 세대 \d+/)).toBeVisible();
  await expect(page.getByRole("link", { name: /MES 생산관리/ })).toBeVisible();
  await page.screenshot({
    path: "../work/fs017/launcher-desktop.png",
    fullPage: true,
  });
});
test("게스트의 포털 탐색", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
  await page.getByRole("link", { name: "전체 흐름", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "전체 업무 흐름", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: /08 \/ QMS/ }).click();
  await expect(
    page.getByRole("heading", { name: "품질관리 (QMS)" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "도움말", exact: true }).click();
  await page.getByRole("link", { name: /공통 이용 안내 오류/ }).click();
  await expect(
    page.getByRole("heading", { name: "공통 이용 안내" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "내 공간", exact: true }).click();
  await expect(page.getByRole("switch", { name: "MES 사용" })).toHaveAttribute(
    "aria-checked",
    "true",
  );
});
test("새로고침 후 모듈 변경과 초기화", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
  await page.goto("/workspace");
  await page.getByRole("switch", { name: "MES 사용" }).click();
  await expect(page.getByRole("switch", { name: "MES 사용" })).toHaveAttribute(
    "aria-checked",
    "false",
  );
  await page
    .getByRole("button", { name: "예시 데이터 초기화", exact: true })
    .click();
  await page.getByRole("button", { name: "초기화 확인" }).click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "새 예시 데이터 세대로 초기화했습니다." }),
  ).toBeVisible();
  await expect(page.getByRole("switch", { name: "MES 사용" })).toHaveAttribute(
    "aria-checked",
    "false",
  );
});
test("게스트 운영 기록 접근은 404 표시", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
  await page.goto("/records");
  await expect(page.getByText("404 · NOT_FOUND")).toBeVisible();
});
test("360px 화면에서 런처 가로 넘침 없음", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
  await expect(
    page.getByRole("link", { name: /FEMS 에너지관리/ }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(360);
  await page.screenshot({
    path: "../work/fs017/launcher-mobile.png",
    fullPage: true,
  });
});
