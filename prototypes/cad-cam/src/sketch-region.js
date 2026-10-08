import clipping from "polygon-clipping";
import {
  profileRing,
  validateProfile,
  polygonDistance,
  segmentDistance,
} from "./profile.js";
export function validateHoles(s) {
  if (!s.holes) return;
  if (s.type !== "profile" || !Array.isArray(s.holes) || s.holes.length > 8)
    throw Error("내부 경계는 자유 윤곽에 최대8개입니다.");
  const outer = profileRing({ ...s, x: 0, y: 0 }),
    rings = [];
  let total = outer.length;
  for (const h of s.holes) {
    if (
      h.type !== "profile" ||
      h.x !== 0 ||
      h.y !== 0 ||
      (h.angle ?? 0) !== 0 ||
      h.holes?.length ||
      h.constraints?.length
    )
      throw Error("내부 경계는 로컬 좌표의 단일 자유 윤곽이어야 합니다.");
    validateProfile(h);
    const ring = profileRing(h);
    total += ring.length;
    if (total > 4096) throw Error("전체 영역은 최대4096근사점입니다.");
    for (const [i, a] of ring.entries()) {
      const b = ring[(i + 1) % ring.length];
      const N = Math.max(
        1,
        Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.05),
      );
      for (let j = 0; j <= N; j++) {
        const p = a.map((v, k) => v + ((b[k] - v) * j) / N);
        if (polygonDistance(outer, ...p) > -0.099)
          throw Error("내부 경계와 외곽 사이에 최소0.1mm를 남기세요.");
      }
    }
    if (clipping.difference([ring], [outer]).length)
      throw Error("내부 경계가 외곽을 벗어납니다.");
    for (const other of rings) {
      if (clipping.intersection([ring], [other]).length)
        throw Error("내부 경계는 서로 겹치거나 포함할 수 없습니다.");
      for (const a of ring)
        for (let i = 0; i < other.length; i++)
          if (segmentDistance(a, other[i], other[(i + 1) % other.length]) < 0.1)
            throw Error("내부 경계 사이에 최소0.1mm를 남기세요.");
      for (const a of other)
        for (let i = 0; i < ring.length; i++)
          if (segmentDistance(a, ring[i], ring[(i + 1) % ring.length]) < 0.1)
            throw Error("내부 경계 사이에 최소0.1mm를 남기세요.");
    }
    rings.push(ring);
  }
}
export function regionRings(s, outer) {
  return [
    outer,
    ...(s.holes ?? []).map((h) => profileRing({ ...h, x: s.x, y: s.y })),
  ];
}
