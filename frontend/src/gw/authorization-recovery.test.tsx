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
  useNavigate,
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
    meStatus: 0,
    meNetwork: false,
    binding: "ACTIVE",
    bindingVersion: 1,
    bindingId: "77",
    bindingError: false,
    deferBinding: false,
    lateBinding: undefined as undefined | ((r: Response) => void),
    acceptStatus: 0,
    acceptCode: "",
    acceptNetwork: false,
    acceptMalformed: false,
    deferAccept: false,
    lateAccept: undefined as undefined | ((r: Response) => void),
    personActive: true,
    ready: true,
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
        return reply([
          { id: 11, name: "합성 회사" },
          { id: 12, name: "합성 두번째 회사" },
        ]);
      if (path.endsWith("/me")) {
        if (state.meNetwork) throw new TypeError("synthetic network failure");
        if (state.meStatus)
          return reply(
            {
              code: "SYNTHETIC_CONNECTION_ERROR",
              message: "합성 연결 조회 실패",
            },
            state.meStatus,
          );
        return reply({
          company: {
            id: Number(url.searchParams.get("companyId")),
            name: "합성 회사",
          },
          person: {
            id: "501",
            name: "합성 직원",
            isActive: state.personActive,
          },
          bindingStatus: state.binding,
          roles:
            state.binding === "ACTIVE" && state.personActive
              ? ["SECURITY_ADMIN"]
              : [],
          authzVersion: state.version,
          setupRequired: false,
          businessReady: state.ready,
        });
      }
      if (path.endsWith("/me/binding/accept")) {
        if (state.acceptNetwork) throw new TypeError("synthetic lost response");
        if (state.acceptMalformed)
          return new Response("not-json", { status: 200 });
        if (state.acceptStatus)
          return reply(
            {
              code:
                state.acceptCode ||
                (state.acceptStatus === 403
                  ? "STEP_UP_REQUIRED"
                  : "VERSION_CONFLICT"),
              message: "합성 동의 오류",
            },
            state.acceptStatus,
          );
        if (state.deferAccept)
          return new Promise((resolve) => {
            state.lateAccept = resolve;
          });
        state.binding = "ACTIVE";
        return reply({ id: state.bindingId });
      }
      if (path.endsWith("/me/binding")) {
        if (state.bindingError)
          return reply(
            { code: "SYNTHETIC_ERROR", message: "합성 요청 조회 실패" },
            500,
          );
        if (state.deferBinding)
          return new Promise((resolve) => {
            state.lateBinding = resolve;
          });
        return reply({
          id: state.bindingId,
          state: state.binding,
          name: "합성 직원",
          hrEmployeeCode: "SYN-501",
          version: state.bindingVersion,
        });
      }
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
  const navigate = useNavigate();
  return (
    <>
      <output aria-label="current query">{l.search}</output>
      <button onClick={() => navigate("/gw/board?companyId=12")}>
        합성 다른 회사로 전환
      </button>
      <button
        onClick={() =>
          navigate("/gw/pending?companyId=11&open=10&status=IN_REVIEW")
        }
      >
        과거 선택 주소 다시 방문
      </button>
    </>
  );
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
          <Route path="dashboard" element={<p>회사 업무현황</p>} />
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
it.each([403, 404, 500, 0])(
  "connection lookup failure %s clears original and retries without reopening it",
  async (status) => {
    const { state, fetch } = fixture();
    show();
    await screen.findByText("합성 비공개 본문");
    await openApproval();
    state.meStatus = status;
    state.meNetwork = status === 0;
    fireEvent(window, new Event("focus"));
    await screen.findByRole("heading", {
      name: "회사 연결을 확인하지 못했습니다",
    });
    await waitFor(() => expect(query().has("open")).toBe(false));
    expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("합성 미저장 사유"),
    ).not.toBeInTheDocument();
    expect(query().get("companyId")).toBe("11");
    expect(query().get("status")).toBe("IN_REVIEW");
    const meCount = () =>
      fetch.mock.calls.filter(([url]) => String(url).includes("/me?")).length;
    const before = meCount();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    await waitFor(() => expect(meCount()).toBe(before + 1));
    await screen.findByRole("button", { name: "다시 시도" });
    expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
    state.meStatus = 0;
    state.meNetwork = false;
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    await screen.findByRole("button", { name: "합성 비공개 원문" });
    expect(query().has("open")).toBe(false);
    expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
    expect(
      fetch.mock.calls.filter(([, i]) => i?.method === "POST"),
    ).toHaveLength(0);
    expect(auth.fail).not.toHaveBeenCalled();
  },
);
it.each(["SUSPENDED", "CANCELLED", "UNBOUND", "INACTIVE", "NOT_READY"])(
  "same-version connection %s removes selection and only queries on recheck",
  async (mode) => {
    const { state, fetch } = fixture();
    show();
    await screen.findByText("합성 비공개 본문");
    await openApproval();
    if (mode === "INACTIVE") state.personActive = false;
    else if (mode === "NOT_READY") state.ready = false;
    else state.binding = mode;
    fireEvent(window, new Event("focus"));
    await screen.findByRole("button", { name: "회사 연결 다시 확인" });
    await waitFor(() => expect(query().has("open")).toBe(false));
    expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("합성 미저장 사유"),
    ).not.toBeInTheDocument();
    if (mode === "SUSPENDED")
      expect(
        await screen.findByText(/GW 연결이 정지되어 있습니다/),
      ).toBeInTheDocument();
    if (mode === "CANCELLED" || mode === "UNBOUND")
      expect(
        await screen.findByText(
          /GW 조직 관리자에게 직원 연결 요청을 문의하세요/,
        ),
      ).toBeInTheDocument();
    if (mode === "INACTIVE")
      expect(
        await screen.findByText(/GW 직원이 비활성 상태입니다/),
      ).toBeInTheDocument();
    state.binding = "ACTIVE";
    state.personActive = true;
    state.ready = true;
    fireEvent.click(
      screen.getByRole("button", { name: "회사 연결 다시 확인" }),
    );
    await screen.findByRole("button", { name: "합성 비공개 원문" });
    expect(query().get("companyId")).toBe("11");
    expect(query().has("open")).toBe(false);
    expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
    expect(
      fetch.mock.calls.filter(([, i]) => i?.method === "POST"),
    ).toHaveLength(0);
  },
);
it("a connection failure discards a late pending approval result", async () => {
  const { state } = fixture();
  show();
  await screen.findByText("합성 비공개 본문");
  await openApproval();
  state.deferWrite = true;
  fireEvent.click(screen.getByRole("button", { name: "확정" }));
  await waitFor(() => expect(state.lateWrite).toBeDefined());
  state.meStatus = 403;
  fireEvent(window, new Event("focus"));
  await screen.findByRole("heading", {
    name: "회사 연결을 확인하지 못했습니다",
  });
  await waitFor(() => expect(query().has("open")).toBe(false));
  state.meStatus = 0;
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
  const row = await screen.findByRole("button", { name: "합성 비공개 원문" });
  expect(row.closest("section")).not.toHaveAttribute("inert");
  await act(async () =>
    state.lateWrite!(reply({ ...doc, body: "옛 연결 처리 결과" })),
  );
  expect(query().has("open")).toBe(false);
  expect(screen.queryByText("옛 연결 처리 결과")).not.toBeInTheDocument();
});
it("an initial connection failure clears a deep link without issuing business reads or writes", async () => {
  const { state, fetch } = fixture();
  state.meStatus = 403;
  show();
  await screen.findByRole("heading", {
    name: "회사 연결을 확인하지 못했습니다",
  });
  await waitFor(() => expect(query().has("open")).toBe(false));
  expect(
    fetch.mock.calls.filter(([url]) => String(url).includes("/documents")),
  ).toHaveLength(0);
  expect(fetch.mock.calls.filter(([, i]) => i?.method !== "GET")).toHaveLength(
    0,
  );
});
it("a late detail response cannot revive an original after connection failure", async () => {
  const { state, fetch } = fixture();
  show();
  await screen.findByText("합성 비공개 본문");
  state.deferRead = true;
  fireEvent.click(screen.getByRole("button", { name: "서버 상태 다시 확인" }));
  await waitFor(() => expect(state.lateRead).toBeDefined());
  state.meStatus = 500;
  fireEvent(window, new Event("focus"));
  await screen.findByRole("heading", {
    name: "회사 연결을 확인하지 못했습니다",
  });
  const calls = fetch.mock.calls.filter(([url]) =>
    String(url).includes("/documents/10?"),
  );
  expect(calls.at(-1)?.[1]?.signal?.aborted).toBe(true);
  await act(async () =>
    state.lateRead!(reply({ ...doc, body: "옛 연결 지연 원문" })),
  );
  expect(screen.queryByText("옛 연결 지연 원문")).not.toBeInTheDocument();
});
it.each([401, 410])(
  "connection %s follows the existing session failure path",
  async (status) => {
    const { state } = fixture();
    show();
    await screen.findByText("합성 비공개 본문");
    state.meStatus = status;
    fireEvent(window, new Event("focus"));
    await waitFor(() => expect(auth.fail).toHaveBeenCalledTimes(1));
    expect(auth.fail.mock.calls[0][0].status).toBe(status);
    await waitFor(() => expect(query().has("open")).toBe(false));
    expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
  },
);
it("revisiting a stale selection while connection is unavailable cannot restore it", async () => {
  const { state, fetch } = fixture();
  state.meStatus = 403;
  show();
  await screen.findByRole("heading", {
    name: "회사 연결을 확인하지 못했습니다",
  });
  await waitFor(() => expect(query().has("open")).toBe(false));
  fireEvent.click(
    screen.getByRole("button", { name: "과거 선택 주소 다시 방문" }),
  );
  await waitFor(() => expect(query().has("open")).toBe(false));
  expect(
    fetch.mock.calls.filter(([url]) => String(url).includes("/documents")),
  ).toHaveLength(0);
  state.meStatus = 0;
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
  await screen.findByRole("button", { name: "합성 비공개 원문" });
  expect(query().has("open")).toBe(false);
  expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
});

