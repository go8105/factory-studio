// FS-018g F-07 목표 대비 실적. 검증 항목별로 테스트를 나눈다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import type { TargetData } from "./Targets";
const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const row = {
  unit: "kWh",
  actual: "100",
  target: "102",
  achievementRate: "98.0",
  status: "WITHIN" as const,
};
const sample = (over: Partial<TargetData> = {}): TargetData => ({
  period: {
    month: "2026-09",
    from: "2026-09-01",
    to: "2026-09-23",
    monthToDate: true,
  },
  site: [
    { ...row, energySourceCode: "ELEC", name: "전력" },
    {
      ...row,
      energySourceCode: "GAS",
      name: "도시가스",
      unit: "Nm3",
      achievementRate: "102.0",
      status: "EXCEEDED",
    },
    {
      ...row,
      energySourceCode: null,
      name: "사업장 전체 (1차에너지 환산)",
      unit: "TOE",
    },
  ],
  equipment: [
    {
      ...row,
      equipmentId: 5,
      equipmentCode: "ASM-02",
      equipmentName: "조립기 2호",
      estimatedDays: 1,
      achievementRate: "111.1",
      status: "EXCEEDED",
    },
    {
      ...row,
      equipmentId: 8,
      equipmentCode: "INS-02",
      equipmentName: "검사기 2호",
      estimatedDays: 0,
      target: null,
      achievementRate: null,
      status: "UNSET",
    },
  ],
  ...over,
});
function mockApi(data: TargetData = sample()) {
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
    .filter((url) => url.includes("/targets/performance"));
function show() {
  render(
    <MemoryRouter initialEntries={["/fems/targets"]}>
      <App />
    </MemoryRouter>,
  );
}
it("사이드바 원단위·목표에 F-07이 있다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("link", { name: /F-07 목표 대비 실적/ }),
  ).toHaveAttribute("href", "/fems/targets");
  expect(screen.getByRole("heading", { name: "원단위·목표" })).toBeVisible();
});
it("요금제는 기준정보 그룹에 있다", async () => {
  mockApi();
  show();
  const menu = await screen.findByRole("complementary", { name: "FEMS 메뉴" });
  const group = [...menu.querySelectorAll("section")].find(
    (s) => s.querySelector("h2")?.textContent === "기준정보",
  );
  expect(group?.textContent).toContain("요금제");
});
it("사업장과 설비를 별도 섹션으로 보여준다", async () => {
  mockApi();
  show();
  expect(await screen.findByLabelText("사업장 목표")).toBeVisible();
  expect(screen.getByLabelText("설비 목표")).toBeVisible();
});
it("첫 조회는 한 번만 요청하고 서버가 정한 달을 보여준다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findByLabelText("사업장 목표");
  expect(screen.getByLabelText("조회 월")).toHaveValue("2026-09");
  expect(calls(fetcher)).toHaveLength(1);
});
it("조회 월을 바꾸면 그 달로 요청한다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findByLabelText("사업장 목표");
  fireEvent.change(screen.getByLabelText("조회 월"), {
    target: { value: "2026-08" },
  });
  await waitFor(() => expect(calls(fetcher).at(-1)).toContain("month=2026-08"));
});
it("당월은 누계 기준임을 알린다", async () => {
  mockApi();
  show();
  expect(await screen.findByRole("note")).toHaveTextContent("당월 누계 기준");
});
it("지난달은 월 전체 기준임을 알린다", async () => {
  mockApi(
    sample({
      period: {
        month: "2026-08",
        from: "2026-08-01",
        to: "2026-08-31",
        monthToDate: false,
      },
    }),
  );
  show();
  expect(await screen.findByRole("note")).toHaveTextContent("월 전체 기준");
});
it("달성률과 목표 이내·초과를 텍스트로 표시한다", async () => {
  mockApi();
  show();
  const elec = await screen.findByRole("row", { name: /전력/ });
  expect(elec).toHaveTextContent("98%");
  expect(elec).toHaveTextContent("목표 이내");
  expect(screen.getByRole("row", { name: /도시가스/ })).toHaveTextContent(
    "목표 초과",
  );
});
it("목표가 없는 설비는 미설정이고 달성률을 비운다", async () => {
  mockApi();
  show();
  const ins02 = await screen.findByRole("row", { name: /INS-02/ });
  expect(ins02).toHaveTextContent("미설정");
  expect(ins02).not.toHaveTextContent("%");
});
it("추정 배분이 있는 설비는 추정 일수를 보여준다", async () => {
  mockApi();
  show();
  expect(await screen.findByText("추정 1일")).toBeVisible();
});
it("계측값이 없으면 계측 조회로 안내한다", async () => {
  mockApi({ period: null, site: [], equipment: [] });
  show();
  expect(
    await screen.findByRole("link", { name: /계측값 보기/ }),
  ).toHaveAttribute("href", "/fems/readings");
});
