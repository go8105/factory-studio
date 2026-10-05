import {
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
} from "./build-soap-assembly.mjs";
import fs from "node:fs";
const dir = new URL("../private/soap-poc/", import.meta.url);
// Rigid cartridge carries the drawer and lower friction plate; the user's hand
// contacts a separate elastomer sleeve/cap. No modulus or force is simulated.
let base = body.intersect(box(200, 200, 15.5));
base = base.add(cyl(35.8, 3.1, 14.9).subtract(cyl(34.4, 5, 14)));
base = base.add(
  rounded(83.2, 103.2, 7.6, 2.5, 15.5).subtract(rounded(80, 100, 6, 4, 15)),
);
let lower = rotor;
for (const x of [-31, 31]) {
  base = base.add(cyl(1.4, 3.2, 14.8).translate([x, 0, 0]));
  lower = lower.subtract(cyl(1.7, 6, -1).translate([x, 0, 0]));
}
const carrier = body.intersect(box(200, 200, 12, 33));
let sleeve = rounded(86, 106, 9, 17.5, 15.5, 64).subtract(
  rounded(83.6, 103.6, 7.8, 17.7, 15.4, 64),
);
sleeve = sleeve.warp((v) => {
  const t = (v[2] - 15.5) / 17.5;
  const factor = 1 + 0.028 * Math.sin(4 * Math.PI * t);
  v[0] *= factor;
  v[1] *= factor;
});
let cover = rounded(88, 108, 10, 5.4, 39).subtract(
  rounded(86.4, 106.4, 9.2, 3.2, 38.9),
);
cover = cover.subtract(box(66, 15, 5, 38).translate([0, 57, 0]));
const boot = rounded(88, 108, 10, 17.2, -1.2)
  .subtract(rounded(86.4, 106.4, 9.2, 18, 0))
  .subtract(box(80, 8, 13, 1.2).translate([0, -54, 0]));
report.version = "POC-03";
report.parts = [];
report.checks = [];
report.description =
  "Soft squeeze-and-twist sleeve and cap; rigid lower cartridge and friction inserts; removable drawer. Kinematic illustration, NOT elastic FEA.";
report.assumptions = {
  soap: [50, 40, 18],
  compressionTravel: 10,
  twistDegrees: 12,
  sleeveWall: 1.2,
  nozzle: 0.4,
  layer: 0.2,
  softMaterial: "TPU screening candidate; grade/hardness unselected",
  rigidMaterial: "PETG fit-test candidate; wear unverified",
  assemblyRetention:
    "Sleeve clamping/bonding and closure retention require prototype validation",
};
for (const t of [0, 30, 60, 90, 115])
  check("drawer travel " + t, base, drawer.translate([0, -t, 0]));
check("keyed lower plate", base, lower.translate([0, 0, 15]));
for (const press of [0, 5, 10])
  for (const twist of [-12, 0, 12]) {
    const moved = lid.translate([0, 0, -press]).rotate([0, 0, twist]);
    check("rigid lid/base " + press + "/" + twist, base, moved);
    check(
      "rigid lid/plate " + press + "/" + twist,
      lower.translate([0, 0, 15]),
      moved,
    );
    check(
      "carrier/base " + press + "/" + twist,
      base,
      carrier.translate([0, 0, -press]).rotate([0, 0, twist]),
    );
  }
for (const a of [0, 30, 60, 90, 110])
  check(
    "lid open " + a,
    carrier,
    lid.translate([0, -56, -39]).rotate([-a, 0, 0]).translate([0, 56, 39]),
  );
for (const t of [0, 30, 60, 115])
  check("soft boot / rigid drawer " + t, boot, drawer.translate([0, -t, 0]));
save("boot-v3", boot.translate([0, 0, 1.2]), {
  position: [0, 0, -1.2],
  material: "flexible",
});
save("base-v3", base, { position: [0, 0, 0], material: "rigid" });
save("carrier-v3", carrier.translate([0, 0, -33]), {
  position: [0, 0, 33],
  material: "rigid",
});
save("lid-v3", lid.rotate([180, 0, 0]).translate([0, 0, 43]), {
  rotation: [180, 0, 0],
  position: [0, 0, 43],
  material: "rigid",
});
save("plate-v3", lower, { position: [0, 0, 15], material: "rigid" });
save("drawer-v3", drawer.translate([0, 0, -1.8]), {
  position: [0, 0, 1.8],
  material: "rigid",
});
save("hinge-pin-v3", pin, {
  rotation: [0, 90, 0],
  position: [-30, 56, 39],
  material: "rigid",
});
save("sleeve-v3", sleeve.translate([0, 0, -15.5]), {
  position: [0, 0, 15.5],
  material: "flexible",
});
save("cover-v3", cover.rotate([180, 0, 0]).translate([0, 0, 44.4]), {
  rotation: [180, 0, 0],
  position: [0, 0, 44.4],
  material: "flexible",
});
fs.writeFileSync(
  new URL("assembly-v3.json", dir),
  JSON.stringify(report, null, 2) + "\n",
);
console.log(
  "POC-03: " +
    report.parts.length +
    " solids, " +
    report.checks.length +
    " rigid clearance samples passed; elastomer self-contact NOT verified",
);
