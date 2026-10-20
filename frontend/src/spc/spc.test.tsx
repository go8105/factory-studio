// FS-028b SPC 화면 (화면 설계 6장 단위 검증). 검증 항목별로 테스트를 나눈다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const P = "/api/v1/spc";
type Reply = { status: number; body?: unknown };
const ok = (data: unknown, status = 200): Reply => ({ status, body: { data } });
const fail = (status: number, code: string, details: unknown): Reply => ({
  status,
  body: { error: { code, message: "요청을 처리할 수 없습니다.", details } },
});

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

const ch = {
  id: 7,
  code: "CH-C200-INJ-H",
  itemCode: "FG-C200",
  itemName: "커넥터 C200",
  processCode: "INJ",
  name: "하우징 높이",
  unit: "mm",
  lsl: "11.9000",
  usl: "12.1000",
  target: "12.0000",
  subgroupSize: 5,
  decimals: 3,
  isActive: true,
  chartType: "XBAR_R" as const,
  defectSource: null,
  rules: [] as number[],
  subgroupCount: 30,
  limitVersion: 2,
  openSignals: 1,
};
const limit = (version: number, effectiveAt: string) => ({
  id: version,
  characteristicId: 7,
  version,
  effectiveAt,
  basisFrom: "2026-09-01T00:00:00+09:00",
  basisTo: effectiveAt,
  basisCount: 20,
  xbarCl: "12.000000",
  xbarUcl: "12.040000",
  xbarLcl: "11.960000",
  rCl: "0.030000",
  rUcl: "0.063000",
  rLcl: "0.000000",
  reason: "초기 한계",
  publishedAt: effectiveAt,
});
const point = (
  id: number,
  at: string,
  xbar: string,
  extra: Record<string, unknown> = {},
) => ({
  id,
  lotNo: `LT-00${10 + id}`,
  equipmentCode: "INJ-02",
  measuredAt: at,
  xbar,
  r: "0.030000",
  status: "valid",
  limitVersion: 1,
  signals: [],
  ...extra,
});
const chart = {
  characteristic: ch,
  limits: [
    limit(1, "2026-09-05T00:00:00+09:00"),
    limit(2, "2026-09-10T00:00:00+09:00"),
  ],
  points: [
    point(1, "2026-09-03T06:00:00+09:00", "12.001", { limitVersion: null }),
    point(2, "2026-09-06T06:00:00+09:00", "12.010"),
    point(3, "2026-09-07T06:00:00+09:00", "12.020", { status: "void" }),
    point(4, "2026-09-11T06:00:00+09:00", "12.052", {
      limitVersion: 2,
      signals: [
        { id: 41, subgroupId: 4, chart: "XBAR", rule: 1, status: "open" },
      ],
    }),
  ],
};

it("S-02 관리도: 이상·무효·정상 점, 버전 경계, 값 표의 판정", async () => {
  mount("/spc/chart?c=7", {
    [`GET ${P}/characteristics`]: ok([ch]),
    [`GET ${P}/characteristics/7/chart`]: ok(chart),
  });
  const xbar = await screen.findByRole("figure", { name: "X̄ 관리도" });
  expect(xbar.querySelectorAll(".spc-signal")).toHaveLength(1);
  expect(xbar.querySelectorAll(".spc-void")).toHaveLength(1);
  expect(xbar.querySelectorAll(".marker")).toHaveLength(2);
  expect(xbar.textContent).toContain("v2 적용");
  // 이상 점은 키보드로 이상 상세에 갈 수 있다.
  expect(
    screen.getAllByRole("button", { name: /규칙 1 · 한계 밖\(미조치\)/ }),
  ).toHaveLength(1);
  expect(
    screen.getByRole("link", { name: /규칙 1 · 한계 밖 · 미조치/ }),
  ).toHaveAttribute("href", "/spc/signals?c=7&signal=41");
  expect(screen.getAllByText("미게시").length).toBeGreaterThan(0);
  expect(screen.getByText("무효")).toBeVisible();
});

