import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import OC from "replicad-opencascadejs";
import { setKernel, buildPart } from "../src/part-kernel.js";
import { emptyPart, validatePart } from "../src/part-model.js";
import {
  directReferences,
  resolveEdge,
  checkFace,
} from "../src/part-references.js";
import { asProfile } from "../src/sketch-edit.js";
setKernel(
  await OC({
    wasmBinary: readFileSync(
      new URL(import.meta.resolve("replicad-opencascadejs/wasm")),
    ),
  }),
);
const near = (a, b) => assert.ok(Math.abs(a - b) < 0.001, `${a} != ${b}`);
function refs(m) {
  const result = buildPart(m);
  try {
    return directReferences(result.shape);
  } finally {
    result.shape.delete();
  }
}
test("real kernel analytic profiles and internal hole subtract exact cylinder volume", () => {
  const m = emptyPart();
  m.base = asProfile(m.base);
  m.base.holes = [
    asProfile({ type: "circle", x: 0, y: 0, w: 8, h: 8, radius: 0 }),
  ];
  const result = buildPart(m);
  try {
    near(result.info.volume, 60 * 40 * 10 - Math.PI * 16 * 10);
  } finally {
    result.shape.delete();
  }
});
test("kernel semantic edge and face descriptors match one actual entity", () => {
  const m = emptyPart(),
    result = buildPart(m);
  try {
    const r = directReferences(result.shape);
    assert.equal(r.edges.length, 12);
    assert.equal(r.faces.length, 6);
    const edge = resolveEdge(result.shape, r.edges[0]);
    edge.delete();
    for (const face of r.faces) checkFace(result.shape, face);
    const old = structuredClone(r.edges[0]);
    old.a[0] += 0.1;
    assert.throws(() => resolveEdge(result.shape, old), /参照|참조/);
  } finally {
    result.shape.delete();
  }
});
test("one local chamfer removes analytic triangular prism and upstream edit invalidates reference", () => {
  const m = emptyPart(),
    r = refs(m),
    edge = r.edges.find((e) => Math.abs(e.length - 10) < 0.001);
  m.operations = [
    {
      id: "chamfer",
      name: "국소 모따기",
      kind: "chamfer",
      plane: "XY",
      offset: 0,
      referenceId: "base",
      scope: "edge",
      radius: 1,
      edgeReference: edge,
    },
  ];
  validatePart(m);
  const result = buildPart(m);
  try {
    near(result.info.volume, 24000 - 5);
    assert.ok(result.shape.mesh().triangles.length);
  } finally {
    result.shape.delete();
  }
  m.base.w += 1;
  assert.throws(
    () => buildPart(m),
    (e) => e.featureId === "chamfer" && /참조/.test(e.message),
  );
});
test("local fillet removes only one edge; unaffected reference survives independent edit", () => {
  const m = emptyPart(),
    r = refs(m),
    edge = r.edges.find((e) => Math.abs(e.length - 10) < 0.001 && e.a[0] < 0);
  m.operations = [
    {
      id: "round",
      name: "국소 필렛",
      kind: "fillet",
      plane: "XY",
      offset: 0,
      referenceId: "base",
      scope: "edge",
      radius: 1,
      edgeReference: edge,
    },
  ];
  const result = buildPart(m);
  try {
    near(result.info.volume, 24000 - (1 - Math.PI / 4) * 10);
  } finally {
    result.shape.delete();
  }
  m.base.height += 1;
  assert.throws(() => buildPart(m), /참조/);
});
test("selected plane creates cut on outward normal and stale face stops rebuild", () => {
  const m = emptyPart(),
    r = refs(m),
    face = r.faces.find((f) => f.plane === "YZ" && f.sign === 1);
  m.operations = [
    {
      id: "side",
      name: "면 기반 구멍",
      kind: "cut",
      plane: face.plane,
      referenceId: "base",
      offset: 0,
      supportFace: face,
      amount: 10,
      sketch: { type: "circle", x: 0, y: 5, w: 4, h: 4, radius: 0, angle: 0 },
    },
  ];
  const result = buildPart(m);
  try {
    near(result.info.volume, 24000 - Math.PI * 4 * 10);
  } finally {
    result.shape.delete();
  }
  m.base.h += 1;
  assert.throws(
    () => buildPart(m),
    (e) => e.featureId === "side" && /작업면 참조/.test(e.message),
  );
});
test("negative face extrudes outward when adding material and reference file roundtrips", () => {
  const m = emptyPart(),
    face = refs(m).faces.find((f) => f.plane === "YZ" && f.sign === -1);
  m.operations = [
    {
      id: "boss",
      name: "음방향 돌출",
      kind: "add",
      plane: "YZ",
      referenceId: "base",
      offset: 0,
      supportFace: face,
      amount: 5,
      sketch: { type: "rect", x: 0, y: 5, w: 10, h: 4, radius: 0, angle: 0 },
    },
  ];
  validatePart(JSON.parse(JSON.stringify(m)));
  const result = buildPart(m);
  try {
    near(result.info.volume, 24200);
    near(result.info.bounds[0][0], -35);
  } finally {
    result.shape.delete();
  }
});

