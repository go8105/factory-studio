import { screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";

it("원장은 계정별 잔액과 명세를 보여 준다", async () => {
  mount("/erp/books");
  expect(await screen.findByText("AR 외상매출금")).toBeVisible();
  expect(screen.getByRole("note")).toHaveTextContent(/기초 잔액\(E-35\)/);
});
it("원장은 저장하지 않고 센다고 안내한다", async () => {
  mount("/erp/books");
  expect(await screen.findByRole("note")).toHaveTextContent(/그때그때 셉니다/);
});
it("시산표는 같은 계산을 범위만 바꿔 본다", async () => {
  mount("/erp/trial-balance");
  expect(await screen.findByRole("button", { name: "일계표" })).toBeVisible();
  expect(screen.getByRole("button", { name: "월계표" })).toBeVisible();
  expect(screen.getByRole("button", { name: "합계잔액시산표" })).toBeVisible();
});
it("재무제표는 당기순이익을 자본에 얹어 보여 준다", async () => {
  mount("/erp/statements");
  expect(await screen.findByText("당기순이익")).toBeVisible();
  expect(screen.getByRole("heading", { name: "요약" })).toBeVisible();
});
it("월 마감은 작성 중·미반영 수를 함께 보여 준다", async () => {
  mount("/erp/closing");
  expect(await screen.findByText("2026-07")).toBeVisible();
  expect(screen.getByRole("button", { name: "해제" })).toBeVisible();
  expect(screen.getByText("2건")).toBeVisible();
});
it("마감이 업무를 막지 않는다고 안내한다", async () => {
  mount("/erp/closing");
  expect(await screen.findByText(/업무는.*막지 않습니다/)).toBeVisible();
});
