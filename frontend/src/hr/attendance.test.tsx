// W1b-2 HR: 마감한 달은 고칠 수 없고, 휴가 승인은 부서장을 골라야 한다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
const employees = [
  {
    id: 5,
    employeeCode: "E001",
    name: "홍길동",
    status: "ACTIVE",
    departmentId: 1,
    gradeId: 2,
    dutyId: null,
    workPatternId: 4,
    hireDate: "2026-01-02",
    retireDate: null,
  },
  {
    id: 6,
    employeeCode: "E100",
    name: "김부장",
    status: "ACTIVE",
    departmentId: 1,
    gradeId: 2,
    dutyId: 3,
    workPatternId: 4,
    hireDate: "2026-01-02",
    retireDate: null,
  },
];
const duties = [
  { id: 3, code: "HEAD", name: "부서장", titleKind: "DUTY", isHead: true },
];
const attendance = [
  {
    id: 7,
    employeeId: 5,
    employeeCode: "E001",
    employeeName: "홍길동",
    workDate: "2026-03-02",
    dayKind: "WORKDAY",
    status: "NORMAL",
    clockIn: "09:00:00",
    clockOut: "18:00:00",
    overtimeMinutes: 0,
    nightMinutes: 0,
    holidayMinutes: 0,
    source: "AUTO",
    note: null,
  },
];
const leaveRequest = {
  id: 8,
  requestNo: "LV-20260302-001",
  employeeId: 5,
  leaveKind: "ANNUAL",
  fromDate: "2026-03-02",
  toDate: "2026-03-03",
  days: "2",
  reason: null,
  status: "REQUESTED",
  approverCode: null,
  decidedAt: null,
};

/** closed로 근태 목록의 마감 여부를 바꿔 가며 화면을 띄운다. */
function mockApi(closed: boolean, extra: Record<string, unknown> = {}) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/sessions/current"))
      return new Response(JSON.stringify({ data: session }), { status: 200 });
    if (url.includes("/workspace/modules"))
      return new Response(
        JSON.stringify({
          data: ["core", "hr"].map((moduleKey) => ({
            moduleKey,
            enabled: true,
            updatedAt: null,
          })),
        }),
        { status: 200 },
      );
    const data = url.includes("/hr/attendance?")
      ? attendance
      : url.includes("/hr/employees")
        ? employees
        : url.includes("/hr/titles")
          ? duties
          : url.includes("/hr/leave-requests")
            ? [leaveRequest]
            : [];
    return new Response(
      JSON.stringify({
        data,
        page: { offset: 0, limit: 100, total: data.length },
        closed,
        ...extra,
      }),
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

it("마감하지 않은 달은 근태를 고칠 수 있다", async () => {
  mockApi(false);
  show("/hr/attendance");
  expect(await screen.findByText("2026-03-02")).toBeVisible();
  expect(screen.getByRole("button", { name: "고치기" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "고치기" }));
  expect(await screen.findByLabelText("연장 근무(분)")).toBeVisible();
});

it("마감한 달은 고치기 버튼도 만들기 버튼도 잠근다", async () => {
  mockApi(true);
  show("/hr/attendance");
  expect(await screen.findByText(/마감됨/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "고치기" })).toBeNull();
  expect(screen.getByRole("button", { name: /근태 만들기/ })).toBeDisabled();
});

it("휴가 승인은 부서장을 고르기 전에는 안내만 한다", async () => {
  const fetcher = mockApi(false);
  show("/hr/leaves");
  expect(await screen.findByText("LV-20260302-001")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "승인" }));
  expect(await screen.findByText(/부서장을 먼저 고르세요/)).toBeVisible();
  expect(
    fetcher.mock.calls.filter(([url]) => String(url).includes("/approve")),
  ).toHaveLength(0);

  // 부서장(직책 is_head)만 결재자로 고를 수 있다.
  fireEvent.change(screen.getByLabelText("결재 부서장"), {
    target: { value: "E100" },
  });
  fireEvent.click(screen.getByRole("button", { name: "승인" }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.filter(([url]) => String(url).includes("/approve")),
    ).toHaveLength(1),
  );
  const [, init] = fetcher.mock.calls.find(([url]) =>
    String(url).includes("/approve"),
  )!;
  expect(JSON.parse(String(init?.body))).toEqual({ approverCode: "E100" });
});
