// BEMS-1e 화면: B-09 피크 감축(제안 → 승인·실행 → 복귀).
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

const alarm = (over: Record<string, unknown> = {}) => ({
  ruleCode: "PEAK-1",
  ruleName: "계약전력 대비 피크",
  alarmKind: "PEAK",
  threshold: "0.9",
  unit: "%",
  peakValue: "98.00",
  status: "OPEN",
  raisedAt: "2026-09-24T02:00:00+00:00",
  alarmRef: "PEAK-1@2026-09-24T02:00",
  planId: null,
  overKw: "8.00",
  ...over,
});
const plan = (over: Record<string, unknown> = {}) => ({
  id: 4,
  planNo: "PK-20260924-01",
  femsAlarmRef: "PEAK-1@2026-09-24T02:00",
  proposedAt: "2026-09-24T02:10:00+00:00",
  targetReductionKw: "8.00",
  status: "PROPOSED",
  decidedAt: null,
  executedAt: null,
  restoredAt: null,
  decisionNote: null,
  expectedKw: "9.50",
  steps: [
    {
      id: 1,
      seq: 1,
      hvacUnitId: 2,
      hvacCode: "AHU-PRD",
      hvacName: "생산동 공조기",
      curtailPriority: 1,
      lightingCircuitId: null,
      action: "RAISE_SETPOINT",
      deltaValue: "2.0",
      expectedKw: "5.40",
      commandId: null,
      restoreCommandId: null,
    },
    {
      id: 2,
      seq: 2,
      hvacUnitId: 1,
      hvacCode: "AHU-OFF",
      hvacName: "사무동 공조기",
      curtailPriority: 2,
      lightingCircuitId: null,
      action: "SET_FAN",
      deltaValue: null,
      expectedKw: "4.10",
      commandId: null,
      restoreCommandId: null,
    },
  ],
  alarmOpen: true,
  ...over,
});

it("B-09 FEMS를 끄면 감축안 대신 안내를 보인다", async () => {
  mount("/bems/peak", {
    [`GET ${B}/peak-alarms`]: ok({ femsEnabled: false, rows: [] }),
  });
  expect(
    await screen.findByText(/감축안은 FEMS 경보에서 시작합니다/),
  ).toBeVisible();
  expect(screen.queryByRole("table")).toBeNull();
});

it("B-09 계약전력을 모르면 줄일 양이 '모름'이고 감축안을 만들 수 없다", async () => {
  mount("/bems/peak", {
    [`GET ${B}/peak-alarms`]: ok({
      femsEnabled: true,
      rows: [alarm({ overKw: null })],
    }),
  });
  expect(await screen.findByText("모름")).toBeVisible();
  expect(screen.getByRole("button", { name: "감축안 만들기" })).toBeDisabled();
});

it("B-09 감축안을 만들면 단계와 예상 감축을 보인다", async () => {
  const fetcher = mount("/bems/peak", {
    [`GET ${B}/peak-alarms`]: ok({ femsEnabled: true, rows: [alarm()] }),
    [`GET ${B}/demand-plans`]: ok([]),
    [`POST ${B}/demand-plans`]: ok(plan(), 201),
    [`GET ${B}/demand-plans/4`]: ok(plan()),
  });
  expect(await screen.findByText("98 kW")).toBeVisible();
  expect(screen.getByText("계약전력의 90%")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "감축안 만들기" }));
  expect(
    await screen.findByText(/PK-20260924-01 감축안을 만들었습니다/),
  ).toBeVisible();
  expect(await screen.findByText("냉방 설정 상향 +2℃")).toBeVisible();
  expect(screen.getByText("송풍 전환")).toBeVisible();
  expect(
    JSON.parse(
      String(
        (sent(fetcher, "POST", "/demand-plans")[0][1] as RequestInit).body,
      ),
    ),
  ).toEqual({ alarmRef: "PEAK-1@2026-09-24T02:00" });
});

const executedPlan = (alarmOpen: boolean) =>
  plan({
    status: "EXECUTED",
    executedAt: "2026-09-24T02:20:00+00:00",
    alarmOpen,
  });
const executedReplies = (alarmOpen: boolean): Record<string, Reply> => ({
  [`GET ${B}/peak-alarms`]: ok({
    femsEnabled: true,
    rows: [alarm({ planId: 4 })],
  }),
  [`GET ${B}/demand-plans`]: ok([executedPlan(alarmOpen)]),
  [`GET ${B}/demand-plans/4`]: ok(executedPlan(alarmOpen)),
  [`POST ${B}/demand-plans/4/restore`]: ok(
    plan({ status: "RESTORED", restoredAt: "2026-09-24T03:00:00+00:00" }),
  ),
});

it("B-09 경보가 진행 중이면 복귀를 막는다", async () => {
  mount("/bems/peak", executedReplies(true));
  fireEvent.click(await screen.findByRole("button", { name: "감축안" }));
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(
    await screen.findByRole("button", { name: "복귀 승인" }),
  ).toBeDisabled();
  expect(
    screen.getByText(/피크 경보가 해제되면 복귀할 수 있습니다/),
  ).toBeVisible();
});

it("B-09 경보가 해제되면 복귀를 승인한다", async () => {
  const fetcher = mount("/bems/peak", executedReplies(false));
  fireEvent.click(await screen.findByRole("button", { name: "감축안" }));
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(
    await screen.findByRole("button", { name: "복귀 승인" }),
  ).toBeEnabled();
  expect(screen.getByText(/복귀를 승인하세요/)).toBeVisible();
  // 상세를 다시 읽어 버튼이 바뀔 수 있으므로 누르기 직전에 다시 찾는다.
  fireEvent.click(screen.getByRole("button", { name: "복귀 승인" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/restore")).toHaveLength(1),
  );
  // 안내문(화면 안내)에도 같은 말이 있어 상태 메시지만 가리킨다.
  expect(await screen.findByText(/^복귀했습니다\./)).toBeVisible();
});
