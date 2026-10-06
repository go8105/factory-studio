// Analytic sketch entities remain in JSON; only the displayed/manufactured boundary is tessellated.
const TAU = Math.PI * 2;
const cache = new WeakMap();
export function arcPoints(a, via, b) {
  const [x1, y1] = a,
    [x2, y2] = via,
    [x3, y3] = b;
  const d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2));
  if (Math.abs(d) < 1e-7)
    throw Error("원호의 세 점은 서로 다르고 일직선이 아니어야 합니다.");
  const q1 = x1 * x1 + y1 * y1,
    q2 = x2 * x2 + y2 * y2,
    q3 = x3 * x3 + y3 * y3;
  const cx = (q1 * (y2 - y3) + q2 * (y3 - y1) + q3 * (y1 - y2)) / d;
  const cy = (q1 * (x3 - x2) + q2 * (x1 - x3) + q3 * (x2 - x1)) / d;
  const r = Math.hypot(x1 - cx, y1 - cy);
  if (r > 1000) throw Error("원호 반경은 1000mm 이하여야 합니다.");
  const start = Math.atan2(y1 - cy, x1 - cx);
  const positive = (t) => ((t % TAU) + TAU) % TAU;
  const end = positive(Math.atan2(y3 - cy, x3 - cx) - start);
  const through = positive(Math.atan2(y2 - cy, x2 - cx) - start);
  const sweep = through < end ? end : end - TAU;
  const n = Math.max(
    2,
    Math.ceil(
      Math.abs(sweep) /
        Math.min(Math.PI / 16, 2 * Math.acos(Math.max(-1, 1 - 0.01 / r))),
    ),
  );
  if (n > 1024) throw Error("원호가 너무 복잡합니다. 반경을 줄이세요.");
  return Array.from({ length: n }, (_, i) => [
    cx + r * Math.cos(start + (sweep * i) / n),
    cy + r * Math.sin(start + (sweep * i) / n),
  ]);
}
export function profileRing(s) {
  if (s.type === "slot") {
    const r = s.h / 2,
      half = (s.w - s.h) / 2,
      angle = ((s.angle ?? 0) * Math.PI) / 180;
    const points = [];
    for (const [cx, start] of [
      [half, -Math.PI / 2],
      [-half, Math.PI / 2],
    ]) {
      for (let i = 0; i <= 64; i++) {
        const t = start + (Math.PI * i) / 64,
          x = cx + r * Math.cos(t),
          y = r * Math.sin(t);
        points.push([
          s.x + x * Math.cos(angle) - y * Math.sin(angle),
          s.y + x * Math.sin(angle) + y * Math.cos(angle),
        ]);
      }
    }
    return points;
  }
  let points = cache.get(s.nodes);
  if (!points) {
    points = [];
    for (let i = 0; i < s.nodes.length; i++) {
      const node = s.nodes[i],
        next = s.nodes[(i + 1) % s.nodes.length];
      if (node.arcVia && (s.closed || i < s.nodes.length - 1))
        points.push(...arcPoints(node.point, node.arcVia, next.point));
      else points.push(node.point);
    }
    cache.set(s.nodes, points);
  }
  return points.map(([x, y]) => [x + s.x, y + s.y]);
}
export function segmentDistance(p, a, b) {
  const dx = b[0] - a[0],
    dy = b[1] - a[1],
    len = dx * dx + dy * dy;
  const t = len
    ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len))
    : 0;
  return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
}
export function polygonDistance(points, x, y) {
  let inside = false,
    min = Infinity;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const a = points[j],
      b = points[i];
    min = Math.min(min, segmentDistance([x, y], a, b));
    if (
      a[1] > y !== b[1] > y &&
      x < ((b[0] - a[0]) * (y - a[1])) / (b[1] - a[1]) + a[0]
    )
      inside = !inside;
  }
  return inside ? -min : min;
}
export function syncProfile(s) {
  if (s.nodes) cache.delete(s.nodes);
  const pts = profileRing(s);
  if (!pts.length) {
    s.w = s.h = 1;
    return s;
  }
  const xs = pts.map((p) => p[0]),
    ys = pts.map((p) => p[1]);
  s.w = Math.max(...xs) - Math.min(...xs);
  s.h = Math.max(...ys) - Math.min(...ys);
  return s;
}
export function validateProfile(s) {
  if (!s.closed) throw Error("윤곽을 닫은 뒤 돌출 또는 파내기를 적용하세요.");
  if (!Array.isArray(s.nodes) || s.nodes.length < 2 || s.nodes.length > 64)
    throw Error("윤곽은 2~64개 꼭짓점으로 만드세요.");
  const ids = new Set();
  const pointOK = (p) =>
    Array.isArray(p) &&
    p.length === 2 &&
    p.every((v) => Number.isFinite(v) && Math.abs(v) <= 200);
  for (const n of s.nodes) {
    if (
      typeof n.id !== "string" ||
      !/^[a-zA-Z0-9_-]{1,64}$/.test(n.id) ||
      ids.has(n.id) ||
      !pointOK(n.point) ||
      (n.arcVia && !pointOK(n.arcVia))
    )
      throw Error("잘못되거나 중복된 꼭짓점입니다.");
    ids.add(n.id);
  }
  cache.delete(s.nodes);
  const pts = profileRing(s);
  if (pts.length > 4096) throw Error("윤곽이 너무 복잡합니다.");
  let area = 0;
  const cross = (a, b, c) =>
    (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i],
      b = pts[(i + 1) % pts.length];
    if (Math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6)
      throw Error("겹친 꼭짓점이나 길이가 없는 선을 제거하세요.");
    area += a[0] * b[1] - b[0] * a[1];
    for (let j = i + 2; j < pts.length; j++) {
      if (i === 0 && j === pts.length - 1) continue;
      const c = pts[j],
        d = pts[(j + 1) % pts.length];
      const c1 = cross(a, b, c),
        c2 = cross(a, b, d),
        c3 = cross(c, d, a),
        c4 = cross(c, d, b);
      if (
        c1 * c2 <= 0 &&
        c3 * c4 <= 0 &&
        Math.max(Math.min(a[0], b[0]), Math.min(c[0], d[0])) <=
          Math.min(Math.max(a[0], b[0]), Math.max(c[0], d[0])) + 1e-8 &&
        Math.max(Math.min(a[1], b[1]), Math.min(c[1], d[1])) <=
          Math.min(Math.max(a[1], b[1]), Math.max(c[1], d[1])) + 1e-8
      )
        throw Error("윤곽의 선이 교차하거나 겹칩니다. 꼭짓점을 수정하세요.");
    }
  }
  if (Math.abs(area) < 0.02) throw Error("면적이 있는 닫힌 윤곽이 필요합니다.");
  const w =
    Math.max(...pts.map((p) => p[0])) - Math.min(...pts.map((p) => p[0]));
  const h =
    Math.max(...pts.map((p) => p[1])) - Math.min(...pts.map((p) => p[1]));
  if (Math.abs(s.w - w) > 0.001 || Math.abs(s.h - h) > 0.001)
    throw Error("윤곽 치수가 꼭짓점과 일치하지 않습니다.");
}
