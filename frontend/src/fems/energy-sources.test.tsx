// FS-018a FEMS 레이아웃·F-11 에너지원. 검증 항목별로 테스트를 나눈다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import { femsScreens } from "./FemsLayout";
const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const rows = [
  ["ELEC", "전력", "ELECTRIC", "kWh"],
  ["GAS", "도시가스", "FUEL", "Nm3"],
].map(([sourceCode, name, sourceKind, measureUnit], i) => ({
  id: i + 1,
  sourceCode,
  name,
  sourceKind,
  measureUnit,
  isBillable: true,
  isActive: true,
  createdAt: "2026-09-24T00:00:00Z",
}));
type Reply = { status: number; body?: unknown } | "network";
function mockApi(replies: Record<string, Reply> = {}) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const reply = replies[`${method} ${url.split("?")[0]}`];
      if (reply === "network") throw new TypeError("network");
      if (reply)
        return new Response(
          reply.status === 204 ? null : JSON.stringify(reply.body),
          { status: reply.status },
        );
      const data = url.endsWith("/sessions/current")
        ? session
        : url.endsWith("/workspace/modules")
          ? ["core", "mes", "erp", "fems"].map((moduleKey) => ({
              moduleKey,
              enabled: true,
              updatedAt: null,
            }))
          : rows;
      return new Response(
        JSON.stringify({ data, page: { offset: 0, limit: 20, total: 2 } }),
        { status: 200 },
      );
    });
}
function show(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
const SOURCES = "/api/v1/fems/energy-sources";
const calls = (fetcher: ReturnType<typeof mockApi>, method: string) =>
  fetcher.mock.calls.filter(
    ([url, init]) =>
      String(url).startsWith(SOURCES) && (init?.method ?? "GET") === method,
  );
async function fillNew() {
  fireEvent.click(await screen.findByRole("button", { name: "에너지원 등록" }));
  fireEvent.change(await screen.findByLabelText("에너지원 코드"), {
    target: { value: "steam" },
  });
  fireEvent.change(screen.getByLabelText("에너지원명"), {
    target: { value: "스팀" },
  });
}
it("런처의 FEMS 카드는 FEMS 화면으로 연결된다", async () => {
  mockApi();
  show("/home");
  expect(
    await screen.findByRole("link", { name: /FEMS 에너지관리/ }),
  ).toHaveAttribute("href", "/fems");
});
it("F-11은 실제 목록을 표시한다", async () => {
  mockApi();
  show("/fems/energy-sources");
  expect(await screen.findByRole("cell", { name: "도시가스" })).toBeVisible();
});
it("사이드바는 구현된 화면만 보여준다", async () => {
  mockApi();
  show("/fems/energy-sources");
  const menu = await screen.findByRole("complementary", { name: "FEMS 메뉴" });
  expect(menu.querySelectorAll('a[href^="/fems/"]')).toHaveLength(
    femsScreens.length,
  );
});
it("F-11 도움말은 FEMS 도움말로 연결된다", async () => {
  mockApi();
  show("/fems/energy-sources");
  expect(
    await screen.findByRole("link", { name: "에너지원 도움말" }),
  ).toHaveAttribute("href", "/help/fems/f-11");
});
it("사용 중만 보기는 active 조건으로 조회한다", async () => {
  const fetcher = mockApi();
  show("/fems/energy-sources");
  fireEvent.click(await screen.findByLabelText("사용 중인 에너지원만"));
  await waitFor(() =>
    expect(
      calls(fetcher, "GET").some(([url]) =>
        String(url).includes("active=true"),
      ),
    ).toBe(true),
  );
});
it("등록은 CSRF·멱등 키와 대문자 코드로 요청한다", async () => {
  const fetcher = mockApi({
    [`POST ${SOURCES}`]: { status: 201, body: { data: rows[0] } },
  });
  show("/fems/energy-sources");
  await fillNew();
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() => expect(calls(fetcher, "POST")).toHaveLength(1));
  const [, init] = calls(fetcher, "POST")[0];
  expect(init?.headers).toMatchObject({
    "X-CSRF-Token": "test-csrf",
    "Idempotency-Key": expect.any(String),
  });
  expect(JSON.parse(String(init?.body)).sourceCode).toBe("STEAM");
});
it("중복 코드는 입력 칸 옆에 오류를 표시한다", async () => {
  mockApi({
    [`POST ${SOURCES}`]: {
      status: 400,
      body: {
        error: {
          code: "VALIDATION_FAILED",
          message: "입력값을 확인해 주세요.",
          details: { fields: { sourceCode: "이미 사용 중인 코드입니다." } },
        },
      },
    },
  });
  show("/fems/energy-sources");
  await fillNew();
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  expect(await screen.findByText("이미 사용 중인 코드입니다.")).toBeVisible();
  expect(screen.getByLabelText("에너지원 코드")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
});
it("응답이 불확실하면 같은 멱등 키로 재시도한다", async () => {
  const fetcher = mockApi({ [`POST ${SOURCES}`]: "network" });
  show("/fems/energy-sources");
  await fillNew();
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await screen.findByText(/응답을 확인하지 못했습니다/);
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() => expect(calls(fetcher, "POST")).toHaveLength(2));
  const keys = calls(fetcher, "POST").map(
    ([, init]) => (init?.headers as Record<string, string>)["Idempotency-Key"],
  );
  expect(keys[0]).toBe(keys[1]);
});
it("수정은 바뀐 항목만 PATCH로 보낸다", async () => {
  const fetcher = mockApi({
    [`PATCH ${SOURCES}/2`]: { status: 200, body: { data: rows[1] } },
  });
  show("/fems/energy-sources");
  fireEvent.click((await screen.findAllByRole("button", { name: "수정" }))[1]);
  fireEvent.change(screen.getByLabelText("에너지원명"), {
    target: { value: "LNG" },
  });
  fireEvent.click(screen.getByRole("button", { name: "수정 저장" }));
  await waitFor(() => expect(calls(fetcher, "PATCH")).toHaveLength(1));
  expect(JSON.parse(String(calls(fetcher, "PATCH")[0][1]?.body))).toEqual({
    name: "LNG",
  });
});
it("삭제는 확정 전 요청하지 않는다", async () => {
  const fetcher = mockApi();
  show("/fems/energy-sources");
  fireEvent.click((await screen.findAllByRole("button", { name: "삭제" }))[0]);
  expect(screen.getByRole("button", { name: "삭제 확정" })).toBeVisible();
  expect(calls(fetcher, "DELETE")).toHaveLength(0);
});
it("참조 중인 에너지원 삭제는 참조처별 건수를 보여준다", async () => {
  mockApi({
    [`DELETE ${SOURCES}/1`]: {
      status: 409,
      body: {
        error: {
          code: "REFERENCED_BY_OTHERS",
          message: "다른 기준정보가 참조 중이라 삭제할 수 없습니다.",
          details: {
            references: [
              { table: "fems.meter_channel", label: "계측 채널", count: 3 },
            ],
          },
        },
      },
    },
  });
  show("/fems/energy-sources");
  fireEvent.click((await screen.findAllByRole("button", { name: "삭제" }))[0]);
  fireEvent.click(screen.getByRole("button", { name: "삭제 확정" }));
  expect(await screen.findByText("계측 채널 3건")).toBeVisible();
});
it("FEMS를 끈 공간은 내 공간으로 안내한다", async () => {
  mockApi({
    [`GET ${SOURCES}`]: {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "사용하지 않도록 설정되어 있습니다.",
          details: { reason: "MODULE_DISABLED", moduleKey: "fems" },
        },
      },
    },
  });
  show("/fems/energy-sources");
  expect(
    await screen.findByRole("link", { name: /내 공간으로/ }),
  ).toHaveAttribute("href", "/workspace");
});
