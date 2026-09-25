// FS-020e MES 자재 투입(M-06)·실적 확정(M-07). 검증 항목별로 테스트를 나눈다.
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
const running = [
  {
    id: 50,
    lotId: 2,
    lotNo: "LT-0027",
    routeStepId: 11,
    sequenceNo: 1,
    processId: 101,
    equipmentId: 7,
    startedAt: "2026-09-24T01:00:00Z",
    unit: "EA",
  },
];
const lots = [
  {
    id: 2,
    lotNo: "LT-0027",
    status: "in_progress",
    completionReason: null,
    workOrderId: 1,
    orderNo: "WO-0031",
    itemId: 1,
    planQty: "2000.000",
    orderStatus: "in_progress",
    routeCode: "RT-C100",
    routeVersion: 1,
    unit: "EA",
    stepCount: 3,
    completedSteps: 0,
    finalGoodQty: null,
    running: {
      routeStepId: 11,
      sequenceNo: 1,
      processId: 101,
      inputQty: "2000.000",
    },
    nextStep: null,
  },
];
const items = [
  {
    id: 1,
    itemCode: "FG-C100",
    name: "커넥터",
    baseUnit: "EA",
    conversions: [],
  },
  {
    id: 5,
    itemCode: "RM-PBT",
    name: "PBT 수지",
    baseUnit: "KG",
    conversions: [],
  },
  {
    id: 6,
    itemCode: "RM-PIN",
    name: "단자 핀",
    baseUnit: "EA",
    conversions: [{ fromUnit: "BOX" }],
  },
];
const requirement = [
  {
    materialItemId: 5,
    unit: "KG",
    qtyPerUnit: "0.012",
    lossRate: "2.00",
    requiredQty: "24.480",
    issuedQty: "0",
    suggestedQty: "24.480",
  },
  {
    materialItemId: 6,
    unit: "EA",
    qtyPerUnit: "4.000",
    lossRate: "0.50",
    requiredQty: "8040",
    issuedQty: "8040.000",
    suggestedQty: "0",
  },
];
const results = [
  {
    id: 1,
    lotNo: "LT-0018",
    completionReason: "all_defective",
    sequenceNo: 3,
    processId: 103,
    equipmentId: 9,
    inputQty: "980.000",
    goodQty: "0.000",
    defectQty: "980.000",
    unit: "EA",
    defectReason: "금형 손상",
    confirmedAt: "2026-09-20T00:00:00Z",
  },
  {
    id: 2,
    lotNo: "LT-0001",
    completionReason: "normal",
    sequenceNo: 1,
    processId: 101,
    equipmentId: 7,
    inputQty: "2000.000",
    goodQty: "2000.000",
    defectQty: "0.000",
    unit: "EA",
    defectReason: null,
    confirmedAt: "2026-09-01T00:00:00Z",
  },
];
const processes = [
  { id: 101, name: "사출", equipmentIds: [7] },
  { id: 103, name: "검사", equipmentIds: [9] },
];
const equipments = [
  {
    id: 7,
    equipmentCode: "INJ-01",
    name: "사출기",
    isActive: true,
    locationId: 1,
    equipmentType: "INJ",
  },
  {
    id: 9,
    equipmentCode: "INS-01",
    name: "검사기",
    isActive: true,
    locationId: 1,
    equipmentType: "INS",
  },
];
type Reply = { status: number; body?: unknown };
function mockApi(
  replies: Record<string, Reply> = {},
  lists: Record<string, unknown> = {},
) {
  const LISTS: Record<string, unknown> = {
    "/api/v1/mes/executions": running,
    "/api/v1/mes/lots": lots,
    "/api/v1/mes/items": items,
    "/api/v1/mes/processes": processes,
    "/api/v1/mes/equipments": equipments,
    "/api/v1/mes/results": results,
    "/api/v1/mes/executions/50/bom-requirement": requirement,
    "/api/v1/mes/executions/50/material-issues": [],
    ...lists,
  };
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
async function openIssue() {
  const t = await screen.findByRole("table", { name: "실행 중인 공정" });
  fireEvent.click(
    within(within(t).getByRole("row", { name: /^LT-0027/ })).getByRole(
      "button",
      { name: "투입" },
    ),
  );
}

it("자재 투입은 재고 차감 없음을 안내한다", async () => {
  mockApi();
  show("/mes/material-issues");
  expect(await screen.findByText(/재고를 차감하지 않습니다/)).toBeVisible();
});

it("BOM 기준 소요량과 제안량을 보여주고 제안량으로 투입한다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/mes/executions/50/material-issues": {
      status: 201,
      body: { data: {} },
    },
  });
  show("/mes/material-issues");
  await openIssue();
  const table = await screen.findByRole("table", { name: "BOM 기준 소요량" });
  expect(within(table).getByRole("row", { name: /RM-PIN/ })).toHaveTextContent(
    "투입 완료",
  );
  fireEvent.click(
    within(within(table).getByRole("row", { name: /RM-PBT/ })).getByRole(
      "button",
      { name: "제안량 채우기" },
    ),
  );
  expect(screen.getByLabelText("투입 수량")).toHaveValue("24.48");
  fireEvent.click(screen.getByRole("button", { name: "투입 기록" }));
  await waitFor(() =>
    expect(body(fetcher)).toEqual({
      materialItemId: 5,
      materialLotId: null,
      issuedQty: "24.48",
      unit: "KG",
    }),
  );
});

