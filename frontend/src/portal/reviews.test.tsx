// FS-040: 런처 평가 한 줄·패널(AC-241·243 화면 쪽).
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const guest = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const modules = ["core", "mes", "erp"].map((moduleKey) => ({
  moduleKey,
  enabled: true,
  updatedAt: null,
}));
function reply(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status });
}

it("평점 한 줄을 보이고, 패널에서 별점·별칭·한줄평으로 평가한다", async () => {
  let posted: Record<string, unknown> | undefined;
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const path = String(input);
      if (path.endsWith("/sessions/current")) return reply({ data: guest });
      if (path.endsWith("/workspace/modules")) return reply({ data: modules });
      if (path.endsWith("/reviews/summary"))
        return reply({
          data: [
            { moduleKey: "mes", average: 4.8, count: 12, reviewed: false },
          ],
        });
      if (path.includes("/reviews?moduleKey=")) return reply({ data: [] });
      if (path.endsWith("/reviews") && init?.method === "POST") {
        posted = JSON.parse(String(init.body));
        return reply(
          {
            error: {
              code: "NICKNAME_TAKEN",
              message: "이 별칭으로 이미 평가가 있습니다. 다른 별칭을 쓰세요.",
              details: {
                fields: { nickname: "이 별칭으로 이미 평가가 있습니다." },
              },
            },
          },
          409,
        );
      }
      return reply({ data: [] });
    });
  render(
    <MemoryRouter initialEntries={["/home"]}>
      <App />
    </MemoryRouter>,
  );
  const mes = await screen.findByRole("button", {
    name: "MES 평점 4.8, 후기 12건 보기",
  });
  expect(mes).toHaveTextContent("4.8 · 후기 12");
  expect(
    screen.getByRole("button", { name: "ERP 평가 남기기" }),
  ).toHaveTextContent("평가 모으는 중");
  fireEvent.click(mes);
  const panel = await screen.findByRole("dialog", { name: "MES 평가" });
  const form = within(panel);
  fireEvent.click(form.getByRole("button", { name: "평가 남기기" }));
  expect(
    await form.findByText("별점을 고르세요.", { selector: "small" }),
  ).toBeVisible();
  fireEvent.click(form.getByLabelText("4점"));
  fireEvent.change(form.getByLabelText("별칭"), { target: { value: "현장1" } });
  fireEvent.change(form.getByLabelText("한줄평"), {
    target: { value: "작업지시가 편해요" },
  });
  fireEvent.click(form.getByRole("button", { name: "평가 남기기" }));
  expect(
    await form.findByText("이 별칭으로 이미 평가가 있습니다.", {
      selector: "small",
    }),
  ).toBeVisible();
  expect(posted).toEqual({
    moduleKey: "mes",
    rating: 4,
    comment: "작업지시가 편해요",
    nickname: "현장1",
  });
  const post = fetcher.mock.calls.find(([, init]) => init?.method === "POST");
  expect(new Headers(post?.[1]?.headers).get("X-CSRF-Token")).toBe("test-csrf");
});
