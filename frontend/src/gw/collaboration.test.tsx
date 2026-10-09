import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { Calendar, Chat, Comments, Notifications } from "./Collaboration";
import { RoleContext } from "./common";
vi.mock("../app/session", () => ({
  useSession: () => ({
    session: { workspaceId: 1, generationId: 1, csrfToken: "synthetic" },
    fail: vi.fn(),
  }),
}));
const reply = (data: unknown) =>
  new Response(JSON.stringify({ data }), { status: 200 });
const people = [
  {
    id: "1",
    code: "P1",
    name: "등록자",
    jobRole: "STAFF",
    isActive: true,
    version: 1,
  },
  {
    id: "2",
    code: "P2",
    name: "참석자",
    jobRole: "STAFF",
    isActive: true,
    version: 1,
  },
];
function show(node: React.ReactNode, person = "1") {
  return render(
    <MemoryRouter>
      <RoleContext.Provider
        value={{
          person,
          setPerson: vi.fn(),
          people,
          reload: vi.fn(),
          setBusy: vi.fn(),
        }}
      >
        {node}
      </RoleContext.Provider>
    </MemoryRouter>,
  );
}
it("comments show append history and edit only with comment version", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (_url, o) =>
      reply(
        o?.method === "POST" || o?.method === "PATCH"
          ? { id: "3" }
          : [
              {
                id: "3",
                authorId: "1",
                authorName: "등록자",
                body: "현재 의견",
                status: "ACTIVE",
                version: 2,
                createdAt: "2026-10-10T00:00:00Z",
                revisions: [
                  {
                    revisionNo: 1,
                    body: "이전 의견",
                    createdAt: "2026-10-09T00:00:00Z",
                  },
                ],
              },
            ],
      ),
    );
  show(<Comments kind="DOCUMENT" id="9" />);
  await screen.findByText("현재 의견");
  fireEvent.click(screen.getByRole("button", { name: "댓글 수정" }));
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "다음 의견" },
  });
  fireEvent.click(screen.getByRole("button", { name: "수정 저장" }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([u, o]) => String(u).endsWith("/comments/3") && o?.method === "PATCH",
      ),
    ).toBe(true),
  );
  const payload = JSON.parse(
    String(fetch.mock.calls.find(([, o]) => o?.method === "PATCH")?.[1]?.body),
  );
  expect(payload).toEqual({
    actingPersonId: "1",
    body: "다음 의견",
    expectedVersion: 2,
  });
  expect(screen.getByText("이전 의견", { exact: false })).toBeInTheDocument();
});
it("deleted comments conceal content and have no edit controls", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    reply([
      {
        id: "4",
        authorId: "1",
        authorName: "등록자",
        body: "",
        status: "DELETED",
        version: 2,
        createdAt: null,
        revisions: [],
      },
    ]),
  );
  show(<Comments kind="POST" id="5" />);
  await screen.findByText("삭제된 댓글입니다.");
  expect(
    screen.queryByRole("button", { name: "댓글 수정" }),
  ).not.toBeInTheDocument();
});
it("notification read links to source and marks selected recipient", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (_u, o) =>
      reply(
        o?.method === "POST" || o?.method === "PATCH"
          ? { id: "7" }
          : [
              {
                id: "7",
                title: "새 결재",
                kind: "APPROVAL_ARRIVED",
                refKind: "DOCUMENT",
                refId: "9",
                createdAt: null,
                readAt: null,
              },
            ],
      ),
    );
  show(<Notifications />);
  expect(await screen.findByRole("link", { name: "새 결재" })).toHaveAttribute(
    "href",
    "/gw/documents?open=9",
  );
  fireEvent.click(screen.getByRole("button", { name: "읽음 표시" }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([u, o]) =>
          String(u).endsWith("/notifications/7/read") && o?.method === "POST",
      ),
    ).toBe(true),
  );
});
it("calendar saves Korean timezone interval and chosen attendees", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (_u, o) =>
      reply(
        o?.method === "POST" || o?.method === "PATCH"
          ? {
              id: "8",
              title: "합성 일정",
              attendees: [],
              ownerId: "1",
              ownerName: "등록자",
              scope: "PERSONAL",
              status: "ACTIVE",
              version: 1,
              startsAt: "2026-10-12T00:00:00Z",
              endsAt: "2026-10-12T01:00:00Z",
              allDay: false,
            }
          : [],
      ),
    );
  show(<Calendar />);
  fireEvent.click(screen.getByRole("button", { name: "새 일정" }));
  fireEvent.change(screen.getByLabelText("일정 제목"), {
    target: { value: "합성 일정" },
  });
  fireEvent.change(screen.getByLabelText("시작 (한국 시간)"), {
    target: { value: "2026-10-12T09:00" },
  });
  fireEvent.change(screen.getByLabelText("끝 (한국 시간)"), {
    target: { value: "2026-10-12T10:00" },
  });
  fireEvent.click(screen.getByRole("checkbox", { name: "참석자" }));
  fireEvent.click(screen.getByRole("button", { name: "일정 저장" }));
  await waitFor(() =>
    expect(fetch.mock.calls.some(([, o]) => o?.method === "POST")).toBe(true),
  );
  const payload = JSON.parse(
    String(fetch.mock.calls.find(([, o]) => o?.method === "POST")?.[1]?.body),
  );
  expect(payload.startsAt).toBe("2026-10-12T00:00:00.000Z");
  expect(payload.attendeeIds).toEqual(["2"]);
});
it("chat retry preserves client key after an uncertain network failure", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (u, o) => {
      if (o?.method === "POST") throw new TypeError("lost");
      if (String(u).includes("/messages"))
        return reply({
          channel: { id: "6", name: "합성 대화", lastSeq: 0 },
          messages: [],
          members: [],
          lastReadSeq: 0,
        });
      return reply([
        { id: "6", name: "합성 대화", lastSeq: 0, lastReadSeq: 0 },
      ]);
    });
  show(<Chat />);
  fireEvent.click(await screen.findByRole("button", { name: /합성 대화/ }));
  const body = await screen.findByRole("textbox");
  fireEvent.change(body, { target: { value: "전송 내용" } });
  fireEvent.click(screen.getByRole("button", { name: "전송" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "전송" })).not.toBeDisabled(),
  );
  fireEvent.click(screen.getByRole("button", { name: "전송" }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.filter(([, o]) => o?.method === "POST"),
    ).toHaveLength(2),
  );
  const writes = fetch.mock.calls.filter(([, o]) => o?.method === "POST");
  expect(JSON.parse(String(writes[0][1]?.body)).clientKey).toBe(
    JSON.parse(String(writes[1][1]?.body)).clientKey,
  );
});
it("collaboration does not read private resources without a selected role", () => {
  const fetch = vi.spyOn(globalThis, "fetch");
  show(<Chat />, "");
  expect(
    screen.getByRole("link", { name: /체험 담당자 등록/ }),
  ).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});
it("comment deletion requires an inline confirmation and preserves version", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (_u, o) =>
      reply(
        o?.method === "POST"
          ? { id: "3", status: "DELETED" }
          : [
              {
                id: "3",
                authorId: "1",
                authorName: "등록자",
                body: "의견",
                status: "ACTIVE",
                version: 4,
                createdAt: null,
                revisions: [],
              },
            ],
      ),
    );
  show(<Comments kind="POST" id="5" />);
  fireEvent.click(await screen.findByRole("button", { name: "댓글 삭제" }));
  expect(fetch.mock.calls.filter(([, o]) => o?.method === "POST")).toHaveLength(
    0,
  );
  fireEvent.click(screen.getByRole("button", { name: "댓글 삭제 확인" }));
  await waitFor(() =>
    expect(fetch.mock.calls.some(([, o]) => o?.method === "POST")).toBe(true),
  );
  expect(
    JSON.parse(
      String(fetch.mock.calls.find(([, o]) => o?.method === "POST")?.[1]?.body),
    ),
  ).toEqual({ actingPersonId: "1", expectedVersion: 4 });
});
