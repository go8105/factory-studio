import test from "node:test";
import assert from "node:assert/strict";
import { parseNC, NC_PROFILE } from "../src/nc-parser.js";
import { ncDigest, generateNCOutput, verifyNCOutput } from "../src/nc-post.js";
import { analyzeEnergy, energyPlan, ENERGY_MODEL } from "../src/nc-energy.js";
async function fixture(
  text = "G21 G17 G90 G94\r\nT1 M6\r\nG1 X10 F600\r\n(🙂 P999) G4 P600 ; P888\r\nM2\r\n",
) {
  const nc = parseNC(text, {
    profile: NC_PROFILE,
    confirmed: true,
    unit: "mm",
    initial: [0, 0, 10],
  });
  nc.originalText = text;
  nc.sourceHash = await ncDigest(text);
  const stock = {
    ncSourceHash: nc.sourceHash,
    setup: { initialTool: 1 },
    rapidContactLines: [],
    maxRemaining: 0,
    maxOvercut: 0,
    targetVolumeError: 0,
    segments: nc.segments.map((r) => ({
      id: r.id,
      line: r.line,
      removedMm3: 0,
    })),
  };
  const model = {
    version: ENERGY_MODEL,
    machine: "synthetic",
    source: "test",
    provenance: "assumption",
    confirmed: true,
    wholeMachineConfirmed: true,
    axes: [0, 1, 2].map(() => ({ velocity: 3000, acceleration: 500 })),
    states: Object.fromEntries(
      energyPlan(nc, stock).states.map((r) => [
        r.key,
        { min: 1, max: 1, seconds: 1 },
      ]),
    ),
  };
  const energy = analyzeEnergy(nc, stock, model);
  const proposalSettings = {
    quality: {
      source: "test",
      maxRemaining: 0,
      maxOvercut: 0,
      maxGridErrorPercent: 0,
    },
    riskReviewed: true,
    marginKWh: 0,
    marginSource: "test",
    dwells: energy.rows
      .filter((r) => r.kind === "dwell")
      .map((r) => ({
        id: r.id,
        seconds: 10,
        source: "test minimum",
        confirmed: true,
      })),
  };
  return { nc, stock, energy, proposalSettings };
}
test("original bytes, comments, CRLF and independently reopened paths remain identical", async () => {
  const f = await fixture();
  const r = await generateNCOutput(f);
  assert.equal(r.text, f.nc.originalText);
  assert.equal(r.manifest.sourceHash, r.manifest.outputHash);
  assert.deepEqual(parseNC(r.text, f.nc.settings).segments, f.nc.segments);
});
test("candidate patches only P literal, never P in emoji comments; roundtrip/manifest", async () => {
  const f = await fixture();
  const r = await generateNCOutput({ ...f, number: 1 });
  assert.equal(r.text, f.nc.originalText.replace("G4 P600", "G4 P10"));
  assert.equal(r.manifest.changes[0].line, 4);
  assert.equal(
    parseNC(r.text, f.nc.settings).events.find((r) => r.kind === "dwell")
      .seconds,
    10,
  );
});
test("inch relative movement/full circle and T/F/S/coolant are preserved", async () => {
  const f = await fixture(
    "G20 G17 G91 G94\nT1 M6\nS500\nM3\nM8\nG1 X1 F10\nG2 I.5 J0\nG4 P600\nM9\nM5\nM30",
  );
  const r = await generateNCOutput({ ...f, number: 1 });
  assert.deepEqual(parseNC(r.text, f.nc.settings).segments, f.nc.segments);
});
test("stale hash, altered analysis, unsupported controller and invalid number rejected", async () => {
  const f = await fixture();
  await assert.rejects(generateNCOutput({ ...f, profile: "fanuc" }), /프로필/);
  await assert.rejects(generateNCOutput({ ...f, number: 99 }), /후보/);
  const stale = structuredClone(f);
  stale.nc.originalText += "\n";
  await assert.rejects(generateNCOutput(stale), /해시/);
  const corrupt = structuredClone(f);
  corrupt.nc.segments[0].to[0]++;
  await assert.rejects(generateNCOutput(corrupt), /분석 변경/);
});
test("quality/review change cannot export previously valid candidate", async () => {
  const f = await fixture();
  f.proposalSettings.riskReviewed = false;
  await assert.rejects(generateNCOutput({ ...f, number: 1 }), /품질/);
});
test("unsupported H compensation, missing termination and hidden code after end block export", async () => {
  for (const text of [
    "G43 H1\nG1 X10 F100\nM2",
    "G1 X10 F100",
    "G1 X10 F100\nM2\nG0 X99",
  ]) {
    const nc = parseNC(text, {
      confirmed: true,
      unit: "mm",
      initial: [0, 0, 10],
    });
    Object.assign(nc, { originalText: text, sourceHash: await ncDigest(text) });
    await assert.rejects(generateNCOutput({ nc }), /완전|종료/);
  }
});
test("independent verification rejects path, spindle or non-selected dwell changes", async () => {
  const f = await fixture();
  const altered = parseNC(
    f.nc.originalText.replace("X10", "X11"),
    f.nc.settings,
  );
  assert.throws(() => verifyNCOutput(f.nc, altered, []), /보존/);
  const dwell = parseNC(
    f.nc.originalText.replace("P600", "P300"),
    f.nc.settings,
  );
  assert.throws(() => verifyNCOutput(f.nc, dwell, []), /보존/);
});

