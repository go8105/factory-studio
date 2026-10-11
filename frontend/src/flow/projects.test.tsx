import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Projects } from "./Projects";
import { MemoryRouter } from "react-router-dom";
const state = vi.hoisted(() => ({ actor: "MEMBER", role: "OWNER" }));
vi.mock("../app/session", () => ({
  useSession: () => ({
    session: { actorKind: state.actor, csrfToken: "synthetic-csrf" },
  }),
}));
const company = { id: 4, name: "예제 회사", timezone: "Asia/Seoul" };
const task = {
  id: 2,
  board_id: 1,
  group_id: 3,
  parent_id: null as number | null,
  title: "합성 업무",
  description: "내용",
  status: "WAITING",
  priority: "NORMAL",
  starts_on: "2026-10-12",
  ends_on: "2026-10-15",
  progress: 0,
  position: 1,
  version: 1,
  archived_at: null,
  assignees: [{ user_id: 8, display_name: "직원 A", active: true }],
};
function data(board = false) {
  return {
    company,
    userId: 8,
    companyOwner: true,
    members: [{ id: 8, name: "직원 A", active: true, role: "OWNER" }],
    boards: [
      {
        id: 1,
        name: "예제 보드",
        description: "",
        template: "PROJECT",
        version: 1,
        archived_at: null,
      },
    ],
    favorites: [],
    allowCreate: true,
    ...(board
      ? {
          board: {
            id: 1,
            name: "예제 보드",
            description: "",
            template: "PROJECT",
            version: 1,
            archived_at: null,
          },
          role: state.role,
          groups: [
            { id: 3, name: "계획", color: "#658ab1", position: 1, version: 1 },
          ],
          tasks: [task],
          preference: [],
          boardMembers: [],
        }
      : {}),
  };
}
beforeEach(() => {
  state.actor = "MEMBER";
  state.role = "OWNER";
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (url: string) =>
        new Response(
          JSON.stringify({
            data: url.endsWith("/companies")
              ? [company]
              : url.includes("/detail")
                ? { comments: [], events: [] }
                : url.includes("boardId=1")
                  ? data(true)
                  : url.includes("/task-update")
                    ? { id: 2 }
                    : data(),
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    ),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("게스트 체험은 실제 회사 API를 호출하지 않는다", () => {
  state.actor = "GUEST";
  render(
    <MemoryRouter>
      <Projects />
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "DONE" } });
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.getByText("합성 업무 체험")).toBeInTheDocument();
});
it("회사 보드를 열고 네 보기가 같은 업무를 표시한다", async () => {
  render(
    <MemoryRouter>
      <Projects />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "예제 보드" }));
  await screen.findByRole("button", { name: "합성 업무" });
  for (const view of ["칸반", "캘린더", "간트", "메인 테이블"]) {
    fireEvent.click(screen.getByRole("button", { name: view }));
    expect(screen.getAllByText("합성 업무").length).toBeGreaterThan(0);
  }
  fireEvent.change(screen.getByLabelText("합성 업무 상태"), {
    target: { value: "WORKING" },
  });
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/flow/task-update?companyId=4",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});
it("조회 권한은 수정 입력을 표시하지 않으며 상세를 열 수 있다", async () => {
  state.role = "VIEWER";
  render(
    <MemoryRouter>
      <Projects />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "예제 보드" }));
  fireEvent.click(await screen.findByRole("button", { name: "합성 업무" }));
  expect(screen.queryByLabelText("합성 업무 상태")).not.toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "업무 상세" })).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "댓글 등록" }),
  ).not.toBeInTheDocument();
});
it("조회 실패 후 다른 메뉴와 재시도는 비활성화하지 않는다", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            error: { code: "INTERNAL_ERROR", message: "조회 실패" },
          }),
          { status: 500 },
        ),
    ),
  );
  render(
    <MemoryRouter>
      <Projects />
    </MemoryRouter>,
  );
  expect(await screen.findByText("조회 실패")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "다시 시도" })).toBeEnabled();
});

