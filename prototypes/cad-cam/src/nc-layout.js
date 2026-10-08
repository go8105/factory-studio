// Move existing nodes, preserving values, event handlers and analysis references.
export function arrangeNCReview(doc = document) {
  const main = doc.querySelector("main");
  const inputs = doc.querySelector(".inputs");
  const file = doc.createElement("details");
  file.className = "preparation-step";
  file.open = true;
  file.innerHTML = "<summary>1 · NC 파일과 초기 설정</summary>";
  for (const child of [...inputs.children]) {
    if (!child.matches(".stock-panel")) file.append(child);
  }
  inputs.prepend(file);
  [
    ".stock-panel:not(.energy-panel):not(.proposal-panel)",
    ".energy-panel",
    ".proposal-panel",
  ].forEach((selector, i) => {
    const panel = inputs.querySelector(selector);
    if (!panel) return;
    panel.classList.add("preparation-step");
    panel.open = false;
    const summary = panel.querySelector("summary");
    summary.textContent = `${i + 2} · ${summary.textContent}`;
  });
  const title = doc.createElement("h2");
  title.textContent = "분석 준비";
  inputs.prepend(title);
  const results = doc.createElement("aside");
  results.className = "review-results";
  results.setAttribute("aria-label", "분석 결과와 휴디");
  results.innerHTML =
    '<h2>분석 결과·제안</h2><p class="muted">품질을 먼저 확인하고 예상 소비 범위를 비교합니다.</p>';
  for (const selector of [
    ".hugh-panel",
    ".proposal-output",
    ".energy-output",
    ".stock-output:not(.energy-output):not(.proposal-output)",
  ]) {
    const node = doc.querySelector(selector);
    if (!node) continue;
    if (selector === ".hugh-panel" || selector === ".proposal-output")
      results.append(node);
    else {
      const group = doc.createElement("details");
      group.open = selector === ".energy-output";
      const heading = node.querySelector("h2");
      const summary = doc.createElement("summary");
      summary.textContent = heading?.textContent || "분석 근거";
      group.append(summary, node);
      results.append(group);
    }
  }
  main.append(results);
  main.classList.add("nc-review-layout");
}
