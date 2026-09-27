// FS-023b QMS 화면. 검증 항목별로 테스트를 나눈다.
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
            data: ["core", "mes", "erp", "fems", "qms"].map((m) => ({
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

const lot = {
  lotNo: "LT-0016",
  itemCode: "FG-C100",
  itemName: "커넥터 C100",
  finalGoodQty: "1940.000",
  unit: "EA",
  completedAt: "2026-09-24T07:10:00+00:00",
  status: "pending",
  draftInspectionId: null,
  latestResult: null,
  hasSpec: true,
};
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
    passValue: null,
    judgement: null,
    defectTypeId: null,
    defectCode: null,
    defectName: null,
  },
  {
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
  },
];
const inspection = (over: object = {}) => ({
  id: 9,
  inspectionNo: "QI-20260924-001",
  source: "MES",
  lotNo: "LT-0016",
  itemCode: "FG-C100",
  itemName: "커넥터 C100",
  lotQty: "1940.000",
  unit: "EA",
  sampleQty: "32.000",
  specId: 3,
  specVersion: 1,
  reinspectionOfId: null,
  status: "draft",
  result: null,
  inspectedOn: "2026-09-24",
  confirmedAt: null,
  note: null,
  values,
  activeHold: null,
  ...over,
});

it("런처에 QMS가 있고 설명 카드는 WMS·BEMS·SCM 3종이다", async () => {
  mount("/home");
  expect(
    await screen.findByRole("link", { name: /QMS 품질관리/ }),
  ).toHaveAttribute("href", "/qms");
  expect(
    screen.queryByRole("link", { name: /^QMS 품질$/ }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /WMS 물류/ })).toBeVisible();
});

it("검사 대기는 MES LOT을 읽어 오고 검사 시작은 MES 출처로 만든다", async () => {
  const fetcher = mount("/qms/pending", {
    [`GET ${Q}/lookups/mes-lots`]: ok([lot]),
    [`POST ${Q}/inspections`]: { status: 201, body: { data: inspection() } },
    [`GET ${Q}/inspections/9`]: ok(inspection()),
  });
  const table = await screen.findByRole("table", { name: "검사 대기 LOT" });
  expect(within(table).getByText("FG-C100 커넥터 C100")).toBeVisible();
  fireEvent.click(within(table).getByRole("button", { name: "검사 시작" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/inspections")).toHaveLength(1),
  );
  expect(
    JSON.parse(String(sent(fetcher, "POST", "/inspections")[0][1]?.body)),
  ).toEqual({ source: "MES", lotNo: "LT-0016", sampleQty: "32" });
  expect(
    await screen.findByRole("dialog", { name: /QI-20260924-001/ }),
  ).toBeVisible();
});

it("MES를 끄면 검사 대기는 직접 입력으로 안내한다", async () => {
  mount("/qms/pending", {
    [`GET ${Q}/lookups/mes-lots`]: {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message: "x",
          details: { reason: "SOURCE_MODULE_DISABLED" },
        },
      },
    },
  });
  fireEvent.click(
    await screen.findByRole("button", { name: /직접 입력으로 검사/ }),
  );
  expect(
    await screen.findByRole("dialog", { name: "직접 입력 검사" }),
  ).toBeVisible();
});

it("검사 입력은 기준 대비 판정을 미리 보이고 불합격이면 불량 유형을 묻는다", async () => {
  mount("/qms/inspections?open=9", {
    [`GET ${Q}/inspections`]: ok([inspection()]),
    [`GET ${Q}/inspections/9`]: ok(inspection()),
    [`GET ${Q}/defect-types`]: ok([
      {
        id: 4,
        code: "DIMENSION",
        name: "치수 불량",
        isActive: true,
        usedCount: 0,
      },
    ]),
  });
  const dialog = await screen.findByRole("dialog", { name: /QI-20260924-001/ });
  fireEvent.change(within(dialog).getByLabelText("핀 피치 측정값"), {
    target: { value: "2.60" },
  });
  const row = within(dialog).getByLabelText("핀 피치 측정값").closest("tr")!;
  expect(within(row).getByText("불합격")).toBeVisible();
  expect(within(row).getByLabelText("핀 피치 불량 유형")).toBeVisible();
  fireEvent.change(within(dialog).getByLabelText("핀 피치 측정값"), {
    target: { value: "2.52" },
  });
  expect(within(row).getByText("합격")).toBeVisible();
});

it("확정은 저장 뒤 확정을 부르고 불합격이면 보류를 알린다", async () => {
  const failed = inspection({
    status: "confirmed",
    result: "FAIL",
    activeHold: { id: 5, holdNo: "QH-20260924-001" },
  });
  const fetcher = mount("/qms/inspections?open=9", {
    [`GET ${Q}/inspections`]: ok([inspection()]),
    [`GET ${Q}/inspections/9`]: ok(inspection()),
    [`PATCH ${Q}/inspections/9`]: ok(inspection()),
    [`POST ${Q}/inspections/9/confirm`]: ok(failed),
  });
  const dialog = await screen.findByRole("dialog", { name: /QI-20260924-001/ });
  fireEvent.click(within(dialog).getByRole("button", { name: "확정" }));
  expect(await screen.findByRole("status")).toHaveTextContent(
    "QH-20260924-001",
  );
  const patch = JSON.parse(
    String(sent(fetcher, "PATCH", "/inspections/9")[0][1]?.body),
  );
  expect(patch.values).toHaveLength(2);
  expect(sent(fetcher, "POST", "/inspections/9/confirm")).toHaveLength(1);
});

