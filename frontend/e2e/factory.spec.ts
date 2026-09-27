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
