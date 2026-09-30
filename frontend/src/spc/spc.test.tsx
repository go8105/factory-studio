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
