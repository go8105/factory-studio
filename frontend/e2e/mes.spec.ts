import { expect, test } from "@playwright/test";

// MES 기준정보(FS-020a). 테스트마다 새 게스트 공간을 쓴다.
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});

test("포털에서 MES로 들어가면 생산계획 화면이 열린다", async ({ page }) => {
  await page.getByRole("link", { name: /MES 생산관리/ }).click();
  await expect(page).toHaveURL(/\/mes\/production-plans$/);
  await expect(
    page.getByRole("heading", { name: "생산계획", level: 1 }),
  ).toBeVisible();
});

test("계획 라인에서 작업지시를 만들어 발행하면 LOT이 생긴다", async ({
  page,
}) => {
  await page.goto("/mes/production-plans");
  await page
    .getByRole("table", { name: "생산계획 목록" })
    .getByRole("row", { name: /^PP-2026-09/ })
    .getByRole("button", { name: /라인/ })
    .click();
  await page
    .getByRole("table", { name: "PP-2026-09 계획 라인" })
    .getByRole("link", { name: "지시 만들기" })
    .first()
    .click();
  await expect(page).toHaveURL(/\/mes\/work-orders\?line=\d+$/);
  await page.getByLabel("지시 수량").fill("100");
  await page.getByLabel("계획 시작일").fill("2026-09-28");
  await page.getByLabel("계획 종료일").fill("2026-09-30");
  await page.getByRole("button", { name: "등록" }).click();
  const orders = page.getByRole("table", { name: "작업지시 목록" });
  const created = orders.getByRole("row", { name: /^WO-0031/ });
  await expect(created).toContainText("등록");
  await created.getByRole("button", { name: "발행" }).click();
  await expect(created).toContainText("LT-0027");
});

test("품목 단위 환산을 보고 기준 단위 잠금을 확인한다", async ({ page }) => {
  await page.goto("/mes/items");
  const items = page.getByRole("table", { name: "품목 목록" });
  const pin = items.getByRole("row", { name: /^RM-PIN/ });
  await pin.getByRole("button", { name: /환산/ }).click();
  await expect(
    page
      .getByRole("table", { name: "RM-PIN 단위 환산 목록" })
      .getByRole("cell", { name: "1 BOX = 10,000 EA" }),
  ).toBeVisible();
  await pin.getByRole("button", { name: "수정" }).click();
  await page.getByLabel("기준 단위").selectOption("KG");
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page.getByText("단위 환산 1건")).toBeVisible();
});

test("공정은 허용 설비를 보여준다", async ({ page }) => {
  await page.goto("/mes/processes");
  await expect(
    page
      .getByRole("table", { name: "공정 목록" })
      .getByRole("row", { name: /^INJ/ }),
  ).toContainText("INJ-01");
});

test("공정 경로를 개정해 초안 순서를 바꾸고 게시한다", async ({ page }) => {
  await page.goto("/mes/routes");
  const routes = page.getByRole("table", { name: "공정 경로 목록" });
  await routes
    .getByRole("row", { name: /^RT-C100 .* v1/ })
    .getByRole("button", { name: "개정" })
    .click();
  const steps = page.getByRole("table", { name: "RT-C100 v2 공정 순서" });
  await expect(steps.getByRole("row")).toHaveCount(4);
  await page.getByRole("button", { name: "3번째 공정 위로" }).click();
  await page.getByRole("button", { name: "순서 저장" }).click();
  await expect(steps.getByRole("row").nth(2)).toContainText("INS");
  await routes
    .getByRole("row", { name: /^RT-C100 .* v2/ })
    .getByRole("button", { name: "게시" })
    .click();
  // 게시된 버전에만 "폐기" 버튼이 생긴다.
  await expect(
    routes
      .getByRole("row", { name: /^RT-C100 .* v2/ })
      .getByRole("button", { name: "폐기" }),
  ).toBeVisible();
});

test("게시된 BOM은 구성을 바꿀 수 없다", async ({ page }) => {
  await page.goto("/mes/boms");
  await page
    .getByRole("table", { name: "BOM 목록" })
    .getByRole("row", { name: /^BOM-C100/ })
    .getByRole("button", { name: /자재/ })
    .click();
  await expect(
    page.getByText(/게시·폐기된 버전은 바꿀 수 없습니다/),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "구성 저장" })).toHaveCount(0);
});
