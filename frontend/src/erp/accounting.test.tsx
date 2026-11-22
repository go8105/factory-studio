import { screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";
it("전표 목록에 자동 전표가 함께 나온다", async () => {
  mount("/erp/journal-entries");
  expect(await screen.findByText("JV-20260909-001")).toBeVisible();
  expect(screen.getByText("SALE")).toBeVisible();
});
it("확정 조건 넷을 안내한다", async () => {
  mount("/erp/journal-entries");
  expect(await screen.findByRole("note")).toHaveTextContent(
    /차변 합 = 대변 합/,
  );
});
it("미반영 현황이 왜 전표가 없는지 말한다", async () => {
  mount("/erp/unposted");
  expect(
    await screen.findByText("규칙이 가리키는 계정이 사용 중지됐습니다."),
  ).toBeVisible();
});
it("업무가 회계 때문에 막히지 않는다고 안내한다", async () => {
  mount("/erp/unposted");
  expect(await screen.findByRole("note")).toHaveTextContent(
    /업무는 회계 때문에 막히지 않습니다/,
  );
});
it("지출결의서 목록을 보여 준다", async () => {
  mount("/erp/expense-claims");
  expect(await screen.findByText("EC-20260915-001")).toBeVisible();
  expect(screen.getByText("계좌 이체")).toBeVisible();
});
