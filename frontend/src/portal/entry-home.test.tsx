// FS-017a: P-01/P-02 검증 항목을 개별 테스트로 유지한다.
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
const guest = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const modules = ["core", "mes", "erp", "fems"].map((moduleKey) => ({
  moduleKey,
  enabled: true,
  updatedAt: null,
}));
function reply(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status });
}
function renderEntry() {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
}
it("게스트 진입 응답에 roles가 없어도 런처를 렌더링한다", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = String(input);
    if (path.endsWith("/sessions/current"))
      return reply(
        { error: { code: "SESSION_EXPIRED", message: "세션 없음" } },
        401,
      );
    return reply({ data: path.endsWith("/guest-sessions") ? guest : modules });
  });
  renderEntry();
  fireEvent.click(
    await screen.findByRole("button", { name: /가입 없이 둘러보기/ }),
  );
  expect(
    await screen.findByRole("link", { name: /MES 생산관리/ }),
  ).toBeVisible();
});
it("P-01 게스트 재시도는 같은 멱등 키를 사용한다", async () => {
  let calls = 0;
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input) => {
      if (String(input).endsWith("/sessions/current"))
        return reply(
          { error: { code: "SESSION_EXPIRED", message: "세션 없음" } },
          401,
        );
      calls++;
      return reply(
        { error: { code: "INTERNAL_ERROR", message: "다시 확인" } },
        500,
      );
    });
  renderEntry();
  fireEvent.click(
    await screen.findByRole("button", { name: /가입 없이 둘러보기/ }),
  );
  fireEvent.click(await screen.findByRole("button", { name: "다시 시도" }));
  await waitFor(() => expect(calls).toBe(2));
  const attempts = fetcher.mock.calls.filter(([url]) =>
    String(url).endsWith("/guest-sessions"),
  );
  expect(attempts[0][1]?.headers).toEqual(attempts[1][1]?.headers);
});
it("로그인 폼이 열려 있어도 실패한 게스트 요청을 그대로 재시도한다", async () => {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input) =>
      String(input).endsWith("/sessions/current")
        ? reply(
            { error: { code: "SESSION_EXPIRED", message: "세션 없음" } },
            401,
          )
        : reply(
            { error: { code: "INTERNAL_ERROR", message: "다시 확인" } },
            500,
          ),
    );
  renderEntry();
  fireEvent.click(
    await screen.findByRole("button", { name: "계정이 있다면 로그인" }),
  );
  fireEvent.click(screen.getByRole("button", { name: /가입 없이 둘러보기/ }));
  fireEvent.click(await screen.findByRole("button", { name: "다시 시도" }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.filter(([url]) =>
        String(url).endsWith("/guest-sessions"),
      ),
    ).toHaveLength(2),
  );
});
it("P-01 로그인은 입력한 자격 증명으로 기존 세션 API를 호출한다", async () => {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input) =>
      String(input).endsWith("/sessions/current")
        ? reply(
            { error: { code: "SESSION_EXPIRED", message: "세션 없음" } },
            401,
          )
        : reply(
            { error: { code: "INVALID_CREDENTIALS", message: "로그인 실패" } },
            401,
          ),
    );
  renderEntry();
  fireEvent.click(
    await screen.findByRole("button", { name: "계정이 있다면 로그인" }),
  );
  fireEvent.change(screen.getByLabelText("아이디"), {
    target: { value: "synthetic" },
  });
  fireEvent.change(screen.getByLabelText("비밀번호"), {
    target: { value: "synthetic-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "로그인" }));
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/core/sessions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          loginId: "synthetic",
          password: "synthetic-password",
        }),
      }),
    ),
  );
});
it("P-02 활성 앱은 승인된 기존 솔루션 도움말로 연결한다", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
    reply({
      data: String(input).endsWith("/sessions/current")
        ? { ...guest, roles: ["GUEST"] }
        : modules,
    }),
  );
  render(
    <MemoryRouter initialEntries={["/home"]}>
      <App />
    </MemoryRouter>,
  );
  expect(
    await screen.findByRole("link", { name: /MES 생산관리/ }),
  ).toHaveAttribute("href", "/mes");
});
