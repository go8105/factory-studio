import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Users } from "./Users";
const state = vi.hoisted(() => ({
  actor: "MEMBER",
  setBusy: vi.fn(),
  setNavigationBlocked: vi.fn(),
}));
vi.mock("../app/session", () => ({
  useSession: () => ({
    session: { actorKind: state.actor, csrfToken: "synthetic" },
    setBusy: state.setBusy,
    setNavigationBlocked: state.setNavigationBlocked,
  }),
}));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
beforeEach(() => {
  state.actor = "MEMBER";
});
function page() {
  render(
    <MemoryRouter>
      <Users />
    </MemoryRouter>,
  );
}
function fake() {
  const fetch = vi.fn(
    async (url: string) =>
      new Response(
        JSON.stringify({
          data: url.includes("managed-companies")
            ? [{ id: 4, name: "hugh-D Company" }]
            : url.includes("/users?")
              ? [
                  {
                    userId: 2,
                    loginId: "hugh-staff",
                    employeeCode: "HUGH-002",
                    name: "예제 직원",
                    role: "STAFF",
                    active: false,
                  },
                ]
              : { userId: 2 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
  );
  vi.stubGlobal("fetch", fetch);
  return fetch;
}
it("게스트에게 관리자 로그인을 안내하고 사용자 API를 호출하지 않는다", () => {
  state.actor = "GUEST";
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  page();
  expect(
    screen.getByText("관리자 계정으로 로그인해 주세요."),
  ).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});
it("관리 가능한 회사가 없는 직원에게 사용자 추가 폼을 표시하지 않는다", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ data: [] }))),
  );
  page();
  expect(
    await screen.findByText(/관리할 수 있는 회사가 없습니다/),
  ).toBeInTheDocument();
  expect(screen.queryByLabelText("새 비밀번호")).not.toBeInTheDocument();
});
it("관리자 화면에서 준비된 직원 비밀번호를 설정하며 응답 후 입력을 지운다", async () => {
  const fetch = fake();
  page();
  fireEvent.click(await screen.findByRole("button", { name: "계정 관리" }));
  const secret = "Synthetic-ui-password";
  fireEvent.change(screen.getByLabelText("새 비밀번호"), {
    target: { value: secret },
  });
  fireEvent.change(screen.getByLabelText("비밀번호 확인"), {
    target: { value: secret },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "비밀번호 설정·사용 재개" }),
  );
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/hr/work/users/password?companyId=4",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ userId: 2, password: secret }),
      }),
    ),
  );
  expect(screen.getByLabelText("새 비밀번호")).toHaveValue("");
  expect(screen.queryByText(secret)).not.toBeInTheDocument();
});
it("직원 추가 시 회사·사원 코드·권한·연차를 함께 전송한다", async () => {
  const fetch = fake();
  page();
  await screen.findByRole("button", { name: "+ 사용자 추가" });
  for (const [label, value] of [
    ["아이디", "new-user"],
    ["직원 이름", "새 직원"],
    ["사원 코드", "HUGH-003"],
    ["새 비밀번호", "Synthetic-ui-new-user"],
    ["비밀번호 확인", "Synthetic-ui-new-user"],
  ])
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  fireEvent.click(screen.getByRole("button", { name: /^사용자 추가$/ }));
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/hr/work/users?companyId=4",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          loginId: "new-user",
          name: "새 직원",
          employeeCode: "HUGH-003",
          role: "STAFF",
          annualDays: 15,
          password: "Synthetic-ui-new-user",
        }),
      }),
    ),
  );
});

it("총 관리자는 회사가 없어도 첫 회사와 회사 관리자 계정을 등록한다", async () => {
  const fetch = vi.fn(
    async (url: string, init?: RequestInit) =>
      new Response(
        JSON.stringify({
          data: url.includes("management-capabilities")
            ? { isPlatformAdmin: true }
            : url.includes("managed-companies")
              ? []
              : init?.method === "POST"
                ? { companyId: 6 }
                : [],
        }),
      ),
  );
  vi.stubGlobal("fetch", fetch);
  page();
  fireEvent.click(await screen.findByRole("button", { name: /회사 등록/ }));
  fireEvent.change(screen.getByLabelText("회사명"), {
    target: { value: "합성 회사" },
  });
  fireEvent.change(screen.getByLabelText("아이디"), {
    target: { value: "synthetic-owner" },
  });
  fireEvent.change(screen.getByLabelText("직원 이름"), {
    target: { value: "회사 관리자" },
  });
  fireEvent.change(screen.getByLabelText("사원 코드"), {
    target: { value: "OWNER-001" },
  });
  fireEvent.change(screen.getByLabelText("새 비밀번호", { exact: true }), {
    target: { value: "Synthetic-password-123" },
  });
  fireEvent.change(screen.getByLabelText("비밀번호 확인"), {
    target: { value: "Synthetic-password-123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "회사·첫 관리자 등록" }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([url, init]) => url.endsWith("/companies") && init?.method === "POST",
      ),
    ).toBe(true),
  );
});
