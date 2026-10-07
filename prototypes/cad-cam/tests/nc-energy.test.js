import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { parseNC } from "../src/nc-parser.js";
import { analyzeStock } from "../src/nc-stock.js";
import {
  energyPlan,
  analyzeEnergy,
  movementTime,
  stopTime,
  ENERGY_MODEL,
} from "../src/nc-energy.js";
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);
function nc(text = "T1\nM6\nS1000\nM3\nG0 X10\nG1 Z5 F60\nG1 X15\nG4 P2\nM2") {
  const n = parseNC(text, {
    confirmed: true,
    unit: "mm",
    initial: [-3, 10, 10],
  });
  n.sourceHash = createHash("sha256").update(text).digest("hex");
  return n;
}
function stubStock(n) {
  return {
    ncSourceHash: n.sourceHash,
    rapidContactLines: [],
    remaining: 0,
    overcut: 0,
    setup: { initialTool: 1 },
    segments: n.segments.map((s) => ({
      id: s.id,
      line: s.line,
      removedMm3: s.code === "G0" ? 0 : 1,
    })),
  };
}
function model(n, s) {
  return {
    version: ENERGY_MODEL,
    machine: "synthetic",
    source: "independent test",
    provenance: "assumption",
    confirmed: true,
    wholeMachineConfirmed: true,
    axes: [0, 1, 2].map(() => ({ velocity: 3000, acceleration: 500 })),
    states: Object.fromEntries(
      energyPlan(n, s).states.map((s) => [
        s.key,
        { min: 2, max: 3, seconds: s.eventTime ? 3 : undefined },
      ]),
    ),
  };
}
test("independent triangular/trapezoidal closed forms and exact zero move", () => {
  near(stopTime(1, 10, 4), 1);
  near(stopTime(100, 10, 10), 11);
  near(movementTime({ length: 0 }, []).seconds, 0);
  assert.throws(() => stopTime(1, 0, 1));
});
test("linear diagonal axis limits and XY arc acceleration budget are independent", () => {
  const s = {
    length: 100,
    from: [0, 0, 0],
    to: [60, 80, 0],
    code: "G0",
    state: {},
  };
  const t = movementTime(s, [
    { velocity: 60, acceleration: 6 },
    { velocity: 120, acceleration: 8 },
    {},
  ]);
  near(t.seconds, 60 + 1 / 6);
  near(t.velocity, 5 / 3);
  near(t.acceleration, 10);
  const a = movementTime(
    {
      length: Math.PI * 10,
      arc: { radius: 10 },
      code: "G2",
      state: { feed: 600 },
    },
    [
      { velocity: 600, acceleration: 4 },
      { velocity: 600, acceleration: 4 },
      {},
    ],
  );
  near(a.velocity, Math.sqrt(20));
  near(a.acceleration, 2);
  near(a.seconds, (Math.PI * 10) / Math.sqrt(20) + Math.sqrt(20) / 2);
});
test("kW-second to kWh ledger sum, whole power model, all event time once", () => {
  const n = nc(),
    s = stubStock(n),
    m = model(n, s),
    a = analyzeEnergy(n, s, m);
  const expectedSeconds =
    3 +
    3 +
    (13 / 50 + 50 / 500) +
    (5 / 1 + 1 / 500) +
    (5 / 1 + 1 / 500) +
    2 +
    3;
  near(a.totalTime, expectedSeconds);
  near(a.totalEnergy[0], (2 * expectedSeconds) / 3600);
  near(a.totalEnergy[1], (3 * expectedSeconds) / 3600);
  near(
    a.rows.reduce((sum, r) => sum + r.energy[0], 0),
    a.totalEnergy[0],
  );
  near(a.averagePower[0], 2);
  near(a.averagePower[1], 3);
  assert.equal(a.rows.filter((r) => r.kind === "end").length, 1);
});
test("tool exchange/end absorb spindle/coolant automatic events without duplicates", () => {
  const n = nc("T1\nM6\nS1000 M3\nM8\nG0 X10\nT2\nM6\nS500 M4\nG1 Z5 F60\nM30"),
    s = stubStock(n),
    a = analyzeEnergy(n, s, model(n, s));
  const toolLine = n.blocks.find((b) => b.raw === "M6" && b.line > 2).line;
  assert.deepEqual(
    a.rows.filter((r) => r.line === toolLine).map((r) => r.kind),
    ["tool-change"],
  );
  assert.deepEqual(
    a.rows
      .filter((r) => r.line === n.blocks.find((b) => b.raw === "M30").line)
      .map((r) => r.kind),
    ["end"],
  );
  assert.equal(a.rows.filter((r) => r.kind === "spindle").length, 2);
  assert.equal(a.rows.filter((r) => r.kind === "coolant").length, 1);
});
test("different rpm/coolant/tool split states; redundant spindle and off-speed changes add no time", () => {
  const n = nc(
      "S1000\nT1\nM6\nM3\nM3\nG1 X1 F60\nS500\nG1 X2\nM8\nG1 X3\nT2\nM6\nM3\nG1 X4\nM2",
    ),
    s = stubStock(n),
    p = energyPlan(n, s);
  assert.equal(p.rows.filter((r) => r.kind === "spindle").length, 3);
  assert.equal(p.states.filter((r) => r.kind === "removal").length, 4);
});
test("unknown inputs propagate null independently, never silently zero, known subtotals explicit", () => {
  const n = nc(),
    s = stubStock(n),
    m = model(n, s),
    p = energyPlan(n, s);
  m.states[p.states.find((v) => v.kind === "removal").key].min = null;
  let a = analyzeEnergy(n, s, m);
  assert.ok(a.totalTime > 0);
  assert.equal(a.totalEnergy, null);
  assert.ok(a.knownEnergy[0] > 0);
  m.axes[0].velocity = null;
  a = analyzeEnergy(n, s, m);
  assert.equal(a.totalTime, null);
  assert.equal(a.totalEnergy, null);
  assert.ok(a.issues.some((i) => i.reasons.includes("X 속도/가속도 미정")));
});
test("explicit zero event seconds and zero kW differ from missing", () => {
  const n = nc(),
    s = stubStock(n),
    m = model(n, s);
  for (const k of Object.keys(m.states))
    m.states[k] = { min: null, max: null, seconds: 0 };
  const a = analyzeEnergy(n, s, m);
  assert.ok(
    a.rows
      .filter((r) => r.eventTime)
      .every((r) => r.seconds === 0 && r.energy[0] === 0),
  );
  assert.equal(a.totalEnergy, null);
  for (const k of Object.keys(m.states))
    m.states[k] = { min: 0, max: 0, seconds: 0 };
  near(analyzeEnergy(n, s, m).totalEnergy[0], 0);
});
test("bad ranges, nonfinite/negative time, missing provenance confirmation are blocked", () => {
  const n = nc(),
    s = stubStock(n);
  for (const mutate of [
    (m) => (m.confirmed = false),
    (m) => (m.wholeMachineConfirmed = false),
    (m) => (m.source = ""),
    (m) => (m.states[Object.keys(m.states)[0]].seconds = -1),
    (m) => (m.states[Object.keys(m.states)[0]].min = Infinity),
    (m) => (m.states[Object.keys(m.states)[0]].max = 1),
    (m) => (m.axes[0].acceleration = 0),
  ]) {
    const m = model(n, s);
    mutate(m);
    assert.throws(() => analyzeEnergy(n, s, m));
  }
});
test("current hash/geometry association, unsupported NC, rapid contact, missing termination block full energy", () => {
  const n = nc(),
    s = stubStock(n);
  assert.throws(() => energyPlan(n, { ...s, ncSourceHash: "stale" }));
  assert.throws(() => energyPlan(n, { ...s, rapidContactLines: [1] }));
  assert.throws(() => energyPlan({ ...n, complete: false }, s));
  assert.throws(() => energyPlan({ ...n, ended: false }, s));
  const bad = structuredClone(s);
  bad.segments[0].line = 99;
  assert.throws(() => energyPlan(n, bad));
  const mixed = nc("T1\nM6\nS1000 M3\nG1 X10 S500 F60\nM2");
  assert.throws(() => energyPlan(mixed, stubStock(mixed)), /혼합/);
});
test("measured input stays uncalibrated; separate holdout comparison never alters prediction", () => {
  const n = nc(),
    s = stubStock(n),
    m = model(n, s);
  m.provenance = "measured-input";
  assert.throws(() => analyzeEnergy(n, s, m));
  m.date = "2026-10-08";
  m.conditions = "synthetic T1";
  const a = analyzeEnergy(n, s, m);
  m.validation = {
    seconds: a.totalTime * 2,
    kWh: a.totalEnergy[0] * 2,
    source: "separate synthetic holdout",
  };
  const b = analyzeEnergy(n, s, m);
  near(b.comparison.timeDifferencePercent, -50);
  near(b.comparison.energyDifferencePercent[0], -50);
  assert.deepEqual(a.totalEnergy, b.totalEnergy);
  assert.equal(b.model.provenance, "measured-input");
});
test("inch feed time uses normalized mm/min, no extra 25.4 scaling", () => {
  const n = nc("G20\nT1\nM6\nS1000 M3\nG1 X1 F60\nM2");
  const move = n.segments[0];
  near(move.state.feed, 1524);
  const t = movementTime(move, [
    { velocity: 6000, acceleration: 1000 },
    {},
    {},
  ]);
  near(t.seconds, move.length / 25.4 + 25.4 / 1000);
});
test("actual stock removal ledger matches total and distinguishes air/zero-removal without guessing G1", () => {
  const n = nc(),
    mesh = {
      vertices: [
        0, 0, 0, 20, 0, 0, 20, 20, 0, 0, 20, 0, 0, 0, 5, 20, 0, 5, 20, 20, 5, 0,
        20, 5,
      ],
      triangles: [
        0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 1, 2, 6, 1, 6, 5,
        2, 3, 7, 2, 7, 6, 3, 0, 4, 3, 4, 7,
      ],
    };
  const s = analyzeStock(
    n,
    { solid: true, volume: 2000, mesh },
    {
      stock: { min: [0, 0, 0], size: [20, 20, 8], material: "synthetic" },
      tools: [{ t: 1, type: "flat", diameter: 4, flute: 15 }],
      initialTool: 1,
      pitch: 1,
      transform: { angle: 0, offset: [0, 0, 0] },
      aligned: true,
      topSurfaceConfirmed: true,
    },
  );
  near(
    s.segments.reduce((a, r) => a + r.removedMm3, 0),
    s.removed,
  );
  assert.equal(s.ncSourceHash, n.sourceHash);
  assert.equal(
    energyPlan(n, s).rows.filter((r) => r.kind === "removal").length,
    2,
  );
});
test("distinct-state cap bounds user input table", () => {
  const lines = ["T1", "M6", "S1000 M3"];
  for (let i = 0; i < 120; i++) lines.push(`S${1000 + i}`, `G1 X${i % 2} F60`);
  lines.push("M2");
  const n = nc(lines.join("\n"));
  assert.throws(() => energyPlan(n, stubStock(n)), /200종/);
});
test(
  "actual energy worker transports null totals, tagged success and guarded errors",
  { timeout: 5000 },
  async () => {
    const { Worker } = await import("node:worker_threads");
    const url = new URL("../src/nc-energy.worker.js", import.meta.url).href;
    const w = new Worker(
      `const {parentPort}=require('node:worker_threads');globalThis.self={postMessage:data=>parentPort.postMessage(data)};parentPort.on('message',data=>self.onmessage({data}));import(${JSON.stringify(url)}).then(()=>parentPort.postMessage({ready:true}));`,
      { eval: true },
    );
    try {
      await new Promise((resolve, reject) => {
        w.once("message", resolve);
        w.once("error", reject);
      });
      const request = (data) =>
        new Promise((resolve, reject) => {
          w.once("message", resolve);
          w.once("error", reject);
          w.postMessage(data);
        });
      const n = nc(),
        s = stubStock(n),
        m = model(n, s);
      m.axes[0].velocity = null;
      let reply = await request({ revision: 41, nc: n, stock: s, model: m });
      assert.equal(reply.revision, 41);
      assert.equal(reply.analysis.totalTime, null);
      assert.equal(reply.analysis.totalEnergy, null);
      reply = await request({
        revision: 42,
        nc: { ...n, complete: false },
        stock: s,
        model: m,
      });
      assert.equal(reply.revision, 42);
      assert.ok(reply.error);
      assert.equal(reply.analysis, undefined);
    } finally {
      await w.terminate();
    }
  },
);
test("invalid measured date cannot masquerade as actual measurement provenance", () => {
  const n = nc(),
    s = stubStock(n),
    m = model(n, s);
  m.provenance = "measured-input";
  m.date = "2026-02-31";
  m.conditions = "synthetic";
  assert.throws(() => analyzeEnergy(n, s, m), /측정/);
});
test("compact worker transport omits raw source/points and preserves all computed totals", async () => {
  const { compactEnergyNC } = await import("../src/nc-energy.js");
  const n = nc(),
    s = stubStock(n),
    m = model(n, s),
    packed = compactEnergyNC({ ...n, originalText: "synthetic source" });
  assert.equal(packed.originalText, undefined);
  assert.ok(packed.segments.every((s) => s.points === undefined));
  assert.deepEqual(
    analyzeEnergy(packed, s, m).totalEnergy,
    analyzeEnergy(n, s, m).totalEnergy,
  );
  assert.equal(
    JSON.parse(JSON.stringify(analyzeEnergy(packed, s, m))).totalTime,
    analyzeEnergy(n, s, m).totalTime,
  );
});
