import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  Link,
  MemoryRouter,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { GwLayout } from "./GwLayout";
import { Documents } from "./Documents";
const auth = vi.hoisted(() => ({ fail: vi.fn() }));
vi.mock("../app/session", () => ({
  useSession: () => ({
    session: {
      actorKind: "MEMBER",
      workspaceId: 1,
      generationId: 2,
      csrfToken: "synthetic",
    },
    fail: auth.fail,
  }),
}));
vi.mock("../shared/SolutionLayout", () => ({
  SolutionLayout: ({
    beforeContent,
    content,
    linkQuery,
  }: {
    beforeContent: ReactNode;
    content?: ReactNode;
    linkQuery?: string;
  }) => (
    <>
      {beforeContent}
      <Link to={"/gw/board?" + linkQuery}>다른 업무</Link>
      {content ?? <Outlet />}
    </>
  ),
}));
afterEach(() => {
  vi.restoreAllMocks();
  auth.fail.mockClear();
});
const doc = {
  id: "10",
  documentNo: "SYN-10",
  title: "합성 비공개 원문",
  body: "합성 비공개 본문",
  kind: "GENERAL",
  status: "IN_REVIEW",
  version: 4,
  drafterId: "1",
  drafterName: "기안자",
  routeId: "3",
  routeName: "합성 결재선",
  currentStep: 1,
  roundNo: 1,
  amount: "100",
  currency: "KRW",
  sourceSnapshot: null,
  sourceComparison: null,
  steps: [
    {
      id: "20",
      personId: "501",
      personName: "합성 직원",
      seq: 1,
      participantRole: "APPROVER",
      status: "WAITING",
    },
  ],
  events: [],
  availableActions: ["approve"],
  actionSteps: [
    { stepId: "20", personName: "합성 직원", participantRole: "APPROVER" },
  ],
};
const reply = (data: unknown, status = 200) =>
  new Response(JSON.stringify(status < 400 ? { data } : { error: data }), {
    status,
  });
