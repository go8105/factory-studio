import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { CompanyContext, RoleContext } from "./common";
import { Masters } from "./Masters";
import { Board } from "./Board";
import { MissingGwPage, NoRole } from "./ui";
vi.mock("../app/session", () => ({
  useSession: () => ({
    session: { workspaceId: 1, generationId: 2, csrfToken: "synthetic" },
    fail: vi.fn(),
  }),
}));
afterEach(() => vi.restoreAllMocks());
const reply = (data: unknown) => new Response(JSON.stringify({ data }));
function Location() {
  const location = useLocation();
  return <output aria-label="current query">{location.search}</output>;
}
function show(node: ReactNode, companyId?: string, search = "") {
  return render(
    <MemoryRouter
      initialEntries={[
        "/gw/routes?" + (companyId ? `companyId=${companyId}&` : "") + search,
      ]}
    >
      <CompanyContext.Provider value={{ companyId }}>
        <RoleContext.Provider
          value={{
            person: "501",
            people: [],
            setPerson: vi.fn(),
            reload: vi.fn(),
            companyId,
            roles: [],
          }}
        >
          {node}
          <Location />
        </RoleContext.Provider>
      </CompanyContext.Provider>
    </MemoryRouter>,
  );
}
it.each(["11", undefined])(
  "empty GW lists and missing pages return within scope %s",
  async (companyId) => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      reply({ rows: [], total: 0 }),
    );
    for (const node of [
      <Masters kind="routes" />,
      <Board />,
      <MissingGwPage />,
    ]) {
      const view = show(node, companyId);
      expect(
        await screen.findByRole("link", { name: "GW 업무로 돌아가기 →" }),
      ).toHaveAttribute(
        "href",
        companyId ? "/gw/dashboard?companyId=11" : "/gw/dashboard",
      );
      expect(
        screen.queryByRole("link", { name: "앱 런처로 →" }),
      ).not.toBeInTheDocument();
      view.unmount();
    }
  },
);
it.each(["11", undefined])(
  "search and pagination preserve scope and reset only the offset %s",
  async (companyId) => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      reply({
        rows: [{ id: "1", code: "SYN", name: "synthetic", isActive: true }],
        total: 41,
      }),
    );
    show(
      <Masters kind="routes" />,
      companyId,
      "search=old&offset=20&marker=keep",
    );
    await screen.findByText("synthetic");
    fireEvent.change(screen.getByLabelText("검색"), {
      target: { value: "new" },
    });
    await waitFor(() =>
      expect(
        new URLSearchParams(
          screen.getByLabelText("current query").textContent!,
        ).get("search"),
      ).toBe("new"),
    );
    let query = new URLSearchParams(
      screen.getByLabelText("current query").textContent!,
    );
    expect(query.get("companyId")).toBe(companyId ?? null);
    expect(query.has("offset")).toBe(false);
    expect(query.get("marker")).toBe("keep");
    await waitFor(() =>
      expect(
        fetch.mock.calls.some(([url]) => String(url).includes("search=new")),
      ).toBe(true),
    );
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    await waitFor(() =>
      expect(
        new URLSearchParams(
          screen.getByLabelText("current query").textContent!,
        ).get("offset"),
      ).toBe("20"),
    );
    query = new URLSearchParams(
      screen.getByLabelText("current query").textContent!,
    );
    expect(query.get("companyId")).toBe(companyId ?? null);
    expect(query.get("search")).toBe("new");
    expect(query.get("marker")).toBe("keep");
    await waitFor(() =>
      expect(
        fetch.mock.calls.some(
          ([url]) =>
            String(url).includes("offset=20") &&
            String(url).includes("search=new"),
        ),
      ).toBe(true),
    );
    for (const [url, init] of fetch.mock.calls) {
      expect(init?.method ?? "GET").toBe("GET");
      const params = new URL(String(url), "http://localhost").searchParams;
      expect(params.get("companyId")).toBe(companyId ?? null);
    }
  },
);
it("a read-only company route role has no enabled create action", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
    reply({ rows: [], total: 0 }),
  );
  show(<Masters kind="routes" />, "11");
  await screen.findByRole("link", { name: "GW 업무로 돌아가기 →" });
  expect(screen.getByRole("button", { name: "등록" })).toBeDisabled();
});
it("personal missing-person guidance still leads to personal registration", () => {
  show(<NoRole />);
  expect(
    screen.getByRole("link", { name: "체험 담당자 등록 →" }),
  ).toHaveAttribute("href", "/gw/people");
});
