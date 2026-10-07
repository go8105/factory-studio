import {
  DraftHistory,
  shortcutCommand,
  SHORTCUT_HELP,
} from "./editor-commands.js";
import "./style.css";
import freeExample from "../examples/cnc_E1_2026-10-06_L-slot-arc.form.json";
import {
  emptyModel,
  defaultTool,
  sampleModel,
  clone,
  round,
  validateModel,
  validateTool,
  parseModel,
  ring,
  bounds,
  distance,
} from "./model.js";
import { Viewer } from "./viewer.js";
import { syncProfile, profileRing } from "./profile.js";

const icons = {
  cube: "M12 3 3 8v9l9 5 9-5V8L12 3Zm0 0v10m-9-5 9 5 9-5m-9 5v9",
  profile: "M3 20V4h7v8h11v8H3Z",
  arc: "M3 17C3 1 21 1 21 17",
  slot: "M8 5h8a7 7 0 0 1 0 14H8A7 7 0 0 1 8 5Z",
  rect: "M4 5h16v14H4z",
  circle: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  select: "m5 3 14 10-7 1-3 7-4-18Z",
  extrude: "m4 8 8-4 8 4-8 4-8-4Zm0 0v9l8 4 8-4V8m-8 4v9",
  cut: "M4 5h16v15H4V5Zm4 0v7h8V5m-4 9v4m-2-2 2 2 2-2",
  play: "m8 4 12 8-12 8V4Z",
  pause: "M8 4v16M16 4v16",
  save: "M5 3h12l4 4v14H3V3h2Zm2 0v6h10V3M7 21v-8h10v8",
  folder: "M3 6h7l2 3h9v11H3V6Z",
  undo: "m8 4-5 5 5 5M3 9h10a7 7 0 0 1 0 14",
  redo: "m16 4 5 5-5 5m5-5H11a7 7 0 0 0 0 14",
  trash: "M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7",
  fit: "M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5",
  download: "M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4",
  plus: "M12 4v16M4 12h16",
  reset: "M4 10a8 8 0 1 1 1 8M4 3v7h7",
  top: "M4 4h16v16H4V4Zm0 5h16M9 4v16",
  help: "M9 8a3 3 0 1 1 5 2c-2 1-2 2-2 4m0 3v1",
};
const icon = (key) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[key] ? `<path d="${icons[key]}"/>` : ""}</svg>`;
const esc = (s) =>
  String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const $ = (s) => document.querySelector(s);
const uid = () => `f-${crypto.randomUUID().slice(0, 8)}`;
let model = emptyModel(),
  selected = null,
  draft = null,
  mode = "design",
  view = "sketch",
  drawTool = "select",
  tool = defaultTool();
let past = [],
  future = [],
  path = null,
  revision = 0,
  request = 0,
  playing = false,
  fraction = 0,
  busy = false,
  queued = null,
  speed = 10,
  showPaths = true;
let gridStep = 1,
  endpointSnap = true,
  arcClicks = [],
  camPending = false,
  proposals = null,
  camTimer = null;
const draftHistory = new DraftHistory();
const draftState = () => ({
  draft: clone(draft),
  arcClicks: clone(arcClicks),
  drawTool,
});
function recordDraft(before, group = null) {
  draftHistory.record(before, draftState(), group);
}
function restoreDraft(state) {
  if (!state) return;
  ({ draft, arcClicks, drawTool } = state);
  dragStart = null;
  render();
}
function updateHistoryButtons() {
  document.querySelector('[data-action="undo"]').disabled = draft
    ? !draftHistory.canUndo
    : !past.length;
  document.querySelector('[data-action="redo"]').disabled = draft
    ? !draftHistory.canRedo
    : !future.length;
}
const scope = new URLSearchParams(location.search).get("scope");
const storageKey = scope
  ? `form-studio-design-v1:${scope}`
  : "form-studio-design-v1";
try {
  const saved = localStorage.getItem(storageKey);
  if (saved) model = parseModel(saved);
} catch {}
if (model.stock) {
  selected = "stock";
  view = "solid";
}
$("#app").innerHTML = `
<header class="app-header"><a class="brand" href="#" aria-label="Form Studio 홈"><span class="brand-mark">${icon("cube")}</span><span>FORM<span class="brand-light"> STUDIO</span><small>DESIGN / MANUFACTURE</small></span></a><div class="document"><input id="document-name" aria-label="설계 이름" maxlength="80"/><span class="save-status" id="save-status">이 브라우저에 저장</span></div><nav class="file-actions"><button data-action="new" title="새 설계 · 이전 작업은 실행 취소로 복구">${icon("plus")}새 설계</button><button data-action="open">${icon("folder")}열기</button><button data-action="save">${icon("save")}저장</button><button data-action="stl" title="삼각형 메시 STL · mm">${icon("download")}STL</button></nav>${new URLSearchParams(location.search).get("poc") === "1" ? `<a class="prototype" href="/cad-cam?view=soap" target="_parent">비누 POC ↗</a>` : `<span class="prototype">검토 시제품</span>`}</header>
<div class="workspace-nav"><div class="tabs"><button data-action="design" class="active">01 <strong>설계</strong></button><button data-action="cam">02 <strong>가공 시뮬레이션</strong></button></div><a class="part-link" href="${new URLSearchParams(location.search).get("embedded") === "1" ? "/cad-cam?view=part" : "./part-design.html?" + new URLSearchParams(location.search)}" target="${new URLSearchParams(location.search).get("embedded") === "1" ? "_parent" : "_self"}">3D 부품 설계 ↗</a><span class="scope">2.5D · 단일 부품 · mm</span><button data-action="help" class="icon-button" aria-label="사용 방법" title="? 단축키 도움말">${icon("help")}</button></div>
<div class="toolstrip"><div class="tools" id="tools"></div><div class="history-actions"><button data-action="undo" class="icon-button" aria-label="실행 취소" title="실행 취소 Ctrl/⌘ Z">${icon("undo")}</button><button data-action="redo" class="icon-button" aria-label="다시 실행" title="Ctrl/⌘+Shift+Z · Ctrl+Y">${icon("redo")}</button><span class="divider"></span><button data-action="fit" class="icon-button" aria-label="화면 맞춤">${icon("fit")}</button></div></div>
<main class="workbench"><aside class="left-panel"><div class="panel-heading">설계 탐색기 <span id="feature-count">0</span></div><div id="tree"></div><div class="left-bottom"><div class="mini-label">YOUR NEXT STEP</div><p id="next-step"></p><button class="text-button" data-action="sample">연습 부품 불러오기 ↗</button><button class="text-button" data-action="free-sample">자유 스케치 예제 ↗</button><div class="quiet-note">직접 그린 형상으로 설계합니다.<br>변경 사항은 로컬에 자동 저장됩니다.</div></div></aside>
<section class="viewport"><div class="view-top"><div class="view-switch"><button data-action="sketch">평면 스케치</button><button data-action="solid">3D 모델</button></div><span id="view-label">XY 스케치 평면</span></div><div id="three-view"></div><svg id="sketch" aria-label="스케치 작업면" role="application"><defs><pattern id="minor-grid" width="5" height="5" patternUnits="userSpaceOnUse"><path d="M 5 0 L 0 0 0 5" fill="none" stroke="#e0e4e2" stroke-width=".15"/></pattern><pattern id="major-grid" width="25" height="25" patternUnits="userSpaceOnUse"><rect width="25" height="25" fill="url(#minor-grid)"/><path d="M25 0H0V25" fill="none" stroke="#cdd3d2" stroke-width=".23"/></pattern></defs><rect id="grid-bg" x="-500" y="-500" width="1000" height="1000" fill="url(#major-grid)"/><path d="M-500 0H500M0-500V500" stroke="#9fadaa" stroke-width=".22"/><g id="sketch-shapes"></g><g id="draft-shape"></g></svg><div class="empty-guide" id="empty-guide"><span class="eyebrow">FROM YOUR FIRST LINE</span><h1>생각을, 형상으로.</h1><p>선을 이어 윤곽을 그리고 두께를 더하세요.<br>첫 스케치가 부품의 시작이 됩니다.</p><button class="primary" data-action="rect">${icon("rect")}사각형으로 시작</button><button class="text-button" data-action="sample">먼저 연습 부품 살펴보기 →</button></div><div class="view-bottom"><span id="view-hint"></span><div class="axis-label"><span class="axis-x">X</span><span class="axis-y">Y</span><span>Z</span></div></div><div id="cam-legend" hidden><span class="dot cut"></span>절삭 이동 <span class="dot rapid"></span>안전 높이 이동</div></section>
<aside class="right-panel"><div class="panel-heading" id="properties-heading">속성</div><div id="properties"></div></aside></main>
<section class="bottom-panel"><div id="timeline"></div><div id="simulation-controls" hidden></div></section>
<footer class="statusbar"><span><span class="status-dot"></span><span id="status-text">준비됨</span></span><span id="model-summary">빈 설계 · 원점 XY / Z↑</span><span>로컬 작업 공간</span></footer>
<div id="toast" role="status" aria-live="polite"></div><input type="file" id="file-input" accept=".json,application/json" hidden/>
<dialog id="help-dialog"><div class="dialog-head"><h2>직접 설계하는 첫 부품</h2><button data-action="close-help" aria-label="닫기">×</button></div><p class="shortcut-note">${SHORTCUT_HELP}</p><ol><li><b>스케치</b> — 사각형은 대각선으로, 원은 중심에서 바깥으로 드래그합니다. 1mm 격자에 맞춰집니다.</li><li><b>돌출</b> — 오른쪽에서 치수와 높이를 정하고 ‘돌출 만들기’를 누릅니다.</li><li><b>파내기</b> — 새 사각형·원을 추가하고 깊이를 정합니다. 기존 작업을 선택해 치수 변경·복제·삭제도 가능합니다.</li><li><b>가공</b> — 공구 지름·깊이 간격을 정하고 경로를 생성합니다. 재생하거나 진행 막대를 움직여 소재 제거를 확인합니다.</li><li><b>보관</b> — JSON으로 편집 가능한 설계를 저장하고, STL로 3D 메시를 내보냅니다.</li></ol><p>선 연결은 점을 클릭하고 첫 점 또는 ‘윤곽 닫기’로 마칩니다. 3점 원호는 시작·통과·끝을 클릭하면 끝에서 시작까지 직선으로 닫힙니다. 슬롯은 길이·폭·각도로 편집합니다. 좌표 치수 편집과 격자·끝점 스냅을 지원합니다. 평면 스케치의 돌출·상면 포켓을 지원합니다. 자유 곡면·조립·스케치 구속·STEP·기계용 NC 출력은 포함하지 않습니다. 소재 제거는 격자 근사이며 실제 절삭력·공구 홀더·고정구 충돌은 계산하지 않습니다.</p><button class="primary" data-action="close-help">설계 시작하기</button></dialog>`;
const viewer = new Viewer($("#three-view"), (p) => {
  if (mode !== "design") return;
  const f = [...model.features]
    .reverse()
    .find((f) => distance(f, p.x, p.y) <= 0);
  select(f?.id ?? "stock");
});
let camWorker;
function resetCamWorker() {
  camWorker?.terminate();
  camWorker = new Worker(new URL("./cam.worker.js", import.meta.url), {
    type: "module",
  });
  const currentWorker = camWorker;
  camWorker.onmessage = ({ data }) => {
    if (currentWorker !== camWorker) return;
    if (data.revision !== revision) return;
    clearTimeout(camTimer);
    camPending = false;
    if (data.error) {
      renderProperties();
      $("#status-text").textContent = "경로 계산 실패 · 다시 시도하세요";
      toast(data.error, true);
      return;
    }
    if (data.proposals) {
      proposals = data.proposals;
      renderProperties();
      if (path) requestSimulation(fraction);
      $("#status-text").textContent = "경로 제안 준비됨 · 적용 전";
      toast("후보를 비교하고 적용할 경로를 선택하세요.");
    } else {
      path = data.path;
      fraction = 0;
      $("#status-text").textContent = "경로 준비됨";
      render();
      toast("가공 경로를 생성했습니다. 재생으로 소재 제거를 확인하세요.");
    }
  };
  camWorker.onerror = () =>
    cancelCam("가공 계산기를 불러오지 못했습니다. 다시 시도하세요.");
}
function cancelCam(
  message = "경로 계산을 취소했습니다. 기존 경로를 유지합니다.",
) {
  clearTimeout(camTimer);
  camPending = false;
  resetCamWorker();
  render();
  $("#status-text").textContent = "경로 계산 중단됨";
  toast(message, true);
}
resetCamWorker();
function calculateCam(propose = false) {
  try {
    const next = Object.fromEntries(
      [...new FormData($("#tool-form"))].map(([k, v]) => [k, Number(v)]),
    );
    validateTool(next);
    if (!propose || JSON.stringify(next) !== JSON.stringify(tool)) invalidate();
    stop();
    tool = next;
    proposals = null;
    camPending = true;
    camWorker.postMessage({
      model,
      tool,
      revision,
      action: propose ? "propose" : "generate",
    });
    camTimer = setTimeout(
      () => cancelCam("30초 계산 한도를 초과했습니다. 기존 경로를 유지합니다."),
      30000,
    );
    render();
    $("#status-text").textContent = propose
      ? "품질 우선 후보 비교 중…"
      : "가공 윤곽 계산 중…";
  } catch (error) {
    toast(error.message, true);
  }
}
function proposalHtml() {
  if (!proposals) return "";
  const base = proposals.candidates[0].metrics;
  return `<section class="path-proposals" aria-label="품질 우선 경로 비교"><h3>품질 우선 경로 비교</h3><p>${esc(proposals.reason)}</p>${proposals.candidates.map((c) => `<article><b>${esc(c.name)}${c.id === proposals.recommendedId ? " · 제안" : ""}</b><p>안전 높이·공구 여유 검사 통과<br>절삭 방향·깊이·마무리 유지<br>동일 격자 잔삭 ${c.metrics.residualVolume == null ? "—" : (c.metrics.residualVolume / 1000).toFixed(2) + " cm³"}</p><dl><dt>절삭 거리</dt><dd>${c.metrics.cutLength.toFixed(1)} mm</dd><dt>비절삭 거리</dt><dd>${c.metrics.rapidLength.toFixed(1)} mm</dd><dt>이송 시간 추정</dt><dd>${c.metrics.seconds.toFixed(1)} 초</dd><dt>비절삭 이동 감소</dt><dd>${((100 * (base.rapidLength - c.metrics.rapidLength)) / Math.max(base.rapidLength, 1e-9)).toFixed(1)}%</dd><dt>소비 에너지 / 절감률</dt><dd>산정 불가</dd></dl><button data-action="apply-${c.id}" class="full">${c.id === proposals.recommendedId ? "이 제안 적용" : "이 경로 적용"}</button></article>`).join("")}<p class="quiet-note">장비·재질 정보가 없어 kWh를 계산하지 않습니다. 거리 감소는 전력 절감률이 아닙니다. 전역 최적·실제 Ra/치수 공차를 보증하지 않습니다.</p></section>`;
}
const worker = new Worker(new URL("./simulation.worker.js", import.meta.url), {
  type: "module",
});
worker.onmessage = ({ data }) => {
  busy = false;
  if (data.revision === revision) {
    if (data.error) {
      playing = false;
      toast(data.error, true);
    } else if (mode === "cam") {
      viewer.showSimulation(data.grid, data.pos, tool.diameter);
      viewer.paths.visible = showPaths;
      $("#removed-volume").textContent =
        `${(data.grid.removed / 1000).toFixed(2)} cm³`;
      $("#residual-volume").textContent =
        `${(data.residual / 1000).toFixed(2)} cm³`;
      $("#sim-resolution").textContent =
        `格子 ${Math.max(data.grid.dx, data.grid.dy).toFixed(2)} mm`.replace(
          "格子",
          "격자",
        );
      $("#status-text").textContent =
        `소재 제거 ${Math.round(data.fraction * 100)}% · 공구 Z ${data.pos.z.toFixed(2)} mm`;
    }
  }
  if (queued !== null) {
    const q = queued;
    queued = null;
    requestSimulation(q);
  }
};
worker.onerror = () => {
  busy = false;
  playing = false;
  toast("시뮬레이션 계산을 완료하지 못했습니다. 경로를 다시 생성하세요.", true);
};
function toast(text, error = false) {
  const el = $("#toast");
  el.textContent = text;
  el.className = error ? "error visible" : "visible";
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("visible"), 5000);
}
function stop() {
  playing = false;
}
if (new URLSearchParams(location.search).get("poc") === "1") {
  const link = document.querySelector(".prototype");
  link.href = "/cad-cam?view=soap";
  link.target = "_parent";
}
function invalidate() {
  clearTimeout(camTimer);
  if (camPending) resetCamWorker();
  proposals = null;
  camPending = false;
  stop();
  path = null;
  fraction = 0;
  revision++;
  queued = null;
  viewer.setPaths(null);
  $("#status-text").textContent = "준비됨";
}
function persist() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(model));
    $("#save-status").textContent = "이 브라우저에 저장됨";
  } catch {
    $("#save-status").textContent = "자동 저장 불가 · 파일로 저장하세요";
  }
}
function commit(next, selection) {
  try {
    validateModel(next);
  } catch (e) {
    toast(e.message, true);
    return false;
  }
  draftHistory.clear();
  past.push(clone(model));
  if (past.length > 50) past.shift();
  future = [];
  model = next;
  selected = selection ?? (model.stock ? "stock" : null);
  draft = null;
  drawTool = "select";
  invalidate();
  persist();
  render();
  return true;
}
function select(id) {
  draftHistory.clear();
  selected = id;
  draft = null;
  drawTool = "select";
  render();
}
function active() {
  return (
    draft ??
    (selected === "stock"
      ? model.stock
      : model.features.find((f) => f.id === selected))
  );
}
function field(label, key, value, min, max) {
  return `<label class="field"><span>${label}</span><div><input type="number" name="${key}" aria-label="${label}" value="${round(value)}" min="${min}" max="${max}" step="any" required/><span>${key === "angle" ? "°" : key === "stepOver" ? "%" : key === "feed" ? "mm/min" : "mm"}</span></div></label>`;
}
function shapeSvg(s, cls = "", id = "") {
  let boundary;
  try {
    boundary = ring(s, 0, 16);
  } catch {
    boundary = (s.nodes ?? []).map((n) => [n.point[0] + s.x, n.point[1] + s.y]);
  }
  const pts = boundary.map(([x, y]) => `${x},${-y}`).join(" ");
  return `<${s.type === "profile" && !s.closed ? "polyline" : "polygon"} points="${pts}" class="${cls}" ${id ? `data-select="${esc(id)}"` : ""}/>`;
}
function renderSketch() {
  $("#sketch-shapes").innerHTML =
    (model.stock
      ? shapeSvg(
          model.stock,
          selected === "stock" ? "base selected" : "base",
          "stock",
        )
      : "") +
    model.features
      .map((f) =>
        shapeSvg(f, selected === f.id ? "pocket selected" : "pocket", f.id),
      )
      .join("");
  $("#draft-shape").innerHTML = draft
    ? shapeSvg(draft, "draft") +
      (draft.type === "profile"
        ? draft.nodes
            .map(
              (n) =>
                `<circle cx="${n.point[0] + draft.x}" cy="${-n.point[1] - draft.y}" r=".8" fill="#1F2D3D"/>`,
            )
            .join("")
        : "") +
      `<text x="${draft.x}" y="${-draft.y - draft.h / 2 - 3}" class="dimension">${draft.type === "circle" ? "Ø " : ""}${round(draft.w)}${draft.type !== "circle" ? ` × ${round(draft.h)}` : ""} mm</text>`
    : "";
}
function fitSketch() {
  const s = model.stock;
  let w = Math.max(150, (s?.w ?? 90) * 1.65),
    h = Math.max(120, (s?.h ?? 70) * 1.65);
  const box = s ? bounds(s) : null;
  const x = box ? (box.minX + box.maxX) / 2 : 0,
    y = box ? (box.minY + box.maxY) / 2 : 0;
  $("#sketch").setAttribute("viewBox", `${x - w / 2} ${-y - h / 2} ${w} ${h}`);
}
function renderProperties() {
  $(".right-panel").scrollTop = 0;
  $("#properties-heading").textContent =
    mode === "cam"
      ? "가공 설정"
      : draft
        ? "새 스케치"
        : selected
          ? "치수 편집"
          : "설계 안내";
  if (mode === "cam") {
    $("#properties").innerHTML =
      `<div class="section-kicker">FLAT END MILL</div><h3>평 엔드밀</h3><p class="muted">기본 돌출 형상을 소재로 사용합니다.<br>윗면에서 홈을 깊이별로 가공합니다.</p><form id="tool-form">${field("공구 지름", "diameter", tool.diameter, 0.5, 40, 0.5)}${field("깊이 간격", "stepDown", tool.stepDown, 0.1, 20, 0.1)}${field("가로 간격", "stepOver", tool.stepOver, 10, 80, 5)}${field("이송 속도", "feed", tool.feed, 10, 5000, 50)}${field("안전 높이", "safeHeight", tool.safeHeight, 1, 30)}<button class="primary full" type="submit" ${camPending ? "disabled" : ""}>${icon("cut")}${camPending ? "계산 중…" : "가공 경로 생성"}</button><button type="button" data-action="propose" class="full" ${camPending ? "disabled" : ""}>품질 우선 경로 제안</button>${camPending ? `<button type="button" data-action="cancel-cam" class="full">계산 취소</button>` : ""}</form>${proposalHtml()}<label class="check"><input type="checkbox" id="show-paths" ${showPaths ? "checked" : ""}/>공구 경로 표시</label><div class="cam-stats"><div><span>제거 부피 (근사)</span><b id="removed-volume">—</b></div><div><span>남은 절삭량 (근사)</span><b id="residual-volume">—</b></div><small id="sim-resolution">격자 기반 소재 제거</small></div><div id="cam-warnings">${path ? path.warnings.map((w) => `<p class="warning">${esc(w)}</p>`).join("") : ""}</div><p class="quiet-note">상면 2.5D 포켓 · 바깥 윤곽은 이미 가공된 소재로 가정합니다. 시간은 이송 길이 기반 추정입니다. 실제 장비용 NC는 생성하지 않습니다.</p>`;
    return;
  }
  const a = active();
  if (!a) {
    $("#properties").innerHTML =
      `<div class="section-kicker">SKETCH → SOLID</div><h3>선부터 시작하세요.</h3><p class="muted">상단에서 선 연결·원호·슬롯 또는 기본 도형을 선택하세요.</p><div class="instruction-card"><span>01</span><p>윤곽을 그립니다.</p></div><div class="instruction-card"><span>02</span><p>치수와 두께를 정합니다.</p></div><div class="instruction-card"><span>03</span><p>홈을 파고 가공해 봅니다.</p></div>`;
    return;
  }
  const isBase = !model.stock || (!draft && selected === "stock");
  const outlineFields =
    a.type === "profile"
      ? `<p class="muted">${a.closed ? "닫힌 윤곽" : "작업면을 클릭해 꼭짓점을 추가하세요. 원호는 시작·통과·끝 순서로 클릭합니다."} · ${a.nodes.length}점<br>외곽 ${round(a.w)} × ${round(a.h)} mm</p>${draft ? '<div class="property-actions"><button type="button" data-action="close-profile">윤곽 닫기</button><button type="button" data-action="pop-node">마지막 점 취소</button></div>' : ""}${a.nodes.map((n, i) => `<div class="node-fields"><small>점 ${i + 1} · ${n.arcVia ? "원호 시작" : "직선 시작"}</small><div class="field-row">${field("점 " + (i + 1) + " X", "nx-" + i, n.point[0], -200, 200)}${field("점 " + (i + 1) + " Y", "ny-" + i, n.point[1], -200, 200)}</div>${n.arcVia ? `<div class="field-row">${field("원호 통과 X", "vx-" + i, n.arcVia[0], -200, 200)}${field("원호 통과 Y", "vy-" + i, n.arcVia[1], -200, 200)}</div>` : ""}</div>`).join("")}`
      : field(
          a.type === "circle"
            ? "지름"
            : a.type === "slot"
              ? "슬롯 전체 길이"
              : "폭",
          "w",
          a.w,
          1,
          200,
        ) +
        (["rect", "slot"].includes(a.type)
          ? field(a.type === "slot" ? "슬롯 폭" : "길이", "h", a.h, 1, 200) +
            (a.type === "slot"
              ? field("회전 각도", "angle", a.angle, -180, 180)
              : field("모서리 반경", "radius", a.radius, 0, 100))
          : "");
  $("#properties").innerHTML =
    `<div class="section-kicker">${isBase ? "BASE EXTRUSION" : "POCKET CUT"}</div><h3>${isBase ? "기본 돌출" : draft ? "새 파내기" : esc(a.name)}</h3><form id="shape-form">${!isBase ? `<label class="field text-field"><span>작업 이름</span><input name="name" aria-label="작업 이름" maxlength="80" value="${esc(a.name ?? `홈 ${model.features.length + 1}`)}"/></label>` : ""}<div class="field-row">${field("중심 X", "x", a.x, -200, 200, 0.5)}${field("중심 Y", "y", a.y, -200, 200, 0.5)}</div>${outlineFields}${isBase ? field("돌출 높이", "height", a.height ?? 12, 1, 80, 0.5) : field("파내기 깊이", "depth", a.depth ?? Math.min(4, model.stock.height), 0.1, model.stock.height, 0.1)}<button type="submit" class="primary full">${icon(isBase ? "extrude" : "cut")}${draft ? (isBase ? "돌출 만들기" : "파내기 적용") : "치수 변경 적용"}</button></form>${draft ? '<button class="text-button full" data-action="cancel">스케치 취소</button>' : `<div class="property-actions">${!isBase ? `<button data-action="duplicate">${icon("plus")}복제</button>` : ""}<button data-action="delete">${icon("trash")}삭제</button></div>`}<p class="quiet-note">${isBase ? "치수를 바꾸면 3D 형상이 다시 계산됩니다. 모든 홈이 외곽 안에 들어가야 합니다." : "깊이는 부품 윗면 기준입니다. 돌출 높이와 같은 깊이를 입력하면 관통 구멍이 됩니다."}</p>`;
}
function render() {
  $("#document-name").value = model.name;
  document
    .querySelectorAll(".tabs button")
    .forEach((b) => b.classList.toggle("active", b.dataset.action === mode));
  $("#tools").innerHTML =
    mode === "design"
      ? `<button data-action="select" class="${drawTool === "select" ? "active" : ""}">${icon("select")}선택</button><span class="divider"></span><button data-action="rect" class="${drawTool === "rect" ? "active" : ""}">${icon("rect")}사각형</button><button data-action="circle" class="${drawTool === "circle" ? "active" : ""}">${icon("circle")}원</button><button data-action="profile">${icon("profile")}선 연결</button><button data-action="arc">${icon("arc")}3점 원호</button><button data-action="slot">${icon("slot")}슬롯</button><label class="snap-control">격자<select id="grid-step" aria-label="격자 스냅">${[0, 0.1, 0.5, 1, 5].map((v) => `<option value="${v}" ${v === gridStep ? "selected" : ""}>${v ? `${v}mm` : "끔"}</option>`).join("")}</select></label><label class="snap-control"><input id="endpoint-snap" type="checkbox" ${endpointSnap ? "checked" : ""}/>끝점</label><span class="tool-description">${model.stock ? "그린 스케치를 파내기로 적용합니다" : "첫 스케치를 돌출해 부품을 만듭니다"}</span>`
      : `<span class="cam-tool-label">${icon("cut")}상면 포켓 밀링</span><span class="tool-description">공구 설정 → 경로 생성 → 소재 제거 확인</span>`;
  updateHistoryButtons();
  document.querySelector('[data-action="stl"]').disabled = !model.stock;
  $("#feature-count").textContent =
    model.features.length + (model.stock ? 1 : 0);
  $("#tree").innerHTML =
    `<div class="tree-document">${icon("cube")}<strong>${esc(model.name)}</strong></div>` +
    (model.stock
      ? `<button data-select="stock" class="tree-item ${selected === "stock" ? "selected" : ""}">${icon("extrude")}<span>기본 돌출<small>${model.stock.w} × ${model.stock.h} × ${model.stock.height} mm</small></span><span class="tree-num">01</span></button>`
      : '<p class="tree-empty">아직 형상이 없습니다.</p>') +
    model.features
      .map(
        (f, i) =>
          `<button data-select="${f.id}" class="tree-item ${selected === f.id ? "selected" : ""}">${icon(f.type === "circle" ? "circle" : "cut")}<span>${esc(f.name)}<small>깊이 ${f.depth} mm</small></span><span class="tree-num">${String(i + 2).padStart(2, "0")}</span></button>`,
      )
      .join("");
  $("#next-step").textContent = !model.stock
    ? "첫 스케치를 그리고 돌출하세요."
    : !model.features.length
      ? "윗면에 새 스케치를 그려 홈을 만드세요."
      : "치수를 다듬거나 가공 화면에서 공구 경로를 확인하세요.";
  $("#three-view").hidden = view === "sketch";
  $("#sketch").toggleAttribute("hidden", view !== "sketch");
  document.querySelectorAll(".view-switch button").forEach((b) => {
    b.classList.toggle("active", b.dataset.action === view);
    b.disabled = mode === "cam";
  });
  $("#empty-guide").hidden = !!model.stock || !!draft || mode === "cam";
  $("#view-label").textContent =
    mode === "cam"
      ? "소재 제거 시뮬레이션"
      : view === "sketch"
        ? `XY 스케치 평면 · 격자 ${gridStep ? gridStep + "mm" : "끔"} / 끝점 ${endpointSnap ? "켜짐" : "꺼짐"}`
        : "모델 보기 · Z↑";
  $("#view-hint").textContent =
    view === "sketch"
      ? ["profile", "arc"].includes(drawTool)
        ? "작업면 클릭으로 점 추가 · 윤곽 닫기 후 적용"
        : drawTool === "circle"
          ? "중심에서 바깥으로 드래그 · 반지름 지정"
          : drawTool === "rect"
            ? "대각선으로 드래그 · 사각형 그리기"
            : "형상 클릭으로 선택 · 오른쪽에서 치수 편집"
      : "드래그 회전 · 휠 확대 · 우클릭 이동";
  $("#cam-legend").hidden = mode !== "cam";
  $("#timeline").hidden = mode === "cam";
  $("#simulation-controls").hidden = mode !== "cam";
  $("#timeline").innerHTML =
    `<div class="timeline-label">작업 이력<small>선택하여 편집</small></div><div class="timeline-items">${model.stock ? `<button data-select="stock" class="feature-chip ${selected === "stock" ? "selected" : ""}">${icon("extrude")}돌출 <b>${model.stock.height}</b></button>` : '<span class="muted">첫 스케치를 기다리고 있습니다.</span>'}${model.features.map((f) => `<span class="timeline-arrow">›</span><button data-select="${f.id}" class="feature-chip ${selected === f.id ? "selected" : ""}">${icon("cut")}${esc(f.name)} <b>${f.depth}</b></button>`).join("")}</div>`;
  $("#model-summary").textContent = model.stock
    ? `${model.stock.w} × ${model.stock.h} × ${model.stock.height} mm · 홈 ${model.features.length}개`
    : "빈 설계 · 원점 XY / Z↑";
  renderSketch();
  renderProperties();
  if (draft)
    $("#properties").insertAdjacentHTML(
      "beforeend",
      `<p class="quiet-note">${draft.type === "profile" ? "마지막 점/윤곽 닫기도 되돌릴 수 있습니다. " : "진행 중 스케치는 확정 부품과 별도로 되돌립니다. "}Ctrl/⌘+Z · 다시 실행 Shift+Z / Ctrl+Y</p><button class="full" data-action="cancel-edit" title="Esc">편집 취소</button>`,
    );
  renderSimControls();
  if (mode === "design" || !path) viewer.showModel(model);
  if (mode === "cam" && path) {
    viewer.setPaths(path);
    requestSimulation(fraction);
  }
}
function renderSimControls() {
  $("#simulation-controls").innerHTML =
    `<div class="playback-buttons"><button class="icon-button" data-action="restart" aria-label="시뮬레이션 처음으로" ${!path ? "disabled" : ""}>${icon("reset")}</button><button class="play-button" data-action="play" ${!path ? "disabled" : ""}>${icon(playing ? "pause" : "play")}<span>${playing ? "일시정지" : "재생"}</span></button></div><div class="scrubber"><div><strong>소재 제거</strong><span id="sim-percent">${Math.round(fraction * 100)}%</span></div><input type="range" id="sim-progress" aria-label="가공 진행률" min="0" max="100" step=".1" value="${fraction * 100}" ${!path ? "disabled" : ""}/></div><label class="speed">재생 속도<select id="sim-speed" aria-label="재생 속도">${[1, 5, 10, 30, 100].map((v) => `<option value="${v}" ${v === speed ? "selected" : ""}>${v}×</option>`).join("")}</select></label><div class="time-estimate">${path ? `<b>${Math.ceil(path.seconds / 60)}분</b><span>이송 시간 추정 · ${path.operations.length}개 작업</span>` : "<span>오른쪽에서 가공 경로를 생성하세요.</span>"}</div>`;
}
function requestSimulation(value) {
  if (!path) return;
  if (busy) {
    queued = value;
    return;
  }
  busy = true;
  worker.postMessage({
    model,
    path,
    fraction: value,
    revision,
    request: ++request,
  });
}
function startShape(type) {
  draftHistory.clear();
  arcClicks = [];
  mode = "design";
  view = "sketch";
  drawTool = type;
  selected = null;
  draft = {
    id: uid(),
    type: type === "arc" ? "profile" : type,
    angle: 0,
    ...(["profile", "arc"].includes(type) ? { nodes: [], closed: false } : {}),
    x: model.stock?.x ?? 0,
    y: model.stock?.y ?? 0,
    w: type === "circle" ? 20 : 40,
    h: type === "circle" ? 20 : 30,
    radius: 0,
    height: 12,
    depth: Math.min(4, model.stock?.height ?? 4),
    name: `홈 ${model.features.length + 1}`,
  };
  stop();
  render();
}
function download(data, name, type) {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function setMode(next) {
  draftHistory.clear();
  mode = next;
  draft = null;
  drawTool = "select";
  stop();
  if (next === "cam") view = "solid";
  render();
}
function applyProposal(id) {
  const candidate = proposals?.candidates.find((c) => c.id === id);
  if (!candidate?.valid) return;
  stop();
  revision++;
  queued = null;
  path = candidate.path;
  fraction = 0;
  render();
  toast("선택한 경로를 적용했습니다. 소재 제거를 확인하세요.");
}
const actions = {
  "cancel-edit": () => cancelEdit(),
  propose: () => calculateCam(true),
  "cancel-cam": () => cancelCam(),
  "apply-baseline": () => applyProposal("baseline"),
  "apply-nearest": () => applyProposal("nearest"),
  profile: () => startShape("profile"),
  arc: () => startShape("arc"),
  slot: () => startShape("slot"),
  "close-profile": () => {
    if (draft?.type !== "profile") return;
    const before = draftState();
    draft.closed = true;
    try {
      syncProfile(draft);
    } catch (err) {
      toast(err.message, true);
      draft.closed = false;
      return;
    }
    recordDraft(before);
    render();
  },
  "pop-node": () => {
    if (draft?.type !== "profile") return;
    restoreDraft(draftHistory.undo(draftState()));
  },
  rect: () => startShape("rect"),
  circle: () => startShape("circle"),
  select: () => {
    draft = null;
    drawTool = "select";
    render();
  },
  cancel: () => {
    draft = null;
    drawTool = "select";
    render();
  },
  design: () => setMode("design"),
  cam: () => setMode("cam"),
  sketch: () => {
    view = "sketch";
    render();
  },
  solid: () => {
    view = "solid";
    render();
  },
  fit: () => {
    viewer.fit(model.stock);
    fitSketch();
  },
  undo: () => {
    if (draft) {
      restoreDraft(draftHistory.undo(draftState()));
      return;
    }
    if (!past.length) return;
    future.push(clone(model));
    model = past.pop();
    selected = model.stock ? "stock" : null;
    draft = null;
    invalidate();
    persist();
    render();
  },
  redo: () => {
    if (draft) {
      restoreDraft(draftHistory.redo(draftState()));
      return;
    }
    if (!future.length) return;
    past.push(clone(model));
    model = future.pop();
    selected = model.stock ? "stock" : null;
    draft = null;
    invalidate();
    persist();
    render();
  },
  new: () => {
    mode = "design";
    view = "sketch";
    commit(emptyModel());
    fitSketch();
    viewer.fit(null);
    toast("새 설계입니다. 실행 취소로 이전 설계를 복구할 수 있습니다.");
  },
  "free-sample": () => {
    mode = "design";
    view = "solid";
    commit(clone(freeExample));
    fitSketch();
    viewer.fit(model.stock);
    toast(
      "L자·회전 슬롯·3점 원호 예제입니다. 각 작업을 선택해 치수를 편집하세요.",
    );
  },
  sample: () => {
    mode = "design";
    view = "solid";
    commit(sampleModel());
    fitSketch();
    viewer.fit(model.stock);
    toast("연습 부품입니다. 작업을 선택해 치수를 바꿔 보세요.");
  },
  save: () => {
    download(
      JSON.stringify(model, null, 2),
      "design.form.json",
      "application/json",
    );
    toast("편집 가능한 설계를 저장했습니다.");
  },
  open: () => $("#file-input").click(),
  stl: () => {
    if (!model.stock) return;
    download(viewer.stl(model), "part-mm.stl", "application/octet-stream");
    toast("mm 기준 STL 메시를 내보냈습니다.");
  },
  delete: () => {
    if (!selected) return;
    const next = clone(model);
    if (selected === "stock") {
      next.stock = null;
      next.features = [];
    } else next.features = next.features.filter((f) => f.id !== selected);
    commit(next);
  },
  duplicate: () => {
    const a = active();
    if (!a || selected === "stock") return;
    draftHistory.clear();
    draft = { ...clone(a), id: uid(), name: `${a.name.slice(0, 70)} 복사` };
    selected = null;
    view = "sketch";
    render();
    toast("중심 좌표를 변경한 뒤 파내기를 적용하세요.");
  },
  play: () => {
    if (!path) return;
    if (fraction >= 1) fraction = 0;
    playing = !playing;
    renderSimControls();
    requestSimulation(fraction);
  },
  restart: () => {
    stop();
    fraction = 0;
    renderSimControls();
    requestSimulation(0);
  },
  help: () => $("#help-dialog").showModal(),
  "close-help": () => $("#help-dialog").close(),
};
document.addEventListener("click", (e) => {
  const selectButton = e.target.closest("[data-select]");
  if (selectButton) {
    if (drawTool === "select" && mode === "design")
      select(selectButton.dataset.select);
    return;
  }
  const b = e.target.closest("[data-action]");
  if (b && !b.disabled) actions[b.dataset.action]?.();
});
function readShapeValues(shape, values) {
  const s = clone(shape);
  for (const [key, v] of Object.entries(values)) {
    const match = key.match(/^(nx|ny|vx|vy)-(\d+)$/);
    if (match) {
      const n = s.nodes[Number(match[2])],
        index = match[1].endsWith("x") ? 0 : 1;
      n[match[1].startsWith("v") ? "arcVia" : "point"][index] = Number(v);
    } else s[key] = key === "name" ? v.trim() || "홈" : Number(v);
  }
  if (s.type === "profile") syncProfile(s);
  if (s.type === "circle") {
    s.h = s.w;
    s.radius = 0;
  }
  return s;
}
document.addEventListener("submit", (e) => {
  e.preventDefault();
  const values = Object.fromEntries(new FormData(e.target));
  if (e.target.id === "shape-form") {
    const next = clone(model);
    let s;
    try {
      s = active() ? readShapeValues(active(), values) : null;
    } catch (err) {
      toast(err.message, true);
      return;
    }
    if (!s) return;
    const base = !model.stock || (!draft && selected === "stock");
    if (base) {
      s.id = "stock";
      delete s.depth;
      delete s.name;
      next.stock = s;
    } else {
      delete s.height;
      if (draft) next.features.push(s);
      else
        next.features = next.features.map((f) => (f.id === selected ? s : f));
    }
    if (commit(next, base ? "stock" : s.id)) {
      view = "solid";
      render();
      if (base) {
        viewer.fit(model.stock);
        fitSketch();
      }
      toast(base ? "돌출 형상을 만들었습니다." : "파내기를 적용했습니다.");
    }
  } else if (e.target.id === "tool-form") {
    calculateCam();
  }
});
$("#document-name").addEventListener("change", (e) => {
  const next = clone(model);
  next.name = e.target.value.trim() || "새 부품";
  commit(next, selected);
});
$("#file-input").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  try {
    if (f.size > 100000) throw Error("100KB 이하의 설계 파일을 선택하세요.");
    const m = parseModel(await f.text());
    if (commit(m)) {
      mode = "design";
      view = m.stock ? "solid" : "sketch";
      render();
      viewer.fit(model.stock);
      fitSketch();
      toast("설계를 불러왔습니다.");
    }
  } catch (err) {
    toast(`파일을 열지 못했습니다. ${err.message}`, true);
  }
  e.target.value = "";
});
document.addEventListener("change", (e) => {
  if (e.target.id === "grid-step") {
    gridStep = Number(e.target.value);
    render();
  }
  if (e.target.id === "endpoint-snap") {
    endpointSnap = e.target.checked;
    render();
  }
  if (e.target.id === "sim-speed") speed = Number(e.target.value);
  if (e.target.id === "show-paths") {
    showPaths = e.target.checked;
    viewer.paths.visible = showPaths;
  }
  if (
    e.target.closest("#tool-form") &&
    e.target.tagName === "INPUT" &&
    (path || proposals || camPending)
  ) {
    invalidate();
    const submit = $("#tool-form button[type=submit]");
    if (submit) {
      submit.disabled = false;
      submit.innerHTML = icon("cut") + "가공 경로 생성";
    }
    $(".path-proposals")?.remove();
    document.querySelector('[data-action="propose"]').disabled = false;
    document.querySelector('[data-action="cancel-cam"]')?.remove();
    viewer.showModel(model);
    renderSimControls();
    $("#cam-warnings").innerHTML =
      '<p class="warning">설정이 바뀌었습니다. 경로를 다시 생성하세요.</p>';
  }
});
document.addEventListener("input", (e) => {
  if (draft && e.target.closest("#shape-form")) {
    try {
      const before = draftState();
      const preview = readShapeValues(
        draft,
        Object.fromEntries(new FormData($("#shape-form"))),
      );
      if (
        [preview.x, preview.y, preview.w, preview.h, preview.radius].every(
          Number.isFinite,
        )
      ) {
        draft = preview;
        recordDraft(before, e.target.name);
        updateHistoryButtons();
        renderSketch();
      }
    } catch {}
  }
  if (e.target.closest("#tool-form") && (path || proposals || camPending)) {
    invalidate();
    const submit = $("#tool-form button[type=submit]");
    if (submit) {
      submit.disabled = false;
      submit.innerHTML = icon("cut") + "가공 경로 생성";
    }
    $(".path-proposals")?.remove();
    document.querySelector('[data-action="propose"]').disabled = false;
    document.querySelector('[data-action="cancel-cam"]')?.remove();
    viewer.showModel(model);
    renderSimControls();
    $("#removed-volume").textContent = "—";
    $("#residual-volume").textContent = "—";
    $("#cam-warnings").innerHTML =
      '<p class="warning">설정이 바뀌었습니다. 경로를 다시 생성하세요.</p>';
  }
  if (e.target.id === "sim-progress") {
    stop();
    fraction = Number(e.target.value) / 100;
    $("#sim-percent").textContent = `${Math.round(fraction * 100)}%`;
    requestSimulation(fraction);
    const b = document.querySelector('[data-action="play"]');
    b.innerHTML = icon("play") + "<span>재생</span>";
  }
});
function cancelEdit() {
  if (camPending) {
    cancelCam();
    return;
  }
  draft = null;
  arcClicks = [];
  drawTool = "select";
  dragStart = null;
  dragBefore = null;
  draftHistory.clear();
  render();
  toast("진행 중 편집 취소 · 확정 설계 유지");
}
document.addEventListener("focusout", () => draftHistory.endGroup());
document.addEventListener("keydown", (e) => {
  const command = shortcutCommand(e);
  if (!command) return;
  if ($("#help-dialog").open) {
    if (command === "cancel") {
      e.preventDefault();
      $("#help-dialog").close();
    }
    return;
  }
  if (command === "cancel") {
    e.preventDefault();
    cancelEdit();
    return;
  }
  if (command === "undo-point") {
    if (!draft) return;
    e.preventDefault();
    actions.undo();
    return;
  }
  if (command === "delete" && mode !== "design") return;
  if (actions[command]) {
    e.preventDefault();
    actions[command]();
  }
});
let dragStart = null,
  dragBefore = null;
function sketchPoint(e) {
  const pt = new DOMPoint(e.clientX, e.clientY).matrixTransform(
    $("#sketch").getScreenCTM().inverse(),
  );
  let point = { x: pt.x, y: -pt.y };
  if (endpointSnap) {
    const vertices = [
      ...(model.stock ? [model.stock] : []),
      ...model.features,
    ].flatMap((s) =>
      s.type === "profile"
        ? s.nodes.map((n) => [n.point[0] + s.x, n.point[1] + s.y])
        : s.type === "rect"
          ? ring(s)
          : [],
    );
    if (draft?.type === "profile")
      vertices.push(
        ...draft.nodes.map((n) => [n.point[0] + draft.x, n.point[1] + draft.y]),
      );
    const matrix = $("#sketch").getScreenCTM(),
      threshold = 8 / Math.hypot(matrix.a, matrix.b);
    let best = threshold;
    for (const [x, y] of vertices) {
      const d = Math.hypot(x - point.x, y - point.y);
      if (d < best) {
        best = d;
        point = { x, y };
      }
    }
    if (best < threshold) return point;
  }
  return {
    x: gridStep
      ? round(Math.round(point.x / gridStep) * gridStep)
      : round(point.x),
    y: gridStep
      ? round(Math.round(point.y / gridStep) * gridStep)
      : round(point.y),
  };
}
$("#sketch").addEventListener("pointerdown", (e) => {
  if (e.button !== 0 || drawTool === "select" || !draft) return;
  if (draft.type === "profile") {
    if (draft.closed) return;
    const before = draftState();
    const p = sketchPoint(e),
      point = [round(p.x - draft.x), round(p.y - draft.y)];
    if (drawTool === "arc") {
      arcClicks.push(point);
      if (arcClicks.length < 3) {
        draft.nodes = arcClicks.map((p) => ({ id: uid(), point: p }));
      } else {
        draft.nodes = [
          { id: uid(), point: arcClicks[0], arcVia: arcClicks[1] },
          { id: uid(), point: arcClicks[2] },
        ];
        try {
          syncProfile(draft);
          draft.closed = true;
        } catch (err) {
          toast(err.message, true);
          restoreDraft(before);
          e.preventDefault();
          return;
        }
      }
    } else {
      const first = draft.nodes[0]?.point;
      if (
        first &&
        draft.nodes.length >= 3 &&
        Math.hypot(first[0] - point[0], first[1] - point[1]) < 0.001
      )
        draft.closed = true;
      else if (draft.nodes.length < 64)
        draft.nodes = [...draft.nodes, { id: uid(), point }];
      else toast("꼭짓점은 최대 64개입니다.", true);
    }
    try {
      syncProfile(draft);
    } catch {}
    recordDraft(before);
    render();
    e.preventDefault();
    return;
  }
  dragBefore = draftState();
  dragStart = sketchPoint(e);
  $("#sketch").setPointerCapture(e.pointerId);
  e.preventDefault();
});
$("#sketch").addEventListener("pointermove", (e) => {
  if (!dragStart || !draft) return;
  const p = sketchPoint(e);
  if (["rect", "slot"].includes(drawTool)) {
    draft.x = round((p.x + dragStart.x) / 2);
    draft.y = round((p.y + dragStart.y) / 2);
    draft.w = Math.max(1, Math.min(200, Math.abs(p.x - dragStart.x)));
    draft.h = Math.max(1, Math.min(200, Math.abs(p.y - dragStart.y)));
    draft.radius = 0;
    if (drawTool === "slot" && draft.h > draft.w)
      [draft.w, draft.h] = [draft.h, draft.w];
  } else {
    draft.x = dragStart.x;
    draft.y = dragStart.y;
    draft.w = draft.h = Math.max(
      1,
      Math.min(
        200,
        round(Math.hypot(p.x - dragStart.x, p.y - dragStart.y) * 2),
      ),
    );
  }
  renderSketch();
  renderProperties();
});
$("#sketch").addEventListener("pointerup", () => {
  if (dragBefore && draft) recordDraft(dragBefore);
  dragBefore = null;
  updateHistoryButtons();
  dragStart = null;
});
$("#sketch").addEventListener("pointercancel", () => {
  if (dragBefore) restoreDraft(dragBefore);
  dragBefore = null;
  dragStart = null;
});
let lastTick = performance.now();
setInterval(() => {
  const now = performance.now(),
    delta = Math.min(0.3, (now - lastTick) / 1000);
  lastTick = now;
  if (!playing || !path || busy) return;
  fraction = Math.min(1, fraction + (delta * speed) / path.seconds);
  $("#sim-progress").value = fraction * 100;
  $("#sim-percent").textContent = `${Math.round(fraction * 100)}%`;
  requestSimulation(fraction);
  if (fraction >= 1) {
    stop();
    renderSimControls();
  }
}, 100);
fitSketch();
viewer.fit(model.stock);
render();
