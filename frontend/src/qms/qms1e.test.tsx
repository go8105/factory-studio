// QMS-1e 화면: Q-09 고객 클레임, Q-10 공급처 품질.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
            data: ["core", "mes", "erp", "qms"].map((m) => ({
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

const claim = {
  id: 4,
  claimNo: "CL-20260924-001",
  customerCode: "CUST-001",
  receivedOn: "2026-09-24",
  itemCode: "FG-C100",
  lotNo: "LT-0013",
  qty: "20.000",
  severity: "MAJOR",
  description: "핀이 휘어 체결이 되지 않습니다.",
  returnRef: null,
  status: "RECEIVED",
  response: null,
  respondedOn: null,
  closedAt: null,
  crmInquiryNo: null,
  ncrCount: 0,
};
const trace = {
  lotNo: "LT-0013",
  itemCode: "FG-C100",
  itemName: "커넥터 C100",
  orderNo: "WO-001",
  status: "completed",
  materials: [
    {
      itemCode: "RM-PBT",
      itemName: "PBT 수지",
      lotNo: null,
      qty: "30.000",
      unit: "KG",
      processCode: "INJ",
      issuedAt: "2026-09-20T01:00:00+00:00",
    },
  ],
  parents: [],
  children: [],
  usedIn: [],
};

it("접수 상태에서는 조사 시작만 내고 회신·종결은 내지 않는다", async () => {
  mount("/qms/claims", {
    [`GET ${Q}/claims`]: ok([claim]),
    [`GET ${Q}/claims/4`]: ok({
      ...claim,
      ncrs: [],
      trace: null,
      mesEnabled: true,
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(
    await screen.findByRole("button", { name: "조사 시작" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "회신" })).toBeNull();
  expect(screen.queryByRole("button", { name: "종결" })).toBeNull();
});

it("조사를 시작하지 않았으면 부적합이 없다고 알린다", async () => {
  mount("/qms/claims", {
    [`GET ${Q}/claims`]: ok([claim]),
    [`GET ${Q}/claims/4`]: ok({
      ...claim,
      ncrs: [],
      trace: null,
      mesEnabled: true,
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(
    await screen.findByText(/아직 조사를 시작하지 않았습니다/),
  ).toBeInTheDocument();
});

it("LOT 계보가 오면 투입 자재를 보여 준다", async () => {
  mount("/qms/claims", {
    [`GET ${Q}/claims`]: ok([claim]),
    [`GET ${Q}/claims/4`]: ok({ ...claim, ncrs: [], trace, mesEnabled: true }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(await screen.findByText("RM-PBT PBT 수지")).toBeInTheDocument();
  expect(screen.getByText("30 KG")).toBeInTheDocument();
});

it("MES를 끄면 LOT 계보를 못 읽는다고 알린다", async () => {
  mount("/qms/claims", {
    [`GET ${Q}/claims`]: ok([claim]),
    [`GET ${Q}/claims/4`]: ok({
      ...claim,
      ncrs: [],
      trace: null,
      mesEnabled: false,
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(
    await screen.findByText(/MES를 사용하지 않아 LOT 계보를 읽을 수 없습니다/),
  ).toBeInTheDocument();
});

it("MES는 켜져 있는데 없는 LOT이면 다른 안내를 낸다", async () => {
  mount("/qms/claims", {
    [`GET ${Q}/claims`]: ok([claim]),
    [`GET ${Q}/claims/4`]: ok({
      ...claim,
      ncrs: [],
      trace: null,
      mesEnabled: true,
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(
    await screen.findByText(/MES에 LT-0013 LOT이 없습니다/),
  ).toBeInTheDocument();
});

it("조사 시작은 확인한 내용만 보낸다", async () => {
  const fetcher = mount("/qms/claims", {
    [`GET ${Q}/claims`]: ok([claim]),
    [`GET ${Q}/claims/4`]: ok({
      ...claim,
      ncrs: [],
      trace: null,
      mesEnabled: true,
    }),
    [`POST ${Q}/claims/4/investigation`]: ok({
      ...claim,
      status: "INVESTIGATING",
      ncrId: 7,
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  fireEvent.click(await screen.findByRole("button", { name: "조사 시작" }));
  fireEvent.change(await screen.findByLabelText("확인한 내용"), {
    target: { value: "치수를 재니 상한을 벗어났습니다" },
  });
  fireEvent.click(screen.getAllByRole("button", { name: "조사 시작" }).at(-1)!);
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/investigation")).toHaveLength(1),
  );
  expect(
    JSON.parse(String(sent(fetcher, "POST", "/investigation")[0][1]?.body)),
  ).toEqual({ description: "치수를 재니 상한을 벗어났습니다" });
});

const level = {
  id: 1,
  partnerCode: "SUP-001",
  itemCode: null,
  level: "TIGHTENED",
  validFrom: "2026-09-20",
  reason: "연속 불합격",
  ratingId: null,
  ratingMonth: null,
  grade: null,
  isCurrent: true,
};
const rating = {
  id: 3,
  ratingMonth: "2026-09",
  partnerCode: "SUP-001",
  lotCount: 4,
  failedLotCount: 2,
  defectPpm: "50000.0",
  scarCount: 1,
  grade: "D",
  suggestedLevel: "TIGHTENED",
};
const scar = {
  id: 6,
  scarNo: "SC-20260924-001",
  partnerCode: "SUP-001",
  inspectionId: null,
  inspectionNo: null,
  ncrId: null,
  ncrNo: null,
  issuedOn: "2026-09-24",
  dueOn: "2026-10-10",
  response: null,
  respondedOn: null,
  status: "OPEN",
  closedAt: null,
};

function mountSuppliers(extra: Record<string, Reply> = {}) {
  return mount("/qms/suppliers", {
    [`GET ${Q}/supplier-levels`]: ok([level]),
    [`GET ${Q}/supplier-ratings`]: ok([rating]),
    [`GET ${Q}/scars`]: ok([scar]),
    [`GET ${Q}/suppliers`]: ok([
      {
        partnerCode: "SUP-001",
        partnerName: "대한수지",
        partnerKind: "SUPPLIER",
      },
    ]),
    ...extra,
  });
}

it("검사 수준 행은 품목 범위·수준·현재 여부를 함께 보여 준다", async () => {
  mountSuppliers();
  const cell = await screen.findByText("SUP-001");
  const row = cell.closest("tr")!;
  // 품목을 비운 행은 "전체", 지금 적용 중인 행은 "현재"로 읽힌다.
  expect(row).toHaveTextContent("전체");
  expect(row).toHaveTextContent("강화");
  expect(row).toHaveTextContent("현재");
});

it("전환 제안을 누르면 사유가 채워진 검사 수준 입력이 열린다", async () => {
  mountSuppliers();
  fireEvent.click(await screen.findByRole("button", { name: "월 평가" }));
  fireEvent.click(await screen.findByRole("button", { name: "강화로 확정" }));
  expect(await screen.findByLabelText("사유")).toHaveValue(
    "2026-09 평가 D등급 제안",
  );
});

it("평가할 대상이 없으면 0건이 아니라 '수입 검사가 없다'고 알린다", async () => {
  const fetcher = mountSuppliers({
    [`POST ${Q}/supplier-ratings`]: ok({ month: "2026-09", partners: [] }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "월 평가" }));
  fireEvent.change(await screen.findByLabelText("평가 월"), {
    target: { value: "2026-09" },
  });
  fireEvent.click(screen.getByRole("button", { name: "이 달 평가 계산" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/supplier-ratings")).toHaveLength(1),
  );
  expect(
    await screen.findByText(/확정한 수입 검사가 없어 평가할 공급처가 없습니다/),
  ).toBeInTheDocument();
});

it("발행한 시정 요구는 회신만, 회신받은 것은 종결만 낸다", async () => {
  mountSuppliers();
  fireEvent.click(await screen.findByRole("button", { name: "시정 요구" }));
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(
    await screen.findByRole("button", { name: "회신 입력" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "종결" })).toBeNull();
  expect(screen.getByText(/아직 회신을 받지 않았습니다/)).toBeInTheDocument();
});
