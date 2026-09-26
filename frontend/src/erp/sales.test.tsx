// FS-019b E-02 견적 · E-03 판매계획 · E-04 수주. 검증 항목별로 테스트를 나눈다.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";

const E = "/api/v1/erp";
const line = {
  id: 11,
  lineNo: 1,
  itemId: 2,
  quoteQty: "100.000",
  unit: "EA",
  unitPrice: "1200.0000",
  discountRate: "0.00",
  amount: "120000",
  masterPrice: "1200.0000",
  priceSource: "partner_price",
};
const quote = (over: object = {}) => ({
  id: 7,
  quoteNo: "Q-0001",
  revisionNo: 2,
  revisionCount: 2,
  isLatest: true,
  partnerId: 1,
  quotedOn: "2026-09-20",
  validUntil: null,
  status: "sent",
  remark: null,
  salesOrderId: null,
  totalAmount: "120000",
  lines: [line],
  history: [
    { id: 1, status: "draft", changedAt: "2026-09-20T00:00:00Z", reason: null },
  ],
  ...over,
});
const list = (data: unknown[]) => ({ status: 200, body: { data } });
const sentBody = (fetcher: ReturnType<typeof mount>, method: string) => {
  const call = fetcher.mock.calls.find(([, init]) => init?.method === method)!;
  return { url: String(call[0]), body: JSON.parse(String(call[1]?.body)) };
};

it("견적은 단가 출처를 표시한다", async () => {
  mount("/erp/quotations", { [`GET ${E}/quotations`]: list([quote()]) });
  fireEvent.click(await screen.findByRole("button", { name: "열기" }));
  expect(screen.getByText("거래처 단가 적용")).toBeVisible();
});

it("수동 단가는 단가표 값과 함께 표시한다", async () => {
  const manual = { ...line, unitPrice: "1000.0000", priceSource: "manual" };
  mount("/erp/quotations", {
    [`GET ${E}/quotations`]: list([quote({ lines: [manual] })]),
  });
  fireEvent.click(await screen.findByRole("button", { name: "열기" }));
  expect(screen.getByText(/수동 입력 \(단가표 1,200원\)/)).toBeVisible();
});

it("제출된 견적은 수락·개정·수주 전환을 보여 준다", async () => {
  mount("/erp/quotations", { [`GET ${E}/quotations`]: list([quote()]) });
  fireEvent.click(await screen.findByRole("button", { name: "열기" }));
  expect(screen.getByRole("button", { name: "수락" })).toBeVisible();
  expect(screen.getByRole("button", { name: "개정" })).toBeVisible();
  expect(screen.getByRole("form", { name: "수주 전환" })).toBeVisible();
});

it("거절은 사유를 입력해야 누를 수 있다", async () => {
  const fetcher = mount("/erp/quotations", {
    [`GET ${E}/quotations`]: list([quote()]),
    [`POST ${E}/quotations/7/status`]: {
      status: 200,
      body: { data: quote({ status: "rejected" }) },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "열기" }));
  const reject = screen.getByRole("button", { name: "거절" });
  expect(reject).toBeDisabled();
  fireEvent.change(screen.getByLabelText("거절·취소 사유"), {
    target: { value: "가격" },
  });
  fireEvent.click(reject);
  await screen.findByRole("button", { name: "열기" });
  expect(sentBody(fetcher, "POST").body).toEqual({
    status: "rejected",
    reason: "가격",
  });
});

it("작성 중 견적의 빈 단가는 null로 보낸다(거래처 단가)", async () => {
  const fetcher = mount("/erp/quotations", {
    [`GET ${E}/quotations`]: list([quote({ status: "draft", lines: [] })]),
    [`PUT ${E}/quotations/7/lines`]: {
      status: 200,
      body: { data: quote({ status: "draft" }) },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "열기" }));
  fireEvent.click(screen.getByRole("button", { name: "라인 추가" }));
  fireEvent.change(screen.getByLabelText("1번째 수량"), {
    target: { value: "5" },
  });
  fireEvent.click(screen.getByRole("button", { name: "라인 저장" }));
  await screen.findByRole("button", { name: "열기" });
  expect(sentBody(fetcher, "PUT").body.lines).toEqual([
    { itemId: 2, quoteQty: "5", unitPrice: null, discountRate: "0" },
  ]);
});

it("개정 이력에서 이전 개정본을 읽기 전용으로 연다", async () => {
  const old = quote({ id: 6, revisionNo: 1, isLatest: false, status: "sent" });
  mount("/erp/quotations", {
    [`GET ${E}/quotations`]: list([quote()]),
    [`GET ${E}/quotations/7/revisions`]: list([quote(), old]),
  });
  fireEvent.click(await screen.findByRole("button", { name: "열기" }));
  fireEvent.click(screen.getByRole("button", { name: "개정 이력 2건 보기" }));
  const table = await screen.findByRole("table", { name: "개정 이력" });
  fireEvent.click(within(table).getAllByRole("button", { name: "열기" })[1]);
  expect(screen.getByText("1차 (이전 개정본 · 읽기 전용)")).toBeVisible();
});

