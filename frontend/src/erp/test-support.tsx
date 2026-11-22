import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { App } from "../app/App";
export const partner = {
  id: 1,
  partnerCode: "C-001",
  partnerName: "예시 거래처",
  partnerKind: "CUSTOMER",
  paymentTermDays: 30,
  isActive: true,
};
export const item = {
  id: 2,
  itemCode: "FG-001",
  name: "예시 품목",
  baseUnit: "EA",
  itemType: "finished",
  taxCategory: "TAXABLE",
  isActive: true,
  trackStock: true,
};
export const price = {
  id: 3,
  partnerId: 1,
  itemId: 2,
  priceKind: "SALE",
  unitPrice: "1200.0000",
  currency: "KRW",
  effectiveFrom: "2026-01",
  effectiveTo: null,
  isActive: true,
};
export const department = {
  id: 7,
  code: "D-SALES",
  name: "영업부",
  costCenterKind: "SALES",
  isActive: true,
};
const ROWS: Record<string, unknown[]> = {
  "/partners": [partner],
  "/items": [item],
  "/partner-prices": [price],
  "/accounts": [
    {
      id: 4,
      accountCode: "AR",
      accountName: "외상매출금",
      accountClass: "ASSET",
      normalSide: "DEBIT",
      statementGroup: "유동자산",
      requiresPartner: true,
      requiresDepartment: false,
      isActive: true,
    },
  ],
  "/posting-rules": [
    {
      id: 5,
      transactionKind: "SALE",
      lineNo: 1,
      entrySide: "DEBIT",
      accountCode: "AR",
      amountBasis: "TOTAL",
    },
  ],
  "/conversions": [
    { id: 6, fromUnit: "BOX", toUnit: "EA", factor: "12.000000" },
  ],
  "/departments": [department],
  "/employees": [
    {
      id: 8,
      code: "E-2001",
      name: "박영업",
      departmentId: 7,
      hrEmployeeCode: null,
      isActive: true,
    },
  ],
  "/projects": [
    {
      id: 9,
      code: "PJ-2026A",
      name: "커넥터 라인 증설",
      startOn: "2026-01-02",
      endOn: null,
      isActive: true,
    },
  ],
  "/price-groups": [
    {
      id: 10,
      code: "PG-SALE-A",
      name: "판매 A군",
      priceKind: "SALE",
      isActive: true,
    },
  ],
  "/purchase-requests": [
    {
      id: 30,
      requestNo: "PR-20260924-001",
      requestedOn: "2026-09-24",
      departmentCode: "D-PROD",
      employeeCode: "E-1001",
      source: "MANUAL",
      sourceRef: null,
      status: "confirmed",
      cancelReason: null,
      lines: [
        {
          id: 31,
          lineNo: 1,
          itemId: 2,
          itemCode: "RM-PBT",
          itemName: "PBT 수지",
          quantity: "100.000",
          unit: "KG",
          ordered: false,
        },
      ],
    },
  ],
  "/purchase-orders": [
    {
      id: 40,
      poNo: "PO-SEED-0001",
      orderedOn: "2026-09-04",
      dueOn: "2026-09-19",
      partnerId: 1,
      partnerCode: "V-001",
      partnerName: "공급사 라",
      totalAmount: "385000.00",
      status: "confirmed",
      cancelReason: null,
      lines: [],
      receipt: {
        state: "PARTIAL",
        orderedQty: "100.000",
        receivedQty: "95.000",
        lines: [],
      },
    },
  ],
  "/sales-returns": [
    {
      id: 50,
      returnNo: "SR-20260909-001",
      returnedOn: "2026-09-09",
      partnerCode: "C-003",
      partnerName: "고객 다",
      reason: "외관 불량 반품(합성)",
      totalAmount: "132000.00",
      status: "confirmed",
      cancelReason: null,
      lines: [],
    },
  ],
  "/purchase-returns": [],
  "/journal-entries": [
    {
      id: 60,
      entryNo: "JV-20260909-001",
      entryDate: "2026-09-09",
      entryKind: "SALE",
      status: "confirmed",
      description: "매출 SH-0001",
      sourceRef: "SH-0001",
      reversalOfNo: null,
      reversedByNo: null,
      debitTotal: "3627800.00",
      creditTotal: "3627800.00",
      lines: [
        {
          id: 61,
          lineNo: 1,
          accountId: 4,
          accountCode: "AR",
          accountName: "외상매출금",
          side: "DEBIT",
          amount: "3627800.00",
          partnerCode: "C-001",
          departmentCode: null,
          memo: null,
        },
        {
          id: 62,
          lineNo: 2,
          accountId: 5,
          accountCode: "PRODUCT_SALES",
          accountName: "제품매출",
          side: "CREDIT",
          amount: "3627800.00",
          partnerCode: null,
          departmentCode: null,
          memo: null,
        },
      ],
    },
  ],
  "/unposted": [
    {
      sourceKind: "purchase_invoice",
      entryKind: "PURCHASE",
      sourceId: 77,
      label: "매입",
      ref: "PI-0004",
      entryDate: "2026-09-10",
      amount: "2546500.00",
      reason: "NO_ACCOUNT",
      reasonText: "규칙이 가리키는 계정이 사용 중지됐습니다.",
      postable: false,
    },
  ],
  "/expense-claims": [
    {
      id: 70,
      claimNo: "EC-20260915-001",
      claimedOn: "2026-09-15",
      employeeCode: "E-3001",
      employeeName: "최경리",
      departmentCode: "D-ADMIN",
      payMethod: "BANK",
      totalAmount: "180000.00",
      status: "confirmed",
      cancelReason: null,
      lines: [],
    },
  ],
  "/group-prices": [
    {
      id: 11,
      priceGroupId: 10,
      itemId: 2,
      unitPrice: "860.0000",
      currency: "KRW",
      validFrom: "2026-01-02",
    },
  ],
};
export function mount(
  path: string,
  replies: Record<string, { status: number; body?: unknown }> = {},
) {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input).split("?")[0];
      const method = init?.method ?? "GET";
      if (url.endsWith("/workspace/menus"))
        return new Response(
          JSON.stringify({
            data: { menuIds: [], sidebarMode: "all", version: 1 },
          }),
          { status: 200 },
        );
      const reply = replies[`${method} ${url}`];
      if (reply)
        return new Response(
          reply.status === 204 ? null : JSON.stringify(reply.body),
          { status: reply.status },
        );
      if (url.endsWith("/sessions/current"))
        return new Response(
          JSON.stringify({
            data: {
              actorKind: "GUEST",
              workspaceId: 1,
              generationId: 2,
              roles: ["GUEST"],
              expiresAt: "2099-01-01T00:00:00Z",
              csrfToken: "csrf-test",
            },
          }),
        );
      const data =
        ROWS[Object.keys(ROWS).find((k) => url.endsWith(k)) ?? ""] ?? [];
      return new Response(
        JSON.stringify({
          data,
          page: { offset: 0, limit: 20, total: data.length },
        }),
      );
    });
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  return fetcher;
}
