import {
  ring,
  distance,
  validateModel,
  validateTool,
  simulationAt,
  residualVolume,
} from "./model.js";
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
function prepare(m, t, C) {
  validateModel(m);
  validateTool(t);
  if (!m.stock || !m.features.length)
    throw Error("먼저 기본 돌출에 파내기 작업을 추가하세요.");
  const groups = [];
  const R = t.diameter / 2;
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
      groups.push({
        feature: f,
        spans,
        finishes: contours.map((r) => [...r, r[0]]),
      });
    } finally {
      region?.delete();
      original?.delete();
    }
  }
  return groups;
}
function nearest(spans, start) {
  const left = [...spans],
    result = [];
  let end = start ?? spans[0]?.[0];
  while (left.length) {
    let best = 0;
    for (let i = 1; i < left.length; i++)
      if (
        Math.hypot(...left[i][0].map((v, k) => v - end[k])) <
        Math.hypot(...left[best][0].map((v, k) => v - end[k]))
      )
        best = i;
    const stroke = left.splice(best, 1)[0];
    result.push(stroke);
    end = stroke.at(-1);
  }
  return result;
}
function build(m, t, groups, optimize = false) {
  const points = [],
    operations = [],
    finishGroups = [];
  const safe = m.stock.height + t.safeHeight;
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
  for (const { feature: f, spans, finishes } of groups) {
    const start = points.length,
      passes = Math.ceil(f.depth / t.stepDown);
    for (let pass = 1; pass <= passes; pass++) {
      const z = m.stock.height - Math.min(f.depth, pass * t.stepDown);
      const last = points.at(-1);
      const raster = optimize
        ? nearest(spans, last ? [last.x, last.y] : null)
        : spans;
      for (const stroke of [...raster, ...finishes]) {
        const last = points.at(-1),
          a = stroke[0];
        if (last) push(last.x, last.y, safe, false, f.id);
        push(a[0], a[1], safe, false, f.id);
        push(a[0], a[1], z, true, f.id);
        for (const b of stroke.slice(1)) push(b[0], b[1], z, true, f.id);
      }
      finishGroups.push({ feature: f.id, z, strokes: finishes });
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
  }
  return {
    points,
    operations,
    finishGroups,
    warnings: [
      "윤곽 근사·평 엔드밀 기준입니다. 코너 잔삭은 소재 제거 결과에서 확인하세요.",
    ],
    seconds: points.at(-1).time,
    length: points.reduce((s, p) => s + p.length, 0),
    tool: { ...t },
  };
}
export function generateKernelPaths(m, t, C) {
  return build(m, t, prepare(m, t, C));
}
export function pathMetrics(path) {
  let cutLength = 0,
    rapidLength = 0;
  for (let i = 1; i < path.points.length; i++) {
    const a = path.points[i - 1],
      b = path.points[i];
    const length = Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z);
    if (b.cut) cutLength += length;
    else rapidLength += length;
  }
  return {
    cutLength,
    rapidLength,
    seconds: (cutLength / path.tool.feed) * 60 + (rapidLength / 3000) * 60,
    energyKWh: null,
    energySavingPercent: null,
  };
}
function cutSignature(path) {
  const segments = [];
  for (let i = 1; i < path.points.length; i++) {
    const a = path.points[i - 1],
      b = path.points[i];
    if (b.cut)
      segments.push(JSON.stringify([b.feature, a.x, a.y, a.z, b.x, b.y, b.z]));
  }
  return segments.sort().join("\n");
}
export function validateProposal(m, baseline, candidate) {
  if (
    JSON.stringify(baseline.tool) !== JSON.stringify(candidate.tool) ||
    cutSignature(baseline) !== cutSignature(candidate) ||
    JSON.stringify(baseline.finishGroups) !==
      JSON.stringify(candidate.finishGroups)
  )
    throw Error("절삭 방향·깊이·마무리 보존 검증 실패");
  const safe = m.stock.height + baseline.tool.safeHeight;
  const featureOrder = [],
    cutGroups = new Map();
  for (let i = 1; i < candidate.points.length; i++) {
    const a = candidate.points[i - 1],
      b = candidate.points[i];
    if (![b.x, b.y, b.z].every(Number.isFinite))
      throw Error("경로 좌표 검증 실패");
    if (
      !b.cut &&
      (a.x !== b.x || a.y !== b.y) &&
      Math.min(a.z, b.z) < safe - 1e-8
    )
      throw Error("안전 높이 검증 실패");
    if (b.cut) {
      const f = m.features.find((f) => f.id === b.feature);
      if (!f || b.z < m.stock.height - f.depth - 1e-8 || b.z > safe + 1e-8)
        throw Error("깊이 검증 실패");
      const n = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / 0.1));
      for (let j = 0; j <= n; j++)
        if (
          distance(
            f,
            a.x + ((b.x - a.x) * j) / n,
            a.y + ((b.y - a.y) * j) / n,
          ) >
          -baseline.tool.diameter / 2 - 0.005
        )
          throw Error("공구 여유 검증 실패");
      const key = JSON.stringify([b.feature, b.z]);
      if (featureOrder.at(-1) !== key) featureOrder.push(key);
      if (!cutGroups.has(key)) cutGroups.set(key, []);
      cutGroups.get(key).push([b.x, b.y]);
    }
  }
  const order = baseline.finishGroups.map((g) =>
    JSON.stringify([g.feature, g.z]),
  );
  if (JSON.stringify(featureOrder) !== JSON.stringify(order))
    throw Error("피처·깊이 순서 검증 실패");
  for (const g of baseline.finishGroups) {
    const expected = g.strokes.flat();
    const actual = cutGroups.get(JSON.stringify([g.feature, g.z])) ?? [];
    if (
      JSON.stringify(actual.slice(-expected.length)) !==
      JSON.stringify(expected)
    )
      throw Error("마무리 윤곽의 마지막 실행 순서 검증 실패");
  }
  return true;
}
export function generatePathProposals(m, t, C) {
  const groups = prepare(m, t, C),
    baseline = build(m, t, groups);
  validateProposal(m, baseline, baseline);
  const baseGrid = simulationAt(m, baseline, 1).grid;
  const baseResidual = residualVolume(m, baseGrid);
  const candidates = [
    {
      id: "baseline",
      name: "기존 순서",
      path: baseline,
      metrics: { ...pathMetrics(baseline), residualVolume: baseResidual },
      valid: true,
    },
  ];
  if (groups.some((g) => g.spans.length > 256))
    return {
      candidates,
      recommendedId: "baseline",
      reason:
        "같은 깊이의 래스터가 256개를 초과합니다. 기존 경로를 유지하세요.",
    };
  const candidate = build(m, t, groups, true);
  validateProposal(m, baseline, candidate);
  const grid = simulationAt(m, candidate, 1).grid;
  if (grid.heights.some((h, i) => Math.abs(h - baseGrid.heights[i]) > 1e-6))
    return {
      candidates,
      recommendedId: "baseline",
      reason: "동일 격자 소재 제거 검증 실패. 기존 경로를 유지하세요.",
    };
  candidates.push({
    id: "nearest",
    name: "가까운 시작점 순서",
    path: candidate,
    metrics: {
      ...pathMetrics(candidate),
      residualVolume: residualVolume(m, grid),
    },
    valid: true,
  });
  const improved =
    pathMetrics(candidate).rapidLength <
    pathMetrics(baseline).rapidLength - 1e-6;
  return {
    candidates,
    recommendedId: improved ? "nearest" : "baseline",
    reason: improved
      ? "품질 유지·비절삭 이동 감소 제안"
      : "검토한 후보에 이동 감소가 없습니다. 기존 순서를 제안합니다.",
  };
}
