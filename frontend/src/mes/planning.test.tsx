// FS-020c MES 생산계획(M-02)·작업지시(M-03). 검증 항목별로 테스트를 나눈다.
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
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
const items = [
  {
    id: 1,
    itemCode: "FG-C100",
    name: "커넥터",
    baseUnit: "EA",
    conversions: [],
  },
  {
    id: 2,
    itemCode: "FG-C200",
    name: "커넥터2",
    baseUnit: "EA",
    conversions: [],
  },
];
const line = (id: number, itemId: number, week: string, allocated: string) => ({
  id,
  productionPlanId: 1,
  itemId,
  targetWeek: week,
  planQty: "5000.000",
  unit: "EA",
  allocatedQty: allocated,
  remainingQty: String(5000 - Number(allocated)),
});
const plans = [
  {
    id: 1,
    planCode: "PP-2026-09",
    targetMonth: "2026-09",
    salesPlanCode: "SP-2026-09",
    status: "confirmed",
    lines: [
      line(11, 1, "2026-W39", "4000.000"),
      line(12, 2, "2026-W39", "5000.000"),
    ],
  },
  {
    id: 2,
    planCode: "PP-2026-10",
    targetMonth: "2026-10",
    salesPlanCode: null,
    status: "draft",
    lines: [],
  },
];
const routes = [
  {
    id: 21,
    itemId: 1,
    routeCode: "RT-C100",
    version: 1,
    status: "published",
    steps: [],
  },
  {
    id: 22,
    itemId: 1,
    routeCode: "RT-C100",
    version: 2,
    status: "draft",
    steps: [],
  },
];
const boms = [
  {
    id: 31,
    itemId: 1,
    bomCode: "BOM-C100",
    versionNo: 1,
    status: "published",
    lines: [],
  },
];
const order = (id: number, no: string, status: string, extra = {}) => ({
  id,
  orderNo: no,
  itemId: 1,
  routeVersionId: 21,
  bomVersionId: 31,
  productionPlanLineId: 11,
  planQty: "500.000",
  unit: "EA",
  planStartDate: "2026-09-21",
  planEndDate: "2026-09-23",
  status,
  cancelReason: null,
  lotId: null,
  lotNo: null,
  lotStatus: null,
  ...extra,
});
const orders = [
  order(40, "WO-0031", "draft"),
  order(30, "WO-0030", "released"),
  order(29, "WO-0029", "released", {
    lotId: 7,
    lotNo: "LT-0026",
    lotStatus: "ready",
  }),
];
const LISTS: Record<string, unknown> = {
  "/api/v1/mes/items": items,
  "/api/v1/mes/production-plans": plans,
  "/api/v1/mes/routes": routes,
  "/api/v1/mes/boms": boms,
  "/api/v1/mes/work-orders": orders,
};
type Reply = { status: number; body?: unknown };
function mockApi(replies: Record<string, Reply> = {}) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input).split("?")[0];
      const reply = replies[`${init?.method ?? "GET"} ${url}`];
      if (reply)
        return new Response(
          reply.status === 204 ? null : JSON.stringify(reply.body),
          { status: reply.status },
        );
      const data = url.endsWith("/sessions/current")
        ? session
        : url.endsWith("/workspace/modules")
          ? ["core", "mes", "erp", "fems"].map((moduleKey) => ({
              moduleKey,
              enabled: true,
              updatedAt: null,
            }))
          : (LISTS[url] ?? []);
      return new Response(JSON.stringify({ data }), { status: 200 });
    });
}
function show(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
const body = (fetcher: ReturnType<typeof mockApi>, method: string) =>
  JSON.parse(
    String(
      fetcher.mock.calls.filter(([, i]) => i?.method === method)[0][1]!.body,
    ),
  );
async function row(table: string, name: RegExp) {
  const t = await screen.findByRole("table", { name: table });
  return within(t).getByRole("row", { name });
}

it("확정 계획 라인은 배정·잔여와 지시 만들기 링크를 보여준다", async () => {
  mockApi();
  show("/mes/production-plans");
  fireEvent.click(
    within(await row("생산계획 목록", /^PP-2026-09/)).getByRole("button", {
      name: /라인 2/,
    }),
  );
  const open = await row(
    "PP-2026-09 계획 라인",
    /^2026-W39 지시 만들기 FG-C100/,
  );
  expect(open).toHaveTextContent("4,000");
  expect(open).toHaveTextContent("1,000");
  expect(
    within(open).getByRole("link", { name: "지시 만들기" }),
  ).toHaveAttribute("href", "/mes/work-orders?line=11");
  const full = await row("PP-2026-09 계획 라인", /FG-C200/);
  expect(within(full).queryByRole("link")).toBeNull();
});

it("판매계획 코드가 선택임을 안내하고 빈 값은 null로 보낸다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/mes/production-plans": {
      status: 201,
      body: { data: plans[1] },
    },
  });
  show("/mes/production-plans");
  expect(
    await screen.findByText(/판매계획 코드는 직접 입력합니다/),
  ).toBeVisible();
  const form = await screen.findByRole("form", { name: "생산계획 만들기" });
  fireEvent.change(within(form).getByLabelText("계획 코드"), {
    target: { value: "pp-2026-11" },
  });
  fireEvent.change(within(form).getByLabelText("대상 월"), {
    target: { value: "2026-11" },
  });
  fireEvent.click(within(form).getByRole("button", { name: "만들기" }));
  await waitFor(() =>
    expect(body(fetcher, "POST")).toEqual({
      planCode: "PP-2026-11",
      targetMonth: "2026-11",
      salesPlanCode: null,
    }),
  );
});

