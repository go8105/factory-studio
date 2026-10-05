import Module from "manifold-3d";
import fs from "node:fs";
const mod = await Module();
mod.setup();
const { Manifold: M, CrossSection: C } = mod;
const dir = new URL("../private/soap-poc/", import.meta.url);
fs.mkdirSync(dir, { recursive: true });
const box = (w, d, h, z = 0) =>
  M.cube([w, d, h], true).translate([0, 0, z + h / 2]);
function rounded(w, d, r, h, z = 0, divisions = 0) {
  const pts = [];
  for (const [x, y, a] of [
    [w / 2 - r, d / 2 - r, 0],
    [-w / 2 + r, d / 2 - r, 90],
    [-w / 2 + r, -d / 2 + r, 180],
    [w / 2 - r, -d / 2 + r, 270],
  ])
    for (let j = 0; j <= 8; j++) {
      const t = ((a + (j * 90) / 8) * Math.PI) / 180;
      pts.push([x + r * Math.cos(t), y + r * Math.sin(t)]);
    }
  return new C([pts]).extrude(h, divisions).translate([0, 0, z]);
}
const cyl = (r, h, z = 0) => M.cylinder(h, r, r, 96).translate([0, 0, z]);
const knuckle = (length, x) =>
  cyl(4, length)
    .subtract(cyl(1.9, length + 2, -1))
    .rotate([0, 90, 0])
    .translate([x, 56, 39]);
let body = rounded(86, 106, 9, 39)
  .subtract(rounded(74, 96, 4, 11, 2))
  .subtract(rounded(80, 100, 6, 26, 15))
  .subtract(cyl(29, 4, 12.5));
body = body.subtract(box(74, 14, 11, 2).translate([0, -53, 0]));
body = body.add(cyl(35.8, 3.1, 14.9).subtract(cyl(34.4, 5, 14)));
body = body.subtract(box(16, 26, 10, 14.5).translate([39, 0, 0]));
body = body.subtract(box(34, 12, 12, 33).translate([0, 57, 0]));
for (const x of [-28, 18])
  body = body
    .add(knuckle(10, x))
    .add(box(10, 7, 6, 33).translate([x + 5, 52, 0]));
// Re-cut bores after the support webs have been joined.
body = body.subtract(cyl(1.9, 62).rotate([0, 90, 0]).translate([-31, 56, 39]));
let lid = rounded(86, 106, 9, 3, 39)
  .add(knuckle(32, -16))
  .add(box(32, 7, 3, 39).translate([0, 52.5, 0]));
lid = lid.subtract(cyl(1.9, 62).rotate([0, 90, 0]).translate([-31, 56, 39]));
for (const x of [-28.4, 17.6])
  lid = lid.subtract(cyl(4.4, 10.8).rotate([0, 90, 0]).translate([x, 56, 39]));
lid = lid.add(rounded(54, 44, 3, 1.1, 37.9));
const teeth = [],
  slots = [],
  grips = [];
for (let i = -2; i <= 2; i++)
  for (let j = -2; j <= 2; j++) {
    if (i === 0 && j === 0) continue;
    const x = i * 8,
      y = j * 8,
      a = (Math.atan2(y, x) * 180) / Math.PI + 90;
    teeth.push(
      new C([
        [
          [-1.5, -0.05],
          [1.5, -0.05],
          [-1.5, 1],
        ],
      ])
        .extrude(4)
        .rotate([90, 0, 0])
        .translate([0, 2, 3])
        .rotate([0, 0, a])
        .translate([x, y, 0]),
    );
    slots.push(
      box(1.2, 4, 5, -1)
        .translate([-2.4, 0, 0])
        .rotate([0, 0, a])
        .translate([x, y, 0]),
    );
    // The lid's pyramids grip the soap while the lower disc rotates.
    grips.push(
      new C([
        [
          [-1.5, -1.5],
          [1.5, -1.5],
          [1.5, 1.5],
          [-1.5, 1.5],
        ],
      ])
        .extrude(1.1, 0, 0, [0, 0])
        .rotate([180, 0, 0])
        .translate([x, y, 38.1]),
    );
  }