test("local direct edit STEP roundtrip retains solid volume", async () => {
  const r = await import("replicad"),
    m = emptyPart(),
    edge = refs(m).edges.find((e) => Math.abs(e.length - 10) < 0.001);
  m.operations = [
    {
      id: "chamfer",
      name: "roundtrip",
      kind: "chamfer",
      plane: "XY",
      offset: 0,
      referenceId: "base",
      scope: "edge",
      radius: 1,
      edgeReference: edge,
    },
  ];
  const original = buildPart(m);
  let imported;
  try {
    const step = original.shape.blobSTEP();
    assert.ok(step.size > 5000);
    imported = await r.importSTEP(step);
    const p = r.measureShapeVolumeProperties(imported);
    try {
      near(p.volume, 23995);
    } finally {
      p.delete();
    }
    const stl = await original.shape
        .blobSTL({ binary: true, tolerance: 0.05 })
        .arrayBuffer(),
      view = new DataView(stl),
      count = view.getUint32(80, true);
    assert.ok(count >= 12);
    assert.equal(stl.byteLength, 84 + count * 50);
    let volume = 0;
    for (let i = 0; i < count; i++) {
      const pts = Array.from({ length: 3 }, (_, j) =>
          Array.from({ length: 3 }, (_, k) =>
            view.getFloat32(84 + i * 50 + 12 + j * 12 + k * 4, true),
          ),
        ),
        [a, b, c] = pts;
      volume +=
        (a[0] * (b[1] * c[2] - b[2] * c[1]) +
          a[1] * (b[2] * c[0] - b[0] * c[2]) +
          a[2] * (b[0] * c[1] - b[1] * c[0])) /
        6;
    }
    near(Math.abs(volume), 23995);
  } finally {
    original.shape.delete();
    imported?.delete();
  }
});

test("equal area and bounds do not hide a moved inner face boundary", () => {
  const m = emptyPart();
  m.operations = [
    {
      id: "hole",
      name: "inner",
      kind: "cut",
      plane: "XY",
      referenceId: "base",
      offset: 0,
      amount: 5,
      sketch: { type: "circle", x: 0, y: 0, w: 4, h: 4, radius: 0, angle: 0 },
    },
  ];
  const face = refs(m).faces.find(
    (f) =>
      f.plane === "XY" && f.sign === 1 && Math.abs(f.position - 10) < 0.001,
  );
  m.operations.push({
    id: "boss",
    name: "supported",
    kind: "add",
    plane: "XY",
    referenceId: "hole",
    offset: 0,
    amount: 2,
    supportFace: face,
    sketch: { type: "rect", x: -20, y: 0, w: 4, h: 4, radius: 0, angle: 0 },
  });
  const result = buildPart(m);
  result.shape.delete();
  m.operations[0].sketch.x = 5;
  assert.throws(
    () => buildPart(m),
    (e) => e.featureId === "boss" && /작업면 참조/.test(e.message),
  );
});
