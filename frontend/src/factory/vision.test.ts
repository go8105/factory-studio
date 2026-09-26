import { expect, it } from "vitest";
import { visionAt } from "./vision";
it("검사 중에는 제품이 중앙에서 멈추고 판정 수량은 증가하지 않는다", () => {
  expect(visionAt(2.5)).toMatchObject({
    x: 0,
    scanning: true,
    inspected: 0,
    result: "판정 대기",
  });
});
it("판정 시점에만 수량이 증가하고 다섯 번째 제품이 불합격이다", () => {
  expect(visionAt(27.4).inspected).toBe(4);
  expect(visionAt(27.5)).toMatchObject({
    inspected: 5,
    rejected: 1,
    result: "불합격",
  });
  expect(visionAt(30)).toMatchObject({
    inspected: 5,
    rejected: 1,
    result: "판정 대기",
  });
});
it("이상 상태에서는 검사 조명이 꺼진다", () => {
  expect(visionAt(2.5, true)).toMatchObject({
    scanning: false,
    phase: "이상 정지",
  });
});
