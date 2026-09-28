import { act, renderHook } from "@testing-library/react";
import { expect, it, vi, afterEach } from "vitest";
import { useCnc } from "./useCnc";
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});
it("탭 숨김은 운전을 일시정지하고 복귀만으로 재개하지 않는다", () => {
  vi.useFakeTimers();
  const { result, unmount } = renderHook(() => useCnc(true));
  act(() => result.current[1]({ type: "start" }));
  act(() => vi.advanceTimersByTime(300));
  expect(result.current[0].elapsed).toBeGreaterThan(0);
  const hidden = vi.spyOn(document, "hidden", "get").mockReturnValue(true);
  act(() => document.dispatchEvent(new Event("visibilitychange")));
  const paused = result.current[0];
  expect(paused.mode).toBe("paused");
  hidden.mockReturnValue(false);
  act(() => {
    document.dispatchEvent(new Event("visibilitychange"));
    vi.advanceTimersByTime(2000);
  });
  expect(result.current[0]).toEqual(paused);
  unmount();
  expect(vi.getTimerCount()).toBe(0);
});
it("전체 정지·그래픽 대기 동안 진행하지 않고 재활성화 후 위치를 이어간다", () => {
  vi.useFakeTimers();
  const { result, rerender, unmount } = renderHook(
    ({ enabled }) => useCnc(enabled),
    { initialProps: { enabled: true } },
  );
  act(() => result.current[1]({ type: "start" }));
  act(() => vi.advanceTimersByTime(300));
  rerender({ enabled: false });
  const snapshot = result.current[0];
  act(() => vi.advanceTimersByTime(10000));
  expect(result.current[0]).toEqual(snapshot);
  rerender({ enabled: true });
  act(() => vi.advanceTimersByTime(100));
  expect(result.current[0].phase).toBe(snapshot.phase);
  expect(result.current[0].elapsed).toBeGreaterThan(snapshot.elapsed);
  unmount();
  expect(vi.getTimerCount()).toBe(0);
});
