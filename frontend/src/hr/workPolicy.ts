export type WorkPolicy = {
  daily_minutes: number;
  annual_days: number;
  start_time: string;
  end_time: string;
  break_start: string;
  break_end: string;
};

export const examplePolicy: WorkPolicy = {
  daily_minutes: 480,
  annual_days: 15,
  start_time: "09:00",
  end_time: "18:00",
  break_start: "12:00",
  break_end: "13:00",
};

function minute(value: string) {
  if (!/^\d{2}:\d{2}(:00)?$/.test(value)) return NaN;
  const [hour, min] = value.split(":").map(Number);
  return hour < 24 && min < 60 ? hour * 60 + min : NaN;
}
function clock(value: number) {
  return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
}

// Same-day daytime policy, with one unpaid break, matching the work API.
export function policySchedule(policy: WorkPolicy) {
  const start = minute(policy.start_time);
  const end = minute(policy.end_time);
  const breakStart = minute(policy.break_start);
  const breakEnd = minute(policy.break_end);
  if (
    !(start < breakStart && breakStart < breakEnd && breakEnd < end) ||
    policy.daily_minutes !== breakStart - start + end - breakEnd
  )
    return null;
  const half = policy.daily_minutes / 2;
  return {
    start: clock(start),
    end: clock(end),
    breakStart: clock(breakStart),
    breakEnd: clock(breakEnd),
    halfAmEnd: Number.isInteger(half)
      ? clock(
          half <= breakStart - start
            ? start + half
            : breakEnd + half - (breakStart - start),
        )
      : null,
    halfPmStart: Number.isInteger(half)
      ? clock(
          half <= end - breakEnd
            ? end - half
            : breakStart - (half - (end - breakEnd)),
        )
      : null,
    hourlyEnd: clock(
      policy.daily_minutes >= 60
        ? 60 <= breakStart - start
          ? start + 60
          : breakEnd + 60 - (breakStart - start)
        : end,
    ),
  };
}

export function paidMinutes(from: string, to: string, policy: WorkPolicy) {
  const start = minute(from),
    end = minute(to);
  return (
    Math.max(
      0,
      Math.min(end, minute(policy.break_start)) -
        Math.max(start, minute(policy.start_time)),
    ) +
    Math.max(
      0,
      Math.min(end, minute(policy.end_time)) -
        Math.max(start, minute(policy.break_end)),
    )
  );
}

export function hours(minutes: number) {
  return (minutes / 60).toLocaleString("ko-KR", { maximumFractionDigits: 3 });
}
