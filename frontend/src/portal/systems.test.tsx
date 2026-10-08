// MAP-02 P-03 계층 아키텍처·시스템 카탈로그 — 정적 데이터 계약과 화면 동작.
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import { solutions } from "./Home";
import systems from "../../../content/systems.json";
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
it("시스템 18개, 구현 표시는 홈 솔루션 목록과 정확히 같다", () => {
  expect(systems.systems).toHaveLength(18);
  expect(
    systems.systems
      .filter((s) => s.status === "implemented")
      .map((s) => [s.id, s.to]),
  ).toEqual(expect.arrayContaining(solutions.map((s) => [s.key, s.to])));
  expect(
    systems.systems.filter((s) => s.status === "implemented"),
  ).toHaveLength(solutions.length);
});
it("계층·연관 시스템 참조가 모두 존재한다", () => {
  const ids = new Set(systems.systems.map((s) => s.id));
  expect(ids.size).toBe(18);
  for (const s of systems.systems) {
    expect(systems.layers, s.id).toContain(s.layer);
    expect(
      s.rel.filter((r) => !ids.has(r)),
      s.id,
    ).toEqual([]);
  }
});
it("운영이 아닌 9개는 모두 예정이고 운영 SPC·GW는 제외한다", () => {
  const planned = systems.systems.filter((s) => s.status === "planned");
  expect(planned).toHaveLength(9);
  expect(
    planned
      .map((s) => ("order" in s ? (s.order ?? 0) : 0))
      .sort((a, b) => a - b),
  ).toEqual([2, 3, 4, 5, 6, 7, 8, 9, 11]);
  expect(systems.fields).toHaveLength(5);
  expect(systems.systems.every((s) => systems.fields.includes(s.field))).toBe(
    true,
  );
  expect(systems.systems.find((s) => s.id === "gw")?.abbr).toBe("GW");
});
it("계층 아키텍처에서 시스템을 누르면 카탈로그 상세로 간다", async () => {
  show("/flow?view=arch");
  expect(await screen.findByRole("region", { name: "생산실행" })).toBeTruthy();
  fireEvent.click(screen.getByRole("link", { name: /^CMMS/ }));
  expect(await screen.findByText(/← BEMS 경보/)).toBeTruthy();
});
it("카탈로그의 구현 솔루션은 화면으로 이동 링크가 있다", async () => {
  show("/flow?view=catalog&sys=qms");
  expect(
    await screen.findByRole("link", { name: "화면으로 이동" }),
  ).toHaveAttribute("href", "/qms");
});
