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
