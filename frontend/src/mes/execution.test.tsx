// FS-020d MES LOT 현황(M-04)·공정 실행(M-05). 검증 항목별로 테스트를 나눈다.
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
const step = (
  routeStepId: number,
  sequenceNo: number,
  processId: number,
  extra = {},
) => ({
  routeStepId,
  sequenceNo,
  processId,
  executionId: null,
  equipmentId: null,
  executionStatus: null,
  startedAt: null,
  endedAt: null,
  inputQty: null,
  goodQty: null,
  defectQty: null,
  defectReason: null,
  ...extra,
});
const base = {
  workOrderId: 1,
  itemId: 1,
  planQty: "2000.000",
  routeCode: "RT-C100",
  routeVersion: 1,
  unit: "EA",
  stepCount: 3,
  finalGoodQty: null,
  running: null,
  nextStep: null,
};
const lots = [
  {
    ...base,
    id: 1,
    lotNo: "LT-0025",
    status: "ready",
    completionReason: null,
    orderNo: "WO-0025",
    orderStatus: "released",
    completedSteps: 0,
    nextStep: { ...step(11, 1, 101), inputQty: "2000.000" },
  },
  {
    ...base,
    id: 2,
    lotNo: "LT-0024",
    status: "in_progress",
    completionReason: null,
    orderNo: "WO-0024",
    orderStatus: "in_progress",
    completedSteps: 1,
    running: {
      ...step(12, 2, 102, {
        executionId: 50,
        equipmentId: 8,
        executionStatus: "running",
      }),
      inputQty: "1950.000",
    },
  },
  {
    ...base,
    id: 3,
    lotNo: "LT-0018",
    status: "completed",
    completionReason: "all_defective",
    orderNo: "WO-0018",
    orderStatus: "completed",
    completedSteps: 3,
    finalGoodQty: "0.000",
  },
];
const detail = {
  ...lots[2],
  steps: [
    step(11, 1, 101, {
      executionId: 1,
      equipmentId: 7,
      executionStatus: "completed",
      inputQty: "1000.000",
      goodQty: "0.000",
      defectQty: "1000.000",
      defectReason: "금형 손상",
      materialIssues: [
        { id: 1, materialItemId: 5, issuedQty: "12.240", unit: "KG" },
      ],
    }),
    step(12, 2, 102),
    step(13, 3, 103),
  ],
};
const running = [
  {
    id: 50,
    lotId: 2,
    lotNo: "LT-0024",
    routeStepId: 12,
    sequenceNo: 2,
    processId: 102,
    equipmentId: 8,
    startedAt: "2026-09-24T01:00:00Z",
    unit: "EA",
  },
];
const processes = [
  { id: 101, processCode: "INJ", name: "사출", equipmentIds: [7, 9] },
  { id: 102, processCode: "ASM", name: "조립", equipmentIds: [8] },
  { id: 103, processCode: "INS", name: "검사", equipmentIds: [] },
];
const equipments = [
  {
    id: 7,
    locationId: 1,
    equipmentCode: "INJ-01",
    name: "사출기 1호",
    equipmentType: "INJ",
    isActive: true,
  },
  {
    id: 8,
    locationId: 2,
    equipmentCode: "ASM-01",
    name: "조립기 1호",
    equipmentType: "ASM",
    isActive: true,
  },
  {
    id: 9,
    locationId: 1,
    equipmentCode: "INJ-02",
    name: "사출기 2호",
    equipmentType: "INJ",
    isActive: false,
  },
];
const items = [
  { id: 1, itemCode: "FG-C100", name: "커넥터" },
  { id: 5, itemCode: "RM-PBT", name: "PBT 수지" },
];
const LISTS: Record<string, unknown> = {
  "/api/v1/mes/lots": lots,
  "/api/v1/mes/lots/3": detail,
  "/api/v1/mes/executions": running,
  "/api/v1/mes/processes": processes,
  "/api/v1/mes/equipments": equipments,
  "/api/v1/mes/items": items,
};
type Reply = { status: number; body?: unknown };
function mockApi(replies: Record<string, Reply> = {}) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input).split("?")[0];
      const reply = replies[`${init?.method ?? "GET"} ${url}`];
      if (reply)
        return new Response(JSON.stringify(reply.body), {
          status: reply.status,
        });
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
const body = (fetcher: ReturnType<typeof mockApi>) =>
  JSON.parse(
    String(fetcher.mock.calls.find(([, i]) => i?.method === "POST")![1]!.body),
  );