it("초안 계획은 라인을 편집해 통째로 저장한다", async () => {
  const fetcher = mockApi({
    "PUT /api/v1/mes/production-plans/2/lines": {
      status: 200,
      body: { data: plans[1] },
    },
  });
  show("/mes/production-plans");
  fireEvent.click(
    within(await row("생산계획 목록", /^PP-2026-10/)).getByRole("button", {
      name: /라인 0/,
    }),
  );
  fireEvent.click(screen.getByRole("button", { name: "라인 추가" }));
  fireEvent.change(screen.getByLabelText("1번째 주차"), {
    target: { value: "2026-W41" },
  });
  fireEvent.change(screen.getByLabelText("1번째 수량"), {
    target: { value: "300" },
  });
  fireEvent.click(screen.getByRole("button", { name: "라인 저장" }));
  await waitFor(() =>
    expect(body(fetcher, "PUT")).toEqual({
      lines: [{ itemId: 1, targetWeek: "2026-W41", planQty: "300" }],
    }),
  );
});

it("지시 등록은 링크로 고른 라인의 잔여와 게시된 경로·BOM을 채운다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/mes/work-orders": { status: 201, body: { data: orders[0] } },
  });
  show("/mes/work-orders?line=11");
  const route = await screen.findByLabelText("공정 경로 (게시된 버전)");
  expect(route).toHaveTextContent("RT-C100 v1");
  expect(route).not.toHaveTextContent("RT-C100 v2");
  expect(screen.getByLabelText("지시 수량")).toHaveValue("1000");
  fireEvent.change(screen.getByLabelText("계획 시작일"), {
    target: { value: "2026-09-28" },
  });
  fireEvent.change(screen.getByLabelText("계획 종료일"), {
    target: { value: "2026-09-30" },
  });
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() =>
    expect(body(fetcher, "POST")).toEqual({
      productionPlanLineId: 11,
      routeVersionId: 21,
      bomVersionId: 31,
      planQty: "1000",
      planStartDate: "2026-09-28",
      planEndDate: "2026-09-30",
    }),
  );
});

it("계획 초과 오류를 보여준다", async () => {
  mockApi({
    "POST /api/v1/mes/work-orders": {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "계획 잔여 수량(1000)을 넘습니다.",
          details: { reason: "PLAN_QTY_EXCEEDED" },
        },
      },
    },
  });
  show("/mes/work-orders?line=11");
  fireEvent.change(await screen.findByLabelText("지시 수량"), {
    target: { value: "2000" },
  });
  fireEvent.change(screen.getByLabelText("계획 시작일"), {
    target: { value: "2026-09-28" },
  });
  fireEvent.change(screen.getByLabelText("계획 종료일"), {
    target: { value: "2026-09-30" },
  });
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  expect(
    await screen.findByText(/계획 잔여 수량\(1000\)을 넘습니다/),
  ).toBeVisible();
});

it("상태별로 발행·수정·취소 또는 LOT 생성만 보여준다", async () => {
  mockApi();
  show("/mes/work-orders");
  const draft = await row("작업지시 목록", /^WO-0031/);
  for (const name of ["발행", "수정", "취소"])
    expect(within(draft).getByRole("button", { name })).toBeVisible();
  const noLot = await row("작업지시 목록", /^WO-0030/);
  expect(within(noLot).getByRole("button", { name: "LOT 생성" })).toBeVisible();
  const withLot = await row("작업지시 목록", /^WO-0029/);
  expect(within(withLot).queryByRole("button")).toBeNull();
  expect(withLot).toHaveTextContent("LT-0026");
});

it("취소는 사유를 받아 보낸다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/mes/work-orders/40/cancel": {
      status: 200,
      body: { data: orders[0] },
    },
  });
  show("/mes/work-orders");
  fireEvent.click(
    within(await row("작업지시 목록", /^WO-0031/)).getByRole("button", {
      name: "취소",
    }),
  );
  fireEvent.change(screen.getByLabelText("취소 사유"), {
    target: { value: "계획 변경" },
  });
  fireEvent.click(screen.getByRole("button", { name: "취소 확정" }));
  await waitFor(() =>
    expect(body(fetcher, "POST")).toEqual({ cancelReason: "계획 변경" }),
  );
});

it("상태 필터로 목록을 좁힌다", async () => {
  mockApi();
  show("/mes/work-orders");
  fireEvent.change(await screen.findByLabelText("상태:"), {
    target: { value: "draft" },
  });
  const table = screen.getByRole("table", { name: "작업지시 목록" });
  expect(within(table).getAllByRole("row")).toHaveLength(2);
});
