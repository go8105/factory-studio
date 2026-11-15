// BEMS-1f 화면: B-11 건물 에너지, B-12 공용 비용 배분, B-13 월간 보고서.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const B = "/api/v1/bems";
type Reply = { status: number; body?: unknown };
const ok = (data: unknown, status = 200): Reply => ({ status, body: { data } });

function mount(path: string, replies: Record<string, Reply> = {}) {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input).split("?")[0];
      const reply = replies[`${init?.method ?? "GET"} ${url}`];
      if (reply)
        return new Response(JSON.stringify(reply.body), {
          status: reply.status,
        });
      if (url.endsWith("/sessions/current"))
        return new Response(
          JSON.stringify({
            data: {
              actorKind: "GUEST",
              workspaceId: 1,
              generationId: 2,
              roles: ["GUEST"],
              expiresAt: "2099-01-01T00:00:00Z",
              csrfToken: "csrf-test",
            },
          }),
        );
      return new Response(JSON.stringify({ data: [] }));
    });
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  return fetcher;
}
const sent = (
  fetcher: ReturnType<typeof mount>,
  method: string,
  suffix: string,
) =>
  fetcher.mock.calls.filter(
    ([url, init]) =>
      (init?.method ?? "GET") === method &&
      String(url).split("?")[0].endsWith(suffix),
  );

it("B-11 연면적·목표가 없으면 0%가 아니라 '—'로 둔다", async () => {
  mount("/bems/energy", {
    [`GET ${B}/building-energy`]: ok({
      month: "2026-09",
      totalKwh: "30.00",
      grossAreaM2: "0.00",
      euiKwhPerM2: null,
      targetKwh: null,
      achievement: null,
      zones: [],
    }),
  });
  expect(await screen.findByText("30 kWh")).toBeVisible();
  expect(screen.getByText("목표 없음")).toBeVisible();
  // 원단위·달성률 칸이 모두 '—'다.
  expect(screen.getAllByText("—").length).toBeGreaterThan(0);
});

it("B-11 달성률이 100%를 넘으면 눈에 띄게 표시한다", async () => {
  mount("/bems/energy", {
    [`GET ${B}/building-energy`]: ok({
      month: "2026-09",
      totalKwh: "50.00",
      grossAreaM2: "2000.00",
      euiKwhPerM2: "0.0250",
      targetKwh: "40.00",
      achievement: "1.2500",
      zones: [
        {
          zoneId: 1,
          zoneCode: "Z-OFF",
          zoneName: "사무동",
          kind: "OFFICE",
          floorAreaM2: "1000.00",
          kwh: "50.00",
          euiKwhPerM2: "0.0500",
          targetKwh: null,
          achievement: null,
        },
      ],
    }),
  });
  // 건물 전체 달성률은 KPI 숫자로, 구역 달성률은 배지로 보인다.
  expect(await screen.findByText("125%")).toHaveClass("kpi-value");
  expect(screen.getByText("목표 없음")).toHaveClass("badge", { exact: false });
  expect(screen.getByText("0.025")).toBeVisible();
});

it("B-12 부서별 배분과 확정을 보인다", async () => {
  const run = {
    id: 3,
    costMonth: "2026-09",
    version: 1,
    status: "draft",
    totalKwh: "30.00",
    totalCost: "4000.00",
    currency: "KRW",
    confirmedAt: null,
    lines: [
      {
        id: 1,
        departmentCode: "ADM",
        areaM2: "1000.00",
        share: "0.250000",
        cost: "1000.00",
        currency: "KRW",
      },
      {
        id: 2,
        departmentCode: "PROD",
        areaM2: "3000.00",
        share: "0.750000",
        cost: "3000.00",
        currency: "KRW",
      },
    ],
  };
  const fetcher = mount("/bems/costs", {
    [`GET ${B}/cost-runs`]: ok([run]),
    [`GET ${B}/cost-runs/3`]: ok(run),
    [`POST ${B}/cost-runs/3/confirm`]: ok({
      ...run,
      status: "confirmed",
      confirmedAt: "2026-09-30T02:00:00+00:00",
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(await screen.findByText("25%")).toBeVisible();
  expect(screen.getByText("3,000원")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "확정" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/confirm")).toHaveLength(1),
  );
  expect(await screen.findByText(/옛 확정본은 대체됩니다/)).toBeVisible();
});

it("B-13 초안을 만들면 확정한 비용과 쾌적 비율을 보인다", async () => {
  const review = {
    id: 7,
    reviewMonth: "2026-09",
    version: 1,
    status: "draft",
    totalKwh: "30.00",
    euiKwhPerM2: "0.0150",
    targetAchievement: "0.7500",
    totalCost: "4000.00",
    currency: "KRW",
    comfortRatio: "0.8300",
    issues: "시운전",
    confirmedAt: null,
  };
  const fetcher = mount("/bems/reviews", {
    [`GET ${B}/reviews`]: ok([]),
    [`POST ${B}/reviews`]: ok(review, 201),
    [`GET ${B}/reviews/7`]: ok(review),
  });
  fireEvent.change(await screen.findByLabelText("주요 이슈·조치(선택)"), {
    target: { value: "시운전" },
  });
  fireEvent.click(screen.getByRole("button", { name: "초안 작성" }));
  expect(
    await screen.findByText(/2026-09 보고서 초안을 만들었습니다/),
  ).toBeVisible();
  expect(await screen.findByText("83%")).toBeVisible();
  expect(screen.getByText("4,000원")).toBeVisible();
  expect(
    JSON.parse(
      String((sent(fetcher, "POST", "/reviews")[0][1] as RequestInit).body),
    ),
  ).toEqual({ month: new Date().toISOString().slice(0, 7), issues: "시운전" });
});
