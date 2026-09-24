// FS-018h F-08 요금 산정. 검증 항목별로 테스트를 나눈다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import { SourceBilling, type BillingData, type BillingSource } from "./Billing";
const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const tariff = (
  code: string,
  rate: string,
  from: string,
  to: string | null,
) => ({
  tariffCode: code,
  name: "산업용",
  basicCharge: "250000",
  usageRate: rate,
  effectiveFrom: from,
  effectiveTo: to,
});
const elec: BillingSource = {
  energySourceId: 1,
  sourceCode: "ELEC",
  name: "전력",
  unit: "kWh",
  status: "CALCULATED",
  usage: "300",
  total: "537000",
  segments: [
    {
      month: "2026-08",
      usage: "100",
      tariff: tariff("TR-ELEC-01", "120", "2025-09", "2026-08"),
      basicCharge: "250000",
      usageCharge: "12000",
      amount: "262000",
    },
    {
      month: "2026-09",
      usage: "200",
      tariff: tariff("TR-ELEC-02", "130", "2026-09", null),
      basicCharge: "250000",
      usageCharge: "26000",
      amount: "276000",
    },
  ],
};
const sample = (over: Partial<BillingData> = {}): BillingData => ({
  period: {
    from: "2026-08",
    to: "2026-09",
    dateFrom: "2026-08-01",
    dateTo: "2026-09-23",
    monthToDate: true,
  },
  sources: [elec],
  total: "538000",
  currency: "KRW",
  complete: true,
  ...over,
});
function mockApi(data: BillingData = sample()) {
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
const calls = (fetcher: ReturnType<typeof mockApi>) =>
  fetcher.mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes("/fems/billing"));
function show() {
  render(
    <MemoryRouter initialEntries={["/fems/billing"]}>
      <App />
    </MemoryRouter>,
  );
}
it("사이드바 요금 그룹에 F-08이 있다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("link", { name: /F-08 요금 산정/ }),
  ).toHaveAttribute("href", "/fems/billing");
  expect(screen.getByRole("heading", { name: "요금" })).toBeVisible();
});
it("첫 조회는 기간 없이 요청하고 서버 기간을 채운다", async () => {
  const fetcher = mockApi();
  show();
  await waitFor(() =>
    expect(screen.getByLabelText("시작월")).toHaveValue("2026-08"),
  );
  expect(calls(fetcher)[0]).not.toContain("from=");
});
it("조회 버튼은 입력한 월로 요청한다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findByLabelText("예상 요금 합계");
  fireEvent.change(screen.getByLabelText("시작월"), {
    target: { value: "2026-07" },
  });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() => expect(calls(fetcher).at(-1)).toContain("from=2026-07"));
});
it("합계를 원 단위로 보여준다", async () => {
  mockApi();
  show();
  expect(await screen.findByLabelText("예상 요금 합계")).toHaveTextContent(
    "538,000 원",
  );
});
it("당월이 누계 기준임을 알린다", async () => {
  mockApi();
  show();
  expect(await screen.findByLabelText("예상 요금 합계")).toHaveTextContent(
    "2026-09-23까지 누계",
  );
});
it("요금제가 바뀐 달은 구간별 요금제를 보여준다", () => {
  render(<SourceBilling source={elec} />);
  expect(screen.getByText(/TR-ELEC-01 \(2025-09 ~ 2026-08\)/)).toBeVisible();
  expect(screen.getByText(/TR-ELEC-02 \(2026-09 ~ 계속\)/)).toBeVisible();
});
it("구간마다 사용량 × 단가 계산을 보여준다", () => {
  render(<SourceBilling source={elec} />);
  expect(screen.getByText(/200 kWh × 130원 = 26,000원/)).toBeVisible();
});
it("요금제 없는 달은 요금제 없음으로 표시한다", () => {
  render(
    <SourceBilling
      source={{
        ...elec,
        status: "TARIFF_MISSING",
        segments: [
          {
            ...elec.segments[1],
            tariff: null,
            basicCharge: null,
            usageCharge: null,
            amount: null,
          },
        ],
      }}
    />,
  );
  expect(screen.getByText("요금제 없음")).toBeVisible();
  expect(screen.getByText("요금제 없는 달 제외")).toBeVisible();
});
it("합계가 불완전하면 알린다", async () => {
  mockApi(sample({ complete: false }));
  show();
  expect(
    await screen.findByText("요금제 없는 달은 합계에서 빠졌습니다"),
  ).toBeVisible();
});
it("요금 부과 대상이 아닌 에너지원은 표 대신 설명을 보여준다", () => {
  render(
    <SourceBilling
      source={{ ...elec, status: "NOT_BILLABLE", total: null, segments: [] }}
    />,
  );
  expect(screen.getByText(/요금 부과 대상이 아닙니다/)).toBeVisible();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});
it("계측값이 없으면 계측 조회로 안내한다", async () => {
  mockApi(sample({ sources: [] }));
  show();
  expect(
    await screen.findByRole("link", { name: /계측값 보기/ }),
  ).toHaveAttribute("href", "/fems/readings");
});
