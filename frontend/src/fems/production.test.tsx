// FS-018i F-05 생산량 등록. 검증 항목별로 테스트를 나눈다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import { ErrorNotice } from "../shared/components";
import { ApiError } from "../shared/api";
import type { ProductionRecord } from "./Production";
const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const record = (over: Partial<ProductionRecord> = {}): ProductionRecord => ({
  id: 1,
  sourceKey: "MES:LT-0016:INS",
  versionNo: 2,
  equipmentId: 7,
  equipmentCode: "INS-01",
  equipmentName: "검사기 1호",
  itemCode: "FG-C100",
  startDate: "2026-09-10",
  endDate: "2026-09-10",
  productionQty: "1940.000",
  unit: "EA",
  status: "confirmed",
  confirmedAt: "2026-09-11T00:00:00+00:00",
  isLatest: true,
  isEffective: true,
  ...over,
});
const draft = record({
  id: 2,
  sourceKey: "MAN-20260920-001",
  versionNo: 1,
  status: "draft",
  confirmedAt: null,
  isEffective: false,
});
type Reply = { status: number; body?: unknown };
function mockApi(
  rows: ProductionRecord[] = [record(), draft],
  replies: Record<string, Reply> = {},
) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const reply = replies[`${method} ${url.split("?")[0]}`];
      if (reply)
        return new Response(
          reply.status === 204 ? null : JSON.stringify(reply.body),
          { status: reply.status },
        );
      const data = url.endsWith("/sessions/current")
        ? session
        : url.includes("/equipments")
          ? [{ id: 7, equipmentCode: "INS-01", name: "검사기 1호" }]
          : rows;
      return new Response(
        JSON.stringify({
          data,
          page: { offset: 0, limit: 20, total: rows.length },
        }),
        { status: 200 },
      );
    });
}
const BASE = "/api/v1/fems/production-records";
const calls = (fetcher: ReturnType<typeof mockApi>, method: string) =>
  fetcher.mock.calls.filter(
    ([url, init]) =>
      String(url).startsWith(BASE) && (init?.method ?? "GET") === method,
  );
