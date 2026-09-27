// FS-018m F-09 사업장·공간. 검증 항목별로 테스트를 나눈다.
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};

const sites = [
  { id: 1, siteCode: "S01", name: "본사 공장", timezone: "Asia/Seoul" },
  { id: 2, siteCode: "S02", name: "제2공장", timezone: "Asia/Seoul" },
];
const places = [
  {
    id: 1,
    siteId: 1,
    parentLocationId: null,
    locationCode: "L-INJ",
    name: "사출동",
    kind: "workcenter",
  },
  {
    id: 4,
    siteId: 1,
    parentLocationId: 1,
    locationCode: "L-UTL",
    name: "유틸리티실",
    kind: "zone",
  },
  {
    id: 9,
    siteId: 2,
    parentLocationId: null,
    locationCode: "L-B2",
    name: "2공장 본관",
    kind: "building",
  },
];

type Reply = { status: number; body?: unknown };

function mockApi(replies: Record<string, Reply> = {}, siteRows = sites) {
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
        : url.endsWith("/workspace/modules")
          ? ["core", "mes", "erp", "fems"].map((moduleKey) => ({
              moduleKey,
              enabled: true,
              updatedAt: null,
            }))
          : url.endsWith("/sites")
            ? siteRows
            : places;
      return new Response(JSON.stringify({ data }), { status: 200 });
    });
}

function show() {
  render(
    <MemoryRouter initialEntries={["/fems/sites"]}>
      <App />
    </MemoryRouter>,
  );
}

const sent = (fetcher: ReturnType<typeof mockApi>, method: string) =>
  fetcher.mock.calls.filter(([, init]) => init?.method === method);

async function row(table: string, code: string) {
  const t = await screen.findByRole("table", { name: table });
  return within(t).getByRole("row", { name: new RegExp(`^${code}`) });
}

it("사이드바 기준정보에 F-09가 있다", async () => {
  mockApi();
  show();
  const menu = await screen.findByRole("complementary", { name: "FEMS 메뉴" });
  expect(menu.querySelector('a[href="/fems/sites"]')).not.toBeNull();
});

it("FEMS 전용 데이터임을 안내한다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByText(/MES의 사업장·공간과 코드가 같아도/),
  ).toBeVisible();
});

it("공간 목록은 사업장과 상위 공간을 보여준다", async () => {
  mockApi();
  show();
  const utl = await row("공간 목록", "L-UTL");
  expect(utl).toHaveTextContent("본사 공장");
  expect(utl).toHaveTextContent("L-INJ");
  expect(utl).toHaveTextContent("구역");
});

it("사업장 등록은 대문자 코드와 기본 시간대로 보낸다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/fems/sites": { status: 201, body: { data: sites[1] } },
  });
  show();
  fireEvent.click(await screen.findByRole("button", { name: "사업장 등록" }));
  const form = await screen.findByRole("form", { name: "사업장 등록" });
  fireEvent.change(within(form).getByLabelText("사업장 코드"), {
    target: { value: "s03" },
  });
  fireEvent.change(within(form).getByLabelText("사업장명"), {
    target: { value: "제3공장" },
  });
  fireEvent.click(within(form).getByRole("button", { name: "등록" }));
  await waitFor(() => expect(sent(fetcher, "POST")).toHaveLength(1));
  const init = sent(fetcher, "POST")[0][1]!;
  expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("test-csrf");
  expect(new Headers(init.headers).get("Idempotency-Key")).toBeTruthy();
  expect(JSON.parse(String(init.body))).toEqual({
    siteCode: "S03",
    name: "제3공장",
    timezone: "Asia/Seoul",
  });
});

