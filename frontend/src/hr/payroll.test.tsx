// W1b-3 HR 급여: 계산 → 검토 → 확정, 확정본은 고치지 않는다. 명세서는 지급·공제를 나눠 보여준다.
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
const draftRun = {
  id: 7,
  payMonth: "2026-03",
  attendanceCloseId: 3,
  payDate: "2026-04-10",
  version: 1,
  status: "draft",
  confirmedAt: null,
};
const slips = [
  {
    id: 11,
    employeeId: 5,
    employeeCode: "E001",
    employeeName: "홍길동",
    departmentCode: "PROD",
    gradeName: "과장",
    grossPay: "2325000",
    deductionTotal: "95625",
    netPay: "2229375",
  },
];
const slipDetail = {
  ...slips[0],
  payMonth: "2026-03",
  payDate: "2026-04-10",
  status: "confirmed",
  version: 1,
  lines: [
    {
      id: 1,
      itemCode: "BASE",
      itemName: "기본급",
      itemKind: "EARNING",
      calcKind: "BASE",
      amount: "2090000",
      basisQuantity: null,
    },
    {
      id: 2,
      itemCode: "OT",
      itemName: "연장수당",
      itemKind: "EARNING",
      calcKind: "OVERTIME",
      amount: "30000",
      basisQuantity: "2.00",
    },
    {
      id: 3,
      itemCode: "PENSION",
      itemName: "국민연금",
      itemKind: "DEDUCTION",
      calcKind: "RATE",
      amount: "95625",
      basisQuantity: "4.5",
    },
  ],
};
const severance = {
  employeeCode: "E001",
  employeeName: "홍길동",
  months: ["2026-03"],
  averageDailyWage: "75000",
  serviceYears: "1.02",
  estimate: "2295000",
};
type Reply = { status: number; body?: unknown };

function mockApi(runs: unknown[], replies: Record<string, Reply> = {}) {
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
      if (url.includes("/hr/severance"))
        return new Response(JSON.stringify({ data: severance }), {
          status: 200,
        });
      if (/\/hr\/payslips\/\d+/.test(url))
        return new Response(JSON.stringify({ data: slipDetail }), {
          status: 200,
        });
      const data = url.includes("/hr/payroll-runs")
        ? runs
        : url.includes("/hr/payslips")
          ? slips
          : [];
      return new Response(
        JSON.stringify({
          data,
          page: { offset: 0, limit: 200, total: data.length },
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

it("작성 중인 실행만 확정할 수 있고 계산 결과를 바로 검토한다", async () => {
  const fetcher = mockApi([draftRun], {
    "POST /api/v1/hr/payroll-runs/7/confirm": {
      status: 200,
      body: { data: { ...draftRun, status: "confirmed" } },
    },
  });
  show("/hr/payroll");
  expect(await screen.findByText("2026-03")).toBeVisible();
  expect(screen.getByText("작성 중")).toBeVisible();
  // 가장 최근 버전의 명세서가 자동으로 펼쳐진다.
  expect(await screen.findByText("2,229,375")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "확정" }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.filter(([url]) => String(url).includes("/confirm")),
    ).toHaveLength(1),
  );
  expect(await screen.findByText(/급여를 확정했습니다/)).toBeVisible();
});

it("확정한 실행에는 확정 버튼이 없다", async () => {
  mockApi([
    { ...draftRun, status: "confirmed", confirmedAt: "2026-04-01T00:00:00Z" },
  ]);
  show("/hr/payroll");
  expect(await screen.findByText("확정")).toBeVisible();
  expect(screen.queryByRole("button", { name: "확정" })).toBeNull();
});

it("명세서는 지급과 공제를 나눠 보여주고 퇴직금 추계를 함께 적는다", async () => {
  mockApi([
    { ...draftRun, status: "confirmed", confirmedAt: "2026-04-01T00:00:00Z" },
  ]);
  show("/hr/payslips");
  fireEvent.click(await screen.findByRole("button", { name: "열기" }));
  expect(await screen.findByText("기본급")).toBeVisible();
  expect(screen.getByText("2.00시간")).toBeVisible(); // 연장 근거
  expect(screen.getByText("4.5%")).toBeVisible(); // 공제 비율
  expect(screen.getByText("국민연금")).toBeVisible();
  expect(screen.getByText(/2,295,000원/)).toBeVisible(); // 퇴직금 추계
});

it("급여 계산은 근태 마감을 먼저 하라고 알린다", async () => {
  mockApi([], {
    "POST /api/v1/hr/payroll-runs": {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "2026-03 근태를 먼저 마감해야 급여를 계산할 수 있습니다.",
          details: { reason: "ATTENDANCE_NOT_CLOSED", month: "2026-03" },
        },
      },
    },
  });
  show("/hr/payroll");
  fireEvent.click(await screen.findByRole("button", { name: /급여 계산$/ }));
  expect(await screen.findByText(/근태를 먼저 마감해야/)).toBeVisible();
});

it("급여 기준은 항목·사원 기준·상여로 나뉜다", async () => {
  mockApi([]);
  show("/hr/pay-standards");
  expect(
    await screen.findByRole("button", { name: "급여 항목" }),
  ).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "상여 규칙" }));
  expect(
    await screen.findByText(/계산 방식이 '상여'인 급여 항목을 먼저 만드세요/),
  ).toBeVisible();
});
