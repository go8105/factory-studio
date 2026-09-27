import { expect, it, vi, afterEach } from "vitest";
import { NativeEngine } from "./nativeEngine";
import { api, ApiError } from "../shared/api";
import { defaultRecipe, inspect } from "./inspection";
vi.mock("../shared/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../shared/api")>()),
  api: vi.fn(),
}));
const request = {
  version: 1 as const,
  sample: "foreign" as const,
  recipe: defaultRecipe,
};
const result = {
  ...inspect(request),
  source: "synthetic-opencv-cpp-v1" as const,
};
afterEach(() => vi.clearAllMocks());
it("네이티브 요청 ID·CSRF를 전달하고 순수 시간을 사용한다", async () => {
  vi.mocked(api).mockResolvedValue({
    data: { requestId: "run:1", result, inspectionMs: 1.25 },
  });
  const engine = new NativeEngine("csrf", vi.fn());
  expect(await engine.execute(request, "run:1")).toEqual({
    result,
    inspectionMs: 1.25,
  });
  expect(api).toHaveBeenCalledWith(
    "/api/v1/factory/vision/inspect",
    expect.objectContaining({
      csrf: "csrf",
      body: { requestId: "run:1", request },
    }),
  );
});
it("다른 요청 ID와 브라우저 출처는 거부한다", async () => {
  const engine = new NativeEngine("csrf", vi.fn());
  for (const data of [
    { requestId: "old", result, inspectionMs: 1 },
    { requestId: "run:1", result: inspect(request), inspectionMs: 1 },
  ]) {
    vi.mocked(api).mockResolvedValue({ data });
    await expect(engine.execute(request, "run:1")).rejects.toThrow("형식");
  }
});
it("취소 후 늦은 응답은 수용하지 않는다", async () => {
  let complete!: (value: { data: unknown }) => void;
  vi.mocked(api).mockImplementation(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  );
  const engine = new NativeEngine("csrf", vi.fn());
  const pending = engine.execute(request, "run:1");
  engine.cancel();
  complete({ data: { requestId: "run:1", result, inspectionMs: 1 } });
  await expect(pending).rejects.toThrow("취소");
});
it("미설정은 실패하며 세션 만료만 공통 처리한다", async () => {
  const fail = vi.fn();
  const engine = new NativeEngine("csrf", fail);
  vi.mocked(api).mockRejectedValue(
    new ApiError(503, { code: "NATIVE_UNAVAILABLE", message: "미설정" }),
  );
  await expect(engine.execute(request)).rejects.toThrow("미설정");
  expect(fail).not.toHaveBeenCalled();
  vi.mocked(api).mockRejectedValue(
    new ApiError(401, { code: "SESSION_EXPIRED", message: "만료" }),
  );
  await expect(engine.execute(request)).rejects.toThrow("만료");
  expect(fail).toHaveBeenCalledOnce();
});