it("시간대 잠금 오류를 보여준다", async () => {
  mockApi({
    "PATCH /api/v1/fems/sites/1": {
      status: 409,
      body: {
        error: {
          code: "PRECONDITION_NOT_MET",
          message:
            "기록이 있는 사업장은 시간대를 바꿀 수 없습니다. 날짜 경계가 달라져 지난 합계가 바뀝니다.",
          details: { reason: "TIMEZONE_IN_USE", references: [] },
        },
      },
    },
  });
  show();
  fireEvent.click(
    within(await row("사업장 목록", "S01")).getByRole("button", {
      name: "수정",
    }),
  );
  fireEvent.change(screen.getByLabelText("시간대"), {
    target: { value: "Asia/Tokyo" },
  });
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  expect(
    await screen.findByText(/기록이 있는 사업장은 시간대를 바꿀 수 없습니다/),
  ).toBeVisible();
});

it("상위 공간 선택지는 같은 사업장의 다른 공간만 보여준다", async () => {
  mockApi();
  show();
  fireEvent.click(
    within(await row("공간 목록", "L-INJ")).getByRole("button", {
      name: "수정",
    }),
  );
  const parent = screen.getByLabelText("상위 공간");
  expect(parent).toHaveTextContent("L-UTL");
  expect(parent).not.toHaveTextContent("L-INJ 사출동");
  expect(parent).not.toHaveTextContent("L-B2");
});

it("공간 수정은 사업장을 잠그고 바뀐 값만 보낸다", async () => {
  const fetcher = mockApi({
    "PATCH /api/v1/fems/locations/4": {
      status: 200,
      body: { data: places[1] },
    },
  });
  show();
  fireEvent.click(
    within(await row("공간 목록", "L-UTL")).getByRole("button", {
      name: "수정",
    }),
  );
  expect(screen.getByLabelText("사업장")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("공간명"), {
    target: { value: "유틸리티동" },
  });
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
  await waitFor(() =>
    expect(JSON.parse(String(sent(fetcher, "PATCH")[0][1]!.body))).toEqual({
      name: "유틸리티동",
    }),
  );
});

it("공간 등록은 선택한 사업장으로 보낸다", async () => {
  const fetcher = mockApi({
    "POST /api/v1/fems/locations": { status: 201, body: { data: places[2] } },
  });
  show();
  fireEvent.click(await screen.findByRole("button", { name: "공간 등록" }));
  const form = await screen.findByRole("form", { name: "공간 등록" });
  fireEvent.change(within(form).getByLabelText("사업장"), {
    target: { value: "2" },
  });
  fireEvent.change(within(form).getByLabelText("공간 코드"), {
    target: { value: "l-b3" },
  });
  fireEvent.change(within(form).getByLabelText("공간명"), {
    target: { value: "별관" },
  });
  fireEvent.click(within(form).getByRole("button", { name: "등록" }));
  await waitFor(() =>
    expect(JSON.parse(String(sent(fetcher, "POST")[0][1]!.body))).toEqual({
      siteId: 2,
      parentLocationId: null,
      locationCode: "L-B3",
      name: "별관",
      kind: "zone",
    }),
  );
});

it("삭제가 막히면 참조 건수를 보여준다", async () => {
  mockApi({
    "DELETE /api/v1/fems/locations/1": {
      status: 409,
      body: {
        error: {
          code: "REFERENCED_BY_OTHERS",
          message: "하위 공간·설비·계측기가 있는 공간은 삭제할 수 없습니다.",
          details: {
            references: [{ table: "fems.equipment", label: "설비", count: 3 }],
          },
        },
      },
    },
  });
  show();
  const inj = await row("공간 목록", "L-INJ");
  fireEvent.click(within(inj).getByRole("button", { name: "삭제" }));
  fireEvent.click(within(inj).getByRole("button", { name: "삭제 확정" }));
  expect(await screen.findByText("설비 3건")).toBeVisible();
});

it("사업장이 없으면 공간 등록 대신 안내한다", async () => {
  mockApi({}, []);
  show();
  expect(
    await screen.findByText("공간은 사업장을 먼저 등록한 뒤 추가합니다."),
  ).toBeVisible();
  expect(screen.queryByRole("form", { name: "공간 등록" })).toBeNull();
});

it("F-09 도움말로 연결된다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("link", { name: "사업장·공간 도움말" }),
  ).toHaveAttribute("href", "/help/fems/f-09");
});
