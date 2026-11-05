// FEMS-1f 화면: F-19 절감 활동, F-20 월간 검토, F-21 온실가스 명세서.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2099-01-01T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const sources = [
  { id: 1, sourceCode: "ELEC", name: "전력", measureUnit: "kWh" },
];
const saving = (over: object = {}) => ({
  id: 3,
  code: "SV-1",
  title: "대기전력 차단",
  equipmentId: null,
  energySourceId: 1,
  expectedSaving: "1000.000000",
  investment: "0.00",
  startOn: "2026-09-01",
  baselineStartOn: "2026-08-25",
  baselineEndOn: "2026-09-01",
  measuredSaving: null,
  status: "ACTIVE",
  ...over,
});
const review = (over: object = {}) => ({
  id: 5,
  reviewMonth: "2026-08",
  version: 1,
  status: "draft",
  primaryEnergyToe: "12.3456",
  energyCost: "1500000.00",
  emissionTco2e: "30.5",
  targetAchievement: null,
  issues: "※ 계측 8일/31일분 (2026-08-24 ~ 2026-08-31)",
  confirmedAt: null,
  ...over,
});
const inventory = (over: object = {}) => ({
  id: 8,
  inventoryYear: "2026",
  version: 1,
  status: "draft",
  scope1Tco2e: "4.0",
  scope2Tco2e: "26.5",
  confirmedAt: null,
  lines: [
    {
      scope: 2,
      equipmentCode: null,
      equipmentName: null,
      sourceCode: "ELEC",
      sourceName: "전력",
      activityQty: "57600",
      unit: "kWh",
      factorValue: "0.0004600000",
      emissionTco2e: "26.5",
    },
  ],
  coverage: { days: 31, expectedDays: 365, partial: true },
  ...over,
});

function mount(path: string, data: Record<string, unknown>) {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input).split("?")[0];
      const key = `${init?.method ?? "GET"} ${url.replace(/^.*\/api\/v1\/fems/, "")}`;
      if (key in data)
        return new Response(JSON.stringify({ data: data[key] }), {
          status: 200,
        });
      if (url.endsWith("/sessions/current"))
        return new Response(JSON.stringify({ data: session }));
      return new Response(JSON.stringify({ data: [] }));
    });
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  return fetcher;
}
const sent = (f: ReturnType<typeof mount>, method: string, suffix: string) =>
  f.mock.calls.filter(
    ([url, init]) =>
      (init?.method ?? "GET") === method &&
      String(url).split("?")[0].endsWith(suffix),
  );

// ---------- F-19 ----------

it("시행 중인 과제에만 검증을 둔다", async () => {
  mount("/fems/savings", {
    "GET /savings": [
      saving(),
      saving({ id: 4, code: "SV-2", status: "PLANNED" }),
    ],
    "GET /energy-sources": sources,
  });
  await screen.findByRole("table", { name: "절감 과제" });
  expect(screen.getAllByRole("button", { name: "검증" })).toHaveLength(1);
  expect(screen.getByRole("button", { name: "시행 시작" })).toBeInTheDocument();
});

it("검증한 과제는 더 바꿀 수 없다", async () => {
  mount("/fems/savings", {
    "GET /savings": [
      saving({ status: "VERIFIED", measuredSaving: "850.000000" }),
    ],
    "GET /energy-sources": sources,
  });
  await screen.findByRole("table", { name: "절감 과제" });
  expect(screen.queryByRole("button", { name: "검증" })).toBeNull();
  expect(screen.queryByRole("button", { name: "취소" })).toBeNull();
  expect(screen.getByText(/850 kWh/)).toBeInTheDocument();
});

it("마이너스 절감도 그대로 보인다", async () => {
  mount("/fems/savings", {
    "GET /savings": [
      saving({ status: "VERIFIED", measuredSaving: "-120.000000" }),
    ],
    "GET /energy-sources": sources,
  });
  expect(await screen.findByText(/-120 kWh/)).toBeInTheDocument();
});

it("설비 없는 과제는 생산량 보정을 안 한다고 안내한다", async () => {
  mount("/fems/savings", {
    "GET /savings": [],
    "GET /energy-sources": sources,
  });
  fireEvent.click(await screen.findByRole("button", { name: "과제 등록" }));
  expect(screen.getByText(/생산량으로 보정하지 않습니다/)).toBeInTheDocument();
});

