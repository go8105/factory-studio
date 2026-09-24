// FS-018c F-03 설비별 배분. 검증 항목별로 테스트를 나눈다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import {
  AllocationSummary,
  BasisPanel,
  type Allocation,
  type SummaryRow,
} from "./Allocations";
const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const allocation = (over: Partial<Allocation> = {}): Allocation => ({
  id: 1,
  periodStart: "2026-09-06T15:00:00+00:00",
  periodEnd: "2026-09-07T15:00:00+00:00",
  timezone: "Asia/Seoul",
  equipmentId: 5,
  equipmentCode: "ASM-02",
  equipmentName: "조립기 2호",
  channelCode: "CH-ASM-02-KWH",
  channelName: "조립기 2호 전력",
  energySourceCode: "ELEC",
  quantity: "1234.5",
  unit: "kWh",
  methodKey: "DIRECT_METER",
  methodVersion: 1,
  inputRevision: 1,
  quality: "estimated",
  basis: { summed_hours: 18, missing_hours: 6 },
  isLatest: true,
  ...over,
});
const summary: SummaryRow[] = [
  {
    equipmentId: 5,
    equipmentCode: "ASM-02",
    equipmentName: "조립기 2호",
    energySourceCode: "ELEC",
    unit: "kWh",
    quantity: "1234.5",
    days: 1,
    estimatedDays: 1,
  },
  {
    equipmentId: 1,
    equipmentCode: "INJ-01",
    equipmentName: "사출기 1호",
    energySourceCode: "WATER",
    unit: "m3",
    quantity: "3.2",
    days: 1,
    estimatedDays: 0,
  },
];
function mockApi(rows: Allocation[] = [allocation()]) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const data = url.endsWith("/sessions/current")
      ? session
      : url.includes("/fems/allocations")
        ? rows
        : [];
    return new Response(
      JSON.stringify({
        data,
        page: { offset: 0, limit: 50, total: rows.length },
        range: { from: "2026-09-17", to: "2026-09-23" },
        summary,
      }),
      { status: 200 },
    );
  });
}
const allocationCalls = (fetcher: ReturnType<typeof mockApi>) =>
  fetcher.mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes("/fems/allocations"));
function show() {
  render(
    <MemoryRouter initialEntries={["/fems/allocations"]}>
      <App />
    </MemoryRouter>,
  );
}
it("사이드바 에너지 현황에 F-03이 있다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("link", { name: /F-03 설비별 배분/ }),
  ).toHaveAttribute("href", "/fems/allocations");
});
it("첫 조회는 서버가 정한 기간을 입력 칸에 보여준다", async () => {
  mockApi();
  show();
  await waitFor(() =>
    expect(screen.getByLabelText("시작일")).toHaveValue("2026-09-17"),
  );
});
it("합계는 단위별로 표를 나눈다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("heading", { name: "설비별 합계 · kWh" }),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "설비별 합계 · m3" }),
  ).toBeVisible();
});
it("합계에 추정 일수를 표시한다", () => {
  render(<AllocationSummary rows={summary} />);
  expect(screen.getByText("추정 1일")).toBeVisible();
});
it("배분 방법은 한국어 이름으로 표시한다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("cell", { name: "전용 계량기 직접 귀속" }),
  ).toBeVisible();
});
it("근거 패널은 접힌 상태로 시작한다", () => {
  const { container } = render(<BasisPanel row={allocation()} />);
  expect(container.querySelector("details")).not.toHaveAttribute("open");
});
it("근거 패널은 근거 항목을 한국어 라벨로 보여준다", () => {
  render(<BasisPanel row={allocation()} />);
  fireEvent.click(screen.getByText("근거"));
  expect(screen.getByText("결측 시간")).toBeInTheDocument();
  expect(screen.getByText("6")).toBeInTheDocument();
});
it("근거 패널은 방법 버전과 입력 버전을 보여준다", () => {
  render(
    <BasisPanel row={allocation({ methodVersion: 2, inputRevision: 3 })} />,
  );
  expect(screen.getByText(/v2/)).toBeInTheDocument();
  expect(screen.getByText("3")).toBeInTheDocument();
});
it("기본 조회는 이전 결과를 요청하지 않는다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findByRole("heading", { name: "설비별 합계 · kWh" });
  expect(allocationCalls(fetcher)[0]).not.toContain("includeSuperseded");
});
it("이전 결과 포함은 조회 버튼 후 요청하고 결과 열을 보여준다", async () => {
  const fetcher = mockApi([
    allocation(),
    allocation({ id: 2, inputRevision: 0, isLatest: false }),
  ]);
  show();
  await screen.findByRole("heading", { name: "설비별 합계 · kWh" });
  fireEvent.click(screen.getByLabelText("이전 산정 결과 포함"));
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() =>
    expect(allocationCalls(fetcher).at(-1)).toContain("includeSuperseded=true"),
  );
  expect(await screen.findByRole("cell", { name: "이전" })).toBeVisible();
});
it("조회 조건은 설비와 방법을 전달한다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findByRole("heading", { name: "설비별 합계 · kWh" });
  fireEvent.change(screen.getByLabelText("배분 방법"), {
    target: { value: "RUNTIME_SHARE" },
  });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() =>
    expect(allocationCalls(fetcher).at(-1)).toContain(
      "methodKey=RUNTIME_SHARE",
    ),
  );
});
