import test from "node:test";
import assert from "node:assert/strict";
import { parseNC } from "../src/nc-parser.js";
import { energyPlan, analyzeEnergy, ENERGY_MODEL } from "../src/nc-energy.js";
import { compareProposals } from "../src/nc-proposals.js";
import { proposalTimeline, timelineFrame } from "../src/nc-playback.js";
import { HughCommands, parseHughCommand } from "../src/hugh-commands.js";
function fixture() {
  const nc = parseNC("T1 M6\nG1 X10 F600\nG4 P600\nG4 P300\nM2", {
    confirmed: true,
    unit: "mm",
    initial: [0, 0, 10],
  });
  nc.sourceHash = "synthetic";
  const stock = {
    ncSourceHash: nc.sourceHash,
    setup: { initialTool: 1 },
    rapidContactLines: [],
    remaining: 0,
    overcut: 0,
    maxRemaining: 0,
    maxOvercut: 0,
    targetVolumeError: 0,
    segments: nc.segments.map((s) => ({
      id: s.id,
      line: s.line,
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
      energyPlan(nc, stock).states.map((s) => [
        s.key,
        { min: 1, max: 1, seconds: 1 },
      ]),
    ),
  };
  const energy = analyzeEnergy(nc, stock, model);
  const settings = {
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
        source: "synthetic",
        confirmed: true,
      })),
  };
  return {
    nc,
    stock,
    energy,
    settings,
    report: compareProposals(nc, stock, energy, settings),
  };
}
test("candidate 2 preserves original motion/events and candidate sums; events keep tool still", () => {
  const f = fixture(),
    before = JSON.stringify(f),
    timeline = proposalTimeline(f.nc, f.energy, f.report, 2);
  assert.equal(timeline.seconds, f.report.candidates[1].seconds);
  assert.deepEqual(timeline.energy, f.report.candidates[1].energy);
  const dwells = timeline.rows.filter((r) => r.kind === "dwell");
  assert.deepEqual(
    dwells.map((r) => r.seconds),
    [600, 10],
  );
  for (const row of dwells) {
    const a = timelineFrame(timeline, row.start + row.seconds / 2);
    assert.deepEqual(a.position, [10, 0, 10]);
  }
  assert.deepEqual(timelineFrame(timeline, Infinity).energy, timeline.energy);
  assert.equal(JSON.stringify(f), before);
});
test("motion interpolation, zero time rows and endpoint completion", () => {
  const f = fixture(),
    timeline = proposalTimeline(f.nc, f.energy, f.report, 3),
    row = timeline.rows.find((r) => r.segment);
  assert.ok(
    Math.abs(
      timelineFrame(timeline, row.start + row.seconds / 2).position[0] - 5,
    ) < 1e-9,
  );
  assert.equal(timelineFrame(timeline, timeline.seconds).done, true);
  assert.equal(timelineFrame(timeline, -1).time, 0);
});
test("blocked, missing, stale, indeterminate and corrupted candidates are handled", () => {
  const f = fixture();
  assert.throws(() => proposalTimeline(f.nc, f.energy, f.report, 99));
  f.report.candidates[1].status = "blocked";
  assert.throws(() => proposalTimeline(f.nc, f.energy, f.report, 2));
  f.report.candidates[0].status = "indeterminate";
  assert.equal(
    proposalTimeline(f.nc, f.energy, f.report, 1).status,
    "indeterminate",
  );
  f.nc.sourceHash = "changed";
  assert.throws(() => proposalTimeline(f.nc, f.energy, f.report, 1));
  f.nc.sourceHash = "synthetic";
  f.report.candidates[0].seconds += 1;
  assert.throws(() => proposalTimeline(f.nc, f.energy, f.report, 1));
});
test("Korean/English wake and numbered aliases parse without arbitrary execution", () => {
  assert.deepEqual(parseHughCommand("Hey Hugh-D!"), {
    wake: true,
    type: "wake",
  });
  for (const text of [
    "2번으로 가공 실행해줘",
    "두 번째로 시뮬레이션 재생해줘",
    "이 번 실행",
  ])
    assert.equal(parseHughCommand(text).number, 2);
  assert.equal(parseHughCommand("몇번째로 실행해줘").type, "unknown");
  assert.equal(parseHughCommand("2번 실행하지 마").type, "unknown");
  assert.equal(parseHughCommand("2번 말고 3번 실행").type, "unknown");
  assert.equal(
    parseHughCommand("헤이 휴디 현재 최적안 제안해줘").type,
    "propose",
  );
});
test("wake window, duplicate final events, stop/off, and manual fallback", () => {
  let now = 1,
    calls = [];
  const c = new HughCommands(
    {
      propose: () => {
        calls.push("propose");
        return "ok";
      },
      play: (n) => {
        calls.push(n);
        return "play";
      },
      stop: () => calls.push("stop"),
      off: () => calls.push("off"),
    },
    () => now,
  );
  assert.equal(c.accept("2번 실행", "0"), null);
  c.accept("헤이 휴디", "1");
  c.accept("최적안 제안해줘", "2");
  c.accept("최적안 제안해줘", "2");
  assert.deepEqual(calls, ["propose"]);
  c.accept("두번째 실행", "3");
  assert.equal(calls.at(-1), 2);
  now += 30001;
  assert.equal(c.accept("멈춰", "4"), null);
  c.accept("멈춰", "5", true);
  assert.equal(calls.at(-1), "stop");
  c.accept("마이크 꺼", "6", true);
  assert.equal(calls.at(-1), "off");
  assert.equal(c.until, 0);
});

test("YC wake aliases enter the existing command window and select number3", () => {
  for (const wake of ["헤이 와이씨", "헤이 와이시", "hey YC", "헤이YC"]) {
    assert.equal(parseHughCommand(wake).type, "wake");
    assert.deepEqual(parseHughCommand(wake + " 3번 시뮬레이션 실행해줘"), {
      wake: true,
      type: "play",
      number: 3,
    });
    let selected = null;
    const c = new HughCommands(
      {
        play: (n) => {
          selected = n;
          return "played";
        },
      },
      () => 100,
    );
    c.accept(wake, "wake");
    c.accept("3번 시뮬레이션 실행해줘", "play");
    assert.equal(selected, 3);
  }
});
