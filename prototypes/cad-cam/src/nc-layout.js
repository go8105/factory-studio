// Keep original controls and handlers while changing workspace structure.
export function arrangeNCReview(doc = document, getState = () => ({})) {
  const main = doc.querySelector("main"),
    inputs = doc.querySelector(".inputs"),
    workspace = doc.querySelector(".workspace");
  const file = doc.createElement("details");
  file.className = "preparation-step";
  file.innerHTML = "<summary>NC 파일·초기 상태</summary>";
  for (const child of [...inputs.children])
    if (!child.matches(".stock-panel")) file.append(child);
  const panels = [file, ...inputs.querySelectorAll(":scope > .stock-panel")];
  const inspector = doc.createElement("aside");
  inspector.className = "review-results";
  inspector.setAttribute("aria-label", "속성과 YC");
  inspector.innerHTML =
    '<h2>현재 단계 속성</h2><div class="inspector-forms"></div>';
  const returnView = doc.createElement("button");
  returnView.className = "nc-return-view";
  returnView.textContent = "작업 화면으로";
  returnView.onclick = () => workspace.scrollIntoView({ block: "start" });
  inspector.prepend(returnView);
  const forms = inspector.querySelector(".inspector-forms");
  for (const panel of panels) {
    panel.classList.add("preparation-step");
    forms.append(panel);
  }
  inputs.innerHTML =
    '<h2>분석 준비</h2><p class="muted">단계를 선택해 오른쪽에서 조건을 확인하세요.</p><nav class="preparation-nav" aria-label="NC 준비 단계"></nav><p class="muted">품질 조건을 먼저 검토하고 예상 소비 범위를 비교합니다.</p>';
  const nav = inputs.querySelector("nav");
  const labels = [
    "파일·초기 상태",
    "소재·공구·STEP",
    "장비·시간·소비",
    "품질 조건",
  ];
  const buttons = panels.map((panel, i) => {
    panel.id = `nc-preparation-${i}`;
    const button = doc.createElement("button");
    button.type = "button";
    button.dataset.step = i;
    button.setAttribute("aria-controls", panel.id);
    button.innerHTML = `<span>${i + 1} · ${labels[i]}</span><small data-step-status>확인 필요</small>`;
    button.onclick = () => select(i);
    nav.append(button);
    return button;
  });
  function select(index) {
    if (main.classList.contains("nc-showing-proposals"))
      doc.querySelector("[data-stage-close]")?.click();
    panels.forEach((panel, i) => {
      panel.hidden = i !== index;
      panel.open = i === index;
      buttons[i].setAttribute("aria-expanded", String(i === index));
      if (i === index) buttons[i].setAttribute("aria-current", "step");
      else buttons[i].removeAttribute("aria-current");
    });
    if (inspector.isConnected && doc.defaultView?.innerWidth <= 950)
      inspector.scrollIntoView({ block: "start" });
  }
  select(0);
  const viewport = doc.createElement("div");
  viewport.className = "nc-viewport";
  for (const selector of [".view-head", "#viewer", ".legend", ".navigation"])
    if (workspace.querySelector(selector))
      viewport.append(workspace.querySelector(selector));
  const empty = doc.createElement("div");
  empty.className = "nc-empty";
  empty.innerHTML =
    '<h2>NC 파일을 열어<br>가공 경로를 확인하세요.</h2><p>소재와 품질 조건을 확인한 뒤 예상 시간·소비를 비교합니다.</p><div class="buttons"><button data-empty-load>NC 파일 열기</button><button data-empty-demo>YC 발표 예제로 시작</button></div>';
  viewport.append(empty);
  empty.querySelector("[data-empty-load]").onclick = () =>
    doc.querySelector("#load")?.click();
  empty.querySelector("[data-empty-demo]").onclick = () =>
    doc.querySelector("#voice-sample")?.click();
  workspace.prepend(viewport);
  const source = doc.createElement("details");
  source.className = "nc-source-details";
  source.innerHTML = "<summary>원본 NC · 행별 상태와 선택 구간</summary>";
  for (const selector of ["#detail", ".code-head", "#code"])
    if (workspace.querySelector(selector))
      source.append(workspace.querySelector(selector));
  workspace.append(source);
  const voice = doc.querySelector(".hugh-panel");
  if (voice) inspector.append(voice);
  const evidence = doc.createElement("details");
  evidence.className = "nc-evidence";
  evidence.innerHTML = "<summary>분석 근거·상세 결과</summary>";
  for (const selector of [
    ".stock-output:not(.energy-output):not(.proposal-output)",
    ".energy-output",
    ".proposal-output",
  ])
    if (doc.querySelector(selector))
      evidence.append(doc.querySelector(selector));
  inspector.append(evidence);
  main.append(inspector);
  main.classList.add("nc-review-layout", "nc-workbench");
  const footer = doc.createElement("footer");
  footer.className = "nc-playback-dock";
  const playback = doc.querySelector(".playback-panel");
  if (playback) {
    footer.append(playback);
    const details = doc.createElement("details");
    details.innerHTML = "<summary>가공 시간·소비 상세</summary>";
    if (playback.querySelector("#playback-values"))
      details.append(playback.querySelector("#playback-values"));
    playback.append(details);
  }
  main.after(footer);
  function update() {
    const state = getState();
    [state.nc, state.stock, state.energy, state.quality].forEach(
      (complete, i) => {
        buttons[i].dataset.complete = String(!!complete);
        buttons[i].querySelector("small").textContent = complete
          ? "확인 완료"
          : "확인 필요";
      },
    );
    empty.hidden = !!state.nc;
    const heading = inspector.querySelector(":scope > h2");
    if (heading)
      heading.textContent = main.classList.contains("nc-showing-proposals")
        ? "YC · 제안 명령"
        : "현재 단계 속성";
    viewport.classList.toggle("is-empty", !state.nc);
    const propose = doc.querySelector("#hugh-propose");
    if (propose) propose.disabled = !(state.nc && state.stock && state.energy);
  }
  const Observer = doc.defaultView?.MutationObserver;
  if (Observer) {
    const observer = new Observer(update);
    for (const id of [
      "summary",
      "stock-status",
      "energy-status",
      "proposal-status",
    ])
      if (doc.getElementById(id))
        observer.observe(doc.getElementById(id), {
          childList: true,
          subtree: true,
          characterData: true,
        });
  }
  update();
  return { select, update };
}
