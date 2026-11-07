import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { App } from "../app/App";
import { SessionProvider, useSession } from "../app/session";
import { FavoritesProvider, type Preferences } from "../shared/favorites";
import { SolutionLayout } from "../shared/SolutionLayout";
import { defaultMenuIds, mesScreens, menuCatalog } from "../shared/menuCatalog";

const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-10-11T00:00:00+09:00",
  csrfToken: "synthetic-csrf",
};
const modules = [
  "core",
  "mes",
  "erp",
  "gw",
  "wms",
  "hr",
  "fems",
  "bems",
  "qms",
  "spc",
].map((moduleKey) => ({ moduleKey, enabled: true, updatedAt: null }));
function response(data: unknown, status = 200) {
  return new Response(
    JSON.stringify(status === 200 ? { data } : { error: data }),
    { status },
  );
}
type Handler = (
  body: {
    menuIds: string[];
    sidebarMode: Preferences["sidebarMode"];
    expectedVersion: number;
  },
  options?: RequestInit,
) => Response | Promise<Response> | undefined;
function mock(
  initial: Preferences = {
    menuIds: [...defaultMenuIds],
    sidebarMode: "favorites",
    version: 1,
  },
  handler?: Handler,
) {
  let stored = initial;
  const calls: { body: unknown; key: string | null }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, options) => {
    const path = String(input).replace("/api/v1/core", "");
    if (path === "/sessions/current") return response(session);
    if (path === "/workspace/modules") return response(modules);
    if (path === "/workspace")
      return response({
        id: 10,
        workspaceKind: "GUEST",
        configVersion: 1,
        expiresAt: session.expiresAt,
        createdAt: "2026-10-10",
      });
    if (path === "/workspace/menus" && options?.method === "PUT") {
      const body = JSON.parse(String(options.body));
      calls.push({
        body,
        key: new Headers(options.headers).get("Idempotency-Key"),
      });
      const custom = handler?.(body, options);
      if (custom) return custom;
      stored = {
        menuIds: body.menuIds,
        sidebarMode: body.sidebarMode,
        version: stored.version + 1,
      };
      return response(stored);
    }
    if (path === "/workspace/menus") return response(stored);
    return response({});
  });
  return {
    calls,
    get: () => stored,
    change: (value: Preferences) => {
      stored = value;
    },
  };
}
function workspace() {
  render(
    <MemoryRouter initialEntries={["/workspace"]}>
      <App />
    </MemoryRouter>,
  );
}
function OtherOperation() {
  const { setNavigationBlocked } = useSession();
  return (
    <>
      <button onClick={() => setNavigationBlocked(true)}>
        다른 업무 작업 시작
      </button>
      <button onClick={() => setNavigationBlocked(false)}>
        다른 업무 작업 종료
      </button>
    </>
  );
}
function sidebar() {
  render(
    <MemoryRouter initialEntries={["/mes/work-orders"]}>
      <SessionProvider>
        <OtherOperation />
        <FavoritesProvider>
          <Routes>
            <Route
              path="/mes"
              element={
                <SolutionLayout
                  name="MES"
                  title="MES 생산관리"
                  base="/mes"
                  screens={mesScreens}
                  others={[]}
                />
              }
            >
              <Route path="work-orders" element={<h1>작업지시 본문</h1>} />
            </Route>
          </Routes>
        </FavoritesProvider>
      </SessionProvider>
    </MemoryRouter>,
  );
}
async function open() {
  fireEvent.click(
    (await screen.findAllByRole("button", { name: "메뉴 추가" }))[0],
  );
  return screen.findByRole("dialog", { name: "내 공간에 메뉴 추가" });
}
beforeEach(() => {
  localStorage.clear();
  for (const method of ["showModal", "close"] as const) {
    if (!(method in HTMLDialogElement.prototype)) {
      Object.defineProperty(HTMLDialogElement.prototype, method, {
        configurable: true,
        writable: true,
        value: () => {},
      });
    }
  }
  vi.spyOn(HTMLDialogElement.prototype, "showModal").mockImplementation(
    function (this: HTMLDialogElement) {
      this.setAttribute("open", "");
    },
  );
  vi.spyOn(HTMLDialogElement.prototype, "close").mockImplementation(function (
    this: HTMLDialogElement,
  ) {
    this.removeAttribute("open");
  });
});