it("S-03 공정능력: 표본 부족은 계산하지 않고, 한쪽 규격은 Cp를 비운다", async () => {
  const f = mount("/spc/capability?c=7", {
    [`GET ${P}/characteristics`]: ok([ch]),
    [`GET ${P}/characteristics/7/capability`]: ok({
      characteristic: ch,
      subgroupCount: 12,
      minimum: 20,
      openSignals: 0,
      insufficient: true,
    }),
  });
  expect(
    await screen.findByText(
      "유효 부분군이 20개 이상이어야 계산합니다(현재 12개).",
    ),
  ).toBeVisible();
  f.mockRestore();
  mount("/spc/capability?c=7", {
    [`GET ${P}/characteristics`]: ok([{ ...ch, lsl: null }]),
    [`GET ${P}/characteristics/7/capability`]: ok({
      characteristic: { ...ch, lsl: null },
      subgroupCount: 30,
      minimum: 20,
      openSignals: 2,
      insufficient: false,
      mu: "12.021000",
      sigma: "0.022500",
      cp: null,
      cpk: "1.170000",
      judgement: "MARGINAL",
      histogram: [
        { from: "11.98", to: "12.00", count: 40 },
        { from: "12.00", to: "12.06", count: 110 },
      ],
    }),
  });
  expect(await screen.findByText("한쪽 규격 — 계산 안 함")).toBeVisible();
  expect(screen.getByText("주의")).toBeVisible();
  expect(screen.getByRole("note")).toHaveTextContent("미조치 이상이 2건");
});

const runs = [
  {
    lotNo: "LT-0023",
    itemCode: "FG-C200",
    processCode: "INJ",
    equipmentCode: "INJ-02",
    startedAt: "2026-09-23T00:00:00+09:00",
    endedAt: null,
    subgroupCount: 4,
  },
];

