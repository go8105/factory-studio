import { render, screen, fireEvent, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { it, expect, vi } from "vitest";
import { App } from "../app/App";
function show(
  auth = true,
  workspaceId = 10,
  roles = ["GUEST"],
  path = "/cad-cam",
) {
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async () =>
      new Response(
        JSON.stringify(
          auth
            ? {
                data: {
                  actorKind: roles.includes("GUEST") ? "GUEST" : "MEMBER",
                  workspaceId,
                  generationId: 20,
                  roles,
                  csrfToken: "synthetic",
                  expiresAt: null,
                },
              }
            : {
                error: { code: "SESSION_REQUIRED", message: "세션이 없습니다" },
              },
        ),
        { status: auth ? 200 : 401 },
      ),
  );
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
it("reaches CAD from the app switcher and scopes the embedded editor", async () => {
  show();
  const frame = await screen.findByTitle("CAD·CAM 편집기");
  expect(frame).toHaveAttribute(
    "src",
    "/cad-cam-app/index.html?embedded=1&scope=10%3A20",
  );
  // CAD·CAM은 헤더에 따로 두지 않고 앱 전환기 안에 있다(UI-REDESIGN-01 R1-a).
  const nav = within(screen.getByRole("navigation", { name: "주 메뉴" }));
  expect(nav.queryByRole("link", { name: "CAD·CAM" })).toBeNull();
  // jsdom은 summary 클릭으로 details를 열지 않는다. open을 직접 주고 toggle을 보낸다.
  const switcher = nav.getByRole("group", {
    name: "앱 전환",
  }) as HTMLDetailsElement;
  switcher.open = true;
  fireEvent(switcher, new Event("toggle", { bubbles: false }));
  expect(nav.getByRole("link", { name: "CAD·CAM" })).toHaveAttribute(
    "href",
    "/cad-cam",
  );
  expect(nav.getByRole("link", { name: "3D 공장" })).toHaveAttribute(
    "href",
    "/factory",
  );
  expect(nav.getByRole("link", { name: "앱 런처" })).toHaveAttribute(
    "href",
    "/home",
  );
  expect(
    screen.queryByRole("link", { name: "비누 그라인더 POC" }),
  ).not.toBeInTheDocument();
});
it("uses another browser save namespace for another workspace", async () => {
  show(true, 11);
  expect(await screen.findByTitle("CAD·CAM 편집기")).toHaveAttribute(
    "src",
    expect.stringContaining("scope=11%3A20"),
  );
});
it("does not mount the editor without a session", async () => {
  show(false);
  await screen.findByText("세션이 만료되었습니다");
  expect(screen.queryByTitle("CAD·CAM 편집기")).not.toBeInTheDocument();
});

it("admin alone can open protected POC route", async () => {
  show(true, 10, ["ADMIN"]);
  await screen.findByTitle("CAD·CAM 편집기");
  fireEvent.click(screen.getByRole("link", { name: "비누 그라인더 POC" }));
  expect(await screen.findByTitle("비누 그라인더 POC")).toHaveAttribute(
    "src",
    "/api/v1/cad/admin/soap-poc/soap-poc.html?embedded=1&scope=10%3A20&poc=1",
  );
});
it.each([["GUEST"], ["MEMBER"]])(
  "direct POC query is ignored without ADMIN: %s",
  async (role) => {
    show(true, 10, [role], "/cad-cam?view=soap");
    await screen.findByTitle("CAD·CAM 편집기");
    expect(screen.queryByTitle("비누 그라인더 POC")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "비누 그라인더 POC" }),
    ).not.toBeInTheDocument();
  },
);

it("keeps E2 route and workspace scope on direct entry and separates it from protected POC", async () => {
  show(true, 11, ["GUEST"], "/cad-cam?view=part");
  expect(await screen.findByTitle("3D 부품 설계")).toHaveAttribute(
    "src",
    "/cad-cam-app/part-design.html?embedded=1&scope=11%3A20",
  );
  expect(screen.getByRole("link", { name: "3D 부품 설계" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(
    screen.queryByRole("link", { name: "비누 그라인더 POC" }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("link", { name: "설계·가공 편집기" }));
  expect(await screen.findByTitle("CAD·CAM 편집기")).toHaveAttribute(
    "src",
    "/cad-cam-app/index.html?embedded=1&scope=11%3A20",
  );
});

it("opens the separate NC review without admin-only soap assets", async () => {
  show(true, 11, ["GUEST"], "/cad-cam?view=nc");
  expect(await screen.findByTitle("NC 경로 검토")).toHaveAttribute(
    "src",
    "/cad-cam-app/nc-review.html?embedded=1&scope=11%3A20",
  );
  expect(screen.getByTitle("NC 경로 검토")).toHaveAttribute(
    "allow",
    "microphone",
  );
  expect(screen.getByRole("link", { name: "NC 경로 검토" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(
    screen.getByRole("link", { name: "설계·가공 편집기" }),
  ).not.toHaveAttribute("aria-current");
  expect(
    screen.queryByRole("link", { name: "비누 그라인더 POC" }),
  ).not.toBeInTheDocument();
});
