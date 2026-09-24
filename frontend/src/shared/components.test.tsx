import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { act } from "react";
import { ApiError } from "./api";
import {
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  Loading,
  SessionExpired,
  csvText,
} from "./components";
afterEach(() => vi.useRealTimers());
it("빈 상태는 사유와 다음 행동을 제공한다", () => {
  render(
    <MemoryRouter>
      <EmptyState reason="등록된 항목이 없습니다" to="/home" action="홈 이동" />
    </MemoryRouter>,
  );
  expect(screen.getByRole("link", { name: /홈 이동/ })).toHaveAttribute(
    "href",
    "/home",
  );
  expect(screen.getByText("등록된 항목이 없습니다")).toBeVisible();
});
it("참조 오류 봉투의 참조처별 건수를 표시한다", () => {
  render(
    <ErrorNotice
      error={
        new ApiError(409, {
          code: "REFERENCED_BY_OTHERS",
          message: "참조 중입니다",
          details: { references: { orders: 3 } },
        })
      }
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent('"orders":3');
});
it("입력 필드를 레이블과 연결한다", () => {
  render(<Field label="품목 코드" error="필수 항목" />);
  expect(screen.getByLabelText("품목 코드")).toHaveAccessibleDescription(
    "필수 항목",
  );
});
it("로딩은 1초 이전에 표시하지 않는다", () => {
  vi.useFakeTimers();
  render(<Loading delay={1000} />);
  act(() => vi.advanceTimersByTime(999));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});
it("로딩은 1초 이후 진행 상태를 표시한다", () => {
  vi.useFakeTimers();
  render(<Loading delay={1000} />);
  act(() => vi.advanceTimersByTime(1000));
  expect(screen.getByRole("status")).toBeVisible();
});
it("세션 만료 안내에서 진입 화면으로 복귀할 수 있다", () => {
  render(
    <MemoryRouter>
      <SessionExpired />
    </MemoryRouter>,
  );
  expect(screen.getByRole("link", { name: "진입 화면으로" })).toHaveAttribute(
    "href",
    "/",
  );
});
const rows = [
  { id: 2, name: "둘째" },
  { id: 1, name: "첫째" },
];
const columns = [
  { key: "id" as const, label: "번호" },
  { key: "name" as const, label: "이름" },
];
it("표의 숫자 정렬은 현재 페이지에 적용한다", () => {
  render(
    <MemoryRouter>
      <DataTable
        rows={rows}
        columns={columns}
        caption="목록"
        offset={0}
        total={2}
        limit={20}
        onPage={() => {}}
      />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: "번호 ↕" }));
  expect(screen.getAllByRole("row")[1]).toHaveTextContent("1첫째");
});
it("표 페이지 이동은 다음 offset을 전달한다", () => {
  const next = vi.fn();
  render(
    <MemoryRouter>
      <DataTable
        rows={rows}
        columns={columns}
        caption="목록"
        offset={0}
        total={30}
        limit={20}
        onPage={next}
      />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: "다음" }));
  expect(next).toHaveBeenCalledWith(20);
});
it("CSV는 따옴표와 수식 시작 문자를 이스케이프한다", () => {
  expect(csvText([{ id: 1, name: "=1+1" }], columns)).toContain('"\'=1+1"');
});
