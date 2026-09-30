// UI-04: 입력 중인 패널이 있으면 앱 안 링크 이동도 "변경 버리기 / 계속 편집"을 거친다.
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it } from "vitest";
import { FormPanel, useDiscardGuard } from "./components";

function Editor() {
  const [value, setValue] = useState("");
  const guard = useDiscardGuard(value !== "");
  return (
    <>
      <nav>
        <Link to="/other">다른 메뉴</Link>
      </nav>
      <FormPanel
        title="등록"
        guard={guard}
        onClose={() => undefined}
        onSubmit={(e) => e.preventDefault()}
        actions={<button type="submit">저장</button>}
      >
        <label>
          이름
          <input value={value} onChange={(e) => setValue(e.target.value)} />
        </label>
      </FormPanel>
    </>
  );
}
function show() {
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<Editor />} />
        <Route path="/other" element={<p>다른 화면</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

it("변경이 없으면 메뉴 링크로 바로 이동한다", () => {
  show();
  fireEvent.click(screen.getByRole("link", { name: "다른 메뉴" }));
  expect(screen.getByText("다른 화면")).toBeInTheDocument();
});

it("변경이 있으면 메뉴 이동 전에 확인하고, 계속 편집이면 남고 변경 버리기면 이동한다", () => {
  show();
  fireEvent.change(screen.getByLabelText("이름"), {
    target: { value: "초안" },
  });
  fireEvent.click(screen.getByRole("link", { name: "다른 메뉴" }));
  expect(screen.queryByText("다른 화면")).toBeNull();
  expect(screen.getByRole("alert")).toHaveTextContent(
    "저장하지 않은 변경이 있습니다",
  );
  fireEvent.click(screen.getByRole("button", { name: "계속 편집" }));
  expect(screen.getByLabelText("이름")).toHaveValue("초안");

  fireEvent.click(screen.getByRole("link", { name: "다른 메뉴" }));
  fireEvent.click(screen.getByRole("button", { name: "변경 버리기" }));
  expect(screen.getByText("다른 화면")).toBeInTheDocument();
});

it("새 탭으로 여는 클릭(⌘/Ctrl)은 가로채지 않는다", () => {
  show();
  fireEvent.change(screen.getByLabelText("이름"), {
    target: { value: "초안" },
  });
  fireEvent.click(screen.getByRole("link", { name: "다른 메뉴" }), {
    metaKey: true,
  });
  expect(screen.queryByRole("alert")).toBeNull();
});
