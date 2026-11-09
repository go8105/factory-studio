// BEMS-1c 화면: B-08 조명 제어, B-05 휴일·조명 스케줄, B-07 건물·층·부서, P-08 휴일 달력.
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const B = "/api/v1/bems";
const CORE = "/api/v1/core";
type Reply = { status: number; body?: unknown };
const ok = (data: unknown, status = 200): Reply => ({ status, body: { data } });

function mount(
  path: string,
  replies: Record<string, Reply> = {},
  roles = ["GUEST"],
) {
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
              actorKind: roles.includes("GUEST") ? "GUEST" : "MEMBER",
              workspaceId: 1,
              generationId: 2,
              roles,
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

const zone = {
  id: 1,
  code: "Z-OFF",
  name: "사무동",
  kind: "OFFICE",
  floorAreaM2: "1200.00",
  isActive: true,
  buildingId: null,
  floorLabel: null,
  departmentCode: null,
};
const building = {
  id: 7,
  code: "BLD-OFF",
  name: "사무동",
  floors: 3,
  grossAreaM2: "1800.00",
  isActive: true,
};
const circuit = {
  id: 5,
  zoneId: 1,
  code: "L-OFF",
  name: "사무동 조명",
  meterId: null,
  ratedKw: "6.00",
  state: "OFF" as const,
  controlSource: "SCHEDULE" as const,
  stateChangedAt: null,
  isActive: true,
};
const clock = {
  next: "2026-09-24T09:00:00+09:00",
  limit: "2026-09-25T00:00:00+09:00",
  canAdvance: true,
};

it("B-08 조명 회로를 켜면 명령을 보내고 스케줄 복귀 시각을 알린다", async () => {
  const fetcher = mount("/bems/lighting", {
    [`GET ${B}/lighting-circuits`]: ok([circuit]),
    [`GET ${B}/zones`]: ok([zone]),
    [`GET ${B}/simulation/clock`]: ok(clock),
    [`GET ${B}/lighting-circuits/5/detail`]: ok({
      ...circuit,
      commands: [],
      schedule: [
        { id: 1, dayKind: "WEEKDAY", startHour: 7, endHour: 20, mode: "ON" },
      ],
    }),
    [`POST ${B}/commands`]: ok(
      {
        id: 11,
        zoneId: 1,
        hvacUnitId: null,
        hvacCode: null,
        lightingCircuitId: 5,
        lightingCode: "L-OFF",
        command: "POWER_ON",
        mode: null,
        setpointKind: null,
        value: null,
        source: "MANUAL",
        requestedAt: clock.next,
        result: "APPLIED",
        rejectReason: null,
        note: null,
      },
      201,
    ),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  fireEvent.click(await screen.findByRole("button", { name: "켜기" }));
  // 09:00부터 평일 07~20 켜짐 → 다음 경계는 20:00
  expect(
    await screen.findByText(
      /다음 스케줄 경계\(09\. 24\. 20:00\)까지 수동 운전/,
    ),
  ).toBeVisible();
  expect(body(sent(fetcher, "POST", "/commands")[0])).toEqual({
    zoneId: 1,
    lightingCircuitId: 5,
    command: "POWER_ON",
  });
});

it("B-05 공조기와 조명 회로를 한 표에 두고 조명은 켜짐만 고른다", async () => {
  const unit = {
    id: 1,
    zoneId: 1,
    code: "AHU-OFF",
    name: "사무동 공조기",
    meterId: null,
    ratedKw: "12.00",
    state: "OFF",
    controlSource: "SCHEDULE",
    stateChangedAt: null,
    isActive: true,
  };
  const fetcher = mount("/bems/schedules", {
    [`GET ${B}/hvac-units`]: ok([unit]),
    [`GET ${B}/lighting-circuits`]: ok([circuit]),
    [`GET ${B}/hvac-units/1/detail`]: ok({
      ...unit,
      commands: [],
      schedule: [
        { id: 2, dayKind: "HOLIDAY", startHour: 11, endHour: 15, mode: "FAN" },
      ],
    }),
    [`GET ${B}/lighting-circuits/5/detail`]: ok({
      ...circuit,
      commands: [],
      schedule: [],
    }),
    [`PUT ${B}/lighting-circuits/5/schedule`]: ok([]),
  });
  // 공조기 행은 휴일 칸에 요약을, 조명 행은 '—'를 보인다.
  expect(await screen.findByText("11–15 송풍")).toBeVisible();
  const rows = screen.getAllByRole("row");
  const lightRow = rows.find((r) => r.textContent?.includes("L-OFF"))!;
  expect(lightRow).toHaveTextContent("조명");
  fireEvent.click(within(lightRow).getByRole("button", { name: "편집" }));
  fireEvent.click(screen.getByRole("button", { name: "시간대 추가" }));
  const mode = screen.getByLabelText("1번째 모드") as HTMLSelectElement;
  expect(mode.disabled).toBe(true);
  expect([...mode.options].map((o) => o.textContent)).toEqual(["켜짐"]);
  expect(
    [...(screen.getByLabelText("1번째 요일") as HTMLSelectElement).options].map(
      (o) => o.textContent,
    ),
  ).toEqual(["평일", "주말", "휴일"]);
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() =>
    expect(sent(fetcher, "PUT", "/lighting-circuits/5/schedule")).toHaveLength(
      1,
    ),
  );
  expect(
    body(sent(fetcher, "PUT", "/lighting-circuits/5/schedule")[0]).slots[0],
  ).toMatchObject({ dayKind: "WEEKDAY", mode: "ON" });
});

it("B-07 건물을 고르면 층을 입력할 수 있고, 건물을 비우면 층도 비운다", async () => {
  const fetcher = mount("/bems/zones", {
    [`GET ${B}/zones`]: ok([{ ...zone, buildingId: 7, floorLabel: "2F" }]),
    [`GET ${B}/buildings`]: ok([building]),
    [`GET ${B}/lookups/departments`]: ok({
      hrEnabled: true,
      rows: [{ code: "ADM", name: "경영지원팀" }],
    }),
    [`PATCH ${B}/zones/1`]: ok(zone),
  });
  const zoneRow = (await screen.findByText("사무동 2F")).closest("tr")!;
  fireEvent.click(within(zoneRow).getByRole("button", { name: "수정" }));
  const floor = (await screen.findByLabelText(
    "층 표기(선택)",
  )) as HTMLInputElement;
  expect(floor.value).toBe("2F");
  expect(floor.disabled).toBe(false);
  fireEvent.change(screen.getByLabelText("사용 부서(선택)"), {
    target: { value: "ADM" },
  });
  fireEvent.change(screen.getByLabelText("건물(선택)"), {
    target: { value: "" },
  });
  expect(
    (screen.getByLabelText("층 표기(선택)") as HTMLInputElement).disabled,
  ).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() =>
    expect(sent(fetcher, "PATCH", "/zones/1")).toHaveLength(1),
  );
  expect(body(sent(fetcher, "PATCH", "/zones/1")[0])).toMatchObject({
    buildingId: null,
    floorLabel: null,
    departmentCode: "ADM",
  });
});

it("B-07 HR을 껐으면 부서를 직접 입력한다", async () => {
  mount("/bems/zones", {
    [`GET ${B}/zones`]: ok([zone]),
    [`GET ${B}/buildings`]: ok([]),
    [`GET ${B}/lookups/departments`]: ok({ hrEnabled: false, rows: [] }),
  });
  const row = (await screen.findByText("Z-OFF")).closest("tr")!;
  fireEvent.click(within(row).getByRole("button", { name: "수정" }));
  expect(await screen.findByLabelText("사용 부서(선택)")).toHaveProperty(
    "tagName",
    "INPUT",
  );
  expect(screen.getByText(/HR을 켜면 부서 목록에서/)).toBeVisible();
});

it("P-08 회사 공간의 일반 회원은 휴일을 고치지 못한다", async () => {
  mount(
    "/holidays",
    {
      [`GET ${CORE}/holidays`]: ok([
        { id: 1, date: "2026-10-03", name: "개천절", kind: "PUBLIC" },
      ]),
    },
    ["MEMBER"],
  );
  expect(await screen.findByText("개천절")).toBeVisible();
  expect(screen.getByText("2026-10-03 (토)")).toBeVisible();
  expect(screen.getByRole("button", { name: "휴일 등록" })).toBeDisabled();
  expect(screen.getByText(/관리자만 고칠 수 있습니다/)).toBeInTheDocument();
});

it("P-08 연도를 바꾸면 그 해 휴일을 다시 부르고, 회사 휴무를 등록한다", async () => {
  const fetcher = mount("/holidays", {
    [`GET ${CORE}/holidays`]: ok([]),
    [`POST ${CORE}/holidays`]: ok(
      { id: 2, date: "2026-12-24", name: "창립기념일", kind: "COMPANY" },
      201,
    ),
  });
  await screen.findByRole("button", { name: "휴일 등록" });
  const year = new Date().getFullYear();
  fireEvent.change(screen.getByLabelText("조회 연도"), {
    target: { value: String(year + 1) },
  });
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(([url]) =>
        String(url).includes(`year=${year + 1}`),
      ),
    ).toBe(true),
  );
  fireEvent.click(screen.getByRole("button", { name: "휴일 등록" }));
  fireEvent.change(await screen.findByLabelText("날짜 (YYYY-MM-DD)"), {
    target: { value: "2026-12-24" },
  });
  fireEvent.change(screen.getByLabelText("이름"), {
    target: { value: "창립기념일" },
  });
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/holidays")).toHaveLength(1),
  );
  expect(body(sent(fetcher, "POST", "/holidays")[0])).toEqual({
    date: "2026-12-24",
    name: "창립기념일",
    kind: "COMPANY",
  });
});
