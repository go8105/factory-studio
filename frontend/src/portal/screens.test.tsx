import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const modules = ["core", "mes", "erp", "fems"].map((moduleKey) => ({
  moduleKey,
  enabled: true,
  updatedAt: null,
}));
function mockApi(overrides: Record<string, unknown> = {}) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = String(input).replace("/api/v1/core", "");
    const defaults: Record<string, unknown> = {
      "/sessions/current": session,
      "/workspace/modules": modules,
      "/workspace": {
        id: 10,
        workspaceKind: "GUEST",
        configVersion: 1,
        expiresAt: session.expiresAt,
        createdAt: "2026-09-24",
      },
      "/workspace/generations": { generationId: 21 },
    };
    return new Response(
      JSON.stringify({ data: overrides[path] ?? defaults[path] }),
      { status: 200 },
    );
  });
}
function show(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
it("P-01은 게스트를 주 동선으로 제공한다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        error: { code: "SESSION_EXPIRED", message: "세션 없음" },
      }),
      { status: 401 },
    ),
  );
  show("/");
  expect(
    await screen.findByRole("button", { name: /가입 없이 둘러보기/ }),
  ).toBeVisible();
});
it("P-02는 실제 세션 공간을 표시한다", async () => {
  mockApi();
  show("/home");
  expect(await screen.findByText("공간 10 · 데이터 세대 20")).toBeVisible();
});
it("P-02의 꺼진 앱은 내 공간으로 연결된다", async () => {
  mockApi({
    "/workspace/modules": modules.map((m) => ({
      ...m,
      enabled: m.moduleKey !== "mes",
    })),
  });
  show("/home");
  expect(
    await screen.findByRole("link", { name: /MES 생산관리/ }),
  ).toHaveAttribute("href", "/workspace");
});
it("P-03의 품질검사 노드는 QMS 카드로 연결된다", async () => {
  mockApi();
  show("/flow");
  expect(
    await screen.findByRole("link", { name: /08 \/ QMS/ }),
  ).toHaveAttribute("href", "/cards/qms");
});
it("P-04는 원본 QMS 문안을 표시한다", async () => {
  mockApi();
  show("/cards/qms");
  expect(
    await screen.findByRole("heading", { name: "품질관리 (QMS)" }),
  ).toBeVisible();
});
it("P-04 SCM에는 미확정 본문을 만들지 않는다", async () => {
  mockApi();
  show("/cards/scm");
  await screen.findByRole("heading", { name: "SCM 공급망관리" });
  expect(screen.queryByText("무엇을 하는 시스템인가")).not.toBeInTheDocument();
});
it("P-05는 공통 도움말을 제공한다", async () => {
  mockApi();
  show("/help/common");
  expect(
    await screen.findByRole("heading", { name: "공통 이용 안내" }),
  ).toBeVisible();
});
it("P-06 초기화는 확인 전 요청하지 않는다", async () => {
  const fetcher = mockApi();
  show("/workspace");
  fireEvent.click(
    await screen.findByRole("button", { name: "예시 데이터 초기화" }),
  );
  expect(
    fetcher.mock.calls.some(([url]) =>
      String(url).endsWith("/workspace/generations"),
    ),
  ).toBe(false);
});
it("P-06 모듈 변경은 CSRF·멱등 키를 사용한다", async () => {
  const fetcher = mockApi({
    "/workspace/modules/mes": { moduleKey: "mes", enabled: false },
  });
  show("/workspace");
  fireEvent.click(await screen.findByRole("switch", { name: "MES 사용" }));
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/core/workspace/modules/mes",
      expect.objectContaining({
        method: "PATCH",
        headers: expect.objectContaining({
          "X-CSRF-Token": "test-csrf",
          "Idempotency-Key": expect.any(String),
        }),
      }),
    ),
  );
});
it("P-07 게스트 직접 접근은 404 화면으로 처리한다", async () => {
  mockApi();
  show("/records");
  expect(await screen.findByText("404 · NOT_FOUND")).toBeVisible();
  expect(
    screen.queryByRole("link", { name: "운영 기록" }),
  ).not.toBeInTheDocument();
});
it("P-07 관리자는 실제 감사 기록을 볼 수 있다", async () => {
  mockApi({
    "/sessions/current": { ...session, actorKind: "MEMBER", roles: ["ADMIN"] },
    "/admin/audit-events?offset=0&limit=20": [
      {
        id: 1,
        action: "workspace_module.updated",
        entityKind: "workspace_module",
        actorKind: "GUEST",
        createdAt: "2026-09-24",
      },
    ],
  });
  show("/records");
  expect(
    await screen.findByRole("cell", { name: "workspace_module.updated" }),
  ).toBeVisible();
});
it("만료된 게스트는 만료 안내를 받는다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({ error: { code: "WORKSPACE_EXPIRED", message: "만료" } }),
      { status: 410 },
    ),
  );
  show("/workspace");
  expect(
    await screen.findByRole("heading", {
      name: "게스트 공간 이용이 만료되었습니다",
    }),
  ).toBeVisible();
});
