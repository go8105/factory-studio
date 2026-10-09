// FS-020a MES 기준정보(M-10~M-13). 검증 항목별로 테스트를 나눈다.
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import { mesScreens } from "./MesLayout";

const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const sites = [
  { id: 1, siteCode: "S01", name: "본사 공장", timezone: "Asia/Seoul" },
];
const places = [
  {
    id: 1,
    siteId: 1,
    parentLocationId: null,
    locationCode: "L-INJ",
    name: "사출동",
    kind: "workcenter",
  },
  {
    id: 2,
    siteId: 1,
    parentLocationId: null,
    locationCode: "L-ASM",
    name: "조립동",
    kind: "workcenter",
  },
];
const equipments = [
  {
    id: 7,
    locationId: 1,
    equipmentCode: "INJ-01",
    name: "사출기 1호",
    equipmentType: "INJ",
    isActive: true,
  },
  {
    id: 8,
    locationId: 2,
    equipmentCode: "ASM-01",
    name: "조립기 1호",
    equipmentType: "ASM",
    isActive: false,
  },
];
const items = [
  {
    id: 5,
    itemCode: "RM-PIN",
    name: "커넥터 핀",
    baseUnit: "EA",
    itemType: "raw",
    isActive: true,
    conversions: [
      {
        id: 9,
        itemId: 5,
        fromUnit: "BOX",
        toUnit: "EA",
        factor: "10000.000000",
      },
    ],
  },
];
const processes = [
  {
    id: 3,
    processCode: "INJ",
    name: "사출",
    processType: "INJ",
    isActive: true,
    equipmentIds: [7],
  },
];

type Reply = { status: number; body?: unknown };
const LISTS: Record<string, unknown> = {
  // 진입 화면의 비동기 조회도 실제 대시보드 계약을 반환해야 한다.
  "/api/v1/mes/dashboard": {
    month: "2026-09",
    openOrders: 0,
    producedQty: "0",
    goodRate: null,
    receivedPallets: 0,
    pipeline: [],
    defectReasons: [],
    planVsActual: [],
    pending: { unconfirmedResults: 0, unpackedLots: 0 },
  },
  "/api/v1/mes/sites": sites,
  "/api/v1/mes/locations": places,
  "/api/v1/mes/equipments": equipments,
  "/api/v1/mes/items": items,
  "/api/v1/mes/processes": processes,
};

function mockApi(replies: Record<string, Reply> = {}) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input).split("?")[0];
      const method = init?.method ?? "GET";
      const reply = replies[`${method} ${url}`];
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
          : (LISTS[url] ?? []);
      return new Response(JSON.stringify({ data }), { status: 200 });
    });
}

function show(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

const sent = (fetcher: ReturnType<typeof mockApi>, method: string) =>
  fetcher.mock.calls.filter(([, init]) => init?.method === method);

async function row(table: string, code: string) {
  const t = await screen.findByRole("table", { name: table });
  return within(t).getByRole("row", { name: new RegExp(`^${code}`) });
}

it("MES 진입은 대시보드로 가고 사이드바에 구현 화면만 둔다", async () => {
  mockApi();
  show("/mes");
  expect(
    await screen.findByRole("heading", { name: "생산 개요", level: 1 }),
  ).toBeVisible();
  const menu = screen.getByRole("complementary", { name: "MES 메뉴" });
  expect(menu.querySelectorAll('a[href^="/mes/"]')).toHaveLength(
    mesScreens.length,
  );
});

it("M-10은 FEMS와 별개 데이터임을 안내하고 공간의 사업장을 보여준다", async () => {
  mockApi();
  show("/mes/sites");
  expect(await screen.findByText(/FEMS의 사업장·공간과/)).toBeVisible();
  expect(await row("공간 목록", "L-INJ")).toHaveTextContent("본사 공장");
});

it("공간 등록은 대문자 코드로 보낸다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/mes/locations": { status: 201, body: { data: places[0] } },
  });
  show("/mes/sites");
  fireEvent.click(await screen.findByRole("button", { name: "공간 등록" }));
  const form = await screen.findByRole("form", { name: "공간 등록" });
  fireEvent.change(within(form).getByLabelText("공간 코드"), {
    target: { value: "l-pkg" },
  });
  fireEvent.change(within(form).getByLabelText("공간명"), {
    target: { value: "포장실" },
  });
  fireEvent.click(within(form).getByRole("button", { name: "등록" }));
  await waitFor(() =>
    expect(JSON.parse(String(sent(fetcher, "POST")[0][1]!.body))).toEqual({
      siteId: 1,
      parentLocationId: null,
      locationCode: "L-PKG",
      name: "포장실",
      kind: "workcenter",
    }),
  );
  const init = sent(fetcher, "POST")[0][1]!;
  expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("test-csrf");
  expect(new Headers(init.headers).get("Idempotency-Key")).toBeTruthy();
});

