import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { RetentionReviews } from "./RetentionReviews";
import { CompanyContext, RoleContext } from "./common";
vi.mock("../app/session", () => ({
  useSession: () => ({
    session: { workspaceId: 1, generationId: 2, csrfToken: "synthetic" },
    fail: vi.fn(),
  }),
}));
const response = (data: unknown, status = 200) =>
  new Response(JSON.stringify(status < 400 ? { data } : { error: data }), {
    status,
  });
const data = {
  total: 2,
  companyHold: false,
  holdReason: null,
  settingsVersion: 2,
  items: [
    {
      id: "1",
      kind: "documents",
      sourceId: "12",
      dueOn: "2024-02-29",
      state: "DUE",
      version: 1,
      reason: "합성 기한 검토",
      revisionNo: 1,
      currentPolicy: true,
      canReadSource: false,
      effectiveHold: false,
    },
    {
      id: "2",
      kind: "posts",
      sourceId: "13",
      dueOn: "2024-02-29",
      state: "HELD",
      version: 1,
      reason: "합성 보류",
      revisionNo: 1,
      currentPolicy: false,
      canReadSource: true,
      effectiveHold: true,
    },
  ],
};
function show(canEdit = true) {
  return render(
    <MemoryRouter>
      <CompanyContext.Provider value={{ companyId: "10" }}>
        <RoleContext.Provider
          value={{
            person: "3",
            setPerson: () => {},
            people: [],
            reload: () => {},
            companyId: "10",
            roles: ["SECURITY_ADMIN"],
          }}
        >
          <RetentionReviews canEdit={canEdit} disabled={false} />
        </RoleContext.Provider>
      </CompanyContext.Provider>
    </MemoryRouter>,
  );
}
beforeEach(() => vi.restoreAllMocks());
it("원문 권한 없는 기록은 식별자만 표시하고 감사 담당자는 상태를 변경하지 못한다", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
    response(
      String(url).includes("/retention-events")
        ? { total: 0, items: [] }
        : data,
    ),
  );
  show(false);
  expect(await screen.findByText(/일반 기안 #12/)).toBeVisible();
  expect(screen.getByText("원문 열람 권한 없음")).toBeVisible();
  expect(screen.getAllByRole("link", { name: "원문 열기" })).toHaveLength(1);
  expect(screen.getByRole("link", { name: "원문 열기" })).toHaveAttribute(
    "href",
    "/gw/board?companyId=10&open=13",
  );
  expect(screen.queryByRole("button", { name: "보관 준비" })).toBeNull();
  expect(screen.queryByRole("button", { name: "검토 대상 갱신" })).toBeNull();
});
it("보류 적용과 최근 인증 오류 뒤 사유·동의를 유지하고 계속 편집으로 돌아온다", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (url, init) =>
      init?.method === "POST"
        ? response(
            {
              code: "STEP_UP_REQUIRED",
              message: "추가 본인 확인이 필요합니다.",
            },
            403,
          )
        : response(
            String(url).includes("/retention-events")
              ? { total: 0, items: [] }
              : data,
          ),
    );
  show();
  fireEvent.click(
    await screen.findByRole("button", { name: "회사 전체 보존 중지" }),
  );
  const reason = screen.getByLabelText("보관 검토 처리 사유");
  fireEvent.change(reason, { target: { value: "합성 조사 자료 보존" } });
  fireEvent.click(
    screen.getByLabelText("처리 범위와 원본 유지 안내를 확인했습니다"),
  );
  reason.focus();
  fireEvent.click(screen.getByRole("button", { name: "취소" }));
  fireEvent.click(screen.getByRole("button", { name: "계속 편집" }));
  await waitFor(() => expect(reason).toHaveFocus());
  fireEvent.click(screen.getByRole("button", { name: "사유 확인하고 적용" }));
  expect(await screen.findByText("추가 본인 확인이 필요합니다.")).toBeVisible();
  expect(reason).toHaveValue("합성 조사 자료 보존");
  expect(
    screen.getByLabelText("처리 범위와 원본 유지 안내를 확인했습니다"),
  ).toBeChecked();
  const posts = fetch.mock.calls.filter(([, init]) => init?.method === "POST");
  expect(posts).toHaveLength(1);
  expect(posts[0][0]).toBe("/api/v1/gw/retention-company-hold?companyId=10");
  expect(JSON.parse(posts[0][1]!.body as string)).toEqual({
    expectedVersion: 2,
    hold: true,
    reason: "합성 조사 자료 보존",
  });
});
it("회사 보존 중지 중에는 원문 권한이 있어도 보관 준비를 표시하지 않는다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    response({
      ...data,
      companyHold: true,
      items: [{ ...data.items[0], canReadSource: true, effectiveHold: true }],
    }),
  );
  show();
  expect(await screen.findByText(/회사 전체 보존 중지:/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "보관 준비" })).toBeNull();
  expect(
    screen.getByRole("button", { name: "회사 보존 중지 해제" }),
  ).toBeEnabled();
  expect(screen.getByRole("button", { name: "개별 보류" })).toBeEnabled();
});
