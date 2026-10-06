import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { validateNotes, mergeNotes } from "../src/research-notes.js";
const note = {
  id: "test",
  createdAt: "2026-10-06T00:00:00Z",
  revision: "POC-03",
  title: "출력 전",
  hypothesis: "벽 두께 비교",
  result: "미실행",
  decision: "출력 후 측정",
};
test("archive history points to exact existing designs", () => {
  const root = new URL("../private/soap-poc/", import.meta.url),
    data = JSON.parse(readFileSync(new URL("research-history.json", root)));
  assert.deepEqual(
    data.entries.map((e) => e.id),
    ["POC-01", "POC-02", "POC-03"],
  );
  for (const entry of data.entries)
    for (const f of entry.files)
      assert.equal(
        createHash("sha256")
          .update(readFileSync(new URL(f.name, root)))
          .digest("hex"),
        f.sha256,
      );
});
test("backup merges duplicate notes once and refuses conflicting replacement", () => {
  assert.equal(mergeNotes([note], [note]).length, 1);
  assert.throws(() => mergeNotes([note], [{ ...note, result: "changed" }]));
  assert.throws(() => validateNotes([{ ...note, revision: "unknown" }]));
  assert.throws(() => validateNotes([{ ...note, title: "x".repeat(121) }]));
});
