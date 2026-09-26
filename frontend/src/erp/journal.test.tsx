// FS-019g E-14 분개 미리보기 · 공통 패널. 검증 항목별로 테스트를 나눈다.
import { fireEvent, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";

const E = "/api/v1/erp";
const list = (data: unknown[]) => ({ status: 200, body: { data } });
const salePreview = {
  kind: "SALES",
  id: 3,
  doc: "SH-0001",
  lines: [
    {
      lineNo: 1,
      entrySide: "DEBIT",
      accountCode: "AR",
      accountName: "외상매출금",
      amountBasis: "TOTAL",
      amount: "1100.00",
    },
    {
      lineNo: 2,
      entrySide: "CREDIT",
      accountCode: "PRODUCT_SALES",
      accountName: "제품매출",
      amountBasis: "SUPPLY",
      amount: "1000.00",
    },
    {
      lineNo: 3,
      entrySide: "CREDIT",
      accountCode: "VAT_PAYABLE",
      accountName: "부가세예수금",
      amountBasis: "TAX",
      amount: "100.00",
    },
  ],
  debitTotal: "1100.00",
  creditTotal: "1100.00",
  balanced: true,
  unapplied: null,
};
const sale = {
  id: 3,
  shipmentNo: "SH-0001",
  orderNo: "SO-0001",
  partnerId: 1,
  supplyAmount: "1000.00",
  taxAmount: "100.00",
  totalAmount: "1100.00",
  recognizedAt: "2026-09-01T01:00:00Z",
  cancelledAt: null,
  cancelReason: null,
  dueDate: null,
  appliedAmount: "0",
  taxInvoiceId: null,
  taxInvoiceStatus: null,
  cancelBlockedReason: null,
};

it("독립 화면은 유형·대상을 고르면 분개를 보여 준다", async () => {
  mount("/erp/journal-preview", {
    [`GET ${E}/sales-records`]: list([sale]),
    [`GET ${E}/journal-preview`]: { status: 200, body: { data: salePreview } },
  });
  fireEvent.change(await screen.findByLabelText("대상"), {
    target: { value: "3" },
  });
  const panel = await screen.findByRole("region", { name: "분개 미리보기" });
  expect(await within(panel).findByText("외상매출금 1,100원")).toBeVisible();
  expect(within(panel).getByText("부가세예수금 100원")).toBeVisible();
  expect(
    within(panel).getByText("차변 합계 1,100원 · 대변 합계 1,100원"),
  ).toBeVisible();
  expect(within(panel).getByText(/저장하지 않습니다/)).toBeVisible();
});

it("미소명 잔여는 분개 표 밖에 안내한다", async () => {
  mount("/erp/journal-preview", {
    [`GET ${E}/receipts`]: list([
      {
        id: 9,
        receiptNo: "RC-0002",
        applications: [{ id: 41, amount: "900.00", shipmentNo: "SH-0003" }],
      },
    ]),
    [`GET ${E}/journal-preview`]: {
      status: 200,
      body: {
        data: {
          ...salePreview,
          kind: "RECEIPT",
          doc: "RC-0002",
          lines: [
            {
              lineNo: 1,
              entrySide: "DEBIT",
              accountCode: "BANK",
              accountName: "보통예금",
              amountBasis: "APPLY",
              amount: "900.00",
            },
            {
              lineNo: 2,
              entrySide: "CREDIT",
              accountCode: "AR",
              accountName: "외상매출금",
              amountBasis: "APPLY",
              amount: "900.00",
            },
          ],
          unapplied: "100.00",
        },
      },
    },
  });
  fireEvent.change(await screen.findByLabelText("거래 유형"), {
    target: { value: "RECEIPT" },
  });
  fireEvent.change(screen.getByLabelText("대상"), { target: { value: "41" } });
  expect(
    await screen.findByText(/미소명 잔여 100원은 분개하지 않습니다/),
  ).toBeVisible();
});

it("매출 화면의 분개 버튼은 같은 공통 패널을 연다", async () => {
  const fetcher = mount("/erp/sales-records", {
    [`GET ${E}/sales-records`]: list([sale]),
    [`GET ${E}/journal-preview`]: { status: 200, body: { data: salePreview } },
  });
  fireEvent.click(await screen.findByRole("button", { name: "분개" }));
  expect(await screen.findByText("외상매출금 1,100원")).toBeVisible();
  const url = fetcher.mock.calls
    .map(([u]) => String(u))
    .find((u) => u.includes("journal"));
  expect(url).toContain("kind=SALES&sourceId=3");
});