function show() {
  render(
    <MemoryRouter initialEntries={["/fems/production"]}>
      <App />
    </MemoryRouter>,
  );
}
it("사이드바 원단위·목표에 F-05가 있다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("link", { name: /F-05 생산량 등록/ }),
  ).toHaveAttribute("href", "/fems/production");
});
it("MES 연동 환경의 자동 입력 값이라는 안내를 둔다", async () => {
  mockApi();
  show();
  expect(await screen.findByRole("note")).toHaveTextContent(
    "MES를 쓰는 환경이라면 생산실적에서 자동으로 넘어오는 값",
  );
});
it("원천 키와 버전을 함께 보여준다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("cell", { name: "MES:LT-0016:INS · v2" }),
  ).toBeVisible();
});
it("확정·원단위 반영과 초안을 구분해 표시한다", async () => {
  mockApi();
  show();
  expect(await screen.findByText("확정 · 원단위 반영")).toBeVisible();
  expect(screen.getByRole("cell", { name: "초안" })).toBeVisible();
});
it("이전 버전은 이전 버전으로 표시한다", async () => {
  mockApi([record({ versionNo: 1, isLatest: false, isEffective: false })]);
  show();
  expect(await screen.findByText("확정 · 이전 버전")).toBeVisible();
});
it("확정 기록에는 수정·삭제 대신 정정만 있다", async () => {
  mockApi([record()]);
  show();
  expect(await screen.findByRole("button", { name: "정정" })).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "수정" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "삭제" }),
  ).not.toBeInTheDocument();
});
it("이전 버전에는 정정 버튼이 없다", async () => {
  mockApi([record({ versionNo: 1, isLatest: false, isEffective: false })]);
  show();
  await screen.findByText("확정 · 이전 버전");
  expect(
    screen.queryByRole("button", { name: "정정" }),
  ).not.toBeInTheDocument();
});
it("이전 버전 포함은 includeHistory로 조회한다", async () => {
  const fetcher = mockApi();
  show();
  fireEvent.click(await screen.findByLabelText("이전 버전 포함"));
  await waitFor(() =>
    expect(
      calls(fetcher, "GET").some(([url]) =>
        String(url).includes("includeHistory=true"),
      ),
    ).toBe(true),
  );
});
it("등록은 대문자 품목 코드와 날짜로 초안을 요청한다", async () => {
  const fetcher = mockApi([record()], {
    [`POST ${BASE}`]: { status: 201, body: { data: draft } },
  });
  show();
  await screen.findByRole("option", { name: "INS-01 검사기 1호" });
  fireEvent.change(screen.getByLabelText("설비"), {
    target: { value: "7" },
  });
  fireEvent.change(screen.getByLabelText("품목 코드"), {
    target: { value: "fg-c100" },
  });
  fireEvent.change(screen.getByLabelText("시작일"), {
    target: { value: "2026-09-20" },
  });
  fireEvent.change(screen.getByLabelText("종료일 (포함)"), {
    target: { value: "2026-09-20" },
  });
  fireEvent.change(screen.getByLabelText("생산량"), {
    target: { value: "50" },
  });
  fireEvent.click(screen.getByRole("button", { name: "초안 등록" }));
  await waitFor(() => expect(calls(fetcher, "POST")).toHaveLength(1));
  const body = JSON.parse(String(calls(fetcher, "POST")[0][1]?.body));
  expect(body).toMatchObject({
    equipmentId: 7,
    itemCode: "FG-C100",
    startDate: "2026-09-20",
    endDate: "2026-09-20",
    productionQty: "50",
    unit: "EA",
  });
  expect(await screen.findByRole("status")).toHaveTextContent(
    "확정해야 원단위에 반영됩니다",
  );
});
it("확정은 confirm 경로를 CSRF·멱등 키로 호출한다", async () => {
  const fetcher = mockApi([draft], {
    [`POST ${BASE}/2/confirm`]: {
      status: 200,
      body: { data: { ...draft, status: "confirmed", isEffective: true } },
    },
  });
  show();
  fireEvent.click(await screen.findByRole("button", { name: "확정" }));
  await waitFor(() => expect(calls(fetcher, "POST")).toHaveLength(1));
  expect(calls(fetcher, "POST")[0][1]?.headers).toMatchObject({
    "X-CSRF-Token": "test-csrf",
    "Idempotency-Key": expect.any(String),
  });
});
it("정정은 새 초안을 만들고 설비·품목·단위를 잠근다", async () => {
  mockApi([record()], {
    [`POST ${BASE}/1/revise`]: {
      status: 201,
      body: {
        data: record({
          id: 3,
          versionNo: 3,
          status: "draft",
          isEffective: false,
        }),
      },
    },
  });
  show();
  fireEvent.click(await screen.findByRole("button", { name: "정정" }));
  expect(await screen.findByRole("status")).toHaveTextContent("v3 정정 초안");
  expect(screen.getByLabelText("설비")).toBeDisabled();
  expect(screen.getByLabelText("품목 코드")).toBeDisabled();
  expect(screen.getByLabelText("단위")).toBeDisabled();
  expect(screen.getByLabelText("생산량")).toBeEnabled();
});
it("초안 삭제는 확정 전 요청하지 않는다", async () => {
  const fetcher = mockApi([draft]);
  show();
  fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
  expect(screen.getByRole("button", { name: "삭제 확정" })).toBeVisible();
  expect(calls(fetcher, "DELETE")).toHaveLength(0);
});
it("기간이 겹치면 겹치는 기록을 읽을 수 있게 보여준다", () => {
  render(
    <ErrorNotice
      error={
        new ApiError(409, {
          code: "PRECONDITION_NOT_MET",
          message: "같은 설비·품목의 확정 생산량과 기간이 겹칩니다.",
          details: {
            reason: "PERIOD_OVERLAP",
            conflicts: [
              {
                id: 9,
                sourceKey: "MAN-20260920-001",
                startDate: "2026-09-20",
                endDate: "2026-09-21",
              },
            ],
          },
        })
      }
    />,
  );
  expect(
    screen.getByText("MAN-20260920-001 · 2026-09-20 · 2026-09-21"),
  ).toBeVisible();
});
