// FS-018f F-01 대시보드. 검증 항목별로 테스트를 나눈다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import {
  Composition,
  DailyChart,
  TargetTile,
  type DashboardData,
} from "./Dashboard";
const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const converted = (
  sourceCode: string,
  name: string,
  toe: string | null,
  status: DashboardData["primaryEnergy"]["sources"][0]["status"] = "CALCULATED",
) => ({
  sourceCode,
  name,
  status,
  consumption: { quantity: "100", unit: "kWh" },
  toe,
});
const sample = (over: Partial<DashboardData> = {}): DashboardData => ({
  period: { month: "2026-09", from: "2026-09-01", to: "2026-09-23" },
  primaryEnergy: {
    total: "12.365156",
    unit: "TOE",
    complete: true,
    sources: [
      converted("ELEC", "전력", "11.163956"),
      converted("GAS", "도시가스", "1.2012"),
      converted("WATER", "용수", null, "NOT_APPLICABLE"),
    ],
  },
  target: {
    status: "SET",
    target: "12.488808",
    actual: "12.365156",
    unit: "TOE",
    achievementRate: "99.0",
  },
  charge: { total: "8345117", currency: "KRW", complete: true },
  emission: { total: "24.989514", unit: "tCO2eq", complete: true },
  daily: [
    { date: "2026-09-01", toe: "0.5" },
    { date: "2026-09-02", toe: "0.6" },
  ],
  topEquipment: [
    {
      equipmentId: 2,
      equipmentCode: "INJ-02",
      equipmentName: "사출기 2호",
      energySourceCode: "ELEC",
      unit: "kWh",
      quantity: "9000",
      days: 23,
      estimatedDays: 0,
    },
  ],
  quality: {
    issues: 6,
    recent: [
      {
        observedAt: "2026-09-07T07:00:00+00:00",
        timezone: "Asia/Seoul",
        channelName: "조립기 2호 전력",
        quality: "invalid",
      },
    ],
  },
  ...over,
});
function mockApi(data: DashboardData = sample()) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    return new Response(
      JSON.stringify({
        data: url.endsWith("/sessions/current") ? session : data,
      }),
      { status: 200 },
    );
  });
}
const dashboardCalls = (fetcher: ReturnType<typeof mockApi>) =>
  fetcher.mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes("/fems/dashboard"));
function show(path = "/fems/dashboard") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
it("FEMS 진입은 F-01 대시보드로 이동한다", async () => {
  mockApi();
  show("/fems");
  expect(
    await screen.findByRole("heading", { name: "에너지 개요" }),
  ).toBeVisible();
});
it("네 가지 핵심 지표를 보여준다", async () => {
  mockApi();
  show();
  for (const label of ["총 소비", "목표 대비", "예상 요금", "배출량"])
    expect(await screen.findByLabelText(label)).toBeVisible();
});
it("첫 조회는 월 없이 한 번만 요청하고 서버가 정한 달을 보여준다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findByLabelText("총 소비");
  expect(screen.getByLabelText("조회 월")).toHaveValue("2026-09");
  expect(dashboardCalls(fetcher)).toHaveLength(1);
  expect(dashboardCalls(fetcher)[0]).not.toContain("month=");
});
it("조회 월을 바꾸면 그 달로 요청한다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findByLabelText("총 소비");
  fireEvent.change(screen.getByLabelText("조회 월"), {
    target: { value: "2026-08" },
  });
  await waitFor(() =>
    expect(dashboardCalls(fetcher).at(-1)).toContain("month=2026-08"),
  );
});
it("달성률 100% 이하는 목표 이내로 표시한다", () => {
  render(<TargetTile target={sample().target} />);
  expect(screen.getByText("목표 이내")).toBeVisible();
});
it("달성률 100% 초과는 목표 초과로 표시한다", () => {
  render(
    <TargetTile target={{ ...sample().target, achievementRate: "104.2" }} />,
  );
  expect(screen.getByText("목표 초과")).toBeVisible();
});
it("목표가 없으면 미설정으로 두고 달성률을 쓰지 않는다", () => {
  render(
    <TargetTile
      target={{
        ...sample().target,
        status: "UNSET",
        target: null,
        achievementRate: null,
      }}
    />,
  );
  expect(screen.getByText("미설정")).toBeVisible();
  expect(screen.queryByText("%")).not.toBeInTheDocument();
});
it("일부 계산 불가면 총 소비에 알린다", async () => {
  mockApi(
    sample({
      primaryEnergy: { ...sample().primaryEnergy, complete: false },
    }),
  );
  show();
  expect(await screen.findByLabelText("총 소비")).toHaveTextContent(
    "일부 계산 불가",
  );
});
it("구성은 TOE 환산 비중으로 보여준다", () => {
  render(<Composition sources={sample().primaryEnergy.sources} />);
  expect(screen.getByText(/11\.164 TOE · 90\.3%/)).toBeVisible();
});
it("용수는 구성 막대 대신 환산 대상 아님으로 표시한다", () => {
  render(<Composition sources={sample().primaryEnergy.sources} />);
  expect(screen.getByText(/용수: 환산 대상 아님/)).toBeVisible();
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
});
it("일자별 추이는 선 그래프로 그린다", () => {
  render(<DailyChart daily={sample().daily} />);
  expect(
    screen.getByRole("img", { name: "일자별 TOE 선 그래프" }),
  ).toBeVisible();
});
it("설비 상위 목록은 설비별 배분으로 연결된다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("link", { name: /설비별 배분 보기/ }),
  ).toHaveAttribute("href", "/fems/allocations");
});
it("품질 이상 건수와 최근 항목을 보여준다", async () => {
  mockApi();
  show();
  const panel = await screen.findByLabelText("계측 품질 이상");
  expect(panel).toHaveTextContent("6건");
  expect(panel).toHaveTextContent("조립기 2호 전력");
});
it("계측값이 없으면 기준정보 등록으로 안내한다", async () => {
  mockApi({ period: null } as DashboardData);
  show();
  expect(
    await screen.findByRole("link", { name: /에너지원 등록/ }),
  ).toHaveAttribute("href", "/fems/energy-sources");
});
