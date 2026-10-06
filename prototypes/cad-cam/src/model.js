import clipping from "polygon-clipping";
import { profileRing, polygonDistance, validateProfile } from "./profile.js";

export const emptyModel = () => ({
  version: 2,
  name: "새 부품",
  stock: null,
  features: [],
});
export const defaultTool = () => ({
  diameter: 4,
  stepDown: 2,
  stepOver: 45,
  feed: 600,
  safeHeight: 5,
});
export const clone = (value) => structuredClone(value);
export const round = (value) => Math.round(value * 100) / 100;
export const sampleModel = () => ({
  version: 2,
  name: "포켓 연습 부품",
  stock: {
    id: "stock",
    type: "rect",
    x: 0,
    y: 0,
    w: 90,
    h: 70,
    radius: 8,
    height: 16,
  },
  features: [
    {
      id: "pocket-1",
      type: "rect",
      x: 0,
      y: 0,
      w: 70,
      h: 50,
      radius: 6,
      depth: 10,
      name: "수집 공간",
    },
    {
      id: "pocket-2",
      type: "circle",
      x: 0,
      y: 0,
      w: 12,
      h: 12,
      radius: 0,
      depth: 14,
      name: "중앙 홈",
    },
  ],
});

// Signed distance to convex profiles. Negative means inside; units are millimetres.
export function distance(shape, x, y) {
  if (shape.type === "profile" || shape.type === "slot")
    return polygonDistance(ring(shape), x, y);
  const dx = Math.abs(x - shape.x),
    dy = Math.abs(y - shape.y);
  if (shape.type === "circle") return Math.hypot(dx, dy) - shape.w / 2;
  const r = shape.radius;
  const qx = dx - shape.w / 2 + r,
    qy = dy - shape.h / 2 + r;
  return (
    Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) +
    Math.min(Math.max(qx, qy), 0) -
    r
  );
}
export function ring(shape, inset = 0, segments = 24) {
  if (shape.type === "profile" || shape.type === "slot") {
    if (inset) throw Error("자유 윤곽의 가공은 윤곽 커널을 사용하세요.");
    return profileRing(shape);
  }
  const w = shape.w - inset * 2,
    h = shape.h - inset * 2;
  if (w <= 0 || h <= 0) return [];
  const out = [];
  if (shape.type === "circle") {
    for (let i = 0; i < segments * 4; i++) {
      const t = (i * Math.PI) / (segments * 2);
      out.push([
        shape.x + (w / 2) * Math.cos(t),
        shape.y + (w / 2) * Math.sin(t),
      ]);
    }
  } else {
    const r = Math.max(0, shape.radius - inset);
    if (!r)
      return [
        [shape.x - w / 2, shape.y - h / 2],
        [shape.x + w / 2, shape.y - h / 2],
        [shape.x + w / 2, shape.y + h / 2],
        [shape.x - w / 2, shape.y + h / 2],
      ];
    for (const [cx, cy, angle] of [
      [w / 2 - r, h / 2 - r, 0],
      [-w / 2 + r, h / 2 - r, 90],
      [-w / 2 + r, -h / 2 + r, 180],
      [w / 2 - r, -h / 2 + r, 270],
    ]) {
      for (let i = 0; i <= segments; i++) {
        const t = ((angle + (i * 90) / segments) * Math.PI) / 180;
        out.push([
          shape.x + cx + r * Math.cos(t),
          shape.y + cy + r * Math.sin(t),
        ]);
      }
    }
  }
  return out;
}
export function bounds(shape) {
  if (["profile", "slot"].includes(shape.type)) {
    const pts = ring(shape);
    return {
      minX: Math.min(...pts.map((p) => p[0])),
      maxX: Math.max(...pts.map((p) => p[0])),
      minY: Math.min(...pts.map((p) => p[1])),
      maxY: Math.max(...pts.map((p) => p[1])),
    };
  }
  return {
    minX: shape.x - shape.w / 2,
    maxX: shape.x + shape.w / 2,
    minY: shape.y - shape.h / 2,
    maxY: shape.y + shape.h / 2,
  };
}
function number(v, min, max, label) {
  if (!Number.isFinite(v) || v < min || v > max)
    throw Error(`${label}: ${min}~${max} 범위의 숫자를 입력하세요.`);
}
export function validateShape(s) {
  if (!s || !["rect", "circle", "profile", "slot"].includes(s.type))
    throw Error("지원하지 않는 스케치입니다.");
  if (s.type === "profile") validateProfile(s);
  if (s.type === "slot") {
    number(s.angle, -180, 180, "회전 각도");
    if (s.w < s.h) throw Error("슬롯 길이는 폭 이상이어야 합니다.");
  }
  number(s.x, -200, 200, "중심 X");
  number(s.y, -200, 200, "중심 Y");
  number(s.w, 1, 200, "폭 / 지름");
  number(s.h, 1, 200, "길이");
  number(s.radius, 0, Math.min(s.w, s.h) / 2, "모서리 반경");
  if (s.type === "circle" && s.w !== s.h)
    throw Error("원의 폭과 길이는 같아야 합니다.");
}
export function validateModel(m) {
  if (
    !m ||
    ![1, 2].includes(m.version) ||
    typeof m.name !== "string" ||
    m.name.length > 80 ||
    !Array.isArray(m.features) ||
    m.features.length > 32
  )
    throw Error("지원하지 않는 설계 파일입니다. (최대 32개 홈)");
  if (!m.stock) {
    if (m.features.length) throw Error("기본 돌출이 필요합니다.");
    return m;
  }
  validateShape(m.stock);
  number(m.stock.height, 1, 80, "돌출 높이");
  const ids = new Set(["stock"]);
  for (const f of m.features) {
    validateShape(f);
    number(f.depth, 0.1, m.stock.height, "파내기 깊이");
    if (
      typeof f.id !== "string" ||
      !/^[a-zA-Z0-9_-]{1,64}$/.test(f.id) ||
      ids.has(f.id)
    )
      throw Error("중복되거나 잘못된 작업 ID입니다.");
    ids.add(f.id);
    if (typeof f.name !== "string" || f.name.length > 80)
      throw Error("작업 이름은 80자 이내로 입력하세요.");
    const edge = ring(f);
    const crosses = edge.some((a, i) => {
      const b = edge[(i + 1) % edge.length],
        n = Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.05);
      for (let j = 0; j <= n; j++)
        if (
          distance(
            m.stock,
            a[0] + ((b[0] - a[0]) * j) / Math.max(1, n),
            a[1] + ((b[1] - a[1]) * j) / Math.max(1, n),
          ) > -0.099
        )
          return true;
      return false;
    });
    if (crosses || clipping.difference([edge], [ring(m.stock)]).length)
      throw Error(
        "홈을 외곽 안에 배치하세요. 바깥쪽 벽을 최소 0.1mm 남겨야 합니다.",
      );
  }
  return m;
}
export function parseModel(text) {
  if (text.length > 100000) throw Error("설계 파일은 100KB 이하여야 합니다.");
  const m = validateModel(JSON.parse(text));
  m.version = 2;
  return m;
}
export function validateTool(t) {
  number(t.diameter, 0.5, 40, "공구 지름");
  number(t.stepDown, 0.1, 20, "깊이 간격");
  number(t.stepOver, 10, 80, "가로 간격 (%)");
  number(t.feed, 10, 5000, "이송 속도");
  number(t.safeHeight, 1, 30, "안전 높이");
}
export function layers(m) {
  if (!m.stock) return [];
  const top = m.stock.height;
  const levels = [
    ...new Set([0, top, ...m.features.map((f) => top - f.depth)]),
  ].sort((a, b) => a - b);
  const base = [[ring(m.stock)]];
  return levels.slice(0, -1).map((z, i) => {
    const cuts = m.features
      .filter((f) => top - f.depth <= z + 1e-8)
      .map((f) => [ring(f)]);
    return {
      z0: z,
      z1: levels[i + 1],
      polygons: cuts.length
        ? clipping.difference(base, ...cuts)
        : clipping.union(base),
    };
  });
}
export const polygonDifference = (a, b) =>
  b.length ? clipping.difference(a, b) : a;

