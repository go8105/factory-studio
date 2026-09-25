import { expect, it } from "vitest";
import { START, canStand, inputVector, move } from "./world";
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
