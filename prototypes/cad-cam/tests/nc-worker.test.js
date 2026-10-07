import { test } from "node:test";
import assert from "node:assert/strict";
import { Worker } from "node:worker_threads";
import { createHash } from "node:crypto";
const moduleURL = new URL("../src/nc-worker.js", import.meta.url).href;
// Browser worker module, exercised under a Node message bridge (not a browser performance test).
function workerBridge() {
  return new Worker(
    `const {parentPort}=require('node:worker_threads');globalThis.self={postMessage:data=>parentPort.postMessage(data)};parentPort.on('message',data=>self.onmessage({data}));import(${JSON.stringify(moduleURL)}).then(()=>parentPort.postMessage({ready:true}));`,
    { eval: true },
  );
}
function ready(w) {
  return new Promise((resolve, reject) => {
    w.once("error", reject);
    w.once("message", resolve);
  });
}
function result(w, data) {
  return new Promise((resolve, reject) => {
    const listen = (v) => {
      if (v.result || v.error) {
        w.off("message", listen);
        resolve(v);
      }
    };
    w.on("message", listen);
    w.once("error", reject);
    w.postMessage(data);
  });
}
test(
  "NC worker tags responses, hashes exact source and never fabricates full analysis",
  { timeout: 5000 },
  async () => {
    const w = workerBridge();
    try {
      await ready(w);
      const text = "\uFEFFG0 X5\r\nG43 H1\r\nG0 X50",
        settings = { initial: [0, 0, 0], unit: "mm", confirmed: true };
      const reply = await result(w, { revision: 42, text, settings });
      assert.equal(reply.revision, 42);
      assert.equal(reply.result.originalText, text);
      assert.equal(
        reply.result.sourceHash,
        createHash("sha256").update(text).digest("hex"),
      );
      assert.equal(reply.result.complete, false);
      assert.equal(reply.result.segments.length, 1);
      assert.equal(reply.result.blocks[2].status, "blocked");
      const bad = await result(w, {
        revision: 43,
        text,
        settings: { ...settings, confirmed: false },
      });
      assert.equal(bad.revision, 43);
      assert.match(bad.error, /초기 XYZ/);
      assert.equal(bad.result, undefined);
    } finally {
      await w.terminate();
    }
  },
);
