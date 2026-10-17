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
import { examplePolicy } from "./workPolicy";
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
  fireEvent.click(screen.getByRole("button", { name: /^승인$/ }));
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
    policy: examplePolicy,
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

it("체험 시간차도 선택한 두 시간을 차감한다", () => {
  page(true);
  fireEvent.change(screen.getByLabelText("종료 시간"), {
    target: { value: "11:00" },
  });
  fireEvent.change(screen.getByLabelText("사유"), {
    target: { value: "합성 두 시간" },
  });
  fireEvent.click(screen.getByRole("button", { name: "신청하기" }));
  expect(screen.getByText(/차감 2시간/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("체험 역할"), {
    target: { value: "ADMIN" },
  });
  fireEvent.click(screen.getByRole("button", { name: /^승인$/ }));
  expect(screen.getByText("118시간")).toBeInTheDocument();
});

it("관리자 정정에서 원래 출퇴근의 초·밀리초를 보존한다", async () => {
  state.actor = "MEMBER";
  const company = {
    id: 4,
    name: "hugh-D Company",
    isExample: true,
    timezone: "Asia/Seoul",
  };
  const data = {
    company,
    person: { id: 1, name: "예제 관리자", role: "ADMIN" },
    remainingMinutes: 7200,
    activeSession: null,
    sessions: [
      {
        id: 8,
        employee_id: 2,
        employeeName: "예제 직원",
        work_date: "2026-10-10",
        clock_in: "2026-10-10T01:22:03.123Z",
        clock_out: "2026-10-10T01:22:04.456Z",
      },
    ],
    requests: [],
    events: [],
    policy: examplePolicy,
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
              : { id: 8 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
  );
  vi.stubGlobal("fetch", fetch);
  page();
  fireEvent.click(await screen.findByRole("button", { name: "기록 정정" }));
  fireEvent.change(screen.getByLabelText("정정 사유"), {
    target: { value: "합성 기록 확인" },
  });
  fireEvent.click(screen.getByRole("button", { name: "이력 남기고 정정" }));
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/hr/work/corrections?companyId=4",
      expect.objectContaining({
        body: JSON.stringify({
          id: 8,
          clockIn: "2026-10-10T10:22:03.123+09:00",
          clockOut: "2026-10-10T10:22:04.456+09:00",
          reason: "합성 기록 확인",
        }),
      }),
    ),
  );
});

it("회사별 근무표를 표시하고 연차·반차·분 단위 시간차를 제출한다", async () => {
  state.actor = "MEMBER";
  const company = {
    id: 4,
    name: "합성 정책 회사",
    isExample: true,
    timezone: "Asia/Seoul",
  };
  const data = {
    company,
    person: { id: 2, name: "합성 직원", role: "STAFF" },
    remainingMinutes: 6300,
    activeSession: null,
    sessions: [],
    requests: [],
    events: [],
    closed: false,
    policy: {
      start_time: "08:30:00",
      end_time: "16:30:00",
      break_start: "11:30:00",
      break_end: "12:30:00",
      daily_minutes: 420,
      annual_days: 20,
    },
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
        { status: 200 },
      ),
  );
  vi.stubGlobal("fetch", fetch);
  page();
  expect(
    await screen.findByText(/회사 기준 1일 7시간 · 연차 기준 20일/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/08:30–16:30 · 휴게 11:30–12:30/),
  ).toBeInTheDocument();
  expect(screen.getByText(/잔여 15일/)).toBeInTheDocument();
  expect(
    screen.getByText(/오전 반차 08:30–13:00, 오후 반차 13:00–16:30/),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("시작일"), {
    target: { value: "2026-10-19" },
  });
  fireEvent.change(screen.getByLabelText("사유"), {
    target: { value: "합성 정책 검증" },
  });
  for (const [kind, start, end] of [
    ["ANNUAL", "08:30", "16:30"],
    ["HALF_AM", "08:30", "13:00"],
    ["HALF_PM", "13:00", "16:30"],
    ["HOURLY", "08:30", "09:30"],
  ]) {
    fireEvent.change(screen.getByLabelText("종류"), {
      target: { value: kind },
    });
    if (kind === "HOURLY") {
      expect(screen.getByLabelText("시작 시간")).toHaveValue("08:30");
      expect(screen.getByLabelText("종료 시간")).toHaveValue("09:30");
      expect(screen.getByLabelText("시작 시간")).toHaveAttribute("step", "60");
    }
    fireEvent.click(screen.getByRole("button", { name: "신청하기" }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/hr/work/requests?companyId=4",
        expect.objectContaining({
          body: JSON.stringify({
            kind,
            startsAt: `2026-10-19T${start}:00+09:00`,
            endsAt: `2026-10-19T${end}:00+09:00`,
            reason: "합성 정책 검증",
            destination: null,
          }),
        }),
      ),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "신청하기" })).toBeEnabled(),
    );
  }
  fireEvent.change(screen.getByLabelText("종료 시간"), {
    target: { value: "09:00" },
  });
  const before = fetch.mock.calls.length;
  fireEvent.click(screen.getByRole("button", { name: "신청하기" }));
  expect(screen.getByRole("status")).toHaveTextContent("1시간 단위");
  expect(fetch.mock.calls).toHaveLength(before);
});