it("BOM 없는 지시는 기준 소요량이 없다고 알린다", async () => {
  mockApi({}, { "/api/v1/mes/executions/50/bom-requirement": [] });
  show("/mes/material-issues");
  await openIssue();
  expect(
    await screen.findByText(/BOM 없이 발행된 지시라 기준 소요량이 없습니다/),
  ).toBeVisible();
});

it("단위는 자재의 기준·환산 단위만 고른다", async () => {
  mockApi();
  show("/mes/material-issues");
  await openIssue();
  await screen.findByRole("form", { name: "자재 투입 등록" });
  fireEvent.change(screen.getByLabelText("자재"), { target: { value: "6" } });
  const unit = screen.getByLabelText("단위");
  expect(
    [...unit.querySelectorAll("option")].map((o) => o.textContent),
  ).toEqual(["EA", "BOX"]);
});

it("중복 투입 오류를 보여준다", async () => {
  mockApi({
    "POST /api/v1/mes/executions/50/material-issues": {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "이 공정에 같은 자재(같은 LOT)의 투입 기록이 이미 있습니다.",
          details: { reason: "DUPLICATE_ISSUE" },
        },
      },
    },
  });
  show("/mes/material-issues");
  await openIssue();
  await screen.findByRole("form", { name: "자재 투입 등록" });
  fireEvent.change(screen.getByLabelText("투입 수량"), {
    target: { value: "1" },
  });
  fireEvent.click(screen.getByRole("button", { name: "투입 기록" }));
  expect(await screen.findByText(/투입 기록이 이미 있습니다/)).toBeVisible();
});

it("실적 확정 화면은 전량 불량을 배지로 보여주고 불량만 거를 수 있다", async () => {
  mockApi();
  show("/mes/results");
  const table = await screen.findByRole("table", { name: "확정된 실적" });
  expect(within(table).getByText("전량 불량 980")).toHaveClass(
    "badge",
    "issue",
  );
  expect(within(table).getByText(/100\.0% · 금형 손상/)).toBeVisible();
  fireEvent.click(screen.getByRole("checkbox", { name: "불량이 있는 실적만" }));
  expect(within(table).getAllByRole("row")).toHaveLength(2);
});

it("실적 확정 화면에서도 같은 폼으로 확정한다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/mes/executions/50/result": {
      status: 200,
      body: { data: lots[0] },
    },
  });
  show("/mes/results");
  const t = await screen.findByRole("table", { name: "확정을 기다리는 공정" });
  fireEvent.click(within(t).getByRole("button", { name: "실적 확정" }));
  expect(screen.getByText(/투입 2,000 EA \(지시 수량\)/)).toBeVisible();
  fireEvent.change(screen.getByLabelText("양품"), {
    target: { value: "2000" },
  });
  fireEvent.click(screen.getByRole("button", { name: "확정" }));
  await waitFor(() =>
    expect(body(fetcher)).toEqual({
      goodQty: "2000",
      defectQty: "0",
      defectReason: null,
    }),
  );
});