const consentLabel = "위 사번·이름이 본인임을 확인했습니다.";
it("pending refresh clears consent and requires consent to the new request/version", async () => {
  const { state, fetch } = fixture();
  state.binding = "PENDING";
  show();
  fireEvent.click(await screen.findByLabelText(consentLabel));
  expect(screen.getByRole("button", { name: "본인 연결 동의" })).toBeEnabled();
  state.bindingId = "78";
  state.bindingVersion = 2;
  fireEvent.click(
    screen.getByRole("button", { name: "본인 연결 요청 다시 확인" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText(consentLabel)).not.toBeChecked(),
  );
  expect(screen.getByRole("button", { name: "본인 연결 동의" })).toBeDisabled();
  expect(fetch.mock.calls.filter(([, i]) => i?.method === "POST")).toHaveLength(
    0,
  );
  fireEvent.click(screen.getByLabelText(consentLabel));
  fireEvent.click(screen.getByRole("button", { name: "본인 연결 동의" }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([u, i]) =>
          String(u).includes("/me/binding/accept?companyId=11") &&
          JSON.parse(String(i?.body)).bindingId === "78" &&
          JSON.parse(String(i?.body)).expectedVersion === 2,
      ),
    ).toBe(true),
  );
  await waitFor(() =>
    expect(screen.queryByLabelText(consentLabel)).not.toBeInTheDocument(),
  );
});
it.each(["CANCELLED", "SUSPENDED"])(
  "same-version %s removes pending consent on company refresh",
  async (status) => {
    const { state, fetch } = fixture();
    state.binding = "PENDING";
    show();
    fireEvent.click(await screen.findByLabelText(consentLabel));
    state.binding = status;
    fireEvent.click(
      screen.getByRole("button", { name: "회사 연결 다시 확인" }),
    );
    await waitFor(() =>
      expect(screen.queryByLabelText(consentLabel)).not.toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "본인 연결 동의" }),
    ).not.toBeInTheDocument();
    expect(
      fetch.mock.calls.filter(([, i]) => i?.method === "POST"),
    ).toHaveLength(0);
    expect(query().get("companyId")).toBe("11");
  },
);
it("late pending binding response cannot restore consent after cancellation", async () => {
  const { state } = fixture();
  state.binding = "PENDING";
  state.deferBinding = true;
  show();
  await waitFor(() => expect(state.lateBinding).toBeDefined());
  const late = state.lateBinding!;
  state.deferBinding = false;
  state.binding = "CANCELLED";
  fireEvent.click(screen.getByRole("button", { name: "회사 연결 다시 확인" }));
  await screen.findByText(/GW 조직 관리자에게 직원 연결 요청을 문의하세요/);
  await act(async () =>
    late(reply({ id: "77", state: "PENDING", name: "옛 요청", version: 1 })),
  );
  expect(screen.queryByLabelText(consentLabel)).not.toBeInTheDocument();
  expect(screen.queryByText(/옛 요청/)).not.toBeInTheDocument();
});
it("late accept response does not reload the old company after navigation", async () => {
  const { state, fetch } = fixture();
  state.binding = "PENDING";
  state.deferAccept = true;
  show();
  fireEvent.click(await screen.findByLabelText(consentLabel));
  fireEvent.click(screen.getByRole("button", { name: "본인 연결 동의" }));
  await waitFor(() => expect(state.lateAccept).toBeDefined());
  fireEvent.click(
    screen.getByRole("button", { name: "합성 다른 회사로 전환" }),
  );
  await waitFor(() => expect(query().get("companyId")).toBe("12"));
  await screen.findByLabelText(consentLabel);
  const count = fetch.mock.calls.filter(([u]) =>
    String(u).endsWith("/me?companyId=11"),
  ).length;
  await act(async () => state.lateAccept!(reply({ id: "77" })));
  expect(query().get("companyId")).toBe("12");
  expect(screen.getByLabelText(consentLabel)).not.toBeChecked();
  expect(
    fetch.mock.calls.filter(([u]) => String(u).endsWith("/me?companyId=11")),
  ).toHaveLength(count);
});
it("late binding read is aborted and ignored when switching companies", async () => {
  const { state, fetch } = fixture();
  state.binding = "PENDING";
  state.deferBinding = true;
  show();
  await waitFor(() => expect(state.lateBinding).toBeDefined());
  const late = state.lateBinding!;
  const signal = fetch.mock.calls.find(([u]) =>
    String(u).includes("/me/binding?companyId=11"),
  )![1]!.signal!;
  state.deferBinding = false;
  fireEvent.click(
    screen.getByRole("button", { name: "합성 다른 회사로 전환" }),
  );
  await screen.findByLabelText(consentLabel);
  expect(signal.aborted).toBe(true);
  await act(async () =>
    late(
      reply({ id: "old", state: "PENDING", name: "옛 회사 요청", version: 1 }),
    ),
  );
  expect(screen.queryByText(/옛 회사 요청/)).not.toBeInTheDocument();
  expect(query().get("companyId")).toBe("12");
});

