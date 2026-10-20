// CMMS-1c 화면 — C-05 설비 대장(계층·가져오기)·C-09 고장 코드.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const C = "/api/v1/cmms";
type Reply = { status: number; body?: unknown };
const ok = (data: unknown, status = 200): Reply => ({ status, body: { data } });
const fail = (
  status: number,
  code: string,
  details: unknown,
  message = "요청을 처리할 수 없습니다.",
): Reply => ({
  status,
  body: { error: { code, message, details } },
});

function mount(path: string, replies: Record<string, Reply> = {}) {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input).split("?")[0];
      const query = String(input).includes("source=BEMS") ? ":BEMS" : "";
      const reply =
        replies[`${init?.method ?? "GET"} ${url}${query}`] ??
        replies[`${init?.method ?? "GET"} ${url}`];
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

const node = (
  id: number,
  code: string,
  depth: number,
  extra: Record<string, unknown> = {},
) => ({
  id,
  code,
  name: `${code} 설비`,
  assetType: "INJECTION",
  location: null,
  source: "CMMS",
  sourceCode: null,
  parentAssetId: null,
  criticality: null,
  isActive: true,
  depth,
  ...extra,
});

it("C-05 설비 대장: 계층을 들여 쓰고 출처를 보여 준다", async () => {
  mount("/cmms/assets", {
    [`GET ${C}/assets/tree`]: ok([
      node(1, "LINE-A", 0, { assetType: "LINE" }),
      node(2, "INJ-A1", 1, { parentAssetId: 1, criticality: "A" }),
      node(3, "HV-01", 0, {
        assetType: "HVAC",
        source: "BEMS",
        sourceCode: "HV-01",
        location: "사무동",
      }),
    ]),
  });
  expect(await screen.findByRole("button", { name: "LINE-A" })).toBeVisible();
  expect(screen.getByText("라인")).toBeVisible();
  expect(screen.getByText("BEMS 공조기")).toBeVisible();
  // 하위 설비는 들여쓰기로 계층을 나타낸다.
  const child = screen.getByRole("button", { name: "INJ-A1" }).parentElement!;
  expect(child).toHaveStyle({ paddingLeft: "16px" });
  expect(screen.getByText("A")).toBeVisible();
});

it("C-05 가져오기: 고른 원천 코드만 보내고, 원천이 꺼져 있으면 안내한다", async () => {
  const fetcher = mount("/cmms/assets", {
    [`GET ${C}/assets/tree`]: ok([]),
    [`GET ${C}/assets/import-candidates`]: ok([
      {
        sourceCode: "INJ-01",
        name: "사출기 1",
        assetType: "INJECTION",
        location: "1층",
      },
      {
        sourceCode: "INJ-02",
        name: "사출기 2",
        assetType: "INJECTION",
        location: "1층",
      },
    ]),
    [`GET ${C}/assets/import-candidates:BEMS`]: fail(
      409,
      "PRECONDITION_NOT_MET",
      { reason: "SOURCE_MODULE_DISABLED", sourceModule: "bems" },
      "BEMS를 사용하지 않도록 설정했습니다. 설비를 직접 등록할 수는 있습니다.",
    ),
    [`POST ${C}/assets/import`]: ok({ created: 1, skipped: [], ids: [9] }, 201),
  });
  fireEvent.click(await screen.findByRole("button", { name: "가져오기" }));
  expect(await screen.findByLabelText(/INJ-01/)).toBeInTheDocument();
  // 아무것도 고르지 않으면 보낼 수 없다.
  expect(screen.getByRole("button", { name: "대장에 넣기" })).toBeDisabled();
  fireEvent.click(screen.getByLabelText(/INJ-02/));
  fireEvent.click(screen.getByRole("button", { name: "1건 대장에 넣기" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/assets/import")).toHaveLength(1),
  );
  expect(body(sent(fetcher, "POST", "/assets/import")[0])).toEqual({
    source: "MES",
    sourceCodes: ["INJ-02"],
  });

  fireEvent.change(screen.getByLabelText("원천"), {
    target: { value: "BEMS" },
  });
  expect(await screen.findByText(/사용하지 않도록 설정했습니다/)).toBeVisible();
});

it("C-05 가져온 설비는 코드·이름·종류를 바꿀 수 없다", async () => {
  mount("/cmms/assets", {
    [`GET ${C}/assets/tree`]: ok([
      node(3, "HV-01", 0, {
        assetType: "HVAC",
        source: "BEMS",
        sourceCode: "HV-01",
      }),
    ]),
    [`GET ${C}/assets/3`]: ok({
      ...node(3, "HV-01", 0, {
        assetType: "HVAC",
        source: "BEMS",
        sourceCode: "HV-01",
      }),
      manufacturer: null,
      model: null,
      serialNo: null,
      installedOn: null,
      acquisitionCost: null,
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "HV-01" }));
  expect(await screen.findByText(/원천에서 가져온 설비라/)).toBeVisible();
  expect(screen.getByLabelText("설비명")).toBeDisabled();
  expect(screen.getByLabelText("종류")).toBeDisabled();
  // 상세·중요도·계층은 CMMS에서 정하므로 열려 있다.
  expect(screen.getByLabelText("제조사")).toBeEnabled();
  expect(screen.getByLabelText("중요도")).toBeEnabled();
});

it("C-09 고장 코드: 구분과 원인 분류를 함께 보낸다", async () => {
  const fetcher = mount("/cmms/failure-codes", {
    [`GET ${C}/failure-codes`]: ok([
      {
        id: 1,
        kind: "CAUSE",
        code: "BEARING",
        name: "베어링 마모",
        causeCategory: "WEAR",
        isActive: true,
      },
    ]),
    [`POST ${C}/failure-codes`]: ok({ id: 2 }, 201),
  });
  expect(await screen.findByText("베어링 마모")).toBeVisible();
  expect(screen.getByText("마모")).toBeVisible();
  expect(screen.getByText("원인")).toBeVisible();

  fireEvent.click(screen.getByRole("button", { name: "고장 코드 등록" }));
  fireEvent.change(screen.getByLabelText("구분"), {
    target: { value: "CAUSE" },
  });
  fireEvent.change(screen.getByLabelText("코드"), {
    target: { value: "LOOSE" },
  });
  fireEvent.change(screen.getByLabelText("이름"), {
    target: { value: "체결 풀림" },
  });
  fireEvent.change(screen.getByLabelText("원인 분류"), {
    target: { value: "SETTING" },
  });
  fireEvent.click(screen.getByRole("button", { name: "등록" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/failure-codes")).toHaveLength(1),
  );
  const saved = body(sent(fetcher, "POST", "/failure-codes")[0]);
  expect(saved.kind).toBe("CAUSE");
  expect(saved.causeCategory).toBe("SETTING");
});
