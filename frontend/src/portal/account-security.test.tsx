import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { AccountSecurity } from "./AccountSecurity";
const state = vi.hoisted(() => ({
  setSession: vi.fn(),
  setBusy: vi.fn(),
  setNavigationBlocked: vi.fn(),
}));
vi.mock("../app/session", () => ({
  useSession: () => ({ session: { csrfToken: "synthetic-csrf" }, ...state }),
}));
const response = (data: unknown, status = 200) =>
  new Response(JSON.stringify(status < 400 ? { data } : { error: data }), {
    status,
  });
beforeEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});
it("미등록 계정은 비밀번호·설정 키·번호 확인 후 코드 보관 동의를 요구한다", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (url) => {
      const path = String(url);
      if (path.endsWith("/me"))
        return response({ mfaRegistered: false, recoveryCodesRemaining: 0 });
      if (path.endsWith("/start"))
        return response({
          factorId: "11",
          setupKey: "SYNTHETIC-ONLY",
          provisioningUri: "",
          expiresInSeconds: 600,
        });
      return response({
        recoveryCodes: Array.from(
          { length: 8 },
          (_, n) => `SYNTHETIC-CODE-${n}`,
        ),
      });
    });
  render(
    <MemoryRouter>
      <AccountSecurity />
    </MemoryRouter>,
  );
  fireEvent.change(await screen.findByLabelText("현재 비밀번호"), {
    target: { value: "synthetic-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "설정 키 받기" }));
  expect(await screen.findByLabelText("인증 앱 설정 키")).toHaveValue(
    "SYNTHETIC-ONLY",
  );
  fireEvent.change(screen.getByLabelText("인증 앱 번호"), {
    target: { value: "123456" },
  });
  fireEvent.click(screen.getByRole("button", { name: "번호 확인하고 등록" }));
  expect(await screen.findByText("SYNTHETIC-CODE-0")).toBeVisible();
  const go = screen.getByRole("button", { name: "로그인 화면으로" });
  expect(go).toBeDisabled();
  fireEvent.click(screen.getByLabelText("코드 8개를 안전하게 보관했습니다"));
  expect(go).toBeEnabled();
  expect(
    fetch.mock.calls.some(([, options]) =>
      String(options?.body).includes('"factorId":"11"'),
    ),
  ).toBe(true);
});
it("비밀번호 오류 뒤 입력을 유지하고 인증 앱 단계로 넘기지 않는다", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
    String(url).endsWith("/me")
      ? response({ mfaRegistered: false })
      : response(
          { code: "AUTHENTICATION_FAILED", message: "인증 정보를 확인하세요." },
          401,
        ),
  );
  render(
    <MemoryRouter>
      <AccountSecurity />
    </MemoryRouter>,
  );
  const input = await screen.findByLabelText("현재 비밀번호");
  fireEvent.change(input, { target: { value: "synthetic-password" } });
  fireEvent.click(screen.getByRole("button", { name: "설정 키 받기" }));
  expect(await screen.findByText("인증 정보를 확인하세요.")).toBeVisible();
  expect(input).toHaveValue("synthetic-password");
  expect(screen.queryByLabelText("인증 앱 설정 키")).not.toBeInTheDocument();
});
it("복구 화면은 현재 비밀번호 대신 제한 세션의 CSRF로 시작한다", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
    String(url).endsWith("/status")
      ? response({ csrfToken: "restricted-csrf" })
      : response({
          factorId: "12",
          setupKey: "SYNTHETIC-RECOVERY",
          expiresInSeconds: 600,
        }),
  );
  render(
    <MemoryRouter>
      <AccountSecurity recovery />
    </MemoryRouter>,
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "새 설정 키 받기" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("인증 앱 설정 키")).toHaveValue(
      "SYNTHETIC-RECOVERY",
    ),
  );
  expect(screen.queryByLabelText("현재 비밀번호")).not.toBeInTheDocument();
  const call = fetch.mock.calls.find(([url]) =>
    String(url).endsWith("/recovery/start"),
  );
  expect(call?.[1]?.headers).toMatchObject({
    "X-CSRF-Token": "restricted-csrf",
  });
});
