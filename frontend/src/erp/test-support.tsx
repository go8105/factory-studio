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
      const data = url.endsWith("/partners")
        ? [partner]
        : url.endsWith("/items")
          ? [item]
          : url.endsWith("/partner-prices")
            ? [price]
            : url.endsWith("/accounts")
              ? [{ id: 4, accountCode: "AR", accountName: "외상매출금" }]
              : url.endsWith("/posting-rules")
                ? [
                    {
                      id: 5,
                      transactionKind: "SALE",
                      lineNo: 1,
                      entrySide: "DEBIT",
                      accountCode: "AR",
                      amountBasis: "TOTAL",
                    },
                  ]
                : url.endsWith("/conversions")
                  ? [
                      {
                        id: 6,
                        fromUnit: "BOX",
                        toUnit: "EA",
                        factor: "12.000000",
                      },
                    ]
                  : [];
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
