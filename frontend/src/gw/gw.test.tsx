import {
  act,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { DataTable } from "../shared/components";
import { RoleContext, useGet, useSend } from "./common";
import { NoRole, RoleBar } from "./ui";
const state = vi.hoisted(() => ({
  session: { workspaceId: 1, generationId: 2, csrfToken: "synthetic" },
  fail: vi.fn(),
}));
vi.mock("../app/session", () => ({ useSession: () => state }));
beforeEach(() => {
  state.session = { workspaceId: 1, generationId: 2, csrfToken: "synthetic" };
});
const response = (data: unknown) =>
  new Response(JSON.stringify({ data }), { status: 200 });
it("an old GET cannot replace a new role response", async () => {
  let resolveOld: (r: Response) => void = () => {};
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
    String(input).endsWith("old")
      ? new Promise((resolve) => {
          resolveOld = resolve;
        })
      : response({ name: "new" }),
  );
  const h = renderHook(({ path }) => useGet<{ name: string }>(path), {
    initialProps: { path: "/old" },
  });
  h.rerender({ path: "/new" });
  await waitFor(() => expect(h.result.current.data?.name).toBe("new"));
  await act(async () => resolveOld(response({ name: "old" })));
  expect(h.result.current.data?.name).toBe("new");
});
it("a generation change hides the prior generation before refetch", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(response({ name: "previous" }))
    .mockImplementation(() => new Promise(() => {}));
  const h = renderHook(() => useGet<{ name: string }>("/documents/1"));
  await waitFor(() => expect(h.result.current.data?.name).toBe("previous"));
  state.session = { ...state.session, generationId: 3 };
  h.rerender();
  expect(h.result.current.data).toBeUndefined();
});
it("uncertain mutation retries the same key and blocks a concurrent click", async () => {
  let finish: (r: Response) => void = () => {};
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockRejectedValueOnce(new TypeError("lost"))
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
  const h = renderHook(() => useSend());
  await act(async () => {
    await h.result.current.send("/documents/1/approve", "POST", {
      expectedVersion: 1,
    });
  });
  let pending: Promise<unknown>;
  act(() => {
    pending = h.result.current.send("/documents/1/approve", "POST", {
      expectedVersion: 1,
    });
  });
  await act(async () => {
    expect(
      await h.result.current.send("/documents/1/approve", "POST", {
        expectedVersion: 1,
      }),
    ).toBeUndefined();
  });
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[0][1]?.headers).toEqual(
    fetch.mock.calls[1][1]?.headers,
  );
  await act(async () => {
    finish(response({ version: 2 }));
    await pending;
  });
  expect(h.result.current.pending).toBe(false);
});
it("string IDs keep bigint precision and user text is not executed", () => {
  render(
    <MemoryRouter>
      <DataTable
        rows={[
          { id: "9223372036854775806", title: "<script>alert(1)</script>" },
        ]}
        columns={[
          { key: "id", label: "ID" },
          { key: "title", label: "제목" },
        ]}
        caption="GW 문서"
        offset={0}
        limit={20}
        total={1}
        onPage={() => {}}
      />
    </MemoryRouter>,
  );
  expect(
    screen.getByRole("cell", { name: "9223372036854775806" }),
  ).toBeVisible();
  expect(
    screen.getByRole("cell", { name: "<script>alert(1)</script>" }),
  ).toBeVisible();
  expect(document.querySelector("script")).toBeNull();
});
it("a failed role lookup is not presented as an empty setup", () => {
  render(
    <MemoryRouter>
      <RoleContext.Provider
        value={{
          person: "",
          people: [],
          setPerson: () => {},
          reload: () => {},
          error: new Error("failed"),
        }}
      >
        <RoleBar />
        <NoRole />
      </RoleContext.Provider>
    </MemoryRouter>,
  );
  expect(screen.queryByText("체험 담당자 먼저 등록")).toBeNull();
  expect(screen.getByText(/담당자 조회를 완료하지 못했습니다/)).toBeVisible();
});
