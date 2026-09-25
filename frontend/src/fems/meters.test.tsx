// FS-018l F-12 계측기·채널. 검증 항목별로 테스트를 나눈다.
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

const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};

const channel = (id: number, meterId: number, extra = {}) => ({
  id,
  meterId,
  energySourceId: 1,
  channelCode: `CH-${id}`,
  name: `채널 ${id}`,
  measurementKind: "CUMULATIVE",
  unit: "kWh",
  multiplier: "1.000000",
  isActive: true,
  observed: true,
  ...extra,
});

const meters = [
  {
    id: 1,
    siteId: 1,
    locationId: 4,
    parentMeterId: null,
    equipmentId: null,
    meterCode: "M-MAIN",
    name: "수전 전력량계",
    scopeKind: "site_total",
    channelCount: 1,
    observed: true,
    channels: [channel(11, 1, { multiplier: "80.000000" })],
  },
  {
    id: 2,
    siteId: 1,
    locationId: 1,
    parentMeterId: 1,
    equipmentId: 7,
    meterCode: "M-INJ-01",
    name: "사출 1호",
    scopeKind: "factory",
    channelCount: 1,
    observed: true,
    channels: [channel(12, 2)],
  },
];
const locations = [
  { id: 1, locationCode: "L-INJ", name: "사출동", kind: "workcenter" },
  { id: 4, locationCode: "L-UTL", name: "유틸리티실", kind: "zone" },
];
const equipments = [
  { id: 7, equipmentCode: "INJ-01", name: "사출기 1호", locationId: 1 },
  { id: 8, equipmentCode: "ASM-01", name: "조립 1호", locationId: 2 },
];
const sources = [
  {
    id: 1,
    sourceCode: "ELEC",
    name: "전력",
    sourceKind: "ELECTRIC",
    measureUnit: "kWh",
  },
  {
    id: 2,
    sourceCode: "GAS",
    name: "도시가스",
    sourceKind: "FUEL",
    measureUnit: "Nm3",
  },
];

type Reply = { status: number; body?: unknown };

function mockApi(replies: Record<string, Reply> = {}, sourceRows = sources) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const path = url.split("?")[0];
      const reply = replies[`${method} ${path}`];
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
          : path.endsWith("/locations")
            ? locations
            : path.endsWith("/equipments")
              ? equipments
              : path.endsWith("/energy-sources")
                ? sourceRows
                : meters;
      return new Response(JSON.stringify({ data }), { status: 200 });
    });
}

function show() {
  render(
    <MemoryRouter initialEntries={["/fems/meters"]}>
      <App />
    </MemoryRouter>,
  );
}

const BASE = "/api/v1/fems/meters";
const sent = (fetcher: ReturnType<typeof mockApi>, method: string) =>
  fetcher.mock.calls.filter(([, init]) => init?.method === method);

async function openChannels(code: string) {
  const table = await screen.findByRole("table", { name: "계측기 목록" });
  const row = within(table).getByRole("row", { name: new RegExp(`^${code}`) });
  fireEvent.click(within(row).getByRole("button", { name: /채널/ }));
  return screen.findByRole("table", { name: `${code} 채널 목록` });
}

it("사이드바 기준정보에 F-12가 있다", async () => {
  mockApi();
  show();
  const menu = await screen.findByRole("complementary", { name: "FEMS 메뉴" });
  expect(menu.querySelector('a[href="/fems/meters"]')).not.toBeNull();
});

it("계측기 목록은 상위 계측기·공간·설비를 이름으로 보여준다", async () => {
  mockApi();
  show();
  const table = await screen.findByRole("table", { name: "계측기 목록" });
  const row = within(table).getByRole("row", { name: /M-INJ-01/ });
  expect(row).toHaveTextContent("M-MAIN");
  expect(row).toHaveTextContent("사출동");
  expect(row).toHaveTextContent("사출기 1호");
});

it("채널을 누르면 그 계측기의 채널만 보여준다", async () => {
  mockApi();
  show();
  const channels = await openChannels("M-INJ-01");
  expect(within(channels).getByRole("cell", { name: "CH-12" })).toBeVisible();
  expect(within(channels).queryByRole("cell", { name: "CH-11" })).toBeNull();
});

it("계기 배수가 1이 아니면 강조한다", async () => {
  mockApi();
  show();
  const channels = await openChannels("M-MAIN");
  expect(within(channels).getByText("× 80")).toHaveClass("badge", "warning");
});

it("설비 선택지는 고른 공간의 설비만 보여준다", async () => {
  mockApi();
  show();
  const location = await screen.findByLabelText("공간");
  fireEvent.change(location, { target: { value: "1" } });
  const equipment = screen.getByLabelText("설비");
  expect(equipment).toHaveTextContent("사출기 1호");
  expect(equipment).not.toHaveTextContent("조립 1호");
});

