import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import OC from "replicad-opencascadejs";
import { setKernel, buildPart, planePosition } from "../src/part-kernel.js";
import {
  emptyPart,
  bracketExample,
  shellExample,
  validatePart,
  importPart,
  partKey,
} from "../src/part-model.js";
import { solveSketch } from "../src/sketch-constraints.js";
setKernel(
  await OC({
    wasmBinary: readFileSync(
      new URL(import.meta.resolve("replicad-opencascadejs/wasm")),
    ),
  }),
);
const near = (a, b, t = 0.001) =>
  assert.ok(Math.abs(a - b) < t, `${a} != ${b}`);
const sketch = () => ({
  type: "profile",
  closed: true,
  x: 0,
  y: 0,
  w: 20,
  h: 20,
  nodes: [
    { id: "a", point: [-10, -10] },
    { id: "b", point: [10, -9] },
    { id: "c", point: [10, 10] },
    { id: "d", point: [-10, 10] },
  ],
  constraints: [],
});
test("real BRep side hole and array remove analytic cylinder volumes", () => {
  const m = bracketExample(),
    x = buildPart(m);
  try {
    near(x.info.volume, 70 * 50 * 8 + 60 * 8 * 28 - 3 * Math.PI * 16 * 8);
    assert.deepEqual(
      x.steps.map((s) => s.id),
      ["upright", "side-hole", "hole-array"],
    );
    near(x.info.bounds[1][2], 36);
  } finally {
    x.shape.delete();
  }
});
test("upstream height edit rebuilds dependent support plane", () => {
  const m = bracketExample();
  m.base.height = 12;
  const x = buildPart(m);
  try {
    near(x.info.bounds[1][2], 40);
    near(x.info.volume, 70 * 50 * 12 + 60 * 8 * 28 - 3 * Math.PI * 16 * 8);
  } finally {
    x.shape.delete();
  }
});
test("shell opens top and fillet changes real solid", () => {
  const m = shellExample();
  m.operations.pop();
  const sh = buildPart(m);
  try {
    near(sh.info.volume, 60 * 40 * 24 - 56 * 36 * 22);
  } finally {
    sh.shape.delete();
  }
  const f = buildPart(shellExample());
  try {
    assert.ok(f.info.volume < 13248 && f.info.volume > 13000);
    assert.ok(f.shape.mesh().triangles.length > 100);
  } finally {
    f.shape.delete();
  }
});
test("mirror duplicates cut and circular pattern rotates operand", () => {
  const m = emptyPart();
  m.base.height = 10;
  m.operations = [
    {
      id: "hole",
      name: "hole",
      kind: "cut",
      plane: "XY",
      referenceId: "base",
      offset: 0,
      amount: 10,
      sketch: { type: "circle", x: 12, y: 0, w: 4, h: 4, radius: 0 },
    },
    {
      id: "mirror",
      name: "mirror",
      kind: "mirror",
      sourceId: "hole",
      plane: "YZ",
      referenceId: "world",
      offset: 0,
    },
  ];
  const a = buildPart(m);
  try {
    near(a.info.volume, 24000 - 2 * Math.PI * 4 * 10);
  } finally {
    a.shape.delete();
  }
  m.operations[1] = {
    id: "pattern",
    name: "circular",
    kind: "pattern",
    sourceId: "hole",
    mode: "circular",
    axis: "Z",
    count: 4,
    angle: 90,
    spacing: 10,
    center: [0, 0, 0],
  };
  const b = buildPart(m);
  try {
    near(b.info.volume, 24000 - 4 * Math.PI * 4 * 10);
  } finally {
    b.shape.delete();
  }
});
test("failure names exact feature and leaves input and independent last valid solid intact", () => {
  const good = buildPart(bracketExample()),
    bad = bracketExample();
  bad.operations[0].sketch.x = 150;
  const before = JSON.stringify(bad);
  try {
    assert.throws(
      () => buildPart(bad),
      (e) => e.featureId === "upright",
    );
    assert.equal(JSON.stringify(bad), before);
    assert.ok(good.shape.mesh().vertices.length > 0);
  } finally {
    good.shape.delete();
  }
});
test("excessive fillet fails with failing ID; dangling references and bounds rejected", () => {
  const m = shellExample();
  m.operations[1].radius = 30;
  assert.throws(
    () => buildPart(m),
    (e) => e.featureId === "fillet",
  );
  m.operations[1].referenceId = "shell";
  m.operations.shift();
  assert.throws(() => validatePart(m), /선행/);
  const over = emptyPart();
  over.base.height = 81;
  assert.throws(() => validatePart(over), /높이/);
});
test("v3 round trip and old E1 import retain source IDs without sharing storage", () => {
  const m = bracketExample();
  assert.deepEqual(importPart(JSON.stringify(m)), m);
  assert.notEqual(partKey("901:1"), "form-studio-design-v1:901:1");
  const old = readFileSync(
    new URL(
      "../examples/cnc_E1_2026-10-06_L-slot-arc.form.json",
      import.meta.url,
    ),
    "utf8",
  );
  const result = importPart(old);
  assert.equal(result.version, 3);
  assert.equal(result.operations.length, JSON.parse(old).features.length);
  const built = buildPart(result);
  built.shape.delete();
});
test("horizontal vertical length and fixed point solve together without mutating input", () => {
  const s = sketch();
  s.constraints = [
    { type: "horizontal", a: "a", b: "b" },
    { type: "vertical", a: "b", b: "c" },
    { type: "length", a: "a", b: "b", value: 20 },
    { type: "fix", a: "a", target: [-10, -10] },
  ];
  const before = JSON.stringify(s),
    solved = solveSketch(s);
  assert.equal(JSON.stringify(s), before);
  near(solved.sketch.nodes[1].point[1], -10);
  near(solved.sketch.nodes[1].point[0], 10);
  near(solved.sketch.nodes[2].point[0], 10);
  assert.ok(solved.residual < 1e-4);
});
test("contradictory constraints and duplicates fail without input mutation", () => {
  const s = sketch();
  s.constraints = [
    { type: "fix", a: "a", target: [0, 0] },
    { type: "fix", a: "b", target: [10, 10] },
    { type: "horizontal", a: "a", b: "b" },
  ];
  const before = JSON.stringify(s);
  assert.throws(() => solveSketch(s), /과구속/);
  assert.equal(JSON.stringify(s), before);
  s.constraints = [
    { type: "horizontal", a: "a", b: "b" },
    { type: "horizontal", a: "b", b: "a" },
  ];
  assert.throws(() => solveSketch(s), /중복/);
});
test("arc radius constraint uses true three-point arc", () => {
  const s = sketch();
  s.nodes[0].arcVia = [0, -20];
  s.constraints = [{ type: "radius", a: "a", value: 12 }];
  const solved = solveSketch(s);
  assert.ok(solved.residual < 1e-4);
  assert.ok(solved.sketch.nodes[0].arcVia);
});
test("STEP and binary STL contain actual BRep export", async () => {
  const result = buildPart(bracketExample());
  try {
    const step = await result.shape.blobSTEP().text();
    assert.match(step, /ISO-10303-21/);
    assert.match(step, /MANIFOLD_SOLID_BREP/);
    const bytes = await result.shape.blobSTL({ binary: true }).arrayBuffer();
    const count = new DataView(bytes).getUint32(80, true);
    assert.equal(bytes.byteLength, 84 + 50 * count);
    assert.ok(count > 100);
  } finally {
    result.shape.delete();
  }
});

test("constrained free profile creates a real extrusion", () => {
  const m = emptyPart();
  const s = sketch();
  s.constraints = [{ type: "horizontal", a: "a", b: "b" }];
  m.base = { ...solveSketch(s).sketch, id: "base", height: 10, radius: 0 };
  const a = buildPart(m);
  try {
    near(a.info.volume, 3900);
  } finally {
    a.shape.delete();
  }
});

test("mixed line and arc profile closes into BRep", () => {
  const m = emptyPart();
  const s = sketch();
  s.nodes[0].arcVia = [0, -15];
  s.nodes[1].point = [10, -10];
  s.radius = 0;
  const solved = solveSketch({
    ...s,
    constraints: [{ type: "radius", a: "a", value: 12.5 }],
  });
  m.base = { ...solved.sketch, id: "base", height: 10 };
  const x = buildPart(m);
  try {
    assert.ok(x.info.volume > 4000);
  } finally {
    x.shape.delete();
  }
});
