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
  fireEvent.click(screen.getByRole("button", { name: "합성 업무 업무 메뉴" }));
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

it("접힌 그룹은 머리글 한 줄만 남기고 표와 업무 추가를 숨긴다", async () => {
  render(
    <MemoryRouter>
      <Projects />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "예제 보드" }));
  await screen.findByRole("button", { name: "합성 업무" });
  fireEvent.click(screen.getByRole("button", { name: "▾" }));
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "＋ 업무 추가" }),
  ).not.toBeInTheDocument();
  expect(document.querySelector(".project-group-summary")).toBeNull();
  expect(document.querySelector(".project-group")).toHaveClass("is-collapsed");
  fireEvent.click(screen.getByRole("button", { name: "▸" }));
  expect(screen.getByRole("table")).toBeInTheDocument();
});

it("상세 편집에는 제목과 설명만 있고 삭제는 하위 업무 행 메뉴에서 복구 가능한 보관 요청을 보낸다", async () => {
  const child = { ...task, id: 9, parent_id: 2, title: "하위 검증" };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options?: RequestInit) => {
      const result = url.endsWith("/companies")
        ? [company]
        : url.includes("/detail")
          ? { comments: [], events: [] }
          : url.includes("/task-update")
            ? { id: 9 }
            : url.includes("boardId=1")
              ? { ...data(true), tasks: [task, child] }
              : data();
      if (url.includes("/task-update"))
        expect(JSON.parse(options!.body as string)).toMatchObject({
          id: 9,
          parentId: 2,
          archived: true,
        });
      return new Response(JSON.stringify({ data: result }), { status: 200 });
    }),
  );
  render(
    <MemoryRouter>
      <Projects />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "예제 보드" }));
  fireEvent.click(await screen.findByLabelText("하위 검증 업무 메뉴"));
  fireEvent.click(screen.getByRole("button", { name: "하위 검증 업데이트" }));
  const dialog = await screen.findByRole("dialog", { name: "업무 상세" });
  const editor = dialog.querySelector("form")!;
  expect(
    Array.from(editor.querySelectorAll("label"), (x) =>
      x.firstChild?.textContent?.trim(),
    ),
  ).toEqual(["제목", "설명·참고 링크"]);
  expect(editor.querySelectorAll("input,textarea")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "닫기" }));
  fireEvent.click(screen.getByRole("button", { name: "하위 검증 업무 메뉴" }));
  fireEvent.click(screen.getByRole("button", { name: "하위 업무 삭제" }));
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/task-update"),
      expect.anything(),
    ),
  );
});

it("행에서 담당자·일정·진행률을 적용하고 취소는 저장하지 않는다", async () => {
  render(
    <MemoryRouter>
      <Projects />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "예제 보드" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "합성 업무 담당자 수정" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "취소" }));
  expect(
    vi
      .mocked(fetch)
      .mock.calls.filter(([u]) => String(u).includes("/task-update")),
  ).toHaveLength(0);
  fireEvent.click(
    screen.getByRole("button", { name: "합성 업무 담당자 수정" }),
  );
  fireEvent.click(screen.getByRole("checkbox", { name: "직원 A" }));
  fireEvent.click(screen.getByRole("button", { name: "적용" }));
  await waitFor(() =>
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(
          ([u, o]) =>
            String(u).includes("/task-update") &&
            JSON.parse(o!.body as string).assignees.length === 0,
        ),
    ).toBe(true),
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("form", { name: "합성 업무 담당자 편집" }),
    ).not.toBeInTheDocument(),
  );
  fireEvent.click(screen.getByRole("button", { name: "합성 업무 일정 수정" }));
  fireEvent.change(screen.getByLabelText("합성 업무 시작일"), {
    target: { value: "2026-10-10" },
  });
  fireEvent.click(screen.getByRole("button", { name: "적용" }));
  await waitFor(() =>
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(
          ([u, o]) =>
            String(u).includes("/task-update") &&
            JSON.parse(o!.body as string).startsOn === "2026-10-10",
        ),
    ).toBe(true),
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("form", { name: "합성 업무 일정 편집" }),
    ).not.toBeInTheDocument(),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "합성 업무 진행률 수정" }),
  );
  fireEvent.change(screen.getByLabelText("합성 업무 진행률 입력"), {
    target: { value: "100" },
  });
  fireEvent.click(screen.getByRole("button", { name: "적용" }));
  await waitFor(() =>
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(
          ([u, o]) =>
            String(u).includes("/task-update") &&
            JSON.parse(o!.body as string).progress === 100 &&
            JSON.parse(o!.body as string).status === "DONE",
        ),
    ).toBe(true),
  );
});

it("중요도는 행에서 수정하고 집계 부모의 일정·진행률은 직접 편집하지 않는다", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (url: string) =>
        new Response(
          JSON.stringify({
            data: url.endsWith("/companies")
              ? [company]
              : url.includes("boardId=1")
                ? {
                    ...data(true),
                    tasks: [{ ...task, aggregate: true }],
                    preference: [{ preference: { view: "table", hidden: [] } }],
                  }
                : url.includes("task-update")
                  ? { id: 2 }
                  : data(),
          }),
          { status: 200 },
        ),
    ),
  );
  render(
    <MemoryRouter>
      <Projects />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "예제 보드" }));
  await screen.findByRole("button", { name: "합성 업무" });
  fireEvent.click(screen.getByText("열 관리", { exact: true }));
  fireEvent.click(screen.getByRole("checkbox", { name: "중요도" }));
  fireEvent.change(screen.getByRole("combobox", { name: "합성 업무 중요도" }), {
    target: { value: "HIGH" },
  });
  await waitFor(() =>
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(
          ([u, o]) =>
            String(u).includes("task-update") &&
            JSON.parse(o!.body as string).priority === "HIGH",
        ),
    ).toBe(true),
  );
  expect(
    screen.queryByRole("button", { name: "합성 업무 일정 수정" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "합성 업무 진행률 수정" }),
  ).not.toBeInTheDocument();
});
