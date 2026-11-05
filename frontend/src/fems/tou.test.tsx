// FEMS-1c 화면: F-16 부하 패턴·피크와 F-08 TOU 소계 (DSN-15 F25·F26·Q1·Q2).
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import { SourceBilling, type BillingSource } from "./Billing";

const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2099-01-01T00:00:00+09:00",
  csrfToken: "test-csrf",
};

const pattern = {
  month: "2026-09",
  source: { id: 1, sourceCode: "ELEC", name: "전력", unit: "kWh" },
  sources: [{ id: 1, sourceCode: "ELEC", name: "전력" }],
  profile: [
    { dayKind: "WEEKDAY", hour: 3, days: 20, average: "120", max: "150" },
    { dayKind: "WEEKDAY", hour: 14, days: 20, average: "480", max: "520" },
    { dayKind: "HOLIDAY", hour: 14, days: 4, average: "90", max: "110" },
  ],
  peak: {
    value: "520",
    date: "2026-09-15",
    hour: 14,
    contractKw: "300.00",
    contractRatio: "173.3",
  },
  baseLoad: { value: "120", average: "135", hours: "0~6" },
  hasHolidayCalendar: true,
};

function mount(data: unknown) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    return new Response(
      JSON.stringify({
        data: url.endsWith("/sessions/current") ? session : data,
      }),
      { status: 200 },
    );
  });
  render(
    <MemoryRouter initialEntries={["/fems/load-pattern"]}>
      <App />
    </MemoryRouter>,
  );
}

it("수요전력이 1시간 근사임을 밝힌다", async () => {
  mount(pattern);
  expect(await screen.findByText(/1시간 근사/)).toBeInTheDocument();
  const peak = screen.getByRole("region", { name: "수요전력" });
  expect(peak).toHaveTextContent("520");
  expect(peak).toHaveTextContent("14시");
});

it("계약전력이 없으면 비율을 0이 아니라 계산 불가로 둔다", async () => {
  mount({
    ...pattern,
    peak: { ...pattern.peak, contractKw: null, contractRatio: null },
  });
  const tile = await screen.findByRole("region", { name: "계약전력 대비" });
  expect(tile).toHaveTextContent("계산 불가");
  expect(tile).toHaveTextContent("적용 요금제에 계약전력이 없습니다");
});

it("휴일 달력이 비면 일요일만 휴일로 보았다고 알린다", async () => {
  mount({ ...pattern, hasHolidayCalendar: false });
  expect(await screen.findByText(/일요일만 휴일/)).toBeInTheDocument();
  expect(screen.getByText("휴일 달력 없음")).toBeInTheDocument();
});

it("시간대·요일 표는 24행이고 없는 칸은 줄표다", async () => {
  mount(pattern);
  const table = await screen.findByRole("table", {
    name: "시간대·요일 평균 사용량",
  });
  expect(table.querySelectorAll("tbody tr")).toHaveLength(24);
  const row3 = table.querySelectorAll("tbody tr")[3];
  expect(row3).toHaveTextContent("120");
  // 토요일 3시는 자료가 없다 — 0이 아니라 줄표다.
  expect(row3.querySelectorAll("td")[1]).toHaveTextContent("—");
});

it("기저부하는 밤 최솟값으로 적는다", async () => {
  mount(pattern);
  const tile = await screen.findByRole("region", { name: "기저부하" });
  expect(tile).toHaveTextContent("120");
  expect(tile).toHaveTextContent("0~6시 최솟값");
});

const touSource: BillingSource = {
  energySourceId: 1,
  sourceCode: "ELEC",
  name: "전력",
  unit: "kWh",
  status: "CALCULATED",
  usage: "1000",
  total: "2596000",
  segments: [
    {
      month: "2026-09",
      usage: "1000",
      tariff: {
        tariffCode: "TR-TOU-01",
        name: "산업용(을)",
        tariffKind: "TOU",
        contractKw: "300.00",
        basicCharge: "8320",
        usageRate: "0",
        effectiveFrom: "2026-09",
        effectiveTo: null,
      },
      basicCharge: "2496000",
      usageCharge: "100000",
      amount: "2596000",
      loadBands: [
        { loadBand: "OFF_PEAK", usage: "400", charge: "20000" },
        { loadBand: "MID", usage: "400", charge: "40000" },
        { loadBand: "PEAK", usage: "200", charge: "40000" },
      ],
    },
  ],
};

it("TOU 구간은 계약전력과 부하 구분별 소계를 보인다", () => {
  render(<SourceBilling source={touSource} />);
  expect(screen.getByText("시간대별")).toBeInTheDocument();
  expect(screen.getByText(/계약 300 kW/)).toBeInTheDocument();
  expect(screen.getByText("경부하")).toBeInTheDocument();
  expect(screen.getByText(/200 kWh · 40,000원/)).toBeInTheDocument();
  // TOU는 단가 한 줄로 설명되지 않는다 — "× 단가"를 쓰지 않는다.
  expect(screen.queryByText(/× 0원/)).toBeNull();
});
