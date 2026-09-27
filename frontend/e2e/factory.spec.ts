import { demoExplanation } from "../src/factory/scenarios";
import { test, expect } from "@playwright/test";
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", (route) =>
    route.fulfill({
      json: {
        data: {
          actorKind: "GUEST",
          workspaceId: 10,
          generationId: 20,
          roles: [],
          csrfToken: "factory-preview",
          expiresAt: "2026-09-27T00:00:00+09:00",
        },
      },
    }),
  );
  await page.goto("/factory");
  await expect(page.locator("canvas")).toBeVisible();
  await expect(
    page.getByText("2F 사무실 · 직원 2명", { exact: true }),
  ).toBeAttached({ timeout: 15000 });
});
test("공장 장면은 브라우저 오류 없이 렌더링된다", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.reload();
  await expect(
    page.getByText("2F 사무실 · 직원 2명", { exact: true }),
  ).toBeAttached({ timeout: 15000 });
  expect(errors).toEqual([]);
});
test("앱 런처 바로 다음 메뉴로 3D 공장에 진입한다", async ({ page }) => {
  const links = page
    .getByRole("navigation", { name: "주 메뉴" })
    .getByRole("link");
  await expect(links.nth(1)).toHaveText("3D 공장");
});
test("걷기 입력은 3인칭 화면을 이동시킨다", async ({ page }) => {
  await page.getByRole("button", { name: "시연 일시정지" }).click();
  await page.getByRole("button", { name: "걸어서 둘러보기" }).click();
  // Let the follow camera settle so only movement changes the next capture.
  await page.waitForTimeout(1600);
  const before = await page.locator("canvas").screenshot();
  await page.getByRole("region", { name: "3D 공장 탐색" }).focus();
  await page.keyboard.down("ArrowRight");
  await page.waitForTimeout(600);
  await page.keyboard.up("ArrowRight");
  await page.waitForTimeout(500);
  expect((await page.locator("canvas").screenshot()).equals(before)).toBe(
    false,
  );
});
test("2층 사무실을 선택하면 해당 시점으로 이동한다", async ({ page }) => {
  await page.getByRole("button", { name: "2층 사무실", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "2층 사무실", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({
    path: "../work/factory-office-check.png",
    fullPage: true,
  });
});
test("비전검사 공정 설명을 선택할 수 있다", async ({ page }) => {
  await page.getByRole("button", { name: /02 비전검사/ }).click();
  await expect(
    page.getByText(/카메라와 조명으로 제품의 외관을 검사/),
  ).toBeVisible();
});
test("360px에서 가로 스크롤 없이 공장 화면을 표시한다", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 900 });
  await expect(
    page.getByRole("button", { name: "걸어서 둘러보기" }),
  ).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    360,
  );
  await page.screenshot({
    path: "../work/factory-mobile-check.png",
    fullPage: true,
  });
});
test("그래픽 연결 손실은 재시도 안내로 대체한다", async ({ page }) => {
  await page
    .locator("canvas")
    .evaluate((canvas) =>
      canvas.dispatchEvent(new Event("webglcontextlost", { cancelable: true })),
    );
  await expect(
    page.getByRole("button", { name: "3D 다시 열기" }),
  ).toBeVisible();
});
test("Blender 설비를 불러오고 검사·정지·재개를 시연한다", async ({ page }) => {
  test.setTimeout(60000); // Includes a complete simulated cycle and software WebGL capture.
  const model = await page.request.get("/models/vision-cell.glb");
  expect(model.ok()).toBe(true);
  expect((await model.body()).subarray(0, 4).toString()).toBe("glTF");
  await page.getByRole("button", { name: /02 비전검사/ }).click();
  await page.getByRole("button", { name: "설비 가까이 보기" }).click();
  await expect(page.getByTestId("vision-count")).not.toHaveText("0개", {
    timeout: 15000,
  });
  await page.getByRole("button", { name: "이상 상황 시연" }).click();
  await expect(page.getByTestId("vision-phase")).toHaveText("이상 정지");
  const count = await page.getByTestId("vision-count").textContent();
  await page.waitForTimeout(1200);
  await expect(page.getByTestId("vision-count")).toHaveText(count!);
  await page.getByRole("button", { name: "이상 해제" }).click();
  await expect(page.getByTestId("vision-phase")).not.toHaveText("이상 정지");
  await page.getByRole("button", { name: "시연 일시정지" }).click();
  await expect(page.getByTestId("vision-phase")).toHaveText("일시정지");
  await expect(
    page.getByRole("link", { name: /MES에서 업무 확인/ }),
  ).toHaveAttribute("href", "/mes");
  await page.screenshot({ path: "../work/vision-desktop.png", fullPage: true });
});
test("건물 외관과 내부를 전환하고 모바일에서도 표시한다", async ({ page }) => {
  await expect(
    page.getByRole("button", { name: "건물 외관", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "시연 일시정지" }).click();
  await page.waitForTimeout(800);
  await expect(page.locator(".factory-label").first()).not.toBeVisible();
  await page.getByRole("button", { name: "시점 초기화" }).click();
  await expect(
    page.getByRole("button", { name: "건물 외관", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const exterior = await page.locator("canvas").screenshot();
  await page.screenshot({
    path: "../work/building-exterior.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "내부 펼쳐보기" }).click();
  await expect(
    page.getByRole("button", { name: "내부 펼쳐보기" }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(500);
  expect((await page.locator("canvas").screenshot()).equals(exterior)).toBe(
    false,
  );
  await page.screenshot({
    path: "../work/building-interior.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "건물 외관", exact: true }).click();
  await page.getByRole("button", { name: "걸어서 둘러보기" }).click();
  await expect(
    page.getByRole("button", { name: "내부 펼쳐보기" }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "건물 외관", exact: true }).click();
  await page.setViewportSize({ width: 360, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    360,
  );
  await page.screenshot({
    path: "../work/building-mobile.png",
    fullPage: true,
  });
});

test("비전검사 상세 패널은 모바일에서 넘치지 않는다", async ({ page }) => {
  await page.getByRole("button", { name: "시연 일시정지" }).click();
  await page.getByRole("button", { name: /02 비전검사/ }).click();
  await page.getByRole("button", { name: "설비 가까이 보기" }).click();
  await page.setViewportSize({ width: 360, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    360,
  );
  await page.screenshot({ path: "../work/vision-mobile.png", fullPage: true });
});

test("1인칭에서 설비를 선택하고 같은 화면에서 상태를 확인한다", async ({
  page,
}) => {
  test.setTimeout(60000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "1인칭 비전검사 체험" }).click();
  const inspect = page.getByRole("button", {
    name: "02 비전검사 · 상태 확인 (E)",
  });
  await expect(inspect).toBeEnabled({ timeout: 15000 });
  await page.screenshot({ path: "../work/inspection-first-person.png" });
  await page.getByRole("region", { name: "3D 공장 탐색" }).focus();
  await page.keyboard.press("e");
  const panel = page.getByRole("region", { name: "비전검사 설비 상세" });
  await expect(panel).toBeVisible();
  await expect(panel.getByText("카메라 노출 · 설정")).toBeVisible();
  await page.getByRole("button", { name: "이상 상황 시연" }).click();
  await expect(page.getByTestId("vision-phase")).toHaveText("이상 정지");
  await page.screenshot({ path: "../work/inspection-panel.png" });
  await page.getByRole("button", { name: "상세 닫기" }).click();
  await expect(panel).not.toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "1인칭 비전검사 체험" }),
  ).toBeVisible();
});

test("1인칭 시선 회전과 모바일 설비 선택", async ({ page }) => {
  test.setTimeout(60000);
  await page.getByRole("button", { name: "시연 일시정지" }).click();
  await page.getByRole("button", { name: "1인칭 비전검사 체험" }).click();
  await expect(
    page.getByRole("button", { name: "02 비전검사 · 상태 확인 (E)" }),
  ).toBeEnabled();
  const box = (await page.locator("canvas").boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 280, box.y + box.height / 2, {
    steps: 12,
  });
  await page.mouse.up();
  await expect(
    page.getByRole("region", { name: "비전검사 설비 상세" }),
  ).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "02 비전검사 · 상태 확인 (E)" }),
  ).not.toBeVisible();
  await page.getByRole("button", { name: "시점 초기화" }).click();
  await expect(
    page.getByRole("button", { name: "02 비전검사 · 상태 확인 (E)" }),
  ).toBeEnabled();
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("button", { name: "02 비전검사 · 상태 확인 (E)" })
    .click();
  await expect(
    page.getByRole("region", { name: "비전검사 설비 상세" }),
  ).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    390,
  );
  await page.screenshot({
    path: "../work/inspection-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "체험 나가기" }).click();
});

test("1인칭 직접 클릭과 시선 기준 이동", async ({ page }) => {
  test.setTimeout(60000);
  await page.getByRole("button", { name: "시연 일시정지" }).click();
  await page.getByRole("button", { name: "1인칭 비전검사 체험" }).click();
  await expect(
    page.getByRole("button", { name: "02 비전검사 · 상태 확인 (E)" }),
  ).toBeEnabled();
  const panel = page.getByRole("region", { name: "비전검사 설비 상세" });
  const canvas = page.locator("canvas");
  const rect = (await canvas.boundingBox())!;
  await canvas.click({ position: { x: rect.width / 2, y: rect.height / 2 } });
  await expect(panel).toBeVisible();
  await page.getByRole("button", { name: "상세 닫기" }).click();
  await page.getByRole("region", { name: "3D 공장 탐색" }).focus();
  const before = await canvas.screenshot();
  await page.keyboard.down("d");
  await page.waitForTimeout(500);
  await page.keyboard.up("d");
  expect((await canvas.screenshot()).equals(before)).toBe(false);

  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "1인칭 비전검사 체험" }),
  ).toBeVisible();
});

test("비전검사 세 시나리오와 설명 출처를 구분한다", async ({ page }) => {
  test.setTimeout(90000);
  await page.route("**/api/v1/factory/vision/explanation", (route) => {
    const { scenario } = route.request().postDataJSON();
    return route.fulfill({
      json: { data: demoExplanation(scenario, "not_configured") },
    });
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "1인칭 비전검사 체험" }).click();
  await page
    .getByRole("button", { name: "02 비전검사 · 상태 확인 (E)" })
    .click();
  const panel = page.getByRole("region", { name: "비전검사 설비 상세" });
  await panel.getByRole("button", { name: "AI 설명", exact: true }).click();
  await expect(panel.getByText("데모 설명 · AI 미연결")).toBeVisible();
  await panel.getByRole("button", { name: "불합격 증가", exact: true }).click();
  await expect(panel.getByText("데모 설명 · AI 미연결")).not.toBeVisible();
  await panel.getByRole("button", { name: "AI 설명", exact: true }).click();
  await expect(
    panel.getByText("불합격률 변화: +18%p", { exact: true }).first(),
  ).toBeVisible();
  await panel.getByRole("button", { name: "정지", exact: true }).click();
  await expect(page.getByTestId("vision-phase")).toHaveText("이상 정지");
  const count = await page.getByTestId("vision-count").textContent();
  await page.waitForTimeout(500);
  await expect(page.getByTestId("vision-count")).toHaveText(count!);
  await panel.getByRole("button", { name: "AI 설명", exact: true }).click();
  await expect(
    panel.getByText("불합격률 변화: +0%p", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({ path: "../work/vision-ai-desktop.png" });
});

test("비전검사 설명 오류와 모바일 패널", async ({ page }) => {
  test.setTimeout(60000);
  await page.route("**/api/v1/factory/vision/explanation", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { code: "UNAVAILABLE", message: "Unavailable" } },
    }),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: /02 비전검사/ }).click();
  const panel = page.getByRole("region", { name: "비전검사 설비 상세" });
  await panel.getByRole("button", { name: "불합격 증가", exact: true }).click();
  await panel.getByRole("button", { name: "AI 설명", exact: true }).click();
  await expect(panel.getByText("데모 설명 · AI 미연결")).toBeVisible();
  await expect(
    panel.getByText("다음 확인 항목", { exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    390,
  );
  await panel.screenshot({ path: "../work/vision-ai-mobile.png" });
});

test("합성 검사실 조건 비교와 JSON 저장", async ({ page }) => {
  await page.getByRole("button", { name: /02 비전검사/ }).click();
  await page.getByRole("link", { name: "합성 이미지 검사실 열기" }).click();
  await expect(
    page.getByRole("heading", { name: "합성 이미지 검사실" }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText("검출 2개");
  await page.getByLabel("최소 면적", { exact: true }).fill("100");
  await expect(page.getByRole("status")).toContainText("OK");
  await expect(page.locator(".lab-metrics")).toContainText("116");
  await page.getByRole("button", { name: "조건 초기화" }).click();
  await page.getByLabel("합성 샘플").selectOption("lighting");
  await page.getByLabel("이진화 임계값", { exact: true }).fill("130");
  await expect(page.locator(".lab-metrics")).toContainText("4000");
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "레시피·결과 JSON 저장" }).click();
  expect((await downloadEvent).suggestedFilename()).toBe(
    "vision-lighting.json",
  );
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: "../work/vision-lab-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    390,
  );
  await page.screenshot({
    path: "../work/vision-lab-mobile.png",
    fullPage: true,
  });
});

test("연속 검사 배치와 이력 및 JSON", async ({ page }) => {
  await page.goto("/factory/vision-lab");
  await page.getByRole("button", { name: "연속 검사", exact: true }).click();
  const run = page.getByRole("region", { name: "연속 검사 관제" });
  await run.getByLabel("투입 목표 간격").selectOption("200");
  await run.getByRole("button", { name: "새 배치 시작" }).click();
  await expect(run.getByRole("status").first()).toHaveText("배치 완료", {
    timeout: 15000,
  });
  await expect(run.getByTestId("run-count")).toHaveText("20 / 20");
  await expect(run.locator(".run-metrics")).toContainText("50.0%");
  await run.getByRole("button", { name: /#2 · 이물/ }).click();
  await expect(run.getByText(/이력 재조회 · #2/)).toBeVisible();
  await run.getByRole("button", { name: "이진화 보기" }).click();
  await expect(run.getByRole("button", { name: "원본 보기" })).toBeVisible();
  const downloadEvent = page.waitForEvent("download");
  await run.getByRole("button", { name: "배치 JSON 저장" }).click();
  const download = await downloadEvent;
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(chunk);
  const data = JSON.parse(Buffer.concat(chunks).toString());
  expect(data.records).toHaveLength(20);
  expect(data.summary).toMatchObject({ ok: 10, ng: 10 });
  expect(data.records[1].request.recipe.minArea).toBe(20);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "../work/vision-run-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "레시피 설정", exact: true }).click();
  await page.getByLabel("최소 면적", { exact: true }).fill("100");
  await page.getByRole("button", { name: "연속 검사", exact: true }).click();
  await expect(run.getByText(/배치 조건:.*최소 면적 20/)).toBeVisible();
  await run.getByRole("button", { name: "새 배치 시작" }).click();
  await run.getByRole("button", { name: "일시정지", exact: true }).click();
  await expect(run.getByRole("status").first()).toHaveText("일시정지");
  const count = await run.getByTestId("run-count").textContent();
  await page.waitForTimeout(600);
  await expect(run.getByTestId("run-count")).toHaveText(count!);
  await run.getByRole("button", { name: "재개", exact: true }).click();
  await expect(run.getByRole("status").first()).toHaveText("배치 완료", {
    timeout: 15000,
  });
  await expect(run.locator(".run-metrics")).toContainText("100.0%");
  await expect(run.getByText(/오검출 0 · 미검출 1160/)).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    390,
  );
  await page.screenshot({
    path: "../work/vision-run-mobile.png",
    fullPage: true,
  });
});

test("연속 검사 설정 이동과 종료 및 화면 이탈", async ({ page }) => {
  await page.goto("/factory/vision-lab");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.getByRole("button", { name: "연속 검사", exact: true }).click();
  const run = page.getByRole("region", { name: "연속 검사 관제" });
  await run.getByRole("button", { name: "새 배치 시작" }).click();
  await page.getByRole("button", { name: "레시피 설정", exact: true }).click();
  await page.getByRole("button", { name: "연속 검사", exact: true }).click();
  await expect(run.getByRole("status").first()).toHaveText("일시정지");
  await run.getByRole("button", { name: "배치 종료", exact: true }).click();
  const count = await run.getByTestId("run-count").textContent();
  await page.waitForTimeout(700);
  await expect(run.getByTestId("run-count")).toHaveText(count!);
  await expect(run.getByRole("status").first()).toHaveText("종료");
  await page.setViewportSize({ width: 360, height: 800 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    360,
  );
  await run.getByRole("button", { name: "새 배치 시작" }).click();
  await page.getByRole("link", { name: "앱 런처", exact: true }).click();
  await page.goto("/factory/vision-lab");
  await page.getByRole("button", { name: "연속 검사", exact: true }).click();
  await expect(run.getByTestId("run-count")).toHaveText("0 / 20");
  expect(errors).toEqual([]);
});

test("가상 PLC 정상 배치와 검사 타임아웃 복구", async ({ page }) => {
  await page.goto("/factory/vision-lab");
  await page.clock.install();
  await page.getByRole("button", { name: "연속 검사", exact: true }).click();
  const run = page.getByRole("region", { name: "연속 검사 관제" });
  const plc = page.getByRole("region", { name: "가상 PLC 핸드셰이크" });
  await plc.getByRole("checkbox", { name: "PLC 모드 사용" }).check();
  await run.getByLabel("투입 목표 간격").selectOption("200");
  await run.getByRole("button", { name: "새 배치 시작" }).click();
  await page.clock.runFor(5000);
  await expect(run.getByTestId("run-count")).toHaveText("20 / 20");
  await expect(plc.getByTestId("plc-Vision_Ready")).toHaveText(
    "Vision_ReadyON",
  );
  await plc.getByRole("button", { name: "다음 검사 지연 주입" }).click();
  await run.getByRole("button", { name: "새 배치 시작" }).click();
  await page.clock.runFor(350);
  await expect(plc.getByRole("alert")).toContainText("검사 응답 300ms 초과");
  await expect(plc.getByTestId("plc-Interlock")).toContainText("ON");
  await expect(run.getByTestId("run-count")).toHaveText("0 / 20");
  await expect(
    run.getByRole("button", { name: "새 배치 시작" }),
  ).toBeDisabled();
  const event = page.waitForEvent("download");
  await run.getByRole("button", { name: "배치 JSON 저장" }).click();
  const stream = await (await event).createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(chunk);
  const data = JSON.parse(Buffer.concat(chunks).toString());
  expect(data.plc).toMatchObject({
    enabled: true,
    fault: "INSPECTION_TIMEOUT",
  });
  expect(data.plc.events.at(-1).signals.Interlock).toBe(true);
  expect(data.records).toHaveLength(0);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "../work/vision-plc-desktop.png",
    fullPage: true,
  });
  await plc.getByRole("button", { name: "PLC 리셋" }).click();
  await run.getByRole("button", { name: "새 배치 시작" }).click();
  await page.clock.runFor(5000);
  await expect(run.getByTestId("run-count")).toHaveText("20 / 20");
});

test("가상 PLC 확인 누락 래치와 수동 확인 및 취소", async ({ page }) => {
  await page.goto("/factory/vision-lab");
  await page.clock.install();
  await page.getByRole("button", { name: "연속 검사", exact: true }).click();
  const run = page.getByRole("region", { name: "연속 검사 관제" });
  const plc = page.getByRole("region", { name: "가상 PLC 핸드셰이크" });
  await plc.getByRole("checkbox", { name: "PLC 모드 사용" }).check();
  await plc.getByRole("button", { name: "다음 결과 확인 누락" }).click();
  await run.getByRole("button", { name: "새 배치 시작" }).click();
  await page.clock.runFor(1200);
  await expect(plc.getByRole("alert")).toContainText(
    "PLC 결과 확인 1000ms 초과",
  );
  await expect(plc.getByTestId("plc-Inspection_Done")).toContainText("ON");
  await expect(plc.getByTestId("plc-Result_OK")).toContainText("ON");
  await expect(plc.getByTestId("plc-Result_NG")).toContainText("OFF");
  await expect(run.getByTestId("run-count")).toHaveText("0 / 20");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    390,
  );
  await page.screenshot({
    path: "../work/vision-plc-mobile.png",
    fullPage: true,
  });
  await plc.getByRole("button", { name: "PLC 리셋" }).click();
  await plc.getByRole("button", { name: "다음 결과 확인 누락" }).click();
  await run.getByRole("button", { name: "새 배치 시작" }).click();
  await page.clock.runFor(80);
  await plc.getByRole("button", { name: "중복 트리거 주입" }).click();
  await run.getByRole("button", { name: "일시정지", exact: true }).click();
  await plc.getByRole("button", { name: "PLC 결과 확인", exact: true }).click();
  await page.clock.runFor(1500);
  await expect(run.getByTestId("run-count")).toHaveText("1 / 20");
  await expect(plc.getByTestId("plc-Vision_Ready")).toContainText("ON");
  await run.getByRole("button", { name: "재개", exact: true }).click();
  await page.clock.runFor(500);
  await run.getByRole("button", { name: "배치 종료" }).click();
  await page.clock.runFor(1500);
  await expect(run.getByTestId("run-count")).toHaveText("1 / 20");
  await expect(plc.getByTestId("plc-Vision_Busy")).toContainText("OFF");
});

test("C++ 실제 API 단건·배치·PLC와 사용자 참고 문서", async ({ page }) => {
  test.skip(
    !process.env.VISION_NATIVE_E2E,
    "Requires local native preview server",
  );
  await page.route("**/api/v1/core/sessions/current", async (route) => {
    const response = await route.fetch({
      url: "http://127.0.0.1:5187/_test/session",
    });
    await route.fulfill({ response });
  });
  await page.route("**/api/v1/factory/vision/inspect", async (route) => {
    const response = await route.fetch({
      url: "http://127.0.0.1:5187/api/v1/factory/vision/inspect",
    });
    await route.fulfill({ response });
  });
  await page.goto("/factory/vision-lab");
  const single = page.getByRole("region", { name: "C++ 단건 검사" });
  await single
    .getByRole("button", { name: "C++ 단건 검사", exact: true })
    .click();
  await expect(single.getByRole("status")).toContainText("NG");
  await expect(single.getByRole("status")).toContainText("116");
  const downloadEvent = page.waitForEvent("download");
  await single.getByRole("button", { name: "C++ 결과 JSON 저장" }).click();
  const stream = await (await downloadEvent).createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(chunk);
  expect(JSON.parse(Buffer.concat(chunks).toString()).result.source).toBe(
    "synthetic-opencv-cpp-v1",
  );
  await page.getByRole("button", { name: "연속 검사", exact: true }).click();
  const run = page.getByRole("region", { name: "연속 검사 관제" });
  await run.getByLabel("검사 엔진", { exact: true }).selectOption("native");
  await run.getByRole("button", { name: "새 배치 시작" }).click();
  await expect(run.getByTestId("run-count")).toHaveText("20 / 20", {
    timeout: 20000,
  });
  await expect(run.locator(".run-metrics")).toContainText("50.0%");
  await run.getByRole("checkbox", { name: "PLC 모드 사용" }).check();
  await run.getByRole("button", { name: "새 배치 시작" }).click();
  await expect(run.getByTestId("run-count")).toHaveText("20 / 20", {
    timeout: 20000,
  });
  await page.screenshot({
    path: "../work/vision-native-connected.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "검사실 사용 도움말" }).click();
  await expect(
    page.getByRole("heading", {
      name: "합성 비전 검사실 · 연속 검사 · PLC · C++",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("사용자 참고 문서", { exact: true }).first(),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    390,
  );
  await page.screenshot({
    path: "../work/vision-native-help.png",
    fullPage: true,
  });
});
