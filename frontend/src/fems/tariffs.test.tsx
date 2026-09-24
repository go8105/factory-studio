// FS-018 FEMS 레이아웃·F-14 요금제. 검증 항목별로 테스트를 나눈다.
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

const sources = [
  { id: 1, sourceCode: "ELEC", name: "전력", measureUnit: "kWh" },
  { id: 2, sourceCode: "GAS", name: "도시가스", measureUnit: "Nm3" },
];

const rows = [
  {
    id: 1,
    energySourceId: 1,
    tariffCode: "TR-ELEC-01",
    name: "산업용(갑) 저압",
    contractType: "산업용",
    basicCharge: "250000.0000",
    usageRate: "120.0000",
    currency: "KRW",
    effectiveFrom: "2025-09",
    effectiveTo: "2026-08",
    createdAt: "2026-09-24T00:00:00Z",
  },
  {
    id: 2,
    energySourceId: 1,
    tariffCode: "TR-ELEC-02",
    name: "산업용(갑) 저압 2",
    contractType: "산업용",
    basicCharge: "250000.0000",
    usageRate: "130.0000",
    currency: "KRW",
    effectiveFrom: "2026-09",
    effectiveTo: null,
    createdAt: "2026-09-24T00:00:00Z",
  },
];

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
          : cleanUrl.endsWith("/api/v1/fems/energy-sources")
            ? sources
            : rows;
      return new Response(
        JSON.stringify({
          data,
          page: {
            offset: 0,
            limit: 20,
            total: Array.isArray(data) ? data.length : 0,
          },
        }),
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

const TARIFFS = "/api/v1/fems/tariffs";
const calls = (fetcher: ReturnType<typeof mockApi>, method: string) =>
  fetcher.mock.calls.filter(
    ([url, init]) =>
      String(url).startsWith(TARIFFS) && (init?.method ?? "GET") === method,
  );

async function fillNew() {
  fireEvent.change(await screen.findByLabelText("요금제 코드"), {
    target: { value: "tr-test-01" },
  });
  fireEvent.change(screen.getByLabelText("요금제명"), {
    target: { value: "테스트 요금제" },
  });
  fireEvent.change(screen.getByLabelText("기본요금 (KRW)"), {
    target: { value: "200000" },
  });
  fireEvent.change(screen.getByLabelText("사용량 단가 (KRW)"), {
    target: { value: "115" },
  });
  fireEvent.change(screen.getByLabelText("적용 시작 연월"), {
    target: { value: "2024-01" },
  });
}

it("사이드바는 구현된 화면 목록(femsScreens)을 보여준다", async () => {
  mockApi();
  show("/fems/tariffs");
  const menu = await screen.findByRole("complementary", { name: "FEMS 메뉴" });
  expect(menu.querySelectorAll('a[href^="/fems/"]')).toHaveLength(
    femsScreens.length,
  );
});

it("F-14로 이동해 실제 요금제 목록과 천 단위 금액을 표시한다", async () => {
  mockApi();
  show("/fems/tariffs");
  expect(await screen.findByRole("cell", { name: "TR-ELEC-01" })).toBeVisible();
  // 천 단위 구분 금액 확인: 250,000 및 120
  expect(screen.getAllByRole("cell", { name: "250,000" })[0]).toBeVisible();
  expect(screen.getByRole("cell", { name: "120" })).toBeVisible();
  expect(screen.getByRole("cell", { name: "2025-09 ~ 2026-08" })).toBeVisible();
  expect(
    screen.getByRole("cell", { name: "2026-09 ~ 계속 적용" }),
  ).toBeVisible();
});

it("F-14 도움말은 FEMS 도움말로 연결된다", async () => {
  mockApi();
  show("/fems/tariffs");
  expect(
    await screen.findByRole("link", { name: "요금제 도움말" }),
  ).toHaveAttribute("href", "/help/fems/f-14");
});

it("에너지원 필터로 목록을 조회한다", async () => {
  const fetcher = mockApi();
  show("/fems/tariffs");
  const filter = await screen.findByLabelText("에너지원 필터:");
  await waitFor(() => {
    expect(filter.querySelectorAll("option").length).toBeGreaterThan(1);
  });
  fireEvent.change(filter, { target: { value: "2" } });
  await waitFor(() => {
    expect(
      fetcher.mock.calls.some(([url]) =>
        String(url).includes("energySourceId=2"),
      ),
    ).toBe(true);
  });
});

it("에너지원이 없으면 EmptyState로 안내한다", async () => {
  mockApi({
    "GET /api/v1/fems/energy-sources": { status: 200, body: { data: [] } },
  });
  show("/fems/tariffs");
  expect(await screen.findByText(/등록된 에너지원이 없습니다/)).toBeVisible();
  expect(
    screen.getByRole("link", { name: /에너지원 화면으로/ }),
  ).toHaveAttribute("href", "/fems/energy-sources");
});

it("등록은 CSRF·멱등 키와 대문자 코드로 요청한다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/fems/tariffs": {
      status: 201,
      body: {
        data: {
          id: 3,
          energySourceId: 1,
          tariffCode: "TR-TEST-01",
          name: "테스트 요금제",
          contractType: null,
          basicCharge: "200000",
          usageRate: "115",
          currency: "KRW",
          effectiveFrom: "2024-01",
          effectiveTo: null,
          createdAt: "2026-09-24T00:00:00Z",
        },
      },
    },
  });
  show("/fems/tariffs");
  await fillNew();
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() => expect(calls(fetcher, "POST")).toHaveLength(1));
  const [, init] = calls(fetcher, "POST")[0];
  const headers = init?.headers as Record<string, string>;
  expect(headers["X-CSRF-Token"]).toBe("test-csrf");
  expect(headers["Idempotency-Key"]).toMatch(/^[0-9a-f-]{36}$/);
  expect(JSON.parse(String(init?.body))).toMatchObject({
    tariffCode: "TR-TEST-01",
    name: "테스트 요금제",
    basicCharge: "200000",
    usageRate: "115",
    effectiveFrom: "2024-01",
    effectiveTo: null,
  });
});

