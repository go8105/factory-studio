import { expect, test, type Page } from "@playwright/test";

// FS-024b WMS 실제 API 흐름. 테스트마다 새 게스트 공간(MES·ERP 시드 포함, WMS 시드는 FS-024c).
// 창고·위치는 API로 준비하고, 품목 가져오기·원천 반영·조정 확정은 화면으로 한다.
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});

async function call(page: Page, method: string, path: string, body?: unknown) {
  return page.evaluate(
    async ({ method, path, body }) => {
      const session = await (
        await fetch("/api/v1/core/sessions/current")
      ).json();
      const response = await fetch(path, {
        method,
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": session.data.csrfToken,
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      return { status: response.status, data: (await response.json()).data };
    },
    { method, path, body },
  );
}

async function warehouses(page: Page) {
  for (const [code, name, purpose, location] of [
    ["WH-RAW", "원자재 창고", "RAW", "R-A01"],
    ["WH-FG", "완제품 창고", "FG", "F-A01"],
  ]) {
    const house = await call(page, "POST", "/api/v1/wms/warehouses", {
      code,
      name,
      purpose,
    });
    expect(house.status).toBe(201);
    const loc = await call(
      page,
      "POST",
      `/api/v1/wms/warehouses/${house.data.id}/locations`,
      { code: location, name: "기본 보관" },
    );
    expect(loc.status).toBe(201);
  }
}

test("MES 품목 가져오기 → MES 입고 반영 → 재고 현황·원장 → 폐기 조정", async ({
  page,
}) => {
  await warehouses(page);
  await page.goto("/wms/items");
  await page
    .getByRole("button", { name: "MES 품목 가져오기", exact: true })
    .click();
  const importer = page.getByRole("dialog", { name: "MES 품목 가져오기" });
  await importer.getByRole("button", { name: "5개 가져오기" }).click();
  await expect(page.getByRole("cell", { name: "RM-PIN" })).toBeVisible();

  await page.goto("/wms/sources");
  const table = page.getByRole("table", { name: "MES 완제품 입고 원천" });
  await table
    .getByRole("row", { name: /PL-0001/ })
    .getByRole("button", { name: "반영" })
    .click();
  await expect(page.getByRole("status")).toContainText("반영 1");

  await page.goto("/wms/stock");
  const stock = page.getByRole("table", { name: "재고 현황" });
  await expect(stock.getByRole("row", { name: /LT-0001/ })).toContainText(
    "1,940",
  );

  await page
    .getByRole("row", { name: /LT-0001/ })
    .getByRole("link", { name: "원장" })
    .click();
  await expect(page).toHaveURL(/\/wms\/moves\?itemCode=FG-C100&lotNo=LT-0001/);
  await expect(
    page.getByRole("table", { name: "재고 원장" }).getByRole("row", {
      name: /PL-0001/,
    }),
  ).toContainText("+1,940");

  await page.goto("/wms/documents");
  await page.getByLabel("전표 만들기").selectOption("ADJUSTMENT");
  const form = page.getByRole("dialog", { name: "조정 전표 작성" });
  await form.getByLabel("조정 사유").selectOption("SCRAP");
  await form
    .getByLabel("1번 줄 품목")
    .selectOption({ label: "FG-C100 커넥터 C100" });
  await form.getByLabel("1번 줄 LOT").fill("LT-0001");
  await form.getByLabel("1번 줄 위치").selectOption({ label: "WH-FG F-A01" });
  await form.getByLabel("1번 줄 수량").fill("-40");
  await form.getByRole("button", { name: "확정" }).click();
  await expect(page.getByRole("status")).toContainText("확정");
  await page.goto("/wms/stock?itemCode=FG-C100&lotNo=LT-0001");
  await expect(
    page.getByRole("table", { name: "재고 현황" }).getByRole("row", {
      name: /LT-0001/,
    }),
  ).toContainText("1,900");
});

test("MES를 끄면 입고 원천은 꺼짐으로 안내하고 ERP 원천은 그대로 보인다", async ({
  page,
}) => {
  await page.goto("/workspace");
  await page.getByRole("switch", { name: "MES 사용" }).click();
  await expect(page.getByRole("switch", { name: "MES 사용" })).toHaveAttribute(
    "aria-checked",
    "false",
  );
  await page.goto("/wms/sources");
  await expect(
    page.getByText(/MES를 사용하지 않도록 설정했습니다/),
  ).toBeVisible();
  await page.getByRole("button", { name: "ERP 매입" }).click();
  await expect(
    page.getByRole("table", { name: "ERP 매입 원천" }),
  ).toBeVisible();
});

test("1440 재고 전표 넓은 패널은 가로로 넘치지 않는다", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await warehouses(page);
  await page.goto("/wms/documents");
  await page.getByLabel("전표 만들기").selectOption("TRANSFER");
  const form = page.getByRole("dialog", { name: "창고 간 이동 전표 작성" });
  await expect(form).toBeVisible();
  const box = await form.boundingBox();
  expect(box!.width).toBeLessThanOrEqual(641);
  expect(
    await form.evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
  ).toBe(true);
});
