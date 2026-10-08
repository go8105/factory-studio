import { proposalTimeline, timelineFrame } from "./nc-playback.js";
export function createPlaybackReview(getNC, getEnergy, viewer, selectLine) {
  const panel = document.createElement("section");
  panel.className = "playback-panel";
  panel.innerHTML = `<strong>검토 시나리오 재생 · 실제 CNC 실행 아님</strong><p id="playback-status" role="status">후보 번호를 선택하세요.</p><div class="buttons"><button id="playback-resume" disabled>계속 재생</button><button id="playback-pause" disabled>일시정지</button><label>재생 속도<select id="playback-speed"><option value="1">1배</option><option value="10" selected>10배</option><option value="50">50배</option></select></label></div><progress id="playback-progress" max="1" value="0" aria-label="후보 재생 진행률"></progress><pre id="playback-values">재생 모델 없음</pre>`;
  document.querySelector("#viewer").after(panel);
  const $ = (id) => panel.querySelector("#" + id);
  let timeline = null,
    elapsed = 0,
    frame = null,
    last = null,
    lastLine = null;
  function paint() {
    if (!timeline) return;
    const f = timelineFrame(timeline, elapsed);
    if (f.row.line !== lastLine) {
      selectLine(f.row.line);
      lastLine = f.row.line;
    }
    viewer.marker.visible = true;
    viewer.marker.position.set(...f.position);
    $("playback-progress").value = timeline.seconds
      ? f.time / timeline.seconds
      : 1;
    const range = (a) => a.map((v) => v.toFixed(6)).join("–");
    $("playback-values").textContent =
      `${timeline.number}번 · ${timeline.status === "indeterminate" ? "우열 판단 불가 · 검토용" : "입력 범위의 소비 감소 후보"}\n현재 ${f.row.line}행 · ${f.row.label} · ${f.time.toFixed(2)} / ${timeline.seconds.toFixed(2)}초\n누적 후보 ${range(f.energy)} kWh\n원본 전체 ${timeline.baseline.seconds.toFixed(2)}초 · ${range(timeline.baseline.energy)} kWh\n후보 전체 ${timeline.seconds.toFixed(2)}초 · ${range(timeline.energy)} kWh`;
    return f;
  }
  function pause() {
    if (frame != null) cancelAnimationFrame(frame);
    frame = null;
    last = null;
    if (timeline)
      $("playback-status").textContent = `${timeline.number}번 · 일시정지`;
  }
  function tick(now) {
    elapsed = Math.min(
      timeline.seconds,
      elapsed +
        (last == null ? 0 : (now - last) / 1000) *
          Number($("playback-speed").value),
    );
    last = now;
    const f = paint();
    if (f.done) {
      frame = null;
      last = null;
      $("playback-status").textContent = `${timeline.number}번 · 재생 완료`;
    } else frame = requestAnimationFrame(tick);
  }
  function resume() {
    if (!timeline) return;
    pause();
    if (elapsed >= timeline.seconds) elapsed = 0;
    $("playback-status").textContent =
      `${timeline.number}번 · 시나리오 재생 중`;
    frame = requestAnimationFrame(tick);
  }
  function clear() {
    pause();
    timeline = null;
    elapsed = 0;
    lastLine = null;
    $("playback-resume").disabled = $("playback-pause").disabled = true;
    $("playback-progress").value = 0;
    $("playback-values").textContent = "입력/제안 변경 · 이전 재생 무효화";
    $("playback-status").textContent = "현재 후보를 다시 계산하세요.";
    viewer.marker.visible = false;
  }
  $("playback-pause").onclick = pause;
  $("playback-resume").onclick = resume;
  return {
    clear,
    pause,
    play(report, number) {
      const next = proposalTimeline(getNC(), getEnergy(), report, number);
      pause();
      timeline = next;
      elapsed = 0;
      lastLine = null;
      $("playback-resume").disabled = $("playback-pause").disabled = false;
      paint();
      resume();
      return `${number}번 검토 시나리오를 재생합니다. ${next.status === "indeterminate" ? "우열 판단은 불가합니다." : ""} 예상 ${next.seconds.toFixed(1)}초입니다.`;
    },
  };
}
