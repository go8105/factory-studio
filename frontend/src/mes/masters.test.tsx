// W2a-1b MES 기준정보: 불량·사유 코드, 작업자·근무조, 라벨 양식, 공정 검사 기준.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-10-10T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const defectCodes = [
  { id: 1, code: "SCR", name: "긁힘", category: "APPEARANCE", isActive: true },
];
const reasonCodes = [
  {
    id: 2,
    category: "DOWNTIME",
    code: "PM",
    name: "예방보전",
    planned: true,
    isActive: true,
  },
];
const shifts = [
  {
    id: 3,
    code: "A",
    name: "주간조",
    startTime: "08:00:00",
    endTime: "20:00:00",
    isActive: true,
  },
];
const workers = [
  {
    id: 4,
    code: "W001",
    name: "홍길동",
    shiftId: 3,
    hrEmployeeCode: "E001",
    isActive: true,
  },
];
const labels = [
  {
    id: 5,
    code: "PAL1",
    labelKind: "PALLET",
    barcodeType: "QR",
    widthMm: 100,
    heightMm: 80,
    fields: "palletNo,itemCode",
    isDefault: true,
    isActive: true,
  },
];
const processes = [{ id: 6, code: "INJ", name: "사출" }];
const items = [{ id: 7, itemCode: "FG-C200", name: "하우징" }];
const inspectionItems = [
  {
    id: 8,
    processId: 6,
    itemId: null,
    seq: 1,
    name: "하우징 높이",
    method: "RANGE",
    lowerLimit: "9.8",
    upperLimit: "10.2",
    unit: "mm",
    isActive: true,
  },
];
type Reply = { status: number; body?: unknown };

function mockApi(replies: Record<string, Reply> = {}) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input);
      const reply = replies[`${init?.method ?? "GET"} ${url.split("?")[0]}`];
      if (reply)
        return new Response(JSON.stringify(reply.body), {
          status: reply.status,
        });
      if (url.includes("/sessions/current"))
        return new Response(JSON.stringify({ data: session }), { status: 200 });
      if (url.includes("/workspace/modules"))
        return new Response(
          JSON.stringify({
            data: ["core", "mes"].map((moduleKey) => ({
              moduleKey,
              enabled: true,
              updatedAt: null,
            })),
          }),
          { status: 200 },
        );
      const data = url.includes("/mes/defect-codes")
        ? defectCodes
        : url.includes("/mes/reason-codes")
          ? reasonCodes
          : url.includes("/mes/shifts")
            ? shifts
            : url.includes("/mes/workers")
              ? workers
              : url.includes("/mes/label-templates")
                ? labels
                : url.includes("/mes/inspection-items")
                  ? inspectionItems
                  : url.includes("/mes/processes")
                    ? processes
                    : url.includes("/mes/items")
                      ? items
                      : [];
      return new Response(
        JSON.stringify({
          data,
          page: { offset: 0, limit: 20, total: data.length },
        }),
        { status: 200 },
      );
    });
}

function show(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

it("불량·사유 코드는 탭으로 나뉘고 계획된 정지를 표시한다", async () => {
  mockApi();
  show("/mes/codes");
  expect(await screen.findByText("긁힘")).toBeVisible();
  expect(screen.getByText("외관")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "사유 코드" }));
  expect(await screen.findByText("예방보전")).toBeVisible();
  // 안내 문구와 배지 두 군데에 나온다 — 배지가 있는지만 본다.
  expect(screen.getAllByText("계획된 정지").length).toBeGreaterThan(1);
});

it("작업자는 근무조 이름과 HR 사원 코드를 함께 보여준다", async () => {
  mockApi();
  show("/mes/workers");
  expect(await screen.findByText("W001")).toBeVisible();
  expect(screen.getByText("주간조")).toBeVisible();
  expect(screen.getByText("E001")).toBeVisible();
});

it("작업자 등록은 코드를 대문자로 보내고 멱등 키를 붙인다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/mes/workers": { status: 201, body: { data: workers[0] } },
  });
  show("/mes/workers");
  fireEvent.click(await screen.findByRole("button", { name: "작업자 등록" }));
  fireEvent.change(await screen.findByLabelText("코드(바코드)"), {
    target: { value: "w002" },
  });
  fireEvent.change(screen.getByLabelText("이름"), {
    target: { value: "김철수" },
  });
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.filter(
        ([url, init]) =>
          String(url).includes("/mes/workers") && init?.method === "POST",
      ),
    ).toHaveLength(1),
  );
  const [, init] = fetcher.mock.calls.find(
    ([url, options]) =>
      String(url).includes("/mes/workers") && options?.method === "POST",
  )!;
  expect(init?.headers).toMatchObject({
    "X-CSRF-Token": "test-csrf",
    "Idempotency-Key": expect.any(String),
  });
  expect(JSON.parse(String(init?.body))).toMatchObject({ code: "W002" });
});

it("라벨 양식은 종류·바코드·크기와 기본 표시를 보여준다", async () => {
  mockApi();
  show("/mes/labels");
  expect(await screen.findByText("PAL1")).toBeVisible();
  expect(screen.getByText("팔레트")).toBeVisible();
  expect(screen.getByText("QR")).toBeVisible();
  expect(screen.getByText(/100 . 80 mm/)).toBeVisible();
  // 열 제목("기본")과 배지가 같이 있다 — 배지까지 둘 다 있으면 된다.
  expect(screen.getAllByText("기본").length).toBeGreaterThan(1);
});

it("공정 검사 기준은 품목을 비우면 공정 공통으로 보여준다", async () => {
  mockApi();
  show("/mes/inspection-items");
  expect(await screen.findByText("하우징 높이")).toBeVisible();
  expect(screen.getByText("공정 공통")).toBeVisible();
  expect(screen.getByText("9.8 ~ 10.2 mm")).toBeVisible();
  expect(screen.getByText("수치(상·하한)")).toBeVisible();
});
