// FS-017c: 변경·권한·조회 항목마다 독립 테스트.
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  MemoryRouter,
  useNavigate,
  type NavigateFunction,
} from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "../app/App";
const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-24T15:00:00Z",
  csrfToken: "csrf-c",
};
const modules = ["core", "mes", "erp", "fems"].map((moduleKey) => ({
  moduleKey,
  enabled: true,
  updatedAt: null,
}));
const workspace = {
  id: 10,
  workspaceKind: "GUEST",
  configVersion: 1,
  expiresAt: session.expiresAt,
  createdAt: "2026-09-24",
};
function response(data: unknown, status = 200) {
  return new Response(
    JSON.stringify(
      status === 200
        ? { data, page: { offset: 0, limit: 20, total: 21 } }
        : { error: { code: "FAILURE", message: "요청 실패" } },
    ),
    { status },
  );
}
type Handler = (
  path: string,
  options?: RequestInit,
) => Promise<Response> | Response | undefined;
function mock(handler: Handler = () => undefined, roles = ["GUEST"]) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, options) => {
      const path = String(input).replace("/api/v1/core", "");
      const handled = handler(path, options);
      if (handled) return handled;
      if (path === "/sessions/current")
        return response({
          ...session,
          roles,
          actorKind: roles.includes("GUEST") ? "GUEST" : "MEMBER",
        });
      if (path === "/workspace") return response(workspace);
      if (path === "/workspace/modules") return response(modules);
      if (path.startsWith("/admin/"))
        return response([{ id: 1, action: "session.created" }]);
      return response({ generationId: 21 });
    });
}
let navigate: NavigateFunction;
function NavHarness() {
  navigate = useNavigate();
  return <App />;
}
function show(path = "/workspace") {
  render(
    <MemoryRouter initialEntries={["/home", path]} initialIndex={1}>
      <NavHarness />
    </MemoryRouter>,
  );
}
async function confirmReset() {
  fireEvent.click(
    await screen.findByRole("button", { name: "예시 데이터 초기화" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "초기화 확인" }));
}
function deferred() {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
afterEach(() => vi.useRealTimers());
it("초기화 확인 단계에서 되돌릴 수 없음을 경고한다", async () => {
  mock();
  show();
  fireEvent.click(
    await screen.findByRole("button", { name: "예시 데이터 초기화" }),
  );
  expect(
    screen.getByRole("button", { name: "초기화 확인" }),
  ).toHaveAccessibleDescription(
    "변경한 예시 데이터는 되돌릴 수 없습니다. 초기화하시겠습니까?",
  );
});
it("초기화 취소는 POST를 보내지 않는다", async () => {
  const fetcher = mock();
  show();
  fireEvent.click(
    await screen.findByRole("button", { name: "예시 데이터 초기화" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "취소" }));
  expect(
    fetcher.mock.calls.some(([url]) =>
      String(url).endsWith("/workspace/generations"),
    ),
  ).toBe(false);
});
it("초기화는 CSRF와 멱등 키를 전달한다", async () => {
  const fetcher = mock();
  show();
  await confirmReset();
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/core/workspace/generations",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-CSRF-Token": "csrf-c",
          "Idempotency-Key": expect.any(String),
        }),
      }),
    ),
  );
});
it("초기화 중 중복 POST를 막는다", async () => {
  const pending = deferred();
  const fetcher = mock((p) =>
    p === "/workspace/generations" ? pending.promise : undefined,
  );
  show();
  await confirmReset();
  fireEvent.click(screen.getByRole("button", { name: "초기화 확인" }));
  expect(
    fetcher.mock.calls.filter(([url]) =>
      String(url).endsWith("/workspace/generations"),
    ),
  ).toHaveLength(1);
  await act(async () => pending.resolve(response({ generationId: 21 })));
});
it("초기화 중 화면 맥락 도움말 이동을 막는다", async () => {
  const pending = deferred();
  mock((p) => (p === "/workspace/generations" ? pending.promise : undefined));
  show();
  await confirmReset();
  fireEvent.click(screen.getByRole("link", { name: "내 공간 도움말" }));
  expect(screen.getByRole("heading", { name: "내 공간" })).toBeVisible();
  await act(async () => pending.resolve(response({ generationId: 21 })));
});
it("초기화 중 푸터 이동을 막는다", async () => {
  const pending = deferred();
  mock((p) => (p === "/workspace/generations" ? pending.promise : undefined));
  show();
  await confirmReset();
  fireEvent.click(screen.getByRole("link", { name: "공통 이용 안내" }));
  expect(screen.getByRole("heading", { name: "내 공간" })).toBeVisible();
  await act(async () => pending.resolve(response({ generationId: 21 })));
});
it("초기화 중 뒤로가기도 업무 진입 화면을 렌더링하지 않는다", async () => {
  const pending = deferred();
  mock((p) => (p === "/workspace/generations" ? pending.promise : undefined));
  show();
  await confirmReset();
  act(() => navigate(-1));
  expect(screen.getByRole("heading", { name: "내 공간" })).toBeVisible();
  await act(async () => pending.resolve(response({ generationId: 21 })));
});
it("모듈 변경 실패 시 기존 토글 값을 유지한다", async () => {
  mock((p) =>
    p === "/workspace/modules/mes" ? response(null, 409) : undefined,
  );
  show();
  fireEvent.click(await screen.findByRole("switch", { name: "MES 사용" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("switch", { name: "MES 사용" })).toHaveAttribute(
    "aria-checked",
    "true",
  );
});
it("불확실한 초기화 재시도는 같은 멱등 키를 쓴다", async () => {
  const fetcher = mock((p) =>
    p === "/workspace/generations" ? response(null, 500) : undefined,
  );
  show();
  await confirmReset();
  fireEvent.click(await screen.findByRole("button", { name: "다시 시도" }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.filter(([url]) =>
        String(url).endsWith("/workspace/generations"),
      ),
    ).toHaveLength(2),
  );
  const calls = fetcher.mock.calls.filter(([url]) =>
    String(url).endsWith("/workspace/generations"),
  );
  expect(calls[0][1]?.headers).toEqual(calls[1][1]?.headers);
});
it("초기화 결과 불확실 중에도 이동 차단을 유지한다", async () => {
  mock((p) =>
    p === "/workspace/generations" ? response(null, 500) : undefined,
  );
  show();
  await confirmReset();
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("link", { name: "앱 런처" }));
  expect(screen.getByRole("heading", { name: "내 공간" })).toBeVisible();
});
it("초기화 성공 뒤 조회 실패 재시도는 POST를 반복하지 않는다", async () => {
  let posted = false;
  const fetcher = mock((p) => {
    if (p === "/workspace/generations") {
      posted = true;
      return response({ generationId: 21 });
    }
    if (p === "/workspace" && posted) return response(null, 500);
  });
  show();
  await confirmReset();
  fireEvent.click(await screen.findByRole("button", { name: "다시 시도" }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.filter(([url]) => String(url).endsWith("/workspace")),
    ).toHaveLength(3),
  );
  expect(
    fetcher.mock.calls.filter(([url]) =>
      String(url).endsWith("/workspace/generations"),
    ),
  ).toHaveLength(1);
});
it("게스트 만료 시각은 KST 자정으로 표시한다", async () => {
  mock();
  show();
  expect(await screen.findByText(/만료 예정/)).toHaveTextContent(
    "2026. 9. 25. 오전 12:00:00 KST",
  );
});
it("남은 시간은 서버 만료 시각과 현재 시간의 차이다", async () => {
  vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-09-24T14:50:00Z"));
  mock();
  show();
  expect(await screen.findByText("남은 시간 10분")).toBeVisible();
});
it("모듈 요청 후 게스트 만료 시각을 연장하지 않는다", async () => {
  mock();
  show();
  const before = (await screen.findByText(/만료 예정/)).textContent;
  fireEvent.click(screen.getByRole("switch", { name: "MES 사용" }));
  await screen.findByText("앱 사용 여부를 변경했습니다.");
  expect(screen.getByText(/만료 예정/).textContent).toBe(before);
});
it("OWNER 직접 접근은 404다", async () => {
  mock(() => undefined, ["OWNER"]);
  show("/records");
  expect(await screen.findByText("404 · NOT_FOUND")).toBeVisible();
});
it("OWNER에게 운영 기록 메뉴를 표시하지 않는다", async () => {
  mock(() => undefined, ["OWNER"]);
  show("/home");
  await screen.findByRole("heading", { name: "제조 현장의 올인원 시스템" });
  expect(
    screen.queryByRole("link", { name: "운영 기록" }),
  ).not.toBeInTheDocument();
});
it("게스트 차단 시 운영 기록 API도 호출하지 않는다", async () => {
  const fetcher = mock();
  show("/records");
  await screen.findByText("404 · NOT_FOUND");
  expect(
    fetcher.mock.calls.some(([url]) => String(url).includes("/admin/")),
  ).toBe(false);
});
it("ADMIN 운영 기록 다음 페이지는 offset 20으로 조회한다", async () => {
  const fetcher = mock(() => undefined, ["ADMIN"]);
  show("/records");
  fireEvent.click(await screen.findByRole("button", { name: "다음" }));
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/core/admin/audit-events?offset=20&limit=20",
      expect.anything(),
    ),
  );
});
it("작업 내역 탭으로 변경하면 offset을 0으로 초기화한다", async () => {
  const fetcher = mock(() => undefined, ["ADMIN"]);
  show("/records");
  fireEvent.click(await screen.findByRole("button", { name: "다음" }));
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/core/admin/audit-events?offset=20&limit=20",
      expect.anything(),
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: "작업 실행 내역" }));
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/core/admin/job-runs?offset=0&limit=20",
      expect.anything(),
    ),
  );
});
it("운영 기록 조회 오류는 같은 화면에서 재시도한다", async () => {
  let failed = true;
  mock(
    (p) =>
      p.startsWith("/admin/") && failed ? response(null, 500) : undefined,
    ["ADMIN"],
  );
  show("/records");
  await screen.findByRole("alert");
  failed = false;
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
  expect(
    await screen.findByRole("cell", { name: "session.created" }),
  ).toBeVisible();
});
it("운영 기록은 조회만 수행한다", async () => {
  const fetcher = mock(() => undefined, ["ADMIN"]);
  show("/records");
  await screen.findByRole("cell", { name: "session.created" });
  expect(
    fetcher.mock.calls
      .filter(([url]) => String(url).includes("/admin/"))
      .every(([, options]) => options?.method === "GET"),
  ).toBe(true);
});
