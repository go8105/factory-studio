import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount, partner } from "./test-support";
it("거래처 시드 목록을 표시한다", async () => {
  mount("/erp/partners");
  expect(await screen.findByText("예시 거래처")).toBeVisible();
});
it("거래처 구분 select를 표시한다", async () => {
  mount("/erp/partners");
  expect(await screen.findByLabelText("거래처 구분")).toHaveValue("CUSTOMER");
});
it("폼 사용 여부는 inline-check다", async () => {
  mount("/erp/partners");
  const box = await screen.findByRole("checkbox", { name: "사용 여부" });
  expect(box.parentElement).toHaveClass("inline-check");
});
it("거래처 수정은 CSRF와 멱등 키를 보낸다", async () => {
  const fetcher = mount("/erp/partners", {
    "PATCH /api/v1/erp/partners/1": {
      status: 200,
      body: { data: { ...partner, partnerName: "수정 거래처" } },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "수정" }));
  fireEvent.change(screen.getByLabelText("거래처명"), {
    target: { value: "수정 거래처" },
  });
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await screen.findByText("저장했습니다.");
  const call = fetcher.mock.calls.find(([, init]) => init?.method === "PATCH")!;
  expect(call[1]?.headers).toMatchObject({
    "X-CSRF-Token": "csrf-test",
    "Idempotency-Key": expect.any(String),
  });
});
it("삭제는 확인 전 요청하지 않는다", async () => {
  const fetcher = mount("/erp/partners");
  fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
  expect(screen.getByRole("button", { name: "삭제 확인" })).toBeVisible();
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(
    false,
  );
});
it("참조 삭제 실패는 건수를 표시한다", async () => {
  mount("/erp/partners", {
    "DELETE /api/v1/erp/partners/1": {
      status: 409,
      body: {
        error: {
          code: "REFERENCED_BY_OTHERS",
          message: "참조 중입니다",
          details: { references: [{ label: "수주", count: 2 }] },
        },
      },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
  fireEvent.click(screen.getByRole("button", { name: "삭제 확인" }));
  expect(await screen.findByText("수주 2건")).toBeVisible();
});
it("입력 필드 오류를 표시한다", async () => {
  mount("/erp/partners", {
    "PATCH /api/v1/erp/partners/1": {
      status: 400,
      body: {
        error: {
          code: "VALIDATION_FAILED",
          message: "입력 오류",
          details: { fields: { partnerName: "이름 확인" } },
        },
      },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "수정" }));
  fireEvent.change(screen.getByLabelText("거래처명"), {
    target: { value: "새 이름" },
  });
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() =>
    expect(screen.getByLabelText("거래처명")).toHaveAttribute(
      "aria-invalid",
      "true",
    ),
  );
});
it("ERP 사이드바에 네 화면을 연결한다", async () => {
  mount("/erp/partners");
  const menu = await screen.findByRole("complementary", { name: "ERP 메뉴" });
  expect(within(menu).getByRole("link", { name: /E-18/ })).toHaveAttribute(
    "href",
    "/erp/accounts",
  );
});
it("ERP 모듈 중단을 안내한다", async () => {
  mount("/erp/partners", {
    "GET /api/v1/erp/partners": {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "중단",
          details: { reason: "MODULE_DISABLED" },
        },
      },
    },
  });
  expect(
    await screen.findByText("ERP를 사용하지 않도록 설정했습니다."),
  ).toBeVisible();
});
