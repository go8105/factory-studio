import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseNC, NC_LIMITS, NC_PROFILE } from "../src/nc-parser.js";
const settings = {
  initial: [0, 0, 0],
  unit: "mm",
  confirmed: true,
  profile: NC_PROFILE,
};
const run = (text, s = settings) => parseNC(text, s);
const near = (actual, expected, eps = 1e-8) =>
  assert.ok(Math.abs(actual - expected) <= eps, `${actual} vs ${expected}`);
test("modal axes, absolute/incremental and state per original row", () => {
  const r = run(
    "G21 G90 G17 G94 G54\nG0 X10 Y20 Z5\nG1 Z-2 F120\nX30\nG91 X-5 Y3\nG90 Y10\nM30",
  );
  assert.equal(r.complete, true);
  assert.equal(r.segments.length, 5);
  assert.deepEqual(
    r.segments.map((s) => s.to),
    [
      [10, 20, 5],
      [10, 20, -2],
      [30, 20, -2],
      [25, 23, -2],
      [25, 10, -2],
    ],
  );
  assert.equal(r.blocks[4].before.distance, "absolute");
  assert.equal(r.blocks[4].after.distance, "incremental");
  assert.equal(r.blocks[3].segment, 2);
  assert.equal(r.segments[2].line, 4);
  assert.equal(r.segments[2].state.feed, 120);
  assert.equal(r.totalTimeSeconds, null);
  assert.equal(r.energyKWh, null);
});
test("inch initial position and mixed unit moves/feeds are canonical mm", () => {
  const r = run("G91 G1 X1 F2\nG21 X25.4 F50.8", {
    ...settings,
    unit: "inch",
    initial: [1, 0, 0],
  });
  near(r.segments[0].from[0], 25.4);
  near(r.segments[0].to[0], 50.8);
  near(r.segments[1].to[0], 76.2);
  near(r.segments[0].state.feed, 50.8);
});
test("CW/CCW I/J quarter arcs match independent circle oracle", () => {
  for (const [g, y, sign] of [
    [3, 10, 1],
    [2, -10, -1],
  ]) {
    const r = run(`G0 X10\nG${g} X0 Y${y} I-10 F100`),
      s = r.segments[1];
    assert.equal(r.complete, true);
    near(s.length, Math.PI * 5);
    near(s.arc.sweep, (sign * Math.PI) / 2);
    const mid = s.points[Math.floor((s.points.length - 1) / 2)];
    near(mid[0], 10 * Math.SQRT1_2);
    near(mid[1], sign * 10 * Math.SQRT1_2);
    for (let j = 1; j < s.points.length; j++) {
      const a = s.points[j - 1],
        b = s.points[j];
      const radialMid = Math.hypot((a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
      assert.ok(10 - radialMid <= 0.05 + 1e-8);
    }
  }
});
test("signed R uses short/long arcs and half-circle", () => {
  for (const g of [2, 3])
    for (const R of [10, -10]) {
      const s = run(`G${g} X10 Y10 R${R} F100`).segments[0];
      near(Math.abs(s.arc.sweep), R > 0 ? Math.PI / 2 : (3 * Math.PI) / 2);
      assert.equal(s.arc.clockwise, g === 2);
      near(s.length, 10 * Math.abs(s.arc.sweep));
      assert.deepEqual(s.points.at(-1), [10, 10, 0]);
    }
  near(run("G2 X20 R10 F100").segments[0].arc.sweep, -Math.PI);
});
test("I/J full circles and incremental end coordinates", () => {
  const s = run("G3 I10 F100").segments[0];
  near(s.length, 20 * Math.PI);
  assert.deepEqual(s.from, s.to);
  const r = run("G0 X10\nG91 G3 X-10 Y10 I-10 F100");
  near(r.segments[1].arc.sweep, Math.PI / 2);
});
test("events and active vs selected tools, coolant additions and end state", () => {
  const r = run(
    "T1\nM6\nS6000 M3\nM7\nM8\nG1 X10 F200\nT2\nG1 X20\nG4 P1.5\nM30\nG1 X999",
  );
  assert.equal(r.complete, true);
  assert.equal(r.segments[1].state.tool, 1);
  assert.equal(r.segments[1].state.selectedTool, 2);
  assert.equal(r.segments[0].state.spindle, "cw");
  assert.deepEqual(r.segments[0].state.coolant, ["mist", "flood"]);
  assert.equal(r.events.find((e) => e.kind === "dwell").seconds, 1.5);
  assert.equal(r.events.find((e) => e.kind === "tool-change").seconds, null);
  assert.equal(r.blocks.at(-1).status, "after-end");
  assert.equal(r.finalState.spindle, "off");
  assert.deepEqual(r.finalState.coolant, []);
});
test("compact/case-insensitive literals, comments, labels, CRLF and BOM", () => {
  const r = run(
    "\uFEFF%\r\nO1201\r\n(comment)\r\nN10g1x.5y-2.f100 ; G43H1\r\nM2\r\n%",
  );
  assert.equal(r.complete, true);
  assert.deepEqual(r.segments[0].to, [0.5, -2, 0]);
  assert.equal(r.blocks[3].number, 10);
});
test("every unsupported semantic family stops and never reconnects later axes", () => {
  for (const bad of [
    "G43 H1",
    "G41 D1",
    "G28",
    "G53 G0 X0",
    "G55",
    "G81 X1 Z-2 R3",
    "G93",
    "G95",
    "G18",
    "G19",
    "G90.1",
    "G92 X1",
    "G64",
    "M0",
    "M1",
    "M98 P1",
    "M100",
    "G1 A10",
    "G1 X#1",
    "G1 X[1+2]",
    "/ G0 X0",
    "G2 X1 Y1 P2 I1",
    "G2 X0 Y20 Z3 I0 J10",
    "G7",
  ]) {
    const r = run(`G0 X5\n${bad}\nG0 X50`);
    assert.equal(r.complete, false, bad);
    assert.equal(r.segments.length, 1, bad);
    assert.equal(r.blocks[2].status, "blocked", bad);
    assert.deepEqual(r.finalState.position, [5, 0, 0], bad);
  }
});
test("atomic rejected block does not leak F/tool/spindle/coordinates/events", () => {
  const r = run("G1 X10 F100\nT9 S9000 M3 G43 X100 F200\nX20");
  assert.equal(r.segments.length, 1);
  assert.equal(r.finalState.feed, 100);
  assert.equal(r.finalState.rpm, 0);
  assert.equal(r.finalState.selectedTool, null);
  assert.equal(r.events.length, 0);
  assert.equal(r.blocks[1].after, undefined);
});
test("malformed or ambiguous blocks fail without state mutation", () => {
  for (const bad of [
    "G1 X1 X2 F100",
    "G0 G1 X1",
    "G90 G91",
    "M3 M5",
    "M3 M6",
    "G1 X1",
    "G4",
    "G4 P-1",
    "G4 P2 X1",
    "G4 P2 M3",
    "G4 G1 P1",
    "G1 X1 F0",
    "T1.5",
    "M6",
    "G1 I2 F10",
    "G3 X10 Y10 R1 F100",
    "G3 R10 F100",
    "G3 X1 I1 R1 F100",
    "G3 X1 I10 F100",
    "N-1 G0 X1",
    "O1 G0 X1",
    "(broken",
    "foo",
    "G1 XNaN",
    "G0 X1e3",
    "G80 X1",
    "M30 F100",
  ])
    assert.equal(run(bad).complete, false, bad);
  assert.equal(run("G80\nX10").complete, false);
  assert.equal(run("G80\nG0 X10").complete, true);
});
test("input prerequisites and resource limits are enforced before allocation", () => {
  for (const s of [
    { ...settings, confirmed: false },
    { ...settings, unit: "bad" },
    { ...settings, initial: [NaN, 0, 0] },
    { ...settings, initial: [0, 0] },
    { ...settings, initial: ["0", 0, 0] },
    { ...settings, profile: "haas" },
  ])
    assert.throws(() => run("G0 X1", s));
  assert.throws(() => run("a".repeat(NC_LIMITS.bytes + 1)), /2MiB/);
  assert.throws(() => run("\n".repeat(NC_LIMITS.lines)), /50,000/);
  assert.equal(run("G0 X1000001").complete, false);
  const largeArc = run(
    "G0 X1000000\n" + "G3 I-1000000 F100\n".repeat(100) + "G0 X0",
  );
  assert.equal(largeArc.complete, false);
  assert.ok(largeArc.diagnostics[0].line > 2);
  assert.ok(largeArc.pointsCount <= NC_LIMITS.points);
  assert.equal(largeArc.blocks.at(-1).status, "blocked");
});
test("synthetic example is valid and preserves raw source in blocks", () => {
  const text = readFileSync(
      new URL("../examples/cnc_CAD12_2026-10-07_milling.ngc", import.meta.url),
      "utf8",
    ),
    r = run(text);
  assert.equal(r.complete, true);
  assert.equal(r.ended, true);
  assert.equal(r.segments.length, 10);
  assert.equal(r.segments.filter((s) => s.arc).length, 3);
  assert.equal(r.blocks.map((b) => b.raw).join("\n"), text);
  assert.deepEqual(r.finalState.position, [0, 0, 10]);
  assert.equal(r.events.find((e) => e.kind === "dwell").seconds, 1.5);
});
test("percent delimiters bound execution and reject unfinished wrappers", () => {
  const r = run("%\nG0 X1\n%\nG0 X100");
  assert.equal(r.complete, true);
  assert.equal(r.ended, true);
  assert.equal(r.segments.length, 1);
  assert.equal(r.blocks.at(-1).status, "after-end");
  assert.equal(run("%\nG0 X1").complete, false);
  assert.equal(run("G0 X1\n%").complete, false);
});
test("tool change stops spindle, preserves coolant and flags unmodeled machine moves", () => {
  const r = run("S6000 M3\nM8\nT2 M6\nG0 X10\nM30");
  assert.equal(r.segments[0].state.spindle, "off");
  assert.deepEqual(r.segments[0].state.coolant, ["flood"]);
  assert.equal(
    r.events.find((e) => e.kind === "tool-change").machineMotionUnknown,
    true,
  );
  assert.equal(r.events.at(-1).machineMotionUnknown, true);
});