const plan = (status: "draft" | "confirmed") => ({
  id: 3,
  planCode: "SP-2026-10",
  targetMonth: "2026-10",
  status,
  confirmedAt: status === "confirmed" ? "2026-09-24T00:00:00Z" : null,
  lines: [
    { id: 1, salesPlanId: 3, itemId: 2, planQty: "1200.000", unit: "EA" },
  ],
});

it("판매계획은 MES와 단방향임을 안내한다", async () => {
  mount("/erp/sales-plans", {
    [`GET ${E}/sales-plans`]: list([plan("confirmed")]),
  });
  expect(
    await screen.findByText(
      /ERP에서는 이 계획이 MES에서 쓰이는지 알 수 없습니다/,
    ),
  ).toBeVisible();
});

it("확정 계획은 확정·삭제 버튼과 편집이 없다", async () => {
  mount("/erp/sales-plans", {
    [`GET ${E}/sales-plans`]: list([plan("confirmed")]),
  });
  fireEvent.click(await screen.findByRole("button", { name: "라인 1" }));
  expect(screen.queryByRole("button", { name: "확정" })).toBeNull();
  expect(screen.queryByRole("button", { name: "라인 저장" })).toBeNull();
  expect(screen.getByText("1,200 EA")).toBeVisible();
});

it("초안 계획 확정은 멱등 키와 함께 POST한다", async () => {
  const fetcher = mount("/erp/sales-plans", {
    [`GET ${E}/sales-plans`]: list([plan("draft")]),
    [`POST ${E}/sales-plans/3/confirm`]: {
      status: 200,
      body: { data: plan("confirmed") },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "확정" }));
  await screen.findByRole("button", { name: "라인 1" });
  const call = fetcher.mock.calls.find(([, init]) => init?.method === "POST")!;
  expect(String(call[0])).toContain("/sales-plans/3/confirm");
  expect(call[1]?.headers).toMatchObject({
    "Idempotency-Key": expect.any(String),
  });
});

const order = (over: object = {}) => ({
  id: 5,
  orderNo: "SO-0005",
  partnerId: 1,
  orderedOn: "2026-09-10",
  dueOn: "2026-09-30",
  status: "open",
  quotationId: null,
  quoteNo: null,
  quoteRevisionNo: null,
  shipmentOrderCount: 0,
  totalAmount: "12000",
  lines: [
    {
      id: 1,
      lineNo: 1,
      itemId: 2,
      orderQty: "10.000",
      unit: "EA",
      unitPrice: "1200.0000",
      amount: "12000",
      instructedQty: "10.000",
      shippedQty: "6.000",
    },
  ],
  ...over,
});

it("수주 명세는 출하 진행률을 보여 준다", async () => {
  mount("/erp/sales-orders", {
    [`GET ${E}/sales-orders`]: list([
      order({ status: "shipping", shipmentOrderCount: 1 }),
    ]),
  });
  fireEvent.click(await screen.findByRole("button", { name: "명세 1" }));
  expect(screen.getByText("10개 중 6개 출하 (60%)")).toBeVisible();
  expect(screen.getByText(/출하지시가 있거나 종결된 수주라/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "취소" })).toBeNull();
});

it("견적 없이 등록한 수주는 직접 등록으로 표시한다", async () => {
  mount("/erp/sales-orders", { [`GET ${E}/sales-orders`]: list([order()]) });
  expect(await screen.findByText("직접 등록")).toBeVisible();
});

it("수주 등록은 헤더와 명세를 함께 보낸다", async () => {
  const fetcher = mount("/erp/sales-orders", {
    [`GET ${E}/sales-orders`]: list([]),
    [`POST ${E}/sales-orders`]: { status: 201, body: { data: order() } },
  });
  const form = await screen.findByRole("form", { name: "수주 등록" });
  fireEvent.change(within(form).getByLabelText("수주번호"), {
    target: { value: "so-9" },
  });
  fireEvent.change(within(form).getByLabelText("납기일"), {
    target: { value: "2026-10-01" },
  });
  fireEvent.click(within(form).getByRole("button", { name: "라인 추가" }));
  fireEvent.change(within(form).getByLabelText("1번째 수량"), {
    target: { value: "3" },
  });
  fireEvent.click(within(form).getByRole("button", { name: "수주 등록" }));
  await waitFor(() =>
    expect(fetcher.mock.calls.some(([, i]) => i?.method === "POST")).toBe(true),
  );
  const { body } = sentBody(fetcher, "POST");
  expect(body).toMatchObject({
    orderNo: "SO-9",
    partnerId: 1,
    dueOn: "2026-10-01",
    lines: [{ itemId: 2, orderQty: "3", unitPrice: null }],
  });
});