async function row(table: string, name: RegExp) {
  const t = await screen.findByRole("table", { name: table });
  return within(t).getByRole("row", { name });
}

it("LOT 목록은 진행과 전량 불량 종결을 구분한다", async () => {
  mockApi();
  show("/mes/lots");
  const defective = await row("LOT 목록", /^LT-0018/);
  expect(within(defective).getByText("전량 불량 종결")).toHaveClass(
    "badge",
    "issue",
  );
  expect(defective).toHaveTextContent("3/3");
  expect(await row("LOT 목록", /^LT-0025/)).toHaveTextContent("대기");
});

it("LOT 이력은 공정·설비·실적·투입 자재를 한 표로 보여준다", async () => {
  mockApi();
  show("/mes/lots");
  fireEvent.click(
    within(await row("LOT 목록", /^LT-0018/)).getByRole("button", {
      name: "이력",
    }),
  );
  const table = await screen.findByRole("table", { name: "LT-0018 공정 이력" });
  const first = within(table).getAllByRole("row")[1];
  expect(first).toHaveTextContent("INJ-01");
  expect(first).toHaveTextContent("금형 손상");
  expect(first).toHaveTextContent("RM-PBT 12.24 KG");
  expect(within(table).getAllByText("투입 없음으로 미실행")).toHaveLength(2);
});

it("공정 시작은 허용·사용 중 설비만 보이고 다른 LOT이 쓰는 설비는 고를 수 없다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/mes/lots/1/executions": {
      status: 201,
      body: { data: lots[0] },
    },
  });
  show("/mes/executions");
  fireEvent.click(
    within(await row("시작할 수 있는 LOT", /^LT-0025/)).getByRole("button", {
      name: "시작",
    }),
  );
  const select = screen.getByLabelText("설비");
  expect(select).toHaveTextContent("INJ-01");
  expect(select).not.toHaveTextContent("INJ-02");
  expect(screen.getByText(/투입 2,000 EA \(지시 수량\)/)).toBeVisible();
  fireEvent.click(
    within(screen.getByRole("form", { name: "공정 시작" })).getByRole(
      "button",
      { name: "시작" },
    ),
  );
  await waitFor(() =>
    expect(body(fetcher)).toEqual({ routeStepId: 11, equipmentId: 7 }),
  );
});

it("실적 확정은 서버 투입을 보여주고 양품·불량·사유를 보낸다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/mes/executions/50/result": {
      status: 200,
      body: { data: lots[1] },
    },
  });
  show("/mes/executions");
  fireEvent.click(
    within(await row("실행 중인 공정", /^LT-0024/)).getByRole("button", {
      name: "실적 확정",
    }),
  );
  expect(screen.getByText(/투입 1,950 EA \(직전 공정 양품\)/)).toBeVisible();
  expect(screen.getByText(/QMS 영역으로 범위에서 제외/)).toBeVisible();
  fireEvent.change(screen.getByLabelText("양품"), {
    target: { value: "1940" },
  });
  fireEvent.change(screen.getByLabelText("불량"), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText("불량 사유"), {
    target: { value: "핀 휨" },
  });
  fireEvent.click(screen.getByRole("button", { name: "확정" }));
  await waitFor(() =>
    expect(body(fetcher)).toEqual({
      goodQty: "1940",
      defectQty: "10",
      defectReason: "핀 휨",
    }),
  );
});

it("설비 점유 오류를 보여준다", async () => {
  mockApi({
    "POST /api/v1/mes/lots/1/executions": {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "설비가 LT-0024 공정을 실행 중입니다. 끝난 뒤에 시작하세요.",
          details: { reason: "EQUIPMENT_BUSY" },
        },
      },
    },
  });
  show("/mes/executions");
  fireEvent.click(
    within(await row("시작할 수 있는 LOT", /^LT-0025/)).getByRole("button", {
      name: "시작",
    }),
  );
  fireEvent.click(
    within(screen.getByRole("form", { name: "공정 시작" })).getByRole(
      "button",
      { name: "시작" },
    ),
  );
  expect(await screen.findByText(/LT-0024 공정을 실행 중입니다/)).toBeVisible();
});
