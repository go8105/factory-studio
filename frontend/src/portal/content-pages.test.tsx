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
    count("qms/q-"),
    count("wms/w-"),
    count("bems/b-"),
  ]).toEqual([7, 15, 18, 14, 6, 9, 7]);
});
it("BEMS는 구현했으므로 설명 카드가 없다(SCM만)", () => {
  expect(Object.keys(cards)).toEqual([]);
});
it("P-03 업무 노드는 해당 솔루션 도움말로 연결된다", async () => {
  show("/flow");
  expect(
    await screen.findByRole("link", { name: /07 \/ MES 실적 확정/ }),
  ).toHaveAttribute("href", "/help/mes/m-07");
});
it("P-03 실적 확정 뒤 품질검사·패킹 연결은 모두 실선이다", async () => {
  show("/flow");
  const list = await screen.findByRole("list", { name: "실적 확정 연결" });
  for (const name of [/패킹/, /품질검사/])
    expect(
      within(list).getByRole("link", { name }).closest("li"),
    ).not.toHaveClass("dashed");
});
it("P-03 FEMS → BEMS 건물 에너지 분해는 실선(BEMS 구현)이고 B-02 도움말로 간다", async () => {
  show("/flow");
  const list = await screen.findByRole("list", {
    name: "에너지 기준정보·조회 연결",
  });
  const bems = within(list).getByRole("link", { name: /건물 에너지 분해/ });
  expect(bems.closest("li")).not.toHaveClass("dashed");
  expect(
    screen.getByRole("link", { name: /BEMS 건물 에너지 분해/ }),
  ).toHaveAttribute("href", "/help/bems/b-02");
});
it("P-04 BEMS 카드는 없어지고 SCM만 남는다", async () => {
  show("/cards/bems");
  expect(await screen.findByText("404 · NOT_FOUND")).toBeVisible();
});
it("P-03 완제품 입고 → 재고 연결은 실선(WMS 구현)이다", async () => {
  show("/flow");
  const list = await screen.findByRole("list", { name: "완제품 입고 연결" });
  const stock = within(list).getByRole("link", { name: /재고/ });
  expect(stock.closest("li")).not.toHaveClass("dashed");
});
it("P-04 정의되지 않은 카드는 404로 처리한다", async () => {
  show("/cards/mes");
  expect(await screen.findByText("404 · NOT_FOUND")).toBeVisible();
});
it("P-05 첫 화면은 구역 카드와 솔루션별 참고 문서 입구를 둔다", async () => {
  show("/help");
  const reference = await screen.findByRole("region", {
    name: "사용자 참고 문서",
  });
  expect(
    within(reference).getByRole("link", { name: /FEMS 에너지관리/ }),
  ).toHaveAttribute("href", "/help/fems/f-01");
});
it("P-05 검색은 제목 일치를 본문 일치보다 위에 둔다", async () => {
  show("/help?q=소명");
  const results = await screen.findByRole("region", { name: "검색 결과" });
  const first = within(results).getAllByRole("link")[0];
  expect(first.textContent).toMatch(/소명/);
});
it("P-05 화면 문서는 트리·목차·이 화면 열기·이전/다음을 갖는다", async () => {
  show("/help/erp/e-09");
  expect(
    await screen.findByRole("link", { name: "이 화면 열기 →" }),
  ).toHaveAttribute("href", "/erp/receivables");
  const tree = screen.getByRole("navigation", { name: "문서 목록" });
  expect(within(tree).getByRole("link", { name: /E-09/ })).toHaveAttribute(
    "aria-current",
    "page",
  );
  const toc = screen.getByRole("navigation", { name: "이 문서 목차" });
  expect(
    within(toc).getByRole("link", { name: "이럴 때 막힙니다" }),
  ).toHaveAttribute("href", "#이럴-때-막힙니다");
  expect(
    screen.getByRole("heading", { name: "이럴 때 막힙니다" }),
  ).toHaveAttribute("id", "이럴-때-막힙니다");
  const pager = screen.getByRole("navigation", { name: "이전·다음 문서" });
  expect(within(pager).getByRole("link", { name: /이전/ })).toHaveAttribute(
    "href",
    "/help/erp/e-08",
  );
});
it("P-05 포털 문서에는 이 화면 열기가 없다", async () => {
  show("/help/common");
  await screen.findByRole("heading", { name: "공통 이용 안내" });
  expect(screen.queryByRole("link", { name: "이 화면 열기 →" })).toBeNull();
});
it("P-05 객체 기본 속성 이름은 도움말 키로 해석하지 않는다", async () => {
  show("/help/constructor");
  expect(await screen.findByText("404 · NOT_FOUND")).toBeVisible();
});
