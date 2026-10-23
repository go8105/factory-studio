// QMS-1c 화면: Q-11 계측기·교정, Q-12 4M 변경.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const Q = "/api/v1/qms";
type Reply = { status: number; body?: unknown };
const ok = (data: unknown, page?: unknown): Reply => ({
  status: 200,
  body: page ? { data, page } : { data },
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
      if (url.endsWith("/workspace/modules"))
        return new Response(
          JSON.stringify({
            data: ["core", "mes", "qms"].map((m) => ({
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

const gauge = {
  id: 7,
  code: "CAL-001",
  name: "버니어 캘리퍼스",
  gaugeKind: "버니어 캘리퍼스",
  measureRange: "0~150 mm",
  resolution: "0.01 mm",
  calibrationCycleDays: 365,
  status: "ACTIVE",
  lastCalibratedOn: "2026-09-01",
  nextDueOn: "2026-10-01",
  lastResult: "PASS",
  dueState: "SOON",
  dueInDays: 7,
};

it("교정 도래가 임박하면 남은 날과 기한을 배지로 알린다", async () => {
  mount("/qms/gauges", { [`GET ${Q}/gauges`]: ok([gauge], { total: 1 }) });
  expect(await screen.findByText("CAL-001")).toBeInTheDocument();
  expect(screen.getByText("7일 남음 · 2026-10-01")).toBeInTheDocument();
});

it("교정 기록이 없으면 0이 아니라 '기록 없음'이다", async () => {
  mount("/qms/gauges", {
    [`GET ${Q}/gauges`]: ok(
      [
        {
          ...gauge,
          lastCalibratedOn: null,
          nextDueOn: null,
          lastResult: null,
          dueState: "NONE",
          dueInDays: null,
        },
      ],
      { total: 1 },
    ),
  });
  expect(await screen.findByText("기록 없음")).toBeInTheDocument();
});

it("폐기한 계측기는 교정 등록 버튼이 잠긴다", async () => {
  mount("/qms/gauges", {
    [`GET ${Q}/gauges`]: ok([{ ...gauge, status: "RETIRED" }], { total: 1 }),
    [`GET ${Q}/gauges/7`]: ok({
      ...gauge,
      status: "RETIRED",
      calibrations: [],
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  const button = await screen.findByRole("button", { name: "교정 등록" });
  expect(button).toBeDisabled();
});

it("교정 기한을 비워 두면 null로 보내 주기로 계산하게 한다", async () => {
  const fetcher = mount("/qms/gauges", {
    [`GET ${Q}/gauges`]: ok([gauge], { total: 1 }),
    [`GET ${Q}/gauges/7`]: ok({ ...gauge, calibrations: [] }),
    [`POST ${Q}/gauges/7/calibrations`]: {
      status: 201,
      body: { data: { id: 1, gaugeStatus: "ACTIVE" } },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  fireEvent.click(await screen.findByRole("button", { name: "교정 등록" }));
  fireEvent.change(await screen.findByLabelText("교정일"), {
    target: { value: "2026-09-24" },
  });
  fireEvent.click(screen.getByRole("button", { name: "기록" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/calibrations")).toHaveLength(1),
  );
  const body = JSON.parse(
    String(sent(fetcher, "POST", "/calibrations")[0][1]?.body),
  );
  expect(body).toMatchObject({ calibratedOn: "2026-09-24", nextDueOn: null });
});

const notice = {
  id: 3,
  cnNo: "CN-20260924-001",
  changeType: "MATERIAL",
  itemCode: "FG-C100",
  description: "수지 공급처를 바꿉니다.",
  requestedOn: "2026-09-24",
  effectiveOn: "2026-10-01",
  status: "APPROVED",
  decidedAt: "2026-09-24T02:00:00+00:00",
  decisionNote: "적용 승인",
  firstArticleInspectionId: null,
  firstArticleNo: null,
  firstArticleResult: null,
  plmEcoNo: null,
};
const article = {
  id: 11,
  inspectionNo: "QI-20260924-001",
  lotNo: "FA-001",
  status: "confirmed",
  result: "PASS",
  inspectedOn: "2026-09-24",
};

it("신청 중에는 승인·반려를 내고 초품 검사는 내지 않는다", async () => {
  mount("/qms/change-notices", {
    [`GET ${Q}/change-notices`]: ok([{ ...notice, status: "REQUESTED" }]),
    [`GET ${Q}/change-notices/3`]: ok({
      ...notice,
      status: "REQUESTED",
      decidedAt: null,
      decisionNote: null,
      firstArticles: [],
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(
    await screen.findByRole("button", { name: "승인·반려" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "초품 검사 만들기" })).toBeNull();
});

it("승인했지만 합격 초품이 없으면 확인 완료가 아니라 안내를 보여 준다", async () => {
  mount("/qms/change-notices", {
    [`GET ${Q}/change-notices`]: ok([notice]),
    [`GET ${Q}/change-notices/3`]: ok({
      ...notice,
      firstArticles: [{ ...article, status: "draft", result: null }],
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(
    await screen.findByText(/합격한 초품 검사가 없어 확인 완료할 수 없습니다/),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "확인 완료" })).toBeNull();
});

it("확정·합격한 초품 검사만 확인 완료로 닫는다", async () => {
  const fetcher = mount("/qms/change-notices", {
    [`GET ${Q}/change-notices`]: ok([notice]),
    [`GET ${Q}/change-notices/3`]: ok({ ...notice, firstArticles: [article] }),
    [`POST ${Q}/change-notices/3/verification`]: ok({
      ...notice,
      status: "VERIFIED",
      firstArticleNo: article.inspectionNo,
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  fireEvent.click(await screen.findByRole("button", { name: "확인 완료" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/verification")).toHaveLength(1),
  );
  expect(
    JSON.parse(String(sent(fetcher, "POST", "/verification")[0][1]?.body)),
  ).toEqual({ firstArticleInspectionId: 11 });
});

it("반려를 고르면 의견이 필요하다고 알린다", async () => {
  mount("/qms/change-notices", {
    [`GET ${Q}/change-notices`]: ok([{ ...notice, status: "REQUESTED" }]),
    [`GET ${Q}/change-notices/3`]: ok({
      ...notice,
      status: "REQUESTED",
      decidedAt: null,
      firstArticles: [],
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  fireEvent.click(await screen.findByRole("button", { name: "승인·반려" }));
  fireEvent.click(await screen.findByRole("radio", { name: "반려" }));
  expect(screen.getByText("반려에는 의견이 필요합니다.")).toBeInTheDocument();
});

it("마지막 교정이 불합격이면 남은 날이 아니라 재교정 필요로 보인다", async () => {
  mount("/qms/gauges", {
    [`GET ${Q}/gauges`]: ok(
      [
        {
          ...gauge,
          status: "REPAIR",
          lastCalibratedOn: "2026-09-20",
          lastResult: "FAIL",
          dueState: "OK",
          dueInDays: 300,
        },
      ],
      { total: 1 },
    ),
  });
  expect(
    await screen.findByText("재교정 필요 · 2026-09-20"),
  ).toBeInTheDocument();
});
