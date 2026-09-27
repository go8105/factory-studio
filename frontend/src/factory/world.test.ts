import { expect, it } from "vitest";
import { START, canStand, inputVector, move, relativeStep } from "./world";
it("방문자 시작 위치는 장애물 밖이다", () =>
  expect(canStand(START)).toBe(true));
it("조립 설비 안으로 들어갈 수 없다", () =>
  expect(canStand({ x: -0.5, y: 0, z: 0 })).toBe(false));
it("2층에서는 바닥 밖으로 나갈 수 없다", () =>
  expect(canStand({ x: 0, y: 4, z: 5 })).toBe(false));
it("사무실 책상과 충돌한다", () =>
  expect(canStand({ x: -8, y: 4, z: 1 })).toBe(false));
it("대각 이동도 직선과 같은 속도다", () => {
  const diagonal = inputVector(new Set(["up", "right"]), 0.04);
  expect(Math.hypot(diagonal.x, diagonal.z)).toBeCloseTo(0.12);
});
it("프레임이 지연돼도 장애물을 뛰어넘지 않는다", () =>
  expect(inputVector(new Set(["up"]), 2).z).toBeCloseTo(-0.15));
it("계단으로 1층에서 2층까지 걸어 올라간다", () => {
  let p = { x: -4.15, y: 0, z: 6.2 };
  for (let i = 0; i < 46; i++) p = move(p, 0, -0.1);
  expect(p.y).toBe(4);
});
it("계단으로 2층에서 1층까지 내려간다", () => {
  let p = { x: -4.15, y: 4, z: 1.8 };
  for (let i = 0; i < 46; i++) p = move(p, 0, 0.1);
  expect(p.y).toBe(0);
});
it("계단 중간에서 옆으로 뛰어내릴 수 없다", () => {
  const p = { x: -4.95, y: 2, z: 4 };
  expect(move(p, -0.15, 0)).toEqual(p);
});
it("창 바깥으로 이동할 수 없다", () =>
  expect(move({ x: 10.65, y: 0, z: 5 }, 0.15, 0).x).toBe(10.65));
it("자재 선반과 공구대 안으로 들어갈 수 없다", () => {
  expect(canStand({ x: 0, y: 0, z: -5 })).toBe(false);
  expect(canStand({ x: -1, y: 0, z: -3.7 })).toBe(false);
  expect(canStand({ x: 4, y: 0, z: -2.8 })).toBe(true);
});

it("1인칭 검사 시작점은 안전하며 작업자와 설비를 통과하지 않는다", () => {
  expect(canStand({ x: 4, y: 0, z: 4.6 })).toBe(true);
  expect(canStand({ x: 2.35, y: 0, z: 2.15 })).toBe(false);
  let p = { x: 4, y: 0, z: 4.6 };
  for (let i = 0; i < 100; i++) p = move(p, 0, -0.15);
  expect(p.z).toBeGreaterThanOrEqual(1.58);
  expect(p.z).toBeLessThan(1.8);
});
it("1인칭 전진은 바라보는 방향을 따른다", () => {
  expect(relativeStep(0, -1, 0)).toEqual({ x: 0, z: -1 });
  expect(relativeStep(0, -1, Math.PI / 2).x).toBeCloseTo(-1);
  expect(relativeStep(1, 0, Math.PI / 2).z).toBeCloseTo(-1);
});
