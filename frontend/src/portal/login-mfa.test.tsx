import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
it("202 인증 요청은 업무 세션으로 취급하지 않고 번호와 복구 경로를 표시한다", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input) => {
      const path = String(input);
      if (path.endsWith("/sessions/current"))
        return new Response(
          JSON.stringify({
            error: { code: "SESSION_EXPIRED", message: "로그인 필요" },
          }),
          { status: 401 },
        );
      if (path.endsWith("/sessions"))
        return new Response(
          JSON.stringify({
            data: {
              mfaRequired: true,
              challengeCsrfToken: "synthetic-challenge",
            },
          }),
          { status: 202 },
        );
      return new Response(
        JSON.stringify({
          error: {
            code: "AUTHENTICATION_FAILED",
            message: "인증 번호를 확인하세요.",
          },
        }),
        { status: 401 },
      );
    });
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "계정이 있다면 로그인" }),
  );
  fireEvent.change(screen.getByLabelText("아이디"), {
    target: { value: "synthetic-user" },
  });
  fireEvent.change(screen.getByLabelText("비밀번호"), {
    target: { value: "synthetic-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "로그인" }));
  expect(await screen.findByLabelText("인증 앱 번호")).toBeVisible();
  expect(screen.queryByText("앱 런처")).not.toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: "휴대폰을 사용할 수 없어요" }),
  );
  const recovery = screen.getByLabelText("복구 코드");
  fireEvent.change(recovery, { target: { value: "a".repeat(32) } });
  fireEvent.click(screen.getByRole("button", { name: "확인하고 계속" }));
  expect(await screen.findByText("인증 번호를 확인하세요.")).toBeVisible();
  expect(recovery).toHaveValue("a".repeat(32));
  const call = fetch.mock.calls.find(([path]) =>
    String(path).endsWith("/login/verify"),
  );
  expect(call?.[1]?.headers).toMatchObject({
    "X-CSRF-Token": "synthetic-challenge",
  });
});
