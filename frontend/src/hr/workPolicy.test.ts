import { expect, it } from "vitest";
import { examplePolicy, paidMinutes, policySchedule } from "./workPolicy";

it("기본 정책과 휴게 경계의 반차는 각각 절반을 차감한다", () => {
  for (const policy of [
    examplePolicy,
    { ...examplePolicy, start_time: "08:00", end_time: "17:00" },
    {
      ...examplePolicy,
      start_time: "08:30:00",
      end_time: "16:30:00",
      break_start: "11:30:00",
      break_end: "12:30:00",
      daily_minutes: 420,
    },
  ]) {
    const schedule = policySchedule(policy)!;
    expect(paidMinutes(schedule.start, schedule.halfAmEnd!, policy)).toBe(
      policy.daily_minutes / 2,
    );
    expect(paidMinutes(schedule.halfPmStart!, schedule.end, policy)).toBe(
      policy.daily_minutes / 2,
    );
  }
  expect(
    policySchedule({
      ...examplePolicy,
      start_time: "08:00",
      end_time: "17:00",
    }),
  ).toMatchObject({ halfAmEnd: "12:00", halfPmStart: "13:00" });
});

it("정책 합계 오류·야간·초 단위는 거부하며 홀수 근무 분은 반차를 생성하지 않는다", () => {
  expect(policySchedule({ ...examplePolicy, daily_minutes: 400 })).toBeNull();
  expect(policySchedule({ ...examplePolicy, end_time: "06:00" })).toBeNull();
  expect(
    policySchedule({ ...examplePolicy, start_time: "09:00:30" }),
  ).toBeNull();
  expect(
    policySchedule({ ...examplePolicy, end_time: "18:01", daily_minutes: 481 }),
  ).toMatchObject({ halfAmEnd: null, halfPmStart: null });
  expect(paidMinutes("11:30", "13:30", examplePolicy)).toBe(60);
});
