// FEMS-1g 화면: F-22 비용 배분, F-23 고지서 대조, F-11 발전. (F-10 부서는 equipments.test.tsx)
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2099-01-01T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const run = (over: object = {}) => ({
  id: 5,
  costMonth: "2026-09",
  version: 1,
  status: "draft",
  confirmedAt: null,
  ...over,
});
const detail = (over: object = {}) => ({
  ...run(),
  total: "900000",
  unallocatedCost: "100000.00",
  coverage: { days: 23, expectedDays: 30, partial: true },
  byDepartment: [
    { departmentCode: "PROD", cost: "600000" },
    { departmentCode: "미지정", cost: "300000" },
  ],
  lines: [
    {
      equipmentCode: "INJ-01",
      equipmentName: "사출 1호",
      sourceCode: "ELEC",
      departmentCode: "PROD",
      itemCode: "FG-C100",
      quantity: "4000",
      unit: "kWh",
      cost: "600000",
    },
    {
      equipmentCode: "ASM-01",
      equipmentName: "조립 1호",
      sourceCode: "ELEC",
      departmentCode: null,
      itemCode: null,
      quantity: "2000",
      unit: "kWh",
      cost: "300000",
    },
  ],
  ...over,
});
const bill = (over: object = {}) => ({
  id: 1,
  sourceCode: "ELEC",
  sourceName: "전력",
  billMonth: "2026-09",
  billedQty: "10000",
  billedAmount: "1500000.00",
  calculatedAmount: "1450000.00",
  difference: "50000.00",
  differenceRate: "3.4",
  note: "검침일 차이",
  ...over,
});
const sources = [
  {
    id: 1,
    sourceCode: "ELEC",
    name: "전력",
    isBillable: true,
    measureUnit: "kWh",
  },
  {
    id: 2,
    sourceCode: "WTR",
    name: "용수",
    isBillable: false,
    measureUnit: "m3",
  },
];

function mount(path: string, data: Record<string, unknown>) {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input).split("?")[0];
      const key = `${init?.method ?? "GET"} ${url.replace(/^.*\/api\/v1\/fems/, "")}`;
      if (key in data)
        return new Response(JSON.stringify({ data: data[key] }), {
          status: 200,
        });
      if (url.endsWith("/sessions/current"))
        return new Response(JSON.stringify({ data: session }));
      return new Response(JSON.stringify({ data: [] }));
    });
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  return fetcher;
}
const sent = (f: ReturnType<typeof mount>, method: string, suffix: string) =>
  f.mock.calls.filter(
    ([url, init]) =>
      (init?.method ?? "GET") === method &&
      String(url).split("?")[0].endsWith(suffix),
  );

// ---------- F-22 ----------

it("월을 고르기 전에는 초안을 만들 수 없다", async () => {
  mount("/fems/cost-runs", { "GET /cost-runs": [] });
  const button = await screen.findByRole("button", { name: "초안 만들기" });
  expect(button).toBeDisabled();
  fireEvent.change(screen.getByLabelText("배분 월"), {
    target: { value: "2026-09" },
  });
  expect(button).toBeEnabled();
});

it("평균 요율로 나눈다는 한계를 먼저 밝힌다", async () => {
  mount("/fems/cost-runs", { "GET /cost-runs": [] });
  expect(
    await screen.findByText(/부하 시간대는 따로 반영하지 않고 평균 요율/),
  ).toBeInTheDocument();
});

it("초안을 만들면 설비·부서별 비용과 공용 비용을 보인다", async () => {
  mount("/fems/cost-runs", {
    "GET /cost-runs": [],
    "POST /cost-runs": detail(),
  });
  fireEvent.change(await screen.findByLabelText("배분 월"), {
    target: { value: "2026-09" },
  });
  fireEvent.click(screen.getByRole("button", { name: "초안 만들기" }));
  const table = await screen.findByRole("table", { name: "설비별 비용" });
  expect(table).toHaveTextContent("INJ-01");
  expect(table).toHaveTextContent("FG-C100");
  // 부서가 없는 설비는 미지정으로 보인다.
  expect(table.querySelectorAll("tbody tr")[1]).toHaveTextContent("미지정");
  expect(screen.getByText(/공용 비용 100,000원/)).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "부서별 비용" })).toHaveTextContent(
    "PROD",
  );
});

it("계측이 달 전체가 아니면 달 전체의 비용이 아니라고 경고한다", async () => {
  mount("/fems/cost-runs", {
    "GET /cost-runs": [],
    "POST /cost-runs": detail(),
  });
  fireEvent.change(await screen.findByLabelText("배분 월"), {
    target: { value: "2026-09" },
  });
  fireEvent.click(screen.getByRole("button", { name: "초안 만들기" }));
  expect(await screen.findByText(/달 전체의/)).toBeInTheDocument();
});

