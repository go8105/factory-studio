import { createVoiceDemo } from "./nc-voice-demo.js";
import { FANUC_REVIEW_PROFILE } from "./nc-controller.js";
import { createNCPostReview } from "./nc-post-review.js";
import { createHughVoice } from "./hugh-voice.js";
import { createPlaybackReview } from "./nc-playback-review.js";
import voiceSample from "../examples/cnc_CADV01_2026-10-08_voice.ngc?raw";
import { createProposalReview } from "./nc-proposal-review.js";
import proposalSample from "../examples/cnc_CAD15_2026-10-08_dwell.ngc?raw";
import { createEnergyReview } from "./nc-energy-review.js";
import { createStockReview } from "./nc-stock-review.js";
import { NCViewer } from "./nc-viewer.js";
import { NC_PROFILE, NC_LIMITS } from "./nc-parser.js";
import stockSample from "../examples/cnc_CAD13_2026-10-07_face.ngc?raw";
import sample from "../examples/cnc_CAD12_2026-10-07_milling.ngc?raw";
import "./nc-style.css";
import { arrangeNCReview } from "./nc-layout.js";
const $ = (s) => document.querySelector(s),
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
$("#app").innerHTML =
  `<header><strong>FORM STUDIO · NC</strong><span>3축 밀링 경로 검토</span><nav><button id="sample">경로 예제</button><button id="stock-sample">소재 예제 NC</button><button id="proposal-sample">대기 검토 예제 NC</button><button id="voice-sample">YC 발표 예제 NC (합성)</button><button id="load">NC 파일 열기</button><button id="export" disabled>분석 JSON 저장</button></nav><input id="file" type="file" accept=".nc,.ngc,.tap,.gcode,.cnc,.txt" hidden></header>
<div class="notice">NC에서 CAD 설계 이력은 복원하지 않습니다. 소재·STEP 정합 후 제한된 상면 가공 검토가 가능합니다. 시간·소비는 장비 입력과 별도 가정 모델로 검토합니다.</div>
<main><aside class="inputs"><h2>파일과 초기 설정</h2><p id="filename">파일 미선택 · 서버 전송 없음</p><label>컨트롤러 프로필<select id="profile"><option value="${NC_PROFILE}">LinuxCNC 기반 · 3축 밀링 (제한)</option><option value="${FANUC_REVIEW_PROFILE}">FANUC 검토용 · 기종 미정 · G4 P 밀리초</option></select></label><p class="muted">선택 프로필의 숫자 리터럴 부분집합. LinuxCNC G4 P초 / FANUC 검토용 G4 P밀리초·O번호 필요. 실제 장비 호환 보증 없음.</p><label>초기 단위<select id="unit"><option value="mm">mm</option><option value="inch">inch</option></select></label><div class="xyz">${["X", "Y", "Z"].map((axis) => `<label>초기 ${axis}<input id="${axis}" type="number" step="any" value="0"></label>`).join("")}</div><p class="muted">G54 작업좌표의 시작 위치. 기계좌표 변환 없음. 기본 G17/G90/증분 I·J/G94/G0, 보정 해제·주축/쿨런트 OFF, 활성 공구 미정.</p><label class="check"><input id="confirmed" type="checkbox">초기 좌표·단위와 기본 상태를 확인했습니다</label><label>입력 NC (붙여넣기)<textarea id="source" spellcheck="false" placeholder="G-code를 붙여넣거나 파일을 여세요"></textarea></label><div class="buttons"><button id="analyze">경로 해석</button><button id="cancel" disabled>해석 취소</button><button id="support">지원 명령</button></div><p id="status" role="status">NC를 입력하고 초기 설정을 확인하세요.</p><p class="muted">2MiB · 50,000행 · 500,000표시점 · 30초 상한. UTF-8/ASCII 텍스트.</p></aside>
<section class="workspace"><div class="view-head"><strong id="summary">해석 결과 없음</strong><button id="fit">전체 보기</button></div><div id="viewer"></div><div class="legend"><span>● 급속 G0</span><span>● 이송 G1/G2/G3 (절삭 여부 미정)</span><span>● 선택 구간</span></div><div class="navigation"><button id="previous" disabled>이전 이동</button><input id="position" aria-label="이동 구간" type="range" min="0" max="0" value="0" disabled><button id="next" disabled>다음 이동</button></div><pre id="detail">원본 행 또는 3D 경로를 선택하세요.</pre><div class="code-head"><h2>원본 NC · 행별 상태</h2><button id="page-prev" disabled>앞 200행</button><span id="page-label"></span><button id="page-next" disabled>뒤 200행</button></div><div id="code" role="list" aria-label="원본 NC 행"></div></section></main>
<dialog id="help"><h2>지원 프로필과 해석 경계</h2><p>G0/G1 XYZ · G17 XY G2/G3(I/J 또는 부호 있는 R, I/J 전체 원) · G20/21 · G90/91 · G91.1 · G94 · G54 · G40/G49/G80 · G4 P초 · F/S/T · M3/4/5/6/7/8/9/2/30.</p><p>FANUC 검토용은 O1~O7999·G4 P밀리초 정수, G91.1 명령 미지원입니다. 내보내기는 결과 패널에서 검토용 파일로만 제공합니다.</p><p>G43/H, G41/42/D, G28/G53, G18/19, 헬릭스/다회전, 고정 사이클, 다른 원점, 매크로/서브프로그램, 선택 블록, M0/1, 사용자 코드는 차단합니다. M 이벤트와 이동은 별도 행만 지원합니다.</p><p>첫 미지원/오류부터 이후 경로는 연결하지 않습니다. M6는 교환 이벤트만, 급속은 끝점 연결만 표시합니다. 장비의 자동 이동/전체 시간/kWh는 미정입니다. F 전체 보기 · Esc 해석 취소.</p><a href="https://linuxcnc.org/docs/html/gcode/g-code.html" target="_blank" rel="noopener">LinuxCNC 공식 명세</a><button id="close-help">닫기</button></dialog>`;
let result = null,
  worker = null,
  revision = 0,
  timer = null,
  page = 0,
  selected = null,
  fileName = "붙여넣기 NC",
  readRevision = 0,
  sourceText = "";
