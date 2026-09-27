import { afterEach, expect, it, vi } from "vitest";
import { defaultRecipe, inspect, type InspectionRequest } from "./inspection";
import { InspectionRun, runSummary, type Engine } from "./inspectionRun";
import { PlcHandshake, plcSignals } from "./plcHandshake";
const request: InspectionRequest = {
  version: 1,
  sample: "foreign",
  recipe: defaultRecipe,
};
const output = { result: inspect(request), inspectionMs: 2 };
const engine: Engine = async () => output;
afterEach(() => vi.useRealTimers());
it("신호 순서와 결과 래치 및 확인 후 해제를 보장한다", async () => {
  vi.useFakeTimers();
  const plc = new PlcHandshake(engine);
  const result = plc.execute(request, "run:1");
  expect(plcSignals(plc.state)).toMatchObject({
    Trigger_In: true,
    Vision_Busy: true,
    Vision_Ready: false,
    Inspection_Done: false,
  });
  await vi.advanceTimersByTimeAsync(80);
  expect(plcSignals(plc.state)).toMatchObject({
    Vision_Busy: false,
    Inspection_Done: true,
    Result_NG: true,
    Result_OK: false,
    Trigger_In: true,
  });
  await vi.advanceTimersByTimeAsync(120);
  expect(await result).toEqual(output);
  expect(plcSignals(plc.state)).toMatchObject({
    Vision_Ready: true,
    Inspection_Done: false,
    Result_NG: false,
    Trigger_In: false,
  });
  expect(plc.state.events.map((e) => e.inspectionId)).toEqual([
    "run:1",
    "run:1",
    "run:1",
  ]);
  expect(vi.getTimerCount()).toBe(0);
});
it("Busy 중 중복 요청은 검사 엔진을 다시 호출하지 않는다", async () => {
  vi.useFakeTimers();
  const fn = vi.fn(engine);
  const plc = new PlcHandshake(fn);
  const result = plc.execute(request);
  await expect(plc.execute(request)).rejects.toThrow("not ready");
  await vi.runAllTimersAsync();
  await result;
  expect(fn).toHaveBeenCalledTimes(1);
});
it("검사 지연은 인터락을 걸고 리셋 전 신규 요청을 차단한다", async () => {
  vi.useFakeTimers();
  const plc = new PlcHandshake(engine);
  plc.inject("delay");
  const result = plc.execute(request).catch((error: Error) => error.message);
  await vi.advanceTimersByTimeAsync(300);
  expect(await result).toBe("INSPECTION_TIMEOUT");
  expect(plcSignals(plc.state)).toMatchObject({
    Interlock: true,
    Vision_Ready: false,
    Vision_Busy: false,
    Result_OK: false,
    Result_NG: false,
  });
  await expect(plc.execute(request)).rejects.toThrow();
  plc.cancel();
  expect(plc.state.fault).toBe("INSPECTION_TIMEOUT");
  plc.reset();
  expect(plc.state.phase).toBe("ready");
  const recovered = plc.execute(request);
  await vi.runAllTimersAsync();
  expect(await recovered).toEqual(output);
});
it("확인 누락은 판정과 Done을 보존하고 수동 확인만으로 오류를 해제하지 못한다", async () => {
  vi.useFakeTimers();
  const plc = new PlcHandshake(engine);
  plc.inject("missingAck");
  const result = plc.execute(request).catch((error: Error) => error.message);
  await vi.runAllTimersAsync();
  expect(await result).toBe("ACK_TIMEOUT");
  expect(plcSignals(plc.state)).toMatchObject({
    Inspection_Done: true,
    Result_NG: true,
    Interlock: true,
    Trigger_In: true,
  });
  expect(plc.state.inspection?.output).toEqual(output);
  plc.acknowledge();
  expect(plc.state.phase).toBe("fault");
  plc.reset();
  expect(plc.state.inspection).toBeNull();
  expect(plc.state.result).toBeNull();
});
it("확인 제한 전 수동 확인은 거래를 한 번만 완료한다", async () => {
  vi.useFakeTimers();
  const plc = new PlcHandshake(engine);
  plc.inject("missingAck");
  const done = vi.fn();
  const result = plc.execute(request).then(done);
  await vi.advanceTimersByTimeAsync(80);
  plc.acknowledge();
  plc.acknowledge();
  await vi.runAllTimersAsync();
  await result;
  expect(done).toHaveBeenCalledTimes(1);
  expect(plc.state.phase).toBe("ready");
});
it("검사 타임아웃 후 늦은 엔진 응답은 리셋된 신호에 반영하지 않는다", async () => {
  vi.useFakeTimers();
  let resolve!: (value: typeof output) => void;
  const plc = new PlcHandshake(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  const result = plc.execute(request).catch(() => {});
  await vi.advanceTimersByTimeAsync(300);
  await result;
  plc.reset();
  resolve(output);
  await vi.runAllTimersAsync();
  expect(plc.state.phase).toBe("ready");
  expect(plc.state.done).toBe(false);
  expect(plc.state.inspection).toBeNull();
});
it("타이머가 늦게 실행되어도 경과시간으로 검사 제한을 적용한다", async () => {
  vi.useFakeTimers();
  const plc = new PlcHandshake(async () => {
    vi.spyOn(performance, "now").mockReturnValueOnce(301);
    return output;
  });
  const result = plc.execute(request).catch((e: Error) => e.message);
  await vi.advanceTimersByTimeAsync(80);
  expect(await result).toBe("INSPECTION_TIMEOUT");
  vi.restoreAllMocks();
});
it("엔진 오류는 별도 알람이고 취소는 모든 타이머를 해제한다", async () => {
  vi.useFakeTimers();
  const plc = new PlcHandshake(async () => {
    throw new Error("engine failed");
  });
  const result = plc.execute(request).catch((e: Error) => e.message);
  await vi.runAllTimersAsync();
  expect(await result).toBe("ENGINE_ERROR");
  plc.reset();
  const cancelled = plc.execute(request).catch((e: Error) => e.message);
  plc.cancel();
  await vi.runAllTimersAsync();
  expect(await cancelled).toBe("PLC cancelled");
  expect(vi.getTimerCount()).toBe(0);
});
it("PLC 연결 배치가 20회 확인되고 장애 거래는 수량에 포함하지 않는다", async () => {
  vi.useFakeTimers();
  const plc = new PlcHandshake();
  const runner = new InspectionRun(defaultRecipe, plc.execute, () =>
    plc.cancel(),
  );
  runner.start(defaultRecipe, 200);
  await vi.runAllTimersAsync();
  expect(runSummary(runner.state.records)).toMatchObject({
    completed: 20,
    ok: 10,
    ng: 10,
  });
  expect(
    plc.state.events.filter((e) => e.event.includes("PLC 결과 확인")),
  ).toHaveLength(20);
  plc.inject("missingAck");
  runner.start(defaultRecipe, 200);
  await vi.runAllTimersAsync();
  expect(runner.state.status).toBe("error");
  expect(runner.state.records).toHaveLength(0);
  expect(plc.state.fault).toBe("ACK_TIMEOUT");
});
it("일시정지는 진행 거래 확인까지 허용하고 종료는 거래를 취소한다", async () => {
  vi.useFakeTimers();
  const plc = new PlcHandshake();
  const run = new InspectionRun(defaultRecipe, plc.execute, () => plc.cancel());
  run.start(defaultRecipe, 500);
  run.pause();
  await vi.runAllTimersAsync();
  expect(run.state.records).toHaveLength(1);
  expect(plc.state.phase).toBe("ready");
  run.resume();
  await vi.advanceTimersByTimeAsync(500);
  run.stop();
  await vi.runAllTimersAsync();
  expect(run.state.records).toHaveLength(1);
  expect(plc.state.phase).toBe("ready");
  expect(vi.getTimerCount()).toBe(0);
});

it("동기 예외를 던지는 교체 엔진도 알람으로 종료한다", async () => {
  vi.useFakeTimers();
  const plc = new PlcHandshake(() => {
    throw new Error("sync engine failure");
  });
  const result = plc.execute(request).catch((e: Error) => e.message);
  await vi.runAllTimersAsync();
  expect(await result).toBe("ENGINE_ERROR");
  expect(vi.getTimerCount()).toBe(0);
});

it("새 배치 로그에는 이전 요청 ID가 섞이지 않고 신호는 상호 배타적이다", async () => {
  vi.useFakeTimers();
  const plc = new PlcHandshake(engine);
  const result = plc.execute(request, "old:1");
  await vi.runAllTimersAsync();
  await result;
  plc.clearLog();
  expect(plc.state.events[0].inspectionId).toBeNull();
  expect(plc.state.inspection).toBeNull();
  const next = plc.execute(request, "new:1");
  await vi.runAllTimersAsync();
  await next;
  for (const event of plc.state.events) {
    expect(event.signals.Result_OK && event.signals.Result_NG).toBe(false);
    expect(event.signals.Vision_Ready && event.signals.Vision_Busy).toBe(false);
    expect(event.inspectionId === null || event.inspectionId === "new:1").toBe(
      true,
    );
  }
});