it("계측기 등록은 CSRF·멱등 키와 대문자 코드로 보내고 채널 관리로 넘어간다", async () => {
  const fetcher = mockApi({
    [`POST ${BASE}`]: { status: 201, body: { data: { ...meters[1], id: 2 } } },
  });
  show();
  fireEvent.change(await screen.findByLabelText("계측기 코드"), {
    target: { value: "m-new" },
  });
  fireEvent.change(screen.getByLabelText("계측기 이름"), {
    target: { value: "신규" },
  });
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() => expect(sent(fetcher, "POST")).toHaveLength(1));
  const init = sent(fetcher, "POST")[0][1]!;
  expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("test-csrf");
  expect(new Headers(init.headers).get("Idempotency-Key")).toBeTruthy();
  expect(JSON.parse(String(init.body))).toEqual({
    meterCode: "M-NEW",
    name: "신규",
    locationId: 1,
    equipmentId: null,
    parentMeterId: null,
    scopeKind: "factory",
  });
  expect(
    await screen.findByRole("table", { name: "M-INJ-01 채널 목록" }),
  ).toBeVisible();
});

it("계측값이 있는 계측기는 공간·설비·상위 계측기를 잠근다", async () => {
  mockApi();
  show();
  const table = await screen.findByRole("table", { name: "계측기 목록" });
  const row = within(table).getByRole("row", { name: /M-INJ-01/ });
  fireEvent.click(within(row).getByRole("button", { name: "수정" }));
  expect(screen.getByLabelText("공간")).toBeDisabled();
  expect(screen.getByLabelText("설비")).toBeDisabled();
  expect(screen.getByLabelText("상위 계측기")).toBeDisabled();
  expect(screen.getByLabelText("계측기 이름")).toBeEnabled();
});

it("계측값이 있는 채널은 에너지원·종류·단위를 잠그고 배수만 바꿔 보낸다", async () => {
  const fetcher = mockApi({
    [`PATCH ${BASE}/2/channels/12`]: {
      status: 200,
      body: { data: channel(12, 2) },
    },
  });
  show();
  const channels = await openChannels("M-INJ-01");
  fireEvent.click(within(channels).getByRole("button", { name: "수정" }));
  expect(screen.getByLabelText("에너지원")).toBeDisabled();
  expect(screen.getByLabelText("측정 종류")).toBeDisabled();
  expect(screen.getByLabelText("단위")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("계기 배수"), {
    target: { value: "2" },
  });
  expect(screen.getByText(/계기 배수가 1이 아닙니다/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() =>
    expect(JSON.parse(String(sent(fetcher, "PATCH")[0][1]!.body))).toEqual({
      multiplier: "2",
    }),
  );
});

it("누적 채널은 에너지원을 바꾸면 단위가 계측 단위로 따라간다", async () => {
  mockApi();
  show();
  await openChannels("M-MAIN");
  const form = screen.getByRole("form", { name: "채널 등록" });
  fireEvent.change(within(form).getByLabelText("에너지원"), {
    target: { value: "2" },
  });
  expect(within(form).getByLabelText("단위")).toHaveValue("Nm3");
});

it("삭제가 막히면 참조 건수를 보여준다", async () => {
  mockApi({
    [`DELETE ${BASE}/1`]: {
      status: 409,
      body: {
        error: {
          code: "REFERENCED_BY_OTHERS",
          message:
            "하위 계측기나 채널이 있어 삭제할 수 없습니다. 먼저 정리하세요.",
          details: {
            references: [
              { table: "fems.meter", label: "하위 계측기", count: 1 },
            ],
          },
        },
      },
    },
  });
  show();
  const table = await screen.findByRole("table", { name: "계측기 목록" });
  const row = within(table).getByRole("row", { name: /^M-MAIN/ });
  fireEvent.click(within(row).getByRole("button", { name: "삭제" }));
  fireEvent.click(within(row).getByRole("button", { name: "삭제 확정" }));
  expect(await screen.findByText("하위 계측기 1건")).toBeVisible();
});

it("에너지원이 없으면 에너지원 화면으로 안내한다", async () => {
  mockApi({}, []);
  show();
  expect(await screen.findByText(/등록된 에너지원이 없습니다/)).toBeVisible();
  expect(
    screen.getByRole("link", { name: /에너지원 화면으로/ }),
  ).toHaveAttribute("href", "/fems/energy-sources");
});

it("F-12 도움말로 연결된다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("link", { name: "계측기·채널 도움말" }),
  ).toHaveAttribute("href", "/help/fems/f-12");
});
