import { parseNC } from "../src/nc-parser.js";
import { energyPlan, analyzeEnergy, ENERGY_MODEL } from "../src/nc-energy.js";
import { dwellReview, compareProposals } from "../src/nc-proposals.js";
const results = [];
for (const count of [1000, 10000, 50000]) {
  const n = parseNC(
    ["T1 M6", "G1 X10 F600", ...Array(count - 3).fill("G4 P600"), "M2"].join(
      "\n",
    ),
    { unit: "mm", confirmed: true, initial: [0, 0, 10] },
  );
  n.sourceHash = "synthetic benchmark " + count;
  const s = {
    ncSourceHash: n.sourceHash,
    segments: n.segments.map((r) => ({
      id: r.id,
      line: r.line,
      removedMm3: 0,
    })),
    setup: { initialTool: 1 },
    rapidContactLines: [],
    remaining: 0,
    overcut: 0,
    maxRemaining: 0,
    maxOvercut: 0,
    targetVolumeError: 0,
  };
  const m = {
    version: ENERGY_MODEL,
    confirmed: true,
    wholeMachineConfirmed: true,
    machine: "synthetic",
    source: "benchmark",
    provenance: "assumption",
    axes: [0, 1, 2].map(() => ({ velocity: 3000, acceleration: 500 })),
    states: Object.fromEntries(
      energyPlan(n, s).states.map((r) => [
        r.key,
        { min: 1, max: 1, seconds: 1 },
      ]),
    ),
  };
  const a = analyzeEnergy(n, s, m);
  global.gc?.();
  const memory = process.memoryUsage(),
    start = performance.now();
  const list = dwellReview(n, s, a),
    listMs = performance.now() - start,
    t = performance.now();
  const report = compareProposals(n, s, a, {
    quality: {
      source: "synthetic",
      maxRemaining: 0,
      maxOvercut: 0,
      maxGridErrorPercent: 0,
    },
    riskReviewed: true,
    marginKWh: 0,
    marginSource: "synthetic zero",
    dwells: list
      .slice(0, 12)
      .map((r) => ({
        id: r.id,
        seconds: 10,
        source: "synthetic minimum",
        confirmed: true,
      })),
  });
  const after = process.memoryUsage();
  results.push({
    lines: count,
    dwells: list.length,
    candidates: report.candidates.length,
    listMilliseconds: +listMs.toFixed(2),
    comparisonMilliseconds: +(performance.now() - t).toFixed(2),
    heapDeltaMiB: +((after.heapUsed - memory.heapUsed) / 1048576).toFixed(2),
    rssDeltaMiB: +((after.rss - memory.rss) / 1048576).toFixed(2),
  });
}
console.log(
  JSON.stringify(
    {
      date: "2026-10-08",
      runtime: process.version,
      scope:
        "Node only; synthetic stock metadata. Excludes browser/DOM/GPU/peak memory/accuracy; worst-case 12 selected dwells and 13 candidates",
      results,
    },
    null,
    2,
  ),
);