it("확정한 검사는 읽기 전용으로 열고 재검사만 제공한다", async () => {
  mount("/qms/inspections?open=9", {
    [`GET ${Q}/inspections`]: ok([]),
    [`GET ${Q}/inspections/9`]: ok(
      inspection({ status: "confirmed", result: "PASS" }),
    ),
  });
  const dialog = await screen.findByRole("dialog", { name: /QI-20260924-001/ });
  expect(within(dialog).getByRole("button", { name: "재검사" })).toBeVisible();
  expect(
    within(dialog).queryByLabelText("핀 피치 측정값"),
  ).not.toBeInTheDocument();
});

it("합격 재검사가 없으면 보류 해제는 특채로 시작하고 사유를 보낸다", async () => {
  const hold = {
    id: 5,
    holdNo: "QH-20260924-001",
    lotNo: "LT-0016",
    itemCode: "FG-C100",
    inspectionId: 9,
    inspectionNo: "QI-20260924-001",
    status: "held",
    heldAt: "2026-09-24T08:00:00+00:00",
    disposition: null,
    releaseInspectionId: null,
    releaseInspectionNo: null,
    releaseReason: null,
    releasedAt: null,
  };
  const fetcher = mount("/qms/holds", {
    [`GET ${Q}/holds`]: ok([hold]),
    [`GET ${Q}/holds/5`]: ok({ ...hold, reinspections: [], failedItems: [] }),
    [`POST ${Q}/holds/5/release`]: ok({
      ...hold,
      status: "released",
      disposition: "CONCESSION",
      reinspections: [],
      failedItems: [],
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  fireEvent.click(await screen.findByRole("button", { name: "해제 처분" }));
  const dialog = await screen.findByRole("dialog", {
    name: "LT-0016 보류 해제",
  });
  expect(within(dialog).getByLabelText("재검사 합격")).toBeDisabled();
  expect(within(dialog).getByLabelText("특채")).toBeChecked();
  fireEvent.change(within(dialog).getByLabelText("사유"), {
    target: { value: "고객 승인" },
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "해제" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/holds/5/release")).toHaveLength(1),
  );
  expect(
    JSON.parse(String(sent(fetcher, "POST", "/holds/5/release")[0][1]?.body)),
  ).toEqual({
    disposition: "CONCESSION",
    releaseInspectionId: null,
    reason: "고객 승인",
  });
});

it("게시한 기준은 개정·폐기만 있고 항목을 바꿀 수 없다", async () => {
  const spec = {
    id: 3,
    itemCode: "FG-C100",
    itemName: "커넥터 C100",
    versionNo: 1,
    status: "published",
    publishedAt: "2026-09-24T00:00:00+00:00",
    note: null,
    itemCount: 2,
    inspectionCount: 1,
  };
  mount("/qms/specs", {
    [`GET ${Q}/inspection-specs`]: ok([spec]),
    [`GET ${Q}/inspection-specs/3`]: ok({ ...spec, items: values }),
  });
  const table = await screen.findByRole("table", { name: "검사 기준 목록" });
  expect(within(table).getByRole("button", { name: "개정" })).toBeVisible();
  expect(
    within(table).queryByRole("button", { name: "게시" }),
  ).not.toBeInTheDocument();
  fireEvent.click(within(table).getByRole("button", { name: "항목 2" }));
  const dialog = await screen.findByRole("dialog", {
    name: "FG-C100 v1 검사 항목",
  });
  expect(within(dialog).getByText(/바꿀 수 없습니다/)).toBeVisible();
  expect(
    within(dialog).queryByRole("button", { name: "항목 추가" }),
  ).not.toBeInTheDocument();
});

it("대시보드는 검사가 없으면 합격률을 계산하지 않고 MES를 끄면 대기를 조회하지 않는다", async () => {
  mount("/qms/dashboard", {
    [`GET ${Q}/dashboard`]: ok({
      month: "2026-09",
      inspected: 0,
      passRate: null,
      activeHolds: 0,
      pendingLots: null,
      daily: [],
      topDefects: [],
      recentFails: [],
      holds: [],
    }),
  });
  expect(await screen.findByLabelText("합격률")).toHaveTextContent("계산 불가");
  expect(screen.getByLabelText("검사 대기")).toHaveTextContent("조회 불가");
});

it("MES 패킹은 QMS 보류 LOT에 배지를 붙이고 막지 않는다고 안내한다", async () => {
  mount("/mes/packing", {
    "GET /api/v1/mes/packable-lots": ok([
      {
        lotId: 1,
        lotNo: "LT-0016",
        itemId: 1,
        unit: "EA",
        finalGoodQty: "1940.000",
        packedQty: "0",
        remainingQty: "1940.000",
        qualityHold: true,
      },
    ]),
  });
  const table = await screen.findByRole("table", { name: "담을 수 있는 LOT" });
  expect(within(table).getByText("QMS 보류")).toBeVisible();
  expect(screen.getByText(/패킹을 막지 않습니다/)).toBeVisible();
});
