import { expect, test, type Page } from "@playwright/test";
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("별칭").fill("GW 평가자");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home", { timeout: 15000 });
});
async function prepare(page: Page) {
  return page.evaluate(async () => {
    const session = (
      await (await fetch("/api/v1/core/sessions/current")).json()
    ).data;
    const post = async (path: string, body: unknown) => {
      const r = await fetch("/api/v1/gw" + path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": session.csrfToken,
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(await r.text());
      return (await r.json()).data;
    };
    const staff = await post("/people", {
      code: "STAFF",
      name: "구매담당",
      jobRole: "STAFF",
    });
    const team = await post("/people", {
      code: "TEAM",
      name: "팀장",
      jobRole: "MANAGER",
    });
    const board = await post("/people", {
      code: "BOARD",
      name: "게시운영",
      jobRole: "BOARD_ADMIN",
    });
    const route = await post("/routes", {
      code: "TEAM-LINE",
      name: "팀장 결재선",
      steps: [{ personId: team.id }],
    });
    return { staff, team, board, route };
  });
}
async function confirm(page: Page) {
  await page.getByRole("button", { name: "확정", exact: true }).click();
}
async function createGeneral(page: Page) {
  await page.getByRole("button", { name: "새 기안", exact: true }).click();
  await page.getByLabel("제목", { exact: true }).fill("비품 구매 검토");
  await page.getByLabel("본문", { exact: true }).fill("합성 기안 본문");
  await page
    .getByLabel("결재선", { exact: true })
    .selectOption({ label: "팀장 결재선" });
  await page.getByRole("button", { name: "초안 저장", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: /비품 구매 검토/ }),
  ).toBeVisible();
}

test("G-01~07: UI master creation, draft, role switch, approval and audit", async ({
  page,
}) => {
  await page.getByRole("link", { name: /GW 그룹웨어/ }).click();
  await page.getByRole("link", { name: "체험 담당자 먼저 등록" }).click();
  for (const [code, name, role] of [
    ["STAFF", "구매담당", "STAFF"],
    ["TEAM", "팀장", "MANAGER"],
  ]) {
    await page.getByRole("button", { name: "등록", exact: true }).click();
    await page.getByLabel("코드", { exact: true }).fill(code);
    await page.getByLabel("이름", { exact: true }).fill(name);
    await page.getByLabel("직무", { exact: true }).selectOption(role);
    await page.getByRole("button", { name: "저장", exact: true }).click();
    await expect(page.getByRole("cell", { name, exact: true })).toBeVisible();
  }
  await page.goto("/gw/routes");
  await page.getByRole("button", { name: "등록", exact: true }).click();
  await page.getByLabel("코드", { exact: true }).fill("TEAM-LINE");
  await page.getByLabel("이름", { exact: true }).fill("팀장 결재선");
  await page
    .getByLabel("1단계 담당자", { exact: true })
    .selectOption({ label: "팀장" });
  await page.getByRole("button", { name: "저장", exact: true }).click();
  await expect(page.getByRole("cell", { name: "팀장 결재선" })).toBeVisible();
  await page.goto("/gw/drafts");
  await page
    .getByLabel("담당자 역할 체험")
    .selectOption({ label: "구매담당 · 담당자" });
  await createGeneral(page);
  await page.getByRole("button", { name: "상신", exact: true }).click();
  await confirm(page);
  await expect(
    page.getByRole("heading", { name: /비품 구매 검토 결재 진행/ }),
  ).toBeVisible();
  await page
    .getByLabel("담당자 역할 체험")
    .selectOption({ label: "팀장 · 팀장" });
  await page.getByRole("button", { name: "승인", exact: true }).click();
  await confirm(page);
  await expect(
    page.getByRole("heading", { name: /비품 구매 검토 승인/ }),
  ).toBeVisible();
  await expect(page.getByRole("table", { name: "사건 이력" })).toContainText(
    "상신",
  );
  await page.goto("/gw/dashboard");
  await expect(page.getByRole("heading", { name: "업무 현황" })).toBeVisible();
  await page.goto("/gw/pending");
  await expect(page.getByRole("heading", { name: "결재함" })).toBeVisible();
});

