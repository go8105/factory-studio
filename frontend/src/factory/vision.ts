export type VisionSnapshot = {
  phase: string;
  result: string;
  inspected: number;
  rejected: number;
  x: number;
  scanning: boolean;
  fault: boolean;
};
// One deterministic six-second cycle; every fifth part is rejected (synthetic demo).
export function visionAt(seconds: number, fault = false): VisionSnapshot {
  const cycle = Math.floor(seconds / 6);
  const t = seconds % 6;
  const judged = t >= 3.5;
  const inspected = cycle + Number(judged);
  return {
    phase: fault
      ? "이상 정지"
      : t < 2
        ? "제품 투입"
        : t < 3.5
          ? "검사 중"
          : t < 4.2
            ? "판정 완료"
            : "제품 배출",
    result: judged ? ((cycle + 1) % 5 === 0 ? "불합격" : "합격") : "판정 대기",
    inspected,
    rejected: Math.floor(inspected / 5),
    x: t < 2 ? -1.25 + t * 0.625 : t < 4.2 ? 0 : ((t - 4.2) / 1.8) * 1.25,
    scanning: !fault && t >= 2 && t < 3.5,
    fault,
  };
}
