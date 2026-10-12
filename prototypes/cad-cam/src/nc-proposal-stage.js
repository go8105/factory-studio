// One live renderer; comparison cards use its frozen image, never duplicate WebGL loops.
export function createProposalStage(
  getNC,
  viewer,
  playback,
  onPlay,
  doc = document,
) {
  const dialog = doc.createElement("dialog");
  dialog.className = "proposal-stage";
  dialog.setAttribute("aria-labelledby", "proposal-stage-title");
  dialog.innerHTML = `<div class="stage-layout"><section class="stage-main"><header><div><h2 id="proposal-stage-title">가공 검토 제안</h2><p>품질 조건을 먼저 확인한 G4 대기 후보 · 실제 장비 실행 아님</p></div><button data-stage-all hidden>전체 제안 보기</button><button data-stage-close aria-label="제안 창 닫기">닫기</button></header><p data-stage-status role="status">번호를 선택하면 재생합니다.</p><div class="stage-cards"></div></section><aside class="stage-assistant" aria-label="YC 음성 명령"></aside></div>`;
  doc.body.append(dialog);
  const cards = dialog.querySelector(".stage-cards"),
    assistant = dialog.querySelector(".stage-assistant"),
    all = dialog.querySelector("[data-stage-all]");
  const moved = [];
  let current = null,
    snapshot = "",
    lastFocus;
  function move(node, destination) {
    if (!node) return;
    const mark = doc.createComment("YC restore");
    node.before(mark);
    moved.push([node, mark]);
    destination.append(node);
  }
  function restore(liveOnly = false) {
    for (let i = moved.length - 1; i >= 0; i--) {
      const [node, mark] = moved[i];
      if (liveOnly && node.classList.contains("hugh-panel")) continue;
      mark.replaceWith(node);
      moved.splice(i, 1);
    }
  }
  function compare() {
    playback.pause();
    restore(true);
    all.hidden = true;
    dialog.querySelectorAll("[data-stage-card]").forEach((card) => {
      card.hidden = false;
      card.classList.remove("is-selected");
      card.querySelector(".stage-live")?.remove();
      card.querySelector("img").hidden = false;
      card.querySelector("[data-stage-play]").hidden = false;
    });
    cards.classList.remove("is-playing");
    dialog.querySelector("[data-stage-status]").textContent =
      "정지 미리보기 · 번호를 선택하면 해당 후보를 재생합니다.";
  }
  function close() {
    playback.pause();
    restore();
    current = null;
    if (dialog.open) dialog.close();
    lastFocus?.focus();
  }
  dialog.querySelector("[data-stage-close]").onclick = close;
  all.onclick = compare;
  dialog.addEventListener("cancel", () => close());
  dialog.addEventListener("close", () => {
    if (dialog.open) return;
    playback.pause();
    restore();
    current = null;
  });
  doc.addEventListener("visibilitychange", () => {
    if (doc.hidden) playback.pause();
  });
  dialog.addEventListener("click", (e) => {
    const b = e.target.closest("[data-stage-play]");
    if (!b) return;
    try {
      onPlay(Number(b.dataset.stagePlay));
    } catch (error) {
      dialog.querySelector("[data-stage-status]").textContent = error.message;
    }
  });
  return {
    clear: close,
    show(report) {
      close();
      current = report;
      lastFocus = doc.activeElement;
      viewer.renderer.render(viewer.scene, viewer.camera);
      try {
        snapshot = viewer.renderer.domElement.toDataURL("image/png");
      } catch {
        snapshot = "";
      }
      cards.replaceChildren();
      cards.classList.remove("is-playing");
      all.hidden = true;
      for (const c of report.candidates) {
        const card = doc.createElement("article");
        card.dataset.stageCard = c.number;
        const title = doc.createElement("h3");
        title.textContent = `${c.number}번 · ${c.lines.length > 1 ? "대기 조합" : c.lines.map((l) => l + "행 대기").join(" + ")}`;
        const state = doc.createElement("p");
        state.className = "stage-state";
        state.textContent =
          c.status === "blocked"
            ? "품질·검토 조건 차단"
            : c.status === "conditional-lower"
              ? "입력 범위의 소비 감소 후보"
              : "우열 판단 불가";
        const image = doc.createElement("img");
        image.alt = "현재 NC·소재의 정지 3D 경로 미리보기";
        image.src = snapshot;
        const metrics = doc.createElement("dl");
        for (const [label, value] of [
          [
            "예상 시간",
            c.seconds == null ? "미정" : `${c.seconds.toFixed(1)}초`,
          ],
          [
            "예상 소비",
            c.energy
              ? `${c.energy.map((v) => v.toFixed(4)).join("–")} kWh`
              : "미정",
          ],
          [
            "원본 대비 시간",
            c.savedSeconds == null
              ? "미정"
              : `${c.savedSeconds.toFixed(1)}초 감소`,
          ],
        ]) {
          const dt = doc.createElement("dt"),
            dd = doc.createElement("dd");
          dt.textContent = label;
          dd.textContent = value;
          metrics.append(dt, dd);
        }
        const reason = doc.createElement("p");
        reason.className = "stage-reasons";
        reason.textContent = report.review
          .filter((r) => c.lines.includes(r.line))
          .map(
            (r) =>
              `${r.line}행 ${r.seconds}→${r.proposedSeconds}초 · ${r.source}`,
          )
          .join(" / ");
        const button = doc.createElement("button");
        button.dataset.stagePlay = c.number;
        button.disabled = c.status === "blocked";
        button.textContent = `${c.number}번 시뮬레이션 실행`;
        card.append(title, state, image, metrics, reason, button);
        cards.append(card);
      }
      dialog.querySelector("#proposal-stage-title").textContent =
        `가공 검토 제안 ${report.candidates.length}개`;
      dialog.querySelector("[data-stage-status]").textContent =
        "정지 미리보기 · G4 대기만 달라 경로는 같습니다. 실측 품질·절감 미검증.";
      dialog.showModal();
      move(doc.querySelector(".hugh-panel"), assistant);
    },
    select(report, number) {
      if (!dialog.open || current !== report) this.show(report);
      restore(true);
      const selected = dialog.querySelector(`[data-stage-card="${number}"]`);
      if (!selected) throw Error("현재 제안 번호가 없습니다");
      cards.classList.add("is-playing");
      all.hidden = false;
      cards.querySelectorAll("[data-stage-card]").forEach((card) => {
        card.hidden = card !== selected;
        card.classList.toggle("is-selected", card === selected);
      });
      selected.querySelector("img").hidden = true;
      selected.querySelector("[data-stage-play]").hidden = true;
      const live = doc.createElement("div");
      live.className = "stage-live";
      selected.querySelector("img").after(live);
      move(doc.querySelector("#viewer"), live);
      move(doc.querySelector(".playback-panel"), live);
      dialog.querySelector("[data-stage-status]").textContent =
        `${number}번 선택 · 실제 NC 경로/시간 모델 재생`;
      requestAnimationFrame(() => viewer.fit());
    },
  };
}
