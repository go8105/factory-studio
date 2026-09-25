// FS-020g MES 대시보드(M-01). 검증 항목별로 테스트를 나눈다.
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
const dashboard = {
  month: "2026-09",
  openOrders: 11,
  producedQty: "11520.000",
  goodRate: "97.4",
  receivedPallets: 0,
  pipeline: [
    { processId: 101, running: 0, waiting: 2 },
    { processId: 102, running: 2, waiting: 2 },
    { processId: 103, running: 0, waiting: 2 },
  ],
  defectReasons: [{ reason: "MOLD_DAMAGE 금형 손상", defectQty: "980.000" }],
  planVsActual: [
    {
      itemId: 1,
      planQty: "15000.000",
      allocatedQty: "8000.000",
      finalGoodQty: "5763.000",
    },
  ],
  pending: { unconfirmedResults: 2, unpackedLots: 2 },
};
const LISTS: Record<string, unknown> = {
  "/api/v1/mes/processes": [
    { id: 101, processCode: "INJ", name: "사출" },
    { id: 102, processCode: "ASM", name: "조립" },
    { id: 103, processCode: "INS", name: "검사" },
  ],
  "/api/v1/mes/items": [{ id: 1, itemCode: "FG-C100", name: "커넥터" }],
};
function mockApi(data: unknown = dashboard) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const path = url.split("?")[0];
    const body = path.endsWith("/sessions/current")
      ? session
      : path.endsWith("/workspace/modules")
        ? ["core", "mes", "erp", "fems"].map((moduleKey) => ({
            moduleKey,
            enabled: true,
            updatedAt: null,
          }))
        : path.endsWith("/mes/dashboard")
          ? data
          : (LISTS[path] ?? []);
    return new Response(JSON.stringify({ data: body }), { status: 200 });
  });
}
function show() {
  render(
    <MemoryRouter initialEntries={["/mes"]}>
      <App />
    </MemoryRouter>,
  );
}

it("핵심 지표 네 가지를 보여준다", async () => {
  mockApi();
  show();
  expect(await screen.findByLabelText("진행 중 지시")).toHaveTextContent("11");
  expect(screen.getByLabelText("당월 생산")).toHaveTextContent("11,520");
  expect(screen.getByLabelText("양품률")).toHaveTextContent("97.4 %");
  expect(screen.getByLabelText("입고 완료")).toHaveTextContent("0");
});

it("공정별 진행 파이프라인을 공정 순서대로 보여주고 가동률이 없는 이유를 적는다", async () => {
  mockApi();
  show();
  const pipeline = await screen.findByLabelText("공정별 진행 현황");
  const rows = within(pipeline).getAllByRole("listitem");
  expect(rows[1]).toHaveTextContent("2. 조립");
  expect(rows[1]).toHaveTextContent("실행 중 2 · 대기 2 LOT");
  expect(within(pipeline).getByText(/가동률은 설비 상태/)).toBeVisible();
});

it("처리 대기에서 실적·패킹 화면으로 간다", async () => {
  mockApi();
  show();
  const pending = await screen.findByLabelText("처리 대기");
  expect(
    within(pending).getByRole("link", { name: "미확정 실적" }),
  ).toHaveAttribute("href", "/mes/results");
  expect(
    within(pending).getByRole("link", { name: "미패킹 LOT" }),
  ).toHaveAttribute("href", "/mes/packing");
});

it("실적이 없는 달은 양품률을 비워 둔다", async () => {
  mockApi({
    ...dashboard,
    month: "2025-01",
    goodRate: null,
    producedQty: "0",
    defectReasons: [],
    planVsActual: [],
  });
  show();
  expect(await screen.findByText("이달 확정 실적 없음")).toBeVisible();
  expect(screen.getByText("이달 확정된 생산계획이 없습니다.")).toBeVisible();
});

it("조회 월을 바꾸면 그 달로 다시 조회한다", async () => {
  const fetcher = mockApi();
  show();
  fireEvent.change(await screen.findByLabelText("조회 월"), {
    target: { value: "2026-08" },
  });
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(([u]) =>
        String(u).includes("/mes/dashboard?month=2026-08"),
      ),
    ).toBe(true),
  );
});
