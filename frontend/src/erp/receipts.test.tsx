// FS-019e E-09 매출채권 현황 · E-10 수금 등록·소명. 검증 항목별로 테스트를 나눈다.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { mount } from "./test-support";

const E = "/api/v1/erp";
const list = (data: unknown[]) => ({ status: 200, body: { data } });
const rv = (over: object = {}) => ({
  id: 21,
  salesRecordId: 3,
  partnerId: 1,
  amount: "1000.00",
  appliedAmount: "600.00",
  balance: "400.00",
  status: "PARTIAL",
  dueDate: null,
  recognizedAt: "2026-08-01T01:00:00Z",
  shipmentNo: "SH-0001",
  applications: [
    {
      id: 5,
      receiptId: 9,
      receivableId: 21,
      amount: "600.00",
      appliedAt: "2026-08-10T01:00:00Z",
      receiptNo: "RC-0001",
      shipmentNo: "SH-0001",
    },
  ],
  ...over,
});
const receipt = (over: object = {}) => ({
  id: 9,
  receiptNo: "RC-0009",
  partnerId: 1,
  receivedOn: "2026-09-20",
  amount: "1200.00",
  status: "confirmed",
  appliedAmount: "0.00",
  unappliedAmount: "1200.00",
  applications: [],
  ...over,
});

it("채권 현황은 서버 잔액·상태와 합계를 보여 준다", async () => {
  mount("/erp/receivables", {
    [`GET ${E}/receivables`]: list([
      rv(),
      rv({
        id: 22,
        shipmentNo: "SH-0002",
        amount: "500.00",
        appliedAmount: "0.00",
        balance: "500.00",
        status: "OPEN",
        applications: [],
      }),
    ]),
  });
  const table = await screen.findByRole("table", { name: "매출채권 목록" });
  expect(within(table).getByText("일부회수")).toBeVisible();
  expect(within(table).getByText("미회수")).toBeVisible();
  const foot = table.querySelector("tfoot")!;
  expect(foot).toHaveTextContent("1,500원");
  expect(foot).toHaveTextContent("900원");
});

it("만기 없는 채권은 미설정으로 표시하고 행을 펼치면 소명 이력이 나온다", async () => {
  mount("/erp/receivables", { [`GET ${E}/receivables`]: list([rv()]) });
  expect(await screen.findByText("미설정")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "소명 1" }));
  expect(
    screen.getByRole("list", { name: "SH-0001 소명 이력" }),
  ).toHaveTextContent("RC-0001");
});

it("상태 필터는 서버 상태 값으로 거른다", async () => {
  mount("/erp/receivables", {
    [`GET ${E}/receivables`]: list([
      rv(),
      rv({ id: 23, shipmentNo: "SH-0003", balance: "0.00", status: "CLOSED" }),
    ]),
  });
  await screen.findByText("SH-0003");
  fireEvent.change(screen.getByLabelText("상태"), {
    target: { value: "CLOSED" },
  });
  expect(screen.queryByText("SH-0001")).toBeNull();
  expect(screen.getByText("SH-0003")).toBeVisible();
});

it("수금 화면은 수금액 = 소명 + 미소명 등식을 보여 준다", async () => {
  mount("/erp/receipts", {
    [`GET ${E}/receipts`]: list([
      receipt({ appliedAmount: "1000.00", unappliedAmount: "200.00" }),
    ]),
    [`GET ${E}/receivables`]: list([rv()]),
  });
  fireEvent.click(await screen.findByRole("button", { name: "소명 0" }));
  expect(
    screen.getByText("수금액 1,200원 = 소명 1,000원 + 미소명 200원"),
  ).toBeVisible();
});

it("FIFO는 제안만 채우고 저장은 누를 때 보낸다", async () => {
  const fetcher = mount("/erp/receipts", {
    [`GET ${E}/receipts`]: list([receipt()]),
    [`GET ${E}/receivables`]: list([rv()]),
    [`GET ${E}/receipts/9/fifo-suggestion`]: list([
      { receivableId: 21, amount: "400.00" },
    ]),
    [`POST ${E}/receipts/9/applications`]: {
      status: 201,
      body: { data: receipt() },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "소명 0" }));
  fireEvent.click(screen.getByRole("button", { name: "FIFO로 채우기" }));
  expect(await screen.findByDisplayValue("400")).toBeVisible();
  expect(fetcher.mock.calls.some(([, i]) => i?.method === "POST")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "소명 저장" }));
  await waitFor(() => {
    const call = fetcher.mock.calls.find(([, i]) => i?.method === "POST")!;
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      lines: [{ receivableId: 21, amount: "400" }],
    });
  });
});

it("한도 초과는 어느 채권인지 풀어 쓴다", async () => {
  mount("/erp/receipts", {
    [`GET ${E}/receipts`]: list([receipt()]),
    [`GET ${E}/receivables`]: list([rv()]),
    [`POST ${E}/receipts/9/applications`]: {
      status: 409,
      body: {
        error: {
          code: "LIMIT_EXCEEDED",
          message: "채권 잔액을 넘어 소명할 수 없습니다.",
          details: {
            reason: "LIMIT_EXCEEDED",
            limit: "RECEIVABLE",
            shipmentNo: "SH-0001",
            availableAmount: "400.00",
          },
        },
      },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "소명 0" }));
  fireEvent.change(screen.getByLabelText("SH-0001 소명액"), {
    target: { value: "500" },
  });
  fireEvent.click(screen.getByRole("button", { name: "소명 저장" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "SH-0001 채권의 남은 잔액은 400원",
  );
});

it("작성 중 수금은 소명 입력 대신 확정 안내를 보여 준다", async () => {
  mount("/erp/receipts", {
    [`GET ${E}/receipts`]: list([receipt({ status: "draft" })]),
    [`GET ${E}/receivables`]: list([rv()]),
  });
  fireEvent.click(await screen.findByRole("button", { name: "소명 0" }));
  expect(screen.getByText(/먼저 확정해야 소명할 수 있습니다/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "FIFO로 채우기" })).toBeNull();
});

it("소명 취소는 확인 뒤 DELETE한다", async () => {
  const applied = receipt({
    appliedAmount: "600.00",
    unappliedAmount: "600.00",
    applications: [rv().applications[0]],
  });
  const fetcher = mount("/erp/receipts", {
    [`GET ${E}/receipts`]: list([applied]),
    [`GET ${E}/receivables`]: list([rv()]),
    [`DELETE ${E}/receipts/9/applications/5`]: {
      status: 200,
      body: { data: receipt() },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "소명 1" }));
  fireEvent.click(screen.getByRole("button", { name: "소명 취소" }));
  expect(fetcher.mock.calls.some(([, i]) => i?.method === "DELETE")).toBe(
    false,
  );
  fireEvent.click(screen.getByRole("button", { name: "소명 취소 확정" }));
  await waitFor(() =>
    expect(fetcher.mock.calls.some(([, i]) => i?.method === "DELETE")).toBe(
      true,
    ),
  );
});
