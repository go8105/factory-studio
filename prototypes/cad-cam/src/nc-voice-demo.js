// Only the named synthetic presentation fills assumptions automatically.
// User uploads keep their own NC, STEP, alignment and review requirements.
export function createVoiceDemo({ voice, getNC, getStock, getEnergy, load }) {
  const button = document.getElementById("voice-sample");
  const note = document.createElement("p");
  note.id = "voice-demo-status";
  note.className = "notice";
  note.setAttribute("role", "status");
  button.closest("header").after(note);
  note.textContent =
    "YC 발표 예제: 합성 검토 준비 후 헤이 와이씨로 요청하세요.";
  let generation = 0;
  let running = false;
  const say = (text) => (note.textContent = text);
  function cancel() {
    if (!running) return;
    generation++;
    running = false;
    button.disabled = false;
    say("발표 준비 중단 · 현재 파일과 입력으로 검토하세요.");
  }
  // Trusted user edits cancel sequencing; programmatic preparation never does.
  for (const type of ["input", "change", "click"])
    document.addEventListener(
      type,
      (event) => {
        if (!event.isTrusted || !running) return;
        if (event.target.closest(".inputs") || event.target.closest("header"))
          cancel();
      },
      true,
    );
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) cancel();
  });
  function check(own) {
    if (generation !== own) throw Error("cancelled");
  }
  function click(id) {
    document.getElementById(id).click();
  }
  async function wait(own, ready, busy, error, milliseconds = 31000) {
    const until = Date.now() + milliseconds;
    while (true) {
      check(own);
      if (ready()) return;
      if (!busy() || Date.now() > until) throw Error(error());
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  async function start() {
    if (running) return;
    running = true;
    const own = ++generation;
    button.disabled = true;
    // Start permission request in this click gesture, before async preparation.
    voice.enable();
    try {
      load();
      say("YC 합성 예제 준비 1/4 · NC 경로 해석 중…");
      click("analyze");
      await wait(
        own,
        () => getNC()?.complete,
        () => document.getElementById("analyze").disabled,
        () => document.getElementById("status").textContent,
      );
      say("YC 합성 예제 준비 2/4 · 목표 STEP 읽기 중…");
      click("step-sample");
      await wait(
        own,
        () => getStock().reference,
        () => document.getElementById("step-sample").disabled,
        () => document.getElementById("stock-status").textContent,
        122000,
      );
      check(own);
      for (const id of ["aligned", "top-confirmed"])
        document.getElementById(id).checked = true;
      click("stock-analyze");
      await wait(
        own,
        () => getStock().analysis,
        () => document.getElementById("stock-analyze").disabled,
        () => document.getElementById("stock-status").textContent,
      );
      say("YC 합성 예제 준비 3/4 · 가정 장비 시간·소비 계산 중…");
      click("energy-demo");
      click("energy-run");
      await wait(
        own,
        () => getEnergy(),
        () => document.getElementById("energy-run").disabled,
        () => document.getElementById("energy-status").textContent,
      );
      check(own);
      click("proposal-demo");
      say(
        "YC 합성 예제 준비 완료 · 헤이 와이씨 → 업로드한 파일 최적안 제안해줘 → 3번 실행해줘. 실제 업로드 파일이 아닌 합성 발표 예제입니다.",
      );
      document
        .getElementById("hugh-enable")
        .scrollIntoView({ block: "nearest" });
    } catch (error) {
      if (generation === own)
        say(
          `발표 준비 실패: ${error.message} · YC 발표 예제를 다시 누르거나 입력을 확인하세요.`,
        );
    } finally {
      if (generation === own) {
        running = false;
        button.disabled = false;
      }
    }
  }
  return { start, cancel };
}
