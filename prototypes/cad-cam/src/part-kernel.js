import { resolveEdge, checkFace } from "./part-references.js";
import * as r from "replicad";
import { validatePart } from "./part-model.js";
export const setKernel = r.setOC;
const normal = { XY: [0, 0, 1], XZ: [0, -1, 0], YZ: [1, 0, 0] };
export function planePosition(f, history) {
  if (f.supportFace) return f.supportFace.position + f.offset;
  if (f.referenceId === "world") return f.offset;
  const box = history.get(f.referenceId);
  if (!box) throw Error("기준 피처를 찾을 수 없습니다.");
  return { XY: box[1][2], XZ: -box[0][1], YZ: box[1][0] }[f.plane] + f.offset;
}
function drawing(s) {
  const holes = s.holes ?? [];
  let d;
  if (s.type === "circle") d = r.drawCircle(s.w / 2);
  else if (s.type === "profile") {
    let path = r.draw(s.nodes[0].point);
    for (let i = 0; i < s.nodes.length; i++) {
      const n = s.nodes[i],
        b = s.nodes[(i + 1) % s.nodes.length].point;
      if (n.arcVia) path = path.threePointsArcTo(b, n.arcVia);
      else if (i < s.nodes.length - 1) path = path.lineTo(b);
    }
    d = path.close();
  } else
    d = r.drawRoundedRectangle(
      s.w,
      s.h,
      s.type === "slot" ? s.h / 2 : s.radius,
    );
  for (const hole of holes) d = d.cut(drawing(hole));
  return d.rotate(s.angle ?? 0).translate(s.x, s.y);
}
function stats(shape) {
  const box = shape.boundingBox,
    p = r.measureShapeVolumeProperties(shape);
  try {
    return { volume: p.volume, bounds: box.bounds };
  } finally {
    p.delete();
    box.delete();
  }
}
function verify(shape) {
  const solids = shape.solids;
  const count = solids.length;
  solids.forEach((s) => s.delete());
  if (count !== 1)
    throw Error(
      "하나로 연결된 부품이 필요합니다. 떨어진 돌출 또는 분리 절삭을 확인하세요.",
    );
  const oc = r.getOC(),
    check = new oc.BRepCheck_Analyzer(shape.wrapped, true, false);
  try {
    if (!check.IsValid()) throw Error("유효한 솔리드를 만들지 못했습니다.");
  } finally {
    check.delete();
  }
  const info = stats(shape);
  if (
    !Number.isFinite(info.volume) ||
    info.volume < 0.001 ||
    info.bounds.flat().some((v) => Math.abs(v) > 400)
  )
    throw Error("빈 형상 또는400mm 작업 범위 초과입니다.");
  return info;
}
export function buildPart(model) {
  validatePart(model);
  let shape;
  const operands = new Map(),
    history = new Map(),
    steps = [];
  try {
    shape = drawing(model.base).sketchOnPlane("XY").extrude(model.base.height);
    history.set("base", verify(shape).bounds);
    for (const f of model.operations) {
      let next, operand;
      const before = stats(shape).volume,
        start = performance.now();
      try {
        if (["add", "cut"].includes(f.kind)) {
          if (f.supportFace) checkFace(shape, f.supportFace);
          operand = drawing(f.sketch)
            .sketchOnPlane(f.plane, planePosition(f, history))
            .extrude(
              (f.kind === "add" ? f.amount : -f.amount) *
                (f.supportFace?.sign ?? 1),
            );
          operands.set(f.id, { shape: operand.clone(), kind: f.kind });
          next = f.kind === "add" ? shape.fuse(operand) : shape.cut(operand);
        } else if (["fillet", "chamfer"].includes(f.kind)) {
          const pos = planePosition(f, history),
            method = f.kind;
          if (f.scope === "edge") {
            const edge = resolveEdge(shape, f.edgeReference);
            try {
              next = shape[method](f.radius, (e) => e.inList([edge]));
            } finally {
              edge.delete();
            }
          } else
            next =
              f.scope === "all"
                ? shape[method](f.radius)
                : shape[method](f.radius, (e) => e.inPlane(f.plane, pos));
        } else if (f.kind === "shell")
          next = shape.shell(f.thickness, (e) =>
            e.inPlane(f.plane, planePosition(f, history)),
          );
        else {
          const source = operands.get(f.sourceId);
          next = shape.clone();
          const count = f.kind === "mirror" ? 2 : f.count;
          for (let i = 1; i < count; i++) {
            operand = source.shape.clone();
            if (f.kind === "mirror") {
              const pos = planePosition(f, history);
              operand = operand.mirror(
                f.plane,
                normal[f.plane].map((v) => v * pos),
              );
            } else if (f.mode === "linear") {
              const offset = {
                X: [f.spacing * i, 0, 0],
                Y: [0, f.spacing * i, 0],
                Z: [0, 0, f.spacing * i],
              }[f.axis];
              operand = operand.translate(offset);
            } else operand = operand.rotate(f.angle * i, f.center, f.axis);
            const combined =
              source.kind === "add" ? next.fuse(operand) : next.cut(operand);
            next.delete();
            next = combined;
            operand.delete();
            operand = null;
          }
        }
        const info = verify(next);
        if (Math.abs(info.volume - before) < 1e-6)
          throw Error(
            "피처가 부품을 변경하지 않습니다. 위치·평면·대상 범위를 확인하세요.",
          );
        shape.delete();
        shape = next;
        next = null;
        history.set(f.id, info.bounds);
        steps.push({
          id: f.id,
          name: f.name,
          volume: info.volume,
          milliseconds: performance.now() - start,
        });
      } catch (error) {
        const failure = new Error(
          typeof error === "number"
            ? `형상 커널 오류(${error}). 치수나 범위를 바꿔보세요.`
            : error.message,
        );
        failure.featureId = f.id;
        failure.featureName = f.name;
        failure.steps = steps;
        throw failure;
      } finally {
        next?.delete();
        operand?.delete();
      }
    }
    return { shape, info: stats(shape), steps };
  } catch (error) {
    shape?.delete();
    throw error;
  } finally {
    for (const value of operands.values()) value.shape.delete();
  }
}
