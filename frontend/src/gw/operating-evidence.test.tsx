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
function show(
  canEdit = true,
  onRecorded?: () => void,
  onDirtyChange?: (dirty: boolean) => void,
) {
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
          <OperatingEvidence
            canEdit={canEdit}
            disabled={false}
            onRecorded={onRecorded}
            onDirtyChange={onDirtyChange}
          />
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
it("실행 증거를 등록한 뒤 상위 준비 판정을 갱신한다", async () => {
  const onRecorded = vi.fn();
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, init) =>
    init?.method === "POST"
      ? response({ id: "1" })
      : response({ total: 0, items: [] }),
  );
  show(true, onRecorded);
  const file = new File(["{}"], "synthetic-proof.json");
  Object.defineProperty(file, "text", { value: async () => "{}" });
  fireEvent.change(screen.getByLabelText("서명된 실행 증거 파일"), {
    target: { files: [file] },
  });
  fireEvent.click(screen.getByRole("button", { name: "실행 증거 확인·등록" }));
  await waitFor(() => expect(onRecorded).toHaveBeenCalledTimes(1));
  expect(
    await screen.findByText(
      "실행 기록을 등록했습니다. 운영 준비 완료를 뜻하지 않습니다.",
    ),
  ).toBeVisible();
});

it("파일 선택을 상위 재점검 잠금에 연결하고 해제한다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    response({ total: 0, items: [] }),
  );
  const dirty = vi.fn();
  const view = show(true, undefined, dirty);
  await screen.findByText("등록된 실행 기록이 없습니다.");
  expect(dirty).toHaveBeenLastCalledWith(false);
  fireEvent.change(screen.getByLabelText("서명된 실행 증거 파일"), {
    target: { files: [new File(["{}"], "synthetic.json")] },
  });
  expect(dirty).toHaveBeenLastCalledWith(true);
  view.unmount();
  expect(dirty).toHaveBeenLastCalledWith(false);
});
