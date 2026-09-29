import { expect, test } from "@playwright/test";

// MES 기준정보(FS-020a). 테스트마다 새 게스트 공간을 쓴다.
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("별칭").fill("E2E 평가자");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});

test("포털에서 MES로 들어가면 대시보드가 열린다", async ({ page }) => {
  await page.getByRole("link", { name: /MES 생산관리/ }).click();
  await expect(page).toHaveURL(/\/mes\/dashboard$/);
  await expect(page.getByLabel("양품률")).toContainText("%");
  await expect(page.getByLabel("공정별 진행 현황")).toContainText("실행 중");
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
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "등록", exact: true })
    .click();
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
  const panel = page.getByRole("dialog", { name: /RT-C100 v2 공정 순서/ });
  await expect(panel).toBeVisible();
  const steps = panel.getByRole("table", { name: "RT-C100 v2 공정 순서" });
  await expect(steps.getByRole("row")).toHaveCount(4);
  await panel.getByRole("button", { name: "3번째 공정 위로" }).click();
  await panel.getByRole("button", { name: "순서 저장" }).click();
  await expect(steps.getByRole("row").nth(2)).toContainText("INS");
  await page.getByRole("button", { name: "패널 닫기" }).click();
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

test("대기 LOT의 첫 공정을 시작하고 실적을 확정하면 이력에 남는다", async ({
  page,
}) => {
  await page.goto("/mes/executions");
  const startable = page.getByRole("table", { name: "시작할 수 있는 LOT" });
  const row = startable.getByRole("row", { name: /1\/3 사출/ }).first();
  const lotNo = (await row.getByRole("cell").first().textContent())!.trim();
  await row.getByRole("button", { name: "시작" }).click();
  await page
    .getByRole("form", { name: "공정 시작" })
    .getByRole("button", { name: "시작" })
    .click();
  const running = page.getByRole("table", { name: "실행 중인 공정" });
  await running
    .getByRole("row", { name: new RegExp(`^${lotNo}`) })
    .getByRole("button", { name: "실적 확정" })
    .click();
  const input = await page
    .getByText(/투입 [\d,]+ EA \(지시 수량\)/)
    .textContent();
  const total = Number(input!.match(/투입 ([\d,]+)/)![1].replaceAll(",", ""));
  await page.getByLabel("양품").fill(String(total - 20));
  await page.getByLabel("불량", { exact: true }).fill("20");
  await page.getByLabel("불량 사유").fill("미성형");
  await page
    .getByRole("form", { name: "실적 확정" })
    .getByRole("button", { name: "확정", exact: true })
    .click();
  await expect(page.getByRole("form", { name: "실적 확정" })).toHaveCount(0);
  await page.goto("/mes/lots");
  await page
    .getByRole("table", { name: "LOT 목록" })
    .getByRole("row", { name: new RegExp(`^${lotNo}`) })
    .getByRole("button", { name: "이력" })
    .click();
  await expect(
    page
      .getByRole("table", { name: `${lotNo} 공정 이력` })
      .getByRole("row")
      .nth(1),
  ).toContainText("미성형");
});

test("새로 시작한 공정에 BOM 제안량으로 자재를 투입한다", async ({ page }) => {
  await page.goto("/mes/executions");
  const row = page
    .getByRole("table", { name: "시작할 수 있는 LOT" })
    .getByRole("row", { name: /1\/3 사출/ })
    .first();
  const lotNo = (await row.getByRole("cell").first().textContent())!.trim();
  await row.getByRole("button", { name: "시작" }).click();
  await page
    .getByRole("form", { name: "공정 시작" })
    .getByRole("button", { name: "시작" })
    .click();
  await page.goto("/mes/material-issues");
  await expect(page.getByText(/재고를 차감하지 않습니다/)).toBeVisible();
  await page
    .getByRole("table", { name: "실행 중인 공정" })
    .getByRole("row", { name: new RegExp(`^${lotNo}`) })
    .getByRole("button", { name: "투입" })
    .click();
  await page
    .getByRole("table", { name: "BOM 기준 소요량" })
    .getByRole("row", { name: /RM-PBT/ })
    .getByRole("button", { name: "제안량 채우기" })
    .click();
  await page.getByRole("button", { name: "투입 기록" }).click();
  const issues = page.getByRole("table", { name: "이 공정의 투입 기록" });
  await expect(issues.getByRole("row", { name: /RM-PBT/ })).toContainText("KG");
  await expect(
    page
      .getByRole("table", { name: "BOM 기준 소요량" })
      .getByRole("row", { name: /RM-PBT/ }),
  ).toContainText("투입 완료");
});

test("남은 양품을 BOX에 담아 PALLET으로 묶고 입고한다", async ({ page }) => {
  await page.goto("/mes/packing");
  await page.getByRole("button", { name: "새 PALLET" }).click();
  await expect(page.getByRole("heading", { name: /PL-0007/ })).toBeVisible();
  // 만든 포장은 오른쪽 패널로 열린다. 닫고 다음 포장을 만든다.
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "새 BOX" }).click();
  await expect(page.getByRole("heading", { name: /BX-0031/ })).toBeVisible();
  await page.getByRole("button", { name: "담기" }).click();
  await expect(
    page.getByRole("table", { name: "BX-0031 구성" }).getByRole("row"),
  ).toHaveCount(2);
  await page.getByRole("button", { name: "BOX 닫기" }).click();
  await page.getByRole("button", { name: "PALLET에 묶기" }).click();
  await page.keyboard.press("Escape");
  const units = page.getByRole("table", { name: "포장 목록" });
  await units
    .getByRole("row", { name: /^PL-0007/ })
    .getByRole("button", { name: "열기" })
    .click();
  await page.getByRole("button", { name: "PALLET 닫기" }).click();
  await page.goto("/mes/receipts");
  await page
    .getByRole("table", { name: "입고할 PALLET" })
    .getByRole("row", { name: /^PL-0007/ })
    .getByRole("button", { name: "입고" })
    .click();
  await expect(
    page
      .getByRole("table", { name: "입고 내역" })
      .getByRole("row", { name: /^PL-0007/ }),
  ).toBeVisible();
});
