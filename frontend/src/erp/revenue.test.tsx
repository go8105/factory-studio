// FS-019d E-07 매출 · E-08 세금계산서. 검증 항목별로 테스트를 나눈다.
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";

const E = "/api/v1/erp";
const list = (data: unknown[]) => ({ status: 200, body: { data } });
const sale = (over: object = {}) => ({
  id: 3,
  shipmentNo: "SH-0002",
  orderNo: "SO-0002",
  partnerId: 1,
  supplyAmount: "1000.00",
  taxAmount: "100.00",
  totalAmount: "1100.00",
  recognizedAt: "2026-09-01T01:00:00Z",
  cancelledAt: null,
  cancelReason: null,
  dueDate: null,
  appliedAmount: "0",
  taxInvoiceId: 8,
  taxInvoiceStatus: "pending",
  cancelBlockedReason: null,
  ...over,
});
const invoice = (over: object = {}) => ({
  id: 8,
  salesRecordId: 3,
  partnerId: 1,
  status: "pending",
  approvalNo: null,
  issuedOn: null,
  totalAmount: "1100.00",
  recognizedAt: "2026-09-01T01:00:00Z",
  shipmentNo: "SH-0002",
  ...over,
});
const postBody = (fetcher: ReturnType<typeof mount>) => {
  const call = fetcher.mock.calls.find(([, init]) => init?.method === "POST")!;
  return { url: String(call[0]), body: JSON.parse(String(call[1]?.body)) };
};

it("취소가 막힌 매출은 버튼을 비활성화하고 이유를 툴팁에 쓴다", async () => {
  mount("/erp/sales-records", {
    [`GET ${E}/sales-records`]: list([
      sale({ cancelBlockedReason: "RECEIPT_APPLIED" }),
    ]),
  });
  const button = await screen.findByRole("button", { name: "취소" });
  expect(button).toBeDisabled();
  expect(button).toHaveAttribute(
    "title",
    expect.stringContaining("수금 소명이 있어"),
  );
});

it("발급대기 계산서가 있으면 함께 삭제됨을 알린다", async () => {
  const fetcher = mount("/erp/sales-records", {
    [`GET ${E}/sales-records`]: list([sale()]),
    [`POST ${E}/sales-records/3/cancel`]: {
      status: 200,
      body: { data: sale() },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "취소" }));
  expect(
    screen.getByText(/발급대기 세금계산서도 함께 삭제됩니다/),
  ).toBeVisible();
  const confirm = screen.getByRole("button", { name: "매출 취소 확정" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("취소 사유"), {
    target: { value: "반품" },
  });
  fireEvent.click(confirm);
  await waitFor(() =>
    expect(postBody(fetcher).body).toEqual({ reason: "반품" }),
  );
});

it("취소된 매출은 사유와 함께 표시한다", async () => {
  mount("/erp/sales-records", {
    [`GET ${E}/sales-records`]: list([
      sale({
        cancelledAt: "2026-09-02T00:00:00Z",
        cancelReason: "반품",
        cancelBlockedReason: "ALREADY_CANCELLED",
      }),
    ]),
  });
  expect(await screen.findByText("취소 · 반품")).toBeVisible();
});

it("세금계산서 화면은 전자세금계산서 연동 제외를 명시한다", async () => {
  mount("/erp/tax-invoices", {
    [`GET ${E}/tax-invoices`]: list([]),
    [`GET ${E}/sales-records`]: list([]),
  });
  expect(
    await screen.findByText(/전자세금계산서 연동이 필요하며 1차 범위에서/),
  ).toBeVisible();
});

it("0원·취소·계산서 있는 매출은 발급 대상에서 뺀다", async () => {
  mount("/erp/tax-invoices", {
    [`GET ${E}/tax-invoices`]: list([]),
    [`GET ${E}/sales-records`]: list([
      sale({
        id: 1,
        shipmentNo: "SH-A",
        taxInvoiceId: null,
        taxInvoiceStatus: null,
      }),
      sale({
        id: 2,
        shipmentNo: "SH-ZERO",
        totalAmount: "0.00",
        taxInvoiceId: null,
        taxInvoiceStatus: null,
      }),
      sale({
        id: 4,
        shipmentNo: "SH-C",
        cancelledAt: "x",
        taxInvoiceId: null,
        taxInvoiceStatus: null,
      }),
      sale({ id: 5, shipmentNo: "SH-I" }),
    ]),
  });
  fireEvent.click(await screen.findByRole("button", { name: "계산서 만들기" }));
  const select = await screen.findByLabelText("매출");
  const options = [...select.querySelectorAll("option")].map(
    (o) => o.textContent,
  );
  expect(options).toHaveLength(2);
  expect(options[1]).toContain("SH-A");
});

it("발급은 승인번호와 발급일을 보낸다", async () => {
  const fetcher = mount("/erp/tax-invoices", {
    [`GET ${E}/tax-invoices`]: list([invoice()]),
    [`GET ${E}/sales-records`]: list([]),
    [`POST ${E}/tax-invoices/8/issue`]: {
      status: 200,
      body: { data: invoice({ status: "issued" }) },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "발급" }));
  fireEvent.change(screen.getByLabelText("승인번호"), {
    target: { value: " A-1 " },
  });
  fireEvent.change(screen.getByLabelText("발급일"), {
    target: { value: "2026-09-24" },
  });
  fireEvent.click(screen.getByRole("button", { name: "발급완료로 기록" }));
  await waitFor(() =>
    expect(postBody(fetcher).body).toEqual({
      approvalNo: "A-1",
      issuedOn: "2026-09-24",
    }),
  );
});

it("발급완료 계산서는 발급 버튼이 없다", async () => {
  mount("/erp/tax-invoices", {
    [`GET ${E}/tax-invoices`]: list([
      invoice({ status: "issued", approvalNo: "A-1", issuedOn: "2026-09-24" }),
    ]),
    [`GET ${E}/sales-records`]: list([]),
  });
  expect(await screen.findByText("A-1")).toBeVisible();
  expect(screen.queryByRole("button", { name: "발급" })).toBeNull();
});