it("초안에만 확정을 둔다", async () => {
  mount("/fems/cost-runs", {
    "GET /cost-runs": [run(), run({ id: 6, version: 2, status: "confirmed" })],
  });
  await screen.findByRole("table", { name: "배분 목록" });
  expect(screen.getAllByRole("button", { name: "확정" })).toHaveLength(1);
});

// ---------- F-23 ----------

it("대조 버튼은 필수 항목이 찰 때까지 꺼져 있다", async () => {
  mount("/fems/utility-bills", {
    "GET /utility-bills": [],
    "GET /energy-sources": sources,
  });
  const button = await screen.findByRole("button", { name: "대조" });
  expect(button).toBeDisabled();
  await screen.findByRole("option", { name: /ELEC/ });
  fireEvent.change(screen.getByLabelText("에너지원"), {
    target: { value: "1" },
  });
  fireEvent.change(screen.getByLabelText("청구 월"), {
    target: { value: "2026-09" },
  });
  fireEvent.change(screen.getByLabelText(/청구 사용량/), {
    target: { value: "10000" },
  });
  fireEvent.change(screen.getByLabelText(/청구 금액/), {
    target: { value: "1500000" },
  });
  expect(button).toBeEnabled();
});

it("요금 부과 대상이 아닌 에너지원은 고르는 목록에 없다", async () => {
  mount("/fems/utility-bills", {
    "GET /utility-bills": [],
    "GET /energy-sources": sources,
  });
  const select = await screen.findByLabelText("에너지원");
  await screen.findByRole("option", { name: /ELEC/ });
  expect(select).toHaveTextContent("ELEC");
  expect(select).not.toHaveTextContent("WTR");
});

it("차이는 부호와 금액, 차이율로 보이고 일치하면 일치라고 적는다", async () => {
  mount("/fems/utility-bills", {
    "GET /utility-bills": [
      bill(),
      bill({
        id: 2,
        billMonth: "2026-08",
        difference: "0.00",
        differenceRate: "0.0",
        note: null,
      }),
    ],
    "GET /energy-sources": sources,
  });
  const table = await screen.findByRole("table", { name: "고지서 대조" });
  const rows = table.querySelectorAll("tbody tr");
  expect(rows[0]).toHaveTextContent("+50,000원 (3.4%)");
  expect(rows[1]).toHaveTextContent("일치");
});

it("산정이 0이면 차이율을 0%로 적지 않는다", async () => {
  mount("/fems/utility-bills", {
    "GET /utility-bills": [
      bill({
        calculatedAmount: "0.00",
        difference: "1000.00",
        differenceRate: null,
      }),
    ],
    "GET /energy-sources": sources,
  });
  const table = await screen.findByRole("table", { name: "고지서 대조" });
  expect(table).toHaveTextContent("+1,000원");
  expect(table).not.toHaveTextContent("%");
});

it("대조 저장은 차이 사유와 함께 보낸다", async () => {
  const fetcher = mount("/fems/utility-bills", {
    "GET /utility-bills": [],
    "GET /energy-sources": sources,
    "POST /utility-bills": bill({
      coverage: { days: 23, partial: true },
    }),
  });
  // 옵션은 목록 응답 뒤에 채워진다. 기다리지 않고 값을 넣으면 반영되지 않아 버튼이 꺼진 채 남는다.
  await screen.findByRole("option", { name: /ELEC/ });
  fireEvent.change(screen.getByLabelText("에너지원"), {
    target: { value: "1" },
  });
  fireEvent.change(screen.getByLabelText("청구 월"), {
    target: { value: "2026-09" },
  });
  fireEvent.change(screen.getByLabelText(/청구 사용량/), {
    target: { value: "10000" },
  });
  fireEvent.change(screen.getByLabelText(/청구 금액/), {
    target: { value: "1500000" },
  });
  fireEvent.change(screen.getByLabelText("차이 사유"), {
    target: { value: "검침일 차이" },
  });
  fireEvent.click(screen.getByRole("button", { name: "대조" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/utility-bills")).toHaveLength(1),
  );
  const body = JSON.parse(
    String(sent(fetcher, "POST", "/utility-bills")[0][1]?.body),
  );
  expect(body).toMatchObject({
    energySourceId: 1,
    billMonth: "2026-09",
    note: "검침일 차이",
  });
  expect(await screen.findByText(/한 달치가 아닙니다/)).toBeInTheDocument();
});

// ---------- F-11 ----------

it("에너지원 목록에서 발전을 구분으로 고를 수 있다", async () => {
  mount("/fems/energy-sources", {
    "GET /energy-sources": [
      {
        id: 3,
        sourceCode: "SOLAR",
        name: "태양광",
        sourceKind: "GENERATION",
        measureUnit: "kWh",
        isBillable: false,
        isActive: true,
        createdAt: "2026-09-01T00:00:00Z",
      },
    ],
  });
  expect(await screen.findByText("발전")).toBeInTheDocument();
  expect(screen.getByText("미부과")).toBeInTheDocument();
});
