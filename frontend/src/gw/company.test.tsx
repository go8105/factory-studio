import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import {
  CompanyContext,
  RoleContext,
  companyPath,
  useGet,
  useSend,
} from "./common";
import { CompanyStart, type CompanyMe } from "./Company";
import { RoleBar } from "./ui";
import { Documents } from "./Documents";
import type { ReactNode } from "react";

vi.mock("../app/session", () => ({
  useSession: () => ({
    session: {
      actorKind: "MEMBER",
      workspaceId: 1,
      generationId: 2,
      csrfToken: "synthetic",
    },
    fail: vi.fn(),
  }),
}));
const response = (data: unknown) =>
  new Response(JSON.stringify({ data }), { status: 200 });
beforeEach(() => vi.restoreAllMocks());
const Wrapper = ({ children }: { children: ReactNode }) => (
  <CompanyContext.Provider value={{ companyId: "11", epoch: 1 }}>
    <RoleContext.Provider
      value={{
        person: "501",
        setPerson: vi.fn(),
        people: [],
        reload: vi.fn(),
        companyId: "11",
      }}
    >
      {children}
    </RoleContext.Provider>
  </CompanyContext.Provider>
);

it("scopes GW paths and preserves external solution independence", () => {
  expect(companyPath("/documents?personId=500&box=pending", "11")).toBe(
    "/documents?box=pending&companyId=11",
  );
  expect(companyPath("/api/v1/hr/employees?limit=1", "11")).toBe(
    "/api/v1/hr/employees?limit=1",
  );
  expect(companyPath("/companies", "11")).toBe("/companies");
  expect(companyPath("/documents?personId=500")).toBe(
    "/documents?personId=500",
  );
  expect(companyPath("/documents", "")).toBe("/documents?companyId=");
});

it.each(["drafts", "pending", "archive"] as const)(
  "%s empty-state route keeps the selected company and personal scope",
  async (box) => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      response({ rows: [], total: 0 }),
    );
    const company = render(
      <MemoryRouter>
        <Wrapper>
          <Documents box={box} />
        </Wrapper>
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole("link", { name: "결재선 관리 →" }),
    ).toHaveAttribute("href", "/gw/routes?companyId=11");
    company.unmount();
    render(
      <MemoryRouter>
        <RoleContext.Provider
          value={{
            person: "501",
            setPerson: vi.fn(),
            people: [],
            reload: vi.fn(),
          }}
        >
          <Documents box={box} />
        </RoleContext.Provider>
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole("link", { name: "결재선 관리 →" }),
    ).toHaveAttribute("href", "/gw/routes");
  },
);

it("aborts an earlier company's GET and rejects its late response", async () => {
  let oldResolve: (r: Response) => void = () => {};
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input) =>
      String(input).includes("companyId=11")
        ? new Promise((resolve) => (oldResolve = resolve))
        : response({ company: "B" }),
    );
  function Probe() {
    const data = useGet<{ company: string }>("/documents");
    return <p>{data.data?.company}</p>;
  }
  const h = render(
    <CompanyContext.Provider value={{ companyId: "11" }}>
      <Probe />
    </CompanyContext.Provider>,
  );
  h.rerender(
    <CompanyContext.Provider value={{ companyId: "12" }}>
      <Probe />
    </CompanyContext.Provider>,
  );
  await screen.findByText("B", { exact: true });
  await act(async () => oldResolve(response({ company: "A" })));
  expect(screen.queryByText("A", { exact: true })).not.toBeInTheDocument();
  expect((fetch.mock.calls[0][1]?.signal as AbortSignal).aborted).toBe(true);
});

it("strips the simulation actor and retries uncertain company writes with the same key", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockRejectedValueOnce(new TypeError("synthetic connection loss"))
    .mockResolvedValue(response({ saved: true }));
  const h = renderHook(() => useSend(), { wrapper: Wrapper });
  await act(async () => {
    await h.result.current.send("/documents", "POST", {
      actingPersonId: "501",
      title: "합성",
    });
  });
  const original = fetch.mock.calls[0][1];
  expect(String(fetch.mock.calls[0][0])).toContain("companyId=11");
  expect(JSON.parse(original!.body as string)).toEqual({ title: "합성" });
  await act(async () => {
    await h.result.current.send("/documents", "POST", {
      actingPersonId: "501",
      title: "다른 본문",
    });
  });
  expect(fetch).toHaveBeenCalledTimes(1);
  await act(async () => {
    await h.result.current.send("/documents", "POST", {
      actingPersonId: "501",
      title: "합성",
    });
  });
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[1][1]?.headers).toEqual(original?.headers);
});

it("does not deliver a write result after the company screen unmounts", async () => {
  let resolve: (r: Response) => void = () => {};
  vi.spyOn(globalThis, "fetch").mockImplementation(
    () => new Promise((r) => (resolve = r)),
  );
  const h = renderHook(() => useSend(), { wrapper: Wrapper });
  let pending: Promise<unknown>;
  act(() => {
    pending = h.result.current.send("/documents", "POST", { title: "합성" });
  });
  h.unmount();
  let result;
  await act(async () => {
    resolve(response({ private: "old-company" }));
    result = await pending;
  });
  expect(result).toBeUndefined();
});

it("company role bar never renders the simulation actor selector", () => {
  render(
    <Wrapper>
      <MemoryRouter>
        <RoleBar />
      </MemoryRouter>
    </Wrapper>,
  );
  expect(screen.queryByLabelText("담당자 역할 체험")).not.toBeInTheDocument();
  expect(
    screen.getByText(/다른 직원의 역할로 전환할 수 없습니다/),
  ).toBeInTheDocument();
});

it("requires confirmation of the pending self identity before consent", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, options) =>
      options?.method === "POST"
        ? response({ state: "ACTIVE" })
        : response({
            id: "77",
            version: 1,
            state: "PENDING",
            name: "합성 직원",
            hrEmployeeCode: "SYN-02",
            organizationName: "합성 조직",
          }),
    );
  const me = {
    company: { id: 11, name: "합성 회사" },
    person: null,
    bindingStatus: "PENDING",
    roles: [],
    authzVersion: 1,
    setupRequired: false,
    companyOwner: false,
    hrIdentityAvailable: true,
    businessReady: false,
  } as CompanyMe;
  render(
    <Wrapper>
      <MemoryRouter>
        <CompanyStart me={me} reload={vi.fn()} />
      </MemoryRouter>
    </Wrapper>,
  );
  await screen.findByText(/SYN-02/);
  expect(screen.getByRole("button", { name: "본인 연결 동의" })).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "본인 연결 동의" }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([, options]) => options?.method === "POST"),
    ).toBe(true),
  );
  const call = fetch.mock.calls.find(
    ([, options]) => options?.method === "POST",
  )!;
  expect(JSON.parse(call[1]!.body as string)).toEqual({
    bindingId: "77",
    expectedVersion: 1,
  });
});
