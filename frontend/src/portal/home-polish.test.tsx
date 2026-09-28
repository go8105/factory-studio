import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
function show(enabled = true) {
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (input) =>
      new Response(
        JSON.stringify({
          data: String(input).endsWith("/sessions/current")
            ? {
                actorKind: "GUEST",
                workspaceId: 10,
                generationId: 20,
                roles: ["GUEST"],
                csrfToken: "preview",
                expiresAt: "2026-09-28T00:00:00+09:00",
              }
            : ["mes", "erp", "fems", "qms", "wms", "bems"].map((moduleKey) => ({
                moduleKey,
                enabled,
                updatedAt: null,
              })),
        }),
      ),
  );
  render(
    <MemoryRouter initialEntries={["/home"]}>
      <App />
    </MemoryRouter>,
  );
}
it("홈은 여섯 솔루션과 미구현 SCM 설명 카드 링크를 보인다", async () => {
  show();
  await screen.findByRole("link", { name: /QMS 품질관리/ });
  expect(screen.getByRole("link", { name: /WMS 창고관리/ })).toHaveAttribute(
    "href",
    "/wms",
  );
  expect(screen.getByRole("link", { name: /BEMS 건물관리/ })).toHaveAttribute(
    "href",
    "/bems",
  );
  expect(screen.getByRole("link", { name: /SCM 공급망/ })).toHaveAttribute(
    "href",
    "/cards/scm",
  );
  expect(screen.queryByRole("link", { name: /BEMS 건물 →/ })).toBeNull();
  expect(screen.queryByRole("link", { name: /QMS 품질 →/ })).toBeNull();
  expect(screen.queryByRole("link", { name: /WMS 물류/ })).toBeNull();
});
it("상세 안내는 첫 화면에서 숨긴다", async () => {
  show();
  expect(
    await screen.findByText("계획에서 실적, 패킹과 입고까지"),
  ).not.toBeVisible();
});
it("키보드 포커스로 앱 상태와 설명을 볼 수 있다", async () => {
  show();
  fireEvent.focus(await screen.findByRole("link", { name: /MES 생산관리/ }));
  expect(screen.getByText("계획에서 실적, 패킹과 입고까지")).toBeVisible();
});
it("Escape로 상세 안내를 닫는다", async () => {
  show();
  const link = await screen.findByRole("link", { name: /MES 생산관리/ });
  fireEvent.focus(link);
  fireEvent.keyDown(link, { key: "Escape" });
  expect(screen.getByText("계획에서 실적, 패킹과 입고까지")).not.toBeVisible();
});
it("터치용 안내 버튼은 상세 상태를 토글한다", async () => {
  show();
  const button = await screen.findByRole("button", { name: "ERP 상세 안내" });
  fireEvent.click(button);
  expect(button).toHaveAttribute("aria-expanded", "true");
  fireEvent.click(button);
  expect(button).toHaveAttribute("aria-expanded", "false");
});
it("꺼진 앱의 안내는 내 공간에서 켜기를 표시한다", async () => {
  show(false);
  fireEvent.click(await screen.findByRole("button", { name: "MES 상세 안내" }));
  expect(
    screen.getByText("내 공간에서 켜기", {
      selector: "#launcher-description-mes .launcher-destination",
    }),
  ).toBeVisible();
});
