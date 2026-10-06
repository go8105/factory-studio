import Module from "manifold-3d";
import { performance } from "node:perf_hooks";
import { readFile, writeFile, mkdir, stat } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import assert from "node:assert/strict";

// Independent clearance oracle: distance to original line segments + even/odd containment.
export function clearance(point, polygons) {
  let inside = false,
    min = Infinity;
  for (const ring of polygons) {
    for (let i = 0; i < ring.length; i++) {
      const a = ring[i],
        b = ring[(i + 1) % ring.length],
        dx = b[0] - a[0],
        dy = b[1] - a[1];
      const t = Math.max(
        0,
        Math.min(
          1,
          ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) /
            (dx * dx + dy * dy),
        ),
      );
      min = Math.min(
        min,
        Math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy),
      );
      if (
        a[1] > point[1] !== b[1] > point[1] &&
        point[0] < ((b[0] - a[0]) * (point[1] - a[1])) / (b[1] - a[1]) + a[0]
      )
        inside = !inside;
    }
  }
  return inside ? min : -min;
}
export function scanRows(polygons, step) {
  if (!Number.isFinite(step) || step <= 0)
    throw Error("Positive scan spacing required");
  if (!polygons.length) return [];
  const ys = polygons.flat().map((p) => p[1]),
    lo = Math.min(...ys),
    hi = Math.max(...ys),
    segments = [];
  // Avoid vertex/tangent scanlines; crossing pairs represent separate cutting spans.
  for (let y = lo + step / 2; y < hi; y += step) {
    const xs = [];
    for (const ring of polygons)
      for (let i = 0; i < ring.length; i++) {
        const a = ring[i],
          b = ring[(i + 1) % ring.length];
        if (a[1] > y !== b[1] > y)
          xs.push(a[0] + ((y - a[1]) * (b[0] - a[0])) / (b[1] - a[1]));
      }
    xs.sort((a, b) => a - b);
    if (xs.length % 2) throw Error("Unpaired scan intersections");
    for (let i = 0; i < xs.length; i += 2)
      if (xs[i + 1] - xs[i] > 1e-6)
        segments.push([
          [xs[i], y],
          [xs[i + 1], y],
        ]);
  }
  return segments;
}
export async function runExperiment() {
  const start = performance.now(),
    mod = await Module();
  mod.setup();
  const initializationMs = performance.now() - start,
    C = mod.CrossSection;
  const cases = [
    {
      id: "l-pocket",
      name: "L-shaped pocket",
      diameter: 6,
      rings: [
        [
          [0, 0],
          [70, 0],
          [70, 20],
          [25, 20],
          [25, 60],
          [0, 60],
        ],
      ],
      expectComponents: 1,
    },
    {
      id: "island",
      name: "Pocket with island",
      diameter: 6,
      rings: [
        [
          [0, 0],
          [80, 0],
          [80, 60],
          [0, 60],
        ],
        [
          [30, 20],
          [50, 20],
          [50, 40],
          [30, 40],
        ],
      ],
      expectComponents: 1,
    },
    {
      id: "narrow-neck",
      name: "Narrow neck splits area",
      diameter: 6,
      rings: [
        [
          [0, 0],
          [30, 0],
          [30, 18],
          [50, 18],
          [50, 0],
          [80, 0],
          [80, 40],
          [50, 40],
          [50, 22],
          [30, 22],
          [30, 40],
          [0, 40],
        ],
      ],
      expectComponents: 2,
    },
    {
      id: "oversize-tool",
      name: "Tool cannot enter",
      diameter: 12,
      rings: [
        [
          [0, 0],
          [40, 0],
          [40, 8],
          [0, 8],
        ],
      ],
      expectComponents: 0,
    },
  ];
  const results = [];
  for (const input of cases) {
    const began = performance.now(),
      original = new C(input.rings, "EvenOdd");
    const region = original.offset(-input.diameter / 2 - 0.05, "Round", 2, 128);
    const polygons = region.toPolygons(),
      pieces = region.decompose();
    const components = pieces.filter((p) => !p.isEmpty()).length;
    pieces.forEach((p) => p.delete());
    assert.equal(components, input.expectComponents);
    const segments = scanRows(polygons, input.diameter * 0.4);
    let minClearance = Infinity,
      samples = 0;
    for (const [a, b] of segments) {
      const count = Math.max(
        1,
        Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.25),
      );
      for (let i = 0; i <= count; i++) {
        const q = [a[0] + ((b[0] - a[0]) * i) / count, a[1]];
        const gap = clearance(q, input.rings);
        minClearance = Math.min(minClearance, gap);
        samples++;
        assert.ok(
          gap >= input.diameter / 2 - 1e-5,
          `${input.id}: cutter crossed original boundary`,
        );
      }
    }
    if (components === 0) assert.equal(segments.length, 0);
    else assert.ok(segments.length > 0);
    const points = [],
      safeZ = 17,
      cutZ = 8;
    // Separate retract/rapid/plunge for every span, including across islands and necks.
    for (const [a, b] of segments) {
      if (points.length) {
        const p = points.at(-1);
        points.push({ ...p, z: safeZ, mode: "retract" });
      }
      points.push(
        { x: a[0], y: a[1], z: safeZ, mode: "rapid" },
        { x: a[0], y: a[1], z: cutZ, mode: "plunge" },
        { x: b[0], y: b[1], z: cutZ, mode: "cut" },
      );
    }
    if (points.length) {
      const p = points.at(-1);
      points.push({ ...p, z: safeZ, mode: "retract" });
    }
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1],
        b = points[i];
      if (b.mode === "rapid" && (a.x !== b.x || a.y !== b.y))
        assert.equal(a.z, safeZ);
      if (b.mode === "rapid") assert.equal(b.z, safeZ);
    }
    const solid = original.extrude(4);
    assert.equal(solid.status(), "NoError");
    assert.ok(Math.abs(solid.volume() - original.area() * 4) < 1e-5);
    results.push({
      ...input,
      originalAreaMm2: original.area(),
      centerAreaMm2: region.area(),
      components,
      segments,
      points,
      centerPolygons: polygons,
      clearanceSamples: samples,
      minClearanceMm: Number.isFinite(minClearance) ? minClearance : null,
      elapsedMs: performance.now() - began,
    });
    solid.delete();
    region.delete();
    original.delete();
  }
  const wasm = await stat(
    new URL("../node_modules/manifold-3d/manifold.wasm", import.meta.url),
  );
  const pkg = JSON.parse(
    await readFile(
      new URL("../node_modules/manifold-3d/package.json", import.meta.url),
      "utf8",
    ),
  );
  return {
    experiment: "CAD-05 CNC E0",
    unit: "mm",
    environment: {
      node: process.version,
      kernel: pkg.version,
      license: pkg.license,
      wasmBytes: wasm.size,
      initializationMs,
    },
    limits: [
      "Node execution, browser and worker performance untested",
      "Single-depth scan spans, no finishing path or complete stock removal verification",
      "Sampled independent cutter clearance, not continuous machine collision proof",
      "Plunge-capable tool assumption; no machine-ready NC",
      "No OCCT/STEP/fillet experiment in this CNC-only stage",
    ],
    results,
  };
}
function svg(report) {
  const panels = report.results
    .map((r, i) => {
      const x = (i % 2) * 450,
        y = Math.floor(i / 2) * 380;
      const rings = r.rings
        .map(
          (p) => "M" + p.map((v) => `${v[0] * 4},${-v[1] * 4}`).join("L") + "Z",
        )
        .join("");
      const lines = r.segments
        .map(
          ([a, b]) =>
            `<line x1="${a[0] * 4}" y1="${-a[1] * 4}" x2="${b[0] * 4}" y2="${-b[1] * 4}" stroke="#536f83" stroke-width="1"/>`,
        )
        .join("");
      return `<g transform="translate(${x + 35},${y + 320})"><path d="${rings}" fill="#e0e5e6" fill-rule="evenodd" stroke="#1F2D3D"/>${lines}<text x="0" y="-280" font-size="18">${r.name}</text><text x="0" y="28" font-size="14">Tool Ø${r.diameter} · ${r.components} region(s) · ${r.clearanceSamples} samples</text></g>`;
    })
    .join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="790" viewBox="0 0 900 790"><rect width="900" height="790" fill="#F7F7F6"/><g fill="#1A1C1E" font-family="sans-serif">${panels}<text x="35" y="777" font-size="13">CAD-05 · Node geometry experiment · not machine-ready NC or full pocket-clearing proof</text></g></svg>`;
}
if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const report = await runExperiment(),
    dir = new URL("../../../work/cnc-e0/", import.meta.url);
  await mkdir(dir, { recursive: true });
  await writeFile(
    new URL("cnc_E0_2026-10-06_report.json", dir),
    JSON.stringify(report, null, 2),
  );
  await writeFile(new URL("cnc_E0_2026-10-06_paths.svg", dir), svg(report));
  console.log(
    JSON.stringify(
      {
        environment: report.environment,
        results: report.results.map(
          ({
            id,
            components,
            clearanceSamples,
            minClearanceMm,
            elapsedMs,
          }) => ({
            id,
            components,
            clearanceSamples,
            minClearanceMm,
            elapsedMs,
          }),
        ),
      },
      null,
      2,
    ),
  );
}
