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
test("흐름 노드에서 QMS 검사 대기 도움말로 이동", async ({ page }) => {
  await page.goto("/flow");
  await page.getByRole("link", { name: /08 \/ QMS/ }).click();
  await expect(page).toHaveURL("/help/qms/q-03");
  await expect(
    page.getByRole("heading", { name: "검사 대기", exact: true }).first(),
  ).toBeVisible();
});
test("도움말 허브에서 공통 도움말로 이동", async ({ page }) => {
  await page.getByRole("link", { name: "도움말", exact: true }).click();
  await page.getByRole("link", { name: "공통 이용 안내", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "공통 이용 안내" }),
  ).toBeVisible();
});
test("참고 문서 ↔ 업무 화면 왕복: 이 화면 열기와 ? 도움말", async ({
  page,
}) => {
  await page.goto("/help?q=소명");
  await page
    .getByRole("region", { name: "검색 결과" })
    .getByRole("link", { name: /E-09/ })
    .click();
  await expect(page).toHaveURL("/help/erp/e-09");
  await page.getByRole("link", { name: "이 화면 열기 →" }).click();
  await expect(page).toHaveURL("/erp/receivables");
  await page.getByRole("link", { name: "매출채권 현황 도움말" }).click();
  await expect(page).toHaveURL("/help/erp/e-09");
  await expect(
    page
      .getByRole("navigation", { name: "문서 목록" })
      .getByRole("link", { name: /E-09/ }),
  ).toHaveAttribute("aria-current", "page");
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
  ["cards/wms", "설명 카드"],
  ["help", "참고 문서"],
  ["workspace", "내 공간"],
  ["records", "페이지를 찾을 수 없습니다"],
  ["erp/dashboard", "경영 개요"],
  ["erp/quotations", "견적"],
  ["erp/sales-plans", "판매계획"],
  ["erp/sales-orders", "수주"],
  ["erp/shipment-orders", "출하지시"],
  ["erp/shipments", "출하"],
  ["erp/sales-records", "매출"],
  ["erp/tax-invoices", "세금계산서"],
  ["erp/receivables", "매출채권 현황"],
  ["erp/receipts", "수금 등록·소명"],
  ["erp/purchase-invoices", "매입 전표"],
  ["erp/payables", "매입채무 현황"],
  ["erp/payments", "지급 등록·소명"],
  ["erp/journal-preview", "분개 미리보기"],
  ["erp/partners", "거래처"],
  ["erp/items", "품목"],
  ["erp/partner-prices", "거래처별 단가"],
  ["erp/accounts", "계정과목·분개규칙"],
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
  ["mes/dashboard", "생산 개요"],
  ["mes/production-plans", "생산계획"],
  ["mes/work-orders", "작업지시"],
  ["mes/lots", "LOT 현황"],
  ["mes/executions", "공정 실행"],
  ["mes/material-issues", "자재 투입"],
  ["mes/results", "실적 확정"],
  ["mes/packing", "패킹"],
  ["mes/receipts", "완제품 입고"],
  ["mes/sites", "사업장·공간"],
  ["mes/equipments", "설비"],
  ["mes/items", "품목"],
  ["mes/processes", "공정"],
  ["mes/routes", "공정 경로"],
  ["mes/boms", "BOM"],
  ["qms/dashboard", "품질 개요"],
  ["qms/pending", "검사 대기"],
  ["qms/inspections", "검사"],
  ["qms/holds", "품질 보류"],
  ["qms/specs", "검사 기준"],
  ["qms/defect-types", "불량 유형"],
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

test("ERP 거래처 등록 → 수정 → 삭제", async ({ page }) => {
  await page.getByRole("link", { name: /ERP/ }).click();
  await expect(page).toHaveURL("/erp/dashboard");
  await page.getByRole("link", { name: /E-15 거래처/ }).click();
  await expect(
    page.getByRole("heading", { name: "거래처", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "거래처 등록" }).click();
  await page.getByLabel("거래처 코드", { exact: true }).fill("E2E-ERP");
  await page.getByLabel("거래처명", { exact: true }).fill("브라우저 거래처");
  await page.getByRole("button", { name: "등록", exact: true }).click();
  const row = page.getByRole("row", { name: /^E2E-ERP/ });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "수정", exact: true }).click();
  await page.getByLabel("거래처명", { exact: true }).fill("변경 거래처");
  await page.getByRole("button", { name: "저장", exact: true }).click();
  await expect(row).toContainText("변경 거래처");
  await row.getByRole("button", { name: "삭제", exact: true }).click();
  await page.getByRole("button", { name: "삭제 확인", exact: true }).click();
  await expect(row).toHaveCount(0);
});

test("ERP 견적 작성 → 확정 → 제출 → 수주 전환", async ({ page }) => {
  await page.goto("/erp/quotations");
  await page.getByRole("button", { name: "견적 만들기" }).click();
  const create = page.getByRole("form", { name: "견적 만들기" });
  await create.getByLabel("견적번호").fill("E2E-Q1");
  await create.getByRole("button", { name: "만들기" }).click();
  const detail = page.getByRole("dialog", { name: /E2E-Q1 1차/ });
  await expect(detail).toBeVisible();
  await detail.getByRole("button", { name: "라인 추가" }).click();
  const item = detail.getByLabel("1번째 품목");
  const option = await item.locator("option", { hasText: "FG-C100" }).first();
  await item.selectOption((await option.getAttribute("value"))!);
  await detail.getByLabel("1번째 수량").fill("10");
  await detail.getByRole("button", { name: "라인 저장" }).click();
  await expect(detail.getByText("거래처 단가 적용")).toBeVisible();
  await detail.getByRole("button", { name: "확정", exact: true }).click();
  await detail.getByRole("button", { name: "제출", exact: true }).click();
  const convert = detail.getByRole("form", { name: "수주 전환" });
  await convert.getByLabel("수주번호").fill("E2E-SO1");
  await convert.getByLabel("납기일").fill("2026-12-31");
  await convert.getByRole("button", { name: "수주로 전환" }).click();
  await expect(detail.getByText(/수주로 전환된 견적입니다/)).toBeVisible();
  await page.goto("/erp/sales-orders");
  await expect(page.getByRole("row", { name: /^E2E-SO1/ })).toContainText(
    "E2E-Q1 (1차)",
  );
});

test("ERP 수주 출하지시 → 출하 확정 → 수주 완료", async ({ page }) => {
  await page.goto("/erp/shipment-orders");
  await page.getByRole("button", { name: "출하지시 만들기" }).click();
  const form = page.getByRole("form", { name: "출하지시 만들기" });
  await form.getByLabel("출하지시번호").fill("E2E-SHO1");
  const order = form.getByLabel("수주");
  const option = order.locator("option", { hasText: "SO-0008" });
  await order.selectOption((await option.getAttribute("value"))!);
  await form.getByRole("button", { name: "출하지시" }).click();
  await expect(page.getByRole("row", { name: /^E2E-SHO1/ })).toContainText(
    "미출하",
  );
  await page.getByRole("link", { name: /E-06 출하$/ }).click();
  await page
    .locator(".page-actions")
    .getByRole("button", { name: "출하 확정" })
    .click();
  const ship = page.getByRole("form", { name: "출하 확정" });
  await ship.getByLabel("출하번호").fill("E2E-SH1");
  const target = ship.getByLabel("출하지시");
  const pick = target.locator("option", { hasText: "E2E-SHO1" });
  await target.selectOption((await pick.getAttribute("value"))!);
  await ship.getByRole("button", { name: "출하 확정" }).click();
  await expect(page.getByRole("row", { name: /^E2E-SH1/ })).toContainText("원");
  await page.getByRole("link", { name: /E-04 수주/ }).click();
  await expect(page.getByRole("row", { name: /^SO-0008/ })).toContainText(
    "완료",
  );
});

test("ERP 세금계산서 발급 → 매출 취소 막힘", async ({ page }) => {
  await page.goto("/erp/tax-invoices");
  await page.getByRole("button", { name: "계산서 만들기" }).click();
  const create = page.getByRole("form", { name: "새 세금계산서" });
  const sale = create.getByLabel("매출");
  const option = sale.locator("option", { hasText: "SH-0004" });
  await sale.selectOption((await option.getAttribute("value"))!);
  await create.getByRole("button", { name: "발급대기로 만들기" }).click();
  const row = page.getByRole("row", { name: /^SH-0004/ });
  await expect(row).toContainText("발급대기");
  await row.getByRole("button", { name: "발급" }).click();
  const issue = page.getByRole("form", { name: "SH-0004 발급" });
  await issue.getByLabel("승인번호").fill("E2E-TI-1");
  await issue.getByRole("button", { name: "발급완료로 기록" }).click();
  await expect(row).toContainText("E2E-TI-1");
  await page.getByRole("link", { name: /E-07 매출/ }).click();
  await expect(
    page
      .getByRole("row", { name: /^SH-0004/ })
      .getByRole("button", { name: "취소" }),
  ).toBeDisabled();
});

test("ERP 수금 등록 → 확정 → FIFO 소명 → 채권 회수완료", async ({ page }) => {
  await page.goto("/erp/receipts");
  await page
    .locator(".page-actions")
    .getByRole("button", { name: "수금 등록" })
    .click();
  const create = page.getByRole("form", { name: "수금 등록" });
  await create.getByLabel("수금번호").fill("E2E-RC1");
  await create.getByLabel("수금액").fill("1827800");
  await create.getByRole("button", { name: "등록" }).click();
  const row = page.getByRole("row", { name: /^E2E-RC1/ });
  await row.getByRole("button", { name: "확정" }).click();
  await expect(row).toContainText("확정");
  const panel = page.getByRole("region", { name: "소명" });
  await panel.getByRole("button", { name: "FIFO로 채우기" }).click();
  await expect(panel.getByLabel("SH-0001 소명액")).toHaveValue("1827800");
  await panel.getByRole("button", { name: "소명 저장" }).click();
  await expect(panel.getByText(/미소명 0원/).first()).toBeVisible();
  await page.getByRole("link", { name: /E-09 매출채권 현황/ }).click();
  await expect(page.getByRole("row", { name: /^SH-0001/ })).toContainText(
    "회수완료",
  );
});

test("ERP 매입 전표 작성 → 확정 → 매입채무 생성", async ({ page }) => {
  await page.goto("/erp/purchase-invoices");
  await page.getByRole("button", { name: "매입 전표 등록" }).click();
  const create = page.getByRole("form", { name: "새 매입 전표" });
  await create.getByLabel("전표번호").fill("E2E-PI1");
  await create.getByRole("button", { name: "등록" }).click();
  const detail = page.getByRole("region", { name: "매입 명세" });
  await detail.getByRole("button", { name: "라인 추가" }).click();
  await detail.getByLabel("1번째 수량").fill("10");
  await detail.getByLabel("1번째 단가").fill("1000");
  await detail.getByRole("button", { name: "명세 저장" }).click();
  await expect(detail).toContainText("합계 11,000원");
  const row = page.getByRole("row", { name: /^E2E-PI1/ });
  await row.getByRole("button", { name: "확정", exact: true }).click();
  await expect(row).toContainText("확정");
  await page.getByRole("link", { name: /E-12 매입채무 현황/ }).click();
  await expect(page.getByRole("row", { name: /^E2E-PI1/ })).toContainText(
    "미지급",
  );
});

test("ERP 매출 분개 보기 → 차대 합계 일치", async ({ page }) => {
  await page.goto("/erp/sales-records");
  await page
    .getByRole("row", { name: /^SH-0001/ })
    .getByRole("button", { name: "분개" })
    .click();
  const panel = page.getByRole("region", { name: "분개 미리보기" });
  await expect(panel).toContainText("외상매출금 3,627,800원");
  await expect(panel).toContainText(
    "차변 합계 3,627,800원 · 대변 합계 3,627,800원",
  );
});

test("ERP 대시보드 → 처리 대기에서 세금계산서로 이동", async ({ page }) => {
  await page.goto("/erp");
  await expect(page).toHaveURL("/erp/dashboard");
  await expect(
    page.getByRole("region", { name: "미수금", exact: true }),
  ).toContainText("원");
  await page.getByRole("link", { name: "세금계산서 미발급 매출" }).click();
  await expect(page).toHaveURL("/erp/tax-invoices");
});
