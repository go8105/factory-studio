// FS-020b MES 공정 경로(M-14)·BOM(M-15). 검증 항목별로 테스트를 나눈다.
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
const items = [
  {
    id: 1,
    itemCode: "FG-C100",
    name: "커넥터",
    baseUnit: "EA",
    itemType: "finished",
    isActive: true,
    conversions: [],
  },
  {
    id: 5,
    itemCode: "RM-PBT",
    name: "PBT 수지",
    baseUnit: "KG",
    itemType: "raw",
    isActive: true,
    conversions: [],
  },
  {
    id: 6,
    itemCode: "RM-PIN",
    name: "단자 핀",
    baseUnit: "EA",
    itemType: "raw",
    isActive: true,
    conversions: [{ fromUnit: "BOX" }],
  },
];
const processes = [
  {
    id: 11,
    processCode: "INJ",
    name: "사출",
    processType: "INJ",
    isActive: true,
    equipmentIds: [],
  },
  {
    id: 12,
    processCode: "ASM",
    name: "조립",
    processType: "ASM",
    isActive: true,
    equipmentIds: [],
  },
  {
    id: 13,
    processCode: "INS",
    name: "검사",
    processType: "INS",
    isActive: true,
    equipmentIds: [],
  },
];
const step = (id: number, processId: number, sequenceNo: number) => ({
  id,
  processId,
  sequenceNo,
});
const routes = [
  {
    id: 21,
    itemId: 1,
    routeCode: "RT-C100",
    version: 1,
    status: "published",
    publishedAt: "2026-07-26T00:00:00Z",
    steps: [step(1, 11, 1), step(2, 12, 2), step(3, 13, 3)],
  },
  {
    id: 22,
    itemId: 1,
    routeCode: "RT-C100",
    version: 2,
    status: "draft",
    publishedAt: null,
    steps: [step(4, 11, 1), step(5, 12, 2), step(6, 13, 3)],
  },
];
const boms = [
  {
    id: 31,
    bomCode: "BOM-C100",
    itemId: 1,
    versionNo: 1,
    status: "published",
    lines: [
      {
        id: 1,
        lineNo: 1,
        materialItemId: 5,
        qtyPerUnit: "0.012",
        unit: "KG",
        lossRate: "2.00",
      },
    ],
  },
  {
    id: 32,
    bomCode: "BOM-C100-V2",
    itemId: 1,
    versionNo: 2,
    status: "draft",
    lines: [],
  },
];
const LISTS: Record<string, unknown> = {
  "/api/v1/mes/items": items,
  "/api/v1/mes/processes": processes,
  "/api/v1/mes/routes": routes,
  "/api/v1/mes/boms": boms,
};

type Reply = { status: number; body?: unknown };
function mockApi(replies: Record<string, Reply> = {}) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input).split("?")[0];
      const reply = replies[`${init?.method ?? "GET"} ${url}`];
      if (reply)
        return new Response(
          reply.status === 204 ? null : JSON.stringify(reply.body),
          {
            status: reply.status,
          },
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
const body = (fetcher: ReturnType<typeof mockApi>, method: string, i = 0) =>
  JSON.parse(
    String(
      fetcher.mock.calls.filter(([, init]) => init?.method === method)[i][1]!
        .body,
    ),
  );
async function row(table: string, name: RegExp) {
  const t = await screen.findByRole("table", { name: table });
  return within(t).getByRole("row", { name });
}

it("경로 목록은 상태별로 다른 작업을 보여준다", async () => {
  mockApi();
  show("/mes/routes");
  const v1 = await row("공정 경로 목록", /^RT-C100 .* v1/);
  expect(within(v1).getByRole("button", { name: "개정" })).toBeVisible();
  expect(within(v1).getByRole("button", { name: "폐기" })).toBeVisible();
  expect(within(v1).queryByRole("button", { name: "게시" })).toBeNull();
  const v2 = await row("공정 경로 목록", /^RT-C100 .* v2/);
  expect(within(v2).getByRole("button", { name: "게시" })).toBeVisible();
  expect(within(v2).getByRole("button", { name: "삭제" })).toBeVisible();
});

it("게시된 경로는 공정 순서를 편집할 수 없다", async () => {
  mockApi();
  show("/mes/routes");
  fireEvent.click(
    within(await row("공정 경로 목록", /^RT-C100 .* v1/)).getByRole("button", {
      name: /공정 3/,
    }),
  );
  expect(
    await screen.findByText(/게시된 버전은 바꿀 수 없습니다/),
  ).toBeVisible();
  expect(screen.queryByRole("button", { name: "순서 저장" })).toBeNull();
});

it("초안 경로의 순서를 바꿔 요청 순서대로 저장한다", async () => {
  const fetcher = mockApi({
    "PUT /api/v1/mes/routes/22/steps": {
      status: 200,
      body: { data: routes[1] },
    },
  });
  show("/mes/routes");
  fireEvent.click(
    within(await row("공정 경로 목록", /^RT-C100 .* v2/)).getByRole("button", {
      name: /공정 3/,
    }),
  );
  fireEvent.click(screen.getByRole("button", { name: "3번째 공정 위로" }));
  fireEvent.click(screen.getByRole("button", { name: "1번째 공정 빼기" }));
  fireEvent.click(screen.getByRole("button", { name: "순서 저장" }));
  await waitFor(() =>
    expect(body(fetcher, "PUT")).toEqual({ processIds: [13, 12] }),
  );
});

it("개정은 새 초안을 열어 준다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/mes/routes/21/revise": {
      status: 201,
      body: { data: routes[1] },
    },
  });
  show("/mes/routes");
  fireEvent.click(
    within(await row("공정 경로 목록", /^RT-C100 .* v1/)).getByRole("button", {
      name: "개정",
    }),
  );
  expect(
    await screen.findByRole("table", { name: "RT-C100 v2 공정 순서" }),
  ).toBeVisible();
  const init = fetcher.mock.calls.find(([, i]) => i?.method === "POST")![1]!;
  expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("test-csrf");
  expect(new Headers(init.headers).get("Idempotency-Key")).toBeTruthy();
});

