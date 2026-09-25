// FS-018j F-06 원단위 분석. 검증 항목별로 테스트를 나눈다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import {
  ChangeBadge,
  RecordStatus,
  type IntensityData,
  type IntensityRecord,
} from "./Intensity";
const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const record = (over: Partial<IntensityRecord> = {}): IntensityRecord => ({
  id: 1,
  sourceKey: "MES:LT-0013:INJ",
  versionNo: 1,
  equipmentCode: "INJ-01",
  equipmentName: "사출기 1호",
  itemCode: "FG-C100",
  startDate: "2026-08-25",
  endDate: "2026-08-27",
  productionQty: "1970.000",
  unit: "EA",
  energy: [
    { quantity: "3179.25", unit: "kWh" },
    { quantity: "18", unit: "m3" },
  ],
  intensity: [
    { value: "1.613832", unit: "kWh/EA" },
    { value: "0.009137", unit: "m3/EA" },
  ],
  toePerUnit: "0.000370",
  status: "CALCULATED",
  ...over,
});
const sample = (over: Partial<IntensityData> = {}): IntensityData => ({
  period: { from: "2026-08-24", to: "2026-09-23" },
  records: [
    record(),
    record({
      id: 2,
      sourceKey: "MES:LT-0018:INS",
      productionQty: "0.000",
      intensity: [],
      toePerUnit: null,
      status: "NO_PRODUCTION",
    }),
  ],
  items: [
    {
      itemCode: "FG-C100",
      lots: ["LT-0013", "LT-0016"],
      energy: { quantity: "7771.5", unit: "kWh" },
      output: { quantity: "3880.000", unit: "EA" },
      intensity: "2.002964",
      intensityUnit: "kWh/EA",
      status: "CALCULATED",
      baseline: {
        code: "BL-C100-01",
        value: "2.002964",
        unit: "kWh/EA",
        periodFrom: "2026-05",
        periodTo: "2026-06",
      },
      changeRate: "0.0",
    },
  ],
  ...over,
});
function mockApi(data: IntensityData = sample()) {
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
    .filter((url) => url.includes("/fems/intensity"));
function show() {
  render(
    <MemoryRouter initialEntries={["/fems/intensity"]}>
      <App />
    </MemoryRouter>,
  );
}
it("사이드바 원단위·목표에 F-06이 있다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("link", { name: /F-06 원단위 분석/ }),
  ).toHaveAttribute("href", "/fems/intensity");
});
it("원단위 계산 규칙을 화면에 적는다", async () => {
  mockApi();
  show();
  expect(await screen.findByRole("note")).toHaveTextContent(
    "최신 확정 버전만 쓰고 초안은 뺍니다",
  );
});
it("첫 조회는 기간 없이 요청하고 서버 기간을 채운다", async () => {
  const fetcher = mockApi();
  show();
  await waitFor(() =>
    expect(screen.getByLabelText("시작일")).toHaveValue("2026-08-24"),
  );
  expect(calls(fetcher)[0]).not.toContain("from=");
});
it("조회 버튼은 입력한 기간으로 요청한다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findByLabelText("품목 원단위");
  fireEvent.change(screen.getByLabelText("시작일"), {
    target: { value: "2026-09-01" },
  });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() =>
    expect(calls(fetcher).at(-1)).toContain("from=2026-09-01"),
  );
});
it("품목 원단위와 기준선을 함께 보여준다", async () => {
  mockApi();
  show();
  const row = await screen.findByRole("row", { name: /FG-C100/ });
  expect(row).toHaveTextContent("2.003 kWh/EA");
  expect(row).toHaveTextContent("BL-C100-01");
});
it("기준선보다 크면 악화로 표시한다", () => {
  render(<ChangeBadge rate="3.2" />);
  expect(screen.getByText("+3.2% 악화")).toBeVisible();
});
it("기준선보다 작으면 개선으로 표시한다", () => {
  render(<ChangeBadge rate="-1.5" />);
  expect(screen.getByText("-1.5% 개선")).toBeVisible();
});
it("증감이 없으면 기준선과 같음으로 표시한다", () => {
  render(<ChangeBadge rate="0.0" />);
  expect(screen.getByText("기준선과 같음")).toBeVisible();
});
it("생산량 0은 계산 불가로 표시한다", () => {
  render(<RecordStatus record={record({ status: "NO_PRODUCTION" })} />);
  expect(screen.getByText("생산량 없음 · 계산 불가")).toBeVisible();
});
it("배분 결과가 없으면 따로 표시한다", () => {
  render(<RecordStatus record={record({ status: "NO_ENERGY" })} />);
  expect(screen.getByText("배분 결과 없음")).toBeVisible();
});
it("에너지원별 원단위를 합치지 않고 나란히 보여준다", async () => {
  mockApi();
  show();
  const row = await screen.findByRole("row", { name: /MES:LT-0013:INJ/ });
  expect(row).toHaveTextContent("1.614 kWh/EA · 0.009 m3/EA");
  expect(row).toHaveTextContent("TOE/EA");
});
it("확정 기준선이 없으면 없다고 적는다", async () => {
  mockApi(
    sample({
      items: [{ ...sample().items[0], baseline: null, changeRate: null }],
    }),
  );
  show();
  expect(await screen.findByText("확정 기준선 없음")).toBeVisible();
});
it("확정 생산량이 없으면 생산량 등록으로 안내한다", async () => {
  mockApi(sample({ records: [], items: [] }));
  show();
  expect(
    await screen.findByRole("link", { name: /생산량 등록/ }),
  ).toHaveAttribute("href", "/fems/production");
});
