import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { inspect } from "../../../frontend/src/factory/inspection.ts";
const binary = resolve(process.argv[2]);
const requests = [];
// Every threshold; minimum-area boundaries including full-frame and ROI limits.
for (const sample of ["normal", "foreign", "lighting"])
  for (const roi of ["full", "center"])
    for (let threshold = 0; threshold <= 255; threshold++)
      for (const minArea of [
        1, 4, 5, 20, 36, 37, 80, 81, 100, 4000, 4001, 4800, 16000,
      ])
        requests.push({
          version: 1,
          sample,
          recipe: { threshold, minArea, roi },
        });
const run = (input, args = []) => {
  const result = spawnSync(binary, args, {
    input,
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
    timeout: 100000,
  });
  assert.ifError(result.error);
  assert.equal(result.stderr, "");
  return result;
};
const result = run(requests.map((r) => JSON.stringify(r)).join("\n"), [
  "--ndjson",
]);
assert.equal(result.status, 0);
const outputs = result.stdout
  .trim()
  .split("\n")
  .map((line) => JSON.parse(line));
assert.equal(outputs.length, requests.length);
outputs.forEach((native, index) => {
  assert.equal(native.source, "synthetic-opencv-cpp-v1");
  const expected = inspect(requests[index]);
  assert.deepEqual(
    { ...native, source: expected.source },
    expected,
    JSON.stringify(requests[index]),
  );
});
const valid = {
  version: 1,
  sample: "foreign",
  recipe: { threshold: 90, minArea: 20, roi: "full" },
};
assert.deepEqual(
  JSON.parse(run(JSON.stringify({ request: valid, result: {} })).stdout),
  JSON.parse(run(JSON.stringify(valid)).stdout),
);
const invalid = [
  null,
  [],
  {},
  { ...valid, version: 2 },
  { ...valid, version: true },
  { ...valid, sample: "camera" },
  { ...valid, recipe: null },
];
for (const patch of [
  { threshold: -1 },
  { threshold: 256 },
  { threshold: 1.5 },
  { threshold: true },
  { threshold: "90" },
  { minArea: 0 },
  { minArea: 16001 },
  { roi: "other" },
])
  invalid.push({ ...valid, recipe: { ...valid.recipe, ...patch } });
for (const input of [
  ...invalid.map((v) => JSON.stringify(v)),
  "",
  "{",
  "null trailing",
  " ".repeat(65537),
]) {
  const failed = run(input);
  assert.equal(failed.status, 2);
  assert.ok(JSON.parse(failed.stdout).error.code);
}
const recovered = run(`{\n${JSON.stringify(valid)}\n`, ["--ndjson"]);
assert.equal(recovered.status, 2);
assert.equal(JSON.parse(recovered.stdout.trim().split("\n")[1]).status, "NG");
const decimal = run(
  '{"version":1.0,"sample":"normal","recipe":{"threshold":90.0,"minArea":20.0,"roi":"full"}}',
);
assert.equal(decimal.status, 0);
assert.equal(
  run("", [new URL("../examples/foreign.json", import.meta.url).pathname])
    .status,
  0,
);
assert.equal(run("", ["does-not-exist.json"]).status, 2);
assert.equal(run("", ["one", "two"]).status, 2);
console.log(
  JSON.stringify(
    {
      parityCases: requests.length,
      mismatches: 0,
      cliValidation: "passed",
      source: "synthetic-opencv-cpp-v1",
    },
    null,
    2,
  ),
);
