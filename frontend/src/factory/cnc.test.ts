import { expect, it } from "vitest";
import {
  cncReducer,
  initialCnc,
  cncPose,
  cncPhases,
  type CncState,
} from "./cnc";
function tick(s: CncState, n: number) {
  for (let i = 0; i < n; i++) s = cncReducer(s, { type: "tick", seconds: 0.1 });
  return s;
}
it("단일 소재는 한 번만 완료 집계하고 중복 시작을 무시한다", () => {
  let s = cncReducer(initialCnc(), { type: "start" });
  s = tick(s, 10);
  expect(cncReducer(s, { type: "start" })).toBe(s);
  s = tick(s, 250);
  expect(s.mode).toBe("complete");
  expect(s.completed).toBe(1);
  expect(cncPose(s).location).toBe("output");
  expect(tick(s, 200).completed).toBe(1);
  s = cncReducer(s, { type: "start" });
  expect(tick(s, 250).completed).toBe(2);
});
it("모든 단계에서 일시정지와 오류는 소재 위치·가공 진행을 보존한다", () => {
  for (let phase = 0; phase < cncPhases.length; phase++) {
    let s: CncState = { ...initialCnc(), mode: "running", phase, elapsed: 0.3 };
    const pose = cncPose(s);
    s = cncReducer(s, { type: "pause" });
    expect(tick(s, 100)).toEqual(s);
    expect(cncPose(s).block).toEqual(pose.block);
    expect(cncPose(s).hand).toEqual(pose.hand);
    expect(cncPose(s).spindle).toBe(false);
    s = cncReducer(s, { type: "fault" });
    expect(cncReducer(s, { type: "resume" })).toBe(s);
    expect(cncReducer(s, { type: "start" })).toBe(s);
    expect(cncReducer(s, { type: "stop" })).toBe(s);
    s = cncReducer(s, { type: "clear" });
    expect(s.mode).toBe("paused");
    expect(tick(s, 100)).toBe(s);
    expect(cncPose(s).block).toEqual(pose.block);
    s = cncReducer(s, { type: "resume" });
    expect(s.mode).toBe("running");
    expect(tick(s, 250).completed).toBe(1);
  }
});
it("주축은 문 닫힘·고정·퇴피 상태에서만 가동하고 문 개방 전에 정지한다", () => {
  let s = cncReducer(initialCnc(), { type: "start" });
  let cutting = false;
  for (let i = 0; i < 230; i++) {
    const pose = cncPose(s);
    if (pose.spindle) {
      cutting = true;
      expect(pose.door).toBe(1);
      expect(pose.clamped).toBe(true);
      expect(pose.clear).toBe(true);
      expect(pose.location).toBe("jig");
    }
    if (pose.door < 1) expect(pose.spindle).toBe(false);
    s = tick(s, 1);
  }
  expect(cutting).toBe(true);
});
it("종료 소재는 보류만 증가하며 오류 래치를 우회하지 않는다", () => {
  let s = tick(cncReducer(initialCnc(), { type: "start" }), 50);
  s = cncReducer(s, { type: "stop" });
  expect(s.held).toBe(1);
  expect(s.completed).toBe(0);
  expect(s.mode).toBe("idle");
  expect(cncReducer(s, { type: "stop" })).toBe(s);
  s = tick(cncReducer(s, { type: "start" }), 250);
  expect(s.completed).toBe(1);
  expect(s.held).toBe(1);
});
it("긴 프레임·유효하지 않은 시간은 단계 건너뛰기나 실적 생성을 하지 않는다", () => {
  const s = cncReducer(initialCnc(), { type: "start" });
  for (const seconds of [NaN, Infinity, -1, 0])
    expect(cncReducer(s, { type: "tick", seconds })).toBe(s);
  expect(cncReducer(s, { type: "tick", seconds: 1000 }).phase).toBe(0);
});
