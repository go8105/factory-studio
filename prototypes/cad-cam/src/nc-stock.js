// Bounded top-surface review, not a controller or general solid simulator.
export const STOCK_LIMITS = {
  cells: 40000,
  triangles: 20000,
  intersections: 20000000,
  visits: 5000000,
};
const fail = (message) => {
  throw Error(message);
};
const finite = (v) =>
  typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= 1e6;
export function transformMesh(mesh, transform) {
  if (
    !transform?.offset?.every(finite) ||
    transform.offset.length !== 3 ||
    !finite(transform.angle)
  )
    fail("STEP 변환 좌표 오류");
  const a = (transform.angle * Math.PI) / 180,
    c = Math.cos(a),
    s = Math.sin(a);
  const vertices = [];
  for (let i = 0; i < mesh.vertices.length; i += 3) {
    const [x, y, z] = mesh.vertices.slice(i, i + 3);
    vertices.push(
      c * x - s * y + transform.offset[0],
      s * x + c * y + transform.offset[1],
      z + transform.offset[2],
    );
  }
  if (!vertices.every(finite)) fail("STEP 좌표 상한 초과");
  return { vertices, triangles: mesh.triangles };
}
export function meshBounds(mesh) {
  const min = [Infinity, Infinity, Infinity],
    max = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < mesh.vertices.length; i++) {
    const j = i % 3;
    min[j] = Math.min(min[j], mesh.vertices[i]);
    max[j] = Math.max(max[j], mesh.vertices[i]);
  }
  return [min, max];
}
export function validateSetup(setup) {
  const { stock, tools, pitch, transform } = setup;
  if (
    !stock?.min?.every(finite) ||
    stock.min.length !== 3 ||
    !stock.size?.every((v) => finite(v) && v > 0) ||
    stock.size.length !== 3 ||
    !stock.material?.trim()
  )
    fail("소재 이름·좌표·양수 크기를 입력하세요");
  if (!finite(pitch) || pitch < 0.1 || pitch > 10) fail("격자 간격은 0.1–10mm");
  if (!Array.isArray(tools) || !tools.length || tools.length > 100)
    fail("공구표 필요 (최대100개)");
  const ids = new Set();
  for (const t of tools) {
    if (!Number.isInteger(t.t) || t.t < 0 || t.t > 99999 || ids.has(t.t))
      fail("공구 T 번호 누락/중복");
    ids.add(t.t);
    if (
      t.type !== "flat" ||
      !finite(t.diameter) ||
      t.diameter <= 0 ||
      !finite(t.flute) ||
      t.flute <= 0
    )
      fail("양수 지름·날 길이의 평엔드밀만 지원");
    for (const k of ["h", "d"])
      if (t[k] != null && (!Number.isInteger(t[k]) || t[k] < 0 || t[k] > 99999))
        fail("H/D 참조 번호 오류");
  }
  if (setup.initialTool != null && !ids.has(setup.initialTool))
    fail("초기 T가 공구표에 없습니다");
  transformMesh({ vertices: [], triangles: [] }, transform);
  if (!setup.aligned || !setup.topSurfaceConfirmed)
    fail("STEP/G54 정합·상면 형상 확인 전 비교 차단");
}
export function analyzeStock(nc, reference, setup) {
  validateSetup(setup);
  if (!nc?.complete || !nc.segments.length) fail("전체 해석된 NC 경로 필요");
  if (!reference?.solid) fail("단일 Solid STEP 필요");
  const mesh = transformMesh(reference.mesh, setup.transform),
    { stock, pitch } = setup;
  const bounds = meshBounds(mesh),
    top = stock.min[2] + stock.size[2],
    bottom = stock.min[2],
    tol = 0.1;
  for (let i = 0; i < 3; i++)
    if (
      bounds[0][i] < stock.min[i] - 0.001 ||
      bounds[1][i] > stock.min[i] + stock.size[i] + 0.001
    )
      fail("STEP 목표가 소재 범위를 벗어납니다");
  const nx = Math.ceil(stock.size[0] / pitch),
    ny = Math.ceil(stock.size[1] / pitch),
    count = nx * ny;
  if (count > STOCK_LIMITS.cells) fail("격자40,000셀 상한 초과");
  const triangles = mesh.triangles.length / 3;
  if (
    triangles > STOCK_LIMITS.triangles ||
    triangles * count > STOCK_LIMITS.intersections
  )
    fail("STEP×격자 검사 상한 초과");
  const dx = stock.size[0] / nx,
    dy = stock.size[1] / ny,
    area = dx * dy;
  const horizontals = [];
  for (let i = 0; i < mesh.triangles.length; i += 3) {
    const p = mesh.triangles
      .slice(i, i + 3)
      .map((k) => mesh.vertices.slice(k * 3, k * 3 + 3));
    const u = p[1].map((v, k) => v - p[0][k]),
      v = p[2].map((v, k) => v - p[0][k]);
    const n = [
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
      ],
      len = Math.hypot(...n);
    if (len < 1e-10) continue;
    if (Math.abs(n[2]) / len < 1e-8) continue; // vertical faces
    if (Math.abs(n[2]) / len < 1 - 1e-8)
      fail("경사·곡면 STEP은 상면 비교 미지원");
    horizontals.push(p);
  }
  const target = new Float64Array(count),
    heights = new Float64Array(count).fill(top);
  for (let iy = 0; iy < ny; iy++)
    for (let ix = 0; ix < nx; ix++) {
      const x = stock.min[0] + (ix + 0.5) * dx,
        y = stock.min[1] + (iy + 0.5) * dy,
        hits = [];
      for (const [a, b, c] of horizontals) {
        const det =
          (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1]);
        const u =
          ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / det;
        const v =
          ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / det;
        if (u >= -1e-9 && v >= -1e-9 && u + v <= 1 + 1e-9) hits.push(a[2]);
      }
      hits.sort((a, b) => a - b);
      const levels = hits.filter((v, k) => !k || v - hits[k - 1] > 0.001);
      if (
        levels.length &&
        (levels.length !== 2 || Math.abs(levels[0] - bottom) > 0.001)
      )
        fail("떠 있는/중공/다층 형상 미지원");
      target[iy * nx + ix] = levels.length ? levels[1] : bottom;
    }
  const targetVolume = target.reduce((sum, z) => sum + (z - bottom) * area, 0);
  if (targetVolume <= 0)
    fail("격자로 목표 형상을 포착하지 못했습니다 · 간격을 줄이세요");
  let visits = 0;
  const segmentReviews = [],
    contacts = [],
    toolMap = new Map(setup.tools.map((t) => [t.t, t]));
  for (const seg of nc.segments) {
    const tool = toolMap.get(seg.state.tool ?? setup.initialTool);
    if (!tool) fail(`${seg.line}행 활성 공구 T 연결 필요`);
    const radius = tool.diameter / 2;
    if (
      seg.code !== "G0" &&
      (seg.state.spindle === "off" || seg.state.rpm <= 0)
    )
      fail(`${seg.line}행 주축 회전 확인 필요`);
    let contact = false,
      segmentRemoved = 0;
    for (let j = 1; j < seg.points.length; j++) {
      const a = seg.points[j - 1],
        b = seg.points[j],
        vx = b[0] - a[0],
        vy = b[1] - a[1],
        d2 = vx * vx + vy * vy;
      if (d2 > 1e-12 && Math.abs(b[2] - a[2]) > 1e-8)
        fail(`${seg.line}행 경사 이동은 제거 검토 미지원`);
      const z = Math.min(a[2], b[2]);
      if (z < bottom - 0.001) fail(`${seg.line}행 소재 바닥 아래 경로`);
      const x0 = Math.max(
          0,
          Math.floor((Math.min(a[0], b[0]) - radius - stock.min[0]) / dx),
        ),
        x1 = Math.min(
          nx - 1,
          Math.floor((Math.max(a[0], b[0]) + radius - stock.min[0]) / dx),
        );
      const y0 = Math.max(
          0,
          Math.floor((Math.min(a[1], b[1]) - radius - stock.min[1]) / dy),
        ),
        y1 = Math.min(
          ny - 1,
          Math.floor((Math.max(a[1], b[1]) + radius - stock.min[1]) / dy),
        );
      for (let iy = y0; iy <= y1; iy++)
        for (let ix = x0; ix <= x1; ix++) {
          if (++visits > STOCK_LIMITS.visits)
            fail("경로×격자 검사5,000,000회 상한 초과");
          const x = stock.min[0] + (ix + 0.5) * dx,
            y = stock.min[1] + (iy + 0.5) * dy;
          const t = d2
            ? Math.max(0, Math.min(1, ((x - a[0]) * vx + (y - a[1]) * vy) / d2))
            : 0;
          if (Math.hypot(x - a[0] - t * vx, y - a[1] - t * vy) > radius)
            continue;
          const k = iy * nx + ix;
          if (heights[k] > z + 0.001) {
            if (heights[k] - z > tool.flute + 0.001)
              fail(`${seg.line}행 날 길이 초과 접촉 · 몸통 검토 필요`);
            if (seg.code === "G0") contact = true;
            else {
              const nextHeight = Math.max(bottom, z);
              segmentRemoved += (heights[k] - nextHeight) * area;
              heights[k] = nextHeight;
            }
          }
        }
    }
    if (contact) contacts.push(seg.line);
    segmentReviews.push({
      id: seg.id,
      line: seg.line,
      removedMm3: segmentRemoved,
    });
  }
  let removed = 0,
    remaining = 0,
    overcut = 0,
    maxOvercut = 0,
    maxRemaining = 0;
  for (let k = 0; k < count; k++) {
    removed += (top - heights[k]) * area;
    const d = heights[k] - target[k];
    if (d > tol) remaining += d * area;
    if (d < -tol) overcut -= d * area;
    maxRemaining = Math.max(maxRemaining, d);
    maxOvercut = Math.max(maxOvercut, -d);
  }
  return {
    schemaVersion: 1,
    ncSourceHash: nc.sourceHash ?? null,
    segments: segmentReviews,
    setup,
    reference: {
      fileName: reference.fileName,
      sourceHash: reference.sourceHash,
      volume: reference.volume,
      bounds,
    },
    grid: { nx, ny, dx, dy, cells: count },
    removed,
    remaining,
    overcut,
    maxOvercut,
    maxRemaining,
    rapidContactLines: contacts,
    tolerance: tol,
    targetVolume,
    targetVolumeError:
      Math.abs(targetVolume - reference.volume) / reference.volume,
    heights: Array.from(heights),
    target: Array.from(target),
    visits,
    energyKWh: null,
    limitations: [
      "격자 셀 중심·원호 현 근사; 작은 특징 누락 가능",
      "프로그램 공구 끝점만; 기계·홀더·지그·교환 이동 제외",
      "0 검출은 안전 보증 아님; 실측 품질/에너지 미정",
    ],
  };
}