it("업무 이름을 클릭해 바로 편집하고 Escape로 저장 없이 취소한다", async () => {
  render(
    <MemoryRouter>
      <Projects />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "예제 보드" }));
  fireEvent.click(await screen.findByRole("button", { name: "합성 업무" }));
  const input = screen.getByLabelText("업무 제목 바로 편집");
  fireEvent.change(input, { target: { value: "취소할 이름" } });
  fireEvent.keyDown(input, { key: "Escape" });
  fireEvent.blur(input);
  expect(
    screen.queryByLabelText("업무 제목 바로 편집"),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "합성 업무" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "합성 업무 업데이트" }));
  expect(
    await screen.findByRole("dialog", { name: "업무 상세" }),
  ).toBeInTheDocument();
});

it("하위 업무를 서버에 한 번 생성하고 부모 아래에서 바로 이름을 편집한다", async () => {
  let child: typeof task | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options?: RequestInit) => {
      let result: unknown;
      if (url.includes("/task-create")) {
        const body = JSON.parse(options!.body as string);
        expect(body).toMatchObject({
          boardId: 1,
          groupId: 3,
          parentId: 2,
          title: "새 하위 업무",
        });
        child = {
          ...task,
          id: 9,
          parent_id: 2,
          title: body.title,
          position: 2,
        };
        result = { id: 9 };
      } else if (url.includes("/task-update")) {
        const body = JSON.parse(options!.body as string);
        child = { ...child!, title: body.title };
        result = { id: 9 };
      } else if (url.endsWith("/companies")) result = [company];
      else if (url.includes("boardId=1"))
        result = { ...data(true), tasks: child ? [task, child] : [task] };
      else result = data();
      return new Response(JSON.stringify({ data: result }), { status: 200 });
    }),
  );
  render(
    <MemoryRouter>
      <Projects />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "예제 보드" }));
  const add = await screen.findByRole("button", {
    name: "합성 업무 하위 업무 추가",
  });
  fireEvent.click(add);
  fireEvent.click(add);
  const input = await screen.findByLabelText("업무 제목 바로 편집");
  expect(input).toHaveValue("새 하위 업무");
  expect(input.closest("tr")?.previousElementSibling).toHaveTextContent(
    "합성 업무",
  );
  expect(
    screen.queryByRole("dialog", { name: "업무 추가" }),
  ).not.toBeInTheDocument();
  expect(
    vi
      .mocked(fetch)
      .mock.calls.filter(([url]) => String(url).includes("/task-create")),
  ).toHaveLength(1);
  await waitFor(() => expect(add).toBeEnabled());
  fireEvent.change(input, { target: { value: "직접 입력한 하위 업무" } });
  fireEvent.blur(input);
  expect(
    await screen.findByRole("button", { name: "직접 입력한 하위 업무" }),
  ).toBeInTheDocument();
});

it("이름 저장 실패 시 입력을 유지하고 재시도할 수 있다", async () => {
  const baseFetch = fetch;
  let failed = true;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options?: RequestInit) => {
      if (url.includes("/task-update")) {
        if (failed)
          return new Response(
            JSON.stringify({
              error: { code: "INTERNAL_ERROR", message: "합성 저장 실패" },
            }),
            { status: 500 },
          );
        task.title = "재시도한 업무";
        return new Response(JSON.stringify({ data: { id: 2 } }), {
          status: 200,
        });
      }
      return baseFetch(url, options);
    }),
  );
  render(
    <MemoryRouter>
      <Projects />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "예제 보드" }));
  fireEvent.click(await screen.findByRole("button", { name: "합성 업무" }));
  const input = screen.getByLabelText("업무 제목 바로 편집");
  fireEvent.change(input, { target: { value: "재시도한 업무" } });
  fireEvent.blur(input);
  await screen.findByText("합성 저장 실패");
  await waitFor(() => expect(input).toBeEnabled());
  expect(input).toHaveValue("재시도한 업무");
  failed = false;
  fireEvent.blur(input);
  await screen.findByRole("button", { name: "재시도한 업무" });
  task.title = "합성 업무";
});
