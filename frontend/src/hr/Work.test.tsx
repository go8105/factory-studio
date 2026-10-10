import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Work } from "./Work";
const state = vi.hoisted(() => ({
  actor: "GUEST",
  setBusy: vi.fn(),
  setNavigationBlocked: vi.fn(),
}));
vi.mock("../app/session", () => ({
  useSession: () => ({
    session: { actorKind: state.actor, csrfToken: "synthetic-csrf" },
    setBusy: state.setBusy,
    setNavigationBlocked: state.setNavigationBlocked,
  }),
}));
beforeEach(() => {
  state.actor = "GUEST";
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    value: true,
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function page(demo = false) {
  render(
    <MemoryRouter>
      <Work demo={demo} />
    </MemoryRouter>,
  );
}
it("게스트는 실제 회사 API를 호출하지 않고 체험을 안내한다", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  page();
  expect(
    screen.getByRole("link", { name: "합성 데이터로 근무 체험하기" }),
  ).toHaveAttribute("href", "/hr/work-demo");
  expect(fetch).not.toHaveBeenCalled();
});
it("합성 체험에서 직원 신청→관리자 승인 및 시간차 잔여를 확인한다", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  page(true);
  fireEvent.change(screen.getByLabelText("시작일"), {
    target: { value: "2026-10-12" },
  });
  fireEvent.change(screen.getByLabelText("사유"), {
    target: { value: "예제 시간차" },
  });
  fireEvent.click(screen.getByRole("button", { name: "신청하기" }));
  expect(
    screen.getByText(/예제 직원 · 시간차 · 승인 대기/),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("체험 역할"), {
    target: { value: "ADMIN" },
  });
  fireEvent.click(screen.getByRole("button", { name: "승인", exact: true }));
  expect(screen.getByText("119시간")).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});
it("회원은 서버 회사 연결로 출근하고 오프라인 제출은 차단한다", async () => {
  state.actor = "MEMBER";
  const company = {
    id: 4,
    name: "hugh-D Company",
    isExample: true,
    timezone: "Asia/Seoul",
  };
  const data = {
    company,
    person: { id: 2, name: "예제 직원", role: "STAFF" },
    remainingMinutes: 7200,
    activeSession: null,
    sessions: [],
    requests: [],
    events: [],
    policy: { daily_minutes: 480, annual_days: 15 },
    closed: false,
  };
  const fetch = vi.fn(
    async (url: string) =>
      new Response(
        JSON.stringify({
          data: url.endsWith("companies")
            ? [company]
            : url.includes("overview")
              ? data
              : { id: 1 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
  );
  vi.stubGlobal("fetch", fetch);
  page();
  const clock = await screen.findByRole("button", { name: "출근하기" });
  await waitFor(() => expect(clock).toBeEnabled());
  fireEvent.click(clock);
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/hr/work/clock/clock-in?companyId=4",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  await waitFor(() => expect(clock).toBeEnabled());
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    value: false,
  });
  fireEvent(window, new Event("offline"));
  expect(clock).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent("오프라인");
});