it("공정 없는 경로 게시 거부를 보여준다", async () => {
  mockApi({
    "POST /api/v1/mes/routes/22/publish": {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "공정 단계이(가) 없는 공정 경로은(는) 게시할 수 없습니다.",
          details: { reason: "EMPTY_VERSION" },
        },
      },
    },
  });
  show("/mes/routes");
  fireEvent.click(
    within(await row("공정 경로 목록", /^RT-C100 .* v2/)).getByRole("button", {
      name: "게시",
    }),
  );
  expect(await screen.findByText(/게시할 수 없습니다/)).toBeVisible();
});

it("BOM 개정은 다음 버전 코드를 제안한다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/mes/boms/31/revise": { status: 201, body: { data: boms[1] } },
  });
  show("/mes/boms");
  fireEvent.click(
    within(await row("BOM 목록", /^BOM-C100 /)).getByRole("button", {
      name: "개정",
    }),
  );
  expect(screen.getByLabelText("새 BOM 코드")).toHaveValue("BOM-C100-V2");
  fireEvent.click(
    within(screen.getByRole("form", { name: "BOM 개정" })).getByRole("button", {
      name: "개정",
    }),
  );
  await waitFor(() =>
    expect(body(fetcher, "POST")).toEqual({ bomCode: "BOM-C100-V2" }),
  );
});

it("초안 BOM에 자재를 추가하면 단위는 기준 단위와 환산 단위만 고를 수 있다", async () => {
  const fetcher = mockApi({
    "PUT /api/v1/mes/boms/32/lines": { status: 200, body: { data: boms[1] } },
  });
  show("/mes/boms");
  fireEvent.click(
    within(await row("BOM 목록", /^BOM-C100-V2/)).getByRole("button", {
      name: /자재 0/,
    }),
  );
  fireEvent.click(screen.getByRole("button", { name: "자재 추가" }));
  const material = screen.getByLabelText("자재");
  expect(material).not.toHaveTextContent("FG-C100");
  fireEvent.change(material, { target: { value: "6" } });
  const unit = screen.getByLabelText("단위");
  expect(
    [...unit.querySelectorAll("option")].map((o) => o.textContent),
  ).toEqual(["EA", "BOX"]);
  fireEvent.change(screen.getByLabelText("소요량(1개당)"), {
    target: { value: "4" },
  });
  fireEvent.click(screen.getByRole("button", { name: "추가" }));
  await waitFor(() =>
    expect(body(fetcher, "PUT")).toEqual({
      lines: [
        { materialItemId: 6, qtyPerUnit: "4", unit: "EA", lossRate: "0" },
      ],
    }),
  );
});

it("BOM 자재 규칙 오류를 보여준다", async () => {
  mockApi({
    "PUT /api/v1/mes/boms/32/lines": {
      status: 400,
      body: {
        error: {
          code: "VALIDATION_FAILED",
          message: "입력값을 확인해 주세요.",
          details: {
            fields: { lines: "1번째 자재: 같은 자재가 이미 있습니다." },
          },
        },
      },
    },
  });
  show("/mes/boms");
  fireEvent.click(
    within(await row("BOM 목록", /^BOM-C100-V2/)).getByRole("button", {
      name: /자재 0/,
    }),
  );
  fireEvent.click(screen.getByRole("button", { name: "자재 추가" }));
  fireEvent.click(screen.getByRole("button", { name: "추가" }));
  expect(
    await screen.findByText("1번째 자재: 같은 자재가 이미 있습니다."),
  ).toBeVisible();
});
