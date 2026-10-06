import { ring, distance, validateModel, validateTool } from "./model.js";
export function scanRows(polygons, step) {
  const ys = polygons.flat().map((p) => p[1]);
  if (!ys.length) return [];
  const spans = [];
  for (let y = Math.min(...ys) + step / 2; y < Math.max(...ys); y += step) {
    const xs = [];
    for (const r of polygons)
      for (let i = 0; i < r.length; i++) {
        const a = r[i],
          b = r[(i + 1) % r.length];
        if (a[1] > y !== b[1] > y)
          xs.push(a[0] + ((y - a[1]) * (b[0] - a[0])) / (b[1] - a[1]));
      }
    xs.sort((a, b) => a - b);
    if (xs.length % 2) throw Error("가공 윤곽의 교차점을 계산하지 못했습니다.");
    for (let i = 0; i < xs.length; i += 2)
      if (xs[i + 1] - xs[i] > 1e-6)
        spans.push([
          [xs[i], y],
          [xs[i + 1], y],
        ]);
  }
  return spans;
}
export function generateKernelPaths(m, t, C) {
  validateModel(m);
  validateTool(t);
  if (!m.stock || !m.features.length)
    throw Error("먼저 기본 돌출에 파내기 작업을 추가하세요.");
  const points = [],
    operations = [],
    warnings = [
      "윤곽 근사·평 엔드밀 기준입니다. 코너 잔삭은 소재 제거 결과에서 확인하세요.",
    ];
  const safe = m.stock.height + t.safeHeight,
    R = t.diameter / 2;
  const push = (x, y, z, cut, feature) => {
    if (points.length >= 60000)
      throw Error("경로가 너무 많습니다. 깊이 간격 또는 공구 지름을 늘리세요.");
    const a = points.at(-1),
      length = a ? Math.hypot(x - a.x, y - a.y, z - a.z) : 0;
    points.push({
      x,
      y,
      z,
      cut,
      feature,
      length,
      time: (a?.time ?? 0) + (length / (cut ? t.feed : 3000)) * 60,
    });
  };
  for (const f of m.features) {
    let original, region;
    try {
      original = new C([ring(f)], "EvenOdd");
      region = original.offset(-R - 0.05, "Round", 2, 128);
      if (region.isEmpty())
        throw Error(
          `${f.name}: 공구가 들어갈 수 없습니다. 작은 공구를 선택하세요.`,
        );
      const contours = region.toPolygons().filter((r) => r.length >= 3),
        spans = scanRows(contours, (t.diameter * t.stepOver) / 100);
      const strokes = [...spans, ...contours.map((r) => [...r, r[0]])];
      for (const stroke of strokes)
        for (let i = 1; i < stroke.length; i++) {
          const a = stroke[i - 1],
            b = stroke[i],
            n = Math.max(
              1,
              Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.1),
            );
          for (let j = 0; j <= n; j++)
            if (
              distance(
                f,
                a[0] + ((b[0] - a[0]) * j) / n,
                a[1] + ((b[1] - a[1]) * j) / n,
              ) >
              -R - 0.005
            )
              throw Error(
                "공구 여유 검증 실패: 윤곽이나 공구 지름을 수정하세요.",
              );
        }
      const start = points.length,
        passes = Math.ceil(f.depth / t.stepDown);
      for (let pass = 1; pass <= passes; pass++) {
        const z = m.stock.height - Math.min(f.depth, pass * t.stepDown);
        for (const stroke of strokes) {
          const last = points.at(-1),
            a = stroke[0];
          if (last) push(last.x, last.y, safe, false, f.id);
          push(a[0], a[1], safe, false, f.id);
          push(a[0], a[1], z, true, f.id);
          for (const b of stroke.slice(1)) push(b[0], b[1], z, true, f.id);
        }
      }
      const last = points.at(-1);
      push(last.x, last.y, safe, false, f.id);
      operations.push({
        id: f.id,
        name: f.name,
        passes,
        start,
        end: points.length - 1,
      });
    } finally {
      region?.delete();
      original?.delete();
    }
  }
  return {
    points,
    operations,
    warnings,
    seconds: points.at(-1).time,
    length: points.reduce((s, p) => s + p.length, 0),
    tool: { ...t },
  };
}
