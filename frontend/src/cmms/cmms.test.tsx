// CMMS-1c 화면 — C-05 설비 대장(계층·가져오기)·C-09 고장 코드.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const C = "/api/v1/cmms";
type Reply = { status: number; body?: unknown };
const ok = (data: unknown, status = 200): Reply => ({ status, body: { data } });
const fail = (
  status: number,
  code: string,
  details: unknown,
  message = "요청을 처리할 수 없습니다.",
): Reply => ({
  status,
  body: { error: { code, message, details } },
});

function mount(path: string, replies: Record<string, Reply> = {}) {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input).split("?")[0];
      const query = String(input).includes("source=BEMS") ? ":BEMS" : "";
      const reply =
        replies[`${init?.method ?? "GET"} ${url}${query}`] ??
        replies[`${init?.method ?? "GET"} ${url}`];
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

const node = (
  id: number,
  code: string,
  depth: number,
  extra: Record<string, unknown> = {},
) => ({
  id,
  code,
  name: `${code} 설비`,
  assetType: "INJECTION",
  location: null,
  source: "CMMS",
  sourceCode: null,
  parentAssetId: null,
  criticality: null,
  isActive: true,
  depth,
  ...extra,
});

it("C-05 설비 대장: 계층을 들여 쓰고 출처를 보여 준다", async () => {
  mount("/cmms/assets", {
    [`GET ${C}/assets/tree`]: ok([
      node(1, "LINE-A", 0, { assetType: "LINE" }),
      node(2, "INJ-A1", 1, { parentAssetId: 1, criticality: "A" }),
      node(3, "HV-01", 0, {
        assetType: "HVAC",
        source: "BEMS",
        sourceCode: "HV-01",
        location: "사무동",
      }),
    ]),
  });
  expect(await screen.findByRole("button", { name: "LINE-A" })).toBeVisible();
  expect(screen.getByText("라인")).toBeVisible();
  expect(screen.getByText("BEMS 공조기")).toBeVisible();
  // 하위 설비는 들여쓰기로 계층을 나타낸다.
  const child = screen.getByRole("button", { name: "INJ-A1" }).parentElement!;
  expect(child).toHaveStyle({ paddingLeft: "16px" });
  expect(screen.getByText("A")).toBeVisible();
});

