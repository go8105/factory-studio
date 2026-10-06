import test from "node:test";
import assert from "node:assert/strict";
import {
  runExperiment,
  scanRows,
  clearance,
} from "../experiments/cnc-offset-e0.mjs";
test("CNC E0 handles concavity, island, split neck, and oversized cutter", async () => {
  const report = await runExperiment();
  assert.deepEqual(
    report.results.map((r) => r.components),
    [1, 1, 2, 0],
  );
  const island = report.results[1];
  assert.ok(
    island.segments.some(([a, b]) => a[1] > 20 && a[1] < 40 && b[0] < 30),
  );
  assert.ok(
    island.segments.some(([a, b]) => a[1] > 20 && a[1] < 40 && a[0] > 50),
  );
  assert.ok(
    report.results.slice(0, 3).every((r) => r.minClearanceMm >= r.diameter / 2),
  );
});
test("independent oracle rejects unsafe bridging across original island", () => {
  const rings = [
    [
      [0, 0],
      [80, 0],
      [80, 60],
      [0, 60],
    ],
    [
      [30, 20],
      [50, 20],
      [50, 40],
      [30, 40],
    ],
  ];
  assert.ok(clearance([40, 30], rings) < 0);
  assert.ok(clearance([10, 30], rings) > 0);
  assert.throws(() => scanRows(rings, 0));
});
