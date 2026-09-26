// FS-019c E-05 출하지시 · E-06 출하. 검증 항목별로 테스트를 나눈다.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";

const E = "/api/v1/erp";
const list = (data: unknown[]) => ({ status: 200, body: { data } });
const order = {
  id: 5,
  orderNo: "SO-0005",
  partnerId: 1,
  orderedOn: "2026-09-10",
  dueOn: "2026-09-30",
  status: "shipping",
  quotationId: null,
  quoteNo: null,
  quoteRevisionNo: null,
  shipmentOrderCount: 1,
  totalAmount: "12000",
  lines: [
    {
      id: 51,
      lineNo: 1,
      itemId: 2,
      orderQty: "10.000",
      unit: "EA",
      unitPrice: "1200.0000",
      amount: "12000",
      instructedQty: "6.000",
      shippedQty: "0",
    },
  ],
};
const shipOrder = (status = "open") => ({
  id: 9,
  shipOrderNo: "SH-O-0009",
  salesOrderId: 5,
  orderNo: "SO-0005",
  partnerId: 1,
  orderedOn: "2026-09-20",
  status,
  cancelReason: null,
  shipmentId: null,
  shipmentNo: null,
  lines: [
    {
      id: 91,
      salesOrderLineId: 51,
      orderQty: "6.000",
      lineNo: 1,
      itemId: 2,
      unit: "EA",
    },
  ],
});
const postBody = (fetcher: ReturnType<typeof mount>) => {
  const call = fetcher.mock.calls.find(([, init]) => init?.method === "POST")!;
  return { url: String(call[0]), body: JSON.parse(String(call[1]?.body)) };
};

it("출하지시 기본 수량은 남은 수량이다", async () => {
  const fetcher = mount("/erp/shipment-orders", {
    [`GET ${E}/shipment-orders`]: list([]),
    [`GET ${E}/sales-orders`]: list([order]),
    [`POST ${E}/shipment-orders`]: { status: 201, body: { data: shipOrder() } },
  });
  const form = await screen.findByRole("form", { name: "출하지시 만들기" });
  fireEvent.change(within(form).getByLabelText("출하지시번호"), {
    target: { value: "sh-o-9" },
  });
  fireEvent.change(within(form).getByLabelText("수주"), {
    target: { value: "5" },
  });
  expect(within(form).getByLabelText("1행 지시 수량")).toHaveValue("4");
  fireEvent.click(within(form).getByRole("button", { name: "출하지시" }));
  await waitFor(() =>
    expect(postBody(fetcher).body.lines).toEqual([
      { salesOrderLineId: 51, orderQty: "4" },
    ]),
  );
  expect(postBody(fetcher).body.shipOrderNo).toBe("SH-O-9");
});

it("미출하 지시 취소는 사유가 있어야 한다", async () => {
  mount("/erp/shipment-orders", {
    [`GET ${E}/shipment-orders`]: list([shipOrder()]),
    [`GET ${E}/sales-orders`]: list([order]),
  });
  fireEvent.click(await screen.findByRole("button", { name: "명세 1" }));
  const cancel = screen.getByRole("button", { name: "지시 취소" });
  expect(cancel).toBeDisabled();
  fireEvent.change(screen.getByLabelText("취소 사유"), {
    target: { value: "변경" },
  });
  expect(cancel).toBeEnabled();
});

it("출하 완료 지시는 취소 버튼이 없다", async () => {
  mount("/erp/shipment-orders", {
    [`GET ${E}/shipment-orders`]: list([shipOrder("shipped")]),
    [`GET ${E}/sales-orders`]: list([order]),
  });
  fireEvent.click(await screen.findByRole("button", { name: "명세 1" }));
  expect(screen.queryByRole("button", { name: "지시 취소" })).toBeNull();
});

it("출하 화면은 패킹번호 수기 입력 이유를 적는다", async () => {
  mount("/erp/shipments", {
    [`GET ${E}/shipments`]: list([]),
    [`GET ${E}/shipment-orders`]: list([shipOrder()]),
  });
  expect(await screen.findByText(/패킹번호는 직접 입력합니다/)).toBeVisible();
});

it("출하 확정은 패킹번호만 보내고 빈 값은 null이다", async () => {
  const fetcher = mount("/erp/shipments", {
    [`GET ${E}/shipments`]: list([]),
    [`GET ${E}/shipment-orders`]: list([shipOrder()]),
    [`POST ${E}/shipments`]: { status: 201, body: { data: {} } },
  });
  const form = await screen.findByRole("form", { name: "출하 확정" });
  fireEvent.change(within(form).getByLabelText("출하번호"), {
    target: { value: "sh-9" },
  });
  fireEvent.change(within(form).getByLabelText("출하지시"), {
    target: { value: "9" },
  });
  expect(within(form).getByText("6 EA")).toBeVisible();
  fireEvent.click(within(form).getByRole("button", { name: "출하 확정" }));
  await waitFor(() =>
    expect(postBody(fetcher).body).toEqual({
      shipmentNo: "SH-9",
      shipmentOrderId: 9,
      lines: [{ shipmentOrderLineId: 91, packingNo: null }],
    }),
  );
});

it("출하 명세는 인식된 매출 금액을 보여 준다", async () => {
  mount("/erp/shipments", {
    [`GET ${E}/shipments`]: list([
      {
        id: 1,
        shipmentNo: "SH-0001",
        shipmentOrderId: 9,
        shipOrderNo: "SH-O-0009",
        orderNo: "SO-0005",
        partnerId: 1,
        shippedAt: "2026-09-20T01:00:00Z",
        salesRecordId: 3,
        supplyAmount: "7200.00",
        taxAmount: "720.00",
        totalAmount: "7920.00",
        lines: [
          {
            id: 1,
            shipmentOrderLineId: 91,
            packingNo: "PL-1",
            shippedQty: "6.000",
            itemId: 2,
            shippedUom: "EA",
          },
        ],
      },
    ]),
    [`GET ${E}/shipment-orders`]: list([]),
  });
  fireEvent.click(await screen.findByRole("button", { name: "명세 1" }));
  expect(
    screen.getByText(/공급가액 7,200원 · 세액 720원 · 합계 7,920원/),
  ).toBeVisible();
  expect(screen.getByText("PL-1")).toBeVisible();
});