it("failed binding refresh hides old request and restores unchecked consent only after retry", async () => {
  const { state, fetch } = fixture();
  state.binding = "PENDING";
  show();
  fireEvent.click(await screen.findByLabelText(consentLabel));
  state.bindingError = true;
  fireEvent.click(
    screen.getByRole("button", { name: "본인 연결 요청 다시 확인" }),
  );
  await screen.findByText("합성 요청 조회 실패");
  expect(screen.queryByLabelText(consentLabel)).not.toBeInTheDocument();
  state.bindingError = false;
  fireEvent.click(
    screen.getByRole("button", { name: "본인 연결 요청 다시 확인" }),
  );
  expect(await screen.findByLabelText(consentLabel)).not.toBeChecked();
  expect(fetch.mock.calls.filter(([, i]) => i?.method === "POST")).toHaveLength(
    0,
  );
});
it("checked consent guards company links and discarding only clears local input", async () => {
  const { state, fetch } = fixture();
  state.binding = "PENDING";
  show();
  fireEvent.click(await screen.findByLabelText(consentLabel));
  fireEvent.click(
    await screen.findByRole("link", { name: "합성 두번째 회사" }),
  );
  await screen.findByText("저장하지 않은 입력이 있습니다.");
  fireEvent.click(screen.getByRole("button", { name: "계속 편집" }));
  expect(query().get("companyId")).toBe("11");
  expect(screen.getByLabelText(consentLabel)).toBeChecked();
  fireEvent.click(screen.getByRole("link", { name: "합성 두번째 회사" }));
  fireEvent.click(screen.getByRole("button", { name: "변경 버리기" }));
  await waitFor(() => expect(query().get("companyId")).toBe("12"));
  expect(await screen.findByLabelText(consentLabel)).not.toBeChecked();
  expect(fetch.mock.calls.filter(([, i]) => i?.method === "POST")).toHaveLength(
    0,
  );
});
it("cancelled company state ignores a late acceptance success without reopening business", async () => {
  const { state } = fixture();
  state.binding = "PENDING";
  state.deferAccept = true;
  show();
  fireEvent.click(await screen.findByLabelText(consentLabel));
  fireEvent.click(screen.getByRole("button", { name: "본인 연결 동의" }));
  await waitFor(() => expect(state.lateAccept).toBeDefined());
  state.binding = "CANCELLED";
  fireEvent.click(screen.getByRole("button", { name: "회사 연결 다시 확인" }));
  await screen.findByText(/GW 조직 관리자에게 직원 연결 요청을 문의하세요/);
  await act(async () => state.lateAccept!(reply({ id: "77" })));
  expect(screen.queryByLabelText(consentLabel)).not.toBeInTheDocument();
  expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
  expect(query().get("companyId")).toBe("11");
});