it("S-04 측정 입력: 입력 중 X̄·R, 규격 밖 표시, 측정 시각 오류는 칸 아래", async () => {
  const f = mount("/spc/measure?c=7", {
    [`GET ${P}/characteristics`]: ok([ch]),
    [`GET ${P}/runs`]: ok(runs),
    [`POST ${P}/subgroups`]: fail(400, "VALIDATION_FAILED", {
      fields: {
        measuredAt: "이 특성의 마지막 부분군(09-23 06:00)보다 늦어야 합니다.",
      },
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "측정 입력" }));
  const values = ["12.01", "12.02", "12.03", "12.00", "12.20"];
  values.forEach((v, i) =>
    fireEvent.change(screen.getByLabelText(`값 ${i + 1}`), {
      target: { value: v },
    }),
  );
  expect(screen.getByText("X̄ 12.0520 · R 0.2000")).toBeVisible();
  expect(screen.getByText("규격 밖")).toBeVisible();
  fireEvent.change(screen.getByLabelText("측정 시각"), {
    target: { value: "2026-09-23T05:00" },
  });
  fireEvent.click(screen.getByRole("button", { name: "기록" }));
  expect(await screen.findByText(/마지막 부분군\(09-23 06:00\)/)).toBeVisible();
  const call = sent(f, "POST", "/subgroups")[0];
  expect(body(call)).toMatchObject({
    characteristicId: 7,
    lotNo: "LT-0023",
    measuredAt: "2026-09-23T05:00:00+09:00",
    values,
  });
});

it("S-04: MES를 끄면 측정 입력만 안내하고 관리도로 보낸다", async () => {
  mount("/spc/measure?c=7", {
    [`GET ${P}/characteristics`]: ok([ch]),
    [`GET ${P}/runs`]: fail(409, "PRECONDITION_NOT_MET", {
      reason: "SOURCE_MODULE_DISABLED",
      sourceModule: "mes",
    }),
  });
  expect(
    await screen.findByText(/MES를 사용하지 않도록 설정했습니다/),
  ).toBeVisible();
  expect(screen.getByRole("link", { name: /관리도로/ })).toHaveAttribute(
    "href",
    "/spc/chart?c=7",
  );
});

const signal = {
  id: 41,
  subgroupId: 4,
  characteristicId: 7,
  characteristicCode: "CH-C200-INJ-H",
  itemCode: "FG-C200",
  processCode: "INJ",
  characteristicName: "하우징 높이",
  lotNo: "LT-0017",
  equipmentCode: "INJ-02",
  chart: "XBAR",
  rule: 3,
  value: "12.030000",
  detectedAt: "2026-09-11T06:00:00+09:00",
  status: "open",
  causeCategory: null,
  action: null,
  resolvedAt: null,
  voidedAt: null,
  limitVersion: 1,
};

it("S-05 이상·조치: 규칙 설명과 원인·조치를 보내 조치 완료", async () => {
  const f = mount("/spc/signals?signal=41", {
    [`GET ${P}/signals`]: ok([signal]),
    [`GET ${P}/characteristics/7/chart`]: ok(chart),
    // 점검 항목이 없으면 점검표가 뜨지 않고 지금까지처럼 바로 조치할 수 있다.
    [`GET ${P}/signals/41/ocap`]: ok({
      signalId: 41,
      status: "open",
      items: [],
      missing: [],
    }),
    [`POST ${P}/signals/41/resolve`]: ok({
      ...signal,
      status: "resolved",
      causeCategory: "MACHINE",
      action: "금형 온도 조정",
      resolvedAt: "2026-09-12T09:00:00+09:00",
    }),
  });
  expect(
    await screen.findByText(/연속 6점 증가 또는 감소했습니다/),
  ).toBeVisible();
  fireEvent.change(screen.getByLabelText("조치 내용"), {
    target: { value: "금형 온도 조정" },
  });
  fireEvent.click(screen.getByRole("button", { name: "조치 완료" }));
  await waitFor(() =>
    expect(sent(f, "POST", "/signals/41/resolve")).toHaveLength(1),
  );
  expect(body(sent(f, "POST", "/signals/41/resolve")[0])).toEqual({
    causeCategory: "MACHINE",
    action: "금형 온도 조정",
  });
  expect(await screen.findByText(/조치 금형 온도 조정/)).toBeVisible();
});

it("S-07 한계 게시: 미리 계산이 20개 미만이면 게시 버튼이 꺼진다", async () => {
  mount("/spc/characteristics?c=7", {
    [`GET ${P}/characteristics`]: ok([ch]),
    [`GET ${P}/lookups/items`]: ok([
      { itemCode: "FG-C200", name: "커넥터 C200" },
    ]),
    [`GET ${P}/characteristics/7/limits`]: ok([
      limit(1, "2026-09-05T00:00:00+09:00"),
    ]),
    [`GET ${P}/characteristics/7/limits/preview`]: ok({
      basisCount: 12,
      minimum: 20,
    }),
  });
  expect(await screen.findByText("관리 한계 버전")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("기준 구간 시작"), {
    target: { value: "2026-09-01T00:00" },
  });
  fireEvent.click(screen.getByRole("button", { name: "미리 계산" }));
  expect(
    await screen.findByText(/유효 부분군 12개 — 20개 이상 필요/),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: "게시" })).toBeDisabled();
});

it("QMS 검사 대기: SPC 이상 배지는 true일 때만, null(꺼짐)이면 없다", async () => {
  const lot = (lotNo: string, spcSignal: boolean | null) => ({
    lotNo,
    itemCode: "FG-C200",
    itemName: "커넥터 C200",
    finalGoodQty: "500",
    unit: "EA",
    completedAt: "2026-09-10T00:00:00+09:00",
    status: "pending",
    draftInspectionId: null,
    latestResult: null,
    hasSpec: true,
    spcSignal,
  });
  mount("/qms/pending", {
    "GET /api/v1/qms/lookups/mes-lots": ok([
      lot("LT-0017", true),
      lot("LT-0014", false),
      lot("LT-0011", null),
    ]),
  });
  expect(await screen.findByText("LT-0017")).toBeVisible();
  expect(screen.getAllByText("SPC 이상")).toHaveLength(1);
});

const violation = (id: number, side: "LOW" | "HIGH", extra = {}) => ({
  id,
  subgroupId: id,
  characteristicId: 7,
  characteristicCode: ch.code,
  characteristicName: ch.name,
  itemCode: ch.itemCode,
  itemName: ch.itemName,
  processCode: ch.processCode,
  unit: "mm",
  seq: 1,
  lotNo: "LT-0023",
  equipmentCode: "INJ-02",
  value: side === "HIGH" ? "12.150000" : "11.880000",
  side,
  limitValue: side === "HIGH" ? "12.100000" : "11.900000",
  detectedAt: "2026-09-11T06:00:00+09:00",
  voidedAt: null,
  status: "open",
  ...extra,
});

