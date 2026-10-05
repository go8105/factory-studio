import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
for (const name of ["tray", "plate-A", "plate-B", "plate-C"])
  test(`${name}: exported STL is closed, oriented and has positive volume`, () => {
    const b = fs.readFileSync(
      new URL(`../public/soap-poc/${name}.stl`, import.meta.url),
    );
    const n = b.readUInt32LE(80);
    assert.equal(b.length, 84 + n * 50);
    const edges = new Map();
    let volume = 0;
    for (let i = 0; i < n; i++) {
      const p = Array.from({ length: 3 }, (_, j) =>
        Array.from({ length: 3 }, (_, k) =>
          b.readFloatLE(84 + i * 50 + 12 + j * 12 + k * 4),
        ),
      );
      const keys = p.map((v) => v.map((x) => x.toFixed(5)).join(","));
      assert.equal(new Set(keys).size, 3);
      for (let j = 0; j < 3; j++) {
        const a = keys[j],
          c = keys[(j + 1) % 3],
          key = [a, c].sort().join("/");
        const e = edges.get(key) || [0, 0];
        e[0]++;
        e[1] += a < c ? 1 : -1;
        edges.set(key, e);
      }
      const [a, c, d] = p;
      volume +=
        (a[0] * (c[1] * d[2] - c[2] * d[1]) +
          a[1] * (c[2] * d[0] - c[0] * d[2]) +
          a[2] * (c[0] * d[1] - c[1] * d[0])) /
        6;
    }
    for (const [edge, [count, balance]] of edges) {
      assert.equal(count, 2, edge);
      assert.equal(balance, 0, edge);
    }
    assert.ok(volume > 0);
  });
