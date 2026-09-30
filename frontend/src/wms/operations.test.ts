import { expect, it } from "vitest";
import { milli, remainder } from "./operations";
it("검수 부족을 소수 3자리 정수로 계산하고 과입력을 거부한다", () => {
  expect(remainder("0.3", "0.1", "0.2")).toBe("0.000");
  expect(remainder("100", "95", "3")).toBe("2.000");
  expect(remainder("100", "101", "0")).toBeNull();
  expect(remainder("1", "0.0001", "0")).toBeNull();
  expect(milli("-1")).toBeNull();
  expect(remainder("999999999999999.999", "999999999999999.998", "0")).toBe(
    "0.001",
  );
});
