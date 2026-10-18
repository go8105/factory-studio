import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { OperatingEvidence } from "./OperatingEvidence";
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
          <OperatingEvidence canEdit={canEdit} disabled={false} />
        </RoleContext.Provider>
      </CompanyContext.Provider>
    </MemoryRouter>,
  );
}
beforeEach(() => vi.restoreAllMocks());
it("실패와 이전 기준을 표시하고 감사 담당자에게 등록 입력을 숨긴다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    response({
      total: 1,
      items: [
        {
          id: "1",
          runId: "synthetic-run",
          kind: "RESTORE",
          result: "FAIL",
          finishedAt: "2026-10-18T01:00:00Z",
          revisionNo: 1,
          currentPolicy: false,
        },
      ],
    }),
  );
  show(false);
  expect(await screen.findByText(/복원 · 실패/)).toBeVisible();
  expect(screen.getByText(/이전 기준/)).toBeVisible();
  expect(screen.queryByLabelText("서명된 실행 증거 파일")).toBeNull();
});
it("잘못된 파일은 보내지 않고 최근 인증 오류에 파일 선택을 유지한다", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (_url, init) =>
      init?.method === "POST"
        ? response({ code: "STEP_UP_REQUIRED", message: "추가 확인 필요" }, 403)
        : response({ total: 0, items: [] }),
    );
  show();
  const input = screen.getByLabelText("서명된 실행 증거 파일");
  const invalid = new File(["{"], "invalid.json", { type: "application/json" });
  Object.defineProperty(invalid, "text", { value: async () => "{" });
  fireEvent.change(input, { target: { files: [invalid] } });
  fireEvent.click(screen.getByRole("button", { name: "실행 증거 확인·등록" }));
  expect(
    await screen.findByText("서명된 JSON 실행 증거 파일을 선택하세요."),
  ).toBeVisible();
  expect(
    fetch.mock.calls.filter(([, init]) => init?.method === "POST"),
  ).toHaveLength(0);
  const valid = new File(["{}"], "proof.json");
  Object.defineProperty(valid, "text", { value: async () => "{}" });
  fireEvent.change(input, { target: { files: [valid] } });
  fireEvent.click(screen.getByRole("button", { name: "실행 증거 확인·등록" }));
  expect(await screen.findByText("추가 확인 필요")).toBeVisible();
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "실행 증거 확인·등록" }),
    ).toBeEnabled(),
  );
  expect(screen.queryByRole("status")).toBeNull();
  expect(
    fetch.mock.calls.filter(([, init]) => init?.method === "POST"),
  ).toHaveLength(1);
});
