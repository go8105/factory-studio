import { render, screen, fireEvent, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { it, expect, vi } from "vitest";
import { App } from "../app/App";
function show(auth = true, workspaceId = 10) {
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async () =>
      new Response(
        JSON.stringify(
          auth
            ? {
                data: {
                  actorKind: "GUEST",
                  workspaceId,
                  generationId: 20,
                  roles: ["GUEST"],
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
    <MemoryRouter initialEntries={["/cad-cam"]}>
      <App />
    </MemoryRouter>,
  );
}
it("places CAD menu immediately after launcher and scopes the embedded editor", async () => {
  show();
  const frame = await screen.findByTitle("CAD·CAM 편집기");
  expect(frame).toHaveAttribute(
    "src",
    "/cad-cam-app/index.html?embedded=1&scope=10%3A20",
  );
  const links = within(
    screen.getByRole("navigation", { name: "주 메뉴" }),
  ).getAllByRole("link");
  expect(links.slice(0, 3).map((x) => x.textContent)).toEqual([
    "앱 런처",
    "CAD·CAM",
    "3D 공장",
  ]);
  fireEvent.click(screen.getByRole("link", { name: "비누 그라인더 POC" }));
  expect(await screen.findByTitle("비누 그라인더 POC")).toHaveAttribute(
    "src",
    "/cad-cam-app/soap-poc.html?embedded=1&scope=10%3A20",
  );
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
