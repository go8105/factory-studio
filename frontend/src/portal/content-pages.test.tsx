// FS-017b P-03~P-05 화면·정적 콘텐츠 계약. 검증 항목별로 테스트를 나눈다.
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import flow from "../../../content/flow-map.json";
import { cards, help } from "../shared/content";
const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
function show(path: string) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ data: session }), { status: 200 }),
  );
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
it("업무 노드의 도움말 키는 노드 소유 솔루션의 도움말이다", () => {
  expect(
    flow.nodes
      .filter((n) => n.kind === "solution")
      .filter((n) => !n.helpKey?.startsWith(`${n.module}/`)),
  ).toEqual([]);
});
it("같은 방향의 연결은 한 번만 정의된다", () => {
  const pairs = flow.edges.map((e) => `${e.from}>${e.to}`);
  expect(new Set(pairs).size).toBe(pairs.length);
});
it("화면 ID마다 도움말 파일이 있다", () => {
  const count = (prefix: string) =>
    Object.keys(help).filter((k) => k.startsWith(prefix)).length;
  expect([
    count("portal/p-"),
    count("mes/m-"),
    count("erp/e-"),
    count("fems/f-"),
  ]).toEqual([7, 15, 18, 14]);
});
it.each(["qms", "wms", "bems"])("%s 카드는 세 항목을 모두 갖춘다", (key) => {
  const headings = cards[key].match(/^## .+$/gm);
  expect(headings).toEqual([
    "## 무엇을 하는 시스템인가",
    "## 왜 이번 범위에서 제외했는가",
    "## 넣는다면 어디에 붙는가",
  ]);
});
it("P-03 업무 노드는 해당 솔루션 도움말로 연결된다", async () => {
  show("/flow");
  expect(
    await screen.findByRole("link", { name: /07 \/ MES 실적 확정/ }),
  ).toHaveAttribute("href", "/help/mes/m-07");
});
it("P-03 QMS 미구현 동안 실적-패킹 직결 연결은 실선이다", async () => {
  show("/flow");
  const list = await screen.findByRole("list", { name: "실적 확정 연결" });
  const direct = within(list).getByRole("link", { name: /패킹/ });
  expect(direct.closest("li")).not.toHaveClass("dashed");
});
it("P-03 설명 카드로 가는 연결은 점선이다", async () => {
  show("/flow");
  const list = await screen.findByRole("list", { name: "실적 확정 연결" });
  const inspection = within(list).getByRole("link", { name: /품질검사/ });
  expect(inspection.closest("li")).toHaveClass("dashed");
});
it("P-04 정의되지 않은 카드는 404로 처리한다", async () => {
  show("/cards/mes");
  expect(await screen.findByText("404 · NOT_FOUND")).toBeVisible();
});
it("P-05 목록은 솔루션별 도움말 링크를 제공한다", async () => {
  show("/help");
  expect(await screen.findByRole("link", { name: /F-01/ })).toHaveAttribute(
    "href",
    "/help/fems/f-01",
  );
});
it("P-05 객체 기본 속성 이름은 도움말 키로 해석하지 않는다", async () => {
  show("/help/constructor");
  expect(await screen.findByText("404 · NOT_FOUND")).toBeVisible();
});
