import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { parseNC } from "../src/nc-parser.js";
import { energyPlan, analyzeEnergy, ENERGY_MODEL } from "../src/nc-energy.js";
import { dwellReview, compareProposals } from "../src/nc-proposals.js";
function fixture(tail = "G4 P600") {
  const text = `T1 M6\nG1 X10 F600\n${tail}\nM2`;
  const n = parseNC(text, { confirmed: true, unit: "mm", initial: [0, 0, 10] });
  n.sourceHash = createHash("sha256").update(text).digest("hex");
  const s = {
    ncSourceHash: n.sourceHash,
    setup: { initialTool: 1 },
    rapidContactLines: [],
    remaining: 0,
    overcut: 0,
    maxRemaining: 0,
    maxOvercut: 0,
    targetVolumeError: 0,
    segments: n.segments.map((r) => ({
      id: r.id,
      line: r.line,
      removedMm3: 0,
    })),
  };
  const m = {
    version: ENERGY_MODEL,
    machine: "synthetic",
    source: "test",
    provenance: "assumption",
    confirmed: true,
    wholeMachineConfirmed: true,
    axes: [0, 1, 2].map(() => ({ velocity: 3000, acceleration: 500 })),
    states: Object.fromEntries(
      energyPlan(n, s).states.map((r) => [
        r.key,
        { min: 1, max: 1, seconds: 1 },
      ]),
    ),
  };
  const a = analyzeEnergy(n, s, m);
  const options = {
    quality: {
      source: "synthetic quality",
      maxRemaining: 0,
      maxOvercut: 0,
      maxGridErrorPercent: 0,
    },
    riskReviewed: true,
    marginKWh: 0,
    marginSource: "test0",
    dwells: a.rows
      .filter((r) => r.kind === "dwell")
      .map((r) => ({
        id: r.id,
        seconds: 10,
        source: "synthetic minimum; not actual machining",
        confirmed: true,
      })),
  };
  return { n, s, m, a, options };
}
const compare = (f) => compareProposals(f.n, f.s, f.a, f.options);
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);
test("independent whole ledger sum; source/model/stock and baseline remain immutable", () => {
  const f = fixture(),
    before = JSON.stringify(f),
    r = compare(f),
    c = r.candidates[0];
  near(r.baseline.seconds, 603.02);
  near(c.seconds, 13.02);
  near(c.energy[0], 13.02 / 3600);
  near(c.savedEnergy[0], 590 / 3600);
  assert.equal(c.status, "conditional-lower");
  assert.equal(JSON.stringify(f), before);
});
test("missing quality/risk confirmation blocks all candidates before energy comparison", () => {
  const f = fixture();
  f.options.quality = {};
  f.options.riskReviewed = false;
  const r = compare(f);
  assert.ok(r.reasons.length >= 3);
  assert.equal(r.candidates.length, 0);
});
test("remaining/overcut/grid maxima independently block even a lower-energy candidate", () => {
  for (const key of ["maxRemaining", "maxOvercut", "targetVolumeError"]) {
    const f = fixture();
    f.s[key] = 0.001;
    assert.ok(compare(f).reasons.some((r) => r.includes("초과")));
  }
});
test("minimum/purpose/impact not confirmed => blocked; no automatic dwell deletion", () => {
  const f = fixture();
  Object.assign(f.options.dwells[0], {
    seconds: null,
    source: "",
    confirmed: false,
  });
  const r = compare(f);
  assert.equal(r.candidates[0].status, "blocked");
  assert.equal(r.candidates[0].reasons.length, 3);
});
test("nonfinite/negative/longer minimum and reversed scope throw; zero explicitly supported", () => {
  for (const v of [-1, NaN, Infinity, 601]) {
    const f = fixture();
    f.options.dwells[0].seconds = v;
    assert.throws(() => compare(f));
  }
  const f = fixture();
  f.options.dwells[0].seconds = 0;
  near(compare(f).candidates[0].seconds, 3.02);
  f.options.dwells[0].id = 999;
  assert.throws(() => compare(f));
});
test("no reduction, overlapping intervals, equality at margin, missing margin => indeterminate", () => {
  const f = fixture();
  f.options.dwells[0].seconds = 600;
  assert.equal(compare(f).candidates[0].status, "indeterminate");
  f.options.dwells[0].seconds = 10;
  f.options.marginKWh = 590 / 3600;
  assert.equal(compare(f).candidates[0].status, "indeterminate");
  f.options.marginKWh = null;
  assert.equal(compare(f).candidates[0].status, "indeterminate");
  for (const v of Object.values(f.m.states))
    Object.assign(v, { min: 1, max: 100 });
  f.a = analyzeEnergy(f.n, f.s, f.m);
  f.options.marginKWh = 0;
  assert.equal(compare(f).candidates[0].status, "indeterminate");
});
test("multiple individual and combined scenarios preserve unselected dwells and event time", () => {
  const f = fixture("G4 P600\nG4 P100\nG4 P50");
  f.options.dwells = f.options.dwells.slice(0, 2);
  const r = compare(f);
  assert.equal(r.candidates.length, 3);
  near(r.candidates[0].seconds, 163.02);
  near(r.candidates[1].seconds, 663.02);
  near(r.candidates[2].seconds, 73.02);
  near(r.candidates[2].savedEnergy[0], 680 / 3600);
});
test("unsupported partial/hash mismatch/rapid contact and unknown total prevent comparison", () => {
  for (const change of [
    (f) => (f.n.complete = false),
    (f) => (f.s.ncSourceHash = "old"),
    (f) => (f.a.sourceHash = "old"),
    (f) => (f.s.rapidContactLines = [2]),
    (f) => (f.a.totalTime = null),
    (f) => (f.a.totalEnergy = null),
  ]) {
    const f = fixture();
    change(f);
    assert.throws(() => compare(f));
  }
});
test("mixed feed/modal setting G4 not eligible; only standalone unchanged state allowed", () => {
  const f = fixture("G4 P600 F700");
  assert.equal(dwellReview(f.n, f.s, f.a)[0].eligible, false);
  assert.equal(compare(f).candidates[0].status, "blocked");
});
test("duplicate and selection limit rejected; no dwell explains unsupported opportunity", () => {
  const f = fixture();
  f.options.dwells.push({ ...f.options.dwells[0] });
  assert.throws(() => compare(f));
  f.options.dwells = Array.from({ length: 13 }, (_, id) => ({ id }));
  assert.throws(() => compare(f));
  const empty = fixture("");
  assert.ok(compare(empty).reasons.some((r) => r.includes("지원 대기 없음")));
});
test("missing/invalid stock quality and margin provenance never promoted to recommendation", () => {
  for (const key of ["maxRemaining", "maxOvercut", "targetVolumeError"]) {
    const f = fixture();
    f.s[key] = null;
    assert.ok(compare(f).reasons.length);
  }
  const f = fixture();
  f.options.marginSource = "";
  assert.ok(compare(f).reasons.includes("추가 비교 여유 근거 필요"));
  f.options.marginKWh = -1;
  assert.throws(() => compare(f));
});
test("actual CAD15 sample preserves every movement and adds only standalone 600-second dwell", () => {
  const load = (name) =>
    parseNC(
      readFileSync(new URL("../examples/" + name, import.meta.url), "utf8"),
      { confirmed: true, unit: "mm", initial: [-3, -1, 10] },
    );
  const original = load("cnc_CAD13_2026-10-07_face.ngc"),
    example = load("cnc_CAD15_2026-10-08_dwell.ngc");
  assert.equal(example.complete, true);
  const movement = (r) => r.segments.map(({ line, ...s }) => s);
  assert.deepEqual(movement(example), movement(original));
  assert.deepEqual(
    example.events.filter((e) => e.kind === "dwell").map((e) => e.seconds),
    [600],
  );
});

test("confirmation must be boolean true and energy range must have exactly two bounds", () => {
  const f = fixture();
  f.options.riskReviewed = "false";
  assert.ok(compare(f).reasons.length);
  f.options.riskReviewed = true;
  f.options.dwells[0].confirmed = "false";
  assert.equal(compare(f).candidates[0].status, "blocked");
  f.a.totalEnergy = [];
  assert.throws(() => compare(f));
});
