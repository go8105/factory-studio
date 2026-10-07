import { performance } from "node:perf_hooks";
import { readFileSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import OC from "replicad-opencascadejs";
import { setOC } from "replicad";
import { readReference } from "../src/nc-step.js";
import { parseNC } from "../src/nc-parser.js";
import { analyzeStock } from "../src/nc-stock.js";
import { energyPlan, analyzeEnergy, ENERGY_MODEL } from "../src/nc-energy.js";
setOC(
  await OC({
    wasmBinary: readFileSync(
      new URL(import.meta.resolve("replicad-opencascadejs/wasm")),
    ),
  }),
);
const reference = await readReference(
  new Blob([
    readFileSync(
      new URL("../examples/cnc_CAD13_2026-10-07_target.step", import.meta.url),
    ),
  ]),
);
const setup = {
  stock: { min: [0, 0, 0], size: [20, 20, 8], material: "synthetic" },
  tools: [{ t: 1, type: "flat", diameter: 4, flute: 15 }],
  initialTool: 1,
  pitch: 1,
  transform: { offset: [0, 0, 0], angle: 0 },
  aligned: true,
  topSurfaceConfirmed: true,
};
const results = [];
for (const linesCount of [1000, 10000, 50000]) {
  const lines = ["T1", "M6", "S1000", "M3"];
  for (let i = 0; i < linesCount - 5; i++) lines.push(`G1 X${i % 2} F600`);
  lines.push("M2");
  const text = lines.join("\n");
  const n = parseNC(text, {
    confirmed: true,
    unit: "mm",
    initial: [-3, -1, 10],
  });
  n.sourceHash = createHash("sha256").update(text).digest("hex");
  const t0 = performance.now(),
    stock = analyzeStock(n, reference, setup),
    t1 = performance.now();
  const plan = energyPlan(n, stock),
    model = {
      version: ENERGY_MODEL,
      machine: "synthetic air feed",
      source: "benchmark assumptions; not measured power",
      provenance: "assumption",
      confirmed: true,
      wholeMachineConfirmed: true,
      axes: [0, 1, 2].map(() => ({ velocity: 3000, acceleration: 500 })),
      states: Object.fromEntries(
        plan.states.map((s) => [s.key, { min: 2, max: 3, seconds: 2 }]),
      ),
    };
  const memory = process.memoryUsage(),
    t2 = performance.now(),
    analysis = analyzeEnergy(n, stock, model),
    t3 = performance.now(),
    after = process.memoryUsage();
  if (analysis.totalTime === null || analysis.totalEnergy === null)
    throw Error("unexpected unknown benchmark result");
  results.push({
    lines: linesCount,
    moves: n.segments.length,
    states: plan.states.length,
    rows: analysis.rows.length,
    stockMilliseconds: +(t1 - t0).toFixed(2),
    energyMilliseconds: +(t3 - t2).toFixed(2),
    energyHeapDeltaMiB: +((after.heapUsed - memory.heapUsed) / 1048576).toFixed(
      2,
    ),
    energyRSSDeltaMiB: +((after.rss - memory.rss) / 1048576).toFixed(2),
    totalSeconds: analysis.totalTime,
    energyKWh: analysis.totalEnergy,
  });
}
const report = {
  runtime: process.version,
  platform: process.platform,
  architecture: process.arch,
  date: "2026-10-08",
  limits: "Node only; no browser/GPU/peak memory/accuracy measurement",
  results,
};
await writeFile(
  new URL(
    "../../../docs/agent/assets/cad-14/energy-benchmark.json",
    import.meta.url,
  ),
  JSON.stringify(report, null, 2) + "\n",
);
console.log(JSON.stringify(report, null, 2));
