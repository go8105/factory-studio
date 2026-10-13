import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { arrangeNCReview } from "../src/nc-layout.js";
test("NC preparation and results retain input values, references and listeners after rearrangement", () => {
  const dom = new JSDOM(
    '<main><aside class="inputs"><input value="retained"><button>run</button><details class="stock-panel"><summary>stock</summary></details><details class="stock-panel energy-panel"><summary>energy</summary></details><details class="stock-panel proposal-panel"><summary>quality</summary></details></aside><section class="workspace"><section class="hugh-panel"></section><section class="stock-output"><h2>stock result</h2></section><section class="stock-output energy-output"></section><section class="stock-output proposal-output"></section></section></main>',
  );
  const doc = dom.window.document,
    input = doc.querySelector("input"),
    button = doc.querySelector("button"),
    output = doc.querySelector(".proposal-output");
  let clicks = 0;
  button.addEventListener("click", () => clicks++);
  let current = { nc: false };
  const layout = arrangeNCReview(doc, () => current);
  button.click();
  assert.equal(doc.querySelector("input"), input);
  assert.equal(input.value, "retained");
  assert.equal(clicks, 1);
  assert.equal(doc.querySelector(".review-results .proposal-output"), output);
  assert.equal(doc.querySelector(".preparation-step").open, true);
  assert.equal(doc.querySelector(".energy-panel").open, false);
  assert.equal(doc.querySelector(".review-results .hugh-panel") !== null, true);
  doc.querySelector('[data-step="1"]').click();
  assert.equal(doc.querySelector(".stock-panel").hidden, false);
  assert.equal(doc.querySelector(".preparation-step").hidden, true);
  assert.equal(
    doc.querySelector('[data-step="1"]').getAttribute("aria-current"),
    "step",
  );
  current = { nc: true, stock: true, energy: false, quality: false };
  layout.update();
  assert.equal(doc.querySelector('[data-step="0"]').dataset.complete, "true");
  assert.equal(doc.querySelector('[data-step="2"]').dataset.complete, "false");
  assert.equal(doc.querySelector(".nc-empty").hidden, true);
  layout.select(0);
  assert.equal(input.value, "retained");
});
