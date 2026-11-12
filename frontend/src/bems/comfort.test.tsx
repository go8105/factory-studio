// BEMS-1d 화면: B-10 쾌적도, B-03 지표 6종, B-06 설비 경보 탭.
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
const body = (call: unknown[]) =>
  JSON.parse(String((call[1] as RequestInit).body));

const comfortRow = (over: Record<string, unknown> = {}) => ({
  zoneId: 1,
  zoneCode: "Z-OFF",
  zoneName: "사무동",
  zoneKind: "OFFICE",
  metric: "TEMP",
  unit: "℃",
  low: "20.00",
  high: "26.00",
  occupiedOnly: true,
  hours: 10,
  insideHours: 8,
  ratio: "80.0",
  reason: null,
  ...over,
});

it("B-10 비율을 못 내는 줄은 0%가 아니라 '모름'과 이유를 보인다", async () => {
  mount("/bems/comfort", {
    [`GET ${B}/comfort`]: ok({
      from: "2026-09-11",
      to: "2026-09-24",
      rows: [
        comfortRow(),
        comfortRow({
          zoneId: 2,
          zoneCode: "Z-PRD",
          zoneName: "생산동",
          zoneKind: "PRODUCTION",
          hours: 0,
          insideHours: 0,
          ratio: null,
          reason: "NO_SCHEDULE",
        }),
      ],
    }),
  });
  expect(await screen.findByText("80.0%")).toBeVisible();
  const badge = screen
    .getAllByText("모름")
    .find((el) => el.className.includes("badge"));
  expect(badge).toBeVisible();
  expect(
    screen
      .getAllByText("운전 스케줄이 없어 근무 시간을 알 수 없습니다")
      .find((el) => el.tagName === "TD"),
  ).toBeVisible();
  expect(
    screen.getAllByText("20 ~ 26 ℃").find((el) => el.tagName === "TD"),
  ).toBeVisible();
});

it("B-10 쾌적 기준은 하한만·상한만도 둘 수 있다", async () => {
  const fetcher = mount("/bems/comfort", {
    [`GET ${B}/comfort`]: ok({
      from: "2026-09-11",
      to: "2026-09-24",
      rows: [],
    }),
    [`GET ${B}/comfort-standards`]: ok([
      {
        id: 3,
        zoneKind: "OFFICE",
        metric: "CO2",
        low: null,
        high: "1000.00",
        occupiedOnly: true,
      },
    ]),
    [`POST ${B}/comfort-standards`]: ok({ id: 4 }, 201),
  });
  fireEvent.click(await screen.findByRole("button", { name: "쾌적 기준" }));
  expect(await screen.findByText("1,000 ppm 이하")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "기준 등록" }));
  fireEvent.change(await screen.findByLabelText("지표"), {
    target: { value: "PM25" },
  });
  fireEvent.change(screen.getByLabelText("상한 (㎍/㎥, 선택)"), {
    target: { value: "35" },
  });
  fireEvent.click(screen.getByLabelText("근무 시간만 센다"));
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/comfort-standards")).toHaveLength(1),
  );
  expect(body(sent(fetcher, "POST", "/comfort-standards")[0])).toEqual({
    zoneKind: "OFFICE",
    metric: "PM25",
    low: null,
    high: "35",
    occupiedOnly: false,
  });
});

it("B-03 센서를 둔 지표만 그래프와 칸을 만든다", async () => {
  const reading = (metric: string, value: string) => ({
    periodStart: "2026-09-23T15:00:00+00:00",
    metric,
    value,
    quality: "valid",
    source: "SIMULATION",
  });
  mount("/bems/environment", {
    [`GET ${B}/zones`]: ok([
      {
        id: 1,
        code: "Z-OFF",
        name: "사무동",
        kind: "OFFICE",
        floorAreaM2: null,
        isActive: true,
        buildingId: null,
        floorLabel: null,
        departmentCode: null,
      },
    ]),
    [`GET ${B}/simulation/clock`]: ok({
      next: "2026-09-24T01:00:00+09:00",
      limit: "2026-09-25T00:00:00+09:00",
      canAdvance: true,
    }),
    [`GET ${B}/environment`]: ok({
      zoneId: 1,
      setpoints: { COOL_TEMP: "26", HEAT_TEMP: "20", CO2_MAX: "1000" },
      readings: [
        reading("TEMP", "22.00"),
        reading("CO2", "500.00"),
        reading("HUMIDITY", "50.00"),
        reading("PM25", "18.00"),
        reading("OCCUPANCY", "0.00"),
      ],
    }),
  });
  expect(await screen.findByRole("figure", { name: "미세먼지" })).toBeVisible();
  expect(screen.getByRole("figure", { name: "재실 인원" })).toBeVisible();
  // 조도 센서가 없으므로 그래프도 만들지 않는다.
  expect(screen.queryByRole("figure", { name: "조도" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "값 표 보기" }));
  expect(await screen.findByText("미세먼지 ㎍/㎥")).toBeVisible();
  expect(screen.queryByText("조도 lx")).toBeNull();
});

it("B-06 설비 경보 탭에서 확인하면 해제는 진행이 한다고 알린다", async () => {
  const alarm = {
    id: 9,
    ruleId: 2,
    hvacUnitId: 1,
    status: "raised",
    raisedAt: "2026-09-24T02:00:00+00:00",
    acknowledgedAt: null,
    clearedAt: null,
    ruleCode: "EQ-LONGRUN",
    condition: "LONG_RUN",
    threshold: "12.00",
    severity: "WARNING",
    hvacCode: "AHU-OFF",
    hvacName: "사무동 공조기",
    zoneId: 1,
  };
  const fetcher = mount("/bems/alarms", {
    [`GET ${B}/alarms`]: ok([]),
    [`GET ${B}/equipment-alarms`]: ok([alarm]),
    [`POST ${B}/equipment-alarms/9/acknowledge`]: ok({
      ...alarm,
      status: "acknowledged",
      acknowledgedAt: "2026-09-24T03:00:00+00:00",
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "설비 경보" }));
  expect(await screen.findByText("연속 운전 12시간 이상")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "확인" }));
  expect(
    await screen.findByText(/해제는 조건이 풀릴 때 1시간 진행이 합니다/),
  ).toBeVisible();
  expect(sent(fetcher, "POST", "/acknowledge")).toHaveLength(1);
});

it("B-06 환경 규칙의 항목은 세 가지뿐이다", async () => {
  mount("/bems/alarms", {
    [`GET ${B}/alarms`]: ok([]),
    [`GET ${B}/alarm-rules`]: ok([]),
    [`GET ${B}/zones`]: ok([]),
  });
  fireEvent.click(await screen.findByRole("button", { name: "환경 규칙" }));
  fireEvent.click(await screen.findByRole("button", { name: "규칙 등록" }));
  const metric = (await screen.findByLabelText("항목")) as HTMLSelectElement;
  expect([...metric.options].map((o) => o.textContent)).toEqual([
    "실내 온도",
    "습도",
    "CO₂",
  ]);
});
