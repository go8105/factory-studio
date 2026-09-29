import { expect, test } from "@playwright/test";

// FS-024 WMS 실제 API 흐름. 테스트마다 새 게스트 공간(MES·ERP·WMS 시드, FS-024c)을 쓴다.
// 시드: WH-RAW·WH-FG 창고, 원자재 2·완제품 3 품목, 반영된 입고 PL-0001~0005 · 미반영 PL-0006(FG-T300, LT-0009·LT-0012).
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("별칭").fill("E2E 평가자");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});

test("시드 품목·환산 → MES 입고 반영 → 재고 현황·원장 → 폐기 조정", async ({
  page,
}) => {
  await page.goto("/wms/items");
  await expect(page.getByRole("row", { name: /RM-PIN/ })).toContainText(
    "1 BOX = 10,000 EA",
  );

  await page.goto("/wms/sources");
  const table = page.getByRole("table", { name: "MES 완제품 입고 원천" });
  await table
    .getByRole("row", { name: /PL-0006/ })
    .getByRole("button", { name: "반영" })
    .click();
  await expect(page.getByRole("status")).toContainText("반영 1");

  await page.goto("/wms/stock?lotNo=LT-0009");
  await expect(
    page.getByRole("table", { name: "재고 현황" }).getByRole("row", {
      name: /LT-0009/,
    }),
  ).toContainText("982");
  await page
    .getByRole("row", { name: /LT-0009/ })
    .getByRole("link", { name: "원장" })
    .click();
  await expect(page).toHaveURL(/\/wms\/moves\?itemCode=FG-T300&lotNo=LT-0009/);
  await expect(
    page.getByRole("table", { name: "재고 원장" }).getByRole("row", {
      name: /PL-0006/,
    }),
  ).toContainText("+982");

  await page.goto("/wms/documents");
  await page.getByLabel("전표 만들기").selectOption("ADJUSTMENT");
  const form = page.getByRole("dialog", { name: "조정 전표 작성" });
  await form.getByLabel("조정 사유").selectOption("SCRAP");
  await form
    .getByLabel("1번 줄 품목")
    .selectOption({ label: "FG-T300 터미널블록 T300" });
  await form.getByLabel("1번 줄 LOT").fill("LT-0009");
  await form.getByLabel("1번 줄 위치").selectOption({ label: "WH-FG F-A01" });
  await form.getByLabel("1번 줄 수량").fill("-40");
  await form.getByRole("button", { name: "확정" }).click();
  await expect(page.getByRole("status")).toContainText("확정");
  await page.goto("/wms/stock?lotNo=LT-0009");
  await expect(
    page.getByRole("table", { name: "재고 현황" }).getByRole("row", {
      name: /LT-0009/,
    }),
  ).toContainText("942");
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
