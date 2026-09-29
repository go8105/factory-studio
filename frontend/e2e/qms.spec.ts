import { expect, test, type Page } from "@playwright/test";

// FS-023 QMS 실제 API 흐름. 테스트마다 새 게스트 공간(MES·QMS 시드 포함, FS-023c)을 쓴다.
// 시드: FG-C100·C200·T300 게시 기준 v1 + FG-C100 v2 초안, LT-0017(FG-C200) 검사 대기, LT-0016 보류 중.
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("별칭").fill("E2E 평가자");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});

test("시드 초안 기준 게시 · 불량 유형 등록", async ({ page }) => {
  await page.goto("/qms/specs");
  const draft = page
    .getByRole("table", { name: "검사 기준 목록" })
    .getByRole("row", { name: /FG-C100.*v2/ });
  await draft.getByRole("button", { name: "게시" }).click();
  await expect(draft.getByRole("button", { name: "개정" })).toBeVisible();
  await page.goto("/qms/defect-types");
  await page
    .getByRole("button", { name: "불량 유형 등록", exact: true })
    .click();
  await page.getByLabel("코드").fill("BURR");
  await page.getByLabel("이름").fill("버");
  await page.getByRole("button", { name: "등록", exact: true }).click();
  await expect(page.getByRole("cell", { name: "BURR" })).toBeVisible();
});

async function fill(dialog: ReturnType<Page["getByRole"]>, pitch: string) {
  await dialog.getByLabel("합격", { exact: true }).check();
  await dialog.getByLabel("핀 피치 측정값").fill(pitch);
  await dialog.getByLabel("하우징 높이 측정값").fill("12.00");
  await dialog.getByLabel("절연 저항 측정값").fill("300");
}

test("MES LOT 검사 → 불합격 보류 → MES 배지 → 재검사 합격으로 해제", async ({
  page,
}) => {
  const lotNo = "LT-0017";
  await page.goto("/qms/pending");
  await page
    .getByRole("table", { name: "검사 대기 LOT" })
    .getByRole("row", { name: new RegExp(lotNo) })
    .getByRole("button", { name: "검사 시작" })
    .click();
  const dialog = page.getByRole("dialog", { name: new RegExp(lotNo) });
  await fill(dialog, "2.60");
  await expect(dialog.getByText("불합격").first()).toBeVisible();
  await dialog
    .getByLabel("핀 피치 불량 유형")
    .selectOption({ label: "PIN_MISALIGN 핀 정렬 불량" });
  await dialog.getByRole("button", { name: "확정" }).click();
  await expect(page.getByRole("status")).toContainText("품질 보류");

  // D10: MES는 배지만 보이고 패킹을 막지 않는다.
  await page.goto("/mes/lots");
  await expect(
    page.getByRole("row", { name: new RegExp(lotNo) }).getByText("QMS 보류"),
  ).toBeVisible();

  await page.goto("/qms/inspections");
  await page
    .getByRole("row", { name: new RegExp(lotNo) })
    .getByRole("button", { name: "상세" })
    .click();
  await page.getByRole("button", { name: "재검사" }).click();
  const again = page.getByRole("dialog", { name: new RegExp(lotNo) });
  await fill(again, "2.54");
  await again.getByRole("button", { name: "확정" }).click();
  await expect(page.getByRole("status")).toContainText("합격 확정");

  await page.goto("/qms/holds");
  await page
    .getByRole("row", { name: new RegExp(lotNo) })
    .getByRole("button", { name: "상세" })
    .click();
  await page.getByRole("button", { name: "해제 처분" }).click();
  await page.getByRole("button", { name: "해제", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("재검사 합격");
  await page.goto("/mes/lots");
  await expect(
    page.getByRole("row", { name: new RegExp(lotNo) }).getByText("QMS 보류"),
  ).toHaveCount(0);
  // 시드 보류 LT-0016은 그대로 남는다.
  await expect(
    page.getByRole("row", { name: /LT-0016/ }).getByText("QMS 보류"),
  ).toBeVisible();
});

test("MES를 끄면 검사 대기는 직접 입력으로 전환된다", async ({ page }) => {
  await page.goto("/workspace");
  await page.getByRole("switch", { name: "MES 사용" }).click();
  await expect(page.getByRole("switch", { name: "MES 사용" })).toHaveAttribute(
    "aria-checked",
    "false",
  );
  await page.goto("/qms/pending");
  await page.getByRole("button", { name: /직접 입력으로 검사/ }).click();
  await expect(
    page.getByRole("dialog", { name: "직접 입력 검사" }),
  ).toBeVisible();
});