test("rejection/resubmission keeps history and retry after lost approval response", async ({
  page,
}) => {
  const { staff, team } = await prepare(page);
  await page.goto("/gw/drafts");
  await page.getByLabel("담당자 역할 체험").selectOption(staff.id);
  await createGeneral(page);
  await page.getByRole("button", { name: "상신", exact: true }).click();
  await confirm(page);
  await page.getByLabel("담당자 역할 체험").selectOption(team.id);
  await page.getByRole("button", { name: "반려", exact: true }).click();
  await page.getByLabel("처리 사유").fill("견적 보완 필요");
  await confirm(page);
  await expect(
    page.getByRole("heading", { name: /비품 구매 검토 반려/ }),
  ).toBeVisible();
  await page.getByLabel("담당자 역할 체험").selectOption(staff.id);
  await page.getByRole("button", { name: "새 초안으로 재상신 준비" }).click();
  await confirm(page);
  await expect(page.getByText(/2회차/)).toBeVisible();
  await page.getByRole("button", { name: "상신", exact: true }).click();
  await confirm(page);
  await page.getByLabel("담당자 역할 체험").selectOption(team.id);
  let lost = true;
  await page.route("**/api/v1/gw/documents/*/approve", async (route) => {
    if (lost) {
      lost = false;
      await route.fetch();
      await route.abort();
    } else await route.continue();
  });
  await page.getByRole("button", { name: "승인", exact: true }).click();
  await confirm(page);
  await expect(page.getByText(/응답을 확인하지 못했습니다/)).toBeVisible();
  await confirm(page);
  await expect(
    page.getByRole("heading", { name: /비품 구매 검토 승인/ }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("table", { name: "사건 이력" })
      .getByRole("cell", { name: "승인", exact: true }),
  ).toHaveCount(1);
});

test("ERP snapshot selection, approval badge and source off", async ({
  page,
}) => {
  const { staff, team } = await prepare(page);
  await page.goto("/gw/drafts");
  await page.getByLabel("담당자 역할 체험").selectOption(staff.id);
  await page.getByRole("button", { name: "새 기안", exact: true }).click();
  await page.getByLabel("문서 종류").selectOption("ERP_PURCHASE");
  await page.getByRole("button", { name: "선택 PI-0001", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: /고정된 ERP 원문/ }),
  ).toBeVisible();
  await page.getByLabel("제목", { exact: true }).fill("ERP 매입 검토");
  await page.getByLabel("본문", { exact: true }).fill("상신 당시 매입 검토");
  await page
    .getByLabel("결재선", { exact: true })
    .selectOption({ label: "팀장 결재선" });
  await page.getByRole("button", { name: "초안 저장", exact: true }).click();
  await page.getByRole("button", { name: "상신", exact: true }).click();
  await confirm(page);
  await page.getByLabel("담당자 역할 체험").selectOption(team.id);
  await page.getByRole("button", { name: "승인", exact: true }).click();
  await confirm(page);
  await page.goto("/erp/purchase-invoices");
  await page
    .getByRole("row")
    .filter({ hasText: "PI-0001" })
    .getByRole("button", { name: /명세/ })
    .click();
  await expect(
    page.getByRole("heading", { name: "GW 결재", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /GW-000001/ })).toBeVisible();
  await page.evaluate(async () => {
    const session = (
      await (await fetch("/api/v1/core/sessions/current")).json()
    ).data;
    const response = await fetch("/api/v1/core/workspace/modules/erp", {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrfToken,
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ enabled: false }),
    });
    if (!response.ok) throw new Error(await response.text());
  });
  await page.goto("/gw/drafts");
  await page.getByLabel("담당자 역할 체험").selectOption(staff.id);
  await page.getByRole("button", { name: "새 기안", exact: true }).click();
  await page.getByLabel("문서 종류").selectOption("ERP_PURCHASE");
  await expect(
    page.getByText("ERP가 꺼져 있어 원문 조회가 불가능합니다."),
  ).toBeVisible();
});

test("mobile bulletin publish/correct/withdraw uses plain text", async ({
  page,
}) => {
  const { board } = await prepare(page);
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto("/gw/board");
  await page.getByLabel("담당자 역할 체험").selectOption(board.id);
  await page.getByRole("button", { name: "새 글", exact: true }).click();
  await page
    .getByLabel("게시판", { exact: true })
    .last()
    .selectOption("NOTICE");
  await page.getByLabel("제목", { exact: true }).fill("합성 공지");
  await page
    .getByLabel("본문", { exact: true })
    .fill("<script>window.gwInjected=true</script>");
  await page.getByRole("button", { name: "초안 저장", exact: true }).click();
  await page.getByRole("button", { name: "게시", exact: true }).click();
  await confirm(page);
  await expect(
    page.getByText("<script>window.gwInjected=true</script>", { exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => "gwInjected" in window)).toBe(false);
  await page.getByRole("button", { name: "정정 글 작성", exact: true }).click();
  await confirm(page);
  await expect(page.getByRole("link", { name: "이전 글" })).toBeVisible();
  await page.getByRole("button", { name: "게시", exact: true }).click();
  await confirm(page);
  await page.getByRole("button", { name: "철회·회수", exact: true }).click();
  await page.getByLabel("철회 사유").fill("공지 철회");
  await confirm(page);
  await expect(page.getByText("철회 사유: 공지 철회")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../work/fs030b/mobile-board.png",
    fullPage: true,
  });
});

test("role changes protect unsaved text and Escape preserves input", async ({
  page,
}) => {
  const { staff, team } = await prepare(page);
  await page.goto("/gw/drafts");
  await page.getByLabel("담당자 역할 체험").selectOption(staff.id);
  await page.getByRole("button", { name: "새 기안", exact: true }).click();
  await page.getByLabel("제목", { exact: true }).fill("작성 중인 내용");
  await page.getByLabel("담당자 역할 체험").selectOption(team.id);
  await expect(page.getByText("저장하지 않은 변경이 있습니다.")).toBeVisible();
  await page.getByRole("button", { name: "계속 편집" }).click();
  await expect(page.getByLabel("제목", { exact: true })).toHaveValue(
    "작성 중인 내용",
  );
  await page.getByLabel("제목", { exact: true }).focus();
  await page.keyboard.press("Escape");
  await expect(page.getByText("저장하지 않은 변경이 있습니다.")).toBeVisible();
  await page.getByRole("button", { name: "계속 편집" }).click();
  await page.getByLabel("담당자 역할 체험").selectOption(team.id);
  await page.getByRole("button", { name: "변경 버리기" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByLabel("담당자 역할 체험")).toHaveValue(team.id);
});
