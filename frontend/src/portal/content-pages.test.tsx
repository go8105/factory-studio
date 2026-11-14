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
    count("spc/s-"),
    count("cmms/c-"),
    count("gw/g-"),
  ]).toEqual([8, 19, 18, 23, 13, 18, 10, 11, 10, 15]);
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
it("따라하기 3편·개념 21편은 유형별 작성 틀(DOC-01 6장)을 따른다", () => {
  const of = (prefix: string) =>
    Object.keys(help).filter((k) => k.startsWith(prefix));
  const shape = (key: string) =>
    help[key].match(/^## .+$/gm)?.map((h) => h.slice(3));
  expect(of("guide/")).toHaveLength(3);
  expect(of("concept/")).toHaveLength(21);
  for (const key of of("guide/"))
    expect(shape(key), key).toEqual([
      "목표",
      "준비 상태",
      "단계",
      "끝나면 보이는 것",
      "막힐 때",
    ]);
  for (const key of of("concept/"))
    expect(shape(key), key).toEqual([
      "한 줄 정의",
      "왜 필요한가",
      "이 제품에서는",
      "관련 화면",
    ]);
});
it("굵게 표시가 문장부호 뒤에서 닫힌 뒤 글자가 붙어 * 가 그대로 보이는 문서가 없다", () => {
  // CommonMark: `**…)**가`는 닫히지 않는다. `**…**(…)가`로 쓴다.
  const broken = Object.entries(help).filter(([, body]) =>
    /[)\]"%.,:;]\*\*[가-힣A-Za-z0-9]/.test(body),
  );
  expect(broken.map(([key]) => key)).toEqual([]);
});
it("설계 문서 8편은 결정 → 대안 → 이유 → 한계 틀이고 본문에 작업 ID가 없다", () => {
  const keys = Object.keys(help).filter((k) => k.startsWith("design/"));
  expect(keys).toHaveLength(8);
  for (const key of keys) {
    expect(
      help[key].match(/^## .+$/gm)?.map((h) => h.slice(3)),
      key,
    ).toEqual(["결정", "검토한 대안", "선택 이유", "한계", "관련 문서"]);
    // 출처 주석(<!-- sources -->)에만 작업 ID를 남긴다(DOC-01 공개 기준).
    const body = help[key].replace(/<!--[\s\S]*?-->/g, "");
    expect(body, key).not.toMatch(/\b(FS|AC|UI|DOC|MAP)-\d/);
  }
});

it("GW 도움말이 늦게 렌더링되어도 요청한 절로 이동한다", async () => {
  const scroll = vi.fn();
  Object.defineProperty(Element.prototype, "scrollIntoView", {
    configurable: true,
    value: scroll,
  });
  try {
    show("/help/gw/operations#" + encodeURIComponent("서버-점검이-필요할-때"));
    const heading = await screen.findByRole("heading", {
      name: "서버 점검이 필요할 때",
    });
    expect(scroll).toHaveBeenCalledWith({ block: "start" });
    expect(scroll.mock.instances).toContain(heading);
  } finally {
    delete (Element.prototype as Partial<Element>).scrollIntoView;
  }
});
