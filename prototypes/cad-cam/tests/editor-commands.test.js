import test from "node:test";
import assert from "node:assert/strict";
import {
  DraftHistory,
  shortcutCommand,
  dependentFeatures,
} from "../src/editor-commands.js";
const event = (key, extras = {}) => ({
  key,
  ctrlKey: false,
  metaKey: false,
  shiftKey: false,
  altKey: false,
  repeat: false,
  isComposing: false,
  ...extras,
});
test("Windows and Mac undo/redo, save, cancel, delete and fit share the same routing", () => {
  for (const mod of [{ ctrlKey: true }, { metaKey: true }]) {
    assert.equal(shortcutCommand(event("z", mod)), "undo");
    assert.equal(
      shortcutCommand(event("Z", { ...mod, shiftKey: true })),
      "redo",
    );
    assert.equal(shortcutCommand(event("s", mod)), "save");
  }
  assert.equal(shortcutCommand(event("y", { ctrlKey: true })), "redo");
  assert.equal(shortcutCommand(event("Delete")), "delete");
  assert.equal(shortcutCommand(event("Escape")), "cancel");
  assert.equal(shortcutCommand(event("F")), "fit");
});
test("native input/contenteditable undo and IME/repeat events cannot alter the design", () => {
  const input = { closest: () => ({}) };
  for (const key of ["z", "y", "Delete", "Backspace", "f"])
    assert.equal(
      shortcutCommand(
        event(key, { ctrlKey: key === "z" || key === "y", target: input }),
      ),
      null,
    );
  assert.equal(
    shortcutCommand(
      event("z", {
        ctrlKey: true,
        target: { closest: () => null },
        composedPath: () => [input],
      }),
    ),
    null,
  );
  assert.equal(shortcutCommand(event("Escape", { target: input })), "cancel");
  for (const extra of [
    { isComposing: true },
    { keyCode: 229 },
    { repeat: true },
    { altKey: true },
  ])
    assert.equal(
      shortcutCommand(event("z", { ctrlKey: true, ...extra })),
      null,
    );
});
test("draft point/arc/closure undo preserves IDs, pending clicks and redo without touching accepted model", () => {
  const h = new DraftHistory(),
    states = [
      { nodes: [], clicks: [], closed: false },
      { nodes: [{ id: "a", point: [0, 0] }], clicks: [[0, 0]], closed: false },
      {
        nodes: [
          { id: "a", point: [0, 0] },
          { id: "b", point: [5, 5] },
        ],
        clicks: [
          [0, 0],
          [5, 5],
        ],
        closed: false,
      },
      {
        nodes: [
          { id: "a", point: [0, 0], arcVia: [5, 5] },
          { id: "c", point: [10, 0] },
        ],
        clicks: [
          [0, 0],
          [5, 5],
          [10, 0],
        ],
        closed: true,
      },
    ];
  for (let i = 1; i < states.length; i++) h.record(states[i - 1], states[i]);
  let s = states.at(-1);
  for (let i = 2; i >= 0; i--) {
    s = h.undo(s);
    assert.deepEqual(s, states[i]);
  }
  assert.equal(h.undo(s), null);
  assert.ok(h.active);
  for (let i = 1; i < states.length; i++) {
    s = h.redo(s);
    assert.deepEqual(s, states[i]);
  }
  s.nodes[0].point[0] = 99;
  assert.equal(states[0].nodes.length, 0);
  assert.equal(states[1].nodes[0].point[0], 0);
});
test("typing and drag previews coalesce into one command; new editing invalidates redo", () => {
  const h = new DraftHistory(),
    group = {};
  h.record({ w: 10 }, { w: 11 }, group);
  h.record({ w: 11 }, { w: 12 }, group);
  h.record({ w: 12 }, { w: 13 }, group);
  assert.deepEqual(h.undo({ w: 13 }), { w: 10 });
  assert.deepEqual(h.redo({ w: 10 }), { w: 13 });
  h.undo({ w: 13 });
  h.record({ w: 10 }, { w: 14 });
  assert.equal(h.canRedo, false);
  h.endGroup();
  h.record({ w: 14 }, { w: 15 }, group);
  assert.deepEqual(h.undo({ w: 15 }), { w: 14 });
});
test("no-op, cancelled draft session and bounded memory preserve history boundaries", () => {
  const h = new DraftHistory(2);
  assert.equal(h.record({ x: 1 }, { x: 1 }), false);
  for (let x = 0; x < 4; x++) h.record({ x }, { x: x + 1 });
  assert.deepEqual(h.undo({ x: 4 }), { x: 3 });
  assert.deepEqual(h.undo({ x: 3 }), { x: 2 });
  assert.equal(h.undo({ x: 2 }), null);
  h.clear();
  assert.equal(h.canUndo, false);
  assert.equal(h.canRedo, false);
  assert.equal(h.active, false);
});
test("deletion checks direct and transitive plane/pattern references, leaves unrelated features", () => {
  const operations = [
    { id: "a", name: "보스", referenceId: "base" },
    { id: "b", name: "구멍", referenceId: "a" },
    { id: "c", name: "배열", sourceId: "b" },
    { id: "d", referenceId: "world" },
  ];
  assert.deepEqual(
    dependentFeatures(operations, "a").map((f) => f.id),
    ["b", "c"],
  );
  assert.deepEqual(
    dependentFeatures(operations, "base").map((f) => f.id),
    ["a", "b", "c"],
  );
  assert.deepEqual(dependentFeatures(operations, "c"), []);
});
