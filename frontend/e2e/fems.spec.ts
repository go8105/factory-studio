import { test, expect } from "@playwright/test";
// FS-018a F-11 실제 API 스모크. 게스트 공간의 시드 에너지원 3종을 사용한다.
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});
test("런처 FEMS에서 대시보드로 이동", async ({ page }) => {
  await page.getByRole("link", { name: /FEMS 에너지관리/ }).click();
  await expect(page).toHaveURL("/fems/dashboard");
  await expect(page.getByLabel("목표 대비")).toContainText("%");
  await expect(page.getByLabel("계측 품질 이상")).toContainText("6건");
});
test("계측 조회는 서버가 정한 기간으로 시작", async ({ page }) => {
  await page.goto("/fems/readings");
  await expect(page.getByLabel("시작일")).not.toHaveValue("");
  await expect(
    page.getByRole("cell", { name: "수전 전력" }).first(),
  ).toBeVisible();
});
test("결측 구간은 결측으로 표시", async ({ page }) => {
  await page.goto("/fems/readings");
  // 첫 로드가 서버 기본 기간으로 입력을 덮어쓰므로 먼저 기다린다(계획서 §7-8).
  await expect(page.getByLabel("시작일")).not.toHaveValue("");
  await page.getByLabel("품질").selectOption("invalid");
  await page.getByLabel("시작일").fill("2026-08-25");
  await page.getByLabel("종료일").fill("2026-09-23");
  await page.getByRole("button", { name: "조회" }).click();
  await expect(page.getByText("총 6건")).toBeVisible();
  await expect(page.getByRole("cell", { name: "결측" }).first()).toBeVisible();
});
test("채널 선택 후 선 그래프 전환", async ({ page }) => {
  await page.goto("/fems/readings");
  await page.getByLabel("채널").selectOption({ label: "수전 전력" });
  await page.getByRole("button", { name: "조회" }).click();
  await page.getByRole("button", { name: "선 그래프" }).click();
  await expect(
    page.getByRole("img", { name: "수전 전력 계측값 선 그래프" }),
  ).toBeVisible();
});
test("에너지원 등록 후 목록에 표시", async ({ page }) => {
  await page.goto("/fems/energy-sources");
  await page.getByLabel("에너지원 코드").fill("STEAM");
  await page.getByLabel("에너지원명").fill("스팀");
  await page.getByRole("button", { name: "등록", exact: true }).click();
  await expect(page.getByRole("cell", { name: "스팀" })).toBeVisible();
});
test("참조 중인 전력 삭제는 참조 건수로 거부", async ({ page }) => {
  await page.goto("/fems/energy-sources");
  const row = page.getByRole("row", { name: /ELEC/ });
  await row.getByRole("button", { name: "삭제" }).click();
  await row.getByRole("button", { name: "삭제 확정" }).click();
  await expect(page.getByText(/계측 채널 \d+건/)).toBeVisible();
  await expect(page.getByRole("cell", { name: "전력" })).toBeVisible();
});
test("설비별 배분은 단위별 합계와 근거를 보여준다", async ({ page }) => {
  await page.goto("/fems/allocations");
  await expect(
    page.getByRole("heading", { name: "설비별 합계 · kWh" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "설비별 합계 · m3" }),
  ).toBeVisible();
  await page.getByText("근거").first().click();
  await expect(page.getByText("배분 방법").first()).toBeVisible();
});
test("결측이 있던 날의 배분은 추정으로 표시", async ({ page }) => {
  await page.goto("/fems/allocations");
  // 첫 조회가 서버 기본 기간으로 입력을 덮어쓰지 않도록 로드를 기다린다.
  await expect(page.getByLabel("시작일")).not.toHaveValue("");
  await page.getByLabel("시작일").fill("2026-09-07");
  await page.getByLabel("종료일").fill("2026-09-07");
  await page.getByRole("button", { name: "조회" }).click();
  await expect(page.getByText("추정 1일")).toBeVisible();
});
test("배출량은 총량과 에너지원별 상태를 보여준다", async ({ page }) => {
  await page.goto("/fems/emissions");
  await expect(page.getByLabel("총 배출량")).toContainText("tCO2eq");
  const water = page.getByRole("row", { name: /용수/ });
  await expect(water.getByText("대상 아님")).toBeVisible();
  const elec = page.getByRole("row", { name: /전력/ });
  await elec.getByText("근거").click();
  await expect(elec.getByText("tCO2eq/kWh")).toBeVisible();
});
test("대시보드 전월은 목표 초과로 표시", async ({ page }) => {
  await page.goto("/fems/dashboard");
  await page.getByLabel("조회 월").fill("2026-08");
  await expect(page.getByLabel("목표 대비")).toContainText("목표 초과");
});
test("목표 대비 실적은 범위별 섹션과 미설정을 보여준다", async ({ page }) => {
  await page.goto("/fems/targets");
  await expect(
    page.getByRole("heading", { name: "사업장 목표" }),
  ).toBeVisible();
  const ins02 = page.getByRole("row", { name: /INS-02/ });
  await expect(ins02.getByText("미설정")).toBeVisible();
  await expect(page.getByText("목표 이내").first()).toBeVisible();
  await expect(page.getByText("목표 초과").first()).toBeVisible();
});
test("요금 산정은 요금제 개정 월에서 구간을 나눈다", async ({ page }) => {
  await page.goto("/fems/billing");
  const elec = page.getByLabel("전력 요금");
  await expect(elec.getByText(/TR-ELEC-01/)).toBeVisible();
  await expect(elec.getByText(/TR-ELEC-02/)).toBeVisible();
  await expect(page.getByLabel("예상 요금 합계")).toContainText("원");
});
test("넓은 화면은 메뉴 링크를 눌러도 사이드바가 남는다", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/fems/dashboard");
  const menu = page.getByRole("complementary", { name: "FEMS 메뉴" });
  await menu.getByRole("link", { name: /F-02 계측 조회/ }).click();
  await expect(page).toHaveURL("/fems/readings");
  await expect(
    menu.getByRole("link", { name: /F-03 설비별 배분/ }),
  ).toBeVisible();
});
test("좁은 화면은 메뉴가 접힌 채 시작하고 펼쳐서 이동한다", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/fems/dashboard");
  const menu = page.getByRole("complementary", { name: "FEMS 메뉴" });
  const link = menu.getByRole("link", { name: /F-02 계측 조회/ });
  await expect(link).toBeHidden();
  await menu.getByText("FEMS 메뉴 · F-01 대시보드").click();
  await link.click();
  await expect(page).toHaveURL("/fems/readings");
  await expect(link).toBeHidden();
});
test("생산량은 초안 등록 → 확정 → 정정 초안 순서로 흐른다", async ({
  page,
}) => {
  await page.goto("/fems/production");
  // UI-02: 등록 폼은 제목 줄의 버튼으로 여는 오른쪽 패널이다.
  await page.getByRole("button", { name: "생산량 등록" }).click();
  const form = page.getByRole("form", { name: "생산량 등록" });
  await form.getByLabel("설비").selectOption({ label: "INS-01 검사기 1호" });
  await form.getByLabel("품목 코드").fill("fg-c100");
  await form.getByLabel("시작일").fill("2026-09-20");
  await form.getByLabel("종료일 (포함)").fill("2026-09-20");
  await form.getByLabel("생산량", { exact: true }).fill("50");
  await form.getByRole("button", { name: "초안 등록" }).click();
  await expect(page.getByRole("status")).toContainText("MAN-20260920-001 v1");
  const row = page.getByRole("row", { name: /MAN-20260920-001/ });
  await row.getByRole("button", { name: "확정" }).click();
  await expect(row.getByText("확정 · 원단위 반영")).toBeVisible();
  await row.getByRole("button", { name: "정정" }).click();
  await expect(page.getByRole("status")).toContainText("v2 정정 초안");
  await expect(page.getByLabel("설비", { exact: true })).toBeDisabled();
});
test("원단위는 기준선을 재현하고 생산량 0을 구분한다", async ({ page }) => {
  await page.goto("/fems/intensity");
  const items = page.getByLabel("품목 원단위");
  await expect(items.getByRole("row", { name: /FG-C100/ })).toContainText(
    "2.003 kWh/EA",
  );
  await expect(items.getByText("기준선과 같음").first()).toBeVisible();
  const zero = page.getByRole("row", { name: /MES:LT-0018:INS/ });
  await expect(zero.getByText("생산량 없음 · 계산 불가")).toBeVisible();
});
test("환산·배출계수는 탭으로 나뉘고 단위는 서버가 정한다", async ({ page }) => {
  await page.goto("/fems/energy-factors");
  const primary = page.getByRole("table", { name: "1차에너지 환산계수 목록" });
  await expect(
    primary.getByRole("cell", { name: "TOE/kWh" }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "온실가스 배출계수" }).click();
  const emission = page.getByRole("table", { name: "온실가스 배출계수 목록" });
  await expect(
    emission.getByRole("cell", { name: "tCO2eq/kWh" }).first(),
  ).toBeVisible();
  await page.getByLabel("적용 연도").fill("2027");
  await page.getByLabel(/^계수 \(/).fill("0.000450");
  await page.getByLabel("출처").fill("e2e 예시값");
  await page.getByRole("button", { name: "등록" }).click();
  await expect(emission.getByRole("row", { name: /2027/ })).toContainText(
    "tCO2eq/kWh",
  );
});
test("계측기 채널은 배수를 강조하고 사용 중인 단위를 잠근다", async ({
  page,
}) => {
  await page.goto("/fems/meters");
  const meters = page.getByRole("table", { name: "계측기 목록" });
  await meters
    .getByRole("row", { name: /^M-MAIN/ })
    .getByRole("button", { name: /채널/ })
    .click();
  const channels = page.getByRole("table", { name: "M-MAIN 채널 목록" });
  await channels.getByRole("button", { name: "수정" }).click();
  await expect(page.getByLabel("단위")).toBeDisabled();
  await page.getByLabel("계기 배수").fill("2");
  await page.getByRole("button", { name: "저장" }).click();
  await expect(channels.getByText("× 2")).toBeVisible();
});
test("사업장 시간대는 기록이 있으면 잠기고 공간 삭제는 참조 건수를 알린다", async ({
  page,
}) => {
  await page.goto("/fems/sites");
  const sites = page.getByRole("table", { name: "사업장 목록" });
  await sites
    .getByRole("row", { name: /^S01/ })
    .getByRole("button", { name: "수정" })
    .click();
  await page.getByLabel("시간대").fill("Asia/Tokyo");
  await page.getByRole("button", { name: "저장" }).click();
  await expect(
    page.getByText(/날짜 경계가 달라져 지난 합계가 바뀝니다/),
  ).toBeVisible();
  const places = page.getByRole("table", { name: "공간 목록" });
  const inj = places.getByRole("row", { name: /^L-INJ/ });
  await inj.getByRole("button", { name: "삭제" }).click();
  await inj.getByRole("button", { name: "삭제 확정" }).click();
  await expect(page.getByText(/^설비 \d+건$/)).toBeVisible();
});
