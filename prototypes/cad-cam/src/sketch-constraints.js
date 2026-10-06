import { syncProfile } from "./profile.js";
// Minimum-displacement Newton projection for the supported point/three-point-arc constraints.
// This is deliberately bounded; failure never mutates the input sketch.
export function solveSketch(input) {
  const s = structuredClone(input),
    constraints = s.constraints ?? [];
  if (!Array.isArray(constraints) || constraints.length > 64)
    throw Error("구속은 최대64개입니다.");
  if (s.type !== "profile" || !constraints.length)
    return { sketch: s, changed: false, residual: 0 };
  const slots = [],
    index = new Map();
  for (const n of s.nodes) {
    index.set(n.id, slots.length);
    slots.push(n.point);
    if (n.arcVia) slots.push(n.arcVia);
  }
  let x = slots.flat(),
    initial = x.slice();
  const seen = new Set();
  for (const c of constraints) {
    if (
      ![
        "horizontal",
        "vertical",
        "coincident",
        "length",
        "radius",
        "fix",
      ].includes(c.type) ||
      !index.has(c.a) ||
      (["horizontal", "vertical", "coincident", "length"].includes(c.type) &&
        (!index.has(c.b) || c.a === c.b))
    )
      throw Error("구속의 종류 또는 점 번호가 잘못되었습니다.");
    if (
      ["length", "radius"].includes(c.type) &&
      (!Number.isFinite(c.value) || c.value < 0.1 || c.value > 1000)
    )
      throw Error("길이/반경 구속은0.1~1000mm입니다.");
    if (
      c.type === "fix" &&
      (!Array.isArray(c.target) ||
        c.target.length !== 2 ||
        c.target.some((v) => !Number.isFinite(v) || Math.abs(v) > 200))
    )
      throw Error("고정점 좌표를 확인하세요.");
    if (c.type === "radius" && !s.nodes.find((n) => n.id === c.a)?.arcVia)
      throw Error("반경 구속에는 원호 시작점이 필요합니다.");
    const key = c.type + ":" + [c.a, c.b ?? ""].sort().join(":");
    if (seen.has(key)) throw Error("과구속: 같은 구속을 중복 지정했습니다.");
    seen.add(key);
  }
  const residual = (v) =>
    constraints.flatMap((c) => {
      const ai = index.get(c.a) * 2,
        a = v.slice(ai, ai + 2),
        bi = index.get(c.b) * 2,
        b = v.slice(bi, bi + 2);
      if (c.type === "horizontal") return [b[1] - a[1]];
      if (c.type === "vertical") return [b[0] - a[0]];
      if (c.type === "coincident") return [b[0] - a[0], b[1] - a[1]];
      if (c.type === "length")
        return [Math.hypot(b[0] - a[0], b[1] - a[1]) - c.value];
      if (c.type === "fix") return [a[0] - c.target[0], a[1] - c.target[1]];
      const n = s.nodes.findIndex((n) => n.id === c.a),
        endIndex = index.get(s.nodes[(n + 1) % s.nodes.length].id) * 2,
        via = v.slice(ai + 2, ai + 4),
        end = v.slice(endIndex, endIndex + 2);
      const cross = Math.abs(
        (via[0] - a[0]) * (end[1] - a[1]) - (via[1] - a[1]) * (end[0] - a[0]),
      );
      return [
        cross < 1e-10
          ? 10000
          : (Math.hypot(a[0] - via[0], a[1] - via[1]) *
              Math.hypot(via[0] - end[0], via[1] - end[1]) *
              Math.hypot(end[0] - a[0], end[1] - a[1])) /
              (2 * cross) -
            c.value,
      ];
    });
  const norm = (r) => Math.max(...r.map(Math.abs), 0);
  for (let iteration = 0; iteration < 60; iteration++) {
    const r = residual(x);
    if (norm(r) < 1e-6) break;
    const J = r.map(() => Array(x.length).fill(0)),
      eps = 1e-4;
    for (let k = 0; k < x.length; k++) {
      const v = x.slice();
      v[k] += eps;
      const next = residual(v);
      for (let i = 0; i < r.length; i++) J[i][k] = (next[i] - r[i]) / eps;
    }
    const A = J.map((row, i) => [
      ...J.map(
        (other, j) =>
          row.reduce((sum, v, k) => sum + v * other[k], 0) +
          (i === j ? 1e-7 : 0),
      ),
      -r[i],
    ]);
    for (let col = 0; col < r.length; col++) {
      let pivot = col;
      for (let row = col + 1; row < r.length; row++)
        if (Math.abs(A[row][col]) > Math.abs(A[pivot][col])) pivot = row;
      [A[col], A[pivot]] = [A[pivot], A[col]];
      const d = A[col][col];
      if (Math.abs(d) < 1e-12) continue;
      for (let k = col; k <= r.length; k++) A[col][k] /= d;
      for (let row = 0; row < r.length; row++)
        if (row !== col) {
          const factor = A[row][col];
          for (let k = col; k <= r.length; k++) A[row][k] -= factor * A[col][k];
        }
    }
    const delta = x.map((_, k) =>
      J.reduce((sum, row, i) => sum + row[k] * A[i][r.length], 0),
    );
    let improved = false;
    for (const scale of [1, 0.5, 0.25, 0.1, 0.01]) {
      const next = x.map((v, k) => v + delta[k] * scale);
      if (next.every(Number.isFinite) && norm(residual(next)) < norm(r)) {
        x = next;
        improved = true;
        break;
      }
    }
    if (!improved) break;
  }
  const error = norm(residual(x));
  if (error > 1e-4)
    throw Error(
      `과구속 또는 해 없음: 구속 오차 ${error.toFixed(3)}mm. 고정점·길이·방향을 확인하세요.`,
    );
  let k = 0;
  for (const n of s.nodes) {
    n.point = x.slice(k, k + 2);
    k += 2;
    if (n.arcVia) {
      n.arcVia = x.slice(k, k + 2);
      k += 2;
    }
  }
  syncProfile(s);
  return {
    sketch: s,
    changed: x.some((v, i) => Math.abs(v - initial[i]) > 1e-4),
    residual: error,
  };
}