function fixture() {
  const state = {
    version: 1,
    denied: 0,
    stepUp: false,
    lateRead: undefined as undefined | ((r: Response) => void),
    lateWrite: undefined as undefined | ((r: Response) => void),
    deferRead: false,
    deferWrite: false,
  };
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = new URL(String(input), "http://localhost");
      const path = url.pathname;
      if (path.endsWith("/companies"))
        return reply([{ id: 11, name: "합성 회사" }]);
      if (path.endsWith("/me"))
        return reply({
          company: { id: 11, name: "합성 회사" },
          person: { id: "501", name: "합성 직원", isActive: true },
          bindingStatus: "ACTIVE",
          roles: ["SECURITY_ADMIN"],
          authzVersion: state.version,
          setupRequired: false,
          businessReady: true,
        });
      if (path.endsWith("/people-options") || path.endsWith("/comments"))
        return reply([]);
      if (path.includes("/documents/10")) {
        if (init?.method === "POST" && state.stepUp)
          return reply(
            {
              code: "STEP_UP_REQUIRED",
              message: "추가 본인 확인이 필요합니다",
            },
            403,
          );
        if (init?.method === "POST" && state.deferWrite)
          return new Promise((resolve) => {
            state.lateWrite = resolve;
          });
        if (init?.method !== "POST" && state.deferRead)
          return new Promise((resolve) => {
            state.lateRead = resolve;
          });
        if (state.denied)
          return reply(
            { code: "GW_PERMISSION_DENIED", message: "합성 권한 거부" },
            state.denied,
          );
        return reply(doc);
      }
      if (path.endsWith("/documents"))
        return reply({
          rows: state.denied || state.version > 1 ? [] : [doc],
          total: state.denied || state.version > 1 ? 0 : 1,
        });
      throw new Error("Unexpected synthetic route " + path);
    });
  return { state, fetch };
}
function CurrentLocation() {
  const l = useLocation();
  return <output aria-label="current query">{l.search}</output>;
}
function show() {
  render(
    <MemoryRouter
      initialEntries={["/gw/pending?companyId=11&open=10&status=IN_REVIEW"]}
    >
      <Routes>
        <Route path="/gw" element={<GwLayout />}>
          <Route path="pending" element={<Documents box="pending" />} />
          <Route path="board" element={<p>다른 업무 현재 범위</p>} />
        </Route>
      </Routes>
      <CurrentLocation />
    </MemoryRouter>,
  );
}
function query() {
  return new URLSearchParams(
    screen.getByLabelText("current query").textContent!,
  );
}
async function openApproval() {
  fireEvent.click(await screen.findByRole("button", { name: "승인" }));
  fireEvent.change(screen.getByLabelText("처리 사유"), {
    target: { value: "합성 미저장 사유" },
  });
}
it.each([403, 404])(
  "GET %s hides original and clears URL selection before same-company retry",
  async (status) => {
    const { state } = fixture();
    show();
    await screen.findByText("합성 비공개 본문");
    state.denied = status;
    fireEvent.click(
      screen.getByRole("button", { name: "서버 상태 다시 확인" }),
    );
    await screen.findByRole("button", { name: "권한과 연결 다시 확인" });
    expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
    await waitFor(() => expect(query().has("open")).toBe(false));
    expect(query().get("companyId")).toBe("11");
    expect(query().get("status")).toBe("IN_REVIEW");
    fireEvent.click(
      screen.getByRole("button", { name: "권한과 연결 다시 확인" }),
    );
    await screen.findByText(/표시할 문서가 없습니다/);
    expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("합성 미저장 사유"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "서버 상태 다시 확인" }),
    ).not.toBeInTheDocument();
    expect(auth.fail).not.toHaveBeenCalled();
  },
);
it.each([403, 404])(
  "POST %s discards approval inputs and allows another company menu",
  async (status) => {
    const { state } = fixture();
    show();
    await screen.findByText("합성 비공개 본문");
    await openApproval();
    state.denied = status;
    fireEvent.click(screen.getByRole("button", { name: "확정" }));
    await screen.findByRole("button", { name: "권한과 연결 다시 확인" });
    await waitFor(() => expect(query().has("open")).toBe(false));
    expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("합성 미저장 사유"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "확정" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "다른 업무" }));
    await screen.findByText("다른 업무 현재 범위");
    expect(query().get("companyId")).toBe("11");
    expect(auth.fail).not.toHaveBeenCalled();
  },
);
it("a new authorization version removes selection and aborts a late detail response", async () => {
  const { state, fetch } = fixture();
  show();
  await screen.findByText("합성 비공개 본문");
  state.deferRead = true;
  fireEvent.click(screen.getByRole("button", { name: "서버 상태 다시 확인" }));
  await waitFor(() => expect(state.lateRead).toBeDefined());
  state.version = 2;
  fireEvent(window, new Event("focus"));
  await waitFor(() => expect(query().has("open")).toBe(false));
  await screen.findByText(/표시할 문서가 없습니다/);
  const detailCalls = fetch.mock.calls.filter(([url]) =>
    String(url).includes("/documents/10?"),
  );
  expect(detailCalls.at(-1)?.[1]?.signal?.aborted).toBe(true);
  await act(async () =>
    state.lateRead!(reply({ ...doc, body: "지연된 옛 원문" })),
  );
  expect(screen.queryByText("지연된 옛 원문")).not.toBeInTheDocument();
  expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
});
it("late approval success from the old authorization cannot reopen the selection", async () => {
  const { state } = fixture();
  show();
  await screen.findByText("합성 비공개 본문");
  await openApproval();
  state.deferWrite = true;
  fireEvent.click(screen.getByRole("button", { name: "확정" }));
  await waitFor(() => expect(state.lateWrite).toBeDefined());
  state.version = 2;
  fireEvent(window, new Event("focus"));
  await waitFor(() => expect(query().has("open")).toBe(false));
  await screen.findByText(/표시할 문서가 없습니다/);
  await act(async () =>
    state.lateWrite!(reply({ ...doc, version: 5, body: "지연된 처리 결과" })),
  );
  await waitFor(() => expect(query().has("open")).toBe(false));
  expect(screen.queryByText("지연된 처리 결과")).not.toBeInTheDocument();
});
it("step-up authentication keeps the original and approval selection for reauthentication", async () => {
  const { state } = fixture();
  show();
  await screen.findByText("합성 비공개 본문");
  await openApproval();
  state.stepUp = true;
  fireEvent.click(screen.getByRole("button", { name: "확정" }));
  await screen.findByText("추가 본인 확인이 필요합니다");
  expect(query().get("open")).toBe("10");
  expect(screen.getByDisplayValue("합성 미저장 사유")).toBeInTheDocument();
  expect(screen.getByText("합성 비공개 본문")).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "권한과 연결 다시 확인" }),
  ).not.toBeInTheDocument();
});
it("the existing 15-second refresh preserves selection when authorization is unchanged", async () => {
  const interval = vi.spyOn(window, "setInterval");
  const { fetch } = fixture();
  show();
  await screen.findByText("합성 비공개 본문");
  const call = interval.mock.calls.find(([, delay]) => delay === 15000);
  expect(call).toBeDefined();
  const before = fetch.mock.calls.filter(([url]) =>
    String(url).includes("/me?"),
  ).length;
  await act(async () => (call![0] as () => void)());
  await waitFor(() =>
    expect(
      fetch.mock.calls.filter(([url]) => String(url).includes("/me?")).length,
    ).toBeGreaterThan(before),
  );
  expect(query().get("open")).toBe("10");
  expect(screen.getByText("합성 비공개 본문")).toBeInTheDocument();
});
