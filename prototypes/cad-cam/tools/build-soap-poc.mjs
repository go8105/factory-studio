import Module from "manifold-3d";
import fs from "node:fs";
const { Manifold: M, CrossSection: C } = await Module().then((m) => {
  m.setup();
  return m;
});
const dir = new URL("../private/soap-poc/", import.meta.url);
fs.mkdirSync(dir, { recursive: true });
const box = (x, y, z, b = 0) =>
  M.cube([x, y, z], true).translate([0, 0, b + z / 2]);
const tray = box(84, 64, 14)
  .subtract(box(74.4, 54.4, 20, 2.4))
  .subtract(box(79.2, 59.2, 10, 10));
const report = {
  unit: "mm",
  seatZ: 10,
  lateralClearancePerSide: 0.4,
  parts: [],
};
function save(name, solid) {
  if (
    solid.status() !== "NoError" ||
    solid.decompose().length !== 1 ||
    solid.volume() <= 0
  )
    throw Error(name + " invalid solid");
  const mesh = solid.getMesh(),
    tri = mesh.triVerts,
    v = mesh.vertProperties,
    s = mesh.numProp;
  const out = Buffer.alloc(84 + (tri.length / 3) * 50);
  out.write("SOAP POC-01 / millimeters / physical performance untested");
  out.writeUInt32LE(tri.length / 3, 80);
  for (let i = 0; i < tri.length; i += 3) {
    const off = 84 + (i / 3) * 50;
    for (let j = 0; j < 3; j++)
      for (let k = 0; k < 3; k++)
        out.writeFloatLE(v[tri[i + j] * s + k], off + 12 + j * 12 + k * 4);
  }
  fs.writeFileSync(new URL(name + ".stl", dir), out);
  report.parts.push({
    name,
    volumeMm3: solid.volume(),
    bounds: solid.boundingBox(),
    triangles: tri.length / 3,
    status: solid.status(),
  });
}
save("tray", tray);
for (const [label, h] of [
  ["A", 0.6],
  ["B", 1],
  ["C", 1.4],
]) {
  let plate = box(78.4, 58.4, 3);
  const teeth = [],
    slots = [];
  for (let i = -3; i <= 3; i++)
    for (let j = -2; j <= 2; j++) {
      teeth.push(
        new C([
          [
            [-1.5, -0.05],
            [1.5, -0.05],
            [-1.5, h],
          ],
        ])
          .extrude(4)
          .rotate([90, 0, 0])
          .translate([i * 8, j * 8 + 2, 3]),
      );
      slots.push(box(1.2, 4, 5, -1).translate([i * 8 - 2.4, j * 8, 0]));
    }
  plate = M.union([plate, ...teeth]).subtract(M.union(slots));
  const overlap = plate.translate([0, 0, 10]).intersect(tray).volume();
  if (overlap > 1e-6) throw Error("assembly collision");
  save("plate-" + label, plate);
  report.parts.at(-1).toothHeight = h;
  report.parts.at(-1).assemblyOverlapMm3 = overlap;
}
fs.writeFileSync(
  new URL("geometry-report.json", dir),
  JSON.stringify(report, null, 2) + "\n",
);
console.log(JSON.stringify(report, null, 2));
