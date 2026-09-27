import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import VisionExplanation from "./VisionExplanation";
import { demoExplanation, scenarioEvidence, scenarios } from "./scenarios";
import { api, ApiError } from "../shared/api";
import { visionAt } from "./vision";
const fail = vi.hoisted(() => vi.fn());
vi.mock("../shared/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../shared/api")>()),
  api: vi.fn(),
}));
vi.mock("../app/session", () => ({
  useSession: () => ({ session: { csrfToken: "test-csrf" }, fail }),
}));
beforeEach(() => {
  vi.mocked(api).mockReset();
  fail.mockReset();
});
it("시나리오 빈도와 비교 구간 수치가 일치한다", () => {
  for (const scenario of ["normal", "reject-rise"] as const) {
    const value = visionAt(600, false, scenarios[scenario].rejectEvery);
    expect(value.inspected).toBe(scenarios[scenario].current.inspected);
    expect(value.rejected).toBe(scenarios[scenario].current.rejected);
  }
  expect(scenarioEvidence("reject-rise")[2]).toBe("불합격률 변화: +18%p");
  expect(scenarioEvidence("stopped")[2]).toBe("불합격률 변화: +0%p");
});
it("미설정 응답을 AI 생성으로 표시하지 않고 근거를 보여준다", async () => {
  vi.mocked(api).mockResolvedValue({
    data: demoExplanation("reject-rise", "not_configured"),
  });
  render(<VisionExplanation scenario="reject-rise" />);
  fireEvent.click(screen.getByRole("button", { name: "AI 설명" }));
  expect(await screen.findByText("데모 설명 · AI 미연결")).toBeVisible();
  expect(screen.getByText("불합격률 변화: +18%p")).toBeVisible();
  expect(api).toHaveBeenCalledWith(
    "/api/v1/factory/vision/explanation",
    expect.objectContaining({
      method: "POST",
      body: { scenario: "reject-rise" },
      csrf: "test-csrf",
    }),
  );
});
it("실제 AI 형식 응답만 모델 출처를 표시한다", async () => {
  vi.mocked(api).mockResolvedValue({
    data: {
      ...demoExplanation("normal", ""),
      mode: "ai",
      model: "gpt-6-astra",
      reason: null,
    },
  });
  render(<VisionExplanation scenario="normal" />);
  fireEvent.click(screen.getByRole("button", { name: "AI 설명" }));
  expect(await screen.findByText("AI 생성 · GPT-6 Astra")).toBeVisible();
});
it("이전 시나리오 응답은 취소하고 새 화면에 섞지 않는다", async () => {
  let resolve!: (data: { data: unknown }) => void;
  vi.mocked(api).mockImplementationOnce(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  const { rerender } = render(
    <VisionExplanation key="normal" scenario="normal" />,
  );
  fireEvent.click(screen.getByRole("button", { name: "AI 설명" }));
  const signal = vi.mocked(api).mock.calls[0][1]?.signal;
  rerender(<VisionExplanation key="stopped" scenario="stopped" />);
  expect(signal?.aborted).toBe(true);
  await act(async () =>
    resolve({ data: demoExplanation("normal", "not_configured") }),
  );
  expect(screen.queryByText(scenarios.normal.summary)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "AI 설명" })).toBeEnabled();
});
it("연결 오류 또는 잘못된 응답은 표시된 데모로 대체한다", async () => {
  vi.mocked(api).mockResolvedValue({
    data: { scenario: "stopped", mode: "ai" },
  });
  render(<VisionExplanation scenario="normal" />);
  fireEvent.click(screen.getByRole("button", { name: "AI 설명" }));
  expect(await screen.findByText("데모 설명 · AI 미연결")).toBeVisible();
  expect(screen.getByText(scenarios.normal.summary)).toBeVisible();
});
it("세션 만료는 설명 데모로 숨기지 않는다", async () => {
  const error = new ApiError(401, { code: "SESSION_EXPIRED", message: "만료" });
  vi.mocked(api).mockRejectedValue(error);
  render(<VisionExplanation scenario="normal" />);
  fireEvent.click(screen.getByRole("button", { name: "AI 설명" }));
  await waitFor(() => expect(fail).toHaveBeenCalledWith(error));
  expect(screen.queryByText("데모 설명 · AI 미연결")).not.toBeInTheDocument();
});
