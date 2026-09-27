import { afterEach, expect, it, vi } from "vitest";
import { defaultRecipe, inspect } from "./inspection";
import { InspectionRun, runSummary, type Engine } from "./inspectionRun";
afterEach(() => vi.useRealTimers());
it("20회 고정 시퀀스와 레시피 스냅샷을 유지한다", async () => {
  vi.useFakeTimers();
  const recipe = { ...defaultRecipe };
  const run = new InspectionRun(recipe);
  run.start(recipe, 200);
  recipe.minArea = 100;
  run.start(recipe, 200);
  await vi.runAllTimersAsync();
  expect(run.state.status).toBe("completed");
  expect(runSummary(run.state.records)).toMatchObject({
    completed: 20,
    ok: 10,
    ng: 10,
    passRate: 50,
  });
  expect(new Set(run.state.records.map((r) => r.inspectionId)).size).toBe(20);
  expect(run.state.records.every((r) => r.request.recipe.minArea === 20)).toBe(
    true,
  );
});
it("일시정지와 재개는 중복 없이 다음 순번을 실행한다", async () => {
  vi.useFakeTimers();
  const run = new InspectionRun(defaultRecipe);
  run.start(defaultRecipe, 500);
  await vi.advanceTimersByTimeAsync(0);
  run.pause();
  await vi.advanceTimersByTimeAsync(5000);
  expect(run.state.records).toHaveLength(1);
  run.resume();
  run.resume();
  await vi.runAllTimersAsync();
  expect(run.state.records.map((r) => r.sequence)).toEqual(
    Array.from({ length: 20 }, (_, i) => i + 1),
  );
});
it("종료한 비동기 검사의 늦은 응답은 새 배치를 오염시키지 않는다", async () => {
  vi.useFakeTimers();
  let resolve!: (v: Awaited<ReturnType<Engine>>) => void;
  const engine: Engine = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    )
    .mockImplementation(async (request) => ({
      result: inspect(request),
      inspectionMs: 1,
    }));
  const run = new InspectionRun(defaultRecipe, engine);
  run.start(defaultRecipe, 500);
  run.stop();
  run.start({ ...defaultRecipe, minArea: 100 }, 500);
  resolve({
    result: inspect({ version: 1, sample: "foreign", recipe: defaultRecipe }),
    inspectionMs: 99,
  });
  await vi.runAllTimersAsync();
  expect(runSummary(run.state.records)).toMatchObject({
    completed: 20,
    ok: 20,
    ng: 0,
  });
  expect(run.state.records.every((r) => r.inspectionMs === 1)).toBe(true);
});
it("진행 중 일시정지는 결과 하나를 반영하고 다음 투입을 보류한다", async () => {
  vi.useFakeTimers();
  let resolve!: (v: Awaited<ReturnType<Engine>>) => void;
  const run = new InspectionRun(
    defaultRecipe,
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  run.start(defaultRecipe, 500);
  run.pause();
  resolve({
    result: inspect({ version: 1, sample: "normal", recipe: defaultRecipe }),
    inspectionMs: 1,
  });
  await vi.runAllTimersAsync();
  expect(run.state.status).toBe("paused");
  expect(run.state.records).toHaveLength(1);
  run.stop();
});
it("검사 실패는 NG 수량에 포함하지 않는다", async () => {
  vi.useFakeTimers();
  const run = new InspectionRun(defaultRecipe, async () => {
    throw new Error("failure");
  });
  run.start(defaultRecipe, 500);
  await vi.runAllTimersAsync();
  expect(run.state.status).toBe("error");
  expect(runSummary(run.state.records)).toMatchObject({
    completed: 0,
    ng: 0,
    passRate: null,
    averageMs: null,
  });
});
it("종료하면 예약된 검사와 구독이 정리된다", async () => {
  vi.useFakeTimers();
  const run = new InspectionRun(defaultRecipe);
  const changed = vi.fn();
  const unsubscribe = run.subscribe(changed);
  run.start(defaultRecipe, 500);
  await vi.advanceTimersByTimeAsync(0);
  run.stop();
  unsubscribe();
  changed.mockClear();
  await vi.runAllTimersAsync();
  expect(run.state.records).toHaveLength(1);
  expect(changed).not.toHaveBeenCalled();
});