it("S-08 규격 이탈: 방향·한계를 보여 주고 처음에는 유효한 것만 조회한다", async () => {
  const fetcher = mount("/spc/violations", {
    [`GET ${P}/characteristics`]: ok([ch]),
    [`GET ${P}/spec-violations`]: ok([
      violation(1, "HIGH"),
      violation(2, "LOW"),
    ]),
  });
  expect(await screen.findByText("상한 초과")).toBeVisible();
  expect(screen.getByText("하한 미만")).toBeVisible();
  expect(screen.getAllByText("12.1500 mm")).toHaveLength(1);
  const [first] = sent(fetcher, "GET", "/spec-violations");
  expect(String(first[0])).toContain("status=open");
});

it("S-07 관리 특성: I-MR을 고르면 부분군 크기 칸이 사라지고 1로 저장된다", async () => {
  const fetcher = mount("/spc/characteristics", {
    [`GET ${P}/characteristics`]: ok([{ ...ch, subgroupCount: 0 }]),
    [`GET ${P}/lookups/items`]: ok([{ itemCode: "FG-C200", name: "커넥터" }]),
    [`PATCH ${P}/characteristics/7`]: ok({ ...ch, chartType: "I_MR" }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "수정" }));
  expect(screen.getByLabelText("부분군 크기(2~10)")).toHaveValue(5);
  fireEvent.change(screen.getByLabelText("관리도 종류"), {
    target: { value: "I_MR" },
  });
  expect(screen.queryByLabelText("부분군 크기(2~10)")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() =>
    expect(sent(fetcher, "PATCH", "/characteristics/7")).toHaveLength(1),
  );
  const saved = body(sent(fetcher, "PATCH", "/characteristics/7")[0]);
  expect(saved.chartType).toBe("I_MR");
  expect(saved.subgroupSize).toBe(1);
});

it("S-07 판정 규칙: 규칙 1은 끌 수 없고 고른 규칙만 보낸다", async () => {
  const fetcher = mount("/spc/characteristics", {
    [`GET ${P}/characteristics`]: ok([ch]),
    [`GET ${P}/lookups/items`]: ok([{ itemCode: "FG-C200", name: "커넥터" }]),
    [`PATCH ${P}/characteristics/7`]: ok(ch),
  });
  fireEvent.click(await screen.findByRole("button", { name: "수정" }));
  // rules가 비어 있으면 기본 1~3이 켜진 채로 보인다.
  expect(screen.getByLabelText(/규칙 1/)).toBeChecked();
  expect(screen.getByLabelText(/규칙 1/)).toBeDisabled();
  expect(screen.getByLabelText(/규칙 5/)).not.toBeChecked();
  fireEvent.click(screen.getByLabelText(/규칙 5/));
  fireEvent.click(screen.getByLabelText(/규칙 3/));
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() =>
    expect(sent(fetcher, "PATCH", "/characteristics/7")).toHaveLength(1),
  );
  expect(body(sent(fetcher, "PATCH", "/characteristics/7")[0]).rules).toEqual([
    1, 2, 5,
  ]);
});

const openSignal = {
  id: 41,
  subgroupId: 4,
  characteristicId: 7,
  characteristicCode: ch.code,
  itemCode: ch.itemCode,
  processCode: ch.processCode,
  characteristicName: ch.name,
  lotNo: "LT-0023",
  equipmentCode: "INJ-02",
  chart: "XBAR" as const,
  rule: 1 as const,
  value: "12.052000",
  detectedAt: "2026-09-11T06:00:00+09:00",
  status: "open" as const,
  causeCategory: null,
  action: null,
  resolvedAt: null,
  voidedAt: null,
  limitVersion: 2,
};
const ocapItem = (id: number, extra = {}) => ({
  id,
  characteristicId: null,
  characteristicCode: null,
  characteristicName: null,
  itemCode: null,
  processCode: null,
  ruleNo: null,
  seq: id,
  checkText: `점검 ${id}`,
  causeCategory: null,
  isActive: true,
  checkCount: 0,
  check: null,
  ...extra,
});

