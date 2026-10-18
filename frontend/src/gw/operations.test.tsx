import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { Operations } from "./Operations";
import { CompanyContext, RoleContext } from "./common";
vi.mock("../app/session", () => ({
  useSession: () => ({
    session: { workspaceId: 1, generationId: 2, csrfToken: "synthetic-csrf" },
    fail: vi.fn(),
  }),
}));
const response = (data: unknown, status = 200) =>
  new Response(JSON.stringify(status < 400 ? { data } : { error: data }), {
    status,
  });
const initial = {
  administrator: true,
  canEdit: true,
  version: 0,
  rolloutState: "DRAFT",
  connectedPeople: 1,
  mfaPeople: 1,
  policy: null,
  revisionNo: null,
  ready: false,
  blockers: ["실제 복원 검증이 필요합니다."],
};
function show() {
  render(
    <MemoryRouter>
      <CompanyContext.Provider value={{ companyId: "10" }}>
        <RoleContext.Provider
          value={{
            person: "3",
            setPerson: () => {},
            people: [
              {
                id: "3",
                code: "SYN-001",
                name: "합성 책임자",
                isActive: true,
                jobRole: "",
                version: 1,
              },
            ],
            reload: () => {},
            companyId: "10",
            roles: ["SECURITY_ADMIN"],
          }}
        >
          <Operations />
        </RoleContext.Provider>
      </CompanyContext.Provider>
    </MemoryRouter>,
  );
}
beforeEach(() => vi.restoreAllMocks());
it("준비 미완료 사유와 기본안을 표시하고 계속 편집 시 입력 포커스를 복원한다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response(initial));
  show();
  await screen.findByText("실제 복원 검증이 필요합니다.");
  fireEvent.click(screen.getByRole("button", { name: "운영 기준 검토·적용" }));
  const reason = screen.getByLabelText("적용 사유");
  reason.focus();
  fireEvent.change(reason, { target: { value: "합성 운영 기준" } });
  fireEvent.click(screen.getByRole("button", { name: "취소" }));
  fireEvent.click(screen.getByRole("button", { name: "계속 편집" }));
  await waitFor(() => expect(reason).toHaveFocus());
  expect(reason).toHaveValue("합성 운영 기준");
  expect(screen.getByLabelText("예정 직원 수")).toHaveValue(10);
  expect(
    screen.getByRole("button", { name: "새 버전으로 적용" }),
  ).toBeDisabled();
});
it("직원 응답에는 관리자 정책 입력을 표시하지 않는다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    response({
      administrator: false,
      nextAction: "내 계정 보안에서 확인하세요.",
    }),
  );
  show();
  expect(await screen.findByText("내 계정 보안에서 확인하세요.")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "운영 기준 검토·적용" }),
  ).not.toBeInTheDocument();
});
it("추가 인증 오류 뒤 패널과 입력을 유지한다", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
    String(url).includes("/operating-policies")
      ? response(
          {
            code: "STEP_UP_REQUIRED",
            message: "내 계정 보안에서 다시 확인하세요.",
          },
          403,
        )
      : response(initial),
  );
  show();
  fireEvent.click(
    await screen.findByRole("button", { name: "운영 기준 검토·적용" }),
  );
  const reason = screen.getByLabelText("적용 사유");
  fireEvent.change(reason, { target: { value: "합성 사유 유지" } });
  fireEvent.click(screen.getByLabelText("변경 내용과 영향을 검토했습니다"));
  fireEvent.click(screen.getByRole("button", { name: "새 버전으로 적용" }));
  expect(
    await screen.findByText("내 계정 보안에서 다시 확인하세요."),
  ).toBeVisible();
  expect(reason).toHaveValue("합성 사유 유지");
  expect(fetch).toHaveBeenCalledTimes(2);
});
