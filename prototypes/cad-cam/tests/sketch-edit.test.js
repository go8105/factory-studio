import test from "node:test";
import assert from "node:assert/strict";
import {
  asProfile,
  transformWire,
  trimWire,
  extendWire,
  offsetWire,
  measureEntity,
  constrain,
} from "../src/sketch-edit.js";
import {
  designJSON,
  validateShape,
  validateModel,
  sampleModel,
  layers,
  distance,
  parseModel,
  defaultTool,
  ring,
} from "../src/model.js";
import { regionRings } from "../src/sketch-region.js";
import { validateProfile, syncProfile } from "../src/profile.js";
import { generateKernelPaths } from "../src/cam.js";
import Module from "manifold-3d";
const kernel = await Module();
kernel.setup();
const rect = (w = 20, h = 10) =>
  asProfile({ type: "rect", x: 0, y: 0, w, h, radius: 0 });
const near = (a, b, t = 0.01) => assert.ok(Math.abs(a - b) < t, `${a} != ${b}`);
test("CAD16 templates retain analytic arcs and legacy dimensions", () => {
  for (const type of ["rect", "circle", "slot"])
    for (const angle of [0, 37]) {
      const s = {
        type,
        x: 5,
        y: 4,
        w: 20,
        h: type === "circle" ? 20 : 10,
        radius: type === "rect" ? 3 : 0,
        angle,
      };
      const p = asProfile(s);
      validateShape(p);
      assert.ok(p.nodes.length <= 8);
      assert.ok(p.nodes.some((n) => n.arcVia));
      near(
        Math.abs(
          p.nodes.length > 0
            ? measureEntity(p, p.nodes.find((n) => n.arcVia).id).radius
            : 0,
        ),
        type === "rect" ? 3 : type === "slot" ? 5 : 10,
      );
    }
  for (const radius of [5, 10])
    validateShape(
      asProfile({ type: "rect", x: 0, y: 0, w: 20, h: 20, radius }),
    );
});
test("multi point transform is immutable and arc via transforms with its entity", () => {
  const s = asProfile({ type: "circle", x: 0, y: 0, w: 20, h: 20, radius: 0 }),
    original = structuredClone(s),
    ids = s.nodes.map((n) => n.id);
  const moved = transformWire(s, ids, "move", [2, 3]);
  assert.deepEqual(s, original);
  assert.deepEqual(moved.nodes[0].point, [12, 3]);
  assert.deepEqual(moved.nodes[0].arcVia, [2, 13]);
  const rotated = transformWire(s, ids, "rotate", [0, 0, 90]);
  near(rotated.nodes[0].point[0], 0);
  near(rotated.nodes[0].point[1], 10);
  const reflected = transformWire(s, ids, "mirror-u", [0, 2, 0]);
  assert.deepEqual(reflected.nodes[0].arcVia, [0, -6]);
});
test("trim preserves ordered entity IDs and opens region; extend only straight open ends", () => {
  const s = rect(),
    cut = trimWire(s, "p2");
  assert.equal(cut.closed, false);
  assert.deepEqual(
    cut.nodes.map((n) => n.id),
    ["p3", "p4", "p1", "p2"],
  );
  assert.throws(() => validateShape(cut), /닫은/);
  assert.equal(s.closed, true);
  const longer = extendWire(cut, "p3", 3);
  near(
    Math.hypot(
      ...longer.nodes[0].point.map((v, k) => v - cut.nodes[0].point[k]),
    ),
    3,
  );
  const clipped = trimWire(cut, "p3", 0.5);
  near(clipped.nodes[0].point[0], 0);
  assert.throws(() => extendWire(s, "p1", 1), /열린/);
  assert.throws(() => trimWire(cut, "p4"), /첫/);
});
test("bounded convex offset has analytic expected dimensions and rejects collapse/concavity/arcs", () => {
  const s = rect();
  const p = offsetWire(s, 2);
  near(p.w, 24);
  near(p.h, 14);
  validateShape(p);
  near(offsetWire(s, -2).w, 16);
  assert.throws(() => offsetWire(s, -6), /소멸/);
  const concave = rect();
  concave.nodes.splice(2, 0, { id: "notch", point: [0, 0] });
  syncProfile(concave);
  assert.throws(() => offsetWire(concave, 1), /볼록/);
  assert.throws(
    () =>
      offsetWire(
        asProfile({ type: "circle", x: 0, y: 0, w: 20, h: 20, radius: 0 }),
        1,
      ),
    /직선/,
  );
});
test("distance constraints solve and edits cannot silently discard constraints", () => {
  const s = constrain(rect(), { type: "length", a: "p1", b: "p2", value: 18 });
  validateShape(s);
  near(
    Math.hypot(...s.nodes[0].point.map((v, k) => v - s.nodes[1].point[k])),
    18,
    0.001,
  );
  assert.throws(() => transformWire(s, ["p1"], "move", [1, 0]), /구속/);
  assert.throws(() => trimWire(s, "p1"), /구속/);
  assert.throws(
    () => constrain(s, { type: "length", a: "missing", b: "p1", value: 5 }),
    /점/,
  );
});
const islandModel = () => {
  const m = sampleModel();
  m.features = [
    {
      ...rect(60, 40),
      id: "pocket",
      name: "섬 포켓",
      depth: 6,
      holes: [rect(10, 8)],
    },
  ];
  return m;
};
test("island area, signed distance and saved JSON preserve removal region", () => {
  const m = islandModel();
  validateModel(m);
  const f = m.features[0];
  assert.equal(regionRings(f, ring(f)).length, 2);
  assert.ok(distance(f, 0, 0) > 0);
  assert.ok(distance(f, 10, 0) < 0);
  assert.deepEqual(parseModel(JSON.stringify(m)), m);
  const layer = layers(m).find((l) => l.z0 === 10);
  assert.equal(layer.polygons.length, 2); // outer material + retained island
});
test("island topology rejects touching, overlap, nesting, open wires and a pocket over stock void", () => {
  const m = islandModel();
  m.features[0].holes[0].nodes.forEach((n) => (n.point[0] += 26));
  syncProfile(m.features[0].holes[0]);
  assert.throws(() => validateModel(m), /0.1/);
  const overlap = islandModel();
  overlap.features[0].holes.push(rect(4, 4));
  assert.throws(() => validateModel(overlap), /겹치/);
  const open = islandModel();
  open.features[0].holes[0].closed = false;
  assert.throws(() => validateModel(open), /닫은/);
  const voided = islandModel();
  voided.stock = {
    ...rect(90, 70),
    height: 16,
    id: "stock",
    holes: [rect(5, 5)],
  };
  voided.features[0].holes = [];
  assert.throws(() => validateModel(voided), /외곽/);
});
test("real Manifold path leaves island plus tool radius; cuts never connect through island", () => {
  const m = islandModel(),
    t = defaultTool(),
    path = generateKernelPaths(m, t, kernel.CrossSection),
    R = t.diameter / 2;
  for (let i = 1; i < path.points.length; i++) {
    const a = path.points[i - 1],
      b = path.points[i];
    if (!b.cut || !a.cut) continue;
    const N = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / 0.1));
    for (let j = 0; j <= N; j++) {
      assert.ok(
        distance(
          m.features[0],
          a.x + ((b.x - a.x) * j) / N,
          a.y + ((b.y - a.y) * j) / N,
        ) <=
          -R + 0.02,
      );
    }
  }
  assert.ok(path.points.length > 50);
});

test("saved expanded region models remain importable within the file cap", () => {
  const m = islandModel();
  m.padding = "a".repeat(98500);
  validateModel(m);
  const text = designJSON(m);
  assert.ok(text.length <= 100000);
  assert.deepEqual(parseModel(text), m);
  m.padding += "a".repeat(2000);
  assert.throws(() => validateModel(m), /상한/);
});