it("S-09 이상 대응 절차: 적용 범위를 비우면 '모든 것'으로 보낸다", async () => {
  const fetcher = mount("/spc/ocap", {
    [`GET ${P}/ocap-items`]: ok([
      ocapItem(1, { causeCategory: "MACHINE" }),
      ocapItem(2, {
        characteristicId: 7,
        characteristicName: ch.name,
        itemCode: ch.itemCode,
        processCode: ch.processCode,
        ruleNo: 1,
      }),
    ]),
    [`GET ${P}/characteristics`]: ok([ch]),
    [`POST ${P}/ocap-items`]: ok(ocapItem(3), 201),
  });
  expect(await screen.findByText("모든 특성 · 모든 규칙")).toBeVisible();
  expect(
    screen.getByText("FG-C200 · INJ · 하우징 높이 · 규칙 1"),
  ).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "항목 등록" }));
  fireEvent.change(screen.getByLabelText("점검 내용"), {
    target: { value: "설비 공기압 확인" },
  });
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/ocap-items")).toHaveLength(1),
  );
  const saved = body(sent(fetcher, "POST", "/ocap-items")[0]);
  expect(saved.characteristicId).toBeNull();
  expect(saved.ruleNo).toBeNull();
});

it("S-05 점검표: 남은 점검을 알리고 NG는 메모 칸이 열린다", async () => {
  const fetcher = mount("/spc/signals?signal=41", {
    [`GET ${P}/signals`]: ok([openSignal]),
    [`GET ${P}/characteristics/7/chart`]: ok(chart),
    [`GET ${P}/signals/41/ocap`]: ok({
      signalId: 41,
      status: "open",
      items: [ocapItem(1, { causeCategory: "MEASUREMENT" })],
      missing: [1],
    }),
    [`POST ${P}/signals/41/ocap`]: ok({
      signalId: 41,
      status: "open",
      items: [
        ocapItem(1, {
          causeCategory: "MEASUREMENT",
          check: {
            id: 9,
            signalId: 41,
            ocapItemId: 1,
            result: "NG",
            note: "영점이 밀려 있었다",
            checkedAt: "2026-09-11T07:00:00+09:00",
          },
        }),
      ],
      missing: [],
    }),
  });
  expect(
    await screen.findByText(/남은 점검 1개를 모두 기록해야/),
  ).toBeVisible();
  expect(screen.queryByLabelText("무엇이 문제였나요")).toBeNull();
  fireEvent.change(screen.getByLabelText("결과"), { target: { value: "NG" } });
  fireEvent.change(screen.getByLabelText("무엇이 문제였나요"), {
    target: { value: "영점이 밀려 있었다" },
  });
  fireEvent.click(screen.getByRole("button", { name: "점검 저장" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/signals/41/ocap")).toHaveLength(1),
  );
  expect(body(sent(fetcher, "POST", "/signals/41/ocap")[0]).checks).toEqual([
    { ocapItemId: 1, result: "NG", note: "영점이 밀려 있었다" },
  ]);
  // NG 항목의 해당 원인이 조치 원인으로 제안된다.
  await waitFor(() =>
    expect(screen.getByLabelText("원인 분류")).toHaveValue("MEASUREMENT"),
  );
});

const report = (id: number, extra = {}) => ({
  id,
  characteristicId: 7,
  characteristicCode: ch.code,
  characteristicName: ch.name,
  itemCode: ch.itemCode,
  itemName: ch.itemName,
  processCode: ch.processCode,
  unit: "mm",
  lsl: ch.lsl,
  usl: ch.usl,
  target: ch.target,
  decimals: 3,
  chartType: "XBAR_R" as const,
  reportStartOn: "2026-09-01",
  reportEndOn: "2026-09-30",
  version: 1,
  status: "draft" as const,
  subgroupCount: 24,
  mean: "12.000000",
  sigmaWithin: "0.020000",
  sigmaOverall: "0.035000",
  cp: "1.666667",
  cpk: "1.600000",
  pp: "0.952381",
  ppk: "0.914286",
  skewness: "0.120000",
  kurtosis: "-0.400000",
  comment: null,
  confirmedAt: null,
  createdAt: "2026-10-01T09:00:00+09:00",
  ...extra,
});

it("S-11 공정능력 보고서: 군내·전체 σ를 나란히 보여 주고 확정하면 읽기 전용이 된다", async () => {
  const fetcher = mount("/spc/reports", {
    [`GET ${P}/characteristics`]: ok([ch]),
    [`GET ${P}/capability-reports`]: ok([report(5)]),
    [`POST ${P}/capability-reports/5/confirm`]: ok(
      report(5, {
        status: "confirmed",
        confirmedAt: "2026-10-02T09:00:00+09:00",
      }),
    ),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세 · 확정" }));
  // Cpk는 좋은데 Ppk가 나쁘다 — 기간 중에 공정이 옮겨 갔다는 뜻이다.
  expect(screen.getByLabelText("Cpk")).toHaveTextContent("1.60");
  expect(screen.getByLabelText("Ppk")).toHaveTextContent("0.91");
  const figures = screen.getByText("군내 σ (R̄/d2)").parentElement!;
  expect(figures).toHaveTextContent("0.02000"); // 군내 σ
  expect(figures).toHaveTextContent("0.03500"); // 전체 σ가 더 크다
  fireEvent.click(screen.getByRole("button", { name: "확정" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/capability-reports/5/confirm")).toHaveLength(
      1,
    ),
  );
  expect(await screen.findByText(/확정된 보고서입니다/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "확정" })).toBeNull();
});

it("S-03 공정능력: Ppk·정규성·월별 추이를 함께 보여 준다", async () => {
  mount("/spc/capability?c=7", {
    [`GET ${P}/characteristics`]: ok([ch]),
    [`GET ${P}/characteristics/7/capability`]: ok({
      characteristic: ch,
      subgroupCount: 24,
      minimum: 20,
      openSignals: 0,
      insufficient: false,
      mu: "12.000000",
      sigma: "0.020000",
      cp: "1.666667",
      cpk: "1.600000",
      judgement: "CAPABLE",
      sigmaOverall: "0.035000",
      pp: "0.952381",
      ppk: "0.914286",
      skewness: "0.120000",
      kurtosis: "-0.400000",
      histogram: [{ from: "11.950000", to: "12.050000", count: 24 }],
      trend: [
        { month: "2026-08", subgroupCount: 4, cpk: null, judgement: null },
        {
          month: "2026-09",
          subgroupCount: 20,
          cpk: "1.600000",
          judgement: "CAPABLE",
        },
      ],
    }),
  });
  expect(await screen.findByLabelText("Ppk")).toHaveTextContent("0.91");
  expect(screen.getByLabelText("정규성")).toHaveTextContent("0.12 · -0.40");
  expect(screen.getByText("2026-08")).toBeVisible();
  // 부분군이 기준에 못 미치는 달은 계산하지 않고 수만 센다.
  expect(screen.getByText("부분군 4개")).toBeVisible();
  expect(screen.getByText("2026-09").parentElement).toHaveTextContent("1.60");
});

it("S-10 층별 비교: 설비별로 갈라 보여 주고 부분군이 적은 그룹은 Cpk를 계산하지 않는다", async () => {
  const fetcher = mount("/spc/strata?c=7", {
    [`GET ${P}/characteristics`]: ok([ch]),
    [`GET ${P}/characteristics/7/strata`]: ok({
      characteristic: ch,
      by: "equipment",
      minimum: 20,
      overallMean: "12.000000",
      groups: [
        {
          id: "INJ-01",
          group: "INJ-01",
          subgroupCount: 30,
          mean: "11.990000",
          shift: "-0.010000",
          cpk: "1.500000",
          judgement: "CAPABLE",
        },
        {
          id: "INJ-02",
          group: "INJ-02",
          subgroupCount: 6,
          mean: "12.060000",
          shift: "0.060000",
          cpk: null,
          judgement: null,
        },
      ],
    }),
  });
  expect(await screen.findByText("INJ-01")).toBeVisible();
  expect(screen.getByText("+0.0600")).toBeVisible();
  expect(screen.getByText(/부분군 20개 미만 — 계산 안 함/)).toBeVisible();
  fireEvent.change(screen.getByLabelText("기준"), { target: { value: "lot" } });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(([url]) => String(url).includes("by=lot")),
    ).toBe(true),
  );
});
