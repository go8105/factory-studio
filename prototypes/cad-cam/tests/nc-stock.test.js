import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import OC from "replicad-opencascadejs";
import * as r from "replicad";
import { readReference } from "../src/nc-step.js";
import { analyzeStock, transformMesh, meshBounds } from "../src/nc-stock.js";
import { parseNC } from "../src/nc-parser.js";
r.setOC(
  await OC({
    wasmBinary: readFileSync(
      new URL(import.meta.resolve("replicad-opencascadejs/wasm")),
    ),
  }),
);
const box = r
  .drawRectangle(20, 20)
  .translate(10, 10)
  .sketchOnPlane("XY")
  .extrude(5);
const reference = await readReference(box.blobSTEP());
box.delete();
const setup = () => ({
  stock: { min: [0, 0, 0], size: [20, 20, 8], material: "synthetic" },
  tools: [{ t: 1, type: "flat", diameter: 4, flute: 15, h: 7, d: 9 }],
  initialTool: 1,
  pitch: 1,
  transform: { offset: [0, 0, 0], angle: 0 },
  aligned: true,
  topSurfaceConfirmed: true,
});
function nc(z = 5, tail = "") {
  let lines = ["T1", "M6", "S1000", "M3", "G0 X-3 Y-1 Z10", `G1 Z${z} F100`];
  for (let y = -1; y <= 21; y += 2)
    lines.push(`G1 Y${y}`, `X${((y + 1) / 2) % 2 === 0 ? 23 : -3}`);
  lines.push(tail, "M2");
  return parseNC(lines.join("\n"), {
    unit: "mm",
    initial: [-3, -1, 10],
    confirmed: true,
  });
}
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-7, `${a} != ${b}`);
test("actual STEP Solid roundtrip preserves analytic bounds and volume", () => {
  near(reference.volume, 2000);
  assert.deepEqual(
    meshBounds(reference.mesh).map((a) => a.map((v) => Math.round(v))),
    [
      [0, 0, 0],
      [20, 20, 5],
    ],
  );
});
test("full face raster agrees with independent box removal volume; no remaining or gouge", () => {
  const a = analyzeStock(nc(), reference, setup());
  near(a.removed, 20 * 20 * 3);
  near(a.remaining, 0);
  near(a.overcut, 0);
  assert.deepEqual(a.rapidContactLines, []);
  assert.equal(a.energyKWh, null);
});
test("under-depth and over-depth independently match box layer volumes", () => {
  let a = analyzeStock(nc(6), reference, setup());
  near(a.remaining, 400);
  near(a.overcut, 0);
  near(a.maxRemaining, 1);
  a = analyzeStock(nc(4), reference, setup());
  near(a.overcut, 400);
  near(a.maxOvercut, 1);
});
test("rapid contact observes current stock; never removes material", () => {
  const a = analyzeStock(nc(5, "G0 X10 Y10\nZ4"), reference, setup());
  near(a.removed, 1200);
  assert.equal(a.rapidContactLines.length, 1);
  const line = a.rapidContactLines[0];
  assert.equal(nc(5, "G0 X10 Y10\nZ4").blocks[line - 1].raw, "Z4");
});
test("alignment transform rotates then translates; original NC remains unchanged", () => {
  const m = transformMesh(
    { vertices: [1, 0, 2], triangles: [] },
    { offset: [10, 20, 30], angle: 90 },
  );
  near(m.vertices[0], 10);
  near(m.vertices[1], 21);
  near(m.vertices[2], 32);
  const n = nc(),
    before = JSON.stringify(n);
  analyzeStock(n, reference, setup());
  assert.equal(JSON.stringify(n), before);
});
test("unconfirmed, incomplete, unmapped, unpowered, flute short, outside target and cap block comparison", () => {
  for (const mutate of [
    (s) => (s.aligned = false),
    (s) => (s.topSurfaceConfirmed = false),
    (s) => (s.tools[0].t = 2),
    (s) => (s.tools[0].type = "ball"),
    (s) => (s.tools[0].flute = 1),
    (s) => (s.transform.offset[0] = 1),
    (s) => (s.pitch = 0.01),
    (s) => (s.stock.size = [10000, 10000, 8]),
  ]) {
    const s = setup();
    mutate(s);
    assert.throws(() => analyzeStock(nc(), reference, s));
  }
  assert.throws(() =>
    analyzeStock({ ...nc(), complete: false }, reference, setup()),
  );
  assert.throws(
    () =>
      analyzeStock(
        nc().segments.length
          ? parseNC("T1\nM6\nG1 Z5 F100", {
              unit: "mm",
              initial: [0, 0, 10],
              confirmed: true,
            })
          : null,
        reference,
        setup(),
      ),
    /주축/,
  );
});
test("floating and sloped STEP are blocked; no fabricated shape comparison", async () => {
  for (const drawing of [
    () => r.drawRectangle(10, 10).sketchOnPlane("XY", 2).extrude(3),
    () =>
      r
        .drawRectangle(10, 10)
        .sketchOnPlane("XY")
        .extrude(3)
        .rotate(10, [0, 0, 0], [1, 0, 0])
        .translate([0, 0, 2]),
  ]) {
    const b = drawing().translate([10, 10, 0]);
    try {
      const ref = await readReference(b.blobSTEP());
      assert.throws(() => analyzeStock(nc(), ref, setup()));
    } finally {
      b.delete();
    }
  }
});
test("malformed STEP and multi-solid assembly are rejected", async () => {
  await assert.rejects(readReference(new Blob(["not a STEP"])));
  const a = r.drawRectangle(2, 2).sketchOnPlane("XY").extrude(2),
    b = a.clone().translate([5, 0, 0]),
    c = r.makeCompound([a, b]);
  try {
    await assert.rejects(readReference(c.blobSTEP()), /단일 Solid/);
  } finally {
    c.delete();
    a.delete();
    b.delete();
  }
});
test("OCCT STEP unit conversion yields mm without user guessed scaling", async () => {
  const text = readFileSync(
    new URL("../examples/cnc_CAD13_2026-10-07_target.step", import.meta.url),
    "utf8",
  ).replace("SI_UNIT(.MILLI.,.METRE.)", "SI_UNIT($,.METRE.)");
  const meter = await readReference(new Blob([text]));
  const bounds = meshBounds(meter.mesh);
  near(bounds[1][0], 20000);
  near(bounds[1][2], 5000);
  assert.ok(Math.abs(meter.volume / 1e9 - 2000) < 0.001);
});
test("small target unobserved by coarse grid blocks comparison", async () => {
  const shape = r
    .drawRectangle(0.2, 0.2)
    .translate(2, 2)
    .sketchOnPlane("XY")
    .extrude(5);
  try {
    const ref = await readReference(shape.blobSTEP());
    assert.throws(
      () => analyzeStock(nc(), ref, { ...setup(), pitch: 10 }),
      /포착/,
    );
  } finally {
    shape.delete();
  }
});
test("actual path visit cap bounds repetitive full-stock sweeps", () => {
  const lines = ["T1", "M6", "S1000", "M3", "G1 Z5 F100"];
  for (let i = 0; i < 13000; i++) lines.push(`G1 X${i % 2 ? 20 : 0}`);
  const n = parseNC(lines.join("\n"), {
      unit: "mm",
      initial: [0, 0, 10],
      confirmed: true,
    }),
    s = setup();
  s.tools[0].diameter = 100;
  assert.throws(() => analyzeStock(n, reference, s), /5,000,000/);
});
