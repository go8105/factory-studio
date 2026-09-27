import { expect, it } from "vitest";
import { defaultRecipe, inspect, type Recipe, type Sample } from "./inspection";
const run = (sample: Sample, overrides: Partial<Recipe> = {}) =>
  inspect({ version: 1, sample, recipe: { ...defaultRecipe, ...overrides } });
it("기본 조건은 정상 잡음을 거르고 두 이물을 정확히 찾는다", () => {
  expect(run("normal")).toMatchObject({
    status: "OK",
    falsePixels: 0,
    missedPixels: 0,
  });
  const result = run("foreign");
  expect(result.regions.map((r) => r.area)).toEqual([80, 36]);
  expect(result).toMatchObject({
    status: "NG",
    falsePixels: 0,
    missedPixels: 0,
  });
});
it("면적 증가와 낮은 임계값이 미검출을 드러낸다", () => {
  expect(run("foreign", { minArea: 100 })).toMatchObject({
    status: "OK",
    missedPixels: 116,
  });
  expect(run("foreign", { threshold: 45 })).toMatchObject({
    status: "OK",
    missedPixels: 116,
  });
});
it("조명 영역과 작은 잡음을 오검출로 계산한다", () => {
  expect(run("lighting", { threshold: 130 }).falsePixels).toBe(4000);
  expect(run("normal", { minArea: 1 }).falsePixels).toBe(4);
});
it("영역 밖 결함을 미검출과 구분한다", () => {
  expect(run("foreign", { roi: "center" })).toMatchObject({
    missedPixels: 0,
    excludedPixels: 36,
  });
  expect(run("foreign", { roi: "center" }).regions).toHaveLength(1);
});
it("잘못된 조건을 거부하고 입력을 변경하지 않는다", () => {
  expect(() => run("normal", { threshold: NaN })).toThrow();
  expect(() => run("normal", { minArea: 0 })).toThrow();
  expect(run("foreign")).toEqual(run("foreign"));
  expect(defaultRecipe).toEqual({ threshold: 90, minArea: 20, roi: "full" });
});
