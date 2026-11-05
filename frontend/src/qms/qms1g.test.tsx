// QMS-1g-1 화면: Q-04 검사 값에 쓴 계측기(F27)와 성적서 인쇄(F25).
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const Q = "/api/v1/qms";
type Reply = { status: number; body?: unknown };
const ok = (data: unknown): Reply => ({ status: 200, body: { data } });

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
            data: ["core", "mes", "wms", "qms"].map((m) => ({
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

const pitch = {
  specItemId: 2,
  seq: 2,
  name: "핀 피치",
  method: "RANGE",
  lowerLimit: "2.4800",
  upperLimit: "2.5200",
  unit: "mm",
  isRequired: true,
  measuredValue: null,
  passValue: null,
  judgement: null,
  defectTypeId: null,
  defectCode: null,
  defectName: null,
  gaugeId: null,
  gaugeCode: null,
  gaugeName: null,
};
const inspection = {
  id: 9,
  inspectionNo: "QI-20260924-001",
  source: "MES",
  lotNo: "LOT-001",
  itemCode: "FG-C100",
  itemName: "완제품",
  lotQty: "100.000",
  unit: "EA",
  sampleQty: "3.000",
  specId: 1,
  specVersion: 1,
  reinspectionOfId: null,
  status: "draft",
  result: null,
  inspectedOn: "2026-09-24",
  confirmedAt: null,
  note: null,
  inspectionKind: "OUTGOING",
  partnerCode: null,
  sourceRef: null,
  sampling: "MANUAL",
  acceptNumber: null,
  rejectNumber: null,
  defectCount: null,
  specAql: null,
  values: [pitch],
  activeHold: null,
};
const gauge = {
  id: 7,
  code: "CAL-001",
  name: "버니어 캘리퍼스",
  gaugeKind: "버니어 캘리퍼스",
  measureRange: "0~150 mm",
  resolution: "0.01 mm",
  calibrationCycleDays: 365,
  status: "ACTIVE",
  lastCalibratedOn: "2026-09-01",
  nextDueOn: "2027-09-01",
  lastResult: "PASS",
  dueState: "OK",
  dueInDays: 342,
};

function openDraft(extraGauges: unknown[] = []) {
  return mount("/qms/inspections?open=9", {
    [`GET ${Q}/inspections`]: ok([inspection]),
    [`GET ${Q}/inspections/9`]: ok(inspection),
    [`GET ${Q}/defect-types`]: ok([]),
    [`GET ${Q}/gauges`]: ok([gauge, ...extraGauges]),
    [`PATCH ${Q}/inspections/9`]: ok(inspection),
  });
}

it("측정값과 함께 쓴 계측기를 보낸다", async () => {
  const fetcher = openDraft();
  fireEvent.change(await screen.findByLabelText("핀 피치 측정값"), {
    target: { value: "2.50" },
  });
  fireEvent.change(screen.getByLabelText("핀 피치 계측기"), {
    target: { value: "7" },
  });
  fireEvent.click(screen.getByRole("button", { name: "임시 저장" }));
  await waitFor(() => expect(sent(fetcher, "PATCH", "/9")).toHaveLength(1));
  const body = JSON.parse(String(sent(fetcher, "PATCH", "/9")[0][1]?.body));
  expect(body.values[0]).toMatchObject({
    specItemId: 2,
    measuredValue: "2.50",
    gaugeId: 7,
  });
});

it("계측기를 고르지 않으면 비운 채로 보낸다", async () => {
  const fetcher = openDraft();
  fireEvent.change(await screen.findByLabelText("핀 피치 측정값"), {
    target: { value: "2.50" },
  });
  fireEvent.click(screen.getByRole("button", { name: "임시 저장" }));
  await waitFor(() => expect(sent(fetcher, "PATCH", "/9")).toHaveLength(1));
  const body = JSON.parse(String(sent(fetcher, "PATCH", "/9")[0][1]?.body));
  expect(body.values[0].gaugeId).toBeNull();
});

it("폐기한 계측기는 고를 수 없다", async () => {
  openDraft([{ ...gauge, id: 8, code: "CAL-OLD", status: "RETIRED" }]);
  const picker = await screen.findByLabelText("핀 피치 계측기");
  expect(picker).toHaveTextContent("CAL-001");
  expect(picker).not.toHaveTextContent("CAL-OLD");
});

it("교정이 지난 계측기를 고르면 경고하되 막지 않는다", async () => {
  const stale = {
    ...gauge,
    id: 8,
    code: "CAL-OVER",
    nextDueOn: "2026-01-01",
    dueState: "OVERDUE",
    dueInDays: -266,
  };
  const fetcher = openDraft([stale]);
  fireEvent.change(await screen.findByLabelText("핀 피치 측정값"), {
    target: { value: "2.50" },
  });
  fireEvent.change(screen.getByLabelText("핀 피치 계측기"), {
    target: { value: "8" },
  });
  expect(screen.getByText("교정 기한 경과")).toBeInTheDocument();
  // 경고는 경고일 뿐 — 저장은 그대로 된다.
  fireEvent.click(screen.getByRole("button", { name: "임시 저장" }));
  await waitFor(() => expect(sent(fetcher, "PATCH", "/9")).toHaveLength(1));
});

it("수리 중 계측기도 쓸 수 있고 그렇게 알린다", async () => {
  openDraft([{ ...gauge, id: 8, code: "CAL-FIX", status: "REPAIR" }]);
  fireEvent.change(await screen.findByLabelText("핀 피치 계측기"), {
    target: { value: "8" },
  });
  expect(screen.getByText("수리 중")).toBeInTheDocument();
});

it("확정 검사는 성적서로 인쇄하고 쓴 계측기를 싣는다", async () => {
  const print = vi.fn();
  Object.defineProperty(window, "print", { value: print, writable: true });
  const confirmed = {
    ...inspection,
    status: "confirmed",
    result: "PASS",
    confirmedAt: "2026-09-24T06:00:00+00:00",
    values: [
      {
        ...pitch,
        measuredValue: "2.5000",
        judgement: "PASS",
        gaugeId: 7,
        gaugeCode: "CAL-001",
        gaugeName: "버니어 캘리퍼스",
      },
    ],
  };
  mount("/qms/inspections?open=9", {
    [`GET ${Q}/inspections`]: ok([confirmed]),
    [`GET ${Q}/inspections/9`]: ok(confirmed),
    [`GET ${Q}/defect-types`]: ok([]),
    [`GET ${Q}/gauges`]: ok([gauge]),
  });
  expect(await screen.findByText("검사 성적서 (COA)")).toBeInTheDocument();
  expect(screen.getByText("CAL-001 버니어 캘리퍼스")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "성적서 인쇄" }));
  expect(print).toHaveBeenCalled();
});
