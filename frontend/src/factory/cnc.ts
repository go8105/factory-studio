export const cncPhases = [
  ["소재 집기", 1.2],
  ["소재 투입", 1.8],
  ["로봇 퇴피", 1.2],
  ["소재 고정", 0.7],
  ["문 닫기", 1],
  ["CNC 가공", 4],
  ["주축 정지", 0.8],
  ["문 열기", 1],
  ["고정 해제", 0.7],
  ["제품 꺼내기", 1.5],
  ["검사 대기 위치로 배출", 1.8],
] as const;
export type CncState = {
  mode: "idle" | "running" | "paused" | "fault" | "complete";
  phase: number;
  elapsed: number;
  completed: number;
  held: number;
  alarm: boolean;
  message: string;
};
export const initialCnc = (): CncState => ({
  mode: "idle",
  phase: 0,
  elapsed: 0,
  completed: 0,
  held: 0,
  alarm: false,
  message: "시작하면 소재 1개를 가공합니다.",
});
export type CncAction =
  | { type: "tick"; seconds: number }
  | { type: "start" | "pause" | "resume" | "fault" | "clear" | "stop" };
export function cncReducer(s: CncState, a: CncAction): CncState {
  switch (a.type) {
    case "start":
      return s.mode === "idle" || s.mode === "complete"
        ? {
            ...s,
            mode: "running",
            phase: 0,
            elapsed: 0,
            message: "단일 소재 가공 중",
          }
        : s;
    case "pause":
      return s.mode === "running"
        ? { ...s, mode: "paused", message: "소재와 진행 위치를 보존했습니다." }
        : s;
    case "resume":
      return s.mode === "paused" && !s.alarm
        ? { ...s, mode: "running", message: "보존한 위치에서 재개합니다." }
        : s;
    case "fault":
      return s.mode === "running" || s.mode === "paused"
        ? {
            ...s,
            mode: "fault",
            alarm: true,
            message: "모의 구동 오류 · 신규 투입 및 주축 정지",
          }
        : s;
    case "clear":
      return s.mode === "fault"
        ? {
            ...s,
            mode: "paused",
            alarm: false,
            message: "오류 해제 완료 · 재개 버튼으로 복구하세요.",
          }
        : s;
    case "stop": {
      if (s.mode === "fault" || s.mode === "idle" || s.mode === "complete")
        return s;
      return {
        ...initialCnc(),
        completed: s.completed,
        held: s.held + 1,
        message:
          "진행 소재 1개를 보류 처리했습니다. 완료 수에 포함하지 않습니다.",
      };
    }
    case "tick": {
      if (s.mode !== "running" || !Number.isFinite(a.seconds) || a.seconds <= 0)
        return s;
      // Never catch up across a background-tab gap or skip interlock stages.
      const elapsed = s.elapsed + Math.min(a.seconds, 0.1);
      if (elapsed < cncPhases[s.phase][1]) return { ...s, elapsed };
      if (s.phase === cncPhases.length - 1)
        return {
          ...s,
          elapsed: cncPhases[s.phase][1],
          mode: "complete",
          completed: s.completed + 1,
          message:
            "가공 완료 · 검사 대기 위치에 배출했습니다. 비전검사는 별도 시연입니다.",
        };
      return { ...s, phase: s.phase + 1, elapsed: 0 };
    }
  }
}
export type CncPoint = [number, number, number];
const home: CncPoint = [-0.95, 1.65, 0.7];
const input: CncPoint = [-0.95, 1.03, 0.96];
const jig: CncPoint = [0.25, 1.22, -0.3];
const approach: CncPoint = [0.25, 1.4, 0.85];
function transfer(a: CncPoint, b: CncPoint, t: number): CncPoint {
  return t < 0.5 ? lerp(a, approach, t * 2) : lerp(approach, b, (t - 0.5) * 2);
}
const output: CncPoint = [1.05, 1.49, 0.65];
function lerp(a: CncPoint, b: CncPoint, t: number): CncPoint {
  return a.map((v, i) => v + (b[i] - v) * t) as CncPoint;
}
export function cncPose(s: CncState) {
  const p = s.phase,
    t = Math.min(1, s.elapsed / cncPhases[p][1]);
  const active = s.mode !== "idle",
    done = s.mode === "complete";
  let hand = home;
  if (active) {
    if (p === 0) hand = lerp(home, input, t);
    else if (p === 1) hand = transfer(input, jig, t);
    else if (p === 2) hand = transfer(jig, home, t);
    else if (p === 9) hand = transfer(home, jig, t);
    else if (p === 10) hand = transfer(jig, output, t);
  }
  const location: "input" | "gripper" | "jig" | "output" =
    !active || p === 0
      ? "input"
      : done
        ? "output"
        : p === 1 || p === 10
          ? "gripper"
          : "jig";
  const block =
    location === "input"
      ? input
      : location === "output"
        ? output
        : location === "gripper"
          ? hand
          : jig;
  const door =
    !active || p < 4 || p > 7 ? 0 : p === 4 ? t : p === 7 ? 1 - t : 1;
  const clamped = active && p >= 4 && p <= 8;
  const clear = active && p >= 3 && p <= 8;
  const spindle =
    s.mode === "running" && p === 5 && door === 1 && clamped && clear;
  return {
    hand,
    block,
    location,
    door,
    clamped,
    clear,
    spindle,
    machined: active && p >= 6,
    progress: t,
  };
}
