import { test, expect, type Page } from "@playwright/test";
// UI-02 공통 레이아웃 규칙: 목록 채움, 표 머리글 고정, 대시보드 격자, 등록 패널.
// 새 화면을 패턴으로 옮길 때 같은 검사를 그 경로에 추가한다(docs/ui/공통UI규약_UI-02.md).
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});
const docHeight = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollHeight);
// 대시보드 하단 카드가 줄마다 2개(또는 1열)인지: 혼자 남은 줄이 없어야 한다.
async function rowsOfCards(page: Page) {
  return page.evaluate(() => {
    const tops = [...document.querySelectorAll(".dashboard-grid > *")].map(
      (el) => Math.round(el.getBoundingClientRect().top),
    );
    const rows = new Map<number, number>();
    for (const t of tops) rows.set(t, (rows.get(t) ?? 0) + 1);
    return [...rows.values()];
  });
}

for (const [w, h] of [
  [1440, 900],
  [1366, 768],
]) {
  test(`${w}×${h} 조회 목록은 한 화면이고 표만 스크롤한다`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: w, height: h });
    await page.goto("/fems/readings");
    await expect(page.getByRole("cell").first()).toBeVisible();
    expect(await docHeight(page)).toBeLessThanOrEqual(h);
    const gap = await page.evaluate(() => {
      const box = document.querySelector(".table-scroll")!;
      box.scrollTop = 400;
      const th = document.querySelector("thead th")!.getBoundingClientRect();
      return Math.abs(th.top - box.getBoundingClientRect().top);
    });
    expect(gap).toBeLessThanOrEqual(2);
    await expect(
      page.getByRole("navigation", { name: /페이지/ }),
    ).toBeInViewport();
    await expect(page.getByRole("button", { name: "조회" })).toBeInViewport();
  });
}

for (const route of ["/fems/dashboard", "/mes/dashboard", "/erp/dashboard"]) {
  for (const w of [1440, 1600, 1920]) {
    test(`${w} ${route} 하단 카드에 고립 카드가 없다`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: 900 });
      await page.goto(route);
      await expect(page.locator(".dashboard-grid")).toBeVisible();
      expect(await rowsOfCards(page)).toEqual([2, 2]);
      const kpiTops = await page
        .locator(".kpi-grid > *")
        .evaluateAll(
          (els) =>
            new Set(els.map((e) => Math.round(e.getBoundingClientRect().top)))
              .size,
        );
      expect(kpiTops).toBe(1);
    });
  }
}

for (const route of ["/mes/dashboard", "/erp/dashboard"]) {
  test(`${route} 조회 월이 PageTitle actions 안에 있고 별도 필터바가 없다`, async ({
    page,
  }) => {
    await page.goto(route);
    await expect(
      page.locator(".page-actions").getByLabel("조회 월"),
    ).toBeVisible();
    await expect(page.locator(".filter-bar")).toHaveCount(0);
  });
}

for (const route of [
  "/mes/receipts",
  "/erp/sales-records",
  "/erp/journal-preview",
]) {
  test(`${route} 조회 목록은 .page-fill 루트를 갖는다`, async ({ page }) => {
    await page.goto(route);
    await expect(page.locator(".page-fill")).toBeVisible();
  });
}

for (const route of [
  "/fems/allocations",
  "/fems/emissions",
  "/fems/intensity",
  "/fems/targets",
  "/fems/billing",
  "/erp/receivables",
]) {
  test(`${route} 보고서형 조회는 .page-fill을 쓰지 않는다`, async ({
    page,
  }) => {
    await page.goto(route);
    await expect(page.locator(".solution-content > .page-fill")).toHaveCount(0);
  });
}

test("1440 생산량 패널은 겹쳐 열리고 Esc로 닫혀 버튼으로 돌아간다", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/fems/production");
  const opener = page.getByRole("button", { name: "생산량 등록" });
  await opener.click();
  const panel = page.getByRole("dialog", { name: "생산량 등록 (초안)" });
  await expect(panel).toHaveAttribute("aria-modal", "true");
  await expect(page.getByLabel("설비", { exact: true })).toBeFocused();
  await expect(
    panel.getByRole("button", { name: "초안 등록" }),
  ).toBeInViewport();
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  await expect(opener).toBeFocused();
});

test("1600 생산량 패널은 목록 옆에 붙고 문서가 스크롤되지 않는다", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.goto("/fems/production");
  await page.getByRole("button", { name: "생산량 등록" }).click();
  const panel = page.getByRole("dialog");
  await expect(panel).not.toHaveAttribute("aria-modal", "true");
  const table = (await page.locator(".table-scroll").boundingBox())!;
  const box = (await panel.boundingBox())!;
  expect(table.x + table.width).toBeLessThanOrEqual(box.x);
  expect(await docHeight(page)).toBeLessThanOrEqual(900);
});

test("저장하지 않은 변경은 닫기 전에 확인한다", async ({ page }) => {
  await page.goto("/fems/production");
  await page.getByRole("button", { name: "생산량 등록" }).click();
  await page.getByLabel("품목 코드").fill("fg-1");
  await page.getByRole("button", { name: "취소" }).click();
  await expect(page.getByText("저장하지 않은 변경이 있습니다.")).toBeVisible();
  await page.getByRole("button", { name: "계속 편집" }).click();
  await expect(page.getByLabel("품목 코드")).toHaveValue("FG-1");
});

test("390px 생산량 패널은 전체 화면이고 저장 버튼이 보인다", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/fems/production");
  await page.getByRole("button", { name: "생산량 등록" }).click();
  const box = (await page.getByRole("dialog").boundingBox())!;
  expect(box.width).toBe(390);
  await expect(
    page.getByRole("button", { name: "초안 등록" }),
  ).toBeInViewport();
});
