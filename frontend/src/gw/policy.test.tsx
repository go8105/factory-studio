import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { Authority } from "./Authority";
import { Documents } from "./Documents";
import { Events } from "./ui";
import { RoleContext } from "./common";
vi.mock("../app/session", () => ({
  useSession: () => ({
    session: { workspaceId: 1, generationId: 2, csrfToken: "synthetic" },
    fail: vi.fn(),
  }),
}));
const reply = (data: unknown) =>
  new Response(JSON.stringify({ data, page: { total: 1 } }), { status: 200 });
it("authority PATCH includes the read version and only changed policy fields", async () => {
  const rule = {
    id: 1,
    code: "SMALL",
    documentKind: "GENERAL",
    currency: "KRW",
    amountFrom: "0",
    amountTo: "100",
    finalSeq: 1,
    effectiveFrom: "2026-10",
    effectiveTo: null,
    isActive: true,
    version: 7,
  };
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (_url, init) =>
      reply(
        init?.method === "PATCH"
          ? { ...rule, finalSeq: 2, version: 8 }
          : [rule],
      ),
    );
  render(
    <MemoryRouter>
      <Authority />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "수정" }));
  fireEvent.change(screen.getByLabelText("최종 결재 단계"), {
    target: { value: "2" },
  });
  fireEvent.click(screen.getByRole("button", { name: "수정 저장" }));
  await waitFor(() =>
    expect(fetch.mock.calls.some(([, i]) => i?.method === "PATCH")).toBe(true),
  );
  const body = fetch.mock.calls.find(([, i]) => i?.method === "PATCH")![1]
    ?.body;
  expect(JSON.parse(String(body))).toEqual({ finalSeq: 2, expectedVersion: 7 });
});
it("delegated approval sends the selected original assignment and current document version", async () => {
  const doc = {
    id: "10",
    documentNo: "GW-10",
    title: "병렬 검토",
    body: "합성",
    kind: "GENERAL",
    status: "IN_REVIEW",
    version: 4,
    drafterId: "1",
    drafterName: "기안자",
    routeId: "3",
    routeName: "병렬",
    currentStep: 1,
    roundNo: 1,
    amount: "100",
    currency: "KRW",
    sourceSnapshot: null,
    sourceComparison: null,
    steps: [
      {
        id: "20",
        personId: "2",
        personName: "원 담당자 A",
        seq: 1,
        participantRole: "APPROVER",
        status: "WAITING",
      },
      {
        id: "21",
        personId: "3",
        personName: "원 담당자 B",
        seq: 1,
        participantRole: "APPROVER",
        status: "WAITING",
      },
    ],
    events: [],
    availableActions: ["approve"],
    actionSteps: [
      {
        stepId: "20",
        personName: "원 담당자 A",
        participantRole: "APPROVER",
        delegationId: "8",
      },
      {
        stepId: "21",
        personName: "원 담당자 B",
        participantRole: "APPROVER",
        delegationId: "9",
      },
    ],
  };
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (url, init) =>
      reply(
        String(url).includes("/comments?")
          ? []
          : String(url).includes("/documents/10")
            ? init?.method === "POST"
              ? { ...doc, version: 5, availableActions: [] }
              : doc
            : { rows: [doc], total: 1, offset: 0, limit: 20 },
      ),
    );
  render(
    <MemoryRouter initialEntries={["/gw/pending?open=10"]}>
      <RoleContext.Provider
        value={{ person: "6", setPerson: vi.fn(), people: [], reload: vi.fn() }}
      >
        <Documents box="pending" />
      </RoleContext.Provider>
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "승인" }));
  fireEvent.change(screen.getByLabelText("처리할 참여자"), {
    target: { value: "21" },
  });
  fireEvent.click(screen.getByRole("button", { name: "확정" }));
  await waitFor(() =>
    expect(fetch.mock.calls.some(([, i]) => i?.method === "POST")).toBe(true),
  );
  expect(
    JSON.parse(
      String(fetch.mock.calls.find(([, i]) => i?.method === "POST")![1]?.body),
    ),
  ).toEqual({
    actingPersonId: "6",
    expectedVersion: 4,
    stepId: "21",
    reason: "",
  });
});
it("reference opinion and delegation retain distinct visible evidence", () => {
  render(
    <MemoryRouter>
      <Events
        rows={[
          {
            id: "1",
            eventSeq: 1,
            eventType: "CONSENTED",
            personName: "대리 담당자",
            actorKind: "GUEST",
            reason: "검토",
            createdAt: "2026-10-09T01:00:00Z",
            onBehalfOfPersonId: "2",
            details: {
              participantRole: "REFERENCE",
              originalPersonName: "원 담당자",
            },
          },
        ]}
      />
    </MemoryRouter>,
  );
  expect(screen.getByText("참고 의견")).toBeInTheDocument();
  expect(
    screen.getByText("대리 담당자 (위임 · 원 담당자 원 담당자)"),
  ).toBeInTheDocument();
});
