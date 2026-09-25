import { screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";
it("계정과목을 조회한다", async () => {
  mount("/erp/accounts");
  expect(await screen.findByText("외상매출금")).toBeVisible();
});
it("분개 규칙을 조회한다", async () => {
  mount("/erp/accounts");
  expect(await screen.findByText("DEBIT")).toBeVisible();
});
it("수정과 삭제를 제공하지 않는다", async () => {
  mount("/erp/accounts");
  await screen.findByText("외상매출금");
  expect(
    screen.queryByRole("button", { name: "수정" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "삭제" }),
  ).not.toBeInTheDocument();
});
it("매핑 이유를 안내한다", async () => {
  mount("/erp/accounts");
  expect(
    await screen.findByRole("heading", { name: "매핑 이유" }),
  ).toBeVisible();
});
