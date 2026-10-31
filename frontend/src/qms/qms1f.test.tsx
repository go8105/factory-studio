// QMS-1f 화면: Q-02 검사 종류·AQL, Q-03 수입 탭, Q-04 AQL 시료·불량 개수.
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

const incomingLot = {
  sourceRef: "IN-20260924-003:1",
  noticeNo: "IN-20260924-003",
  noticeKind: "PURCHASE",
  partnerCode: "V-001",
  inspectedAt: "2026-09-23T02:00:00+00:00",
  lotNo: null,
  itemCode: "RM-PBT",
  itemName: "PBT 수지",
  qty: "3.000",
  unit: "KG",
  level: "NORMAL",
  hasSpec: true,
};

it("수입 탭은 WMS 격리 줄과 검사 수준을 보여 준다", async () => {
  mount("/qms/pending", {
    [`GET ${Q}/lookups/mes-lots`]: ok([]),
    [`GET ${Q}/lookups/incoming-lots`]: ok({
      wmsEnabled: true,
      rows: [incomingLot],
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "수입" }));
  expect(await screen.findByText("IN-20260924-003:1")).toBeInTheDocument();
  expect(screen.getByText("V-001")).toBeInTheDocument();
  expect(screen.getByText("보통")).toBeInTheDocument();
});

it("수입 기준이 없으면 검사 시작 대신 기준 만들기를 낸다", async () => {
  mount("/qms/pending", {
    [`GET ${Q}/lookups/mes-lots`]: ok([]),
    [`GET ${Q}/lookups/incoming-lots`]: ok({
      wmsEnabled: true,
      rows: [{ ...incomingLot, hasSpec: false }],
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "수입" }));
  expect(
    await screen.findByRole("link", { name: /수입 기준 없음/ }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "검사 시작" })).toBeNull();
});

it("WMS를 끄면 수입 대상을 읽을 수 없다고 알린다", async () => {
  mount("/qms/pending", {
    [`GET ${Q}/lookups/mes-lots`]: ok([]),
    [`GET ${Q}/lookups/incoming-lots`]: ok({ wmsEnabled: false, rows: [] }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "수입" }));
  expect(
    await screen.findByText(/WMS를 사용하지 않도록 설정했습니다/),
  ).toBeInTheDocument();
});

it("수입 검사 시작은 입고 원천만 보낸다 — 시료 수는 표가 정한다", async () => {
  const fetcher = mount("/qms/pending", {
    [`GET ${Q}/lookups/mes-lots`]: ok([]),
    [`GET ${Q}/lookups/incoming-lots`]: ok({
      wmsEnabled: true,
      rows: [incomingLot],
    }),
    [`POST ${Q}/inspections/incoming`]: {
      status: 201,
      body: { data: { id: 9 } },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "수입" }));
  fireEvent.click(await screen.findByRole("button", { name: "검사 시작" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/inspections/incoming")).toHaveLength(1),
  );
  expect(
    JSON.parse(
      String(sent(fetcher, "POST", "/inspections/incoming")[0][1]?.body),
    ),
  ).toEqual({ sourceRef: "IN-20260924-003:1" });
});

const values = [
  {
    specItemId: 1,
    seq: 1,
    name: "외관",
    method: "PASS_FAIL",
    lowerLimit: null,
    upperLimit: null,
    unit: null,
    isRequired: true,
    measuredValue: null,
    passValue: true,
    judgement: "PASS",
    defectTypeId: null,
    defectCode: null,
    defectName: null,
  },
];
const aqlInspection = {
  id: 9,
  inspectionNo: "QI-20260924-001",
  source: "WMS",
  lotNo: "IN-20260924-003:1",
  itemCode: "RM-PBT",
  itemName: "PBT 수지",
  lotQty: "3.000",
  unit: "KG",
  sampleQty: "3.000",
  specId: 1,
  specVersion: 1,
  reinspectionOfId: null,
  status: "draft",
  result: null,
  inspectedOn: "2026-09-24",
  confirmedAt: null,
  note: null,
  inspectionKind: "INCOMING",
  partnerCode: "V-001",
  sourceRef: "IN-20260924-003:1",
  sampling: "AQL",
  acceptNumber: 0,
  rejectNumber: 1,
  defectCount: null,
  specAql: "2.5",
  values,
  activeHold: null,
};

it("AQL 검사는 시료 수를 고치게 하지 않고 합격 판정 개수를 알린다", async () => {
  mount("/qms/inspections?open=9", {
    [`GET ${Q}/inspections`]: ok([aqlInspection]),
    [`GET ${Q}/inspections/9`]: ok(aqlInspection),
    [`GET ${Q}/defect-types`]: ok([]),
  });
  expect(
    await screen.findByText(/AQL 2.5 · 시료 3 KG · 합격 판정 개수 0/),
  ).toBeInTheDocument();
  expect(screen.queryByLabelText(/표본 수량/)).toBeNull();
  expect(screen.getByLabelText("시료 불량 개수")).toBeInTheDocument();
});

it("시료 불량 개수는 따로 저장한다", async () => {
  const fetcher = mount("/qms/inspections?open=9", {
    [`GET ${Q}/inspections`]: ok([aqlInspection]),
    [`GET ${Q}/inspections/9`]: ok(aqlInspection),
    [`GET ${Q}/defect-types`]: ok([]),
    [`PATCH ${Q}/inspections/9/defect-count`]: ok({
      ...aqlInspection,
      defectCount: 2,
    }),
  });
  fireEvent.change(await screen.findByLabelText("시료 불량 개수"), {
    target: { value: "2" },
  });
  fireEvent.click(screen.getByRole("button", { name: "불량 개수 저장" }));
  await waitFor(() =>
    expect(sent(fetcher, "PATCH", "/defect-count")).toHaveLength(1),
  );
  expect(
    JSON.parse(String(sent(fetcher, "PATCH", "/defect-count")[0][1]?.body)),
  ).toEqual({ defectCount: 2 });
});

it("직접 입력 검사는 표본 수량을 그대로 고칠 수 있다", async () => {
  mount("/qms/inspections?open=9", {
    [`GET ${Q}/inspections`]: ok([
      { ...aqlInspection, sampling: "MANUAL", specAql: null },
    ]),
    [`GET ${Q}/inspections/9`]: ok({
      ...aqlInspection,
      sampling: "MANUAL",
      acceptNumber: null,
      rejectNumber: null,
      specAql: null,
    }),
    [`GET ${Q}/defect-types`]: ok([]),
  });
  expect(await screen.findByLabelText(/표본 수량/)).toBeInTheDocument();
  expect(screen.queryByLabelText("시료 불량 개수")).toBeNull();
});

it("검사 기준 등록은 종류와 AQL을 함께 보낸다", async () => {
  const fetcher = mount("/qms/specs", {
    [`GET ${Q}/inspection-specs`]: ok([]),
    [`GET ${Q}/lookups/mes-items`]: ok([
      { itemCode: "RM-PBT", name: "PBT 수지", baseUnit: "KG" },
    ]),
    [`POST ${Q}/inspection-specs`]: {
      status: 201,
      body: {
        data: {
          id: 3,
          itemCode: "RM-PBT",
          itemName: "PBT 수지",
          versionNo: 1,
          status: "draft",
          publishedAt: null,
          note: null,
          inspectionKind: "INCOMING",
          aql: "2.5",
          itemCount: 0,
          inspectionCount: 0,
          items: [],
        },
      },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "기준 만들기" }));
  fireEvent.change(await screen.findByLabelText(/품목/), {
    target: { value: "RM-PBT" },
  });
  fireEvent.change(screen.getByLabelText("검사 종류"), {
    target: { value: "INCOMING" },
  });
  fireEvent.change(screen.getByLabelText("AQL (선택)"), {
    target: { value: "2.5" },
  });
  fireEvent.click(screen.getByRole("button", { name: "만들기" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/inspection-specs")).toHaveLength(1),
  );
  expect(
    JSON.parse(String(sent(fetcher, "POST", "/inspection-specs")[0][1]?.body)),
  ).toMatchObject({ inspectionKind: "INCOMING", aql: "2.5" });
});

it("출하 탭의 MES 오류가 수입 탭으로 새지 않는다", async () => {
  mount("/qms/pending", {
    [`GET ${Q}/lookups/mes-lots`]: {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "MES를 사용하지 않도록 설정했습니다.",
          details: { reason: "SOURCE_MODULE_DISABLED", sourceModule: "mes" },
        },
      },
    },
    [`GET ${Q}/lookups/incoming-lots`]: ok({
      wmsEnabled: true,
      rows: [incomingLot],
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "수입" }));
  expect(await screen.findByText("IN-20260924-003:1")).toBeInTheDocument();
  expect(screen.queryByText(/MES를 사용하지 않도록 설정했습니다/)).toBeNull();
});