export function generatePaths(m, t) {
  validateModel(m);
  validateTool(t);
  if (!m.stock || !m.features.length)
    throw Error("먼저 기본 돌출에 파내기 작업을 추가하세요.");
  const points = [],
    warnings = [],
    operations = [];
  const safe = m.stock.height + t.safeHeight,
    toolR = t.diameter / 2;
  // Margin keeps polygonal approximation and raster endpoints inside the analytic profile.
  const margin = 0.02;
  const push = (x, y, z, cut, feature) => {
    if (points.length >= 60000)
      throw Error("경로가 너무 많습니다. 깊이 간격 또는 공구 지름을 늘리세요.");
    const prev = points.at(-1);
    const length = prev ? Math.hypot(x - prev.x, y - prev.y, z - prev.z) : 0;
    const duration = prev ? (length / (cut ? t.feed : 3000)) * 60 : 0;
    points.push({
      x,
      y,
      z,
      cut,
      feature,
      length,
      time: (prev?.time ?? 0) + duration,
    });
  };
  for (const f of m.features) {
    const inset = toolR + margin;
    if (Math.min(f.w, f.h) <= inset * 2)
      throw Error(
        `${f.name}: 공구가 홈보다 큽니다. 더 작은 공구를 선택하세요.`,
      );
    if (f.type === "rect" && f.radius < toolR)
      warnings.push(
        `${f.name}: 안쪽 모서리에 공구 반경 ${toolR}mm만큼 잔삭이 남습니다.`,
      );
    const inner = {
      ...f,
      w: f.w - inset * 2,
      h: f.h - inset * 2,
      radius: Math.max(0, f.radius - inset),
    };
    const contour = ring(f, inset, 12);
    const span = (y) => {
      const dy = Math.abs(y - f.y);
      if (f.type === "circle")
        return Math.sqrt(Math.max(0, inner.w ** 2 / 4 - dy ** 2));
      const q = Math.max(0, dy - inner.h / 2 + inner.radius);
      return (
        inner.w / 2 -
        inner.radius +
        Math.sqrt(Math.max(0, inner.radius ** 2 - q ** 2))
      );
    };
    const rows = Math.max(
      1,
      Math.ceil(inner.h / ((t.diameter * t.stepOver) / 100)),
    );
    const raster = [];
    for (let row = 0; row <= rows; row++) {
      const y = f.y - inner.h / 2 + (inner.h * row) / rows;
      const half = span(y);
      const ends = row % 2 ? [half, -half] : [-half, half];
      for (const x of ends) raster.push([f.x + x, y]);
    }
    const passes = Math.ceil(f.depth / t.stepDown),
      start = points.length;
    for (let p = 1; p <= passes; p++) {
      const z = m.stock.height - Math.min(f.depth, p * t.stepDown);
      const [x, y] = raster[0];
      if (points.length) {
        const prev = points.at(-1);
        push(prev.x, prev.y, safe, false, f.id);
      }
      push(x, y, safe, false, f.id);
      // Educational plunge entry; no machine-ready NC is exported.
      push(x, y, z, true, f.id);
      for (const [rx, ry] of raster.slice(1)) push(rx, ry, z, true, f.id);
      for (const [cx, cy] of [...contour, contour[0]])
        push(cx, cy, z, true, f.id);
    }
    const last = points.at(-1);
    push(last.x, last.y, safe, false, f.id);
    operations.push({
      id: f.id,
      name: f.name,
      passes,
      start,
      end: points.length,
    });
  }
  return {
    points,
    operations,
    warnings,
    seconds: points.at(-1).time,
    length: points.reduce((s, p) => s + p.length, 0),
    tool: clone(t),
  };
}