it("검증하면 근거를 보여 준다", async () => {
  const fetcher = mount("/fems/savings", {
    "GET /savings": [saving()],
    "GET /energy-sources": sources,
    "POST /savings/3/verify": {
      ...saving({ status: "VERIFIED", measuredSaving: "800" }),
      evidence: {
        days: 7,
        productionAdjusted: true,
        periodSaving: "15.5",
        baseline: {
          from: "2026-08-25",
          to: "2026-08-31",
          energy: "100",
          production: "700",
        },
        after: {
          from: "2026-09-01",
          to: "2026-09-07",
          energy: "90",
          production: "700",
        },
      },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "검증" }));
  await waitFor(() => expect(sent(fetcher, "POST", "/verify")).toHaveLength(1));
  const panel = await screen.findByRole("region", { name: "검증 근거" });
  expect(panel).toHaveTextContent("7일 비교");
  expect(panel).toHaveTextContent("생산량으로 보정한 값");
});

// ---------- F-20 ----------

it("검토는 월을 고르기 전에는 초안을 만들 수 없다", async () => {
  mount("/fems/energy-reviews", { "GET /energy-reviews": [] });
  const button = await screen.findByRole("button", { name: "초안 만들기" });
  expect(button).toBeDisabled();
  fireEvent.change(screen.getByLabelText("검토 월"), {
    target: { value: "2026-08" },
  });
  expect(button).toBeEnabled();
});

it("초안에만 확정을 두고 목표가 없으면 0%가 아니라 목표 없음이다", async () => {
  mount("/fems/energy-reviews", {
    "GET /energy-reviews": [
      review(),
      review({ id: 6, version: 2, status: "confirmed" }),
    ],
  });
  const report = await screen.findByRole("region", { name: "검토 보고서" });
  expect(screen.getAllByRole("button", { name: "확정" })).toHaveLength(1);
  expect(report).toHaveTextContent("목표 없음");
  expect(report).not.toHaveTextContent("0 %");
});

it("달 전체가 아니라는 사실이 이슈에 남아 보인다", async () => {
  mount("/fems/energy-reviews", { "GET /energy-reviews": [review()] });
  expect(await screen.findByText(/계측 8일\/31일분/)).toBeInTheDocument();
});

it("검토 보고서는 인쇄 영역이다", async () => {
  const print = vi.fn();
  Object.defineProperty(window, "print", { value: print, writable: true });
  mount("/fems/energy-reviews", { "GET /energy-reviews": [review()] });
  const report = await screen.findByRole("region", { name: "검토 보고서" });
  expect(report).toHaveClass("print-area");
  fireEvent.click(screen.getByRole("button", { name: "보고서 인쇄" }));
  expect(print).toHaveBeenCalled();
});

// ---------- F-21 ----------

it("연 전체가 아니면 연간 배출량으로 보고하지 말라고 경고한다", async () => {
  mount("/fems/ghg-inventories", {
    "GET /ghg-inventories": [inventory()],
    "GET /ghg-inventories/8": inventory(),
  });
  expect(await screen.findByText(/연 전체가 아닙니다/)).toBeInTheDocument();
  expect(screen.getByText(/보고하면 안 됩니다/)).toBeInTheDocument();
});

it("명세서는 Scope별 합계와 사업장 공용 줄을 보인다", async () => {
  mount("/fems/ghg-inventories", {
    "GET /ghg-inventories": [inventory()],
    "GET /ghg-inventories/8": inventory(),
  });
  const table = await screen.findByRole("table", { name: "배출 시설별" });
  expect(table).toHaveTextContent("사업장 공용");
  expect(table).toHaveTextContent("ELEC");
  expect(screen.getByText(/합계 30\.5 tCO2e/)).toBeInTheDocument();
});

it("연도는 네 자리가 아니면 초안을 만들 수 없다", async () => {
  mount("/fems/ghg-inventories", { "GET /ghg-inventories": [] });
  const button = await screen.findByRole("button", { name: "초안 만들기" });
  fireEvent.change(screen.getByLabelText("연도"), { target: { value: "20" } });
  expect(button).toBeDisabled();
  fireEvent.change(screen.getByLabelText("연도"), {
    target: { value: "2026" },
  });
  expect(button).toBeEnabled();
});
