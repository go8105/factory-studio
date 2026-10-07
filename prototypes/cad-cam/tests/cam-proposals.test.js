import test from "node:test";
import assert from "node:assert/strict";
import Module from "manifold-3d";
import { sampleModel, defaultTool, simulationAt } from "../src/model.js";
import {
  generateKernelPaths,
  generatePathProposals,
  validateProposal,
  pathMetrics,
} from "../src/cam.js";
import { syncProfile } from "../src/profile.js";
const kernel = await Module();
kernel.setup();
const C = kernel.CrossSection;
const tool = defaultTool();
const clone = (x) => structuredClone(x);
function splitModel() {
  const f = syncProfile({
    id: "split",
    name: "좁은 연결부",
    type: "profile",
    x: 0,
    y: 0,
    w: 60,
    h: 40,
    radius: 0,
    depth: 4,
    closed: true,
    nodes: [
      [-30, -20],
      [-10, -20],
      [-10, -1],
      [10, -1],
      [10, -20],
      [30, -20],
      [30, 20],
      [10, 20],
      [10, 1],
      [-10, 1],
      [-10, 20],
      [-30, 20],
    ].map((point, i) => ({ id: `n${i}`, point })),
  });
  return { ...sampleModel(), features: [f] };
}
test("split pockets preserve directed cuts, finishes, depth order and full grid; reduce only air moves", () => {
  const m = splitModel(),
    result = generatePathProposals(m, tool, C);
  assert.equal(result.candidates.length, 2);
  assert.equal(result.recommendedId, "nearest");
  const [a, b] = result.candidates;
  assert.deepEqual(generateKernelPaths(m, tool, C), a.path);
  assert.equal(validateProposal(m, a.path, b.path), true);
  assert.deepEqual(
    simulationAt(m, a.path, 1).grid.heights,
    simulationAt(m, b.path, 1).grid.heights,
  );
  assert.ok(b.metrics.rapidLength < a.metrics.rapidLength);
  assert.ok(Math.abs(a.metrics.cutLength - b.metrics.cutLength) < 1e-7);
  assert.equal(b.metrics.energyKWh, null);
  assert.equal(b.metrics.energySavingPercent, null);
  assert.equal(a.metrics.residualVolume, b.metrics.residualVolume);
  console.log(
    `split example: air ${a.metrics.rapidLength.toFixed(1)} -> ${b.metrics.rapidLength.toFixed(1)} mm; seconds ${a.metrics.seconds.toFixed(1)} -> ${b.metrics.seconds.toFixed(1)}`,
  );
});
test("sample includes baseline and recommendation never worsens air distance or time", () => {
  const m = sampleModel(),
    r = generatePathProposals(m, tool, C);
  const chosen = r.candidates.find((c) => c.id === r.recommendedId);
  assert.ok(
    chosen.metrics.rapidLength <= r.candidates[0].metrics.rapidLength + 1e-7,
  );
  assert.ok(chosen.metrics.seconds <= r.candidates[0].metrics.seconds + 1e-7);
  const p = chosen.path;
  let cut = 0,
    air = 0;
  for (let i = 1; i < p.points.length; i++) {
    const a = p.points[i - 1],
      b = p.points[i],
      d = Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2 + (b.z - a.z) ** 2);
    if (b.cut) cut += d;
    else air += d;
  }
  assert.equal(pathMetrics(p).rapidLength, air);
  assert.equal(pathMetrics(p).cutLength, cut);
  assert.ok(Math.abs(pathMetrics(p).seconds - p.seconds) < 1e-7);
});
test("quality/safety gate rejects shorter but missing, reversed, changed-tool or unsafe path", () => {
  const m = splitModel(),
    base = generateKernelPaths(m, tool, C);
  for (const mutate of [
    (p) => p.points.splice(2, 1),
    (p) => p.tool.feed++,
    (p) => p.finishGroups.pop(),
    (p) => {
      p.points[1].z = 0;
    },
    (p) => {
      const i = p.points.findIndex(
        (p, i) => i > 0 && p.cut && p.x !== base.points[i - 1].x,
      );
      p.points[i].x += 0.1;
    },
  ]) {
    const p = clone(base);
    mutate(p);
    assert.throws(() => validateProposal(m, base, p));
  }
});
test("bounded groups keep baseline; oversized tool is rejected", () => {
  const m = sampleModel(),
    small = { ...tool, diameter: 0.5, stepOver: 10, stepDown: 20 };
  const r = generatePathProposals(m, small, C);
  assert.equal(r.candidates.length, 1);
  assert.match(r.reason, /256/);
  assert.throws(() =>
    generatePathProposals(splitModel(), { ...tool, diameter: 40 }, C),
  );
});

test("independent safety oracle catches a low rapid excursion with identical cutting signature", () => {
  const m = sampleModel(),
    base = generateKernelPaths(m, tool, C),
    p = clone(base);
  const a = p.points[0];
  p.points.splice(
    1,
    0,
    { ...a, z: 1 },
    { ...a, x: a.x + 1, z: 1 },
    { ...a, z: 1 },
    { ...a },
  );
  assert.throws(() => validateProposal(m, base, p), /안전 높이/);
});
test("finishing must remain last even if the same directed cutting strokes are preserved", () => {
  const m = sampleModel(),
    base = generateKernelPaths(m, tool, C),
    p = clone(base);
  const strokes = [];
  for (let i = 1; i < base.points.length; i++) {
    if (!base.points[i].cut) continue;
    const stroke = [base.points[i - 1]];
    while (i < base.points.length && base.points[i].cut)
      stroke.push(base.points[i++]);
    strokes.push(stroke);
  }
  const firstGroup = strokes.filter(
    (s) => s[1].feature === strokes[0][1].feature && s[1].z === strokes[0][1].z,
  );
  const last = firstGroup.length - 1;
  [strokes[0], strokes[last]] = [strokes[last], strokes[0]];
  p.points = [];
  for (const stroke of strokes) {
    const previous = p.points.at(-1);
    if (previous)
      p.points.push({
        ...previous,
        z: m.stock.height + tool.safeHeight,
        cut: false,
      });
    p.points.push(...stroke);
  }
  assert.throws(
    () => validateProposal(m, base, p),
    /마무리 윤곽의 마지막 실행 순서/,
  );
});
