import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { EmergencyKit } from "./EmergencyKit";
import { CompanyContext } from "./common";
const state = vi.hoisted(() => ({
  setNavigationBlocked: vi.fn(),
  fail: vi.fn(),
}));
vi.mock("../app/session", () => ({
  useSession: () => ({
    session: { workspaceId: 1, generationId: 2, csrfToken: "synthetic-csrf" },
    ...state,
  }),
}));
const reply = (data: unknown, status = 200) =>
  new Response(JSON.stringify(status < 400 ? { data } : { error: data }), {
    status,
  });
const kit = {
  version: 1,
  userId: "1",
  companyId: "10",
  generationId: "20",
  personId: "30",
  kitId: "40",
  kitSecret: "SYNTHETIC-DO-NOT-USE",
};
beforeEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});
afterEach(() => vi.unstubAllGlobals());
function show(props: Partial<Parameters<typeof EmergencyKit>[0]> = {}) {
  const reload = vi.fn();
  render(
    <MemoryRouter>
      <CompanyContext.Provider value={{ companyId: "10" }}>
        <EmergencyKit
          reload={reload}
          status={{ prepared: false, expiresAt: null }}
          {...props}
        />
      </CompanyContext.Provider>
    </MemoryRouter>,
  );
  return reload;
}
it("문서는 동의 후 발급하고 파일 저장·보관 확인 전 화면을 닫지 않는다", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(reply({ kit, expiresAt: "2027-10-18T00:00:00Z" }));
  const create = vi.fn(() => "blob:synthetic"),
    revoke = vi.fn();
  vi.stubGlobal(
    "URL",
    class extends URL {
      static createObjectURL = create;
      static revokeObjectURL = revoke;
    },
  );
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const reload = show();
  const submit = screen.getByRole("button", {
    name: "본인 긴급 복구 문서 새로 발급",
  });
  expect(submit).toBeDisabled();
  fireEvent.change(screen.getByLabelText("긴급 복구 문서 발급 사유"), {
    target: { value: "합성 문서 별도 보관" },
  });
  fireEvent.click(
    screen.getByLabelText(
      "이전 문서·미사용 승인 파일 회수와 별도 보관 필요를 확인했습니다",
    ),
  );
  fireEvent.click(submit);
  expect(
    await screen.findByRole("heading", {
      name: "긴급 복구 문서를 지금 보관하세요",
    }),
  ).toBeVisible();
  expect(screen.queryByText(kit.kitSecret)).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "보관 확인하고 닫기" }),
  ).toBeDisabled();
  expect(
    screen.getByLabelText("파일을 안전한 별도 장소에 보관했습니다"),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "긴급 복구 문서 파일 저장" }),
  );
  expect(create).toHaveBeenCalledOnce();
  fireEvent.click(
    screen.getByLabelText("파일을 안전한 별도 장소에 보관했습니다"),
  );
  fireEvent.click(screen.getByRole("button", { name: "보관 확인하고 닫기" }));
  expect(reload).toHaveBeenCalledOnce();
  expect(state.setNavigationBlocked).toHaveBeenCalledWith(true);
  expect(fetch.mock.calls[0][0]).toBe("/api/v1/gw/emergency-kit?companyId=10");
});
it("추가 인증 거부 후 사유를 유지하며 자동 발급을 반복하지 않는다", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    reply(
      {
        code: "STEP_UP_REQUIRED",
        message: "내 계정 보안에서 본인을 다시 확인해 주세요.",
      },
      403,
    ),
  );
  show();
  const input = screen.getByLabelText("긴급 복구 문서 발급 사유");
  fireEvent.change(input, { target: { value: "합성 사유 유지" } });
  fireEvent.click(
    screen.getByLabelText(
      "이전 문서·미사용 승인 파일 회수와 별도 보관 필요를 확인했습니다",
    ),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "본인 긴급 복구 문서 새로 발급" }),
  );
  expect(
    await screen.findByText("내 계정 보안에서 본인을 다시 확인해 주세요."),
  ).toBeVisible();
  expect(input).toHaveValue("합성 사유 유지");
  expect(fetch).toHaveBeenCalledOnce();
  expect(
    screen.getByRole("link", { name: "새 탭에서 본인 확인" }),
  ).toHaveAttribute("target", "_blank");
});
it("운영 기준 편집 중에는 긴급 문서를 발급하지 않는다", async () => {
  const fetch = vi.spyOn(globalThis, "fetch");
  show({ disabled: true });
  expect(
    screen.getByRole("button", { name: "본인 긴급 복구 문서 새로 발급" }),
  ).toBeDisabled();
  await waitFor(() => expect(fetch).not.toHaveBeenCalled());
});
