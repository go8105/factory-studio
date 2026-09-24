// FS-018d F-04 배출량 현황. 검증 항목별로 테스트를 나눈다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import {
  EmissionBasis,
  type EmissionResult,
  type EmissionSource,
} from "./Emissions";
const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const elec: EmissionSource = {
  energySourceId: 1,
  sourceCode: "ELEC",
  name: "전력",
  sourceKind: "ELECTRIC",
  status: "CALCULATED",
  consumption: { quantity: "1000", unit: "kWh" },
  excludedReadings: 2,
  emission: "0.46",
  segments: [
    {
      year: "2026",
      consumption: { quantity: "1000", unit: "kWh" },
      factor: {
        kind: "EMISSION",
        year: "2026",
        value: "0.000460",
        unit: "tCO2eq/kWh",
        source: "합성 예시값 — 공표 계수 아님",
      },
      emission: "0.460000",
    },
  ],
};
const water: EmissionSource = {
  ...elec,
  energySourceId: 3,
  sourceCode: "WATER",
  name: "용수",
  sourceKind: "UTILITY",
  status: "NOT_APPLICABLE",
  consumption: { quantity: "340", unit: "m3" },
  excludedReadings: 0,
  emission: null,
  segments: [],
};
const gasMissing: EmissionSource = {
  ...elec,
  energySourceId: 2,
  sourceCode: "GAS",
  name: "도시가스",
  sourceKind: "FUEL",
  status: "FACTOR_MISSING",
  consumption: { quantity: "30", unit: "Nm3" },
  emission: null,
  segments: [
    {
      year: "2026",
      consumption: { quantity: "30", unit: "Nm3" },
      factor: null,
      emission: null,
    },
  ],
};
const result = (over: Partial<EmissionResult> = {}): EmissionResult => ({
  period: { from: "2026-09-01", to: "2026-09-23" },
  sources: [elec, water],
  totalEmission: "0.46",
  unit: "tCO2eq",
  complete: true,
  ...over,
});
function mockApi(data: EmissionResult = result()) {
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
const emissionCalls = (fetcher: ReturnType<typeof mockApi>) =>
  fetcher.mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes("/fems/emissions"));
function show() {
  render(
    <MemoryRouter initialEntries={["/fems/emissions"]}>
      <App />
    </MemoryRouter>,
  );
}
it("사이드바 에너지 현황에 F-04가 있다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("link", { name: /F-04 배출량 현황/ }),
  ).toHaveAttribute("href", "/fems/emissions");
});
it("첫 조회는 기간 없이 요청하고 서버 기간을 채운다", async () => {
  const fetcher = mockApi();
  show();
  await waitFor(() =>
    expect(screen.getByLabelText("시작일")).toHaveValue("2026-09-01"),
  );
  expect(emissionCalls(fetcher)[0]).not.toContain("from=");
});
it("총 배출량을 단위와 함께 보여준다", async () => {
  mockApi();
  show();
  expect(await screen.findByLabelText("총 배출량")).toHaveTextContent(
    "0.46 tCO2eq",
  );
});
it("계산 불가가 있으면 합계에서 빠졌다고 알린다", async () => {
  mockApi(result({ sources: [elec, gasMissing], complete: false }));
  show();
  expect(await screen.findByText(/일부 에너지원은 계산 불가/)).toBeVisible();
});
it("UTILITY는 대상 아님으로 표시한다", async () => {
  mockApi();
  show();
  expect(await screen.findByText("대상 아님")).toBeVisible();
});
it("계수 없음은 대상 아님과 다른 문구로 표시한다", async () => {
  mockApi(result({ sources: [gasMissing], complete: false }));
  show();
  expect(await screen.findByText("계수 없음 · 계산 불가")).toBeVisible();
  expect(screen.queryByText("대상 아님")).not.toBeInTheDocument();
});
it("근거에 배출계수 값·단위·출처를 보여준다", () => {
  render(<EmissionBasis source={elec} />);
  fireEvent.click(screen.getByText("근거"));
  expect(screen.getByText("0.000460 tCO2eq/kWh")).toBeInTheDocument();
  expect(screen.getByText("합성 예시값 — 공표 계수 아님")).toBeInTheDocument();
});
it("근거에 제외한 결측 건수를 보여준다", () => {
  render(<EmissionBasis source={elec} />);
  expect(screen.getByText(/결측 2건은 소비량에서 제외/)).toBeInTheDocument();
});
it("대상 아님 에너지원은 근거 표 대신 설명을 보여준다", () => {
  render(<EmissionBasis source={water} />);
  expect(screen.getByText(/배출 산정 대상이 아닙니다/)).toBeVisible();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});
it("조회 버튼은 입력한 기간으로 요청한다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findByLabelText("총 배출량");
  fireEvent.change(screen.getByLabelText("시작일"), {
    target: { value: "2026-09-05" },
  });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() =>
    expect(emissionCalls(fetcher).at(-1)).toContain("from=2026-09-05"),
  );
});
it("계측값이 없으면 계측 조회로 안내한다", async () => {
  mockApi(result({ sources: [], totalEmission: "0" }));
  show();
  expect(
    await screen.findByRole("link", { name: /계측값 보기/ }),
  ).toHaveAttribute("href", "/fems/readings");
});
