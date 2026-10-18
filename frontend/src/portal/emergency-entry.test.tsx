import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { Entry } from "./Entry";
vi.mock("../app/session", () => ({
  useSession: () => ({ session: null, setSession: vi.fn() }),
}));
beforeEach(() => vi.restoreAllMocks());
async function enter() {
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<Entry />} />
        <Route path="/account/recovery" element={<h1>제한된 재등록 화면</h1>} />
      </Routes>
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: "계정이 있다면 로그인" }));
  fireEvent.change(screen.getByLabelText("아이디"), {
    target: { value: "synthetic-admin" },
  });
  fireEvent.change(screen.getByLabelText("비밀번호"), {
    target: { value: "synthetic-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "로그인" }));
  await screen.findByLabelText("인증 앱 번호");
  fireEvent.click(
    screen.getByRole("button", { name: "인증 앱과 복구 코드를 모두 잃었어요" }),
  );
}
const noSession = () =>
  new Response(
    JSON.stringify({
      data: { mfaRequired: true, challengeCsrfToken: "synthetic-challenge" },
    }),
    { status: 202 },
  );
it("운영자 승인 번호는 중간 인증 CSRF와 함께 제출하고 재등록으로 이동한다", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
    String(url).endsWith("/emergency")
      ? new Response(
          JSON.stringify({
            data: { recoveryOnly: true, csrfToken: "restricted" },
          }),
          { status: 201 },
        )
      : noSession(),
  );
  await enter();
  const input = screen.getByLabelText("운영자 승인 번호");
  expect(input).toHaveAttribute("type", "password");
  fireEvent.change(input, { target: { value: "x".repeat(43) } });
  fireEvent.click(screen.getByRole("button", { name: "확인하고 계속" }));
  expect(
    await screen.findByRole("heading", { name: "제한된 재등록 화면" }),
  ).toBeVisible();
  const call = fetch.mock.calls.find(([u]) => String(u).endsWith("/emergency"));
  expect(call?.[1]?.headers).toMatchObject({
    "X-CSRF-Token": "synthetic-challenge",
  });
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({
    grantToken: "x".repeat(43),
  });
});
it("잘못된 파일을 읽으면 승인 번호를 비우고 서버 요청을 추가하지 않는다", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(noSession());
  await enter();
  const file = new File(["{}"], "synthetic-wrong.json", {
    type: "application/json",
  });
  Object.defineProperty(file, "text", { value: async () => "{}" });
  fireEvent.change(screen.getByLabelText("운영자 승인 파일 선택"), {
    target: { files: [file] },
  });
  expect(
    await screen.findByText("서버 운영자가 발급한 승인 파일을 선택하세요."),
  ).toBeVisible();
  expect(screen.getByLabelText("운영자 승인 번호")).toHaveValue("");
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
});
