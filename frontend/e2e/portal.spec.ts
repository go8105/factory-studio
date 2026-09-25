import { test, expect } from "@playwright/test";
// 실제 API만 사용한다. tools/run_portal_smoke.py가 전용 테스트 DB/서버를 관리한다.
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});
test("게스트 진입 → 시드 공간 앱 런처", async ({ page }) => {
  await expect(page.getByText(/공간 \d+ · 데이터 세대 \d+/)).toBeVisible();
  await page.screenshot({
    path: "../work/fs017c/launcher-desktop.png",
    fullPage: true,
  });
});
test("런처에서 전체 흐름으로 이동", async ({ page }) => {
  await page.getByRole("link", { name: "전체 흐름", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "전체 업무 흐름", exact: true }),
  ).toBeVisible();
});
test("흐름 노드에서 QMS 설명 카드로 이동", async ({ page }) => {
  await page.goto("/flow");
  await page.getByRole("link", { name: /08 \/ QMS/ }).click();
  await expect(
    page.getByRole("heading", { name: "품질관리 (QMS)" }),
  ).toBeVisible();
});
test("도움말 허브에서 공통 도움말로 이동", async ({ page }) => {
  await page.getByRole("link", { name: "도움말", exact: true }).click();
  await page.getByRole("link", { name: /공통 이용 안내 오류/ }).click();
  await expect(
    page.getByRole("heading", { name: "공통 이용 안내" }),
  ).toBeVisible();
});
test("런처에서 내 공간으로 이동", async ({ page }) => {
  await page.getByRole("link", { name: "내 공간", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "내 공간", exact: true }),
  ).toBeVisible();
});
test("새로고침 후 토글 변경", async ({ page }) => {
  await page.goto("/workspace");
  await page.reload();
  await page.getByRole("switch", { name: "MES 사용" }).click();
  await expect(page.getByRole("switch", { name: "MES 사용" })).toHaveAttribute(
    "aria-checked",
    "false",
  );
});
test("새로고침 후 세대 초기화", async ({ page }) => {
  await page.goto("/workspace");
  await page.reload();
  const before = await page.getByText(/활성 데이터 세대/).textContent();
  await page
    .getByRole("button", { name: "예시 데이터 초기화", exact: true })
    .click();
  await page.getByRole("button", { name: "초기화 확인" }).click();
  await expect(page.getByText(/활성 데이터 세대/)).not.toHaveText(before!);
});
test("초기화 후 앱 사용 설정 유지", async ({ page }) => {
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
    page.getByRole("button", { name: "예시 데이터 초기화", exact: true }),
  ).toBeEnabled();
  await expect(page.getByRole("switch", { name: "MES 사용" })).toHaveAttribute(
    "aria-checked",
    "false",
  );
});
test("게스트 운영 기록 직접 접근은 404", async ({ page }) => {
  await page.goto("/records");
  await expect(page.getByText("404 · NOT_FOUND")).toBeVisible();
});
for (const [route, title] of [
  ["home", "제조 현장의 세 시스템"],
  ["flow", "전체 업무 흐름"],
  ["cards/qms", "설명 카드"],
  ["help", "도움말"],
  ["workspace", "내 공간"],
  ["records", "페이지를 찾을 수 없습니다"],
  ["fems/dashboard", "에너지 개요"],
  ["fems/energy-sources", "에너지원"],
  ["fems/readings", "계측 조회"],
  ["fems/allocations", "설비별 배분"],
  ["fems/emissions", "배출량 현황"],
  ["fems/production", "생산량 등록"],
  ["fems/intensity", "원단위 분석"],
  ["fems/targets", "목표 대비 실적"],
  ["fems/billing", "요금 산정"],
  ["fems/sites", "사업장·공간"],
  ["fems/meters", "계측기·채널"],
  ["fems/energy-factors", "환산·배출계수"],
  ["mes/production-plans", "생산계획"],
  ["mes/work-orders", "작업지시"],
  ["mes/lots", "LOT 현황"],
  ["mes/executions", "공정 실행"],
  ["mes/sites", "사업장·공간"],
  ["mes/equipments", "설비"],
  ["mes/items", "품목"],
  ["mes/processes", "공정"],
  ["mes/routes", "공정 경로"],
  ["mes/boms", "BOM"],
]) {
  test(`360px ${route} 가로 스크롤 없음`, async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/" + route);
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(360);
    await page.screenshot({
      path: `../work/fs017c/${route.replaceAll("/", "-")}-mobile.png`,
      fullPage: true,
    });
  });
}

test("360px 진입 화면 가로 스크롤 없음", async ({ page }) => {
  await page.context().clearCookies();
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: /가입 없이 둘러보기/ }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(360);
});
