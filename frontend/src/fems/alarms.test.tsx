// FEMS-1e 화면: F-18 에너지 경보, F-17 설비 비교, F-01 경보 카드.
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
const rules = [
  {
    id: 1,
    code: "AL-PEAK",
    name: "피크 임박",
    alarmKind: "PEAK",
    meterChannelId: null,
    threshold: "0.9000",
    unit: "비율",
    isActive: true,
  },
];
const alarms = [
  {
    id: 7,
    ruleCode: "AL-PEAK",
    ruleName: "피크 임박",
    alarmKind: "PEAK",
    threshold: "0.9000",
    unit: "비율",
    channelCode: null,
    equipmentCode: null,
    raisedAt: "2026-09-20T10:00:00+09:00",
    peakValue: "512.000000",
    status: "OPEN",
  },
];
const comparison = {
  month: "2026-09",
  groups: [
    {
      equipmentType: "사출기",
      ranked: [
        {
          equipmentId: 1,
          equipmentCode: "INJ-01",
          equipmentName: "사출 1호",
          energy: "1000",
          energyUnit: "kWh",
          production: "500",
          productionUnit: "EA",
          intensity: "2.000000",
          rank: 1,
        },
        {
          equipmentId: 2,
          equipmentCode: "INJ-02",
          equipmentName: "사출 2호",
          energy: "1200",
          energyUnit: "kWh",
          production: "400",
          productionUnit: "EA",
          intensity: "3.000000",
          rank: 2,
        },
      ],
      unranked: [
        {
          equipmentId: 3,
          equipmentCode: "INJ-03",
          equipmentName: "사출 3호",
          energy: "80",
          energyUnit: "kWh",
          production: null,
          productionUnit: null,
          intensity: null,
        },
      ],
    },
  ],
};

function mount(path: string, overrides: Record<string, unknown> = {}) {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input).split("?")[0];
      const key = `${init?.method ?? "GET"} ${url}`;
      if (key in overrides)
        return new Response(JSON.stringify({ data: overrides[key] }), {
          status: 200,
        });
      if (url.endsWith("/sessions/current"))
        return new Response(JSON.stringify({ data: session }));
      if (url.endsWith("/fems/alarm-rules"))
        return new Response(JSON.stringify({ data: rules }));
      if (url.endsWith("/fems/alarms"))
        return new Response(JSON.stringify({ data: alarms }));
      if (url.endsWith("/fems/equipment-comparison"))
        return new Response(JSON.stringify({ data: comparison }));
      if (url.endsWith("/fems/meters"))
        return new Response(JSON.stringify({ data: [] }));
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

it("상시 감시가 아니라고 밝힌다", async () => {
  mount("/fems/alarms");
  expect(await screen.findByText(/상시 감시가 아닙니다/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "지금 점검" })).toBeInTheDocument();
});

it("지금 점검은 걸린 규칙이 없으면 그렇게 말한다", async () => {
  const fetcher = mount("/fems/alarms", {
    "POST /api/v1/fems/alarms/evaluate": { raised: [], skipped: [] },
  });
  fireEvent.click(await screen.findByRole("button", { name: "지금 점검" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/alarms/evaluate")).toHaveLength(1),
  );
  expect(await screen.findByText(/걸린 규칙이 없습니다/)).toBeInTheDocument();
});

it("발생한 경보는 확인과 해제를 함께 둔다", async () => {
  mount("/fems/alarms");
  await screen.findByRole("table", { name: "진행 중인 경보" });
  // 발생 상태에서만 확인이 보이고, 해제는 늘 보인다(한 방향으로만 간다).
  expect(screen.getByRole("button", { name: "확인" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "해제" })).toBeEnabled();
  // 넘은 값과 임계를 나란히 읽는다.
  expect(screen.getByText(/512 \/ 0\.9/)).toBeInTheDocument();
});

it("피크 규칙의 임계값이 비율임을 알린다", async () => {
  mount("/fems/alarms");
  fireEvent.click(await screen.findByRole("button", { name: "규칙 추가" }));
  fireEvent.change(screen.getByLabelText("종류"), {
    target: { value: "PEAK" },
  });
  expect(screen.getByText(/계약전력 대비 비율입니다/)).toBeInTheDocument();
});

it("설비 비교는 종류 안에서만 줄 세운다", async () => {
  mount("/fems/equipment-comparison");
  const table = await screen.findByRole("table", {
    name: "사출기 원단위 순위",
  });
  const rows = table.querySelectorAll("tbody tr");
  expect(rows).toHaveLength(2);
  expect(rows[0]).toHaveTextContent("INJ-01");
  expect(
    screen.getByText(/종류가 다른\s*설비는 비교하지 않습니다/),
  ).toBeInTheDocument();
});

it("생산량이 없는 설비는 순위 밖으로 따로 적는다", async () => {
  mount("/fems/equipment-comparison");
  expect(
    await screen.findByText(/생산량이 없어 비교하지 못한 설비: INJ-03/),
  ).toBeInTheDocument();
});
