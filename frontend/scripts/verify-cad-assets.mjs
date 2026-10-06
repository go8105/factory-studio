import assert from "node:assert/strict";
import { readdir, access } from "node:fs/promises";
const root = new URL("../public/cad-cam-app/", import.meta.url);
const files = await readdir(root, { recursive: true });
assert.ok(files.includes("index.html"));
assert.equal(
  files.filter((p) => /soap|\.stl$|\.zip$|\.csv$/i.test(p)).length,
  0,
  "Private POC data leaked into public CAD build",
);
for (const name of [
  "soap-poc.html",
  "research-notebook.html",
  "soap-poc/research-history.json",
  "soap-poc/soap-poc-03.zip",
  "soap-poc/sleeve-v3.stl",
  "soap-poc/drawer-v3.stl",
])
  await access(
    new URL("../../backend/private-assets/soap-poc/" + name, import.meta.url),
  );
console.log("CAD public asset isolation and private artifact presence: passed");