it("겹치는 기간(PERIOD_OVERLAP) 등록 시 충돌 정보(코드 및 기간)를 표시한다", async () => {
  mockApi({
    "POST /api/v1/fems/tariffs": {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "같은 에너지원에 적용 기간이 겹치는 요금제가 있습니다.",
          details: {
            reason: "PERIOD_OVERLAP",
            conflicts: [
              {
                id: 1,
                tariffCode: "TR-ELEC-01",
                effectiveFrom: "2025-09",
                effectiveTo: "2026-08",
              },
            ],
          },
        },
      },
    },
  });
  show("/fems/tariffs");
  await fillNew();
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  expect(
    await screen.findByText(/적용 기간이 겹치는 요금제가 있습니다/),
  ).toBeVisible();
  expect(screen.getByText(/TR-ELEC-01 \(2025-09 ~ 2026-08\)/)).toBeVisible();
});

it("중복 코드는 입력 칸 옆에 오류를 표시한다", async () => {
  mockApi({
    "POST /api/v1/fems/tariffs": {
      status: 400,
      body: {
        error: {
          code: "VALIDATION_FAILED",
          message: "입력값을 확인해 주세요.",
          details: { fields: { tariffCode: "이미 사용 중인 코드입니다." } },
        },
      },
    },
  });
  show("/fems/tariffs");
  await fillNew();
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  expect(await screen.findByText("이미 사용 중인 코드입니다.")).toBeVisible();
});

it("응답이 불확실하면 같은 멱등 키로 재시도한다", async () => {
  let attempts = 0;
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/v1/fems/tariffs") && method === "POST") {
        attempts += 1;
        if (attempts === 1) throw new TypeError("network down");
        return new Response(
          JSON.stringify({
            data: {
              id: 3,
              energySourceId: 1,
              tariffCode: "TR-TEST-01",
              name: "테스트 요금제",
              basicCharge: "200000",
              usageRate: "115",
              currency: "KRW",
              effectiveFrom: "2024-01",
              effectiveTo: null,
              createdAt: "2026-09-24T00:00:00Z",
            },
          }),
          { status: 201 },
        );
      }
      const cleanUrl = url.split("?")[0];
      const data = url.endsWith("/sessions/current")
        ? session
        : url.endsWith("/workspace/modules")
          ? ["core", "mes", "erp", "fems"].map((moduleKey) => ({
              moduleKey,
              enabled: true,
              updatedAt: null,
            }))
          : cleanUrl.endsWith("/api/v1/fems/energy-sources")
            ? sources
            : rows;
      return new Response(
        JSON.stringify({ data, page: { offset: 0, limit: 20, total: 2 } }),
        { status: 200 },
      );
    });
  show("/fems/tariffs");
  await fillNew();
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() => expect(screen.getByRole("alert")).toBeVisible());
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() => expect(attempts).toBe(2));
  const [first, second] = calls(fetcher, "POST");
  const h1 = (first[1]?.headers as Record<string, string>)["Idempotency-Key"];
  const h2 = (second[1]?.headers as Record<string, string>)["Idempotency-Key"];
  expect(h1).toBe(h2);
});

it("수정은 바뀐 항목만 PATCH로 보낸다", async () => {
  const fetcher = mockApi({
    "PATCH /api/v1/fems/tariffs/1": {
      status: 200,
      body: { data: { ...rows[0], name: "요금제명 변경", usageRate: "125" } },
    },
  });
  show("/fems/tariffs");
  const editButtons = await screen.findAllByRole("button", { name: "수정" });
  fireEvent.click(editButtons[0]);
  fireEvent.change(screen.getByLabelText("요금제명"), {
    target: { value: "요금제명 변경" },
  });
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() => expect(calls(fetcher, "PATCH")).toHaveLength(1));
  const [, init] = calls(fetcher, "PATCH")[0];
  expect(JSON.parse(String(init?.body))).toEqual({ name: "요금제명 변경" });
});

it("삭제는 확정 전 요청하지 않고 확인 후 DELETE 요청한다", async () => {
  const fetcher = mockApi({
    "DELETE /api/v1/fems/tariffs/1": { status: 204 },
  });
  show("/fems/tariffs");
  const deleteButtons = await screen.findAllByRole("button", { name: "삭제" });
  fireEvent.click(deleteButtons[0]);
  expect(calls(fetcher, "DELETE")).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "삭제 확정" }));
  await waitFor(() => expect(calls(fetcher, "DELETE")).toHaveLength(1));
  const [url, init] = calls(fetcher, "DELETE")[0];
  expect(url).toContain("/api/v1/fems/tariffs/1");
  expect(init?.method).toBe("DELETE");
});

it("FEMS를 끈 공간은 내 공간으로 안내한다", async () => {
  mockApi({
    "GET /api/v1/fems/tariffs": {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "FEMS가 꺼져 있습니다.",
          details: { reason: "MODULE_DISABLED" },
        },
      },
    },
  });
  show("/fems/tariffs");
  expect(
    await screen.findByText(/FEMS를 사용하지 않도록 설정했습니다/),
  ).toBeVisible();
  expect(screen.getByRole("link", { name: "내 공간으로 →" })).toHaveAttribute(
    "href",
    "/workspace",
  );
});
