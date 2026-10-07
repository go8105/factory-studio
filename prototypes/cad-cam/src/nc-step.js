import * as r from "replicad";
export async function readReference(blob) {
  if (blob.size > 10 * 1024 * 1024) throw Error("STEP10MiB 상한 초과");
  let shape;
  try {
    shape = await r.importSTEP(blob);
    if (!(shape instanceof r.Solid))
      throw Error("단일 Solid STEP만 지원 (조립/쉘 제외)");
    const volume = r.measureVolume(shape);
    if (!Number.isFinite(volume) || volume <= 0)
      throw Error("유효한 STEP 체적 필요");
    const mesh = shape.mesh({ tolerance: 0.05, angularTolerance: 0.2 });
    if (mesh.triangles.length > 60000)
      throw Error("STEP20,000삼각형 상한 초과");
    return { solid: true, volume, mesh };
  } finally {
    shape?.delete();
  }
}
