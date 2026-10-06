import test from "node:test";
import assert from "node:assert/strict";
import Module from "manifold-3d";
import {
  sampleModel,
  validateModel,
  parseModel,
  ring,
  distance,
  defaultTool,
  simulationAt,
  residualVolume,
  createStockGrid,
} from "../src/model.js";
import { syncProfile } from "../src/profile.js";
import { generateKernelPaths } from "../src/cam.js";
import { solidGeometry } from "../src/viewer.js";
const profile = (points) =>
  syncProfile({
    id: "free",
    name: "자유 홈",
    type: "profile",
    x: 0,
    y: 0,
    w: 1,
    h: 1,
    radius: 0,
    depth: 4,
    closed: true,
    nodes: points.map((point, i) => ({ id: `n${i}`, point })),
  });
const model = (f) => ({ ...sampleModel(), features: [f] });
const L = () =>
  profile([
    [-30, -20],
    [10, -20],
    [10, -5],
    [-10, -5],
    [-10, 20],
    [-30, 20],
  ]);
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
  g.dispose();
  return sum;
}
test("v1 migrates losslessly; v2 preserves vertex IDs and analytic arc points", () => {
  const old = sampleModel();
  old.version = 1;
  const newer = parseModel(JSON.stringify(old));
  assert.equal(newer.version, 2);
  assert.deepEqual({ ...newer, version: 1 }, old);
  const arc = profile([
    [-10, 0],
    [10, 0],
  ]);
  arc.nodes[0].arcVia = [0, 10];
  syncProfile(arc);
  assert.deepEqual(parseModel(JSON.stringify(model(arc))), model(arc));
  const points = ring(arc);
  assert.ok(points.length > 20);
  assert.ok(points.every((p) => Math.abs(Math.hypot(...p) - 10) < 1e-8));
  assert.ok(
    Math.abs(
      volume(solidGeometry(model(arc))) -
        (volume(solidGeometry({ ...sampleModel(), features: [] })) -
          Math.PI * 50 * 4),
    ) < 2,
  );
});
test("open, crossing, duplicate, collinear arc and inconsistent outlines are rejected", () => {
  const bads = [
    L(),
    profile([
      [-10, -10],
      [10, 10],
      [-10, 10],
      [10, -10],
    ]),
    profile([
      [0, 0],
      [0, 0],
      [10, 10],
    ]),
    profile([
      [-10, 0],
      [10, 0],
    ]),
    L(),
  ];
  bads[0].closed = false;
  bads[3].nodes[0].arcVia = [0, 0];
  bads[4].w = 10;
  for (const f of bads) assert.throws(() => validateModel(model(f)));
});
test("concave extrusion volume and shifted bounds work; crossing its notch is rejected", () => {
  const stock = { ...L(), id: "stock", height: 10, x: 40, y: 20 };
  delete stock.depth;
  const m = { version: 2, name: "L 소재", stock, features: [] };
  validateModel(m);
  assert.ok(Math.abs(volume(solidGeometry(m)) - 11000) < 0.01);
  const grid = createStockGrid(m);
  assert.equal(grid.minX, 10);
  assert.equal(grid.maxX, 50);
  const f = profile([
    [15, 5],
    [45, 5],
    [25, 35],
  ]);
  assert.throws(() => validateModel({ ...m, features: [f] }));
});
test("rotated capsule supports geometry, distance, through pocket and CAM", async () => {
  const f = {
    id: "slot",
    name: "회전 슬롯",
    type: "slot",
    x: 0,
    y: 0,
    w: 40,
    h: 10,
    angle: 65,
    radius: 0,
    depth: 16,
  };
  const m = model(f);
  validateModel(m);
  assert.ok(distance(f, 0, 0) < 0);
  assert.ok(ring(f).every((p) => Math.abs(distance(f, ...p)) < 1e-7));
  const mod = await Module();
  mod.setup();
  const path = generateKernelPaths(m, defaultTool(), mod.CrossSection);
  const { grid } = simulationAt(m, path, 1);
  assert.ok(grid.removed > 1000);
  assert.ok(residualVolume(m, grid) < 200);
});
test("concave and split-neck paths retain cutter clearance and retract between disjoint strokes", async () => {
  const mod = await Module();
  mod.setup();
  const neck = profile([
    [-30, -15],
    [-10, -15],
    [-10, -1],
    [10, -1],
    [10, -15],
    [30, -15],
    [30, 15],
    [10, 15],
    [10, 1],
    [-10, 1],
    [-10, 15],
    [-30, 15],
  ]);
  for (const f of [L(), neck]) {
    const m = model(f),
      t = defaultTool(),
      path = generateKernelPaths(m, t, mod.CrossSection);
    assert.ok(path.points.length > 20);
    for (let i = 1; i < path.points.length; i++) {
      const a = path.points[i - 1],
        b = path.points[i];
      if (!b.cut && (a.x !== b.x || a.y !== b.y)) {
        assert.equal(a.z, m.stock.height + t.safeHeight);
        assert.equal(b.z, a.z);
      }
      if (b.cut)
        for (let j = 0; j <= 20; j++) {
          const x = a.x + ((b.x - a.x) * j) / 20,
            y = a.y + ((b.y - a.y) * j) / 20;
          assert.ok(distance(f, x, y) <= -t.diameter / 2 + 1e-6);
        }
    }
    assert.ok(simulationAt(m, path, 1).grid.removed > 0);
  }
  assert.throws(
    () =>
      generateKernelPaths(
        model(L()),
        { ...defaultTool(), diameter: 40 },
        mod.CrossSection,
      ),
    /공구/,
  );
});
