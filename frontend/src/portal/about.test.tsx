import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import { About } from "./About";

function openAbout() {
  return render(
    <MemoryRouter initialEntries={["/about"]}>
      <App />
    </MemoryRouter>,
  );
}
it("비로그인 /about은 세션 API 없이 이름과 핵심 숫자를 표시한다", () => {
  const fetcher = vi.spyOn(globalThis, "fetch");
  openAbout();
  expect(screen.getByRole("heading", { name: "황경호" })).toBeVisible();
  for (const value of ["4년+", "6곳", "5개 모듈"])
    expect(screen.getByText(value)).toBeVisible();
  expect(fetcher).not.toHaveBeenCalled();
  expect(document.querySelector(".app-shell")).not.toBeInTheDocument();
});
it("프로젝트 분류를 전환하고 카드의 문제와 해결을 펼치고 접는다", () => {
  openAbout();
  fireEvent.click(
    screen.getByRole("button", {
      name: "자세히 보기 · 실시간 이상 감지 알람 엔진",
    }),
  );
  expect(
    screen.getByText("asyncio 알람 엔진 분리, Redis TTL 중복 억제"),
  ).toBeVisible();
  fireEvent.click(
    screen.getByRole("button", { name: "접기 · 실시간 이상 감지 알람 엔진" }),
  );
  expect(
    screen.queryByText("asyncio 알람 엔진 분리, Redis TTL 중복 억제"),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "MES 7" }));
  expect(screen.getByRole("heading", { name: "육가공 MES" })).toBeVisible();
  expect(
    screen.queryByRole("heading", { name: "실시간 이상 감지 알람 엔진" }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "개인 2" }));
  expect(screen.getByRole("heading", { name: "Factory Studio" })).toBeVisible();
});
it("경력의 프로젝트 링크는 해당 분류를 선택한다", () => {
  openAbout();
  fireEvent.click(screen.getByRole("link", { name: "MES 프로젝트 보기 →" }));
  expect(screen.getByRole("button", { name: "MES 7" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
it("목차는 앵커로 이동하고 스크롤 위치에 따라 현재 항목을 표시한다", () => {
  openAbout();
  for (const id of [
    "intro",
    "career",
    "projects",
    "skills",
    "awards",
    "contact",
  ]) {
    vi.spyOn(
      document.getElementById(id)!,
      "getBoundingClientRect",
    ).mockReturnValue({
      top:
        id === "projects"
          ? 100
          : id === "intro" || id === "career"
            ? -100
            : 900,
    } as DOMRect);
  }
  fireEvent.scroll(window);
  const nav = screen.getByRole("navigation", { name: "섹션 목차" });
  expect(within(nav).getByRole("link", { name: "프로젝트" })).toHaveAttribute(
    "aria-current",
    "location",
  );
  expect(within(nav).getByRole("link", { name: "경력" })).toHaveAttribute(
    "href",
    "#career",
  );
});
it("노트 0편이면 기술 노트 섹션이 없고 공개 연락은 이메일·GitHub만 표시한다", () => {
  const { container } = render(
    <MemoryRouter>
      <About />
    </MemoryRouter>,
  );
  expect(
    screen.queryByRole("heading", { name: "기술 노트" }),
  ).not.toBeInTheDocument();
  expect(container.textContent).not.toMatch(/010-/);
  expect(
    screen.queryByRole("link", { name: "이력서 PDF" }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "GitHub" })).toHaveAttribute(
    "href",
    "https://github.com/go8105",
  );
});
it("노트 미리보기는 실제로 전달된 데이터의 최신 3편만 표시한다", () => {
  const notes = [1, 4, 2, 3].map((n) => ({
    slug: `note-${n}`,
    title: `노트 ${n}`,
    date: `2026-11-0${n}`,
    category: "AI",
    summary: `요약 ${n}`,
  }));
  render(
    <MemoryRouter>
      <About notes={notes} />
    </MemoryRouter>,
  );
  const section = screen.getByRole("region", { name: "기술 노트" });
  expect(
    within(section)
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent),
  ).toEqual(["노트 4", "노트 3", "노트 2"]);
  expect(within(section).getByRole("link", { name: /노트 4/ })).toHaveAttribute(
    "href",
    "/notes/note-4",
  );
});
