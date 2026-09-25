import { fireEvent, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";
it("MES와 독립임을 안내한다", async () => {
  mount("/erp/items");
  expect(await screen.findByText(/MES 품목과 독립/)).toBeVisible();
});
it("품목 과세 구분 select를 표시한다", async () => {
  mount("/erp/items");
  expect(await screen.findByLabelText("과세 구분")).toHaveValue("TAXABLE");
});
it("선택한 품목의 단위환산을 표시한다", async () => {
  mount("/erp/items");
  await screen.findByRole("option", { name: /FG-001/ });
  fireEvent.change(screen.getByLabelText("환산할 품목"), {
    target: { value: "2" },
  });
  expect(await screen.findByText("12.000000")).toBeVisible();
});
it("단위환산 등록은 기준 단위를 클라이언트가 보내지 않는다", async () => {
  const fetcher = mount("/erp/items", {
    "POST /api/v1/erp/items/2/conversions": {
      status: 201,
      body: { data: { id: 7 } },
    },
  });
  await screen.findByRole("option", { name: /FG-001/ });
  fireEvent.change(screen.getByLabelText("환산할 품목"), {
    target: { value: "2" },
  });
  fireEvent.change(await screen.findByLabelText("환산 전 단위"), {
    target: { value: "PACK" },
  });
  fireEvent.submit(screen.getByRole("form", { name: "단위환산 등록" }));
  await screen.findByText("저장했습니다.");
  const call = fetcher.mock.calls.find(([, init]) => init?.method === "POST")!;
  expect(JSON.parse(String(call[1]?.body))).toEqual({
    fromUnit: "PACK",
    factor: "1",
  });
});
