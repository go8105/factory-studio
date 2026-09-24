// FS-018a FEMS 레이아웃·F-10 설비. 검증 항목별로 테스트를 나눈다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

const locations = [
  { id: 1, locationCode: "L-INJ", name: "사출동", kind: "workcenter" },
  { id: 2, locationCode: "L-ASM", name: "조립동", kind: "workcenter" },
];

const rows = [
  ["INJ-01", "사출기 1호", "INJ", 1],
  ["ASM-01", "조립기 1호", "ASM", 2],
].map(([equipmentCode, name, equipmentType, locationId], i) => ({
  id: i + 1,
  locationId,
  equipmentCode,
  name,
  equipmentType,
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
      const cleanUrl = url.split("?")[0];
      const reply = Object.entries(replies).find(([k]) => {
        const [m, p] = k.split(" ");
        return m === method && (cleanUrl === p || cleanUrl.endsWith(p));
      })?.[1];
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
          : url.endsWith("/locations")
            ? locations
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

const EQUIPMENTS = "/api/v1/fems/equipments";
const calls = (fetcher: ReturnType<typeof mockApi>, method: string) =>
  fetcher.mock.calls.filter(
    ([url, init]) =>
      String(url).startsWith(EQUIPMENTS) && (init?.method ?? "GET") === method,
  );

async function fillNew() {
  fireEvent.change(await screen.findByLabelText("설비 코드"), {
    target: { value: "inj-02" },
  });
  fireEvent.change(screen.getByLabelText("설비명"), {
    target: { value: "사출기 2호" },
  });
  fireEvent.change(screen.getByLabelText("설비 유형"), {
    target: { value: "INJ" },
  });
}

it("사이드바는 구현된 화면(F-10, F-11)을 보여준다", async () => {
  mockApi();
  show("/fems/equipments");
  const menu = await screen.findByRole("complementary", { name: "FEMS 메뉴" });
  expect(menu.querySelectorAll('a[href^="/fems/"]')).toHaveLength(2);
  expect(screen.getByRole("link", { name: /F-10 설비/ })).toBeVisible();
  expect(screen.getByRole("link", { name: /F-11 에너지원/ })).toBeVisible();
});

it("F-10으로 이동해 실제 설비 목록을 표시한다", async () => {
  mockApi();
  show("/fems/equipments");
  expect(await screen.findByRole("cell", { name: "사출기 1호" })).toBeVisible();
  expect(screen.getByRole("cell", { name: "사출동" })).toBeVisible();
});

it("F-10 도움말은 FEMS 도움말로 연결된다", async () => {
  mockApi();
  show("/fems/equipments");
  expect(
    await screen.findByRole("link", { name: "설비 도움말" }),
  ).toHaveAttribute("href", "/help/fems/f-10");
});

it("사용 중만 보기는 active 조건으로 조회한다", async () => {
  const fetcher = mockApi();
  show("/fems/equipments");
  fireEvent.click(await screen.findByLabelText("사용 중인 설비만"));
  await waitFor(() =>
    expect(
      calls(fetcher, "GET").some(([url]) =>
        String(url).includes("active=true"),
      ),
    ).toBe(true),
  );
});

it("공간이 없으면 EmptyState로 안내한다", async () => {
  mockApi({
    "GET /api/v1/fems/locations": { status: 200, body: { data: [] } },
  });
  show("/fems/equipments");
  expect(await screen.findByText(/등록된 공간이 없습니다/)).toBeVisible();
  expect(screen.getByRole("link", { name: /공간 안내 보기/ })).toHaveAttribute(
    "href",
    "/help/fems/f-09",
  );
});

it("등록은 CSRF·멱등 키와 대문자 코드로 요청한다", async () => {
  const fetcher = mockApi({
    [`POST ${EQUIPMENTS}`]: { status: 201, body: { data: rows[0] } },
  });
  show("/fems/equipments");
  await fillNew();
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() => expect(calls(fetcher, "POST")).toHaveLength(1));
  const [, init] = calls(fetcher, "POST")[0];
  expect(init?.headers).toMatchObject({
    "X-CSRF-Token": "test-csrf",
    "Idempotency-Key": expect.any(String),
  });
  expect(JSON.parse(String(init?.body)).equipmentCode).toBe("INJ-02");
});

it("중복 코드는 입력 칸 옆에 오류를 표시한다", async () => {
  mockApi({
    [`POST ${EQUIPMENTS}`]: {
      status: 400,
      body: {
        error: {
          code: "VALIDATION_FAILED",
          message: "입력값을 확인해 주세요.",
          details: { fields: { equipmentCode: "이미 사용 중인 코드입니다." } },
        },
      },
    },
  });
  show("/fems/equipments");
  await fillNew();
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  expect(await screen.findByText("이미 사용 중인 코드입니다.")).toBeVisible();
  expect(screen.getByLabelText("설비 코드")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
});

it("응답이 불확실하면 같은 멱등 키로 재시도한다", async () => {
  const fetcher = mockApi({ [`POST ${EQUIPMENTS}`]: "network" });
  show("/fems/equipments");
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
    [`PATCH ${EQUIPMENTS}/2`]: { status: 200, body: { data: rows[1] } },
  });
  show("/fems/equipments");
  fireEvent.click((await screen.findAllByRole("button", { name: "수정" }))[1]);
  fireEvent.change(screen.getByLabelText("설비명"), {
    target: { value: "조립기 2호(개조)" },
  });
  fireEvent.click(screen.getByRole("button", { name: "수정 저장" }));
  await waitFor(() => expect(calls(fetcher, "PATCH")).toHaveLength(1));
  expect(JSON.parse(String(calls(fetcher, "PATCH")[0][1]?.body))).toEqual({
    name: "조립기 2호(개조)",
  });
});

it("삭제는 확정 전 요청하지 않는다", async () => {
  const fetcher = mockApi();
  show("/fems/equipments");
  fireEvent.click((await screen.findAllByRole("button", { name: "삭제" }))[0]);
  expect(screen.getByRole("button", { name: "삭제 확정" })).toBeVisible();
  expect(calls(fetcher, "DELETE")).toHaveLength(0);
});

it("참조 중인 설비 삭제는 참조처별 건수를 보여준다", async () => {
  mockApi({
    [`DELETE ${EQUIPMENTS}/1`]: {
      status: 409,
      body: {
        error: {
          code: "REFERENCED_BY_OTHERS",
          message: "다른 기준정보가 참조 중이라 삭제할 수 없습니다.",
          details: {
            references: [
              { table: "fems.meter", label: "계측기", count: 2 },
              {
                table: "fems.energy_allocation",
                label: "에너지 배분",
                count: 5,
              },
            ],
          },
        },
      },
    },
  });
  show("/fems/equipments");
  fireEvent.click((await screen.findAllByRole("button", { name: "삭제" }))[0]);
  fireEvent.click(screen.getByRole("button", { name: "삭제 확정" }));
  expect(await screen.findByText("계측기 2건")).toBeVisible();
  expect(screen.getByText("에너지 배분 5건")).toBeVisible();
});

it("FEMS를 끈 공간은 내 공간으로 안내한다", async () => {
  mockApi({
    [`GET ${EQUIPMENTS}`]: {
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
  show("/fems/equipments");
  expect(
    await screen.findByRole("link", { name: /내 공간으로/ }),
  ).toHaveAttribute("href", "/workspace");
});
