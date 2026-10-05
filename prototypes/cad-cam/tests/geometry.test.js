import test from "node:test";
import assert from "node:assert/strict";
import { Worker } from "node:worker_threads";
import { once } from "node:events";
import {
  emptyModel,
  sampleModel,
  defaultTool,
  validateModel,
  parseModel,
  distance,
  ring,
  layers,
  generatePaths,
  simulationAt,
  residualVolume,
} from "../src/model.js";
import { solidGeometry } from "../src/viewer.js";
const rectangle = () => ({
  version: 1,
  name: "검증 부품",
  stock: {
    id: "stock",
    type: "rect",
    x: 0,
    y: 0,
    w: 80,
    h: 60,
    radius: 0,
    height: 12,
  },
  features: [],
});
const pocket = (id, w, h, depth) => ({
  id,
  type: "rect",
  x: 0,
  y: 0,
  w,
  h,
  radius: 0,
  depth,
  name: id,
});
function volume(g) {
  const v = g.attributes.position.array;
  let sum = 0;
  for (let i = 0; i < v.length; i += 9) {
    const [ax, ay, az, bx, by, bz, cx, cy, cz] = v.slice(i, i + 9);
    sum +=
      (ax * (by * cz - bz * cy) -
        ay * (bx * cz - bz * cx) +
        az * (bx * cy - by * cx)) /
      6;
  }
  return sum;
}
test("design JSON preserves editable parameters; rejects invalid/oversized shapes", () => {
  const m = sampleModel();
  assert.deepEqual(parseModel(JSON.stringify(m)), m);
  assert.deepEqual(validateModel(emptyModel()), emptyModel());
  for (const modify of [
    (m) => (m.stock.height = NaN),
    (m) => (m.features[0].depth = 99),
    (m) => (m.features[0].x = 90),
    (m) => (m.features[1].id = m.features[0].id),
    (m) => (m.stock.w = Infinity),
    (m) => (m.features[1].h = 10),
  ]) {
    const bad = structuredClone(m);
    modify(bad);
    assert.throws(() => validateModel(bad));
  }
  assert.throws(() => parseModel("x".repeat(100001)));
  assert.throws(() => parseModel("{broken"));
});
test("rounded and circular profile points agree with signed distance", () => {
  const m = sampleModel();
  for (const s of [m.stock, m.features[0], m.features[1]])
    for (const [x, y] of ring(s)) assert.ok(Math.abs(distance(s, x, y)) < 1e-8);
});
test("solid mesh volume includes overlapping pockets at different depths exactly once", () => {
  const m = rectangle();
  m.features = [pocket("a", 40, 20, 4), pocket("b", 20, 20, 8)];
  assert.equal(layers(m).length, 3);
  const g = solidGeometry(m);
  assert.ok(
    Math.abs(volume(g) - (80 * 60 * 12 - 40 * 20 * 4 - 20 * 20 * 4)) < 0.001,
  );
  g.dispose();
});
test("circular through hole changes volume and leaves no bottom cap across the hole", () => {
  const m = rectangle();
  m.features = [{ ...pocket("hole", 20, 20, 12), type: "circle" }];
  const g = solidGeometry(m);
  const expected = 80 * 60 * 12 - Math.PI * 100 * 12;
  assert.ok(Math.abs(volume(g) - expected) < 5);
  g.dispose();
});
test("path cutter centres stay inside pockets and traverse between pockets at safe height", () => {
  const m = sampleModel(),
    t = defaultTool(),
    p = generatePaths(m, t);
  assert.equal(p.operations.length, 2);
  for (let i = 1; i < p.points.length; i++) {
    const a = p.points[i - 1],
      b = p.points[i];
    assert.ok(Number.isFinite(b.time));
    assert.ok(b.time >= a.time);
    if (b.cut) {
      const f = m.features.find((f) => f.id === b.feature);
      assert.ok(b.z >= m.stock.height - f.depth - 1e-7);
      for (let k = 0; k <= 8; k++) {
        const x = a.x + ((b.x - a.x) * k) / 8,
          y = a.y + ((b.y - a.y) * k) / 8;
        assert.ok(distance(f, x, y) <= -t.diameter / 2 + 1e-6);
      }
    } else if (a.x !== b.x || a.y !== b.y) {
      assert.equal(a.z, m.stock.height + t.safeHeight);
      assert.equal(b.z, a.z);
    }
  }
});
test("tool size guard and sharp inside corner residual warning", () => {
  const m = rectangle();
  m.features = [pocket("pocket", 20, 20, 4)];
  assert.throws(
    () => generatePaths(m, { ...defaultTool(), diameter: 20 }),
    /공구/,
  );
  assert.equal(generatePaths(m, defaultTool()).warnings.length, 1);
});
test("material removal is progressive, retains exterior walls, and reports remaining corners", () => {
  const m = rectangle();
  m.features = [pocket("pocket", 30, 20, 6)];
  const p = generatePaths(m, defaultTool());
  const start = simulationAt(m, p, 0),
    mid = simulationAt(m, p, 0.5),
    end = simulationAt(m, p, 1);
  assert.equal(start.grid.removed, 0);
  assert.ok(mid.grid.removed > 0);
  assert.ok(end.grid.removed > mid.grid.removed);
  assert.ok(end.grid.removed < 30 * 20 * 6);
  assert.ok(end.grid.removed > 30 * 20 * 6 * 0.94);
  assert.ok(residualVolume(m, end.grid) > 0);
  const g = end.grid;
  for (let y = 0; y < g.ny; y++)
    for (let x = 0; x < g.nx; x++)
      if (
        distance(
          m.features[0],
          g.minX + (x + 0.5) * g.dx,
          g.minY + (y + 0.5) * g.dy,
        ) > 0
      )
        assert.equal(g.heights[y * g.nx + x], 12);
});
test("through milling reaches zero height instead of preserving an artificial floor", () => {
  const m = rectangle();
  m.features = [{ ...pocket("hole", 16, 16, 12), type: "circle" }];
  const p = generatePaths(m, defaultTool()),
    { grid: g } = simulationAt(m, p, 1);
  assert.equal(
    g.heights[Math.floor(g.ny / 2) * g.nx + Math.floor(g.nx / 2)],
    0,
  );
});
test("incremental worker playback and backward seek agree with full deterministic simulation", async () => {
  const url = new URL("../src/simulation.worker.js", import.meta.url).href;
  const bootstrap = `import {parentPort} from 'node:worker_threads';globalThis.self={postMessage:(data,transfer)=>parentPort.postMessage(data,transfer)};await import(${JSON.stringify(url)});parentPort.on('message',data=>self.onmessage({data}));`;
  const worker = new Worker(
    new URL(`data:text/javascript,${encodeURIComponent(bootstrap)}`),
    { type: "module" },
  );
  try {
    const m = rectangle();
    m.features = [pocket("a", 30, 20, 4)];
    const path = generatePaths(m, defaultTool());
    for (const fraction of [0, 0.13, 0.46, 1, 0.25, 1, 0]) {
      const result = once(worker, "message");
      worker.postMessage({ model: m, path, fraction, revision: 1, request: 1 });
      const [actual] = await result;
      assert.equal(actual.error, undefined);
      const expected = simulationAt(m, path, fraction);
      assert.ok(
        Math.abs(actual.grid.removed - expected.grid.removed) < 0.2,
        `fraction=${fraction}`,
      );
      let maxDiff = 0;
      actual.grid.heights.forEach((v, i) => {
        maxDiff = Math.max(maxDiff, Math.abs(v - expected.grid.heights[i]));
      });
      assert.ok(maxDiff < 0.001);
    }
  } finally {
    await worker.terminate();
  }
});
