// FS-020f MES 패킹(M-08)·완제품 입고(M-09). 검증 항목별로 테스트를 나눈다.
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
const unit = (
  id: number,
  no: string,
  kind: string,
  status: string,
  extra = {},
) => ({
  id,
  packingNo: no,
  packingKind: kind,
  parentPackingUnitId: null,
  parentPackingNo: null,
  parentStatus: null,
  status,
  displayStatus: status,
  receivedAt: null,
  members: [],
  childIds: [],
  itemId: null,
  unit: null,
  totalQty: "0",
  ...extra,
});
const member = {
  id: 1,
  packingUnitId: 30,
  lotId: 4,
  lotNo: "LT-0016",
  itemId: 1,
  unit: "EA",
  packedQty: "900.000",
};
const units = [
  unit(40, "PL-0007", "PALLET", "open"),
  unit(41, "PL-0008", "PALLET", "closed", {
    itemId: 1,
    unit: "EA",
    totalQty: "1800",
    childIds: [42],
  }),
  unit(42, "BX-0033", "BOX", "closed", {
    parentPackingUnitId: 41,
    parentPackingNo: "PL-0008",
    itemId: 1,
    unit: "EA",
    totalQty: "1800",
  }),
  unit(30, "BX-0031", "BOX", "open", {
    members: [member],
    itemId: 1,
    unit: "EA",
    totalQty: "900",
  }),
  unit(31, "BX-0032", "BOX", "closed", {
    members: [member],
    itemId: 1,
    unit: "EA",
    totalQty: "900",
  }),
  unit(2, "BX-0002", "BOX", "received", {
    parentPackingUnitId: 9,
    parentPackingNo: "PL-0002",
    parentStatus: "received",
    displayStatus: "received",
    itemId: 1,
    unit: "EA",
    totalQty: "985",
  }),
];
const packable = [
  {
    lotId: 4,
    lotNo: "LT-0016",
    itemId: 1,
    unit: "EA",
    orderNo: "WO-0016",
    finalGoodQty: "1921.000",
    packedQty: "900.000",
    remainingQty: "1021.000",
  },
  {
    lotId: 5,
    lotNo: "LT-0017",
    itemId: 2,
    unit: "EA",
    orderNo: "WO-0017",
    finalGoodQty: "1921.000",
    packedQty: "0",
    remainingQty: "1921.000",
  },
];
const items = [
  { id: 1, itemCode: "FG-C100", name: "커넥터" },
  { id: 2, itemCode: "FG-C200", name: "커넥터2" },
];
const receipts = [
  {
    id: 1,
    packingUnitId: 9,
    packingNo: "PL-0002",
    itemId: 1,
    totalQty: "3940",
    receivedAt: "2026-08-22T00:00:00Z",
    unitStatus: "received",
    status: "confirmed",
  },
];
const LISTS: Record<string, unknown> = {
  "/api/v1/mes/packing-units": units,
  "/api/v1/mes/packable-lots": packable,
  "/api/v1/mes/items": items,
  "/api/v1/mes/finished-goods-receipts": receipts,
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
const sent = (fetcher: ReturnType<typeof mockApi>, method: string) =>
  JSON.parse(
    String(fetcher.mock.calls.find(([, i]) => i?.method === method)![1]!.body),
  );
async function openUnit(no: string) {
  const t = await screen.findByRole("table", { name: "포장 목록" });
  fireEvent.click(
    within(
      within(t).getByRole("row", { name: new RegExp(`^${no}`) }),
    ).getByRole("button", { name: "열기" }),
  );
}

it("담을 수 있는 LOT의 최종 양품·담음·잔여를 보여준다", async () => {
  mockApi();
  show("/mes/packing");
  const t = await screen.findByRole("table", { name: "담을 수 있는 LOT" });
  const row = within(t).getByRole("row", { name: /^LT-0016/ });
  expect(row).toHaveTextContent("1,921");
  expect(row).toHaveTextContent("1,021");
});

it("입고된 PALLET의 BOX는 부모 상태로 표시한다", async () => {
  mockApi();
  show("/mes/packing");
  const t = await screen.findByRole("table", { name: "포장 목록" });
  expect(within(t).getByRole("row", { name: /^BX-0002/ })).toHaveTextContent(
    "입고",
  );
});

it("열린 BOX에는 같은 품목 LOT만 고를 수 있고 비우면 잔여 전량을 담는다", async () => {
  const fetcher = mockApi({
    "PUT /api/v1/mes/packing-units/30/members": {
      status: 200,
      body: { data: units[3] },
    },
  });
  show("/mes/packing");
  await openUnit("BX-0031");
  const lot = screen.getByLabelText("LOT");
  expect(lot).toHaveTextContent("LT-0016");
  expect(lot).not.toHaveTextContent("LT-0017");
  fireEvent.click(screen.getByRole("button", { name: "담기" }));
  await waitFor(() =>
    expect(sent(fetcher, "PUT")).toEqual({ lotId: 4, packedQty: "1021" }),
  );
});

it("빼기는 수량 0으로 보낸다", async () => {
  const fetcher = mockApi({
    "PUT /api/v1/mes/packing-units/30/members": {
      status: 200,
      body: { data: units[3] },
    },
  });
  show("/mes/packing");
  await openUnit("BX-0031");
  fireEvent.click(
    within(screen.getByRole("table", { name: "BX-0031 구성" })).getByRole(
      "button",
      { name: "빼기" },
    ),
  );
  await waitFor(() =>
    expect(sent(fetcher, "PUT")).toEqual({ lotId: 4, packedQty: "0" }),
  );
});

it("닫힌 BOX는 열린 PALLET에만 묶는다", async () => {
  const fetcher = mockApi({
    "PUT /api/v1/mes/packing-units/31/parent": {
      status: 200,
      body: { data: units[4] },
    },
  });
  show("/mes/packing");
  await openUnit("BX-0032");
  const pallet = screen.getByLabelText("묶을 PALLET");
  expect(pallet).toHaveTextContent("PL-0007");
  expect(pallet).not.toHaveTextContent("PL-0008");
  fireEvent.click(screen.getByRole("button", { name: "PALLET에 묶기" }));
  await waitFor(() =>
    expect(sent(fetcher, "PUT")).toEqual({ parentPackingUnitId: 40 }),
  );
});

it("양품 초과 오류를 보여준다", async () => {
  mockApi({
    "PUT /api/v1/mes/packing-units/30/members": {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "LOT LT-0016의 담을 수 있는 양품은 1021입니다.",
          details: { reason: "EXCEEDS_GOOD_QTY" },
        },
      },
    },
  });
  show("/mes/packing");
  await openUnit("BX-0031");
  fireEvent.change(screen.getByLabelText("담을 수량"), {
    target: { value: "5000" },
  });
  fireEvent.click(screen.getByRole("button", { name: "담기" }));
  expect(
    await screen.findByText(/담을 수 있는 양품은 1021입니다/),
  ).toBeVisible();
});

it("완제품 입고는 닫힌 PALLET만 입고하고 번호 복사를 제공한다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/mes/finished-goods-receipts": {
      status: 201,
      body: { data: units[1] },
    },
  });
  Object.assign(navigator, {
    clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
  show("/mes/receipts");
  expect(await screen.findByText(/출하 화면에 입고/)).toBeVisible();
  const waiting = await screen.findByRole("table", { name: "입고할 PALLET" });
  expect(within(waiting).getAllByRole("row")).toHaveLength(2);
  fireEvent.click(within(waiting).getByRole("button", { name: "입고" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST")).toEqual({ packingUnitId: 41 }),
  );
  fireEvent.click(screen.getByRole("button", { name: "PL-0002 번호 복사" }));
  await waitFor(() =>
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("PL-0002"),
  );
  expect(
    await screen.findByRole("button", { name: "PL-0002 번호 복사" }),
  ).toHaveTextContent("복사됨");
});
