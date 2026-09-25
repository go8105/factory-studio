// FS-018k F-13 환산·배출계수. 검증 항목별로 테스트를 나눈다.
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
  {
    id: 3,
    sourceCode: "WATER",
    name: "용수",
    sourceKind: "UTILITY",
    measureUnit: "m3",
  },
];

const factor = (id: number, kind: string, unit: string) => ({
  id,
  energySourceId: 1,
  factorKind: kind,
  effectiveYear: "2026",
  factorValue: kind === "PRIMARY" ? "0.000229" : "0.000460",
  factorUnit: unit,
  sourceNote: "합성 예시값",
  createdAt: "2026-09-24T00:00:00Z",
});

type Reply = { status: number; body?: unknown };

function mockApi(replies: Record<string, Reply> = {}) {
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
          : path.endsWith("/energy-sources")
            ? sources
            : url.includes("factorKind=EMISSION")
              ? [factor(2, "EMISSION", "tCO2eq/kWh")]
              : [factor(1, "PRIMARY", "TOE/kWh")];
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

function show() {
  render(
    <MemoryRouter initialEntries={["/fems/energy-factors"]}>
      <App />
    </MemoryRouter>,
  );
}

const BASE = "/api/v1/fems/energy-factors";
const posts = (fetcher: ReturnType<typeof mockApi>) =>
  fetcher.mock.calls.filter(
    ([url, init]) => String(url) === BASE && init?.method === "POST",
  );

async function fill(year: string) {
  fireEvent.change(await screen.findByLabelText("적용 연도"), {
    target: { value: year },
  });
  fireEvent.change(screen.getByLabelText(/^계수 \(/), {
    target: { value: "0.000450" },
  });
  fireEvent.change(screen.getByLabelText("출처"), {
    target: { value: "예시" },
  });
}

it("사이드바 기준정보에 F-13이 있다", async () => {
  mockApi();
  show();
  const menu = await screen.findByRole("complementary", { name: "FEMS 메뉴" });
  expect(menu.querySelector('a[href="/fems/energy-factors"]')).not.toBeNull();
});

it("첫 탭은 환산계수만 요청한다", async () => {
  const fetcher = mockApi();
  show();
  expect(await screen.findByRole("cell", { name: "TOE/kWh" })).toBeVisible();
  expect(
    fetcher.mock.calls.some(([url]) =>
      String(url).includes("factorKind=PRIMARY"),
    ),
  ).toBe(true);
});

it("배출계수 탭으로 바꾸면 배출계수 목록을 보여준다", async () => {
  mockApi();
  show();
  fireEvent.click(
    await screen.findByRole("button", { name: "온실가스 배출계수" }),
  );
  expect(await screen.findByRole("cell", { name: "tCO2eq/kWh" })).toBeVisible();
  expect(screen.queryByRole("cell", { name: "TOE/kWh" })).toBeNull();
  expect(screen.getByText(/환산값\(TOE\)에는 곱하지 않습니다/)).toBeVisible();
});

it("용수는 에너지원 선택지에서 빠진다", async () => {
  mockApi();
  show();
  const select = await screen.findByLabelText("에너지원");
  await waitFor(() =>
    expect(select.querySelectorAll("option")).toHaveLength(2),
  );
  expect(select.textContent).not.toContain("용수");
});

it("계수 입력란이 탭과 에너지원에 맞는 단위를 보여준다", async () => {
  mockApi();
  show();
  expect(await screen.findByLabelText("계수 (TOE/kWh)")).toBeVisible();
  fireEvent.change(screen.getByLabelText("에너지원"), {
    target: { value: "2" },
  });
  expect(screen.getByLabelText("계수 (TOE/Nm3)")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "온실가스 배출계수" }));
  expect(await screen.findByLabelText("계수 (tCO2eq/Nm3)")).toBeVisible();
});

it("등록은 현재 탭 유형으로 CSRF·멱등 키와 함께 보낸다", async () => {
  const fetcher = mockApi({
    [`POST ${BASE}`]: {
      status: 201,
      body: { data: factor(9, "EMISSION", "tCO2eq/kWh") },
    },
  });
  show();
  fireEvent.click(
    await screen.findByRole("button", { name: "온실가스 배출계수" }),
  );
  await fill("2027");
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() => expect(posts(fetcher)).toHaveLength(1));
  const init = posts(fetcher)[0][1]!;
  const headers = new Headers(init.headers);
  expect(headers.get("X-CSRF-Token")).toBe("test-csrf");
  expect(headers.get("Idempotency-Key")).toBeTruthy();
  expect(JSON.parse(String(init.body))).toEqual({
    effectiveYear: "2027",
    factorValue: "0.000450",
    sourceNote: "예시",
    energySourceId: 1,
    factorKind: "EMISSION",
  });
});

it("같은 연도 중복 오류를 적용 연도 칸에 보여준다", async () => {
  mockApi({
    [`POST ${BASE}`]: {
      status: 400,
      body: {
        error: {
          code: "VALIDATION_FAILED",
          message: "입력값을 확인해 주세요.",
          details: {
            fields: {
              effectiveYear: "이 에너지원의 2026년 계수가 이미 있습니다.",
            },
          },
        },
      },
    },
  });
  show();
  await fill("2026");
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  expect(
    await screen.findByText("이 에너지원의 2026년 계수가 이미 있습니다."),
  ).toBeVisible();
});

it("수정은 바뀐 값만 보내고 에너지원을 잠근다", async () => {
  const fetcher = mockApi({
    [`PATCH ${BASE}/1`]: {
      status: 200,
      body: { data: factor(1, "PRIMARY", "TOE/kWh") },
    },
  });
  show();
  fireEvent.click(await screen.findByRole("button", { name: "수정" }));
  expect(screen.getByLabelText("에너지원")).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/^계수 \(/), {
    target: { value: "0.000230" },
  });
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() => {
    const patch = fetcher.mock.calls.find(
      ([, init]) => init?.method === "PATCH",
    );
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({
      factorValue: "0.000230",
    });
  });
});

it("삭제는 두 단계이고 계산 불가가 된다고 알린다", async () => {
  const fetcher = mockApi({ [`DELETE ${BASE}/1`]: { status: 204 } });
  show();
  fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
  expect(screen.getByText(/"계수 없음"으로/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "삭제 확정" }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(([, init]) => init?.method === "DELETE"),
    ).toBe(true),
  );
});

it("계수를 등록할 에너지원이 없으면 에너지원 화면으로 안내한다", async () => {
  mockApi({
    "GET /api/v1/fems/energy-sources": {
      status: 200,
      body: { data: [sources[2]] },
    },
  });
  show();
  expect(
    await screen.findByText(/계수를 등록할 에너지원이 없습니다/),
  ).toBeVisible();
  expect(
    screen.getByRole("link", { name: /에너지원 화면으로/ }),
  ).toHaveAttribute("href", "/fems/energy-sources");
});

it("F-13 도움말로 연결된다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("link", { name: "환산·배출계수 도움말" }),
  ).toHaveAttribute("href", "/help/fems/f-13");
});
