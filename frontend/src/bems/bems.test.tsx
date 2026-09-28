// FS-025b BEMS 화면 (화면 설계 5장 단위 검증). 검증 항목별로 테스트를 나눈다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import { nextBoundary } from "./common";

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
      if (url.endsWith("/workspace/modules"))
        return new Response(
          JSON.stringify({
            data: ["core", "fems", "bems"].map((m) => ({
              moduleKey: m,
              enabled: true,
              updatedAt: null,
            })),
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
const body = (call: unknown[]) =>
  JSON.parse(String((call[1] as RequestInit).body));

const row = (period: string, residual: string, mismatch = false) => ({
  period,
  site: "4800",
  manufacturing: "4200",
  common: "500",
  commonByUsage: { HVAC: "260", LIGHTING: "130", OFFICE: "110" },
  residual,
  mismatch,
  missingHours: 0,
});
const clock = {
  next: "2026-09-24T09:00:00+09:00",
  limit: "2026-09-25T00:00:00+09:00",
  canAdvance: true,
};
const unit = {
  id: 1,
  zoneId: 1,
  code: "AHU-OFF",
  name: "사무동 공조기",
  meterId: 1,
  ratedKw: "12.00",
  state: "COOL",
  controlSource: "SCHEDULE",
  stateChangedAt: null,
  isActive: true,
  setpoints: { COOL_TEMP: "26", HEAT_TEMP: "20", CO2_MAX: "1000" },
};
const zone = {
  id: 1,
  code: "Z-OFF",
  name: "사무동",
  kind: "OFFICE",
  floorAreaM2: null,
  isActive: true,
};

it("B-02 잔여가 음수인 날은 불일치 배지와 FEMS F-03 안내를 보인다", async () => {
  mount("/bems/breakdown", {
    [`GET ${B}/breakdown`]: ok({
      granularity: "day",
      from: "2026-09-18",
      to: "2026-09-19",
      rows: [row("2026-09-18", "100"), row("2026-09-19", "-438", true)],
    }),
  });
  expect(await screen.findByText("불일치")).toBeVisible();
  expect(screen.getByText(/불일치 1건/)).toBeVisible();
  expect(
    screen.getByRole("link", { name: /FEMS F-03 설비별 배분/ }),
  ).toHaveAttribute("href", "/fems/allocations");
  expect(screen.getByText(/FEMS에서 읽어 옵니다/)).toHaveAttribute(
    "role",
    "note",
  );
});

it("B-02 FEMS를 끄면 분해 대신 안내를 보인다", async () => {
  mount("/bems/breakdown", {
    [`GET ${B}/breakdown`]: {
      status: 409,
      body: {
        error: {
          code: "CONFLICT",
          message: "FEMS를 사용하지 않도록 설정했습니다.",
          details: { reason: "SOURCE_MODULE_DISABLED", sourceModule: "fems" },
        },
      },
    },
  });
  expect(
    await screen.findByText(/공용 계측\(B-03\)과 공조 운전은 그대로/),
  ).toBeVisible();
  expect(screen.queryByRole("table")).toBeNull();
});

it("B-04 거부된 명령은 사유를 알리고, 적용된 수동 명령은 스케줄 복귀 시각을 알린다", async () => {
  const detail = {
    ...unit,
    commands: [],
    schedule: [
      { id: 1, dayKind: "WEEKDAY", startHour: 8, endHour: 19, mode: "COOL" },
    ],
  };
  const command = (result: string, rejectReason: string | null) =>
    ok(
      {
        id: 9,
        zoneId: 1,
        hvacUnitId: 1,
        hvacCode: "AHU-OFF",
        command: "SET_MODE",
        mode: "FAN",
        setpointKind: null,
        value: null,
        source: "MANUAL",
        requestedAt: clock.next,
        result,
        rejectReason,
        note: null,
      },
      201,
    );
  const replies: Record<string, Reply> = {
    [`GET ${B}/hvac-overview`]: ok([
      { ...unit, environment: {}, lastPower: null },
    ]),
    [`GET ${B}/zones`]: ok([zone]),
    [`GET ${B}/simulation/clock`]: ok(clock),
    [`GET ${B}/hvac-units/1/detail`]: ok(detail),
    [`POST ${B}/commands`]: command("REJECTED", "SAME_STATE"),
  };
  const fetcher = mount("/bems/hvac", replies);
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  fireEvent.change(await screen.findByLabelText("모드"), {
    target: { value: "FAN" },
  });
  fireEvent.click(screen.getByRole("button", { name: "모드 적용" }));
  await waitFor(() =>
    expect(
      screen.getByText(/거부됨: 모드 변경 · 송풍 — 이미 같은 모드/),
    ).toBeVisible(),
  );
  expect(body(sent(fetcher, "POST", "/commands")[0])).toMatchObject({
    zoneId: 1,
    hvacUnitId: 1,
    command: "SET_MODE",
    mode: "FAN",
  });
  replies[`POST ${B}/commands`] = command("APPLIED", null);
  fireEvent.click(screen.getByRole("button", { name: "모드 적용" }));
  // 09:00부터 평일 08~19 냉방 → 다음 경계는 19:00
  expect(
    await screen.findByText(
      /다음 스케줄 경계\(09\. 24\. 19:00\)까지 수동 운전/,
    ),
  ).toBeVisible();
});

it("B-05 겹치는 시간대는 그 행에 오류를 보인다", async () => {
  const fetcher = mount("/bems/schedules", {
    [`GET ${B}/hvac-units`]: ok([unit]),
    [`GET ${B}/hvac-units/1/detail`]: ok({
      ...unit,
      commands: [],
      schedule: [],
    }),
    [`PUT ${B}/hvac-units/1/schedule`]: {
      status: 400,
      body: {
        error: {
          code: "VALIDATION_FAILED",
          message: "입력을 확인하세요.",
          details: { fields: { "slots.1": "1번째 시간대와 겹칩니다." } },
        },
      },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "편집" }));
  fireEvent.click(screen.getByRole("button", { name: "시간대 추가" }));
  fireEvent.click(screen.getByRole("button", { name: "시간대 추가" }));
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  expect(await screen.findByText("1번째 시간대와 겹칩니다.")).toBeVisible();
  expect(body(sent(fetcher, "PUT", "/schedule")[0]).slots).toHaveLength(2);
});

it("B-06 확인 대기 경보를 메모와 함께 확인한다", async () => {
  const alarm = {
    id: 3,
    alarmRuleId: 1,
    sensorId: 1,
    status: "raised",
    raisedAt: "2026-09-24T02:00:00+00:00",
    peakValue: "1180",
    acknowledgedAt: null,
    ackNote: null,
    clearedAt: null,
    zoneId: 1,
    zoneCode: "Z-OFF",
    zoneName: "사무동",
    metric: "CO2",
    comparator: "HIGH",
    threshold: "1000",
    durationHours: 2,
    severity: "WARNING",
  };
  const fetcher = mount("/bems/alarms", {
    [`GET ${B}/alarms`]: ok([alarm]),
    [`GET ${B}/environment`]: ok({ zoneId: 1, readings: [], setpoints: {} }),
    [`POST ${B}/alarms/3/acknowledge`]: ok({
      ...alarm,
      status: "acknowledged",
      acknowledgedAt: "2026-09-24T03:00:00+00:00",
      ackNote: "환기 지시",
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세 · 확인" }));
  fireEvent.change(screen.getByLabelText("확인 메모(선택)"), {
    target: { value: "환기 지시" },
  });
  fireEvent.click(screen.getByRole("button", { name: "확인" }));
  expect(await screen.findByText(/환기 지시\)/)).toBeVisible();
  expect(body(sent(fetcher, "POST", "/acknowledge")[0])).toEqual({
    note: "환기 지시",
  });
  expect(screen.queryByRole("button", { name: "확인" })).toBeNull();
});

it("스케줄 경계는 모드가 바뀌는 첫 시각이다(서버와 같은 KST 규칙)", () => {
  const weekday = [
    {
      dayKind: "WEEKDAY" as const,
      startHour: 1,
      endHour: 3,
      mode: "COOL" as const,
    },
  ];
  // 2026-09-24 목요일 00:00 KST → 01:00 시작, 03:00 끝
  expect(nextBoundary(weekday, "2026-09-24T00:00:00+09:00")).toBe(
    "2026-09-23T16:00:00.000Z",
  );
  expect(nextBoundary(weekday, "2026-09-24T02:00:00+09:00")).toBe(
    "2026-09-23T18:00:00.000Z",
  );
  expect(nextBoundary([], "2026-09-24T00:00:00+09:00")).toBeNull();
});

it("B-03 구역 탭과 온도·CO₂ 그래프에 설정값 점선을 그린다", async () => {
  const reading = (metric: string, value: string) => ({
    periodStart: "2026-09-23T15:00:00+00:00",
    metric,
    value,
    quality: "valid",
    source: "SIMULATION",
  });
  mount("/bems/environment", {
    [`GET ${B}/zones`]: ok([zone]),
    [`GET ${B}/simulation/clock`]: ok({
      ...clock,
      next: "2026-09-24T01:00:00+09:00",
    }),
    [`GET ${B}/environment`]: ok({
      zoneId: 1,
      setpoints: unit.setpoints,
      readings: [reading("TEMP", "19.00"), reading("CO2", "420.00")],
    }),
  });
  expect(
    await screen.findByRole("figure", { name: "실내 온도" }),
  ).toHaveTextContent("냉방 설정 26");
  expect(screen.getByRole("figure", { name: "CO₂" })).toHaveTextContent(
    "CO₂ 상한",
  );
  expect(screen.getByRole("button", { name: "사무동" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
