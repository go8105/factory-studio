// FS-024b WMS 화면. 검증 항목별로 테스트를 나눈다.
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

const W = "/api/v1/wms";
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
            data: ["core", "mes", "erp", "fems", "qms", "wms"].map((m) => ({
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

const receipt = {
  sourceKey: "MES:RECEIPT:PL-0006",
  sourceRef: "PL-0006",
  occurredAt: "2026-08-25T06:00:00+00:00",
  lines: [
    { itemCode: "FG-T300", qty: "982.000", unit: "EA", lotNo: "LT-0009" },
  ],
  state: "pending",
  reason: null,
  documentId: null,
  documentNo: null,
};
const warehouses = [
  {
    id: 1,
    code: "WH-FG",
    name: "완제품 창고",
    purpose: "FG",
    isActive: true,
    locationCount: 2,
  },
];
const locations = [
  {
    id: 11,
    warehouseId: 1,
    warehouseCode: "WH-FG",
    code: "F-A01",
    name: "기본 보관",
    isDefault: true,
    isActive: true,
    moveCount: 3,
  },
  {
    id: 12,
    warehouseId: 1,
    warehouseCode: "WH-FG",
    code: "F-A02",
    name: "예비",
    isDefault: false,
    isActive: true,
    moveCount: 0,
  },
];
const items = [
  {
    id: 21,
    itemCode: "FG-C100",
    name: "커넥터 C100",
    baseUnit: "EA",
    itemClass: "FG",
    lotTracked: true,
    isActive: true,
    moveCount: 2,
    conversions: [],
  },
];

it("W-01 대시보드와 사이드바 W-01~07", async () => {
  mount("/wms/dashboard", {
    [`GET ${W}/dashboard`]: ok({
      month: "2026-09",
      rawItems: 2,
      fgLots: 11,
      negativeCount: 0,
      pendingSources: 9,
      pendingByKind: {
        MES_RECEIPT: 1,
        MES_ISSUE: 6,
        ERP_SHIPMENT: 1,
        ERP_PURCHASE: 1,
      },
      items: [],
      flows: [],
    }),
  });
  expect(
    await screen.findByRole("heading", { name: "재고 개요" }),
  ).toBeVisible();
  for (const id of ["W-01", "W-02", "W-03", "W-04", "W-05", "W-06", "W-07"])
    expect(
      screen.getAllByRole("link", { name: new RegExp(id) }).length,
    ).toBeGreaterThan(0);
  const pending = await screen.findByRole("region", { name: "미반영 원천" });
  expect(within(pending).getByText("9")).toBeVisible();
});

it("W-03 행 반영은 원천 키로 반영 요청을 보내고 결과를 요약한다", async () => {
  const fetcher = mount("/wms/sources", {
    [`GET ${W}/sources`]: ok({
      kind: "MES_RECEIPT",
      disabled: false,
      rows: [receipt],
    }),
    [`POST ${W}/sources/sync`]: ok({
      results: [
        { sourceKey: receipt.sourceKey, state: "synced", documentId: 5 },
      ],
      synced: 1,
      blocked: 0,
    }),
  });
  const table = await screen.findByRole("table", {
    name: "MES 완제품 입고 원천",
  });
  expect(within(table).getByText(/FG-T300 982 EA \(LT-0009\)/)).toBeVisible();
  fireEvent.click(within(table).getByRole("button", { name: "반영" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/sources/sync")).toHaveLength(1),
  );
  expect(body(sent(fetcher, "POST", "/sources/sync")[0])).toEqual({
    kind: "MES_RECEIPT",
    sourceKeys: ["MES:RECEIPT:PL-0006"],
  });
  expect(await screen.findByRole("status")).toHaveTextContent("반영 1");
});

it("W-03 반영 불가 원천은 사유와 해결 화면 링크를 보인다", async () => {
  mount("/wms/sources", {
    [`GET ${W}/sources`]: ok({
      kind: "MES_RECEIPT",
      disabled: false,
      rows: [
        {
          ...receipt,
          state: "blocked",
          reason: { code: "ITEM_NOT_REGISTERED", itemCode: "FG-T300" },
        },
      ],
    }),
  });
  expect(await screen.findByText(/품목 미등록 · FG-T300/)).toBeVisible();
  expect(screen.getByRole("link", { name: "품목·단위로" })).toHaveAttribute(
    "href",
    "/wms/items",
  );
  expect(
    screen.queryByRole("button", { name: /모두 반영/ }),
  ).not.toBeInTheDocument();
});

it("W-03 원천 솔루션이 꺼져 있으면 수동 전표로 안내한다", async () => {
  mount("/wms/sources", {
    [`GET ${W}/sources`]: ok({
      kind: "MES_RECEIPT",
      disabled: true,
      sourceModule: "mes",
      rows: [],
    }),
  });
  expect(
    await screen.findByText(/MES를 사용하지 않도록 설정했습니다/),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: /재고 전표로/ })).toBeVisible();
});

it("W-02는 음수·LOT 미지정을 문구로 표시하고 ERP 꺼짐이면 가용을 계산하지 않는다", async () => {
  mount("/wms/stock", {
    [`GET ${W}/stock`]: ok({
      rows: [
        {
          itemId: 21,
          itemCode: "FG-C200",
          itemName: "커넥터 C200",
          itemClass: "FG",
          unit: "EA",
          locationId: 11,
          locationCode: "F-A01",
          warehouseId: 1,
          warehouseCode: "WH-FG",
          lotNo: null,
          onHand: "-3842.000",
          normalOnHand: "-3842.000",
          quarantinedOnHand: "0",
          reservedQty: "40",
          reservationShortage: "3882",
          available: "-3882",
          negative: true,
          lotUnassigned: true,
        },
      ],
      totals: [
        {
          itemCode: "FG-C200",
          onHand: "-3842.000",
          normalOnHand: "-3842.000",
          quarantinedOnHand: "0",
          reservedQty: "40",
          reservationShortage: "3882",
          available: "-3882",
          openShipmentQty: null,
        },
      ],
    }),
  });
  const table = await screen.findByRole("table", { name: "재고 현황" });
  expect(within(table).getByText("음수")).toBeVisible();
  expect(within(table).getByText("LOT 미지정")).toBeVisible();
  expect(within(table).getByText("(미지정)")).toBeVisible();
  expect(screen.getByText(/ERP 수요 참고 없음/)).toBeVisible();
  expect(screen.getByText(/예약 가능 -3,882/)).toBeVisible();
  expect(within(table).getByText(/예약 부족 3,882/)).toBeVisible();
});

it("W-04 이동 전표는 보낼·받을 위치 쌍으로 보내고 줄 오류를 줄 아래에 보인다", async () => {
  const fetcher = mount("/wms/documents", {
    [`GET ${W}/items`]: ok(items),
    [`GET ${W}/warehouses`]: ok(warehouses),
    [`GET ${W}/warehouses/1/locations`]: ok(locations),
    [`POST ${W}/documents`]: {
      status: 400,
      body: {
        error: {
          code: "VALIDATION_FAILED",
          message: "입력값을 확인해 주세요.",
          details: {
            fields: { "lines.0.lotNo": "완제품 이동은 LOT을 지정해야 합니다." },
          },
        },
      },
    },
  });
  fireEvent.change(await screen.findByLabelText("전표 만들기"), {
    target: { value: "TRANSFER" },
  });
  const dialog = await screen.findByRole("dialog", {
    name: "창고 간 이동 전표 작성",
  });
  await waitFor(() =>
    expect(
      within(dialog).getAllByRole("option", { name: "WH-FG F-A02" }).length,
    ).toBe(2),
  );
  fireEvent.change(within(dialog).getByLabelText("1번 줄 품목"), {
    target: { value: "21" },
  });
  fireEvent.change(within(dialog).getByLabelText("1번 줄 보낼 위치"), {
    target: { value: "11" },
  });
  fireEvent.change(within(dialog).getByLabelText("1번 줄 받을 위치"), {
    target: { value: "12" },
  });
  fireEvent.change(within(dialog).getByLabelText("1번 줄 수량"), {
    target: { value: "500" },
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "임시 저장" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/documents")).toHaveLength(1),
  );
  expect(body(sent(fetcher, "POST", "/documents")[0])).toMatchObject({
    documentType: "TRANSFER",
    lines: [{ itemId: 21, fromLocationId: 11, toLocationId: 12, qty: "500" }],
  });
  expect(
    await within(dialog).findByText("완제품 이동은 LOT을 지정해야 합니다."),
  ).toBeVisible();
});

it("W-06 위치 추가 폼을 닫으면 위치 상세로 돌아간다", async () => {
  mount("/wms/warehouses", {
    [`GET ${W}/warehouses`]: ok(warehouses),
    [`GET ${W}/warehouses/1/locations`]: ok(locations),
  });
  fireEvent.click(await screen.findByRole("button", { name: "위치 2" }));
  const detail = await screen.findByRole("dialog", { name: "WH-FG 위치" });
  expect(
    within(within(detail).getByRole("row", { name: /F-A01/ })).getByText(
      "기본",
    ),
  ).toBeVisible();
  // 기본 위치는 삭제 버튼이 없다(기본 지정은 다른 위치를 기본으로 바꿔서 푼다).
  expect(within(detail).getAllByRole("button", { name: "삭제" })).toHaveLength(
    1,
  );
  fireEvent.click(within(detail).getByRole("button", { name: "위치 추가" }));
  const form = await screen.findByRole("dialog", { name: "WH-FG 위치 추가" });
  fireEvent.click(within(form).getByRole("button", { name: "취소" }));
  expect(
    await screen.findByRole("dialog", { name: "WH-FG 위치" }),
  ).toBeVisible();
});

it.each([
  ["inspection_pending", "검수 대기"],
  ["inspected", "검수 완료"],
  ["inspected_cancelled", "검수 후 원천 취소"],
])("W-03은 %s 원천의 전표가 없어도 상태를 표시한다", async (state, label) => {
  mount("/wms/sources", {
    [`GET ${W}/sources`]: ok({
      kind: "ERP_PURCHASE",
      disabled: false,
      rows: [{ ...receipt, state, documentId: null, documentNo: null }],
    }),
  });
  const table = await screen.findByRole("table");
  expect(within(table).getByText(label)).toBeVisible();
  expect(within(table).queryByRole("button", { name: "반영" })).toBeNull();
});

it("W-07 품목 등록 시 유효기간·안전재고·ABC·PLM 등 확장 필드를 전송한다", async () => {
  const items = [
    {
      id: 1,
      itemCode: "RAW-STEEL",
      name: "강판",
      baseUnit: "KG",
      itemClass: "RAW",
      lotTracked: true,
      shelfLifeDays: 180,
      storageCondition: "상온 건조",
      safetyStock: "50.000",
      maxStock: "200.000",
      abcClass: "A",
      plmPartNo: "PLM-ST-01",
      plmRevision: "R1",
      isActive: true,
      moveCount: 0,
      conversions: [],
    },
  ];
  const fetcher = mount("/wms/items", {
    [`GET ${W}/items`]: ok(items),
    [`POST ${W}/items`]: ok({ id: 2 }),
  });
  expect(await screen.findByText("RAW-STEEL")).toBeVisible();
  expect(screen.getByText("180일")).toBeVisible();
  expect(screen.getByText("50 / 200")).toBeVisible();
  expect(screen.getByText("A")).toBeVisible();

  fireEvent.click(screen.getByRole("button", { name: "품목 등록" }));
  const dialog = await screen.findByRole("dialog", { name: "품목 등록" });

  fireEvent.change(within(dialog).getByLabelText("품목 코드"), {
    target: { value: "FG-BOX" },
  });
  fireEvent.change(within(dialog).getByLabelText("이름"), {
    target: { value: "포장박스" },
  });
  fireEvent.change(within(dialog).getByLabelText("유효기간 (일)"), {
    target: { value: "365" },
  });
  fireEvent.change(within(dialog).getByLabelText("안전재고"), {
    target: { value: "100" },
  });
  fireEvent.change(within(dialog).getByLabelText("최대재고"), {
    target: { value: "500" },
  });
  fireEvent.change(within(dialog).getByLabelText("ABC 등급"), {
    target: { value: "B" },
  });
  fireEvent.change(within(dialog).getByLabelText("PLM 품번"), {
    target: { value: "PLM-BX-01" },
  });
  fireEvent.change(within(dialog).getByLabelText("PLM 리비전"), {
    target: { value: "A" },
  });

  fireEvent.click(within(dialog).getByRole("button", { name: "등록" }));
  await waitFor(() => expect(sent(fetcher, "POST", "/items")).toHaveLength(1));
  expect(body(sent(fetcher, "POST", "/items")[0])).toMatchObject({
    itemCode: "FG-BOX",
    name: "포장박스",
    shelfLifeDays: 365,
    safetyStock: "100",
    maxStock: "500",
    abcClass: "B",
    plmPartNo: "PLM-BX-01",
    plmRevision: "A",
  });
});

it("W-10 LOT 목록 렌더링, 원장 재고 표시, 상세 패널, LOT 등록을 검증한다", async () => {
  const items = [
    {
      id: 1,
      itemCode: "FG-T300",
      name: "T300 완제품",
      baseUnit: "EA",
      itemClass: "FG",
      lotTracked: true,
      shelfLifeDays: 90,
      isActive: true,
      moveCount: 0,
      conversions: [],
    },
  ];
  const lotRow = {
    id: 101,
    itemId: 1,
    itemCode: "FG-T300",
    itemName: "T300 완제품",
    itemClass: "FG",
    baseUnit: "EA",
    lotNo: "LOT-20261015-001",
    origin: "RECEIPT",
    receivedOn: "2026-10-15",
    expiryDate: "2027-01-13",
    supplierLotNo: "SUP-999",
    status: "AVAILABLE",
    rawStatus: "AVAILABLE",
    qtyOnHand: "1500.000",
    isExpired: false,
    holdCount: 0,
    currentHoldReason: null,
    createdAt: "2026-10-15T09:00:00Z",
  };
  const lotDetail = {
    ...lotRow,
    locations: [
      {
        locationId: 11,
        locationCode: "F-A01",
        locationName: "기본 보관",
        warehouseId: 1,
        warehouseCode: "WH-FG",
        warehouseName: "완제품 창고",
        qtyOnHand: "1500.000",
      },
    ],
    holds: [],
  };

  const fetcher = mount("/wms/lots", {
    [`GET ${W}/items`]: ok(items),
    [`GET ${W}/lots`]: {
      status: 200,
      body: {
        data: [lotRow],
        page: { offset: 0, limit: 50, total: 1 },
      },
    },
    [`GET ${W}/lots/101`]: ok(lotDetail),
    [`POST ${W}/lots/101/hold`]: ok({
      ...lotDetail,
      status: "HOLD",
      isHeld: true,
      activeHold: {
        id: 1,
        source: "MANUAL",
        sourceRef: null,
        heldAt: "2026-10-17T09:00:00Z",
        reason: "불량 의심",
      },
      holds: [
        {
          id: 1,
          source: "MANUAL",
          sourceRef: null,
          heldAt: "2026-10-17T09:00:00Z",
          releasedAt: null,
          reason: "불량 의심",
          isActive: true,
        },
      ],
    }),
    [`POST ${W}/lots/101/release`]: ok({
      ...lotDetail,
      status: "AVAILABLE",
      isHeld: false,
      activeHold: null,
      holds: [
        {
          id: 1,
          source: "MANUAL",
          sourceRef: null,
          heldAt: "2026-10-17T09:00:00Z",
          releasedAt: "2026-10-17T09:30:00Z",
          reason: "불량 의심",
          isActive: false,
        },
      ],
    }),
    [`POST ${W}/lots`]: ok({ id: 102, lotNo: "LOT-20261015-002" }),
  });

  // 목록 렌더링 및 원장 합계 재고 표시 확인
  expect(await screen.findByText("LOT-20261015-001")).toBeVisible();
  expect(screen.getByText("1,500 EA")).toBeVisible();
  expect(screen.getByText("SUP-999")).toBeVisible();
  expect(within(screen.getByRole("table")).getByText("가용")).toBeVisible();

  // 상세 패널 열기 및 확인
  fireEvent.click(screen.getByRole("button", { name: "상세" }));
  const detailPanel = await screen.findByRole("dialog", {
    name: "LOT-20261015-001 상세",
  });
  expect(within(detailPanel).getByText("원장 집계 현재고")).toBeVisible();
  expect(within(detailPanel).getByText("F-A01 (기본 보관)")).toBeVisible();
  expect(within(detailPanel).getByText("보류 상태 및 관리")).toBeVisible();
  expect(
    within(detailPanel).getByRole("button", { name: "보류 설정" }),
  ).toBeVisible();

  // 보류 설정 열기 및 제출
  fireEvent.click(
    within(detailPanel).getByRole("button", { name: "보류 설정" }),
  );
  fireEvent.change(within(detailPanel).getByLabelText("보류 사유 (2자 이상)"), {
    target: { value: "검사 불량 의심" },
  });
  fireEvent.click(
    within(detailPanel).getByRole("button", { name: "보류 확정" }),
  );
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/lots/101/hold")).toHaveLength(1),
  );
  expect(body(sent(fetcher, "POST", "/lots/101/hold")[0])).toMatchObject({
    source: "MANUAL",
    reason: "검사 불량 의심",
  });

  // 닫기
  fireEvent.click(within(detailPanel).getByLabelText("패널 닫기"));

  // LOT 등록 모달 열기 및 등록
  fireEvent.click(screen.getByRole("button", { name: "LOT 등록" }));
  const createDialog = await screen.findByRole("dialog", { name: "LOT 등록" });

  fireEvent.change(within(createDialog).getByLabelText("품목"), {
    target: { value: "1" },
  });
  fireEvent.change(within(createDialog).getByLabelText("LOT 번호"), {
    target: { value: "LOT-20261015-002" },
  });
  fireEvent.change(within(createDialog).getByLabelText("공급처 LOT 번호"), {
    target: { value: "SUP-002" },
  });

  fireEvent.click(within(createDialog).getByRole("button", { name: "등록" }));
  await waitFor(() => expect(sent(fetcher, "POST", "/lots")).toHaveLength(1));
  expect(body(sent(fetcher, "POST", "/lots")[0])).toMatchObject({
    itemId: 1,
    lotNo: "LOT-20261015-002",
    supplierLotNo: "SUP-002",
    origin: "RECEIPT",
  });
});

it("W-10 LOT 보류 해제 및 QMS 보류 표시를 검증한다", async () => {
  const heldLot = {
    id: 201,
    itemId: 1,
    itemCode: "FG-T300",
    itemName: "T300 완제품",
    itemClass: "FG" as const,
    baseUnit: "EA",
    lotNo: "LT-HELD-001",
    origin: "RECEIPT" as const,
    receivedOn: "2026-10-15",
    expiryDate: null,
    supplierLotNo: null,
    status: "HOLD" as const,
    rawStatus: "HOLD" as const,
    qtyOnHand: "500.000",
    isExpired: false,
    isHeld: true,
    holdCount: 1,
    currentHoldReason: "인장 강도 미달",
    createdAt: "2026-10-15T09:00:00Z",
    qmsHold: {
      active: true,
      holdNo: "QH-20261017-009",
      reason: "인장 강도 미달",
    },
    activeHold: {
      id: 10,
      source: "QMS" as const,
      sourceRef: "QH-20261017-009",
      heldAt: "2026-10-17T09:00:00Z",
      reason: "인장 강도 미달",
    },
    holds: [
      {
        id: 10,
        source: "QMS" as const,
        sourceRef: "QH-20261017-009",
        heldAt: "2026-10-17T09:00:00Z",
        releasedAt: null,
        reason: "인장 강도 미달",
        isActive: true,
        status: "HELD" as const,
      },
    ],
  };

  const fetcher = mount("/wms/lots", {
    [`GET ${W}/items`]: ok([]),
    [`GET ${W}/lots`]: {
      status: 200,
      body: {
        data: [{ ...heldLot, qmsHold: true }],
        page: { offset: 0, limit: 50, total: 1 },
      },
    },
    [`GET ${W}/lots/201`]: ok(heldLot),
    [`POST ${W}/lots/201/release`]: ok({
      ...heldLot,
      status: "AVAILABLE",
      isHeld: false,
      activeHold: null,
    }),
  });

  expect(await screen.findByText("LT-HELD-001")).toBeVisible();
  expect(screen.getByText("QMS 보류")).toBeVisible();

  // 상세 패널 열기
  fireEvent.click(screen.getByRole("button", { name: "상세" }));
  const detailPanel = await screen.findByRole("dialog", {
    name: "LT-HELD-001 상세",
  });
  expect(within(detailPanel).getByText("현재 보류 중")).toBeVisible();
  expect(
    within(detailPanel).getByText("QMS 품질 보류 (QH-20261017-009)"),
  ).toBeVisible();

  // 보류 해제 클릭
  fireEvent.click(
    within(detailPanel).getByRole("button", { name: "보류 해제" }),
  );
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/lots/201/release")).toHaveLength(1),
  );
});

it("W-08 입고 예정 목록과 상세에서 noticeKind 구분을 표시하고 등록 시 전송한다", async () => {
  const inboundPo = {
    id: 101,
    noticeNo: "IN-20261017-001",
    noticeKind: "PO" as const,
    businessKey: "PO-20261017-01",
    warehouseId: 1,
    expectedOn: "2026-10-25",
    vehicleNo: "서울12가3456",
    partnerRef: "SUP-01",
    status: "PLANNED" as const,
    version: 1,
    arrivedAt: null,
    inspectedAt: null,
    reason: null,
    stockDocumentId: null,
    lines: [
      {
        id: 1,
        itemId: 10,
        lotNo: null,
        expectedQty: "100.000",
        normalLocationId: 11,
        quarantineLocationId: null,
        acceptedQty: null,
        quarantinedQty: null,
        shortageQty: null,
        reason: null,
      },
    ],
    sourceClaim: null,
    sourceState: "manual",
  };

  const fetcher = mount("/wms/inbounds", {
    [`GET ${W}/inbound-notices`]: ok({
      rows: [inboundPo],
      total: 1,
      page: 1,
      pageSize: 50,
    }),
    [`GET ${W}/warehouses`]: ok([
      {
        id: 1,
        code: "WH-RAW",
        name: "원자재 창고",
        purpose: "RAW",
        isActive: true,
        locationCount: 2,
      },
    ]),
    [`GET ${W}/items`]: ok([
      {
        id: 10,
        itemCode: "RM-TEST",
        name: "테스트 원자재",
        baseUnit: "KG",
        itemClass: "RAW",
        isActive: true,
      },
    ]),
    [`GET ${W}/inbound-notices/101`]: ok(inboundPo),
    [`GET ${W}/warehouses/1/locations`]: ok(locations),
    [`GET ${W}/sources`]: ok({ disabled: false, rows: [] }),
    [`POST ${W}/inbound-notices`]: ok({
      ...inboundPo,
      id: 102,
      noticeNo: "IN-20261017-002",
      noticeKind: "SALES_RETURN",
    }),
  });

  // 목록에 "발주" 배지와 번호 표시 확인
  expect(await screen.findByText("IN-20261017-001")).toBeVisible();
  const table = screen.getByRole("table");
  expect(within(table).getByText("발주")).toBeVisible();

  // 상세 패널 열기
  fireEvent.click(screen.getByRole("button", { name: "상세" }));
  const detailPanel = await screen.findByRole("dialog", {
    name: "IN-20261017-001",
  });
  expect(within(detailPanel).getByText(/구분 발주/)).toBeVisible();

  // 닫기
  fireEvent.click(
    within(detailPanel).getByRole("button", { name: "패널 닫기" }),
  );

  // 등록 패널 열기
  fireEvent.click(screen.getByRole("button", { name: "입고 예정 등록" }));
  const formPanel = await screen.findByRole("dialog", {
    name: "입고 예정 등록",
  });

  // 업무 번호 입력
  fireEvent.change(within(formPanel).getByLabelText("업무 중복 방지 번호"), {
    target: { value: "RET-20261017-99" },
  });

  // 구분 선택: 판매 반품
  fireEvent.change(within(formPanel).getByLabelText("입고 구분"), {
    target: { value: "SALES_RETURN" },
  });

  // 품목 선택
  fireEvent.change(within(formPanel).getByLabelText("품목"), {
    target: { value: "10" },
  });

  // 예정 수량 입력
  fireEvent.change(within(formPanel).getByLabelText("예정 수량"), {
    target: { value: "25" },
  });

  // 정상 위치 선택
  fireEvent.change(within(formPanel).getByLabelText("정상 위치"), {
    target: { value: "11" },
  });

  // 등록 제출
  fireEvent.click(within(formPanel).getByRole("button", { name: "예정 등록" }));

  await waitFor(() => {
    const postCalls = sent(fetcher, "POST", "/inbound-notices");
    expect(postCalls).toHaveLength(1);
    const sentBody = body(postCalls[0]);
    expect(sentBody.noticeKind).toBe("SALES_RETURN");
    expect(sentBody.businessKey).toBe("RET-20261017-99");
  });
});

it("W-08 품목 lotTracked 여부에 따른 LOT 입력 필드 노출 및 초기화", async () => {
  const fetcher = mount("/wms/inbounds", {
    [`GET ${W}/inbound-notices`]: ok({
      rows: [],
      total: 0,
      page: 1,
      pageSize: 50,
    }),
    [`GET ${W}/warehouses`]: ok([
      {
        id: 1,
        code: "WH-RAW",
        name: "원자재 창고",
        purpose: "RAW",
        isActive: true,
        locationCount: 2,
      },
    ]),
    [`GET ${W}/items`]: ok([
      {
        id: 10,
        itemCode: "RM-NORMAL",
        name: "일반 원자재",
        baseUnit: "KG",
        itemClass: "RAW",
        lotTracked: false,
        isActive: true,
      },
      {
        id: 20,
        itemCode: "RM-LOT",
        name: "LOT 원자재",
        baseUnit: "KG",
        itemClass: "RAW",
        lotTracked: true,
        isActive: true,
      },
    ]),
    [`GET ${W}/warehouses/1/locations`]: ok(locations),
    [`GET ${W}/sources`]: ok({ disabled: false, rows: [] }),
    [`POST ${W}/inbound-notices`]: ok({
      id: 201,
      noticeNo: "IN-20261017-099",
      version: 1,
    }),
  });

  // 등록 패널 열기
  fireEvent.click(
    await screen.findByRole("button", { name: "입고 예정 등록" }),
  );
  const formPanel = await screen.findByRole("dialog", {
    name: "입고 예정 등록",
  });

  // 초기 상태: LOT 입력 필드 없음
  expect(within(formPanel).queryByLabelText("LOT")).toBeNull();

  // 1. lotTracked=false 품목(10) 선택 -> LOT 필드 미노출
  fireEvent.change(within(formPanel).getByLabelText("품목"), {
    target: { value: "10" },
  });
  expect(within(formPanel).queryByLabelText("LOT")).toBeNull();

  // 2. lotTracked=true 품목(20) 선택 -> LOT 필드 필수 노출
  fireEvent.change(within(formPanel).getByLabelText("품목"), {
    target: { value: "20" },
  });
  const lotField = within(formPanel).getByLabelText("LOT");
  expect(lotField).toBeVisible();
  expect(lotField).toBeRequired();

  // LOT 값 입력
  fireEvent.change(lotField, { target: { value: "LOT-TEMP-123" } });
  expect(lotField).toHaveValue("LOT-TEMP-123");

  // 3. 다시 lotTracked=false 품목(10)으로 변경 -> LOT 필드 사라짐
  fireEvent.change(within(formPanel).getByLabelText("품목"), {
    target: { value: "10" },
  });
  expect(within(formPanel).queryByLabelText("LOT")).toBeNull();

  // 4. 다시 lotTracked=true 품목(20)으로 변경 -> 빈 값으로 노출
  fireEvent.change(within(formPanel).getByLabelText("품목"), {
    target: { value: "20" },
  });
  const newLotField = within(formPanel).getByLabelText("LOT");
  expect(newLotField).toBeVisible();
  expect(newLotField).toHaveValue("");

  // 최종 입력 및 제출
  fireEvent.change(within(formPanel).getByLabelText("업무 중복 방지 번호"), {
    target: { value: "BIZ-LOT-01" },
  });
  fireEvent.change(newLotField, { target: { value: "LOT-FINAL-999" } });
  fireEvent.change(within(formPanel).getByLabelText("예정 수량"), {
    target: { value: "120" },
  });
  fireEvent.change(within(formPanel).getByLabelText("정상 위치"), {
    target: { value: "11" },
  });
  fireEvent.click(within(formPanel).getByRole("button", { name: "예정 등록" }));

  await waitFor(() => {
    const postCalls = sent(fetcher, "POST", "/inbound-notices");
    expect(postCalls).toHaveLength(1);
    const sentBody = body(postCalls[0]);
    expect(sentBody.lines[0].itemId).toBe(20);
    expect(sentBody.lines[0].lotNo).toBe("LOT-FINAL-999");
  });
});

it("W-08 입고 예정 등록 시 RECEIVING 위치가 있으면 기본 선택되고 목록에 [입고장]이 표시된다", async () => {
  const receivingLocations = [
    {
      id: 11,
      warehouseId: 1,
      warehouseCode: "WH-RAW",
      code: "R-A01",
      name: "일반 랙",
      locationType: "NORMAL",
      isDefault: true,
      isActive: true,
      moveCount: 0,
    },
    {
      id: 15,
      warehouseId: 1,
      warehouseCode: "WH-RAW",
      code: "R-REC",
      name: "원자재 입고장",
      locationType: "RECEIVING",
      isDefault: false,
      isActive: true,
      moveCount: 0,
    },
  ];

  const fetcher = mount("/wms/inbounds", {
    [`GET ${W}/inbound-notices`]: ok({
      rows: [],
      total: 0,
      page: 1,
      pageSize: 50,
    }),
    [`GET ${W}/warehouses`]: ok([
      {
        id: 1,
        code: "WH-RAW",
        name: "원자재 창고",
        purpose: "RAW",
        isActive: true,
        locationCount: 2,
      },
    ]),
    [`GET ${W}/items`]: ok([
      {
        id: 10,
        itemCode: "RM-RAW01",
        name: "원자재 품목",
        baseUnit: "KG",
        itemClass: "RAW",
        lotTracked: false,
        isActive: true,
      },
    ]),
    [`GET ${W}/warehouses/1/locations`]: ok(receivingLocations),
    [`GET ${W}/sources`]: ok({ disabled: false, rows: [] }),
    [`POST ${W}/inbound-notices`]: ok({
      id: 301,
      noticeNo: "IN-20261018-001",
      version: 1,
    }),
  });

  fireEvent.click(
    await screen.findByRole("button", { name: "입고 예정 등록" }),
  );
  const formPanel = await screen.findByRole("dialog", {
    name: "입고 예정 등록",
  });

  // RECEIVING 위치가 우선 기본값으로 선택되는지 확인
  const normalSelect = (await within(formPanel).findByLabelText(
    "정상 위치",
  )) as HTMLSelectElement;
  await waitFor(() => {
    expect(normalSelect.value).toBe("15");
  });

  // 드롭다운에 RECEIVING과 NORMAL이 모두 표시되고, RECEIVING에는 [입고장] 꼬리표가 붙음
  expect(
    within(normalSelect).getByRole("option", {
      name: "R-REC 원자재 입고장 [입고장]",
    }),
  ).toBeInTheDocument();
  expect(
    within(normalSelect).getByRole("option", {
      name: "R-A01 일반 랙",
    }),
  ).toBeInTheDocument();

  // 제출 시 normalLocationId로 15가 전송되는지 확인
  fireEvent.change(within(formPanel).getByLabelText("업무 중복 방지 번호"), {
    target: { value: "PO-REC-01" },
  });
  fireEvent.change(within(formPanel).getByLabelText("품목"), {
    target: { value: "10" },
  });
  fireEvent.change(within(formPanel).getByLabelText("예정 수량"), {
    target: { value: "50" },
  });
  fireEvent.click(within(formPanel).getByRole("button", { name: "예정 등록" }));

  await waitFor(() => {
    const postCalls = sent(fetcher, "POST", "/inbound-notices");
    expect(postCalls).toHaveLength(1);
    const sentBody = body(postCalls[0]);
    expect(sentBody.lines[0].normalLocationId).toBe(15);
  });
});

it("W-11 적치 목록 렌더링, 추천 위치 기본 선택·변경 적치 완료 및 취소 검증", async () => {
  const tasks = [
    {
      id: 1,
      taskNo: "PT-20261018-001",
      sourceDocumentId: 101,
      warehouseId: 1,
      warehouseCode: "WH-RAW",
      warehouseName: "원자재 창고",
      itemId: 10,
      itemCode: "RM-RAW01",
      itemName: "원자재 품목",
      baseUnit: "KG",
      lotNo: "LOT-100",
      qty: "70.000",
      fromLocationId: 15,
      fromLocationCode: "R-REC",
      fromLocationName: "원자재 입고장",
      suggestedLocationId: 11,
      suggestedLocationCode: "R-B01",
      suggestedLocationName: "기본 랙",
      toLocationId: null,
      toLocationCode: null,
      toLocationName: null,
      status: "OPEN",
      doneAt: null,
      stockDocumentId: null,
      createdAt: "2026-10-18T10:00:00+09:00",
    },
    {
      id: 2,
      taskNo: "PT-20261018-002",
      sourceDocumentId: 102,
      warehouseId: 1,
      warehouseCode: "WH-RAW",
      warehouseName: "원자재 창고",
      itemId: 20,
      itemCode: "RM-RAW02",
      itemName: "원자재 품목2",
      baseUnit: "EA",
      lotNo: null,
      qty: "50.000",
      fromLocationId: 15,
      fromLocationCode: "R-REC",
      fromLocationName: "원자재 입고장",
      suggestedLocationId: null,
      suggestedLocationCode: null,
      suggestedLocationName: null,
      toLocationId: null,
      toLocationCode: null,
      toLocationName: null,
      status: "OPEN",
      doneAt: null,
      stockDocumentId: null,
      createdAt: "2026-10-18T10:05:00+09:00",
    },
  ];

  const whLocations = [
    {
      id: 11,
      warehouseId: 1,
      warehouseCode: "WH-RAW",
      code: "R-B01",
      name: "기본 랙",
      isDefault: true,
      isActive: true,
      moveCount: 0,
      locationType: "NORMAL",
    },
    {
      id: 12,
      warehouseId: 1,
      warehouseCode: "WH-RAW",
      code: "R-B02",
      name: "보조 랙",
      isDefault: false,
      isActive: true,
      moveCount: 0,
      locationType: "NORMAL",
    },
    {
      id: 15,
      warehouseId: 1,
      warehouseCode: "WH-RAW",
      code: "R-REC",
      name: "원자재 입고장",
      isDefault: false,
      isActive: true,
      moveCount: 1,
      locationType: "RECEIVING",
    },
  ];

  const fetcher = mount("/wms/putaways", {
    [`GET ${W}/warehouses`]: ok([
      {
        id: 1,
        code: "WH-RAW",
        name: "원자재 창고",
        purpose: "RAW",
        isActive: true,
        locationCount: 3,
      },
    ]),
    [`GET ${W}/items`]: ok([
      {
        id: 10,
        itemCode: "RM-RAW01",
        name: "원자재 품목",
        baseUnit: "KG",
        itemClass: "RAW",
        lotTracked: true,
        isActive: true,
      },
      {
        id: 20,
        itemCode: "RM-RAW02",
        name: "원자재 품목2",
        baseUnit: "EA",
        itemClass: "RAW",
        lotTracked: false,
        isActive: true,
      },
    ]),
    [`GET ${W}/putaway-tasks`]: ok({
      rows: tasks,
      total: 2,
      page: 1,
      pageSize: 50,
    }),
    [`GET ${W}/warehouses/1/locations`]: ok(whLocations),
    [`POST ${W}/putaway-tasks/1/complete`]: ok({
      ...tasks[0],
      toLocationId: 12,
      toLocationCode: "R-B02",
      toLocationName: "보조 랙",
      status: "DONE",
      doneAt: "2026-10-18T10:15:00+09:00",
      stockDocumentId: 501,
    }),
    [`POST ${W}/putaway-tasks/2/cancel`]: ok({
      ...tasks[1],
      status: "CANCELLED",
    }),
  });

  expect(
    await screen.findByRole("heading", { name: "W-11 적치" }),
  ).toBeVisible();

  const table = screen.getByRole("table", { name: "적치 작업 목록" });
  expect(within(table).getByText("PT-20261018-001")).toBeVisible();
  expect(within(table).getByText("PT-20261018-002")).toBeVisible();
  expect(within(table).getAllByText("대기")).toHaveLength(2);
  expect(within(table).getByText(/R-B01/)).toBeVisible();
  expect(within(table).getByText("추천 없음")).toBeVisible();

  // 1. 첫 번째 적치 작업(추천 위치 있음) 상세 열기 -> 추천 위치(11)가 기본 선택됨
  const detailButtons = within(table).getAllByRole("button", { name: "상세" });
  fireEvent.click(detailButtons[0]);

  const detailPanel = await screen.findByRole("dialog", {
    name: "PT-20261018-001",
  });
  const locSelect = (await within(detailPanel).findByLabelText(
    "적치 위치 선택",
  )) as HTMLSelectElement;
  expect(locSelect.value).toBe("11");

  // 다른 NORMAL 위치(12: R-B02 보조 랙)로 수동 변경 후 적치 완료 제출
  await waitFor(() => {
    expect(
      within(locSelect).getByRole("option", { name: "R-B02 보조 랙" }),
    ).toBeInTheDocument();
  });
  fireEvent.change(locSelect, { target: { value: "12" } });
  fireEvent.click(
    within(detailPanel).getByRole("button", { name: "적치 완료" }),
  );

  await waitFor(() => {
    const calls = sent(fetcher, "POST", "/putaway-tasks/1/complete");
    expect(calls).toHaveLength(1);
    expect(body(calls[0])).toEqual({ toLocationId: 12 });
  });

  // 패널 닫고 두 번째 적치 작업(추천 위치 없음) 열기 -> 비어 있고 적치 취소 실행
  fireEvent.click(
    within(detailPanel).getByRole("button", { name: "패널 닫기" }),
  );
  fireEvent.click(detailButtons[1]);

  const detailPanel2 = await screen.findByRole("dialog", {
    name: "PT-20261018-002",
  });
  const locSelect2 = (await within(detailPanel2).findByLabelText(
    "적치 위치 선택",
  )) as HTMLSelectElement;
  expect(locSelect2.value).toBe("");
  expect(
    within(detailPanel2).getByRole("button", { name: "적치 완료" }),
  ).toBeDisabled();

  fireEvent.click(
    within(detailPanel2).getByRole("button", { name: "적치 취소" }),
  );
  await waitFor(() => {
    const cancelCalls = sent(fetcher, "POST", "/putaway-tasks/2/cancel");
    expect(cancelCalls).toHaveLength(1);
  });
});

it("W-12 피킹 지시 목록·필터·동선(sequenceNo) 명세·LOT 대체 사유·도착 위치 기본값 및 안내 검증", async () => {
  const pickOrders = [
    {
      id: 101,
      pickNo: "PK-20261018-001",
      reservationId: 10,
      reservationNo: "RV-20261018-001",
      reservationStatus: "ACTIVE",
      shipmentOrderRef: "SO-20261018-01",
      warehouseId: 1,
      warehouseCode: "WH-FG",
      warehouseName: "완제품 창고",
      status: "OPEN",
      pickedAt: null,
      stockDocumentId: null,
      stockDocumentNo: null,
      cancelReason: null,
      createdAt: "2026-10-18T11:00:00+09:00",
      lineCount: 2,
      totalQty: "50.000",
      totalPickedQty: null,
      lotSubstitutions: [
        {
          lineNo: 1,
          itemId: 21,
          itemCode: "FG-C100",
          requestedLotNo: "LOT-HELD-01",
          requestedLocationCode: "F-A01",
          requestedQty: "30.000",
          keptQty: "0.000",
          reason: "HOLD",
          reasonLabel: "보류(HOLD) 상태",
          allocatedLots: [
            {
              lotNo: "LOT-FEFO-02",
              locationCode: "F-B02",
              qty: "30.000",
            },
          ],
          message:
            "예약 LOT LOT-HELD-01이(가) 보류(HOLD) 상태여서 FEFO/FIFO 기준으로 LOT-FEFO-02(F-B02 · 30.000)을(를) 배정했습니다.",
        },
      ],
      // 의도적으로 역순(sequenceNo 2 -> 1)으로 넣어 화면에서 sequenceNo 오름차순 정렬되는지 검증
      lines: [
        {
          id: 1002,
          pickOrderId: 101,
          lineNo: 2,
          sequenceNo: 2,
          itemId: 21,
          itemCode: "FG-C100",
          itemName: "커넥터 C100",
          itemClass: "FG",
          baseUnit: "EA",
          lotTracked: true,
          locationId: 12,
          locationCode: "F-B02",
          locationName: "보조 랙",
          warehouseId: 1,
          warehouseCode: "WH-FG",
          warehouseName: "완제품 창고",
          lotNo: "LOT-FEFO-02",
          expiryDate: "2026-11-30",
          receivedOn: "2026-09-01",
          qty: "30.000",
          pickedQty: null,
          createdAt: "2026-10-18T11:00:00+09:00",
        },
        {
          id: 1001,
          pickOrderId: 101,
          lineNo: 1,
          sequenceNo: 1,
          itemId: 21,
          itemCode: "FG-C100",
          itemName: "커넥터 C100",
          itemClass: "FG",
          baseUnit: "EA",
          lotTracked: true,
          locationId: 11,
          locationCode: "F-A01",
          locationName: "기본 보관",
          warehouseId: 1,
          warehouseCode: "WH-FG",
          warehouseName: "완제품 창고",
          lotNo: "LOT-FEFO-01",
          expiryDate: "2026-10-31",
          receivedOn: "2026-08-15",
          qty: "20.000",
          pickedQty: null,
          createdAt: "2026-10-18T11:00:00+09:00",
        },
      ],
    },
    {
      id: 102,
      pickNo: "PK-20261018-002",
      reservationId: 11,
      reservationNo: "RV-20261018-002",
      reservationStatus: "ACTIVE",
      shipmentOrderRef: null,
      warehouseId: 2,
      warehouseCode: "WH-RAW",
      warehouseName: "원자재 창고",
      status: "OPEN",
      pickedAt: null,
      stockDocumentId: null,
      stockDocumentNo: null,
      cancelReason: null,
      createdAt: "2026-10-18T11:10:00+09:00",
      lineCount: 1,
      totalQty: "15.000",
      totalPickedQty: null,
      lotSubstitutions: [],
      lines: [
        {
          id: 1003,
          pickOrderId: 102,
          lineNo: 1,
          sequenceNo: 1,
          itemId: 31,
          itemCode: "RM-AL01",
          itemName: "알루미늄 바",
          itemClass: "RAW",
          baseUnit: "KG",
          lotTracked: false,
          locationId: 21,
          locationCode: "R-A01",
          locationName: "원자재 랙1",
          warehouseId: 2,
          warehouseCode: "WH-RAW",
          warehouseName: "원자재 창고",
          lotNo: null,
          expiryDate: null,
          receivedOn: "2026-09-10",
          qty: "15.000",
          pickedQty: null,
          createdAt: "2026-10-18T11:10:00+09:00",
        },
      ],
    },
  ];

  // WH-FG(id=1): SHIPPING 위치(F-SHIP, id=19) 있음
  const wh1Locations = [
    {
      id: 11,
      warehouseId: 1,
      warehouseCode: "WH-FG",
      code: "F-A01",
      name: "기본 보관",
      isDefault: true,
      isActive: true,
      moveCount: 2,
      locationType: "NORMAL",
    },
    {
      id: 12,
      warehouseId: 1,
      warehouseCode: "WH-FG",
      code: "F-B02",
      name: "보조 랙",
      isDefault: false,
      isActive: true,
      moveCount: 1,
      locationType: "NORMAL",
    },
    {
      id: 13,
      warehouseId: 1,
      warehouseCode: "WH-FG",
      code: "F-C03",
      name: "여유 랙",
      isDefault: false,
      isActive: true,
      moveCount: 0,
      locationType: "NORMAL",
    },
    {
      id: 19,
      warehouseId: 1,
      warehouseCode: "WH-FG",
      code: "F-SHIP",
      name: "완제품 출고장",
      isDefault: false,
      isActive: true,
      moveCount: 0,
      locationType: "SHIPPING",
    },
  ];

  // WH-RAW(id=2): SHIPPING 위치 없음 (NORMAL 위치만 존재)
  const wh2Locations = [
    {
      id: 21,
      warehouseId: 2,
      warehouseCode: "WH-RAW",
      code: "R-A01",
      name: "원자재 랙1",
      isDefault: true,
      isActive: true,
      moveCount: 1,
      locationType: "NORMAL",
    },
    {
      id: 22,
      warehouseId: 2,
      warehouseCode: "WH-RAW",
      code: "R-A02",
      name: "원자재 랙2",
      isDefault: false,
      isActive: true,
      moveCount: 0,
      locationType: "NORMAL",
    },
  ];

  const fetcher = mount("/wms/picks", {
    [`GET ${W}/warehouses`]: ok([
      {
        id: 1,
        code: "WH-FG",
        name: "완제품 창고",
        purpose: "FG",
        isActive: true,
        locationCount: 4,
      },
      {
        id: 2,
        code: "WH-RAW",
        name: "원자재 창고",
        purpose: "RAW",
        isActive: true,
        locationCount: 2,
      },
    ]),
    [`GET ${W}/items`]: ok([
      ...items,
      {
        id: 31,
        itemCode: "RM-AL01",
        name: "알루미늄 바",
        baseUnit: "KG",
        itemClass: "RAW",
        lotTracked: false,
        isActive: true,
        moveCount: 1,
        conversions: [],
      },
    ]),
    [`GET ${W}/reservations`]: ok({
      rows: [
        {
          id: 10,
          reservationNo: "RV-20261018-001",
          shipmentOrderRef: "SO-20261018-01",
          status: "ACTIVE",
        },
        {
          id: 11,
          reservationNo: "RV-20261018-002",
          shipmentOrderRef: null,
          status: "ACTIVE",
        },
      ],
      total: 2,
    }),
    [`GET ${W}/pick-orders`]: ok({
      rows: pickOrders,
      total: 2,
      page: 1,
      pageSize: 50,
    }),
    [`GET ${W}/warehouses/1/locations`]: ok(wh1Locations),
    [`GET ${W}/warehouses/2/locations`]: ok(wh2Locations),
  });

  expect(
    await screen.findByRole("heading", { name: "W-12 피킹" }),
  ).toBeVisible();

  const listTable = screen.getByRole("table", { name: "피킹 지시 목록" });
  expect(within(listTable).getByText("PK-20261018-001")).toBeVisible();
  expect(within(listTable).getByText("PK-20261018-002")).toBeVisible();
  expect(within(listTable).getByText("LOT 대체 1건")).toBeVisible();

  // 1. 첫 번째 지시(SHIPPING 칸 존재 + LOT 대체 1건) 상세 열기
  const detailBtns = within(listTable).getAllByRole("button", { name: "상세" });
  fireEvent.click(detailBtns[0]);

  const panel1 = await screen.findByRole("dialog", {
    name: "PK-20261018-001",
  });

  // LOT 대체 사유 안내 검증
  const subNote = within(panel1).getByRole("note", {
    name: "예약 LOT 대체 배정 안내",
  });
  expect(within(subNote).getByText("보류(HOLD)")).toBeVisible();
  expect(within(subNote).getByText("LOT-HELD-01")).toBeVisible();
  expect(within(subNote).getByText(/LOT-FEFO-02 \(F-B02 · 30\)/)).toBeVisible();

  // 피킹 동선 명세가 sequenceNo 오름차순(#1 F-A01 -> #2 F-B02)으로 표시되는지 확인
  const routeTable = within(panel1).getByRole("table", {
    name: "피킹 동선 명세",
  });
  const bodyRows = within(routeTable).getAllByRole("row").slice(1);
  expect(bodyRows).toHaveLength(2);
  expect(bodyRows[0]).toHaveTextContent("#1");
  expect(bodyRows[0]).toHaveTextContent("F-A01");
  expect(bodyRows[0]).toHaveTextContent("LOT-FEFO-01");
  expect(bodyRows[1]).toHaveTextContent("#2");
  expect(bodyRows[1]).toHaveTextContent("F-B02");
  expect(bodyRows[1]).toHaveTextContent("LOT-FEFO-02");

  // SHIPPING 칸(19: F-SHIP)이 기본 선택되고, 출고장 부재 안내 문구가 없어야 함
  const toLocSelect1 = (await within(panel1).findByLabelText(
    "도착 위치 선택",
  )) as HTMLSelectElement;
  await waitFor(() => {
    expect(toLocSelect1.value).toBe("19");
  });
  expect(
    within(panel1).queryByText(/출고장 칸이 없어 보관 칸으로 이동합니다/),
  ).toBeNull();
  // 출발 칸(11: F-A01, 12: F-B02)은 도착 위치 후보에서 제외되고 F-SHIP(19), F-C03(13)만 노출
  expect(
    within(toLocSelect1).queryByRole("option", { name: /F-A01/ }),
  ).toBeNull();
  expect(
    within(toLocSelect1).getByRole("option", {
      name: "F-SHIP 완제품 출고장 [출고장]",
    }),
  ).toBeInTheDocument();
  expect(
    within(toLocSelect1).getByRole("option", {
      name: "F-C03 여유 랙 [보관]",
    }),
  ).toBeInTheDocument();

  // D-3 범위: 피킹 확정 및 피킹 취소 버튼 노출
  const confirmBtn1 = within(panel1).getByRole("button", { name: "피킹 확정" });
  const cancelBtn1 = within(panel1).getByRole("button", { name: "피킹 취소" });
  expect(confirmBtn1).toBeInTheDocument();
  expect(confirmBtn1).toBeEnabled();
  expect(cancelBtn1).toBeInTheDocument();
  expect(cancelBtn1).toBeDisabled(); // 취소 사유 입력 전에는 비활성화

  // 2. 두 번째 지시(SHIPPING 칸 없음) 상세 열기 -> 빈 선택 + 안내 문구 노출
  fireEvent.click(within(panel1).getByRole("button", { name: "패널 닫기" }));
  fireEvent.click(detailBtns[1]);

  const panel2 = await screen.findByRole("dialog", {
    name: "PK-20261018-002",
  });
  expect(
    await within(panel2).findByText(
      "출고장 칸이 없어 보관 칸으로 이동합니다. W-06에서 출고장을 만들 수 있습니다.",
    ),
  ).toBeVisible();
  const toLocSelect2 = within(panel2).getByLabelText(
    "도착 위치 선택",
  ) as HTMLSelectElement;
  expect(toLocSelect2.value).toBe("");
  expect(
    within(toLocSelect2).getByRole("option", {
      name: "R-A02 원자재 랙2 [보관]",
    }),
  ).toBeInTheDocument();

  // 3. 서버 필터 변경 시 쿼리 파라미터 반영 검증
  fireEvent.change(screen.getByLabelText("상태 필터"), {
    target: { value: "OPEN" },
  });
  await waitFor(() => {
    const pickCalls = fetcher.mock.calls.filter(([u]) =>
      String(u).includes("/pick-orders?"),
    );
    expect(pickCalls.some(([u]) => String(u).includes("status=OPEN"))).toBe(
      true,
    );
  });
});
