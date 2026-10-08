// Review-only timeline: preserve every motion/event; substitute confirmed G4 only.
export function proposalTimeline(nc, energy, report, number) {
  const candidate = report?.candidates[number - 1];
  if (
    !Number.isInteger(number) ||
    !candidate ||
    candidate.status === "blocked" ||
    report.reasons.length
  )
    throw Error("현재 번호의 재생 가능한 후보가 없습니다");
  if (
    !nc?.complete ||
    nc.sourceHash !== report.sourceHash ||
    energy?.sourceHash !== nc.sourceHash
  )
    throw Error("입력이 변경되었습니다. 제안을 다시 계산하세요");
  const replacements = new Map(
    report.review
      .filter((r) => candidate.lines.includes(r.line))
      .map((r) => [r.id, r]),
  );
  let end = 0,
    sum = [0, 0],
    previous = nc.segments[0]?.from ?? [0, 0, 0];
  const rows = energy.rows.map((r) => {
    const replacement = replacements.get(r.id);
    if (replacement && (r.kind !== "dwell" || replacement.blocked.length))
      throw Error("확인되지 않은 대기 변경");
    const seconds = replacement ? replacement.proposedSeconds : r.seconds;
    const consumption = replacement
      ? r.power?.map((p) => (p * seconds) / 3600)
      : r.energy;
    if (
      !Number.isFinite(seconds) ||
      seconds < 0 ||
      !consumption?.every((v) => Number.isFinite(v) && v >= 0)
    )
      throw Error("시간·소비가 미정인 구간은 재생할 수 없습니다");
    const segment = r.segmentId == null ? null : nc.segments[r.segmentId];
    const row = {
      ...r,
      seconds,
      energy: consumption,
      start: end,
      end: end + seconds,
      beforeEnergy: [...sum],
      segment,
      position: [...previous],
    };
    end += seconds;
    sum = sum.map((v, i) => v + consumption[i]);
    if (segment) previous = segment.to;
    return row;
  });
  if (
    Math.abs(end - candidate.seconds) > 1e-7 ||
    sum.some((v, i) => Math.abs(v - candidate.energy[i]) > 1e-7)
  )
    throw Error("후보 합계와 재생 모델이 다릅니다");
  return {
    rows,
    seconds: end,
    energy: sum,
    number,
    status: candidate.status,
    id: candidate.id ?? `${nc.sourceHash}:${candidate.lines.join(",")}`,
    revision: report.revision,
    baseline: report.baseline,
  };
}
export function timelineFrame(timeline, elapsed) {
  const time = Math.min(timeline.seconds, Math.max(0, elapsed));
  let lo = 0,
    hi = timeline.rows.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (timeline.rows[mid].end <= time) lo = mid + 1;
    else hi = mid;
  }
  const row = timeline.rows[lo];
  if (!row) throw Error("재생 구간 없음");
  const fraction = row.seconds
    ? Math.min(1, Math.max(0, (time - row.start) / row.seconds))
    : 1;
  let position = row.position;
  if (row.segment) {
    const points = row.segment.points;
    // Arc display points have equal angle spacing; straight paths have two endpoints.
    const index = fraction * (points.length - 1),
      a = Math.min(points.length - 2, Math.floor(index)),
      f = index - a;
    position = points[a].map((v, i) => v + (points[a + 1][i] - v) * f);
  }
  return {
    time,
    row,
    position,
    fraction,
    energy: row.beforeEnergy.map((v, i) => v + row.energy[i] * fraction),
    done: time >= timeline.seconds,
  };
}
