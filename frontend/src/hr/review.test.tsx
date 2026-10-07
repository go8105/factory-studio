// W1b-4 HR: 평가는 작성 → 제출 → 평가자 확정, 닫힌 기간은 더 고치지 않는다. 현황·내 정보는 조회만 한다.
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
    hireDate: "2026-03-02",
    retireDate: null,
  },
];
const openCycle = {
  id: 3,
  cycleYear: "2026",
  name: "2026년 평가",
  status: "OPEN",
};
const review = {
  id: 9,
  cycleId: 3,
  cycleYear: "2026",
  employeeId: 5,
  employeeCode: "E001",
  employeeName: "홍길동",
  goals: "불량률 1% 아래로",
  selfComment: null,
  reviewerCode: "E100",
  grade: null,
  reviewerComment: null,
  status: "draft",
  confirmedAt: null,
};
const overview = {
  month: "2026-03",
  headcount: [
    {
      departmentCode: "PROD",
      departmentName: "생산부",
      active: 2,
      onLeave: 0,
      retired: 1,
    },
  ],
  moves: { hires: 2, leavers: 1 },
  attendance: {
    overtimeHours: "3.5",
    nightHours: "1.0",
    holidayHours: "0",
    absentDays: 2,
  },
  leave: { grantedDays: "15.0", usedDays: "3.0", usageRate: "20.0" },
  expiring: [
    {
      employeeCode: "E001",
      employeeName: "홍길동",
      qualKind: "CERT",
      qualName: "지게차운전",
      expiresOn: "2026-10-20",
      expired: false,
    },
  ],
  reviews: [{ cycleYear: "2026", cycleStatus: "OPEN", total: 2, confirmed: 1 }],
};
const me = {
  employee: {
    employeeCode: "E001",
    name: "홍길동",
    status: "ACTIVE",
    hireDate: "2026-03-02",
    departmentCode: "PROD",
    departmentName: "생산부",
    gradeName: "과장",
    dutyName: null,
  },
  month: "2026-03",
  attendance: {
    workedDays: 20,
    absentDays: 0,
    leaveDays: 2,
    overtimeMinutes: 120,
    nightMinutes: 0,
  },
  leave: {
    year: "2026",
    grantedDays: "15.0",
    usedDays: "2.0",
    remainingDays: "13.0",
  },
  payslips: [
    {
      id: 11,
      payMonth: "2026-03",
      payDate: "2026-04-10",
      grossPay: "2312500",
      deductionTotal: "164776",
      netPay: "2147724",
    },
  ],
  reviews: [
    {
      id: 9,
      cycleYear: "2026",
      status: "confirmed",
      grade: "A",
      reviewerCode: "E100",
      reviewerComment: "잘했습니다",
    },
  ],
};
type Reply = { status: number; body?: unknown };

function mockApi(
  data: { cycles?: unknown[]; reviews?: unknown[] } = {},
  replies: Record<string, Reply> = {},
) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input);
      const reply = replies[`${init?.method ?? "GET"} ${url.split("?")[0]}`];
      if (reply)
        return new Response(JSON.stringify(reply.body), {
          status: reply.status,
        });
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
      if (url.includes("/hr/overview"))
        return new Response(JSON.stringify({ data: overview }), {
          status: 200,
        });
      if (url.includes("/hr/me"))
        return new Response(JSON.stringify({ data: me }), { status: 200 });
      const rows = url.includes("/hr/review-cycles")
        ? (data.cycles ?? [openCycle])
        : url.includes("/hr/reviews")
          ? (data.reviews ?? [review])
          : url.includes("/hr/employees")
            ? employees
            : [];
      return new Response(
        JSON.stringify({
          data: rows,
          page: { offset: 0, limit: 20, total: rows.length },
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

it("인사 현황은 인원·연장·연차와 만료 임박 자격을 보여준다", async () => {
  mockApi();
  show("/hr/overview");
  expect(await screen.findByLabelText("재직 인원")).toHaveTextContent("2");
  expect(screen.getByLabelText(/입·퇴사/)).toHaveTextContent("2 / 1");
  expect(screen.getByText("결근 2일")).toBeVisible();
  expect(screen.getByText("지게차운전")).toBeVisible();
  expect(screen.getByText("2026-10-20")).toBeVisible();
});

it("작성 중인 평가는 본인이 저장하고 제출한다", async () => {
  const fetcher = mockApi(
    {},
    {
      "POST /api/v1/hr/reviews/9/submit": {
        status: 200,
        body: { data: { ...review, status: "submitted" } },
      },
    },
  );
  show("/hr/reviews");
  fireEvent.click(await screen.findByRole("button", { name: "열기" }));
  expect(await screen.findByLabelText("자기 평가")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: /제출/ }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.filter(([url]) => String(url).includes("/submit")),
    ).toHaveLength(1),
  );
  expect(await screen.findByText(/평가자가 등급을 매깁니다/)).toBeVisible();
});

it("제출한 평가는 지정된 평가자로 확정한다", async () => {
  const submitted = {
    ...review,
    status: "submitted",
    selfComment: "목표를 넘겼습니다",
  };
  const fetcher = mockApi(
    { reviews: [submitted] },
    {
      "POST /api/v1/hr/reviews/9/confirm": {
        status: 200,
        body: { data: { ...submitted, status: "confirmed", grade: "A" } },
      },
    },
  );
  show("/hr/reviews");
  fireEvent.click(await screen.findByRole("button", { name: "열기" }));
  expect(await screen.findByLabelText("등급")).toBeVisible();
  // 본인 입력 칸은 사라지고 읽기만 된다.
  expect(screen.queryByLabelText("자기 평가")).toBeNull();
  expect(screen.getByText("목표를 넘겼습니다")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "확정" }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.filter(([url]) => String(url).includes("/confirm")),
    ).toHaveLength(1),
  );
  const [, init] = fetcher.mock.calls.find(([url]) =>
    String(url).includes("/confirm"),
  )!;
  expect(JSON.parse(String(init?.body))).toMatchObject({
    reviewerCode: "E100",
    grade: "A",
  });
});

it("닫은 평가 기간에는 추가·수정 버튼이 없다", async () => {
  mockApi({
    cycles: [{ ...openCycle, status: "CLOSED" }],
    reviews: [{ ...review, status: "confirmed", grade: "B" }],
  });
  show("/hr/reviews");
  expect(await screen.findByText(/닫힘/)).toBeVisible();
  expect(screen.getByRole("button", { name: "평가 대상 추가" })).toBeDisabled();
  expect(screen.queryByRole("button", { name: "평가 기간 닫기" })).toBeNull();
  fireEvent.click(await screen.findByRole("button", { name: "열기" }));
  expect(await screen.findByText("불량률 1% 아래로")).toBeVisible();
  expect(screen.queryByLabelText("등급")).toBeNull();
});

it("내 정보는 고른 사원의 잔여 연차·명세서·평가만 보여준다", async () => {
  const fetcher = mockApi();
  show("/hr/me");
  expect(await screen.findByText(/13.0일/)).toBeVisible();
  expect(screen.getByText("2,147,724")).toBeVisible();
  expect(screen.getByRole("combobox", { name: "사원" })).toHaveValue("E001");
  const calls = fetcher.mock.calls.filter(([url]) =>
    String(url).includes("/hr/me"),
  );
  expect(String(calls[0][0])).toContain("employeeCode=E001");
});
