import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Projects } from "./Projects";
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
  parent_id: null,
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
  render(<Projects />);
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "DONE" } });
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.getByText("합성 업무 체험")).toBeInTheDocument();
});
it("회사 보드를 열고 네 보기가 같은 업무를 표시한다", async () => {
  render(<Projects />);
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
      "/api/v1/gw/projects/task-update?companyId=4",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});
it("조회 권한은 수정 입력을 표시하지 않으며 상세를 열 수 있다", async () => {
  state.role = "VIEWER";
  render(<Projects />);
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
  render(<Projects />);
  expect(await screen.findByText("조회 실패")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "다시 시도" })).toBeEnabled();
});
