import { validateReference } from "./part-references.js";
import { designJSON, clone, parseModel, validateShape } from "./model.js";
import { syncProfile } from "./profile.js";
import { solveSketch } from "./sketch-constraints.js";
export const partKey = (scope) =>
  `form-studio-part-v3${scope ? ":" + scope : ""}`;
export const emptyPart = () => ({
  version: 3,
  name: "새 3D 부품",
  base: {
    id: "base",
    type: "rect",
    x: 0,
    y: 0,
    w: 60,
    h: 40,
    radius: 0,
    height: 10,
  },
  operations: [],
});
const check = (v, lo, hi, label) => {
  if (!Number.isFinite(v) || v < lo || v > hi)
    throw Error(`${label}: ${lo}~${hi} 범위가 필요합니다.`);
};
const planes = ["XY", "XZ", "YZ"];
export function importPart(text) {
  if (text.length > 250000) throw Error("250KB 이하 설계만 읽습니다.");
  const raw = JSON.parse(text);
  if (raw.version === 3) return validatePart(raw);
  const old = parseModel(text);
  if (!old.stock) throw Error("기본 돌출이 있는 설계를 가져오세요.");
  return validatePart({
    version: 3,
    name: old.name,
    base: { ...old.stock, id: "base" },
    operations: old.features.map((f) => ({
      id: f.id,
      name: f.name,
      kind: "cut",
      sketch: clone(f),
      plane: "XY",
      referenceId: "base",
      offset: 0,
      amount: f.depth,
    })),
  });
}
export function validatePart(m) {
  designJSON(m, 250000);
  if (
    m?.version !== 3 ||
    typeof m.name !== "string" ||
    m.name.length > 80 ||
    !Array.isArray(m.operations) ||
    m.operations.length > 32
  )
    throw Error("지원하지 않는 3D 설계 파일입니다.");
  if (m.base?.id !== "base" || m.base.kind)
    throw Error("기본 돌출 ID는 base입니다.");
  if (m.base?.constraints !== undefined && !Array.isArray(m.base.constraints))
    throw Error("구속 목록이 잘못되었습니다.");
  validateShape(m.base);
  check(m.base.angle ?? 0, -180, 180, "스케치 회전");
  if (
    m.base.type === "profile" &&
    m.base.constraints?.length &&
    solveSketch(m.base).changed
  )
    throw Error("기본 돌출: 구속을 적용한 뒤 저장하세요.");
  check(m.base.height, 1, 80, "기본 높이");
  const ids = new Map([["base", { kind: "base" }]]);
  let instances = 0;
  for (const f of m.operations) {
    if (
      typeof f.id !== "string" ||
      !/^[a-zA-Z0-9_-]{1,64}$/.test(f.id) ||
      ids.has(f.id) ||
      typeof f.name !== "string" ||
      f.name.length > 80
    )
      throw Error("피처 ID/이름이 잘못되거나 중복되었습니다.");
    if (
      ![
        "add",
        "cut",
        "fillet",
        "chamfer",
        "shell",
        "pattern",
        "mirror",
      ].includes(f.kind)
    )
      throw Error("지원하지 않는 피처입니다.");
    if (
      ["add", "cut", "fillet", "chamfer", "shell", "mirror"].includes(f.kind)
    ) {
      if (!planes.includes(f.plane))
        throw Error("작업면은 XY/XZ/YZ 중 선택하세요.");
      if (f.referenceId !== "world" && !ids.has(f.referenceId))
        throw Error(`${f.name}: 선행 피처 ${f.referenceId} 참조가 없습니다.`);
      check(f.offset, -200, 200, "평면 이동");
    }
    if (["add", "cut"].includes(f.kind)) {
      if (
        f.sketch?.constraints !== undefined &&
        !Array.isArray(f.sketch.constraints)
      )
        throw Error("구속 목록이 잘못되었습니다.");
      validateShape(f.sketch);
      check(f.amount, 0.1, 100, "돌출/파내기 거리");
      check(f.sketch.angle ?? 0, -180, 180, "스케치 회전");
      if (f.sketch.type === "profile" && (f.sketch.constraints?.length ?? 0)) {
        const solved = solveSketch(f.sketch);
        if (solved.changed)
          throw Error(`${f.name}: 구속을 적용한 뒤 저장하세요.`);
      }
      instances++;
    }
    if (["fillet", "chamfer"].includes(f.kind)) {
      check(f.radius, 0.1, 30, "필렛 반경");
      if (!["all", "plane", "edge"].includes(f.scope))
        throw Error("필렛 범위를 선택하세요.");
    }
    if (f.scope === "edge") validateReference(f.edgeReference, "edge");
    if (f.supportFace) {
      validateReference(f.supportFace, "face");
      if (!["add", "cut"].includes(f.kind) || f.plane !== f.supportFace.plane)
        throw Error("작업면 참조와 피처 평면이 다릅니다.");
    }
    if (f.kind === "shell") check(f.thickness, 0.1, 20, "벽 두께");
    if (["pattern", "mirror"].includes(f.kind)) {
      if (!["add", "cut"].includes(ids.get(f.sourceId)?.kind))
        throw Error(`${f.name}: 선행 돌출/파내기 피처를 원본으로 선택하세요.`);
      if (f.kind === "pattern") {
        if (
          !["linear", "circular"].includes(f.mode) ||
          !["X", "Y", "Z"].includes(f.axis) ||
          !Number.isInteger(f.count)
        )
          throw Error("배열 설정이 잘못되었습니다.");
        check(f.count, 2, 16, "배열 개수");
        check(f.spacing, 0.1, 100, "배열 간격");
        check(f.angle, -180, 180, "배열 각도");
        if (!Array.isArray(f.center) || f.center.length !== 3)
          throw Error("회전 중심 3개 좌표가 필요합니다.");
        f.center.forEach((v) => check(v, -200, 200, "회전 중심"));
        instances += f.count - 1;
      } else instances++;
    }
    if (instances > 128) throw Error("총 피처 인스턴스는 최대128개입니다.");
    ids.set(f.id, f);
  }
  return m;
}
export function prepareSketch(s) {
  const out = clone(s);
  if (out.type === "profile") {
    if (out.constraints?.length) return solveSketch(out).sketch;
    syncProfile(out);
  }
  return out;
}
export function bracketExample() {
  const m = emptyPart();
  m.name = "측면 구멍 CNC 브래킷";
  m.base.w = 70;
  m.base.h = 50;
  m.base.height = 8;
  const rect = (w, h, x = 0, y = 0) => ({
    type: "rect",
    x,
    y,
    w,
    h,
    radius: 0,
    angle: 0,
  });
  m.operations = [
    {
      id: "upright",
      name: "세로 벽",
      kind: "add",
      plane: "XY",
      referenceId: "base",
      offset: 0,
      amount: 28,
      sketch: rect(60, 8, 0, 18),
    },
    {
      id: "side-hole",
      name: "측면 관통 구멍",
      kind: "cut",
      plane: "XZ",
      referenceId: "upright",
      offset: 0,
      amount: 60,
      sketch: {
        type: "circle",
        x: -18,
        y: 22,
        w: 8,
        h: 8,
        radius: 0,
        angle: 0,
      },
    },
    {
      id: "hole-array",
      name: "구멍 직선 배열",
      kind: "pattern",
      sourceId: "side-hole",
      mode: "linear",
      axis: "X",
      count: 3,
      spacing: 18,
      angle: 30,
      center: [0, 0, 0],
    },
  ];
  return m;
}
export function shellExample() {
  const m = emptyPart();
  m.name = "필렛과 쉘 연습 케이스";
  m.base.height = 24;
  m.operations = [
    {
      id: "shell",
      name: "윗면 개방 쉘",
      kind: "shell",
      plane: "XY",
      referenceId: "base",
      offset: 0,
      thickness: 2,
    },
    {
      id: "fillet",
      name: "밑면 모서리 필렛",
      kind: "fillet",
      scope: "plane",
      plane: "XY",
      referenceId: "world",
      offset: 0,
      radius: 1,
    },
  ];
  return m;
}
