import { expect, test, type Page } from "@playwright/test";

// FS-028b SPC 실제 API 흐름. SPC 시드는 FS-028c라서 특성·기준 부분군 20개·한계 게시는 API로 준비하고,
// 측정 입력 → 이상 → 조치, MES 끔 안내는 화면으로 확인한다. QMS "SPC 이상" 배지 e2e는 시드 LOT(LT-0017)가 생기는 FS-028c에서 한다.
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("별칭").fill("E2E 평가자");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});

/** 진행 중 공정 실행(LT-0023 FG-C200·ASM)에 기준 부분군 20개를 1시간 간격으로 넣고 한계를 게시한다. */
async function prepare(page: Page): Promise<number> {
  return page.evaluate(async () => {
    const session = await (await fetch("/api/v1/core/sessions/current")).json();
    let n = 0;
    const post = async (path: string, body: unknown) => {
      const r = await fetch(`/api/v1/spc${path}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": session.data.csrfToken,
          "Idempotency-Key": `e2e-${Date.now()}-${n++}`,
        },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`${path} ${r.status} ${await r.text()}`);
      return (await r.json()).data;
    };
    const ch = await post("/characteristics", {
      code: "CH-E2E-ASM",
      itemCode: "FG-C200",
      processCode: "ASM",
      name: "E2E 핀 피치",
      unit: "mm",
      lsl: "2.49",
      usl: "2.59",
    });
    const runs = (
      await (await fetch(`/api/v1/spc/runs?characteristicId=${ch.id}`)).json()
    ).data as { lotNo: string; startedAt: string; endedAt: string | null }[];
    const run = runs.find((r) => !r.endedAt)!;
    const start = Date.parse(run.startedAt);
    for (let i = 0; i < 20; i++) {
      const c = 2.54 + (i % 2 ? 0.001 : -0.001);
      await post("/subgroups", {
        characteristicId: ch.id,
        lotNo: run.lotNo,
        measuredAt: new Date(start + (i + 1) * 3_600_000).toISOString(),
        values: [c - 0.004, c, c + 0.004, c - 0.002, c + 0.002].map((v) =>
          v.toFixed(4),
        ),
      });
    }
    await post(`/characteristics/${ch.id}/limits`, {
      basisFrom: new Date(start).toISOString(),
      basisTo: new Date(start + 24 * 3_600_000).toISOString(),
      reason: "E2E 초기 한계",
    });
    return ch.id as number;
  });
}

test("측정 입력(규격 밖) → 규칙 1 이상 → 이상·조치 → 관리도 판정", async ({
  page,
}) => {
  test.setTimeout(90_000);
  const id = await prepare(page);
  await page.goto(`/spc/measure?c=${id}`);
  await expect(
    page.getByRole("note").filter({ hasText: "MES에서 읽어 옵니다" }),
  ).toBeVisible();
  await page
    .getByRole("row", { name: /진행 중/ })
    .getByRole("button", { name: "측정 입력" })
    .click();
  const form = page.getByRole("dialog", { name: "측정 입력" });
  for (const [i, v] of ["2.571", "2.575", "2.573", "2.579", "2.577"].entries())
    await form.getByLabel(`값 ${i + 1}`).fill(v);
  await expect(form.getByText("X̄ 2.5750 · R 0.0080")).toBeVisible();
  await form.getByRole("button", { name: "기록" }).click();
  await expect(page.getByRole("status")).toContainText("규칙 1 · 한계 밖");
  await page.getByRole("link", { name: /이상·조치 →/ }).click();
  await page.getByRole("button", { name: "상세 · 조치" }).click();
  const detail = page.getByRole("dialog", { name: /X̄ 이상/ });
  await expect(detail).toContainText("관리 상한 또는 하한을 벗어났습니다");
  await detail.getByLabel("원인 분류").selectOption("MACHINE");
  await detail.getByLabel("조치 내용").fill("지그 교체");
  await detail.getByRole("button", { name: "조치 완료" }).click();
  await expect(detail).toContainText("조치 지그 교체");
  await page.goto(`/spc/chart?c=${id}`);
  await expect(
    page.getByRole("link", { name: /규칙 1 · 한계 밖 · 조치 완료/ }),
  ).toBeVisible();
});

test("MES를 끄면 측정 입력만 안내하고 관리도는 그대로", async ({ page }) => {
  test.setTimeout(60_000);
  const id = await prepare(page);
  await page.goto("/workspace");
  await page.getByRole("switch", { name: "MES 사용" }).click();
  await expect(page.getByRole("switch", { name: "MES 사용" })).toHaveAttribute(
    "aria-checked",
    "false",
  );
  await page.goto(`/spc/measure?c=${id}`);
  await expect(
    page.getByText(/MES를 사용하지 않도록 설정했습니다/),
  ).toBeVisible();
  await page.goto(`/spc/chart?c=${id}`);
  await expect(page.getByRole("figure", { name: "X̄ 관리도" })).toBeVisible();
});
