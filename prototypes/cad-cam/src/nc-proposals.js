import { energyPlan, ENERGY_MODEL } from "./nc-energy.js";
export const PROPOSAL_MODEL = "quality-first-dwell-review-v1";
const finite = (v) => typeof v === "number" && Number.isFinite(v) && v >= 0;
const text = (v) => typeof v === "string" && !!v.trim();
export function dwellReview(nc, stock, energy) {
  energyPlan(nc, stock);
  if (energy?.version !== ENERGY_MODEL || energy.sourceHash !== nc.sourceHash)
    throw Error("현재 NC의 시간·소비 분석 필요");
  if (
    !finite(energy.totalTime) ||
    energy.totalEnergy?.length !== 2 ||
    !energy.totalEnergy.every(finite)
  )
    throw Error("전체 시간·소비가 미정이면 제안 비교 불가");
  const rows = energy.rows.filter((r) => r.kind === "dwell");
  return rows.map((r) => {
    const block = nc.blocks[r.line - 1];
    const eligible =
      block?.segment === null &&
      block.events.length === 1 &&
      JSON.stringify(block.before) === JSON.stringify(block.after);
    return {
      id: r.id,
      line: r.line,
      seconds: r.seconds,
      power: r.power,
      eligible,
      reason: eligible
        ? "공정 목적·최소 유지 시간 확인 필요"
        : "모달/이벤트 변화 혼합 대기 미지원",
    };
  });
}
export function compareProposals(nc, stock, energy, settings) {
  const dwells = dwellReview(nc, stock, energy);
  const reasons = [];
  const q = settings?.quality ?? {};
  for (const key of ["maxRemaining", "maxOvercut", "maxGridErrorPercent"]) {
    if (q[key] == null) reasons.push("품질 형상 기준 미정");
    else if (!finite(q[key])) throw Error("품질 형상 기준은0 이상 유한수 필요");
  }
  if (!text(q.source)) reasons.push("품질 기준·근거 필요");
  if (settings?.riskReviewed !== true)
    reasons.push("실기계·공정 위험 별도 검토 확인 필요");
  for (const [key, limit] of [
    ["maxRemaining", q.maxRemaining],
    ["maxOvercut", q.maxOvercut],
    [
      "targetVolumeError",
      q.maxGridErrorPercent == null ? null : q.maxGridErrorPercent / 100,
    ],
  ]) {
    if (!finite(stock[key])) reasons.push("현재 소재 형상 검토 값 미정");
    else if (limit != null && stock[key] > limit)
      reasons.push(
        `${{ maxRemaining: "잔삭 높이", maxOvercut: "과절삭 깊이", targetVolumeError: "목표 격자 체적 오차" }[key]} 형상 기준 초과`,
      );
  }
  const margin = settings?.marginKWh;
  if (margin != null && !finite(margin))
    throw Error("추가 비교 여유는0 이상 유한수 필요");
  if (margin != null && !text(settings.marginSource))
    reasons.push("추가 비교 여유 근거 필요");
  const selected = settings?.dwells ?? [];
  if (!Array.isArray(selected) || selected.length > 12)
    throw Error("선택 대기12개 상한");
  if (new Set(selected.map((r) => r.id)).size !== selected.length)
    throw Error("같은 대기 중복 선택 불가");
  if (!selected.length)
    reasons.push(
      dwells.length
        ? "검토할 대기를 선택하세요"
        : "지원 대기 없음 · 경로/보조 소비 자동 변경 없음",
    );
  const review = selected.map((input) => {
    const row = dwells.find((r) => r.id === input.id);
    if (!row) throw Error("현재 NC에 없는 대기 선택");
    if (
      input.seconds != null &&
      (!finite(input.seconds) || input.seconds > row.seconds)
    )
      throw Error(`${row.line}행 최소 유지 시간 범위 오류`);
    return {
      ...row,
      proposedSeconds: input.seconds,
      source: input.source,
      blocked: [
        !row.eligible && row.reason,
        input.seconds == null && "최소 유지 시간 미정",
        !text(input.source) && "대기 목적·최소 시간 근거 필요",
        input.confirmed !== true && "열/칩/냉각/정삭 영향 검토 미확인",
      ].filter(Boolean),
    };
  });
  const base = { seconds: energy.totalTime, energy: [...energy.totalEnergy] };
  const report = {
    version: PROPOSAL_MODEL,
    sourceHash: nc.sourceHash,
    settings,
    baseline: base,
    quality: {
      maxRemaining: stock.maxRemaining,
      maxOvercut: stock.maxOvercut,
      gridErrorPercent: stock.targetVolumeError * 100,
    },
    reasons: [...new Set(reasons)],
    review,
    candidates: [],
    limitations: [
      "사용자 형상/공정 조건 검토; 실제 품질·안전 미검증",
      "가공 경로/F/S/T·모든 비대기 이벤트 유지; NC 변경/출력 없음",
      "대기 평균 전력 일정 가정; 입력 범위/추가 여유는 통계적 신뢰구간 아님",
      "범위 겹침은 우열 판단 불가; 단일 최적 후보 보장 없음",
    ],
  };
  if (reasons.length) return report;
  const groups = review.map((r) => [r]);
  if (review.length > 1) groups.push(review);
  for (const group of groups) {
    const blocked = group.flatMap((r) =>
      r.blocked.map((s) => `${r.line}행 ${s}`),
    );
    if (blocked.length) {
      report.candidates.push({
        lines: group.map((r) => r.line),
        status: "blocked",
        reasons: blocked,
      });
      continue;
    }
    const times = new Map(group.map((r) => [r.id, r.proposedSeconds]));
    let seconds = 0;
    const energyRange = [0, 0];
    for (const row of energy.rows) {
      const t = times.has(row.id) ? times.get(row.id) : row.seconds;
      seconds += t;
      for (let i = 0; i < 2; i++)
        energyRange[i] += times.has(row.id)
          ? (row.power[i] * t) / 3600
          : row.energy[i];
    }
    const savedEnergy = [0, 0];
    for (const row of group)
      for (let i = 0; i < 2; i++)
        savedEnergy[i] +=
          (row.power[i] * (row.seconds - row.proposedSeconds)) / 3600;
    const gap = base.energy[0] - energyRange[1];
    const lower = margin != null && gap > margin + 1e-12;
    report.candidates.push({
      lines: group.map((r) => r.line),
      status: lower ? "conditional-lower" : "indeterminate",
      seconds,
      energy: energyRange,
      savedSeconds: base.seconds - seconds,
      savedEnergy,
      gapKWh: gap,
      reasons: [
        "사용자 형상/대기 조건 충족 · 실제 품질·안전 미검증",
        lower
          ? "입력 범위와 추가 여유를 넘는 소비 감소 후보"
          : margin == null
            ? "추가 비교 여유 미정 · 우열 판단 불가"
            : "예상 범위 겹침/차이가 추가 여유 이하 · 우열 판단 불가",
      ],
    });
  }
  return report;
}
