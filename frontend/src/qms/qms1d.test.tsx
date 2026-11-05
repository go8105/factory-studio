// QMS-1d 화면: Q-07 부적합 보고, Q-08 시정·예방 조치.
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

const ncr = {
  id: 5,
  ncrNo: "NCR-20260924-001",
  origin: "PROCESS",
  itemCode: "FG-C100",
  lotNo: "LT-0013",
  qty: "12.000",
  defectTypeId: null,
  defectCode: null,
  defectName: null,
  description: "핀 피치가 상한을 벗어났습니다.",
  immediateAction: null,
  inspectionId: null,
  inspectionNo: null,
  claimId: null,
  sourceRef: "LT-0013:INJ",
  reportedOn: "2026-09-24",
  status: "OPEN",
  closedAt: null,
  capaCount: 0,
  verifiedCount: 0,
};
const capa = {
  id: 9,
  capaNo: "CA-20260924-001",
  ncrId: 5,
  ncrNo: ncr.ncrNo,
  itemCode: "FG-C100",
  kind: "CORRECTIVE",
  rootCause: "금형 마모",
  action: "금형 교체",
  ownerName: "김정비",
  dueOn: "2026-10-10",
  status: "OPEN",
  doneAt: null,
  verifiedAt: null,
  verificationNote: null,
  ownerHrCode: null,
};

it("조치가 없으면 '없음'으로 보이고 종결을 눌러도 서버가 막는 것을 안내한다", async () => {
  mount("/qms/ncrs", {
    [`GET ${Q}/ncrs`]: ok([ncr]),
    [`GET ${Q}/ncrs/5`]: ok({ ...ncr, capas: [] }),
  });
  expect(await screen.findByText("NCR-20260924-001")).toBeInTheDocument();
  expect(screen.getByText("없음")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "상세" }));
  expect(
    await screen.findByText(/조치가 없습니다. 조치를 추가하고/),
  ).toBeInTheDocument();
});

it("조치 확인 진행도를 '확인한 수/전체'로 보여 준다", async () => {
  mount("/qms/ncrs", {
    [`GET ${Q}/ncrs`]: ok([{ ...ncr, capaCount: 3, verifiedCount: 1 }]),
  });
  expect(await screen.findByText("1/3 확인")).toBeInTheDocument();
});

it("종결한 보고에는 수정·조치 추가·종결 버튼을 내지 않는다", async () => {
  mount("/qms/ncrs", {
    [`GET ${Q}/ncrs`]: ok([{ ...ncr, status: "CLOSED" }]),
    [`GET ${Q}/ncrs/5`]: ok({
      ...ncr,
      status: "CLOSED",
      closedAt: "2026-09-24T05:00:00+00:00",
      capaCount: 1,
      verifiedCount: 1,
      capas: [{ ...capa, status: "VERIFIED" }],
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(await screen.findByText("CA-20260924-001")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "종결" })).toBeNull();
  expect(screen.queryByRole("button", { name: "조치 추가" })).toBeNull();
});

it("공정 불량을 근거로 고르면 품목·LOT·수량이 그 자리에서 채워진다", async () => {
  mount("/qms/ncrs", {
    [`GET ${Q}/ncrs`]: ok([]),
    [`GET ${Q}/ncrs/sources`]: ok({
      mesEnabled: true,
      rows: [
        {
          sourceRef: "LT-0013:INJ",
          lotNo: "LT-0013",
          itemCode: "FG-C100",
          itemName: "커넥터 C100",
          processCode: "INJ",
          defectQty: "12.000",
          unit: "EA",
          reason: "핀 변형",
          confirmedAt: "2026-09-20T01:00:00+00:00",
        },
      ],
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "부적합 보고" }));
  fireEvent.change(await screen.findByLabelText(/근거/), {
    target: { value: "LT-0013:INJ" },
  });
  await waitFor(() =>
    expect(screen.getByLabelText("품목 코드")).toHaveValue("FG-C100"),
  );
  expect(screen.getByLabelText("부적합 수량")).toHaveValue("12.000");
  expect(screen.getByLabelText("LOT (선택)")).toHaveValue("LT-0013");
});

it("MES를 끄면 공정 불량을 못 읽는다고 알리고 직접 입력을 안내한다", async () => {
  mount("/qms/ncrs", {
    [`GET ${Q}/ncrs`]: ok([]),
    [`GET ${Q}/ncrs/sources`]: ok({ mesEnabled: false, rows: [] }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "부적합 보고" }));
  expect(
    await screen.findByText(/MES를 사용하지 않아 공정 불량을 읽을 수 없습니다/),
  ).toBeInTheDocument();
});

it("진행 중인 조치는 완료만, 완료한 조치는 확인만 낸다", async () => {
  mount("/qms/capas", {
    [`GET ${Q}/capas`]: ok([capa]),
    [`GET ${Q}/capas/9`]: ok(capa),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(
    await screen.findByRole("button", { name: "완료" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "유효성 확인" })).toBeNull();
});

it("무효로 확인하면 새 조치를 만들라고 안내한다", async () => {
  mount("/qms/capas", {
    [`GET ${Q}/capas`]: ok([{ ...capa, status: "INEFFECTIVE" }]),
    [`GET ${Q}/capas/9`]: ok({
      ...capa,
      status: "INEFFECTIVE",
      doneAt: "2026-09-24T01:00:00+00:00",
      verifiedAt: "2026-09-24T02:00:00+00:00",
      verificationNote: "같은 불량 재발",
    }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  expect(
    await screen.findByText(/무효로 확인한 조치입니다/),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "유효성 확인" })).toBeNull();
});

it("유효성 확인은 판정과 내용을 함께 보낸다", async () => {
  const fetcher = mount("/qms/capas", {
    [`GET ${Q}/capas`]: ok([{ ...capa, status: "DONE" }]),
    [`GET ${Q}/capas/9`]: ok({
      ...capa,
      status: "DONE",
      doneAt: "2026-09-24T01:00:00+00:00",
    }),
    [`POST ${Q}/capas/9/verification`]: ok({ ...capa, status: "VERIFIED" }),
  });
  fireEvent.click(await screen.findByRole("button", { name: "상세" }));
  fireEvent.click(await screen.findByRole("button", { name: "유효성 확인" }));
  fireEvent.click(await screen.findByRole("radio", { name: "무효" }));
  fireEvent.change(screen.getByLabelText("확인 내용"), {
    target: { value: "같은 불량 재발" },
  });
  fireEvent.click(screen.getByRole("button", { name: "확인" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/verification")).toHaveLength(1),
  );
  expect(
    JSON.parse(String(sent(fetcher, "POST", "/verification")[0][1]?.body)),
  ).toEqual({ effective: false, note: "같은 불량 재발" });
});