const viewer = new NCViewer($("#viewer"), (id) => selectMove(id));
let energyReview, proposalReview;
const stockReview = createStockReview(
  viewer,
  () => result,
  (line) => selectLine(line),
  () => energyReview?.invalidate(),
);
energyReview = createEnergyReview(
  () => result,
  () => stockReview.analysis(),
  (line) => selectLine(line),
  () => proposalReview?.invalidate(),
);
const playback = createPlaybackReview(
  () => result,
  () => energyReview.analysis(),
  viewer,
  selectLine,
);
proposalReview = createProposalReview(
  () => result,
  () => stockReview.analysis(),
  () => energyReview.analysis(),
  (line) => selectLine(line),
  playback,
  viewer,
);
const voice = createHughVoice({
  propose() {
    const r = proposalReview.run({ present: true });
    if (r.reasons.length) throw Error("제안 차단: " + r.reasons.join(" · "));
    if (!r.candidates.length) throw Error("검토할 대기를 먼저 선택하세요");
    const valid = r.candidates.filter((c) => c.status !== "blocked");
    if (!valid.length)
      throw Error(
        "모든 후보가 차단되었습니다. 대기 근거와 최소 시간을 확인하세요",
      );
    const lower = r.candidates.filter((c) => c.status === "conditional-lower");
    const suggestion = lower.length
      ? `입력 범위의 소비 감소 후보는 ${lower.map((c) => c.number + "번").join(", ")}입니다. 첫 감소 후보 ${lower[0].number}번의 예상 시간은 ${lower[0].seconds.toFixed(1)}초, 소비는 ${lower[0].energy.map((v) => v.toFixed(3)).join("에서 ")} 킬로와트시입니다.`
      : "후보의 소비 범위가 겹치거나 비교 여유가 미정이라 우열 판단은 불가합니다.";
    return `${r.candidates.length}개 후보를 비교했습니다. ${suggestion} 실제 품질과 절감은 미검증입니다. 재생할 번호를 말씀하세요.`;
  },
  play: (number) => proposalReview.play(number),
  stop: () => playback.pause(),
});
arrangeNCReview(document, () => ({
  nc: !!result?.complete,
  stock: !!stockReview.analysis(),
  energy: !!energyReview.analysis(),
  quality:
    !!proposalReview.export().report &&
    !proposalReview.export().report.reasons.length,
}));
const postReview = createNCPostReview(() => ({
  nc: result,
  stock: stockReview.analysis(),
  energy: energyReview.analysis(),
  proposalSettings: proposalReview.export().settings,
}));
function message(text) {
  $("#status").textContent = text;
}
function stop() {
  revision++;
  if (worker) worker.terminate();
  worker = null;
  clearTimeout(timer);
  $("#cancel").disabled = true;
  $("#analyze").disabled = false;
}
function clear() {
  postReview.reset();
  stockReview.resetNC(true);
  result = null;
  selected = null;
  page = 0;
  viewer.show(null);
  $("#code").replaceChildren();
  $("#detail").textContent = "원본 행 또는 3D 경로를 선택하세요.";
  $("#summary").textContent = "해석 결과 없음";
  $("#export").disabled = true;
  $("#position").disabled = true;
  $("#previous").disabled = true;
  $("#next").disabled = true;
  $("#page-prev").disabled = true;
  $("#page-next").disabled = true;
  $("#page-label").textContent = "";
}
function invalidate() {
  stop();
  clear();
  message("입력 변경 · 이전 분석 무효화. 다시 해석하세요.");
}
for (const id of ["source", "profile", "unit", "X", "Y", "Z", "confirmed"])
  $("#" + id).addEventListener("input", () => {
    readRevision++;
    invalidate();
  });