function acceptCalls(fetch: ReturnType<typeof fixture>["fetch"]) {
  return fetch.mock.calls.filter(
    ([url, init]) =>
      String(url).includes("/me/binding/accept") && init?.method === "POST",
  );
}
const idempotencyKey = (call: ReturnType<typeof acceptCalls>[number]) =>
  (call[1]!.headers as Record<string, string>)["Idempotency-Key"];
async function startConsent() {
  fireEvent.click(await screen.findByLabelText(consentLabel));
  fireEvent.click(screen.getByRole("button", { name: "본인 연결 동의" }));
}
it("acceptance conflict clears consent and requires a fresh request before another POST", async () => {
  const { state, fetch } = fixture();
  state.binding = "PENDING";
  state.acceptStatus = 409;
  show();
  await startConsent();
  await screen.findByText(/연결 요청이 변경되어 동의하지 못했습니다/);
  expect(screen.getByLabelText(consentLabel)).not.toBeChecked();
  expect(screen.getByRole("button", { name: "본인 연결 동의" })).toBeDisabled();
  const first = acceptCalls(fetch)[0];
  state.bindingId = "78";
  state.bindingVersion = 2;
  state.acceptStatus = 0;
  fireEvent.click(
    screen.getByRole("button", { name: "본인 연결 요청 다시 확인" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText(consentLabel)).toBeEnabled(),
  );
  expect(acceptCalls(fetch)).toHaveLength(1);
  await startConsent();
  await waitFor(() => expect(acceptCalls(fetch)).toHaveLength(2));
  const second = acceptCalls(fetch)[1];
  expect(JSON.parse(String(second[1]!.body))).toEqual({
    bindingId: "78",
    expectedVersion: 2,
  });
  expect(idempotencyKey(second)).not.toBe(idempotencyKey(first));
});
it("step-up keeps consent and company scope and does not auto-submit", async () => {
  const { state, fetch } = fixture();
  state.binding = "PENDING";
  state.acceptStatus = 403;
  show();
  await startConsent();
  await screen.findByText(/추가 본인 확인이 필요합니다. 내 계정 보안/);
  expect(screen.getByLabelText(consentLabel)).toBeChecked();
  expect(screen.getByRole("button", { name: "본인 연결 동의" })).toBeEnabled();
  expect(query().get("companyId")).toBe("11");
  expect(
    screen.queryByRole("button", { name: "권한과 연결 다시 확인" }),
  ).not.toBeInTheDocument();
  expect(acceptCalls(fetch)).toHaveLength(1);
  state.acceptStatus = 0;
  fireEvent.click(screen.getByRole("button", { name: "본인 연결 동의" }));
  await waitFor(() => expect(acceptCalls(fetch)).toHaveLength(2));
  expect(acceptCalls(fetch)[1][1]!.body).toBe(acceptCalls(fetch)[0][1]!.body);
});
it.each(["network", "server", "malformed"])(
  "%s uncertain response retries exact original body/key after GET changes request",
  async (failure) => {
    const { state, fetch } = fixture();
    state.binding = "PENDING";
    state.acceptNetwork = failure === "network";
    state.acceptStatus = failure === "server" ? 500 : 0;
    state.acceptMalformed = failure === "malformed";
    show();
    await startConsent();
    await screen.findByRole("button", { name: "같은 동의 요청 결과 확인" });
    const first = acceptCalls(fetch)[0];
    expect(idempotencyKey(first)).toBeTruthy();
    state.bindingId = "78";
    state.bindingVersion = 2;
    fireEvent.click(
      screen.getByRole("button", { name: "본인 연결 요청 다시 확인" }),
    );
    await waitFor(() =>
      expect(screen.getByLabelText(consentLabel)).not.toBeChecked(),
    );
    expect(screen.getByLabelText(consentLabel)).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "본인 연결 동의" }),
    ).toBeDisabled();
    expect(acceptCalls(fetch)).toHaveLength(1);
    state.acceptNetwork = state.acceptMalformed = false;
    state.acceptStatus = 0;
    fireEvent.click(
      screen.getByRole("button", { name: "같은 동의 요청 결과 확인" }),
    );
    await waitFor(() => expect(acceptCalls(fetch)).toHaveLength(2));
    const second = acceptCalls(fetch)[1];
    expect(second[0]).toBe(first[0]);
    expect(second[1]!.body).toBe(first[1]!.body);
    expect(idempotencyKey(second)).toBe(idempotencyKey(first));
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "같은 동의 요청 결과 확인" }),
      ).not.toBeInTheDocument(),
    );
  },
);
it("uncertain consent blocks company link navigation and a second uncertain reply keeps its key", async () => {
  const { state, fetch } = fixture();
  state.binding = "PENDING";
  state.acceptNetwork = true;
  show();
  await startConsent();
  await screen.findByRole("button", { name: "같은 동의 요청 결과 확인" });
  fireEvent.click(
    screen.getByRole("button", { name: "본인 연결 요청 다시 확인" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText(consentLabel)).not.toBeChecked(),
  );
  fireEvent.click(screen.getByRole("link", { name: "합성 두번째 회사" }));
  fireEvent.click(screen.getByRole("button", { name: "변경 버리기" }));
  expect(query().get("companyId")).toBe("11");
  expect(acceptCalls(fetch)).toHaveLength(1);
  fireEvent.click(
    screen.getByRole("button", { name: "같은 동의 요청 결과 확인" }),
  );
  await screen.findByRole("button", { name: "같은 동의 요청 결과 확인" });
  expect(acceptCalls(fetch)).toHaveLength(2);
  expect(idempotencyKey(acceptCalls(fetch)[1])).toBe(
    idempotencyKey(acceptCalls(fetch)[0]),
  );
});
it("pending acceptance blocks double submit, request refresh, checkbox and company links", async () => {
  const { state, fetch } = fixture();
  state.binding = "PENDING";
  state.deferAccept = true;
  show();
  await startConsent();
  await waitFor(() => expect(state.lateAccept).toBeDefined());
  expect(screen.getByLabelText(consentLabel)).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "본인 연결 요청 다시 확인" }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "본인 연결 동의" }));
  fireEvent.click(screen.getByRole("link", { name: "합성 두번째 회사" }));
  expect(query().get("companyId")).toBe("11");
  expect(acceptCalls(fetch)).toHaveLength(1);
  await act(async () => state.lateAccept!(reply({ id: "77" })));
});
it("uncertain original attempt resolved as conflict releases retry and requires current request consent", async () => {
  const { state } = fixture();
  state.binding = "PENDING";
  state.acceptNetwork = true;
  show();
  await startConsent();
  await screen.findByRole("button", { name: "같은 동의 요청 결과 확인" });
  state.acceptNetwork = false;
  state.acceptStatus = 409;
  fireEvent.click(
    screen.getByRole("button", { name: "같은 동의 요청 결과 확인" }),
  );
  await screen.findByText(/연결 요청이 변경되어 동의하지 못했습니다/);
  expect(
    screen.queryByRole("button", { name: "같은 동의 요청 결과 확인" }),
  ).not.toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: "본인 연결 요청 다시 확인" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText(consentLabel)).toBeEnabled(),
  );
  expect(screen.getByLabelText(consentLabel)).not.toBeChecked();
});

