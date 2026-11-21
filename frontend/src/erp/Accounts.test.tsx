import { screen, within } from "@testing-library/react";
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
it("분개규칙 줄에는 수정·삭제가 없다", async () => {
  mount("/erp/accounts");
  const row = (await screen.findByText("DEBIT")).closest("tr")!;
  expect(within(row).queryByRole("button", { name: "수정" })).toBeNull();
  expect(within(row).queryByRole("button", { name: "삭제" })).toBeNull();
});
it("매핑 이유를 안내한다", async () => {
  mount("/erp/accounts");
  expect(
    await screen.findByRole("heading", { name: "매핑 이유" }),
  ).toBeVisible();
});
it("계정 분류와 정상 잔액을 보여 준다", async () => {
  mount("/erp/accounts");
  const row = (await screen.findByText("외상매출금")).closest("tr")!;
  expect(within(row).getByText("자산")).toBeVisible();
  expect(within(row).getByText("차변")).toBeVisible();
});
it("계정은 등록할 수 있고 분개규칙은 읽기 전용이다", async () => {
  mount("/erp/accounts");
  await screen.findByText("외상매출금");
  expect(screen.getByRole("button", { name: "계정과목 등록" })).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "분개규칙 등록" }),
  ).not.toBeInTheDocument();
});
it("계정과목에는 삭제 단추를 두지 않는다", async () => {
  mount("/erp/accounts");
  const row = (await screen.findByText("외상매출금")).closest("tr")!;
  expect(within(row).getByRole("button", { name: "수정" })).toBeVisible();
  expect(within(row).queryByRole("button", { name: "삭제" })).toBeNull();
});