$("#source").addEventListener("input", () => {
  sourceText = $("#source").value;
  fileName = "직접 입력 NC";
  $("#filename").textContent = "직접 입력 NC · 서버 전송 없음";
});
$("#load").onclick = () => $("#file").click();
$("#file").onchange = async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  readRevision++;
  const own = readRevision;
  invalidate();
  fileName = file.name;
  $("#filename").textContent = fileName + " · 브라우저 메모리에서만 읽음";
  sourceText = "";
  $("#source").value = "";
  try {
    if (file.size > NC_LIMITS.bytes) throw Error("파일 상한 2MiB 초과");
    const buffer = await file.arrayBuffer();
    if (own !== readRevision) return;
    sourceText = new TextDecoder("utf-8", {
      fatal: true,
      ignoreBOM: true,
    }).decode(buffer);
    $("#source").value = sourceText;
    message("파일 읽기 완료 · 초기 설정을 확인한 뒤 경로를 해석하세요.");
  } catch (error) {
    if (own === readRevision) message(error.message);
  }
};
$("#sample").onclick = () => {
  $("#profile").value = NC_PROFILE;
  readRevision++;
  invalidate();
  fileName = "cnc_CAD12_2026-10-07_milling.ngc";
  $("#filename").textContent = fileName + " · 합성 예제";
  sourceText = sample;
  $("#source").value = sample;
  $("#unit").value = "mm";
  for (const axis of ["X", "Y", "Z"]) $("#" + axis).value = "0";
  $("#confirmed").checked = true;
  message("합성 예제 초기 XYZ=0mm · 경로 해석을 누르세요.");
};
$("#stock-sample").onclick = () => {
  $("#profile").value = NC_PROFILE;
  readRevision++;
  invalidate();
  fileName = "cnc_CAD13_2026-10-07_face.ngc";
  sourceText = stockSample;
  $("#filename").textContent = fileName + " · 합성 면 가공 예제";
  $("#source").value = stockSample;
  $("#unit").value = "mm";
  ["X", "Y", "Z"].forEach((axis, i) => ($("#" + axis).value = [-3, -1, 10][i]));
  $("#confirmed").checked = true;
  message("20×20×8 소재 / T1 지름4·날15 / 목표 STEP 예제와 함께 검토하세요.");
};
$("#proposal-sample").onclick = () => {
  $("#profile").value = NC_PROFILE;
  $("#stock-sample").click();
  fileName = "cnc_CAD15_2026-10-08_dwell.ngc";
  sourceText = proposalSample;
  $("#source").value = proposalSample;
  $("#filename").textContent = fileName + " · 합성 대기 검토 예제";
  message(
    "소재 예제와 동일 형상 · 종료 전 합성 G4 600초. 실제 공정 목적이 아닙니다.",
  );
};
const voiceDemo = createVoiceDemo({
  voice,
  getNC: () => result,
  getStock: () => stockReview.export(),
  getEnergy: () => energyReview.analysis(),
  load() {
    $("#profile").value = NC_PROFILE;
    $("#stock-sample").click();
    fileName = "cnc_CADV01_2026-10-08_voice.ngc";
    sourceText = voiceSample;
    $("#source").value = voiceSample;
    $("#filename").textContent = fileName + " · 합성 발표 예제";
  },
});
$("#voice-sample").onclick = () => voiceDemo.start();
$("#analyze").onclick = () => {
  stop();
  clear();
  const text = sourceText;
  const initial = ["X", "Y", "Z"].map((k) =>
    $("#" + k).value.trim() === "" ? NaN : Number($("#" + k).value),
  );
  const settings = {
    profile: $("#profile").value,
    unit: $("#unit").value,
    initial,
    confirmed: $("#confirmed").checked,
  };
  if (!text.trim()) {
    message("NC 내용을 입력하세요.");
    return;
  }
  if (!settings.confirmed || !initial.every(Number.isFinite)) {
    message("초기 XYZ·단위 확인이 필요합니다.");
    return;
  }
  if (new TextEncoder().encode(text).length > NC_LIMITS.bytes) {
    message("파일 상한 2MiB 초과");
    return;
  }
  const own = revision,
    w = new Worker(new URL("./nc-worker.js", import.meta.url), {
      type: "module",
    });
  worker = w;
  $("#cancel").disabled = false;
  $("#analyze").disabled = true;
  message("NC 해석 중…");
  const reject = (text) => {
    if (worker !== w || own !== revision) return;
    stop();
    clear();
    message(text);
  };
  w.onerror = () => reject("해석 Worker 오류 · 다시 시도하세요.");
  timer = setTimeout(
    () => reject("30초 상한 초과 · 해석 취소"),
    NC_LIMITS.milliseconds,
  );
  w.onmessage = ({ data }) => {
    if (worker !== w || data.revision !== revision) return;
    if (data.progress) {
      message(
        `해석 중 ${data.progress.line.toLocaleString()} / ${data.progress.total.toLocaleString()}행`,
      );
      return;
    }
    if (data.error) {
      reject(data.error);
      return;
    }
    result = data.result;
    result.fileName = fileName;
    stop();
    viewer.show(result);
    stockReview.resetNC(true);
    $("#export").disabled = false;
    $("#summary").textContent =
      `${result.complete ? "지원 범위 해석 완료" : "부분 해석 · 전체 분석 차단"} · ${result.segments.length.toLocaleString()}이동 / ${result.events.length}이벤트`;
    message(
      result.complete
        ? `해석 완료 · ${result.ended ? "종료 명령 확인" : "종료 명령 없음 (EOF)"} · 시간·소비는 별도 장비 모델에서 계산`
        : `${result.diagnostics[0].line}행: ${result.diagnostics[0].message} · 이후 미해석`,
    );
    $("#position").max = Math.max(0, result.segments.length - 1);
    $("#position").disabled = !result.segments.length;
    renderCode();
    if (result.segments.length) selectMove(0);
  };
  w.postMessage({ revision: own, text, settings });
};
$("#cancel").onclick = () => {
  readRevision++;
  stop();
  clear();
  message("사용자가 해석 취소 · 분석 결과 없음");
};
const statusLabels = {
  ok: "해석",
  empty: "주석/빈행",
  delimiter: "구분자",
  error: "오류",
  blocked: "미해석",
  "after-end": "실행 제외",
};
function renderCode() {
  if (!result) return;
  const start = page * 200,
    rows = result.blocks.slice(start, start + 200);
  $("#code").innerHTML = rows
    .map(
      (b) =>
        `<button role="listitem" class="code-row ${b.status} ${selected === b.line ? "selected" : ""}" data-line="${b.line}" aria-label="${b.line}행 ${statusLabels[b.status]}" aria-current="${selected === b.line ? "true" : "false"}"><span>${b.line}</span><code>${esc(b.raw || " ")}</code><small>${statusLabels[b.status]}</small></button>`,
    )
    .join("");
  $("#page-label").textContent =
    `${start + 1}–${Math.min(start + 200, result.blocks.length)} / ${result.blocks.length}행`;
  $("#page-prev").disabled = page === 0;
  $("#page-next").disabled = start + 200 >= result.blocks.length;
}
function selectLine(line) {
  if (!result) return;
  const b = result.blocks[line - 1];
  if (!b) return;
  selected = line;
  page = Math.floor((line - 1) / 200);
  renderCode();
  const row = $("#code .selected"),
    list = $("#code");
  if (row) {
    const a = row.getBoundingClientRect(),
      b = list.getBoundingClientRect();
    if (a.top < b.top) list.scrollTop -= b.top - a.top;
    else if (a.bottom > b.bottom) list.scrollTop += a.bottom - b.bottom;
  }
  viewer.select(b.segment);
  const state = b.after ?? b.before;
  const move = b.segment !== null ? result.segments[b.segment] : null;
  const events = b.events.map((id) => result.events[id]);
  $("#detail").textContent =
    `${line}행 · ${statusLabels[b.status]}${b.message ? " · " + b.message : ""}\n${move ? `${move.code} 시작 [${move.from.map((v) => v.toFixed(3))}] → 끝 [${move.to.map((v) => v.toFixed(3))}] mm\n길이 ${move.length.toFixed(3)} mm${move.arc ? ` · 반경 ${move.arc.radius.toFixed(3)} mm · ${move.arc.clockwise ? "CW" : "CCW"}` : ""}\n` : ""}${state ? `${state.unit} / ${state.distance === "absolute" ? "G90" : "G91"} / G17 / G91.1 / G94 / G54\nF ${state.feed ?? "미정"} mm/min · S ${state.rpm} rpm · 선택 T ${state.selectedTool ?? "미정"} / 활성 T ${state.tool ?? "미정"}\n주축 ${state.spindle} · 쿨런트 ${state.coolant.join("+") || "off"}` : "이 행의 상태는 해석되지 않았습니다."}${events.length ? "\n이벤트 " + events.map((v) => v.kind + (v.seconds !== undefined ? ` (${v.seconds ?? "미정"}초)` : "")).join(", ") : ""}\n시간·소비: 장비 모델에서 확인 (NC만으로 미정)`;
  if (move) $("#position").value = move.id;
  $("#previous").disabled =
    !result.segments.length || Number($("#position").value) <= 0;
  $("#next").disabled =
    !result.segments.length ||
    Number($("#position").value) >= result.segments.length - 1;
}
function selectMove(id) {
  const s = result?.segments[id];
  if (s) selectLine(s.line);
}
$("#code").onclick = (e) => {
  const b = e.target.closest("[data-line]");
  if (b) selectLine(Number(b.dataset.line));
};
$("#position").oninput = (e) => selectMove(Number(e.target.value));
$("#previous").onclick = () => selectMove(Number($("#position").value) - 1);
$("#next").onclick = () => selectMove(Number($("#position").value) + 1);
$("#page-prev").onclick = () => {
  page--;
  renderCode();
};
$("#page-next").onclick = () => {
  page++;
  renderCode();
};
$("#fit").onclick = () => viewer.fit();
$("#support").onclick = () => $("#help").showModal();
$("#close-help").onclick = () => $("#help").close();
$("#export").onclick = () => {
  if (!result) return;
  const blob = new Blob(
      [
        JSON.stringify(
          {
            ...result,
            stockReview: stockReview.export(),
            energyReview: energyReview.export(),
            proposalReview: proposalReview.export(),
          },
          null,
          2,
        ),
      ],
      {
        type: "application/json",
      },
    ),
    url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = "nc-analysis.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && worker) {
    e.preventDefault();
    $("#cancel").click();
  } else if (
    e.key.toLowerCase() === "f" &&
    !e.ctrlKey &&
    !e.metaKey &&
    !e.altKey &&
    !e.target.closest("input,textarea,select")
  ) {
    e.preventDefault();
    viewer.fit();
  }
});