lid = M.union([lid, ...grips]);
let rotor = M.union([cyl(34, 3), ...teeth]).subtract(M.union(slots));
let drawer = rounded(72.8, 99.8, 3, 10.2).translate([0, -3.5, 2.4]);
drawer = drawer.subtract(
  rounded(68.8, 95.8, 2, 12, 4.4).translate([0, -3.5, 0]),
);
drawer = drawer.add(box(78, 2.1, 11.4, 1.8).translate([0, -54.35, 0]));
const pin = cyl(1.5, 60);
const report = {
  version: "POC-02",
  unit: "mm",
  description:
    "Hinged lid, internal friction rotor, fully removable drawer. Digital fit only.",
  parts: [],
  checks: [],
  assumptions: {
    soap: [50, 40, 18],
    nozzle: 0.4,
    layer: 0.2,
    drawerSideClearance: 0.6,
    rotorRadialClearance: 0.4,
    hingeAxis: [0, 56, 39],
  },
};
function save(name, solid, assembly) {
  if (
    solid.status() !== "NoError" ||
    solid.decompose().length !== 1 ||
    solid.volume() <= 0
  )
    throw Error(name + " invalid " + solid.status());
  const mesh = solid.getMesh(),
    tri = mesh.triVerts,
    v = mesh.vertProperties,
    s = mesh.numProp,
    out = Buffer.alloc(84 + (tri.length / 3) * 50);
  out.write(`SOAP ${report.version} / mm / untested physical prototype`);
  out.writeUInt32LE(tri.length / 3, 80);
  for (let i = 0; i < tri.length; i += 3)
    for (let j = 0; j < 3; j++)
      for (let k = 0; k < 3; k++)
        out.writeFloatLE(
          v[tri[i + j] * s + k],
          84 + (i / 3) * 50 + 12 + j * 12 + k * 4,
        );
  fs.writeFileSync(new URL(name + ".stl", dir), out);
  report.parts.push({
    name,
    volumeMm3: solid.volume(),
    bounds: solid.boundingBox(),
    assembly,
  });
}
function check(name, a, b) {
  const volume = Math.abs(a.intersect(b).volume());
  report.checks.push({ name, overlapMm3: volume });
  if (volume > 1e-4) throw Error(name + " collision " + volume);
}
for (const t of [0, 10, 30, 60, 90, 115])
  check("drawer travel " + t, body, drawer.translate([0, -t, 0]));
for (const a of [0, 30, 60, 90, 120, 180, 270])
  check(
    "rotor angle " + a,
    body,
    rotor.rotate([0, 0, a]).translate([0, 0, 15]),
  );
for (const a of [0, 15, 30, 60, 90, 110]) {
  const opened = lid
    .translate([0, -56, -39])
    .rotate([-a, 0, 0])
    .translate([0, 56, 39]);
  check("lid angle " + a, body, opened);
}
check("lid / rotor closed", lid, rotor.translate([0, 0, 15]));
check("drawer / rotor", drawer, rotor.translate([0, 0, 15]));
save("body-v2", body, { position: [0, 0, 0] });
// Flat outer lid face down for printing; invert this transform in the viewer.
save("lid-v2", lid.rotate([180, 0, 0]).translate([0, 0, 43]), {
  rotation: [180, 0, 0],
  position: [0, 0, 43],
});
save("rotor-v2", rotor, { position: [0, 0, 15] });
save("drawer-v2", drawer.translate([0, 0, -1.8]), { position: [0, 0, 1.8] });
save("hinge-pin-v2", pin, { rotation: [0, 90, 0], position: [-30, 56, 39] });
fs.writeFileSync(
  new URL("assembly-v2.json", dir),
  JSON.stringify(report, null, 2) + "\n",
);
console.log(
  "POC-02: " +
    report.parts.length +
    " solids, " +
    report.checks.length +
    " collision samples passed",
);

export {
  M,
  rounded,
  box,
  cyl,
  body,
  lid,
  rotor,
  drawer,
  pin,
  save,
  report,
  check,
};
