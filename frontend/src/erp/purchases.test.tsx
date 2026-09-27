// FS-019f E-11 매입 전표 · E-12 매입채무 · E-13 지급·소명. 검증 항목별로 테스트를 나눈다.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";

const E = "/api/v1/erp";
const list = (data: unknown[]) => ({ status: 200, body: { data } });
const raw = {
  id: 7,
  itemCode: "RM-PBT",
  name: "PBT 수지",
  baseUnit: "KG",
  itemType: "raw",
  isActive: true,
};
const invoice = (over: object = {}) => ({
  id: 4,
  invoiceNo: "PI-0009",
  partnerId: 1,
  invoiceDate: "2026-09-20",
  dueDate: null,
  supplyAmount: "0.00",
  taxAmount: "0.00",
  totalAmount: "0.00",
  status: "draft",
  cancelReason: null,
  appliedAmount: "0",
  lines: [],
  cancelBlockedReason: null,
  ...over,
});
const payable = {
  id: 31,
  purchaseInvoiceId: 4,
  partnerId: 1,
  amount: "1100.00",
  appliedAmount: "0.00",
  balance: "1100.00",
  status: "OPEN",
  dueDate: "2026-10-20",
  invoiceDate: "2026-09-20",
  invoiceNo: "PI-0009",
  applications: [],
};
const payment = {
  id: 8,
  paymentNo: "PM-0009",
  partnerId: 1,
  paidOn: "2026-09-24",
  amount: "1100.00",
  status: "confirmed",
  appliedAmount: "0.00",
  unappliedAmount: "1100.00",
  applications: [],
};
const call = (fetcher: ReturnType<typeof mount>, method: string) =>
  fetcher.mock.calls.find(([, i]) => i?.method === method);

it("매입 전표는 구매발주·입고검수 제외 이유를 적는다", async () => {
  mount("/erp/purchase-invoices", { [`GET ${E}/purchase-invoices`]: list([]) });
  expect(
    await screen.findByText(/구매발주·입고검수는 WMS 영역이라/),
  ).toBeVisible();
});

it("작성 중 매입 명세는 원재료만 고르고 단위를 대문자로 보낸다", async () => {
  const fetcher = mount("/erp/purchase-invoices", {
    [`GET ${E}/purchase-invoices`]: list([invoice()]),
    [`GET ${E}/items`]: list([
      raw,
      { ...raw, id: 2, itemCode: "FG-001", itemType: "finished" },
    ]),
    [`PUT ${E}/purchase-invoices/4/lines`]: {
      status: 200,
      body: { data: invoice() },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "명세 0" }));
  fireEvent.click(screen.getByRole("button", { name: "라인 추가" }));
  const options = [
    ...screen.getByLabelText("1번째 품목").querySelectorAll("option"),
  ];
  expect(options.map((o) => o.textContent)).toEqual(["RM-PBT PBT 수지 (KG)"]);
  fireEvent.change(screen.getByLabelText("1번째 수량"), {
    target: { value: "10" },
  });
  fireEvent.change(screen.getByLabelText("1번째 단위"), {
    target: { value: "kg" },
  });
  fireEvent.change(screen.getByLabelText("1번째 단가"), {
    target: { value: "3500" },
  });
  fireEvent.click(screen.getByRole("button", { name: "명세 저장" }));
  await waitFor(() =>
    expect(JSON.parse(String(call(fetcher, "PUT")![1]?.body))).toEqual({
      lines: [{ itemId: 7, quantity: "10", unit: "KG", unitPrice: "3500" }],
    }),
  );
});

it("지급 소명이 있는 매입은 취소 버튼이 꺼지고 이유가 툴팁에 있다", async () => {
  mount("/erp/purchase-invoices", {
    [`GET ${E}/purchase-invoices`]: list([
      invoice({ status: "confirmed", cancelBlockedReason: "PAYMENT_APPLIED" }),
    ]),
  });
  const button = await screen.findByRole("button", { name: "취소" });
  expect(button).toBeDisabled();
  expect(button).toHaveAttribute(
    "title",
    expect.stringContaining("지급 소명이 있어"),
  );
});

it("매입채무 현황은 지급 상태 이름과 전표번호를 쓴다", async () => {
  mount("/erp/payables", { [`GET ${E}/payables`]: list([payable]) });
  const table = await screen.findByRole("table", { name: "매입채무 목록" });
  expect(within(table).getByText("미지급")).toBeVisible();
  expect(within(table).getByText("PI-0009")).toBeVisible();
  expect(screen.getByRole("heading", { name: "매입채무 현황" })).toBeVisible();
});

it("지급 소명은 payableId로 보낸다", async () => {
  const fetcher = mount("/erp/payments", {
    [`GET ${E}/payments`]: list([payment]),
    [`GET ${E}/payables`]: list([payable]),
    [`POST ${E}/payments/8/applications`]: {
      status: 201,
      body: { data: payment },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "소명 0" }));
  expect(
    screen.getByText("지급액 1,100원 = 소명 0원 + 미소명 1,100원"),
  ).toBeVisible();
  fireEvent.change(screen.getByLabelText("PI-0009 소명액"), {
    target: { value: "1100" },
  });
  fireEvent.click(screen.getByRole("button", { name: "소명 저장" }));
  await waitFor(() =>
    expect(JSON.parse(String(call(fetcher, "POST")![1]?.body))).toEqual({
      lines: [{ payableId: 31, amount: "1100" }],
    }),
  );
});

it("지급 등록은 paymentNo·paidOn으로 보낸다", async () => {
  const fetcher = mount("/erp/payments", {
    [`GET ${E}/payments`]: list([]),
    [`GET ${E}/payables`]: list([]),
    [`GET ${E}/partners`]: list([
      {
        id: 5,
        partnerCode: "V-001",
        partnerName: "공급사",
        partnerKind: "SUPPLIER",
        isActive: true,
      },
    ]),
    [`POST ${E}/payments`]: { status: 201, body: { data: payment } },
  });
  fireEvent.click(await screen.findByRole("button", { name: "지급 등록" }));
  const form = await screen.findByRole("form", { name: "지급 등록" });
  fireEvent.change(within(form).getByLabelText("지급번호"), {
    target: { value: "pm-1" },
  });
  fireEvent.change(within(form).getByLabelText("지급액"), {
    target: { value: "500" },
  });
  fireEvent.click(within(form).getByRole("button", { name: "등록" }));
  await waitFor(() =>
    expect(JSON.parse(String(call(fetcher, "POST")![1]?.body))).toMatchObject({
      paymentNo: "PM-1",
      partnerId: 5,
      amount: "500",
      paidOn: expect.any(String),
    }),
  );
});
