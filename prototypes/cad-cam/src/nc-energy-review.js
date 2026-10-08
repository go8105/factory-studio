import { energyPlan, ENERGY_MODEL, compactEnergyNC } from "./nc-energy.js";
export function createEnergyReview(
  getNC,
  getStock,
  selectLine,
  onChange = () => {},
) {
  const panel = document.createElement("details");
  panel.className = "stock-panel energy-panel";
  panel.open = true;
  panel.innerHTML = `<summary>가공 시간 · 소비 에너지</summary><p class="muted">상태별 장비 전체 전력 모델. 기본·주축·축·펌프 전력을 별도로 더하지 않습니다. 현재 NC의 소재 검토 완료 후 상태표를 만드세요.</p><label>장비/시나리오 이름<input id="energy-machine" placeholder="입력 필요"></label><label>입력 근거<select id="energy-provenance"><option value="assumption">사용자 가정</option><option value="measured-input">사용자 제공 측정값 (보정 아님)</option></select></label><label>근거 설명<input id="energy-source" placeholder="사양/측정 기록·조건 또는 가정 이유"></label><label>측정 날짜<input id="energy-date" type="date"></label><label>적용 조건<input id="energy-conditions" placeholder="소재·공구·부하 등"></label><h3>축별 제한</h3><p class="muted">최고 속도 mm/min · 가속도 mm/s². 빈칸은 미정.</p><div class="axis-limits">${["X", "Y", "Z"].map((a) => `<fieldset><legend>${a}</legend><label>최고 속도<input id="energy-v${a}" type="number" step="any"></label><label>가속도<input id="energy-a${a}" type="number" step="any"></label></fieldset>`).join("")}</div><label class="check"><input id="energy-confirmed" type="checkbox">구간마다 정지/출발·override 100%·이벤트 별도 시간 가정을 확인했습니다</label><label class="check"><input id="energy-whole" type="checkbox">각 전력은 장비 전체이며, 이벤트 시간/전력에 주축 정지·교환/자동 이동을 모두 포함했습니다</label><div class="buttons"><button id="energy-plan">상태표 만들기</button><button id="energy-demo">합성 장비 값 채우기</button></div><div id="energy-states"></div><details><summary>별도 검증 운전과 비교 (선택)</summary><p class="muted">예측 모델 입력에 사용하지 않은 별도 운전 기록만. 계수를 자동 보정하지 않습니다.</p><label>검증 시간 (초)<input id="energy-check-time" type="number" step="any"></label><label>검증 소비 (kWh)<input id="energy-check-kwh" type="number" step="any"></label><label>검증 기록 근거<input id="energy-check-source"></label></details><div class="buttons"><button id="energy-run">시간·에너지 계산</button><button id="energy-cancel" disabled>에너지 계산 취소</button></div><p id="energy-status" role="status">장비 값은 미정입니다.</p><p class="muted">상태200종 · Worker30초. 입력 범위 시나리오이며 정확도/신뢰구간 보증이 아닙니다. NC 시작~종료만, 부팅/준비/프로그램 밖 대기 제외.</p>`;
  document.querySelector(".inputs").append(panel);
  const output = document.createElement("details");
  output.className = "stock-output energy-output";
  output.open = true;
  output.innerHTML =
    '<summary>시간 · 소비 예상과 근거</summary><pre id="energy-summary">결과 없음 · 시간/kWh 미정</pre><p class="muted">막대: 구간 평균 전력 최대(kW), 폭은 시간 비례가 아닙니다. 선택하면 원본 NC 행을 보여줍니다.</p><div id="energy-chart" aria-label="구간별 평균 전력"></div><div class="buttons"><button id="energy-prev" disabled>앞 200구간</button><span id="energy-page"></span><button id="energy-next" disabled>뒤 200구간</button></div><div class="energy-ledger"><table><thead><tr><th>행/상태</th><th>시간 s</th><th>전체 kW</th><th>kWh</th></tr></thead><tbody id="energy-ledger"></tbody></table></div><p class="muted">제거 미검출은 비접촉/공중 이송을 뜻하지 않습니다. 가감속·원호·이벤트는 명시한 가정 모델, 실제 정확도/장비 안전은 미검증입니다.</p>';
  document.querySelector("#detail").before(output);
  const $ = (id) => document.getElementById(id),
    num = (id) => ($(id).value.trim() === "" ? null : Number($(id).value)),
    esc = (v) =>
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
  let plan = null,
    analysis = null,
    worker = null,
    revision = 0,
    timer,
    page = 0;
  const cellRows = new Map();
  function stop() {
    revision++;
    worker?.terminate();
    worker = null;
    clearTimeout(timer);
    $("energy-cancel").disabled = true;
    $("energy-run").disabled = false;
  }
  function clearResult() {
    stop();
    analysis = null;
    onChange();
    page = 0;
    $("energy-summary").textContent = "결과 없음 · 시간/kWh 미정";
    $("energy-chart").replaceChildren();
    $("energy-ledger").replaceChildren();
    $("energy-page").textContent = "";
    $("energy-prev").disabled = true;
    $("energy-next").disabled = true;
  }
  function invalidate() {
    clearResult();
    plan = null;
    cellRows.clear();
    $("energy-states").replaceChildren();
    $("energy-status").textContent =
      "NC/소재 설정 변경 · 상태표와 이전 분석 무효화";
  }
  panel.addEventListener("input", () => {
    clearResult();
    $("energy-status").textContent = "입력 변경 · 이전 계산 무효화";
  });
  function buildPlan() {
    clearResult();
    plan = energyPlan(getNC(), getStock());
    cellRows.clear();
    $("energy-states").replaceChildren();
    for (const state of plan.states) {
      const card = document.createElement("fieldset");
      card.className = "power-state";
      const legend = document.createElement("legend");
      legend.textContent = state.label;
      card.append(legend);
      const inputs = {};
      for (const [key, label] of [
        ["min", "전체 전력 최소 kW"],
        ["max", "전체 전력 최대 kW"],
        ...(state.eventTime ? [["seconds", "이벤트 전체 시간 초"]] : []),
      ]) {
        const wrapper = document.createElement("label");
        wrapper.textContent = label;
        const input = document.createElement("input");
        input.type = "number";
        input.step = "any";
        input.setAttribute("aria-label", `${state.label} ${label}`);
        wrapper.append(input);
        card.append(wrapper);
        inputs[key] = input;
      }
      cellRows.set(state.key, inputs);
      $("energy-states").append(card);
    }
    $("energy-status").textContent =
      `${plan.states.length}상태 · 시간/전력을 직접 입력하세요 (빈칸 미정)`;
  }
  $("energy-plan").onclick = () => {
    try {
      buildPlan();
    } catch (e) {
      invalidate();
      $("energy-status").textContent = e.message;
    }
  };
  $("energy-demo").onclick = () => {
    try {
      buildPlan();
      $("energy-machine").value = "합성 장비 시나리오 · 실측 아님";
      $("energy-source").value = "CAD-14 논리/화면 검증용 가정값";
      $("energy-provenance").value = "assumption";
      $("energy-date").value = "";
      $("energy-conditions").value = "현재 NC 조건에 대한 합성 전력 가정";
      for (const a of ["X", "Y", "Z"]) {
        $("energy-v" + a).value = "3000";
        $("energy-a" + a).value = "500";
      }
      $("energy-confirmed").checked = true;
      $("energy-whole").checked = true;
      for (const s of plan.states) {
        const row = cellRows.get(s.key),
          range =
            s.kind === "removal"
              ? [2, 3]
              : s.kind === "rapid"
                ? [1, 1.5]
                : s.kind === "no-removal"
                  ? [0.8, 1.2]
                  : [0.5, 0.9];
        row.min.value = range[0];
        row.max.value = range[1];
        if (row.seconds)
          row.seconds.value =
            s.kind === "tool-change" ? 5 : s.kind === "end" ? 1 : 2;
      }
      $("energy-status").textContent =
        "합성 예제 값 · 실제 장비 소비/정확도가 아닙니다";
    } catch (e) {
      $("energy-status").textContent = e.message;
    }
  };
  function model() {
    const states = {};
    for (const [key, inputs] of cellRows) {
      const row = {};
      for (const [name, input] of Object.entries(inputs))
        row[name] = input.value.trim() === "" ? null : Number(input.value);
      states[key] = row;
    }
    const validation = [
      "energy-check-time",
      "energy-check-kwh",
      "energy-check-source",
    ].some((id) => $(id).value.trim())
      ? {
          seconds: num("energy-check-time"),
          kWh: num("energy-check-kwh"),
          source: $("energy-check-source").value,
        }
      : null;
    return {
      version: ENERGY_MODEL,
      machine: $("energy-machine").value,
      source: $("energy-source").value,
      provenance: $("energy-provenance").value,
      date: $("energy-date").value,
      conditions: $("energy-conditions").value,
      confirmed: $("energy-confirmed").checked,
      wholeMachineConfirmed: $("energy-whole").checked,
      axes: ["X", "Y", "Z"].map((a) => ({
        velocity: num("energy-v" + a),
        acceleration: num("energy-a" + a),
      })),
      states,
      validation,
    };
  }
  function fmt(v, d = 3) {
    return v == null ? "미정" : v.toFixed(d);
  }
  function range(v, d = 5) {
    return v ? `${fmt(v[0], d)}–${fmt(v[1], d)}` : "미정";
  }
  function render() {
    if (!analysis) return;
    const start = page * 200,
      rows = analysis.rows.slice(start, start + 200);
    $("energy-page").textContent =
      `${start + 1}–${Math.min(start + 200, analysis.rows.length)} / ${analysis.rows.length}구간`;
    $("energy-prev").disabled = page === 0;
    $("energy-next").disabled = start + 200 >= analysis.rows.length;
    $("energy-ledger").innerHTML = rows
      .map(
        (r) =>
          `<tr><td><button data-energy-line="${r.line}" title="${esc(r.key)}">${r.line}행 ${esc(r.label)}</button>${r.reasons.length ? `<small>${esc(r.reasons.join(" · "))}</small>` : ""}</td><td>${fmt(r.seconds)}</td><td>${range(r.power, 3)}</td><td>${range(r.energy, 6)}</td></tr>`,
      )
      .join("");
    const max = Math.max(1, ...rows.map((r) => r.power?.[1] ?? 0));
    $("energy-chart").replaceChildren();
    for (const r of rows) {
      const button = document.createElement("button");
      button.className = "energy-bar";
      button.style.height = `${r.power ? Math.max(4, (r.power[1] / max) * 85) : 4}px`;
      button.setAttribute(
        "aria-label",
        `${r.line}행 ${r.label} ${range(r.power, 3)}kW`,
      );
      button.title = `${r.line}행 ${r.key} · ${range(r.power, 3)}kW`;
      button.onclick = () => selectLine(r.line);
      $("energy-chart").append(button);
    }
  }
  $("energy-ledger").onclick = (e) => {
    const b = e.target.closest("[data-energy-line]");
    if (b) selectLine(Number(b.dataset.energyLine));
  };
  $("energy-prev").onclick = () => {
    page--;
    render();
  };
  $("energy-next").onclick = () => {
    page++;
    render();
  };
  $("energy-run").onclick = () => {
    clearResult();
    try {
      if (!plan) throw Error("현재 소재 검토의 상태표를 먼저 만드세요");
      const nc = getNC(),
        stock = getStock(),
        m = model(),
        own = revision,
        w = new Worker(new URL("./nc-energy.worker.js", import.meta.url), {
          type: "module",
        });
      worker = w;
      $("energy-run").disabled = true;
      $("energy-cancel").disabled = false;
      $("energy-status").textContent = "시간·에너지 계산 중…";
      const reject = (text) => {
        if (worker !== w || revision !== own) return;
        clearResult();
        $("energy-status").textContent = text;
      };
      timer = setTimeout(() => reject("30초 상한 초과 · 계산 취소"), 30000);
      w.onerror = () =>
        reject("에너지 Worker 오류 · 새로고침 후 다시 연결하세요");
      w.onmessage = ({ data }) => {
        if (worker !== w || data.revision !== own) return;
        if (data.error) {
          reject(data.error);
          return;
        }
        stop();
        analysis = data.analysis;
        onChange();
        $("energy-status").textContent = analysis.issues.length
          ? `미정 ${analysis.issues.length}구간 · 전체 합계 제한`
          : "입력 범위 시나리오 완료 · 실측 정확도 미검증";
        $("energy-summary").textContent =
          `${analysis.model.provenance === "assumption" ? "사용자 가정" : "사용자 측정 입력 (보정 아님)"} · ${analysis.model.machine}\n전체 모델 시간 ${fmt(analysis.totalTime)}초\n전체 소비 ${range(analysis.totalEnergy)} kWh\n평균 전체 전력 ${range(analysis.averagePower, 3)} kW\n시간을 아는 ${analysis.knownTimeRows}구간 소계 ${fmt(analysis.knownTime)}초\n소비를 아는 ${analysis.knownEnergyRows}구간 소계 ${range(analysis.knownEnergy)} kWh\n미정 ${analysis.issues.length}구간 · 입력 범위는 신뢰구간 아님\n소재 제약: 잔삭 ${fmt(analysis.stockConstraints.remaining)} / 과절삭 ${fmt(analysis.stockConstraints.overcut)} mm³${analysis.comparison ? `\n별도 검증 시간 차이 ${fmt(analysis.comparison.timeDifferencePercent)}% · 소비 차이 ${range(analysis.comparison.energyDifferencePercent, 3)}% (보정 미적용)` : ""}`;
        render();
      };
      w.postMessage({
        revision: own,
        nc: compactEnergyNC(nc),
        stock: {
          ncSourceHash: stock.ncSourceHash,
          segments: stock.segments,
          setup: { initialTool: stock.setup.initialTool },
          rapidContactLines: stock.rapidContactLines,
          remaining: stock.remaining,
          overcut: stock.overcut,
        },
        model: m,
      });
    } catch (e) {
      $("energy-status").textContent = e.message;
    }
  };
  $("energy-cancel").onclick = () => {
    clearResult();
    $("energy-status").textContent = "사용자가 에너지 계산 취소";
  };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && worker) {
      e.preventDefault();
      $("energy-cancel").click();
    }
  });
  return {
    invalidate,
    analysis: () => analysis,
    export: () => ({ model: model(), analysis }),
  };
}