test("FANUC review actual dialect: O header, integer ms dwell, ASCII CRLF, reopened 10 seconds", async () => {
  const { FANUC_REVIEW_PROFILE, parseControllerNC } =
    await import("../src/nc-controller.js");
  const f = await fixture();
  const r = await generateNCOutput({
    ...f,
    profile: FANUC_REVIEW_PROFILE,
    number: 1,
    programNumber: 1234,
  });
  assert.match(r.text, /O1234\r\n/);
  assert.match(r.text, /G4 P10000/);
  assert.ok(!r.text.includes("🙂"));
  assert.equal(r.manifest.machineReady, false);
  assert.equal(r.manifest.dwellUnit, "milliseconds");
  const reopened = parseControllerNC(r.text, {
    ...f.nc.settings,
    profile: FANUC_REVIEW_PROFILE,
  });
  assert.equal(reopened.events.find((e) => e.kind === "dwell").seconds, 10);
  assert.deepEqual(
    reopened.segments.map(({ line, ...s }) => s),
    f.nc.segments.map(({ line, ...s }) => s),
  );
  reopened.originalText = r.text;
  reopened.sourceHash = await ncDigest(r.text);
  const again = await generateNCOutput({
    nc: reopened,
    profile: FANUC_REVIEW_PROFILE,
    programNumber: 1234,
  });
  assert.equal(
    parseControllerNC(again.text, reopened.settings).events.find(
      (e) => e.kind === "dwell",
    ).seconds,
    10,
  );
});
test("FANUC ms granularity, program bounds, malformed/import dialect are blocked", async () => {
  const { FANUC_REVIEW_PROFILE, parseControllerNC } =
    await import("../src/nc-controller.js");
  const f = await fixture();
  for (const programNumber of [0, 8000, 1.5])
    await assert.rejects(
      generateNCOutput({ ...f, profile: FANUC_REVIEW_PROFILE, programNumber }),
      /프로그램 번호/,
    );
  f.proposalSettings.dwells[0].seconds = 0.0001;
  await assert.rejects(
    generateNCOutput({ ...f, profile: FANUC_REVIEW_PROFILE, number: 1 }),
    /정밀도/,
  );
  const settings = { ...f.nc.settings, profile: FANUC_REVIEW_PROFILE };
  for (const text of [
    "O1001\nG4 P1.5\nM2",
    "O1001\nG91.1\nM2",
    "G1 X10 F100\nO1001\nM2",
    "O8000\nM2",
    "G4 P10\nM2",
  ])
    assert.throws(() => parseControllerNC(text, settings));
});
test("FANUC original mode converts every dwell, omits only G91.1, preserves mixed modal block state", async () => {
  const { FANUC_REVIEW_PROFILE, parseControllerNC } =
    await import("../src/nc-controller.js");
  const f = await fixture(
    "%\nG21 G17 G90 G91.1 G94\nG091.10\nT1 M6\nG1 X10 F600\nG4 P0\nG21 G4 P2.125\nM2\n%\n",
  );
  const r = await generateNCOutput({ ...f, profile: FANUC_REVIEW_PROFILE });
  assert.ok(!r.text.includes("G91.1"));
  assert.match(r.text, /G21 G4 P2125/);
  assert.deepEqual(
    parseControllerNC(r.text, {
      ...f.nc.settings,
      profile: FANUC_REVIEW_PROFILE,
    })
      .events.filter((e) => e.kind === "dwell")
      .map((e) => e.seconds),
    [0, 2.125],
  );
});

test("FANUC code numeric spellings cannot bypass dwell units or unsupported G91.1", async () => {
  const { FANUC_REVIEW_PROFILE, parseControllerNC } =
    await import("../src/nc-controller.js");
  const settings = {
    profile: FANUC_REVIEW_PROFILE,
    confirmed: true,
    unit: "mm",
    initial: [0, 0, 0],
  };
  for (const word of ["G091.1", "G91.10", "G+91.1"])
    assert.throws(
      () => parseControllerNC(`O1001\n${word}\nM2`, settings),
      /91.1/,
    );
  for (const word of ["G+4", "G004.00"]) {
    const n = parseControllerNC(
      `O1001\nG1 X1 F100\n${word} P10000\nM2`,
      settings,
    );
    assert.equal(n.events.find((e) => e.kind === "dwell").seconds, 10);
  }
  assert.throws(
    () => parseControllerNC("O1001 (unclosed\nM2", settings),
    /주석/,
  );
});