it("152개 실제 메뉴는 고유한 경로와 등록 키를 갖는다", () => {
  expect(menuCatalog).toHaveLength(152);
  expect(new Set(menuCatalog.map((m) => m.key)).size).toBe(152);
  expect(new Set(menuCatalog.map((m) => m.to)).size).toBe(152);
  expect(
    defaultMenuIds.every((key) => menuCatalog.some((m) => m.key === key)),
  ).toBe(true);
});

it("기본 카드와 솔루션별 빈 상태를 표시한다", async () => {
  mock();
  workspace();
  expect(await screen.findByRole("link", { name: /기안함/ })).toHaveAttribute(
    "href",
    "/gw/drafts",
  );
  expect(screen.getByText("선택한 메뉴 6개")).toBeInTheDocument();
  fireEvent.click(
    within(screen.getByLabelText("즐겨찾기 솔루션 필터")).getByRole("button", {
      name: "ERP",
    }),
  );
  expect(
    screen.getByText("이 솔루션에 등록된 메뉴가 없습니다."),
  ).toBeInTheDocument();
});

it("실제 ERP 메뉴를 검색·선택·저장하고 카드로 연결한다", async () => {
  const store = mock();
  workspace();
  await screen.findByRole("link", { name: /기안함/ });
  const dialog = await open();
  fireEvent.click(within(dialog).getByRole("button", { name: /^ERP/ }));
  fireEvent.change(within(dialog).getByRole("textbox", { name: "메뉴 검색" }), {
    target: { value: "매입" },
  });
  fireEvent.click(within(dialog).getByRole("checkbox", { name: /매입 전표/ }));
  fireEvent.click(
    within(dialog).getByRole("button", { name: "내 공간에 적용" }),
  );
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  expect(store.get().menuIds).toContain("erp:purchase-invoices");
  expect(screen.getByRole("link", { name: /매입 전표/ })).toHaveAttribute(
    "href",
    "/erp/purchase-invoices",
  );
});

it("취소는 임시 선택을 버리고 서버 구성을 유지한다", async () => {
  const store = mock();
  workspace();
  await screen.findByRole("link", { name: /기안함/ });
  const dialog = await open();
  fireEvent.click(within(dialog).getByRole("checkbox", { name: /기안함/ }));
  fireEvent.click(within(dialog).getByRole("button", { name: "취소" }));
  expect(store.calls).toHaveLength(0);
  expect(screen.getByRole("link", { name: /기안함/ })).toBeInTheDocument();
});

it("순서 편집을 키보드로 할 수 있는 버튼으로 저장한다", async () => {
  const store = mock();
  workspace();
  await screen.findByRole("link", { name: /기안함/ });
  fireEvent.click(screen.getByRole("button", { name: "순서·구성 편집" }));
  const dialog = await screen.findByRole("dialog");
  fireEvent.click(
    within(dialog).getByRole("button", { name: "기안함 아래로 이동" }),
  );
  fireEvent.click(
    within(dialog).getByRole("button", { name: "내 공간에 적용" }),
  );
  await waitFor(() => expect(store.get().menuIds[0]).toBe("gw:pending"));
  expect(store.get().menuIds[1]).toBe("gw:drafts");
});

