// FS-019h E-01 ERP 대시보드. 검증 항목별로 테스트를 나눈다.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";

const E = "/api/v1/erp";
const board = {
  month: "2026-09",
  salesSupply: "1000.00",
  salesTotal: "1100.00",
  salesCount: 2,
  receivableBalance: "5000.00",
  payableBalance: "3000.00",
  orderBacklog: "7000",
  monthlySales: [
    { month: "2026-08", supplyAmount: "500.00" },
    { month: "2026-09", supplyAmount: "1000.00" },
  ],
  topReceivables: [{ partnerId: 1, balance: "5000.00" }],
  receivableByDue: { overdue: "1000.00", notDue: "1500.00", unset: "2500.00" },
  planVsActual: [
    {
      itemId: 2,
      itemCode: "FG-001",
      name: "예시 품목",
      planQty: "100.000",
      actualQty: "40.000",
    },
  ],
  pending: { uninvoicedSales: 3, unappliedReceipts: 1 },
};
const reply = {
  [`GET ${E}/dashboard`]: { status: 200, body: { data: board } },
};

it("ERP 진입은 대시보드다", async () => {
  mount("/erp", reply);
  expect(
    await screen.findByRole("heading", { name: "경영 개요" }),
  ).toBeVisible();
});

it("핵심 지표 네 개를 보여 준다", async () => {
  mount("/erp/dashboard", reply);
  expect(
    await screen.findByRole("region", { name: "당월 매출" }),
  ).toHaveTextContent("1,000원");
  expect(screen.getByRole("region", { name: "미수금" })).toHaveTextContent(
    "5,000원",
  );
  expect(screen.getByRole("region", { name: "미지급" })).toHaveTextContent(
    "3,000원",
  );
  expect(screen.getByRole("region", { name: "수주잔" })).toHaveTextContent(
    "7,000원",
  );
});

it("만기 미설정은 연체와 따로 적는다", async () => {
  mount("/erp/dashboard", reply);
  const panel = await screen.findByRole("region", {
    name: "거래처별 미수금 상위",
  });
  expect(panel).toHaveTextContent("만기 미설정 2,500원");
  expect(panel).toHaveTextContent("연체 1,000원");
});

it("처리 대기는 해당 화면으로 연결한다", async () => {
  mount("/erp/dashboard", reply);
  const panel = await screen.findByRole("region", { name: "처리 대기" });
  expect(
    within(panel).getByRole("link", { name: "세금계산서 미발급 매출" }),
  ).toHaveAttribute("href", "/erp/tax-invoices");
  expect(panel).toHaveTextContent("3건");
});

it("조회 월을 바꾸면 month로 다시 조회한다", async () => {
  const fetcher = mount("/erp/dashboard", reply);
  fireEvent.change(await screen.findByLabelText("조회 월"), {
    target: { value: "2026-08" },
  });
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(([u]) =>
        String(u).includes("dashboard?month=2026-08"),
      ),
    ).toBe(true),
  );
});
