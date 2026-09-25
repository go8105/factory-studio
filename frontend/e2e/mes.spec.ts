import { expect, test } from "@playwright/test";

// MES 기준정보(FS-020a). 테스트마다 새 게스트 공간을 쓴다.
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});

test("포털에서 MES로 들어가면 기준정보 화면이 열린다", async ({ page }) => {
  await page.getByRole("link", { name: /MES 생산관리/ }).click();
  await expect(page).toHaveURL(/\/mes\/sites$/);
  await expect(
    page.getByRole("heading", { name: "사업장·공간", exact: true }),
  ).toBeVisible();
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
