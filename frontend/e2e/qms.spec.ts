import { expect, test, type Page } from "@playwright/test";

// FS-023b QMS 실제 API 흐름. 테스트마다 새 게스트 공간(MES 시드 포함, QMS 시드 없음)을 쓴다.
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});

async function publishSpec(page: Page) {
  await page.goto("/qms/specs");
  await page.getByRole("button", { name: "기준 만들기", exact: true }).click();
  const item = page.getByLabel("품목 (MES 조회)");
  await item.selectOption({ label: "FG-C100 커넥터 C100" });
  await page.getByRole("button", { name: "만들기", exact: true }).click();
  for (const [name, method] of [
    ["외관", "PASS_FAIL"],
    ["핀 피치", "RANGE"],
  ] as const) {
    await page.getByRole("button", { name: "항목 추가", exact: true }).click();
    await page.getByLabel("항목명").fill(name);
    await page.getByLabel("판정 방식").selectOption(method);
    if (method === "RANGE") {
      await page.getByLabel("하한").fill("2.48");
      await page.getByLabel("상한").fill("2.52");
      await page.getByLabel("단위").fill("mm");
    }
    await page.getByRole("button", { name: "저장", exact: true }).click();
    // 저장이 끝나면 항목 상세로 돌아온다. 그 전에 다음 조작을 하지 않는다.
    await expect(page.getByRole("cell", { name, exact: true })).toBeVisible();
  }
  const items = page.getByRole("dialog", { name: "FG-C100 v1 검사 항목" });
  await items.getByRole("button", { name: "패널 닫기" }).click();
  await expect(items).toBeHidden();
  const row = page
    .getByRole("table", { name: "검사 기준 목록" })
    .getByRole("row", { name: /FG-C100/ });
  await row.getByRole("button", { name: "게시" }).click();
  await expect(row.getByRole("button", { name: "개정" })).toBeVisible();
  await page.goto("/qms/defect-types");
  await page
    .getByRole("button", { name: "불량 유형 등록", exact: true })
    .click();
  await page.getByLabel("코드").fill("DIMENSION");
  await page.getByLabel("이름").fill("치수 불량");
  await page.getByRole("button", { name: "등록", exact: true }).click();
  await expect(page.getByRole("cell", { name: "DIMENSION" })).toBeVisible();
}

test("MES LOT 검사 → 불합격 보류 → MES 배지 → 재검사 합격으로 해제", async ({
  page,
}) => {
  await publishSpec(page);
  await page.goto("/qms/pending");
  const row = page
    .getByRole("table", { name: "검사 대기 LOT" })
    .getByRole("row", { name: /FG-C100/ })
    .filter({ has: page.getByRole("button", { name: "검사 시작" }) })
    .first();
  const lotNo = (await row.getByRole("cell").first().innerText()).trim();
  await row.getByRole("button", { name: "검사 시작" }).click();
  const dialog = page.getByRole("dialog", { name: new RegExp(lotNo) });
  await dialog.getByLabel("합격", { exact: true }).check();
  await dialog.getByLabel("핀 피치 측정값").fill("2.60");
  await expect(dialog.getByText("불합격").first()).toBeVisible();
  await dialog
    .getByLabel("핀 피치 불량 유형")
    .selectOption({ label: "DIMENSION 치수 불량" });
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
  await again.getByLabel("합격", { exact: true }).check();
  await again.getByLabel("핀 피치 측정값").fill("2.50");
  await again.getByRole("button", { name: "확정" }).click();
  await expect(page.getByRole("status")).toContainText("합격 확정");

  await page.goto("/qms/holds");
  await page.getByRole("button", { name: "상세" }).click();
  await page.getByRole("button", { name: "해제 처분" }).click();
  await page.getByRole("button", { name: "해제", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("재검사 합격");
  await page.goto("/mes/lots");
  await expect(
    page.getByRole("row", { name: new RegExp(lotNo) }).getByText("QMS 보류"),
  ).toHaveCount(0);
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