export function createStockGrid(m) {
  const b = bounds(m.stock),
    cell = Math.max(0.4, m.stock.w / 150, m.stock.h / 150);
  const nx = Math.ceil((b.maxX - b.minX) / cell),
    ny = Math.ceil((b.maxY - b.minY) / cell);
  const dx = (b.maxX - b.minX) / nx,
    dy = (b.maxY - b.minY) / ny;
  const heights = new Float32Array(nx * ny),
    initial = new Float32Array(nx * ny);
  for (let y = 0; y < ny; y++)
    for (let x = 0; x < nx; x++) {
      const h =
        distance(m.stock, b.minX + (x + 0.5) * dx, b.minY + (y + 0.5) * dy) <= 0
          ? m.stock.height
          : 0;
      heights[y * nx + x] = initial[y * nx + x] = h;
    }
  return {
    ...b,
    nx,
    ny,
    dx,
    dy,
    heights,
    initial,
    top: m.stock.height,
    removed: 0,
  };
}
// A flat end mill sweeps a cylinder. Height-field cells represent vertical columns.
export function sweep(grid, a, b, radius) {
  if (!b.cut) return;
  const dist = Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z);
  const n = Math.max(
    1,
    Math.ceil(dist / Math.min(grid.dx / 2, grid.dy / 2, radius / 2)),
  );
  for (let k = 0; k <= n; k++) {
    const t = k / n,
      x = a.x + (b.x - a.x) * t,
      y = a.y + (b.y - a.y) * t,
      z = a.z + (b.z - a.z) * t;
    if (z >= grid.top) continue;
    const x0 = Math.max(0, Math.floor((x - radius - grid.minX) / grid.dx)),
      x1 = Math.min(
        grid.nx - 1,
        Math.floor((x + radius - grid.minX) / grid.dx),
      );
    const y0 = Math.max(0, Math.floor((y - radius - grid.minY) / grid.dy)),
      y1 = Math.min(
        grid.ny - 1,
        Math.floor((y + radius - grid.minY) / grid.dy),
      );
    for (let iy = y0; iy <= y1; iy++)
      for (let ix = x0; ix <= x1; ix++) {
        const px = grid.minX + (ix + 0.5) * grid.dx,
          py = grid.minY + (iy + 0.5) * grid.dy;
        if ((px - x) ** 2 + (py - y) ** 2 > radius ** 2) continue;
        const idx = iy * grid.nx + ix,
          old = grid.heights[idx],
          next = Math.max(0, Math.min(old, z));
        grid.removed += (old - next) * grid.dx * grid.dy;
        grid.heights[idx] = next;
      }
  }
}
export function simulationAt(m, path, fraction) {
  const grid = createStockGrid(m),
    time = path.seconds * Math.max(0, Math.min(1, fraction));
  let pos = path.points[0];
  for (let i = 1; i < path.points.length; i++) {
    const a = path.points[i - 1],
      b = path.points[i];
    if (a.time > time) break;
    const t =
      b.time === a.time ? 1 : Math.min(1, (time - a.time) / (b.time - a.time));
    const end = {
      ...b,
      x: a.x + (b.x - a.x) * t,
      y: a.y + (b.y - a.y) * t,
      z: a.z + (b.z - a.z) * t,
    };
    sweep(grid, a, end, path.tool.diameter / 2);
    pos = end;
    if (t < 1) break;
  }
  return { grid, pos };
}
export function residualVolume(m, grid) {
  let residual = 0;
  for (let y = 0; y < grid.ny; y++)
    for (let x = 0; x < grid.nx; x++) {
      const idx = y * grid.nx + x;
      if (!grid.initial[idx]) continue;
      const px = grid.minX + (x + 0.5) * grid.dx,
        py = grid.minY + (y + 0.5) * grid.dy;
      let target = m.stock.height;
      for (const f of m.features)
        if (distance(f, px, py) <= 0)
          target = Math.min(target, m.stock.height - f.depth);
      residual += Math.max(0, grid.heights[idx] - target) * grid.dx * grid.dy;
    }
  return residual;
}