it("M-11은 공간 이름과 사용 안 함을 보여준다", async () => {
  mockApi();
  show("/mes/equipments");
  const asm = await row("설비 목록", "ASM-01");
  expect(asm).toHaveTextContent("조립동");
  expect(within(asm).getByText("사용 안 함")).toHaveClass("badge");
});

it("설비 수정은 바뀐 값만 보낸다", async () => {
  const fetcher = mockApi({
    "PATCH /api/v1/mes/equipments/7": {
      status: 200,
      body: { data: equipments[0] },
    },
  });
  show("/mes/equipments");
  fireEvent.click(
    within(await row("설비 목록", "INJ-01")).getByRole("button", {
      name: "수정",
    }),
  );
  fireEvent.click(screen.getByRole("checkbox", { name: "사용" }));
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() =>
    expect(JSON.parse(String(sent(fetcher, "PATCH")[0][1]!.body))).toEqual({
      isActive: false,
    }),
  );
});

it("M-12는 ERP와 별개 품목임을 안내한다", async () => {
  mockApi();
  show("/mes/items");
  expect(
    await screen.findByText(/ERP 품목과 코드가 같아도 별개 데이터입니다/),
  ).toBeVisible();
});

it("환산을 누르면 그 품목의 단위 환산을 보여준다", async () => {
  mockApi();
  show("/mes/items");
  fireEvent.click(
    within(await row("품목 목록", "RM-PIN")).getByRole("button", {
      name: /환산/,
    }),
  );
  const table = await screen.findByRole("table", {
    name: "RM-PIN 단위 환산 목록",
  });
  expect(
    within(table).getByRole("cell", { name: "1 BOX = 10,000 EA" }),
  ).toBeVisible();
  // 목록만 보여 주고, 등록 패널은 "환산 등록"으로 연다.
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "환산 등록" }));
  expect(await screen.findByLabelText(/^환산 계수/)).toBeVisible();
});

it("기준 단위 잠금 오류를 보여준다", async () => {
  mockApi({
    "PATCH /api/v1/mes/items/5": {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message:
            "단위 환산이나 작업지시가 있는 품목은 기준 단위를 바꿀 수 없습니다.",
          details: {
            reason: "UNIT_IN_USE",
            references: [
              {
                table: "mes.item_unit_conversion",
                label: "단위 환산",
                count: 1,
              },
            ],
          },
        },
      },
    },
  });
  show("/mes/items");
  fireEvent.click(
    within(await row("품목 목록", "RM-PIN")).getByRole("button", {
      name: "수정",
    }),
  );
  fireEvent.change(screen.getByLabelText("기준 단위"), {
    target: { value: "KG" },
  });
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  expect(await screen.findByText("단위 환산 1건")).toBeVisible();
});

it("M-13은 허용 설비 코드를 보여준다", async () => {
  mockApi();
  show("/mes/processes");
  expect(await row("공정 목록", "INJ")).toHaveTextContent("INJ-01");
});

it("공정 수정은 허용 설비 목록을 통째로 보낸다", async () => {
  const fetcher = mockApi({
    "PATCH /api/v1/mes/processes/3": {
      status: 200,
      body: { data: processes[0] },
    },
  });
  show("/mes/processes");
  fireEvent.click(
    within(await row("공정 목록", "INJ")).getByRole("button", {
      name: "수정",
    }),
  );
  fireEvent.click(screen.getByRole("checkbox", { name: /ASM-01/ }));
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() =>
    expect(JSON.parse(String(sent(fetcher, "PATCH")[0][1]!.body))).toEqual({
      equipmentIds: [7, 8],
    }),
  );
});

it("삭제가 막히면 참조 건수를 보여준다", async () => {
  mockApi({
    "DELETE /api/v1/mes/processes/3": {
      status: 409,
      body: {
        error: {
          code: "REFERENCED_BY_OTHERS",
          message: "다른 데이터가 참조 중인 공정은(는) 삭제할 수 없습니다.",
          details: {
            references: [
              { table: "mes.route_step", label: "공정 경로 단계", count: 4 },
            ],
          },
        },
      },
    },
  });
  show("/mes/processes");
  const inj = await row("공정 목록", "INJ");
  fireEvent.click(within(inj).getByRole("button", { name: "삭제" }));
  fireEvent.click(within(inj).getByRole("button", { name: "삭제 확정" }));
  expect(await screen.findByText("공정 경로 단계 4건")).toBeVisible();
});

it("MES가 꺼져 있으면 내 공간으로 안내한다", async () => {
  mockApi({
    "GET /api/v1/mes/items": {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "모듈이 꺼져 있습니다.",
          details: { reason: "MODULE_DISABLED", moduleKey: "mes" },
        },
      },
    },
  });
  show("/mes/items");
  expect(
    await screen.findByText(/MES를 사용하지 않도록 설정했습니다/),
  ).toBeVisible();
});
