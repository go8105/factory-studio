export type Point = { x: number; y: number; z: number };
export type View = "all" | "ground" | "office";
export type Direction = "up" | "down" | "left" | "right";
export const START: Point = { x: 1, y: 0, z: 5 };
export const OFFICE_START: Point = { x: -6, y: 4, z: 5 };
export const stations = [
  {
    x: -0.5,
    name: "01 조립",
    detail: "부품을 투입하고 조립합니다. 키오스크에서 작업지시를 확인합니다.",
  },
  {
    x: 4,
    name: "02 비전검사",
    detail:
      "카메라와 조명으로 제품의 외관을 검사합니다. 화면의 판정은 시연입니다.",
  },
  {
    x: 8.5,
    name: "03 포장",
    detail: "검사한 제품을 포장합니다. 이송 구간을 따라 세 공정이 이어집니다.",
  },
];
const groundBlocks = [
  { x: 2.35, z: 2.15, w: 0.65, d: 0.65 },
  ...[0, 4, 8].map((x) => ({ x, z: -5, w: 2.1, d: 1.1 })),
  { x: -1, z: -3.7, w: 1.3, d: 0.65 },
  { x: 10.4, z: -3.3, w: 0.65, d: 0.55 },
  ...stations.map(({ x }) => ({ x, z: 0, w: 2.8, d: 2.6 })),
  { x: 1.75, z: 0, w: 1.7, d: 1 },
  { x: 6.25, z: 0, w: 1.7, d: 1 },
  { x: -8, z: -3.5, w: 3, d: 2.2 },
  { x: -8, z: 0, w: 2.6, d: 1.2 },
  { x: -3, z: -2.5, w: 0.2, d: 9 },
  ...stations.map(({ x }) => ({ x: x + 1.25, z: 2, w: 0.7, d: 0.6 })),
];
const officeBlocks = [-3.5, 1].map((z) => ({ x: -8, z, w: 3, d: 2.3 }));
export function canStand(p: Point): boolean {
  if (p.x < -10.5 || p.x > 10.7 || p.z < -6.4 || p.z > 6.5) return false;
  if (p.y >= 3.9 && p.x > -3.3) return false;
  const blocks = p.y >= 3.9 ? officeBlocks : p.y < 0.1 ? groundBlocks : [];
  return !blocks.some(
    (b) =>
      Math.abs(p.x - b.x) < b.w / 2 + 0.28 &&
      Math.abs(p.z - b.z) < b.d / 2 + 0.28,
  );
}
function height(p: Point, previous: Point): number {
  if (p.x >= -5 && p.x <= -3.3 && p.z >= 2 && p.z <= 6) return 6 - p.z;
  return previous.y > 2 ? 4 : 0;
}
export function move(p: Point, dx: number, dz: number): Point {
  let next = { ...p };
  // Separate axes let a visitor slide along a wall, rather than get stuck.
  for (const delta of [
    { x: dx, z: 0 },
    { x: 0, z: dz },
  ]) {
    const candidate = { ...next, x: next.x + delta.x, z: next.z + delta.z };
    candidate.y = height(candidate, next);
    if (Math.abs(candidate.y - next.y) <= 0.3 && canStand(candidate))
      next = candidate;
  }
  return next;
}
export function inputVector(keys: Set<Direction>, seconds: number) {
  const x = Number(keys.has("right")) - Number(keys.has("left"));
  const z = Number(keys.has("down")) - Number(keys.has("up"));
  const length = Math.hypot(x, z) || 1;
  const distance = Math.min(seconds, 0.05) * 3;
  return { x: (x / length) * distance, z: (z / length) * distance };
}

export function relativeStep(x: number, z: number, yaw: number) {
  return {
    x: x * Math.cos(yaw) + z * Math.sin(yaw),
    z: -x * Math.sin(yaw) + z * Math.cos(yaw),
  };
}
