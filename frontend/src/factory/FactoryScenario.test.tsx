import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import Factory from "./Factory";
import { visionAt, type VisionSnapshot } from "./vision";
vi.mock("@react-three/fiber", () => ({
  Canvas: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
vi.mock("../app/session", () => ({
  useSession: () => ({ session: { csrfToken: "test" }, fail: vi.fn() }),
}));
vi.mock("./Scene", () => ({
  default: ({
    onSnapshot,
  }: {
    onSnapshot: (value: VisionSnapshot) => void;
  }) => (
    <button onClick={() => onSnapshot(visionAt(6))}>
      검사 완료 모의 이벤트
    </button>
  ),
}));
it("활성 시나리오 재선택은 검사 누계와 설명을 초기화하지 않는다", async () => {
  render(
    <MemoryRouter>
      <Factory />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: /02 비전검사/ }));
  fireEvent.click(
    await screen.findByRole("button", { name: "검사 완료 모의 이벤트" }),
  );
  expect(screen.getByTestId("vision-count")).toHaveTextContent("1개");
  fireEvent.click(screen.getByRole("button", { name: "정상" }));
  expect(screen.getByTestId("vision-count")).toHaveTextContent("1개");
  fireEvent.click(screen.getByRole("button", { name: "불합격 증가" }));
  expect(screen.getByTestId("vision-count")).toHaveTextContent("0개");
});
