import { screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";
it("구매 요청 목록과 명세를 보여 준다", async () => {
  mount("/erp/purchase-requests");
  expect(await screen.findByText("PR-20260924-001")).toBeVisible();
  const row = screen.getByText("PR-20260924-001").closest("tr")!;
  within(row).getByRole("button", { name: "열기" }).click();
  expect(await screen.findByText("RM-PBT PBT 수지")).toBeVisible();
});
it("요청에 금액이 없다고 안내한다", async () => {
  mount("/erp/purchase-requests");
  expect(await screen.findByRole("note")).toHaveTextContent(
    /요청에는 금액이 없습니다/,
  );
});
it("발주서는 WMS에서 읽은 입고 진행을 보여 준다", async () => {
  mount("/erp/purchase-orders");
  expect(await screen.findByText("PO-SEED-0001")).toBeVisible();
  expect(screen.getByText("부분 입고")).toBeVisible();
});
it("입고 진행을 저장하지 않는다고 안내한다", async () => {
  mount("/erp/purchase-orders");
  expect(await screen.findByRole("note")).toHaveTextContent(
    /ERP가 저장하지 않고 WMS 입고/,
  );
});
it("판매 반품은 원 매출을 참조한다고 안내한다", async () => {
  mount("/erp/sales-returns");
  expect(await screen.findByText("SR-20260909-001")).toBeVisible();
  expect(screen.getByRole("note")).toHaveTextContent(/원 매출을 고르고/);
});
