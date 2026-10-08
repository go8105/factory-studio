import * as r from "replicad";
const tol = 1e-5;
const near = (a, b) => Math.abs(a - b) <= tol;
const tuple = (v) => {
  try {
    return v.toTuple();
  } finally {
    v.delete();
  }
};
export function edgeReference(edge) {
  if (edge.geomType !== "LINE") return null;
  let a = tuple(edge.startPoint),
    b = tuple(edge.endPoint);
  if (a.join(",") > b.join(",")) [a, b] = [b, a];
  return { type: "LINE", a, b, length: edge.length };
}
export function faceReference(face) {
  if (face.geomType !== "PLANE") return null;
  const normal = tuple(face.normalAt()),
    axis = normal.findIndex((v) => Math.abs(v) > 1 - tol);
  if (axis < 0) return null;
  const plane = ["YZ", "XZ", "XY"][axis],
    basis = axis === 1 ? -1 : 1,
    sign = Math.sign(normal[axis]) * basis;
  const edges = face.edges;
  let boundary;
  try {
    if (edges.length > 256) return null;
    boundary = JSON.stringify(
      edges
        .map((e) => {
          let a = tuple(e.startPoint),
            b = tuple(e.endPoint);
          if (a.join(",") > b.join(",")) [a, b] = [b, a];
          return [
            e.geomType,
            e.length,
            ...a,
            ...tuple(e.pointAt(0.5)),
            ...b,
          ].map((v) => (typeof v === "number" ? Math.round(v * 1e6) / 1e6 : v));
        })
        .sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
    );
  } finally {
    edges.forEach((e) => e.delete());
  }
  const box = face.boundingBox,
    p = r.measureShapeSurfaceProperties(face);
  try {
    return {
      type: "PLANE",
      plane,
      sign,
      bounds: box.bounds,
      area: p.area,
      position: box.bounds[0][axis] * basis,
      boundary,
    };
  } finally {
    box.delete();
    p.delete();
  }
}
export function sameEdge(a, b) {
  return (
    a &&
    b &&
    a.type === b.type &&
    near(a.length, b.length) &&
    a.a.every((v, i) => near(v, b.a[i])) &&
    a.b.every((v, i) => near(v, b.b[i]))
  );
}
export function sameFace(a, b) {
  return (
    a &&
    b &&
    a.type === b.type &&
    a.plane === b.plane &&
    a.sign === b.sign &&
    a.boundary === b.boundary &&
    near(a.area, b.area) &&
    a.bounds.flat().every((v, i) => near(v, b.bounds.flat()[i]))
  );
}
export function directReferences(shape) {
  const edges = shape.edges,
    faces = shape.faces;
  try {
    return {
      edges: edges.map(edgeReference).filter(Boolean).slice(0, 256),
      faces: faces.map(faceReference).filter(Boolean).slice(0, 256),
    };
  } finally {
    edges.forEach((e) => e.delete());
    faces.forEach((f) => f.delete());
  }
}
export function resolveEdge(shape, reference) {
  const edges = shape.edges,
    matches = edges.filter((e) => sameEdge(reference, edgeReference(e)));
  if (matches.length !== 1) {
    edges.forEach((e) => e.delete());
    throw Error(
      "모서리 참조가 사라졌거나 중복됩니다. 현재 형상에서 다시 선택하세요.",
    );
  }
  edges.filter((e) => e !== matches[0]).forEach((e) => e.delete());
  return matches[0];
}
export function checkFace(shape, reference) {
  const faces = shape.faces;
  try {
    if (faces.filter((f) => sameFace(reference, faceReference(f))).length !== 1)
      throw Error(
        "작업면 참조가 변경됐습니다. 현재 형상에서 면을 다시 선택하세요.",
      );
  } finally {
    faces.forEach((f) => f.delete());
  }
}
export function validateReference(ref, kind) {
  if (
    kind === "face" &&
    (typeof ref?.boundary !== "string" || ref.boundary.length > 50000)
  )
    throw Error("면 경계 참조가 없습니다.");
  const nums =
    kind === "edge"
      ? [...(ref?.a ?? []), ...(ref?.b ?? []), ref?.length]
      : [...(ref?.bounds ?? []).flat(), ref?.area, ref?.position];
  if (
    nums.length !== (kind === "edge" ? 7 : 8) ||
    nums.some((v) => !Number.isFinite(v) || Math.abs(v) > 1000000)
  )
    throw Error("잘못된 기하 참조입니다.");
  if (
    kind === "edge"
      ? ref.type !== "LINE" ||
        ref.a.length !== 3 ||
        ref.b.length !== 3 ||
        ref.length <= 0
      : ref.type !== "PLANE" ||
        !["XY", "XZ", "YZ"].includes(ref.plane) ||
        ![-1, 1].includes(ref.sign) ||
        ref.bounds.length !== 2 ||
        ref.bounds.some((b) => b.length !== 3) ||
        ref.area <= 0
  )
    throw Error("지원하지 않는 기하 참조입니다.");
}
