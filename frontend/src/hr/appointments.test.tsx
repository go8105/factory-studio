// W1b-1 HR: 사원 등록과 발령(작성 → 확정). 확정해야 사원 정보가 바뀐다(DSN-30 F03).
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
const departments = [{ id: 1, code: "PROD", name: "생산부" }];
const titles = [
  { id: 2, code: "G3", name: "과장", titleKind: "GRADE" },
  { id: 3, code: "HEAD", name: "부서장", titleKind: "DUTY" },
];
const patterns = [{ id: 4, code: "DAY", name: "일근" }];
const employees = [
  {
    id: 5,
    employeeCode: "E001",
    name: "홍길동",
    hireDate: "2026-03-02",
    status: "ACTIVE",
    departmentId: 1,
    gradeId: 2,
    dutyId: null,
    workPatternId: 4,
    retireDate: null,
  },
];
const appointments = [
  {
    id: 6,
    appointmentNo: "AP-20260302-001",
    employeeId: 5,
    kind: "HIRE",
    effectiveDate: "2026-03-02",
    departmentId: 1,
    gradeId: 2,
    dutyId: null,
    reason: "사원 등록",
    status: "draft",
    confirmedAt: null,
  },
];
type Reply = { status: number; body?: unknown } | "network";

function mockApi(replies: Record<string, Reply> = {}) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const reply = replies[`${method} ${url.split("?")[0]}`];
      if (reply === "network") throw new TypeError("network");
      if (reply)
        return new Response(
          reply.status === 204 ? null : JSON.stringify(reply.body),
          {
            status: reply.status,
          },
        );
      const data = url.includes("/sessions/current")
        ? session
        : url.includes("/workspace/modules")
          ? ["core", "hr"].map((moduleKey) => ({
              moduleKey,
              enabled: true,
              updatedAt: null,
            }))
          : url.includes("/hr/departments")
            ? departments
            : url.includes("/hr/titles")
              ? titles
              : url.includes("/hr/work-patterns")
                ? patterns
                : url.includes("/hr/employees")
                  ? employees
                  : url.includes("/hr/appointments")
                    ? appointments
                    : [];
      return new Response(
        JSON.stringify({
          data,
          page: {
            offset: 0,
            limit: 20,
            total: Array.isArray(data) ? data.length : 0,
          },
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
const calls = (
  fetcher: ReturnType<typeof mockApi>,
  method: string,
  part: string,
) =>
  fetcher.mock.calls.filter(
    ([url, init]) =>
      String(url).includes(part) && (init?.method ?? "GET") === method,
  );

it("사원 목록은 부서·직위를 이름으로 보여준다", async () => {
  mockApi();
  show("/hr/employees");
  expect(await screen.findByText("E001")).toBeVisible();
  expect(screen.getByText("생산부")).toBeVisible();
  expect(screen.getByText("과장")).toBeVisible();
});

it("사원 등록은 CSRF·멱등 키와 대문자 코드로 요청한다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/hr/employees": { status: 201, body: { data: employees[0] } },
  });
  show("/hr/employees");
  // 부서·직위·근무 형태를 불러오기 전에는 등록 버튼이 잠겨 있다.
  const open = await screen.findByRole("button", { name: "사원 등록" });
  await waitFor(() => expect(open).toBeEnabled());
  fireEvent.click(open);
  fireEvent.change(await screen.findByLabelText("사원 코드"), {
    target: { value: "e002" },
  });
  fireEvent.change(screen.getByLabelText("이름"), {
    target: { value: "김철수" },
  });
  fireEvent.change(screen.getByLabelText("입사일"), {
    target: { value: "2026-04-01" },
  });
  fireEvent.change(screen.getByLabelText("부서"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("직위"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("근무 형태"), {
    target: { value: "4" },
  });
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() =>
    expect(calls(fetcher, "POST", "/hr/employees")).toHaveLength(1),
  );
  const [, init] = calls(fetcher, "POST", "/hr/employees")[0];
  expect(init?.headers).toMatchObject({
    "X-CSRF-Token": "test-csrf",
    "Idempotency-Key": expect.any(String),
  });
  expect(JSON.parse(String(init?.body))).toMatchObject({
    employeeCode: "E002",
    departmentId: 1,
    gradeId: 2,
    workPatternId: 4,
  });
});

it("작성 중인 발령만 확정·삭제할 수 있다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/hr/appointments/6/confirm": {
      status: 200,
      body: { data: { ...appointments[0], status: "confirmed" } },
    },
  });
  show("/hr/appointments");
  expect(await screen.findByText("AP-20260302-001")).toBeVisible();
  expect(screen.getByText("작성 중")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "확정" }));
  await waitFor(() =>
    expect(calls(fetcher, "POST", "/appointments/6/confirm")).toHaveLength(1),
  );
  expect(await screen.findByText(/발령을 확정했습니다/)).toBeVisible();
});

it("확정한 발령에는 확정·삭제 버튼이 없다", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const data = url.includes("/sessions/current")
      ? session
      : url.includes("/workspace/modules")
        ? [{ moduleKey: "hr", enabled: true, updatedAt: null }]
        : url.includes("/hr/appointments")
          ? [
              {
                ...appointments[0],
                status: "confirmed",
                confirmedAt: "2026-03-02T00:00:00Z",
              },
            ]
          : url.includes("/hr/employees")
            ? employees
            : url.includes("/hr/departments")
              ? departments
              : url.includes("/hr/titles")
                ? titles
                : [];
    return new Response(
      JSON.stringify({ data, page: { offset: 0, limit: 20, total: 1 } }),
      { status: 200 },
    );
  });
  show("/hr/appointments");
  expect(await screen.findByText("확정")).toBeVisible();
  expect(screen.queryByRole("button", { name: "확정" })).toBeNull();
  expect(screen.queryByRole("button", { name: "삭제" })).toBeNull();
});

it("HR을 끈 공간은 내 공간으로 안내한다", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/sessions/current"))
      return new Response(JSON.stringify({ data: session }), { status: 200 });
    if (url.includes("/workspace/modules"))
      return new Response(
        JSON.stringify({
          data: [{ moduleKey: "hr", enabled: false, updatedAt: null }],
        }),
        { status: 200 },
      );
    return new Response(
      JSON.stringify({
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "이 앱은 내 공간에서 사용하지 않도록 설정되어 있습니다.",
          details: { reason: "MODULE_DISABLED", moduleKey: "hr" },
        },
      }),
      { status: 409 },
    );
  });
  show("/hr/employees");
  expect(
    await screen.findByText(/HR을 사용하지 않도록 설정했습니다/),
  ).toBeVisible();
});
