export const ENERGY_MODEL = "whole-machine-stop-per-block-v1";
const error = (message) => {
  throw Error(message);
};
const valid = (v, positive = false, max = 1e9) =>
  typeof v === "number" &&
  Number.isFinite(v) &&
  v >= 0 &&
  (!positive || v > 0) &&
  v <= max;
const names = {
  rapid: "급속",
  removal: "제거 발생 이송",
  "no-removal": "제거 미검출 이송",
  dwell: "대기",
  spindle: "주축 전환",
  coolant: "쿨런트 전환",
  "tool-change": "공구 교환",
  end: "종료",
};
function stateKey(s) {
  return `${s.spindle === "off" ? `off (S${s.rpm})` : `${s.spindle}@${s.rpm}rpm`} / ${[...s.coolant].sort().join("+") || "coolant off"} / T${s.tool ?? "미정"}`;
}
function effective(s) {
  return s.spindle === "off" || s.rpm === 0 ? "off" : `${s.spindle}@${s.rpm}`;
}
export function energyPlan(nc, stock) {
  if (!nc?.complete || !nc.segments?.length) error("완전 해석된 NC 필요");
  if (
    !stock ||
    !nc.sourceHash ||
    stock.ncSourceHash !== nc.sourceHash ||
    stock.segments?.length !== nc.segments.length
  )
    error("현재 NC의 소재 검토 완료 필요");
  if (!nc.ended || !nc.events.some((e) => e.kind === "end"))
    error("M2/M30 종료 확인 필요 · 전체 사이클 경계 미정");
  if (stock.rapidContactLines.length)
    error("급속 소재 접촉 후보 있음 · 소비 분석 차단");
  const rows = [],
    states = new Map();
  const keyOf = (s) =>
    stateKey({ ...s, tool: s.tool ?? stock.setup?.initialTool });
  function add(kind, b, seg, event) {
    const signature =
      event && kind !== "dwell"
        ? `${keyOf(b.before)} → ${keyOf(b.after)}`
        : keyOf(seg?.state ?? b.after);
    const key = `${kind} | ${signature}`;
    if (!states.has(key))
      states.set(key, {
        key,
        kind,
        label: `${names[kind]} · ${signature}`,
        eventTime: !!event && kind !== "dwell",
      });
    rows.push({
      id: rows.length,
      line: b.line,
      kind,
      key,
      label: names[kind],
      segmentId: seg?.id ?? null,
      segment: seg ?? null,
      seconds: kind === "dwell" ? event.seconds : null,
      eventTime: !!event && kind !== "dwell",
    });
  }
  for (const b of nc.blocks) {
    if (!b.after) continue;
    const events = b.events.map((k) => nc.events[k]);
    const changed = effective(b.before) !== effective(b.after);
    const compound = events.find((e) =>
      ["tool-change", "end"].includes(e.kind),
    );
    if (
      changed &&
      (b.segment !== null || events.some((e) => e.kind === "dwell"))
    )
      error(`${b.line}행 이동/대기와 주축 변화 혼합 미지원`);
    if (compound) add(compound.kind, b, null, compound);
    else {
      if (changed) add("spindle", b, null, { kind: "spindle" });
      if (
        b.before.coolant.slice().sort().join() !==
        b.after.coolant.slice().sort().join()
      )
        add("coolant", b, null, { kind: "coolant" });
      for (const event of events)
        if (event.kind === "dwell") add("dwell", b, null, event);
    }
    if (b.segment !== null) {
      const seg = nc.segments[b.segment],
        removal = stock.segments[seg.id];
      if (
        removal?.id !== seg.id ||
        removal.line !== seg.line ||
        !valid(removal.removedMm3)
      )
        error("소재 구간 연결 불일치");
      add(
        seg.code === "G0"
          ? "rapid"
          : removal.removedMm3 > 1e-9
            ? "removal"
            : "no-removal",
        b,
        seg,
        null,
      );
    }
  }
  if (states.size > 200) error("전력 상태200종 상한 초과");
  return { rows, states: [...states.values()] };
}
export function stopTime(length, speed, acceleration) {
  if (!valid(length) || !valid(speed, true) || !valid(acceleration, true))
    error("시간 계산 입력 오류");
  if (!length) return 0;
  return length <= (speed * speed) / acceleration
    ? 2 * Math.sqrt(length / acceleration)
    : length / speed + speed / acceleration;
}
export function movementTime(segment, axes) {
  if (segment.length === 0) return { seconds: 0, velocity: 0, acceleration: 0 };
  let velocity = Infinity,
    acceleration = Infinity;
  const axesUsed = segment.arc
    ? [0, 1]
    : [0, 1, 2].filter((i) => Math.abs(segment.to[i] - segment.from[i]) > 1e-9);
  for (const i of axesUsed) {
    const axis = axes[i];
    if (axis?.velocity == null || axis?.acceleration == null)
      return { seconds: null, reason: `${"XYZ"[i]} 속도/가속도 미정` };
    if (
      !valid(axis.velocity, true, 1e6) ||
      !valid(axis.acceleration, true, 1e6)
    )
      error(`${"XYZ"[i]} 속도/가속도 양수 필요`);
    const ratio = segment.arc
      ? 1
      : Math.abs(segment.to[i] - segment.from[i]) / segment.length;
    velocity = Math.min(velocity, axis.velocity / 60 / ratio);
    acceleration = Math.min(acceleration, axis.acceleration / ratio);
  }
  if (segment.arc) {
    acceleration /= 2;
    velocity = Math.min(velocity, Math.sqrt(acceleration * segment.arc.radius));
  }
  if (segment.code !== "G0") {
    if (!valid(segment.state.feed, true))
      error(`${segment.line}행 F 이송 오류`);
    velocity = Math.min(velocity, segment.state.feed / 60);
  }
  return {
    seconds: stopTime(segment.length, velocity, acceleration),
    velocity,
    acceleration,
  };
}
export function analyzeEnergy(nc, stock, model) {
  if (
    model?.version !== ENERGY_MODEL ||
    !model.confirmed ||
    !model.wholeMachineConfirmed
  )
    error("전체 장비 전력·독립 구간/이벤트 가정 확인 필요");
  if (
    !model.machine?.trim() ||
    !model.source?.trim() ||
    !["assumption", "measured-input"].includes(model.provenance)
  )
    error("장비·입력 근거 필요");
  if (
    model.provenance === "measured-input" &&
    (!/^\d{4}-\d{2}-\d{2}$/.test(model.date ?? "") ||
      !Number.isFinite(Date.parse(model.date + "T00:00:00Z")) ||
      new Date(model.date + "T00:00:00Z").toISOString().slice(0, 10) !==
        model.date ||
      !model.conditions?.trim())
  )
    error("측정 날짜·적용 조건 필요");
  if (
    !Array.isArray(model.axes) ||
    model.axes.length !== 3 ||
    !model.states ||
    typeof model.states !== "object"
  )
    error("축 제한/상태표 입력 오류");
  const plan = energyPlan(nc, stock),
    rows = [],
    issues = [];
  for (const r of plan.rows) {
    const input = model.states[r.key] ?? {},
      motion = r.segment ? movementTime(r.segment, model.axes) : null;
    const seconds = r.segment
      ? motion.seconds
      : r.eventTime
        ? (input.seconds ?? null)
        : r.seconds;
    if (seconds !== null && !valid(seconds, false, 86400 * 365))
      error(`${r.line}행 이벤트 시간 범위 오류`);
    if (
      (input.min != null && !valid(input.min, false, 1e6)) ||
      (input.max != null && !valid(input.max, false, 1e6))
    )
      error(`${r.line}행 전력 범위 오류`);
    if (input.min != null && input.max != null && input.min > input.max)
      error(`${r.line}행 전력 최소/최대 역전`);
    const power =
      seconds === 0
        ? [0, 0]
        : input.min != null && input.max != null
          ? [input.min, input.max]
          : null;
    const energy =
      seconds !== null && power ? power.map((p) => (p * seconds) / 3600) : null;
    const reasons = [];
    if (seconds === null) reasons.push(motion?.reason ?? "이벤트 시간 미정");
    if (!power) reasons.push("전체 전력 범위 미정");
    if (reasons.length) issues.push({ line: r.line, key: r.key, reasons });
    rows.push({
      ...r,
      segment: undefined,
      seconds,
      power,
      energy,
      motion,
      removedMm3: r.segment ? stock.segments[r.segment.id].removedMm3 : 0,
      reasons,
    });
  }
  const knownTime = rows.reduce((a, r) => a + (r.seconds ?? 0), 0),
    knownEnergy = rows.reduce(
      (a, r) => a.map((v, i) => v + (r.energy?.[i] ?? 0)),
      [0, 0],
    );
  const totalTime = rows.every((r) => r.seconds !== null) ? knownTime : null,
    totalEnergy = rows.every((r) => r.energy !== null) ? knownEnergy : null;
  const validation = model.validation ?? null;
  if (
    validation &&
    (!valid(validation.seconds, true) ||
      !valid(validation.kWh, true) ||
      !validation.source?.trim())
  )
    error("별도 검증의 양수 시간·kWh·근거 필요");
  const comparison =
    validation && totalTime !== null && totalEnergy
      ? {
          source: validation.source,
          measuredSeconds: validation.seconds,
          measuredKWh: validation.kWh,
          timeDifferencePercent:
            ((totalTime - validation.seconds) / validation.seconds) * 100,
          energyDifferencePercent: totalEnergy.map(
            (e) => ((e - validation.kWh) / validation.kWh) * 100,
          ),
        }
      : null;
  return {
    version: ENERGY_MODEL,
    sourceHash: nc.sourceHash,
    model,
    rows,
    issues,
    knownTime,
    knownTimeRows: rows.filter((r) => r.seconds !== null).length,
    knownEnergy,
    knownEnergyRows: rows.filter((r) => r.energy !== null).length,
    totalTime,
    totalEnergy,
    averagePower:
      totalTime > 0 && totalEnergy
        ? totalEnergy.map((e) => (e * 3600) / totalTime)
        : null,
    comparison,
    stockConstraints: { remaining: stock.remaining, overcut: stock.overcut },
    limitations: [
      "입력 범위 시나리오; 통계적 신뢰구간 아님",
      "구간마다 정지 후 출발; look-ahead/블렌딩/jerk/실기계 궤적 미재현",
      "제거 미검출은 비접촉 보증 아님; 행 전체 평균 전력 가정",
      "실측 보정/장비 정확도·품질/기계 안전 미검증",
      "준비/부팅/NC 밖 대기 제외; 이벤트 시간에 자동 동작 포함",
    ],
  };
}
// Send only fields used by the time/power worker, retaining the original NC in the viewer.
export function compactEnergyNC(nc) {
  const state = (s) =>
    s
      ? {
          spindle: s.spindle,
          rpm: s.rpm,
          coolant: s.coolant,
          tool: s.tool,
          feed: s.feed,
        }
      : undefined;
  return {
    complete: nc.complete,
    ended: nc.ended,
    sourceHash: nc.sourceHash,
    events: nc.events,
    segments: nc.segments.map((s) => ({
      id: s.id,
      line: s.line,
      code: s.code,
      from: s.from,
      to: s.to,
      length: s.length,
      arc: s.arc,
      state: state(s.state),
    })),
    blocks: nc.blocks.map((b) => ({
      line: b.line,
      segment: b.segment,
      events: b.events,
      before: state(b.before),
      after: state(b.after),
    })),
  };
}