it("MES 사이드바는 등록 메뉴만 표시하고 전체 메뉴에서 새 항목을 등록한다", async () => {
  const store = mock({
    menuIds: ["mes:work-orders", "gw:pending", "wms:dashboard"],
    sidebarMode: "favorites",
    version: 1,
  });
  sidebar();
  const aside = await screen.findByLabelText("MES 메뉴");
  await waitFor(() =>
    expect(
      within(aside).getByRole("button", { name: "즐겨찾기만 보기" }),
    ).toHaveAttribute("aria-pressed", "true"),
  );
  expect(
    within(aside).getByRole("link", { name: /M-03 작업지시/ }),
  ).toBeInTheDocument();
  expect(
    within(aside).getByRole("link", { name: /G-03 결재함/ }),
  ).toHaveAttribute("href", "/gw/pending");
  expect(within(aside).getByRole("link", { name: /W-01/ })).toHaveAttribute(
    "href",
    "/wms/dashboard",
  );
  fireEvent.click(within(aside).getByRole("button", { name: "메뉴 접기" }));
  expect(
    within(aside).getByRole("link", { name: /G-03 결재함/ }),
  ).toBeInTheDocument();
  fireEvent.click(within(aside).getByRole("button", { name: "메뉴 펼치기" }));
  expect(
    within(aside).queryByRole("link", { name: /M-12 품목/ }),
  ).not.toBeInTheDocument();
  fireEvent.click(
    within(aside).getByRole("button", { name: "전체 메뉴 보기" }),
  );
  await within(aside).findByRole("link", { name: /M-12 품목/ });
  fireEvent.click(
    within(aside).getByRole("button", { name: "MES LOT 현황 즐겨찾기 등록" }),
  );
  await waitFor(() =>
    expect(store.get().menuIds).toEqual([
      "mes:work-orders",
      "gw:pending",
      "wms:dashboard",
      "mes:lots",
    ]),
  );
  await waitFor(() =>
    expect(
      within(aside).getByRole("button", { name: "즐겨찾기만 보기" }),
    ).toBeEnabled(),
  );
  fireEvent.click(
    within(aside).getByRole("button", { name: "즐겨찾기만 보기" }),
  );
  await waitFor(() =>
    expect(
      within(aside).queryByRole("link", { name: /M-12 품목/ }),
    ).not.toBeInTheDocument(),
  );
  expect(
    within(aside).getByRole("link", { name: /M-04 LOT 현황/ }),
  ).toBeInTheDocument();
});

it("불확실한 저장은 같은 본문·키로 재시도하며 임시 편집과 이동을 잠근다", async () => {
  let count = 0;
  const store = mock(undefined, (body) => {
    count++;
    if (count === 1)
      return Promise.reject(new TypeError("synthetic lost reply"));
    return response({
      menuIds: body.menuIds,
      sidebarMode: body.sidebarMode,
      version: 2,
    });
  });
  workspace();
  await screen.findByRole("link", { name: /기안함/ });
  const dialog = await open();
  fireEvent.click(within(dialog).getByRole("checkbox", { name: /기안함/ }));
  fireEvent.click(
    within(dialog).getByRole("button", { name: "내 공간에 적용" }),
  );
  const retry = await within(dialog).findByRole("button", {
    name: "동일 요청 다시 적용",
  });
  expect(within(dialog).getByRole("button", { name: "취소" })).toBeDisabled();
  // 앱 런처는 헤더 전환기 안으로 들어갔다. 늘 보이는 브랜드 링크로 같은 차단을 확인한다.
  fireEvent.click(screen.getByRole("link", { name: /Factory Studio/ }));
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  fireEvent.click(retry);
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  expect(store.calls).toHaveLength(2);
  expect(store.calls[0]).toEqual(store.calls[1]);
});

it("최근 방문한 실제 메뉴를 브라우저의 현재 공간 키에 보관한다", async () => {
  mock({ menuIds: ["mes:work-orders"], sidebarMode: "favorites", version: 1 });
  sidebar();
  await screen.findByRole("heading", { name: "작업지시 본문" });
  await waitFor(() =>
    expect(
      JSON.parse(localStorage.getItem("fs.recentMenus:v1:GUEST:10")!),
    ).toEqual(["mes:work-orders"]),
  );
});

it("다른 업무의 미확인 작업 잠금을 즐겨찾기 저장이 해제하지 않는다", async () => {
  const server = mock();
  sidebar();
  const pin = await screen.findByRole("button", {
    name: "MES 대시보드 즐겨찾기 해제",
  });
  fireEvent.click(screen.getByRole("button", { name: "다른 업무 작업 시작" }));
  expect(pin).toBeDisabled();
  expect(screen.getByRole("button", { name: "전체 메뉴 보기" })).toBeDisabled();
  fireEvent.click(pin);
  expect(server.calls).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "다른 업무 작업 종료" }));
  expect(pin).toBeEnabled();
  fireEvent.click(pin);
  await waitFor(() => expect(server.calls).toHaveLength(1));
});
