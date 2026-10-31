// QMS-1g-2 화면: Q-13 품질 지표(F72)와 Q-01 미결 업무 카드(F71).
import { render, screen } from "@testing-library/react";
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

const emptyMetrics = {
  month: "2026-09",
  months: ["2026-09"],
  incoming: { lots: 0, failedLots: 0, failRate: null, ppm: null },
  outgoing: { lots: 0, failedLots: 0, failRate: null, ppm: null },
  customer: { claims: 0, qty: "0" },
  process: null,
  pareto: [],
  processPareto: null,
  trend: [],
};

it("PPM을 낼 수 없는 발생처는 0이 아니라 줄표로 둔다", async () => {
  mount("/qms/metrics", {
    [`GET ${Q}/metrics`]: ok({
      ...emptyMetrics,
      incoming: { lots: 4, failedLots: 1, failRate: "25.0", ppm: "333333.3" },
      outgoing: { lots: 2, failedLots: 1, failRate: "50.0", ppm: null },
    }),
  });
  const rows = await screen.findByRole("table", { name: /발생처별/ });
  const cells = (label: string) =>
    Array.from(rows.querySelectorAll("tbody tr"))
      .find((tr) => tr.textContent?.startsWith(label))!
      .querySelectorAll("td");
  expect(cells("수입")[4]).toHaveTextContent("333,333.3");
  // 출하에는 불량 개수 칸이 없다 — 0으로 채우지 않는다.
  expect(cells("출하")[3]).toHaveTextContent("50.0%");
  expect(cells("출하")[4]).toHaveTextContent("—");
  expect(cells("고객")[4]).toHaveTextContent("—");
});

it("MES를 끄면 공정은 0이 아니라 읽지 않는다고 말한다", async () => {
  mount("/qms/metrics", { [`GET ${Q}/metrics`]: ok(emptyMetrics) });
  expect(
    await screen.findByText(/MES를 꺼서 읽지 않습니다/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/MES를 꺼서 공정 불량을 읽지 않습니다/),
  ).toBeInTheDocument();
});

it("파레토는 누적 비율까지 보여 준다", async () => {
  mount("/qms/metrics", {
    [`GET ${Q}/metrics`]: ok({
      ...emptyMetrics,
      pareto: [
        { code: "D01", name: "치수 이탈", count: 3 },
        { code: "D02", name: "흑점", count: 1 },
      ],
    }),
  });
  const table = await screen.findByRole("table", { name: /검사 불량 유형/ });
  const rows = table.querySelectorAll("tbody tr");
  expect(rows[0]).toHaveTextContent("75.0%");
  expect(rows[1].querySelectorAll("td")[3]).toHaveTextContent("100.0%");
});

it("코드 없는 공정 불량도 행마다 따로 센다", async () => {
  // 모두 code가 "—"다. 같은 key로 묶이면 행이 사라진다.
  mount("/qms/metrics", {
    [`GET ${Q}/metrics`]: ok({
      ...emptyMetrics,
      process: {
        records: 2,
        inputQty: "100",
        defectQty: "30",
        ppm: "300000.0",
      },
      processPareto: [
        { code: "—", name: "SHORT_SHOT 미충전", qty: "20.000" },
        { code: "—", name: "PIN_MISALIGN 핀 정렬 불량", qty: "10.000" },
      ],
    }),
  });
  const table = await screen.findByRole("table", { name: /공정 불량/ });
  const rows = table.querySelectorAll("tbody tr");
  expect(rows).toHaveLength(2);
  // 코드가 없으면 줄표를 앞에 붙이지 않는다.
  expect(rows[0].querySelectorAll("td")[0]).toHaveTextContent(
    "SHORT_SHOT 미충전",
  );
  expect(rows[1].querySelectorAll("td")[3]).toHaveTextContent("100.0%");
});

it("검사가 없는 달은 빈 표가 아니라 그 사실을 알린다", async () => {
  mount("/qms/metrics", { [`GET ${Q}/metrics`]: ok(emptyMetrics) });
  expect(
    await screen.findByText("확정한 검사가 아직 없습니다."),
  ).toBeInTheDocument();
  expect(screen.getByText("이 달 불합격 항목이 없습니다.")).toBeInTheDocument();
});

const dashboard = {
  month: "2026-09",
  inspected: 3,
  passRate: "66.7",
  activeHolds: 1,
  pendingLots: 2,
  daily: [],
  topDefects: [],
  recentFails: [],
  holds: [],
  incomingPending: 4,
  openNcrs: 2,
  openCapas: 1,
  openClaims: 0,
  gaugesDue: 3,
};

it("대시보드 미결 업무는 처리할 화면으로 보낸다", async () => {
  mount("/qms/dashboard", { [`GET ${Q}/dashboard`]: ok(dashboard) });
  const panel = await screen.findByRole("region", { name: "미결 업무" });
  expect(panel).toHaveTextContent("수입 검사 대기");
  expect(panel).toHaveTextContent("4건");
  expect(panel).toHaveTextContent("교정 도래 계측기");
  expect(panel).toHaveTextContent("3대");
  expect(screen.getByRole("link", { name: "미결 부적합" })).toHaveAttribute(
    "href",
    "/qms/ncrs",
  );
});

it("WMS를 끄면 수입 대기는 0건이 아니라 조회 불가다", async () => {
  mount("/qms/dashboard", {
    [`GET ${Q}/dashboard`]: ok({ ...dashboard, incomingPending: null }),
  });
  const panel = await screen.findByRole("region", { name: "미결 업무" });
  expect(panel).toHaveTextContent("조회 불가");
});
