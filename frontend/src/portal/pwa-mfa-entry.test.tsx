import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { Entry } from "./Entry";
vi.mock("../app/session", () => ({
  useSession: () => ({ session: null, setSession: vi.fn() }),
}));
afterEach(() => vi.unstubAllGlobals());
it("설치된 PWA의 MFA 로그인도 내 근무로 돌아간다", async () => {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: true,
      media: "(display-mode: standalone)",
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  );
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (url) =>
      new Response(
        JSON.stringify({
          data: String(url).endsWith("/sessions")
            ? { mfaRequired: true, challengeCsrfToken: "synthetic-challenge" }
            : {
                actorKind: "MEMBER",
                workspaceId: 1,
                generationId: 2,
                roles: [],
                csrfToken: "synthetic-csrf",
                expiresAt: null,
              },
        }),
        { status: String(url).endsWith("/sessions") ? 202 : 201 },
      ),
  );
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<Entry />} />
        <Route path="/hr/work" element={<h1>근무 진입 확인</h1>} />
      </Routes>
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: "계정이 있다면 로그인" }));
  fireEvent.change(screen.getByLabelText("아이디"), {
    target: { value: "synthetic-user" },
  });
  fireEvent.change(screen.getByLabelText("비밀번호"), {
    target: { value: "synthetic-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "로그인" }));
  fireEvent.change(await screen.findByLabelText("인증 앱 번호"), {
    target: { value: "123456" },
  });
  fireEvent.click(screen.getByRole("button", { name: "확인하고 계속" }));
  expect(
    await screen.findByRole("heading", { name: "근무 진입 확인" }),
  ).toBeVisible();
});
