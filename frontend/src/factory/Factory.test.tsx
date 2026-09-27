import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import Factory from "./Factory";
vi.mock("@react-three/fiber", () => ({
  Canvas: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
vi.mock("../app/session", () => ({
  useSession: () => ({ session: { csrfToken: "test" }, fail: vi.fn() }),
}));
vi.mock("./Scene", () => ({ default: () => null }));
function show() {
  render(
    <MemoryRouter>
      <Factory />
    </MemoryRouter>,
  );
}
it("실제 설비 연동이 아닌 합성 시연임을 표시한다", () => {
  show();
  expect(
    screen.getByText(/3D 합성 시연 · 실시간 설비 정보 아님/),
  ).toBeVisible();
});
it("걸어서 둘러보기를 누르면 이동 버튼이 나타난다", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: "걸어서 둘러보기" }));
  expect(screen.getByRole("group", { name: "캐릭터 이동" })).toBeVisible();
});
it("Esc를 누르면 조감도로 돌아온다", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: "걸어서 둘러보기" }));
  fireEvent.keyDown(screen.getByRole("region", { name: "3D 공장 탐색" }), {
    code: "Escape",
  });
  expect(screen.getByRole("button", { name: "걸어서 둘러보기" })).toBeVisible();
});
it("시연 일시정지는 다시 재생할 수 있다", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: "시연 일시정지" }));
  expect(screen.getByRole("button", { name: "시연 재생" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
it("2층 사무실 시점을 선택할 수 있다", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: "2층 사무실" }));
  expect(screen.getByRole("button", { name: "2층 사무실" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
it("비전검사 공정 버튼으로 설명을 읽을 수 있다", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: /02 비전검사/ }));
  expect(
    screen.getByText(/카메라와 조명으로 제품의 외관을 검사/),
  ).toBeVisible();
});

it("정지 시나리오와 기존 이상 해제 동작이 같은 상태를 사용한다", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: /02 비전검사/ }));
  fireEvent.click(screen.getByRole("button", { name: "정지" }));
  expect(screen.getByTestId("vision-phase")).toHaveTextContent("이상 정지");
  expect(screen.getByRole("button", { name: "정지" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  fireEvent.click(screen.getByRole("button", { name: "이상 해제" }));
  expect(screen.getByRole("button", { name: "정상" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByTestId("vision-phase")).not.toHaveTextContent("이상 정지");
});
