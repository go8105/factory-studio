import { fireEvent, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";
it("거래처와 품목을 선택할 수 있다", async () => {
  mount("/erp/partner-prices");
  fireEvent.click(
    await screen.findByRole("button", { name: "거래처별 단가 등록" }),
  );
  expect(
    await screen.findByRole("option", { name: "C-001 · 예시 거래처" }),
  ).toBeVisible();
});
it("종료월 없이 등록할 수 있다", async () => {
  mount("/erp/partner-prices");
  fireEvent.click(
    await screen.findByRole("button", { name: "거래처별 단가 등록" }),
  );
  expect(await screen.findByLabelText("종료월")).not.toBeRequired();
});
it("겹침 오류를 표시한다", async () => {
  mount("/erp/partner-prices", {
    "PATCH /api/v1/erp/partner-prices/3": {
      status: 409,
      body: {
        error: {
          code: "PERIOD_OVERLAP",
          message: "적용 구간이 겹칩니다.",
          details: {
            reason: "PERIOD_OVERLAP",
            references: [{ label: "겹치는 단가", count: 1 }],
          },
        },
      },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "수정" }));
  fireEvent.change(screen.getByLabelText("시작월"), {
    target: { value: "2026-02" },
  });
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  expect(await screen.findByText("겹치는 단가 1건")).toBeVisible();
});
