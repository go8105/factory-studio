import { dwellReview, compareProposals } from "./nc-proposals.js";
export function createProposalReview(getNC, getStock, getEnergy, selectLine) {
  const panel = document.createElement("details");
  panel.className = "stock-panel proposal-panel";
  panel.innerHTML = `<summary>품질 우선 개선 제안</summary><p class="muted">G4 대기의 목적과 최소 시간을 확인한 검토 시나리오입니다. 경로·F/S/T·쿨런트는 유지합니다. 실제 공차/Ra·열·칩 배출은 자동 검증하지 않습니다.</p><label>품질 기준·근거<input id="proposal-quality-source" placeholder="도면 기준/검토 기록 또는 가정"></label><label>허용 최대 잔삭 높이 mm<input id="proposal-remaining" type="number" step="any"></label><label>허용 최대 과절삭 깊이 mm<input id="proposal-overcut" type="number" step="any"></label><label>허용 목표 격자 체적 오차 %<input id="proposal-grid-error" type="number" step="any"></label><p class="muted">셀 중심 근사값 기준입니다. 실제 치수 공차/Ra와 다릅니다. 0 검출은 안전 보증이 아닙니다.</p><label>추가 비교 여유 kWh<input id="proposal-margin" type="number" step="any"></label><label>추가 여유 근거<input id="proposal-margin-source" placeholder="미정이면 우열 판단 보류"></label><label class="check"><input id="proposal-risk" type="checkbox">실기계·홀더/지그·공정 위험을 별도로 검토했습니다</label><div class="buttons"><button id="proposal-prepare">대기 목록 만들기</button><button id="proposal-demo">합성 검토 기준 채우기</button></div><p id="proposal-status" role="status">현재 NC/소재/시간·소비 분석 완료 후 검토하세요.</p><div id="proposal-dwells"></div><div class="buttons"><button id="proposal-prev" disabled>앞 200대기</button><span id="proposal-page"></span><button id="proposal-next" disabled>뒤 200대기</button></div><button id="proposal-run">품질 조건과 소비 비교</button><p class="muted">최대12대기 선택/13후보. 입력 변경 시 제안 무효화. NC 자동 적용·실행 파일 출력 없음.</p>`;
  document.querySelector(".inputs").append(panel);
  const output = document.createElement("details");
  output.className = "stock-output proposal-output";
  output.open = true;
  output.innerHTML =
    '<summary>품질 우선 제안 결과</summary><pre id="proposal-summary">결과 없음 · 품질/대기 조건 확인 필요</pre><div id="proposal-candidates"></div><p class="muted">소비량은 CAD-14 가정 모델입니다. 원본과 후보 범위가 겹치거나 추가 여유가 미정이면 우열을 판단하지 않습니다. 실제 품질·안전·전력 절감은 미검증입니다.</p>';
  document.querySelector("#detail").before(output);
  const $ = (id) => document.getElementById(id);
  const num = (id) => ($(id).value.trim() === "" ? null : Number($(id).value));
  const esc = (v) =>
    String(v).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const fmt = (v, d = 3) => (v == null ? "미정" : v.toFixed(d));
  const range = (r) => (r ? r.map((v) => fmt(v, 6)).join("–") : "미정");
  let dwells = null,
    report = null,
    page = 0;
  const inputs = new Map();
  function clear() {
    report = null;
    $("proposal-summary").textContent = "결과 없음 · 품질/대기 조건 확인 필요";
    $("proposal-candidates").replaceChildren();
  }
  function invalidate() {
    clear();
    dwells = null;
    inputs.clear();
    page = 0;
    $("proposal-dwells").replaceChildren();
    $("proposal-page").textContent = "";
    $("proposal-prev").disabled = $("proposal-next").disabled = true;
    $("proposal-status").textContent =
      "NC/소재/장비 분석 변경 · 대기 검토와 제안 무효화";
  }
  panel.addEventListener("input", (e) => {
    const id = e.target.dataset.dwellId;
    if (id != null) {
      const row = inputs.get(Number(id)),
        key = e.target.dataset.field;
      row[key] =
        e.target.type === "checkbox"
          ? e.target.checked
          : e.target.type === "number"
            ? e.target.value.trim() === ""
              ? null
              : Number(e.target.value)
            : e.target.value;
    }
    clear();
    $("proposal-status").textContent = "검토 입력 변경 · 이전 제안 무효화";
  });
  function render() {
    const total = dwells.length,
      start = page * 200;
    $("proposal-page").textContent = total
      ? `${start + 1}–${Math.min(start + 200, total)} / ${total}대기`
      : "대기 없음";
    $("proposal-prev").disabled = !page;
    $("proposal-next").disabled = start + 200 >= total;
    $("proposal-dwells").innerHTML = dwells
      .slice(start, start + 200)
      .map((r) => {
        const v = inputs.get(r.id);
        const attr = (field) => `data-dwell-id="${r.id}" data-field="${field}"`;
        return `<fieldset class="power-state"><legend>${r.line}행 G4 · 원본 ${fmt(r.seconds)}초</legend><button data-proposal-line="${r.line}">원본 ${r.line}행 보기</button><p class="muted">${esc(r.reason)} · 전체 전력 ${range(r.power)}kW</p><label class="check"><input ${attr("selected")} type="checkbox" ${v.selected ? "checked" : ""} ${r.eligible ? "" : "disabled"} aria-label="${r.line}행 대기 선택">검토 대상으로 선택</label><label>최소 유지 시간 초<input ${attr("seconds")} type="number" step="any" value="${v.seconds ?? ""}" aria-label="${r.line}행 최소 유지 시간 초"></label><label>공정 목적·최소 시간 근거<input ${attr("source")} value="${esc(v.source)}" aria-label="${r.line}행 공정 목적·최소 시간 근거"></label><label class="check"><input ${attr("confirmed")} type="checkbox" ${v.confirmed ? "checked" : ""} aria-label="${r.line}행 대기 영향 검토 확인">열/칩/냉각/정삭 영향과 최소 시간 조건을 검토했습니다</label></fieldset>`;
      })
      .join("");
  }
  function prepare() {
    clear();
    dwells = dwellReview(getNC(), getStock(), getEnergy());
    inputs.clear();
    page = 0;
    for (const r of dwells)
      inputs.set(r.id, {
        id: r.id,
        selected: false,
        seconds: null,
        source: "",
        confirmed: false,
      });
    render();
    $("proposal-status").textContent = dwells.length
      ? `${dwells.length}대기 · 기본 미확인, 최대12개 선택`
      : "지원 대기 없음 · 비절삭/주축/쿨런트 자동 변경 없음";
  }
  $("proposal-prepare").onclick = () => {
    try {
      prepare();
    } catch (e) {
      invalidate();
      $("proposal-status").textContent = e.message;
    }
  };
  $("proposal-demo").onclick = () => {
    try {
      prepare();
      $("proposal-quality-source").value = "합성 형상 기준 · 실물 품질 미검증";
      $("proposal-remaining").value = $("proposal-overcut").value = "0";
      $("proposal-grid-error").value = "0.1";
      $("proposal-margin").value = "0";
      $("proposal-margin-source").value =
        "합성 비교 · 추가 여유0 가정, 실제 계측 아님";
      $("proposal-risk").checked = true;
      const first = dwells.find((r) => r.eligible);
      if (first)
        Object.assign(inputs.get(first.id), {
          selected: true,
          seconds: Math.min(10, first.seconds),
          source: "합성 대기 · 최소10초 가정, 실제 공정 검토 아님",
          confirmed: true,
        });
      render();
      $("proposal-status").textContent =
        "합성 검토 기준 · 실제 위험 검토/측정값이 아닙니다";
    } catch (e) {
      $("proposal-status").textContent = e.message;
    }
  };
  function settings() {
    return {
      quality: {
        source: $("proposal-quality-source").value,
        maxRemaining: num("proposal-remaining"),
        maxOvercut: num("proposal-overcut"),
        maxGridErrorPercent: num("proposal-grid-error"),
      },
      riskReviewed: $("proposal-risk").checked,
      marginKWh: num("proposal-margin"),
      marginSource: $("proposal-margin-source").value,
      dwells: [...inputs.values()]
        .filter((r) => r.selected)
        .map(({ selected, ...r }) => r),
    };
  }
  $("proposal-run").onclick = () => {
    clear();
    try {
      if (!dwells) throw Error("현재 분석의 대기 목록을 먼저 만드세요");
      report = compareProposals(getNC(), getStock(), getEnergy(), settings());
      const b = report.baseline;
      $("proposal-summary").textContent =
        `원본 모델 ${fmt(b.seconds)}초 · ${range(b.energy)}kWh\n품질 근거: ${report.settings.quality.source || "미정"}\n추가 비교 여유: ${fmt(report.settings.marginKWh, 6)}kWh · ${report.settings.marginSource || "미정"}\n${report.reasons.length ? "제안 차단: " + report.reasons.join(" · ") : "사용자 조건으로 비교 · 실제 품질·안전 미검증"}\n형상 잔삭 ${fmt(report.quality.maxRemaining)}mm / 과절삭 ${fmt(report.quality.maxOvercut)}mm / 격자 체적 오차 ${fmt(report.quality.gridErrorPercent)}%`;
      $("proposal-candidates").innerHTML = report.candidates
        .map(
          (c) =>
            `<article class="proposal-card"><strong>${c.lines.map((l) => l + "행").join(" + ")} · ${c.status === "blocked" ? "차단" : c.status === "conditional-lower" ? "입력 범위에서 소비 감소 후보" : "우열 판단 불가"}</strong><div>${c.lines.map((l) => `<button data-proposal-line="${l}">원본 ${l}행 보기</button>`).join("")}</div>${c.status === "blocked" ? "" : `<p>후보 ${fmt(c.seconds)}초 · ${range(c.energy)}kWh</p><p>시간 감소 ${fmt(c.savedSeconds)}초 · 대기 소비 감소 ${range(c.savedEnergy)}kWh</p>`}<p>${esc(
              report.review
                .filter((r) => c.lines.includes(r.line))
                .map(
                  (r) =>
                    `${r.line}행 대기 ${fmt(r.seconds)}→${fmt(r.proposedSeconds)}초 · ${r.source || "근거 미정"}`,
                )
                .join(" / "),
            )}</p><p>${esc(c.reasons.join(" · "))}</p></article>`,
        )
        .join("");
      $("proposal-status").textContent = report.reasons.length
        ? "품질/검토 조건 부족 · 제안 차단"
        : `${report.candidates.length}검토 후보 · 단일 최적/실제 절감 보장 없음`;
    } catch (e) {
      $("proposal-status").textContent = e.message;
    }
  };
  panel.addEventListener("click", (e) => {
    const b = e.target.closest("[data-proposal-line]");
    if (b) selectLine(Number(b.dataset.proposalLine));
  });
  output.addEventListener("click", (e) => {
    const b = e.target.closest("[data-proposal-line]");
    if (b) selectLine(Number(b.dataset.proposalLine));
  });
  $("proposal-prev").onclick = () => {
    page--;
    render();
  };
  $("proposal-next").onclick = () => {
    page++;
    render();
  };
  return { invalidate, export: () => ({ settings: settings(), report }) };
}
