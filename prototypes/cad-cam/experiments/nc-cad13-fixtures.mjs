// Synthetic independent planar STEP/NC pair; no company or machine data.
import { readFileSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import OC from "replicad-opencascadejs";
import * as r from "replicad";
r.setOC(
  await OC({
    wasmBinary: readFileSync(
      new URL(import.meta.resolve("replicad-opencascadejs/wasm")),
    ),
  }),
);
const shape = r
  .drawRectangle(20, 20)
  .translate(10, 10)
  .sketchOnPlane("XY")
  .extrude(5);
await writeFile(
  new URL("../examples/cnc_CAD13_2026-10-07_target.step", import.meta.url),
  new Uint8Array(await shape.blobSTEP().arrayBuffer()),
);
shape.delete();
const lines = [
  "(20x20x8 stock; target top Z5; T1 flat D4 flute15; G54 bottom 0)",
  "G21 G17 G90 G94",
  "T1",
  "M6",
  "S1000",
  "M3",
  "G0 X-3 Y-1 Z10",
  "G1 Z5 F100",
];
for (let y = -1; y <= 21; y += 2)
  lines.push(`G1 Y${y}`, `X${((y + 1) / 2) % 2 === 0 ? 23 : -3}`);
lines.push("G0 Z10", "M5", "M2");
await writeFile(
  new URL("../examples/cnc_CAD13_2026-10-07_face.ngc", import.meta.url),
  lines.join("\n") + "\n",
);
