import { screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";
it("부서·담당자·프로젝트를 한 화면에서 조회한다", async () => {
  mount("/erp/organization");
  expect(await screen.findByText("영업부")).toBeVisible();
  expect(await screen.findByText("박영업")).toBeVisible();
  expect(await screen.findByText("커넥터 라인 증설")).toBeVisible();
});
it("담당자의 부서를 코드·이름으로 보여 준다", async () => {
  mount("/erp/organization");
  const row = (await screen.findByText("박영업")).closest("tr")!;
  expect(within(row).getByText("D-SALES · 영업부")).toBeVisible();
});
it("HR 조직과 별개임을 안내한다", async () => {
  mount("/erp/organization");
  expect(await screen.findByRole("note")).toHaveTextContent(
    /HR 조직과 별개로 ERP가 직접 가집니다/,
  );
});
it("세 마스터 모두 등록 단추를 제공한다", async () => {
  mount("/erp/organization");
  await screen.findByText("영업부");
  for (const name of ["부서 등록", "담당자 등록", "프로젝트 등록"])
    expect(screen.getByRole("button", { name })).toBeVisible();
});
it("도움말 링크가 이 화면의 도움말로 간다", async () => {
  mount("/erp/organization");
  expect(
    await screen.findByRole("link", { name: "부서·담당자·프로젝트 도움말" }),
  ).toHaveAttribute("href", "/help/erp/e-19");
});
