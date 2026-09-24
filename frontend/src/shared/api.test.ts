import { expect, it, vi } from "vitest";
import { api, ApiError, MutationKeys } from "./api";
it("변경 요청은 CSRF와 멱등 키를 전달한다", async () => {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(
      new Response(JSON.stringify({ data: { enabled: false } })),
    );
  await api("/workspace/modules/mes", {
    method: "PATCH",
    csrf: "csrf",
    key: "same-key",
    body: { enabled: false },
  });
  expect(fetcher).toHaveBeenCalledWith(
    "/api/v1/core/workspace/modules/mes",
    expect.objectContaining({
      credentials: "same-origin",
      headers: expect.objectContaining({
        "X-CSRF-Token": "csrf",
        "Idempotency-Key": "same-key",
      }),
    }),
  );
});
it("네트워크 불확실은 성공으로 처리하지 않는다", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network"));
  await expect(api("/workspace")).rejects.toMatchObject({
    status: 0,
    error: { code: "NETWORK_UNCERTAIN" },
  });
});
it("오류 응답은 서버 봉투를 보존한다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({ error: { code: "NOT_FOUND", message: "없음" } }),
      { status: 404 },
    ),
  );
  await expect(api("/admin/job-runs")).rejects.toBeInstanceOf(ApiError);
});
it("불확실한 변경의 재시도 키는 유지한다", () => {
  const keys = new MutationKeys();
  expect(keys.get("reset")).toBe(keys.get("reset"));
});
it("확인된 변경 이후의 새 동작에는 새 키를 발급한다", () => {
  const keys = new MutationKeys();
  const first = keys.get("reset");
  keys.complete("reset");
  expect(keys.get("reset")).not.toBe(first);
});