it("C-05 가져오기: 고른 원천 코드만 보내고, 원천이 꺼져 있으면 안내한다", async () => {
  const fetcher = mount("/cmms/assets", {
    [`GET ${C}/assets/tree`]: ok([]),
    [`GET ${C}/assets/import-candidates`]: ok([
      {
        sourceCode: "INJ-01",
        name: "사출기 1",
        assetType: "INJECTION",
        location: "1층",
      },
      {
        sourceCode: "INJ-02",
        name: "사출기 2",
        assetType: "INJECTION",
        location: "1층",
      },
    ]),
    [`GET ${C}/assets/import-candidates:BEMS`]: fail(
      409,
      "PRECONDITION_NOT_MET",
      { reason: "SOURCE_MODULE_DISABLED", sourceModule: "bems" },
      "BEMS를 사용하지 않도록 설정했습니다. 설비를 직접 등록할 수는 있습니다.",
    ),
    [`POST ${C}/assets/import`]: ok({ created: 1, skipped: [], ids: [9] }, 201),
  });
  fireEvent.click(await screen.findByRole("button", { name: "가져오기" }));
  expect(await screen.findByLabelText(/INJ-01/)).toBeInTheDocument();
  // 아무것도 고르지 않으면 보낼 수 없다.
  expect(screen.getByRole("button", { name: "대장에 넣기" })).toBeDisabled();
  fireEvent.click(screen.getByLabelText(/INJ-02/));
  fireEvent.click(screen.getByRole("button", { name: "1건 대장에 넣기" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/assets/import")).toHaveLength(1),
  );
  expect(body(sent(fetcher, "POST", "/assets/import")[0])).toEqual({
    source: "MES",
    sourceCodes: ["INJ-02"],
  });

  fireEvent.change(screen.getByLabelText("원천"), {
    target: { value: "BEMS" },
  });
  expect(await screen.findByText(/사용하지 않도록 설정했습니다/)).toBeVisible();
});

it("C-05 가져온 설비는 코드·이름·종류를 바꿀 수 없다", async () => {
  mount("/cmms/assets", {
    [`GET ${C}/assets/tree`]: ok([
      node(3, "HV-01", 0, {
        assetType: "HVAC",
        source: "BEMS",
        sourceCode: "HV-01",
      }),
    ]),
    [`GET ${C}/assets/3`]: ok({
      ...node(3, "HV-01", 0, {
        assetType: "HVAC",
        source: "BEMS",
        sourceCode: "HV-01",
      }),
      manufacturer: null,
      model: null,
      serialNo: null,
      installedOn: null,
      acquisitionCost: null,
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "HV-01" }));
  expect(await screen.findByText(/원천에서 가져온 설비라/)).toBeVisible();
  expect(screen.getByLabelText("설비명")).toBeDisabled();
  expect(screen.getByLabelText("종류")).toBeDisabled();
  // 상세·중요도·계층은 CMMS에서 정하므로 열려 있다.
  expect(screen.getByLabelText("제조사")).toBeEnabled();
  expect(screen.getByLabelText("중요도")).toBeEnabled();
});

it("C-09 고장 코드: 구분과 원인 분류를 함께 보낸다", async () => {
  const fetcher = mount("/cmms/failure-codes", {
    [`GET ${C}/failure-codes`]: ok([
      {
        id: 1,
        kind: "CAUSE",
        code: "BEARING",
        name: "베어링 마모",
        causeCategory: "WEAR",
        isActive: true,
      },
    ]),
    [`POST ${C}/failure-codes`]: ok({ id: 2 }, 201),
  });
  expect(await screen.findByText("베어링 마모")).toBeVisible();
  expect(screen.getByText("마모")).toBeVisible();
  expect(screen.getByText("원인")).toBeVisible();

  fireEvent.click(screen.getByRole("button", { name: "고장 코드 등록" }));
  fireEvent.change(screen.getByLabelText("구분"), {
    target: { value: "CAUSE" },
  });
  fireEvent.change(screen.getByLabelText("코드"), {
    target: { value: "LOOSE" },
  });
  fireEvent.change(screen.getByLabelText("이름"), {
    target: { value: "체결 풀림" },
  });
  fireEvent.change(screen.getByLabelText("원인 분류"), {
    target: { value: "SETTING" },
  });
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/failure-codes")).toHaveLength(1),
  );
  const saved = body(sent(fetcher, "POST", "/failure-codes")[0]);
  expect(saved.kind).toBe("CAUSE");
  expect(saved.causeCategory).toBe("SETTING");
});

const order = (extra: Record<string, unknown> = {}) => ({
  id: 7,
  woNo: "WO-0001",
  assetId: 1,
  assetCode: "PRESS-01",
  assetName: "프레스 1호",
  assetType: "OTHER",
  kind: "BM",
  source: "MANUAL",
  sourceRef: null,
  sourceSummary: null,
  dueOn: null,
  title: "이상 소음",
  description: null,
  status: "IN_PROGRESS",
  requestedAt: "2026-10-20T09:00:00+09:00",
  failureAt: "2026-10-20T08:50:00+09:00",
  startedAt: "2026-10-20T09:10:00+09:00",
  completedAt: null,
  restoredAt: null,
  causeCategory: null,
  action: null,
  cancelledAt: null,
  cancelReason: null,
  technicianId: 3,
  technicianName: "김보전",
  vendorId: null,
  vendorName: null,
  externalCost: null,
  symptomCodeId: null,
  symptomCode: null,
  symptomName: null,
  actionCodeId: null,
  actionCode: null,
  actionName: null,
  ...extra,
});

it("C-03 작업지시: 진행 중에는 작업 기록과 완료 폼이 함께 보이고 합계를 알려 준다", async () => {
  const fetcher = mount("/cmms/work-orders", {
    [`GET ${C}/work-orders`]: ok([order()]),
    [`GET ${C}/work-orders/7`]: ok({
      ...order(),
      logs: [
        {
          id: 1,
          loggedAt: "2026-10-20T09:20:00+09:00",
          minutes: 40,
          note: "호스 교체",
          technicianId: 3,
          technicianName: "김보전",
        },
        {
          id: 2,
          loggedAt: "2026-10-20T10:00:00+09:00",
          minutes: 35,
          note: null,
          technicianId: 3,
          technicianName: "김보전",
        },
      ],
    }),
    [`GET ${C}/assets/tree`]: ok([]),
    [`POST ${C}/work-orders/7/complete`]: ok(order({ status: "COMPLETED" })),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  // 40 + 35 = 75분 → 1시간 15분
  expect(await screen.findByText(/합계 1시간 15분/)).toBeVisible();
  fireEvent.change(screen.getByLabelText("원인 분류"), {
    target: { value: "LUBRICATION" },
  });
  fireEvent.change(screen.getByLabelText("조치 내용"), {
    target: { value: "그리스 주입" },
  });
  fireEvent.click(screen.getByRole("button", { name: "완료 처리" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/work-orders/7/complete")).toHaveLength(1),
  );
  const saved = body(sent(fetcher, "POST", "/work-orders/7/complete")[0]);
  expect(saved.causeCategory).toBe("LUBRICATION");
  expect(saved.action).toBe("그리스 주입");
  expect(saved.vendorId).toBeNull();
});

it("C-03 외주 비용 칸은 업체를 고를 때만 나온다", async () => {
  mount("/cmms/work-orders", {
    [`GET ${C}/work-orders`]: ok([order()]),
    [`GET ${C}/work-orders/7`]: ok({ ...order(), logs: [] }),
    [`GET ${C}/assets/tree`]: ok([]),
    [`GET ${C}/vendors`]: ok([
      {
        id: 5,
        code: "V-01",
        name: "한빛정비",
        erpPartnerCode: null,
        phone: null,
        isActive: true,
      },
    ]),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(await screen.findByLabelText("조치 내용")).toBeVisible();
  expect(screen.queryByLabelText("외주 비용")).toBeNull();
  fireEvent.change(await screen.findByLabelText("외주 업체(선택)"), {
    target: { value: "5" },
  });
  expect(screen.getByLabelText("외주 비용")).toBeVisible();
});

it("C-02 전환 대기 신호: 추천 설비를 기본값으로 두고 원천을 바꾸지 않는다고 알린다", async () => {
  const fetcher = mount("/cmms/signals", {
    [`GET ${C}/signals`]: ok({
      sources: { bems: true, spc: false },
      signals: [
        {
          id: "BEMS_ALARM:11",
          source: "BEMS_ALARM",
          sourceRef: "11",
          summary: "사무동 TEMP 상한 28 초과(최고 31.2)",
          severity: "CRITICAL",
          detectedAt: "2026-10-20T08:00:00+09:00",
          suggestedAssetId: 4,
          suggestedAssetCode: "AHU-OFF",
        },
      ],
    }),
    [`GET ${C}/assets/tree`]: ok([
      node(2, "PRESS-01", 0),
      node(4, "AHU-OFF", 0, { assetType: "HVAC", source: "BEMS" }),
    ]),
    [`POST ${C}/signals/convert`]: ok(
      order({ id: 9, woNo: "WO-0009", source: "BEMS_ALARM" }),
      201,
    ),
  });
  expect(await screen.findByText(/원천 상태는 바뀌지 않습니다/)).toBeVisible();
  // SPC를 꺼 두면 그 줄만 빠진다고 알린다(조회가 끝나야 안다).
  expect(await screen.findByText(/SPC를 사용하지 않도록 설정해/)).toBeVisible();
  expect(screen.getByText("심각")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "작업지시로" }));
  // 경보 구역의 공조기가 기본으로 잡힌다.
  expect(await screen.findByLabelText("작업할 설비")).toHaveValue("4");
  fireEvent.click(screen.getByRole("button", { name: "전환" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/signals/convert")).toHaveLength(1),
  );
  expect(body(sent(fetcher, "POST", "/signals/convert")[0])).toMatchObject({
    source: "BEMS_ALARM",
    sourceRef: "11",
    assetId: 4,
  });
  expect(
    await screen.findByText(/WO-0009 작업지시를 만들었습니다/),
  ).toBeVisible();
});

it("C-08 정비원·외주 업체는 탭으로 나뉜다", async () => {
  mount("/cmms/technicians", {
    [`GET ${C}/technicians`]: ok([
      {
        id: 3,
        code: "T-01",
        name: "김보전",
        skill: "MECHANICAL",
        hourlyRate: "30000.00",
        currency: "KRW",
        hrEmployeeCode: null,
        isActive: true,
      },
    ]),
    [`GET ${C}/vendors`]: ok([
      {
        id: 5,
        code: "V-01",
        name: "한빛정비",
        erpPartnerCode: null,
        phone: "02-000-0000",
        isActive: true,
      },
    ]),
  });
  expect(await screen.findByText("김보전")).toBeVisible();
  expect(screen.getByText("30,000원")).toBeVisible();
  expect(screen.getByText("기계")).toBeVisible();
  fireEvent.click(screen.getByRole("tab", { name: "외주 업체" }));
  expect(await screen.findByText("한빛정비")).toBeVisible();
});

const plan = (extra: Record<string, unknown> = {}) => ({
  id: 3,
  assetId: 1,
  assetCode: "PRESS-01",
  assetName: "프레스 1호",
  assetSource: "CMMS",
  assetSourceCode: null,
  code: "PM-01",
  title: "월간 점검",
  checklist: "",
  triggerKind: "CALENDAR",
  intervalDays: 30,
  intervalUsage: null,
  startOn: "2026-08-01",
  lastDoneOn: null,
  lastDoneUsage: null,
  isActive: true,
  dueOn: "2026-08-31",
  isDue: true,
  usageNow: null,
  usageSinceLast: null,
  unknown: false,
  ...extra,
});

it("C-04 계획: 사용량 기준은 MES를 끄면 '모름'이라 작업지시를 만들 수 없다", async () => {
  mount("/cmms/pm-plans", {
    [`GET ${C}/pm-plans`]: ok([
      plan(),
      plan({
        id: 4,
        code: "PM-RH",
        triggerKind: "RUN_HOURS",
        intervalDays: null,
        intervalUsage: "100.00",
        dueOn: null,
        isDue: false,
        unknown: true,
        assetSourceCode: "INJ-01",
      }),
    ]),
    [`GET ${C}/assets/tree`]: ok([node(1, "PRESS-01", 0)]),
    [`GET ${C}/pm-plans/4`]: ok(
      plan({
        id: 4,
        code: "PM-RH",
        triggerKind: "RUN_HOURS",
        intervalDays: null,
        intervalUsage: "100.00",
        dueOn: null,
        isDue: false,
        unknown: true,
        items: [],
      }),
    ),
  });
  expect(await screen.findByText("모름(MES 꺼짐)")).toBeVisible();
  const rows = screen.getAllByRole("row");
  expect(rows.find((r) => r.textContent?.includes("PM-01"))).toHaveTextContent(
    "도래",
  );
  fireEvent.click(screen.getAllByRole("button", { name: "상세" })[1]);
  expect(await screen.findByText(/사용량을 읽을 수 없습니다/)).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "PM 작업지시 만들기" }),
  ).toBeNull();
});

it("C-04 점검 항목: 측정값 범위를 고르면 상·하한과 단위를 받는다", async () => {
  const fetcher = mount("/cmms/pm-plans", {
    [`GET ${C}/pm-plans`]: ok([plan()]),
    [`GET ${C}/assets/tree`]: ok([node(1, "PRESS-01", 0)]),
    [`GET ${C}/pm-plans/3`]: ok(plan({ items: [] })),
    [`POST ${C}/pm-plans/3/items`]: ok({ items: [] }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(await screen.findByLabelText("항목 이름")).toBeVisible();
  expect(screen.getByLabelText("기준(선택)")).toBeVisible();
  fireEvent.change(screen.getByLabelText("판정 방법"), {
    target: { value: "RANGE" },
  });
  expect(screen.queryByLabelText("기준(선택)")).toBeNull();
  fireEvent.change(screen.getByLabelText("항목 이름"), {
    target: { value: "유압" },
  });
  fireEvent.change(screen.getByLabelText("하한(선택)"), {
    target: { value: "80" },
  });
  fireEvent.change(screen.getByLabelText("단위"), { target: { value: "bar" } });
  fireEvent.click(screen.getByRole("button", { name: "항목 추가" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/pm-plans/3/items")).toHaveLength(1),
  );
  expect(body(sent(fetcher, "POST", "/pm-plans/3/items")[0])).toMatchObject({
    name: "유압",
    method: "RANGE",
    lowerLimit: "80",
    unit: "bar",
  });
});

it("C-06 예비품: WMS를 잇지 않으면 재고가 0이 아니라 '모름'이다", async () => {
  mount("/cmms/spare-parts", {
    [`GET ${C}/spare-parts`]: ok([
      {
        id: 1,
        code: "SP-01",
        name: "오링",
        unit: "EA",
        safetyStock: "5.000",
        itemCode: null,
        unitCost: null,
        isActive: true,
        stock: null,
        stockKnown: false,
      },
      {
        id: 2,
        code: "SP-02",
        name: "필터",
        unit: "EA",
        safetyStock: "0.000",
        itemCode: "SUP-100",
        unitCost: "1200.0000",
        isActive: true,
        stock: {
          qtyOnHand: "3.000",
          unit: "EA",
          safetyStock: "10.000",
          isShort: true,
        },
        stockKnown: true,
      },
    ]),
  });
  expect(await screen.findByText("오링")).toBeVisible();
  expect(screen.getByText("모름")).toBeVisible();
  expect(screen.getByText("연결 안 됨")).toBeVisible();
  expect(screen.getByText("부족")).toBeVisible();
  expect(screen.getByText("1,200원")).toBeVisible();
});

it("C-07 지표: 고장이 0건이면 0이 아니라 '고장 없음'으로 알린다", async () => {
  mount("/cmms/metrics", {
    [`GET ${C}/metrics`]: ok({
      from: "2026-07-01",
      to: "2026-09-24",
      periodHours: "2040.0",
      failures: 0,
      downtime: "0",
      mttr: null,
      mtbf: null,
      pmTotal: 0,
      pmKept: 0,
      pmRate: null,
      byAsset: [],
      pareto: [],
    }),
  });
  expect(await screen.findByText(/완료된 고장 작업지시가 없어/)).toBeVisible();
  expect(screen.getByLabelText("MTBF")).toHaveTextContent("—");
  expect(screen.getByLabelText("PM 준수율")).toHaveTextContent(
    "이 기간에 예정된 PM이 없습니다",
  );
});

it("C-07 지표: 고장이 있으면 설비별·파레토를 보여 주고 유예 없음을 알린다", async () => {
  mount("/cmms/metrics", {
    [`GET ${C}/metrics`]: ok({
      from: "2026-07-01",
      to: "2026-09-24",
      periodHours: "2040.0",
      failures: 2,
      downtime: "6.0",
      mttr: "3.0",
      mtbf: "1017.0",
      pmTotal: 4,
      pmKept: 3,
      pmRate: "75.0",
      byAsset: [
        {
          id: "INJ-02",
          assetCode: "INJ-02",
          assetName: "사출기 2호",
          failures: 2,
          downtime: "6.0",
          mttr: "3.0",
        },
      ],
      pareto: [{ id: "CAUSE:WEAR", kind: "CAUSE", name: "WEAR", count: 2 }],
    }),
  });
  expect(await screen.findByLabelText("MTTR")).toHaveTextContent("3시간");
  expect(screen.getByLabelText("PM 준수율")).toHaveTextContent("75.0%");
  expect(screen.getByText("3/4건 예정일 안에 완료")).toBeVisible();
  expect(screen.getByText("사출기 2호", { exact: false })).toBeVisible();
  expect(screen.getByText("유예 없음")).toBeVisible();
  // 원인 코드는 사람이 읽는 이름으로 바꿔 보여 준다.
  expect(screen.getByText("마모")).toBeVisible();
});

it("C-10 비용: 설비별·월별로 바꿔 볼 수 있다", async () => {
  const row = {
    id: "INJ-02",
    group: "INJ-02",
    label: "사출기 2호",
    orderCount: 2,
    bmCount: 1,
    pmCount: 1,
    partCost: "3600",
    laborCost: "60000",
    externalCost: "50000",
    totalCost: "113600",
  };
  mount("/cmms/cost", {
    [`GET ${C}/cost`]: ok({
      from: "2026-04-01",
      to: "2026-09-24",
      orderCount: 2,
      partCost: "3600",
      laborCost: "60000",
      externalCost: "50000",
      totalCost: "113600",
      byAsset: [row],
      byMonth: [{ ...row, id: "2026-09", group: "2026-09", label: "2026-09" }],
    }),
  });
  expect(await screen.findByLabelText("합계")).toHaveTextContent("113,600원");
  expect(screen.getByLabelText("인건비")).toHaveTextContent("60,000원");
  expect(screen.getByText("2건 (고장 1 · 예방 1)")).toBeVisible();
  expect(screen.getByText("INJ-02")).toBeVisible();
  fireEvent.change(screen.getByLabelText("기준"), {
    target: { value: "month" },
  });
  expect(await screen.findByText("2026-09")).toBeVisible();
});

it("C-01 개요: 원천이 꺼지면 어느 쪽인지 알리고 모르는 PM 수를 따로 센다", async () => {
  mount("/cmms/overview", {
    [`GET ${C}/overview`]: ok({
      today: "2026-09-24",
      assetCount: 5,
      criticalCount: 1,
      requested: 2,
      inProgress: 1,
      openBm: 3,
      pendingSignals: 1,
      sources: { bems: true, spc: false },
      duePlans: [
        {
          id: 1,
          code: "PM-01",
          title: "월간 점검",
          assetCode: "INJ-02",
          dueOn: "2026-09-20",
        },
      ],
      unknownPlans: 2,
      shortParts: [
        {
          id: 1,
          code: "SP-01",
          name: "오링",
          qtyOnHand: "3.000",
          safetyStock: "10.000",
          unit: "EA",
        },
      ],
    }),
  });
  expect(await screen.findByLabelText("미조치 작업지시")).toHaveTextContent(
    "2건",
  );
  expect(screen.getByLabelText("전환 대기 신호")).toHaveTextContent("SPC 꺼짐");
  expect(screen.getByLabelText("주기 도래 PM")).toHaveTextContent(
    "2건은 MES 꺼짐으로 판정 불가",
  );
  expect(screen.getByText("PM-01")).toBeVisible();
  expect(screen.getByText("3 / 10 EA")).toBeVisible();
});
