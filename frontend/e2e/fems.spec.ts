import { test, expect } from "@playwright/test";
// FS-018a F-11 실제 API 스모크. 게스트 공간의 시드 에너지원 3종을 사용한다.
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});
test("런처 FEMS에서 에너지원 목록으로 이동", async ({ page }) => {
  await page.getByRole("link", { name: /FEMS 에너지관리/ }).click();
  await expect(page).toHaveURL("/fems/energy-sources");
  await expect(page.getByRole("cell", { name: "도시가스" })).toBeVisible();
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