it.each([401, 410, 403])(
  "acceptance %s preserves session/permission failure boundaries",
  async (status) => {
    const { state, fetch } = fixture();
    state.binding = "PENDING";
    state.acceptStatus = status;
    state.acceptCode = "GW_PERMISSION_DENIED";
    show();
    await startConsent();
    if (status === 403) {
      await screen.findByRole("button", { name: "권한과 연결 다시 확인" });
      expect(screen.queryByLabelText(consentLabel)).not.toBeInTheDocument();
      expect(auth.fail).not.toHaveBeenCalled();
    } else {
      await waitFor(() => expect(auth.fail).toHaveBeenCalledTimes(1));
    }
    expect(
      screen.queryByRole("button", { name: "같은 동의 요청 결과 확인" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
    expect(acceptCalls(fetch)).toHaveLength(1);
  },
);
it("permission failure resolving an uncertain retry cannot restore consent or business", async () => {
  const { state, fetch } = fixture();
  state.binding = "PENDING";
  state.acceptNetwork = true;
  show();
  await startConsent();
  await screen.findByRole("button", { name: "같은 동의 요청 결과 확인" });
  state.acceptNetwork = false;
  state.acceptStatus = 404;
  state.acceptCode = "GW_NOT_FOUND";
  fireEvent.click(
    screen.getByRole("button", { name: "같은 동의 요청 결과 확인" }),
  );
  await screen.findByRole("button", { name: "권한과 연결 다시 확인" });
  expect(screen.queryByLabelText(consentLabel)).not.toBeInTheDocument();
  expect(screen.queryByText("합성 비공개 본문")).not.toBeInTheDocument();
  expect(idempotencyKey(acceptCalls(fetch)[1])).toBe(
    idempotencyKey(acceptCalls(fetch)[0]),
  );
});
it("failed GET after uncertain acceptance retains the original explicit result retry", async () => {
  const { state, fetch } = fixture();
  state.binding = "PENDING";
  state.acceptNetwork = true;
  show();
  await startConsent();
  await screen.findByRole("button", { name: "같은 동의 요청 결과 확인" });
  state.bindingError = true;
  fireEvent.click(
    screen.getByRole("button", { name: "본인 연결 요청 다시 확인" }),
  );
  await waitFor(() =>
    expect(screen.queryByLabelText(consentLabel)).not.toBeInTheDocument(),
  );
  await screen.findByText("합성 요청 조회 실패");
  expect(
    screen.getByRole("button", { name: "같은 동의 요청 결과 확인" }),
  ).toBeEnabled();
  expect(acceptCalls(fetch)).toHaveLength(1);
  state.acceptNetwork = false;
  state.acceptStatus = 409;
  fireEvent.click(
    screen.getByRole("button", { name: "같은 동의 요청 결과 확인" }),
  );
  await screen.findByText(/연결 요청이 변경되어 동의하지 못했습니다/);
  expect(acceptCalls(fetch)[1][1]!.body).toBe(acceptCalls(fetch)[0][1]!.body);
});

it("step-up during uncertain retry preserves original key and blocks a new request until explicit resolution", async () => {
  const { state, fetch } = fixture();
  state.binding = "PENDING";
  state.acceptNetwork = true;
  show();
  await startConsent();
  await screen.findByRole("button", { name: "같은 동의 요청 결과 확인" });
  const first = acceptCalls(fetch)[0];
  state.acceptNetwork = false;
  state.acceptStatus = 403;
  fireEvent.click(
    screen.getByRole("button", { name: "같은 동의 요청 결과 확인" }),
  );
  const security = await screen.findByRole("link", {
    name: "다른 탭에서 내 계정 보안 열기",
  });
  expect(security).toHaveAttribute("href", "/account/security");
  expect(security).toHaveAttribute("target", "_blank");
  expect(
    screen.getByRole("button", { name: "같은 동의 요청 결과 확인" }),
  ).toBeEnabled();
  expect(screen.getByRole("button", { name: "본인 연결 동의" })).toBeDisabled();
  state.bindingId = "78";
  state.bindingVersion = 2;
  fireEvent.click(
    screen.getByRole("button", { name: "본인 연결 요청 다시 확인" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText(consentLabel)).not.toBeChecked(),
  );
  expect(acceptCalls(fetch)).toHaveLength(2);
  state.acceptStatus = 0;
  fireEvent.click(
    screen.getByRole("button", { name: "같은 동의 요청 결과 확인" }),
  );
  await waitFor(() => expect(acceptCalls(fetch)).toHaveLength(3));
  for (const call of acceptCalls(fetch)) {
    expect(call[1]!.body).toBe(first[1]!.body);
    expect(idempotencyKey(call)).toBe(idempotencyKey(first));
  }
});
