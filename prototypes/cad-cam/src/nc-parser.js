// Deliberately bounded LinuxCNC literal subset. Never continue across an unknown block.
export const NC_PROFILE = "linuxcnc-mill-subset-v1";
export const NC_LIMITS = Object.freeze({
  bytes: 2 * 1024 * 1024,
  lines: 50000,
  points: 500000,
  milliseconds: 30000,
});
const TAU = Math.PI * 2;
const copy = (v) => structuredClone(v);
const fail = (message) => {
  throw new Error(message);
};
const bounded = (v) => Number.isFinite(v) && Math.abs(v) <= 1000000;
function sweepOf(start, end, clockwise, full = false) {
  if (full) return clockwise ? -TAU : TAU;
  let angle = end - start;
  if (clockwise) {
    while (angle >= 0) angle -= TAU;
  } else {
    while (angle <= 0) angle += TAU;
  }
  return angle;
}
function tokenize(raw) {
  let line = "",
    comment = false;
  for (const c of raw.replace(/^\uFEFF/, "")) {
    if (!comment && c === ";") break;
    if (c === "(") {
      if (comment) fail("중첩 주석 미지원");
      comment = true;
    } else if (c === ")") {
      if (!comment) fail("주석 닫기 불일치");
      comment = false;
    } else if (!comment) line += c;
  }
  if (comment) fail("닫히지 않은 주석");
  line = line.trim().toUpperCase();
  if (!line) return [];
  if (line === "%") return null;
  const words = [];
  while (line) {
    const m = /^([A-Z])\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*/.exec(line);
    if (!m) fail("숫자 리터럴 외 문법/선택 블록/매크로 미지원");
    const value = Number(m[2]);
    if (!Number.isFinite(value) || Math.abs(value) > 1e9)
      fail("숫자 범위 초과");
    words.push([m[1], value]);
    line = line.slice(m[0].length);
  }
  return words;
}
const gGroups = new Map([
  [0, "motion"],
  [1, "motion"],
  [2, "motion"],
  [3, "motion"],
  [80, "motion"],
  [17, "plane"],
  [20, "unit"],
  [21, "unit"],
  [90, "distance"],
  [91, "distance"],
  [91.1, "center"],
  [94, "feedMode"],
  [54, "wcs"],
  [40, "cutter"],
  [49, "length"],
  [4, "dwell"],
]);
const mGroups = new Map([
  [3, "spindle"],
  [4, "spindle"],
  [5, "spindle"],
  [6, "tool"],
  [7, "coolant"],
  [8, "coolant"],
  [9, "coolant"],
  [2, "end"],
  [30, "end"],
]);
function arcGeometry(from, to, w, scale, clockwise) {
  if (Math.abs(to[2] - from[2]) > 1e-9) fail("헬릭스 원호 미지원");
  const hasR = w.R !== undefined,
    hasCenter = w.I !== undefined || w.J !== undefined;
  if (hasR === hasCenter) fail("원호는 I/J 또는 R 중 한 형식만 필요합니다");
  const chord = Math.hypot(to[0] - from[0], to[1] - from[1]);
  let center, radius, sweep, startAngle;
  if (hasR) {
    const r = w.R * scale;
    radius = Math.abs(r);
    if (!radius || chord < 1e-9 || chord > 2 * radius + 1e-8)
      fail("R 원호 반경/끝점 불일치 (전체 원은 I/J 필요)");
    const h = Math.sqrt(Math.max(0, radius * radius - (chord * chord) / 4));
    const middle = [(from[0] + to[0]) / 2, (from[1] + to[1]) / 2];
    for (const sign of [1, -1]) {
      const c = [
        middle[0] - (sign * h * (to[1] - from[1])) / chord,
        middle[1] + (sign * h * (to[0] - from[0])) / chord,
      ];
      const a = Math.atan2(from[1] - c[1], from[0] - c[0]);
      const s = sweepOf(a, Math.atan2(to[1] - c[1], to[0] - c[0]), clockwise);
      if (
        (r > 0 && Math.abs(s) <= Math.PI + 1e-8) ||
        (r < 0 && Math.abs(s) >= Math.PI - 1e-8)
      ) {
        center = c;
        startAngle = a;
        sweep = s;
        break;
      }
    }
    if (!center) fail("R 원호 방향 해석 실패");
  } else {
    center = [from[0] + (w.I ?? 0) * scale, from[1] + (w.J ?? 0) * scale];
    radius = Math.hypot(from[0] - center[0], from[1] - center[1]);
    const endRadius = Math.hypot(to[0] - center[0], to[1] - center[1]);
    if (radius < 1e-9 || Math.abs(radius - endRadius) > 0.005)
      fail("원호 중심/끝점 반경 불일치 (허용 0.005mm)");
    startAngle = Math.atan2(from[1] - center[1], from[0] - center[0]);
    sweep = sweepOf(
      startAngle,
      Math.atan2(to[1] - center[1], to[0] - center[0]),
      clockwise,
      chord < 1e-9,
    );
  }
  if (![...center, radius].every(bounded)) fail("원호 좌표/반경 범위 초과");
  return { center: [...center, from[2]], radius, sweep, startAngle, clockwise };
}
export function displayArc(from, to, arc, budget = NC_LIMITS.points) {
  const step = Math.min(
    Math.PI / 36,
    2 * Math.acos(Math.max(-1, 1 - 0.05 / arc.radius)),
  );
  const count = Math.ceil(Math.abs(arc.sweep) / step);
  if (!Number.isFinite(count) || count + 1 > budget) fail("표시점 상한 초과");
  const points = [copy(from)];
  for (let i = 1; i < count; i++) {
    const a = arc.startAngle + (arc.sweep * i) / count;
    const p = [
      arc.center[0] + arc.radius * Math.cos(a),
      arc.center[1] + arc.radius * Math.sin(a),
      from[2],
    ];
    if (!p.every(bounded)) fail("원호 표시 좌표 범위 초과");
    points.push(p);
  }
  points.push(copy(to));
  return points;
}
export function parseNC(text, settings, progress = () => {}) {
  if (
    typeof text !== "string" ||
    new TextEncoder().encode(text).length > NC_LIMITS.bytes
  )
    fail("파일 상한 2MiB 초과 또는 텍스트 형식 아님");
  const lines = text.split(/\r\n|\n|\r/);
  if (lines.length > NC_LIMITS.lines) fail("원본 행 상한 50,000 초과");
  if (
    (settings?.profile && settings.profile !== NC_PROFILE) ||
    !settings?.confirmed ||
    !["mm", "inch"].includes(settings.unit) ||
    !Array.isArray(settings.initial) ||
    settings.initial.length !== 3 ||
    !settings.initial.every((v) => typeof v === "number" && bounded(v))
  )
    fail("초기 XYZ·단위를 확인해야 합니다");
  const scale = settings.unit === "inch" ? 25.4 : 1;
  let state = {
    position: settings.initial.map((v) => v * scale),
    unit: settings.unit,
    distance: "absolute",
    plane: "XY",
    center: "incremental",
    feedMode: "per-minute",
    wcs: "G54",
    motion: 0,
    feed: null,
    rpm: 0,
    selectedTool: null,
    tool: null,
    spindle: "off",
    coolant: [],
    cutterComp: "off",
    lengthComp: "off",
  };
  if (!state.position.every(bounded)) fail("초기 위치 범위 초과");
  const segments = [],
    events = [],
    blocks = [],
    diagnostics = [];
  let pointsCount = 0,
    ended = false,
    blocked = false,
    delimiterOpen = false,
    sawExecutable = false;
  for (let i = 0; i < lines.length; i++) {
    if (i % 1000 === 0) progress({ line: i + 1, total: lines.length });
    const block = {
      line: i + 1,
      raw: lines[i],
      status: blocked ? "blocked" : ended ? "after-end" : "ok",
      segment: null,
      events: [],
    };
    blocks.push(block);
    if (blocked || ended) continue;
    const before = copy(state);
    try {
      const words = tokenize(lines[i]);
      if (words === null) {
        if (!delimiterOpen && sawExecutable)
          fail("시작 구분자 없는 % 종료 미지원");
        if (delimiterOpen) {
          ended = true;
          block.status = "after-end";
        } else {
          delimiterOpen = true;
          block.status = "delimiter";
        }
        block.before = before;
        block.after = copy(state);
        continue;
      }
      if (!words.length) {
        block.status = "empty";
        continue;
      }
      sawExecutable = true;
      const w = {},
        gs = [],
        ms = [],
        groups = new Set();
      for (const [address, value] of words) {
        if (!"NGMXYZIJRFSTPO".includes(address)) fail(`${address} 주소 미지원`);
        if (address === "G" || address === "M") {
          const group = (address === "G" ? gGroups : mGroups).get(value);
          if (!group) fail(`${address}${value} 명령 미지원`);
          if (groups.has(address + group))
            fail(`${address} 모달 그룹 중복: ${group}`);
          groups.add(address + group);
          (address === "G" ? gs : ms).push(value);
        } else {
          if (w[address] !== undefined) fail(`${address} 중복 주소`);
          w[address] = value;
        }
      }
      if (
        w.N !== undefined &&
        (!Number.isInteger(w.N) || w.N < 0 || w.N > 99999)
      )
        fail("N 행 번호 범위 오류");
      if (
        w.O !== undefined &&
        (words.length !== (w.N === undefined ? 1 : 2) ||
          !Number.isInteger(w.O) ||
          w.O < 1 ||
          w.O > 99999)
      )
        fail("O 프로그램 번호는 단독 정수여야 합니다");
      block.number = w.N ?? null;
      if (ms.length > 1) fail("M 이벤트는 한 행에 하나만 지원합니다");
      if (
        ms.some((m) => m === 2 || m === 30) &&
        words.some(([address]) => !["N", "M"].includes(address))
      )
        fail("프로그램 종료는 단독 행으로 작성해야 합니다");
      const next = copy(state),
        localEvents = [];
      for (const g of gs) {
        if ([0, 1, 2, 3, 80].includes(g)) next.motion = g === 80 ? null : g;
        if (g === 20 || g === 21) next.unit = g === 20 ? "inch" : "mm";
        if (g === 90 || g === 91)
          next.distance = g === 90 ? "absolute" : "incremental";
      }
      const unitScale = next.unit === "inch" ? 25.4 : 1;
      if (w.F !== undefined) {
        if (w.F <= 0) fail("F 이송은 양수여야 합니다");
        next.feed = w.F * unitScale;
      }
      if (w.S !== undefined) {
        if (w.S < 0) fail("S 주축 회전수는 음수 불가");
        next.rpm = w.S;
      }
      if (w.T !== undefined) {
        if (!Number.isInteger(w.T) || w.T < 0 || w.T > 99999)
          fail("T 공구 번호 범위 오류");
        next.selectedTool = w.T;
      }
      const hasAxes = ["X", "Y", "Z"].some((k) => w[k] !== undefined),
        hasArc = ["I", "J", "R"].some((k) => w[k] !== undefined),
        dwell = gs.includes(4);
      if (dwell && (hasAxes || hasArc || groups.has("Gmotion")))
        fail("G4와 이동 명령 혼합 미지원");
      if (w.P !== undefined && !dwell) fail("P는 G4 초 단위 대기에만 지원");
      if (dwell) {
        if (w.P === undefined || w.P < 0) fail("G4는 0 이상 P초 필요");
        localEvents.push({ kind: "dwell", seconds: w.P });
      }
      // Conservative standalone tool/spindle/coolant events avoid controller-specific order.
      if (ms.length && (hasAxes || hasArc || dwell))
        fail("M 이벤트와 이동을 별도 행으로 작성해야 합니다");
      for (const m of ms) {
        if ([3, 4, 5].includes(m)) {
          next.spindle = m === 5 ? "off" : m === 3 ? "cw" : "ccw";
          localEvents.push({
            kind: "spindle",
            direction: next.spindle,
            rpm: next.rpm,
          });
        }
        if (m === 6) {
          if (next.selectedTool === null) fail("M6 이전에 T 공구 선택 필요");
          next.tool = next.selectedTool;
          localEvents.push({
            kind: "tool-change",
            tool: next.tool,
            seconds: null,
          });
        }
        if (m === 7 || m === 8) {
          const type = m === 7 ? "mist" : "flood";
          next.coolant = [...new Set([...next.coolant, type])];
          localEvents.push({ kind: "coolant", value: copy(next.coolant) });
        }
        if (m === 9) {
          next.coolant = [];
          localEvents.push({ kind: "coolant", value: [] });
        }
        if (m === 2 || m === 30) {
          next.spindle = "off";
          next.coolant = [];
          next.distance = "absolute";
          next.motion = 1;
          localEvents.push({ kind: "end", code: `M${m}` });
        }
      }
      if (w.S !== undefined && !ms.some((m) => [3, 4, 5].includes(m)))
        localEvents.push({ kind: "speed", rpm: next.rpm });
      if (w.T !== undefined && !ms.includes(6))
        localEvents.push({ kind: "tool-select", tool: next.selectedTool });
      let segment = null;
      if (hasAxes || hasArc) {
        if (next.motion === null) fail("G80 이후 이동 모드 필요");
        if (hasArc && ![2, 3].includes(next.motion))
          fail("I/J/R은 원호에서만 지원");
        if (next.motion !== 0 && !(next.feed > 0))
          fail("이송 이동 이전 F 필요");
        const from = copy(state.position),
          to = from.map((v, j) => {
            const input = w[["X", "Y", "Z"][j]];
            return input === undefined
              ? v
              : next.distance === "absolute"
                ? input * unitScale
                : v + input * unitScale;
          });
        if (!to.every(bounded)) fail("XYZ 좌표 범위 초과");
        const arc = [2, 3].includes(next.motion)
          ? arcGeometry(from, to, w, unitScale, next.motion === 2)
          : null;
        const display = arc
          ? displayArc(from, to, arc, NC_LIMITS.points - pointsCount)
          : [from, to];
        if (pointsCount + display.length > NC_LIMITS.points)
          fail("표시점 상한 500,000 초과");
        segment = {
          id: segments.length,
          line: i + 1,
          code: `G${next.motion}`,
          from,
          to,
          arc,
          points: display,
          length: arc
            ? arc.radius * Math.abs(arc.sweep)
            : Math.hypot(...to.map((v, j) => v - from[j])),
          state: copy(next),
        };
        next.position = to;
        segment.state.position = copy(to);
      }
      block.before = before;
      block.after = copy(next);
      if (segment) {
        block.segment = segment.id;
        segments.push(segment);
        pointsCount += segment.points.length;
      }
      for (const event of localEvents) {
        event.line = i + 1;
        block.events.push(events.length);
        events.push(event);
      }
      state = next;
      if (ms.includes(2) || ms.includes(30)) ended = true;
    } catch (error) {
      block.status = "error";
      block.before = before;
      block.message = error.message;
      diagnostics.push({ line: i + 1, message: error.message });
      blocked = true;
    }
  }
  if (delimiterOpen && !ended && !blocked) {
    diagnostics.push({
      line: lines.length,
      message: "시작 %에 대응하는 종료 % 또는 M2/M30 필요",
    });
    blocked = true;
  }
  return {
    schemaVersion: 1,
    profile: NC_PROFILE,
    settings: copy(settings),
    complete: !blocked,
    ended,
    segments,
    events,
    blocks,
    diagnostics,
    pointsCount,
    finalState: state,
    totalTimeSeconds: null,
    energyKWh: null,
    limitations: [
      "G54 작업좌표 경로 전용 · 기계좌표 변환 없음",
      "급속은 끝점을 연결한 표시이며 실제 기계 궤적/충돌 검증이 아님",
      "G1/G2/G3은 이송 명령이며 소재 접촉/절삭 여부 미확정",
      "M6 자동 이동·교환 시간 미정 · 전체 시간/전력은 후속 모델 필요",
    ],
  };
}
