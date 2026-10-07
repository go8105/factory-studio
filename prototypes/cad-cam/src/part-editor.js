import {
  DraftHistory,
  shortcutCommand,
  dependentFeatures,
  SHORTCUT_HELP,
} from "./editor-commands.js";
import * as THREE from "three";
import { Viewer } from "./viewer.js";
import { clone } from "./model.js";
import {
  emptyPart,
  importPart,
  validatePart,
  prepareSketch,
  partKey,
  bracketExample,
  shellExample,
} from "./part-model.js";
import { syncProfile, profileRing } from "./profile.js";
import "./part-style.css";
const query = new URLSearchParams(location.search),
  scope = query.get("scope"),
  key = partKey(scope);
const $ = (s) => document.querySelector(s),
  escape = (s) =>
    String(s).replace(
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
const labels = {
  base: "기본 돌출",
  add: "돌출",
  cut: "파내기 / 구멍",
  fillet: "필렛",
  shell: "쉘",
  pattern: "배열",
  mirror: "미러",
};
let model = emptyPart(),
  selected = "base",
  draft,
  worker,
  revision = 0,
  acceptedRevision = 0,
  pending,
  timer,
  busy = false,
  undo = [],
  redo = [];
const draftHistory = new DraftHistory(50);
const draftState = () => clone(draft);
const creating = () =>
  selected !== "base" && !model.operations.some((f) => f.id === selected);
const draftScope = () => creating() || draftHistory.active;
$("#app").innerHTML =
  `<header><strong>FORM STUDIO · 3D</strong><input id="name" aria-label="부품 이름" maxlength="80"><nav><a id="back">2.5D 설계 / CAM ↗</a><button id="open">열기</button><button id="save">설계 저장</button><button id="stl">STL</button><button id="step">STEP</button></nav></header><div class="toolbar">${Object.entries(
    labels,
  )
    .filter(([k]) => k !== "base")
    .map(([k, v]) => `<button data-new="${k}">＋ ${v}</button>`)
    .join(
      "",
    )}<button id="undo" title="Ctrl/⌘+Z">실행 취소</button><button id="redo" title="Ctrl/⌘+Shift+Z · Ctrl+Y">다시 실행</button><button id="fit" title="F 전체 보기">전체 보기</button><button id="help" title="? 단축키 도움말">단축키</button><button id="cancel" hidden>계산 취소</button></div><main class="layout"><aside><h2>피처 이력</h2><div id="tree" class="tree"></div><div class="examples"><button id="bracket">측면 구멍 예제</button><button id="shell-example">쉘 / 필렛 예제</button><button id="copy-e1">2.5D 설계 가져오기</button><button id="new">새 부품</button></div><p class="note">선행 피처를 수정하면 뒤의 피처까지 다시 계산합니다. 실패하면 마지막 정상 설계를 유지합니다.</p><div id="status" role="status"></div><div id="error" role="alert"></div></aside><section class="stage"><div id="viewer"></div><div class="legend"><strong>단일 부품 · mm</strong><div id="measure">3D 커널 준비 중</div><small>드래그 회전 · 휠 확대<br>작업 평면의 U / V 좌표로 설계</small></div></section><aside><h2 id="form-title">기본 돌출</h2><div id="fields" class="fields"></div><div id="profile-ui"></div><button id="apply">변경 적용</button><div class="actions"><button id="discard" title="Esc">편집 취소</button><button id="delete" title="Delete">피처 삭제</button></div><p id="delete-impact" class="note"></p><p class="note">진행 중 입력은 확정 설계와 별도로 되돌립니다. Ctrl/⌘+Z · 다시 실행 Shift+Z / Ctrl+Y</p><p class="note">XY: U=X, V=Y / XZ: U=X, V=Z / YZ: U=Y, V=Z.<br>기준 피처의 바깥 경계면에서 돌출은 외측, 파내기는 내측으로 진행합니다. 평면 이동은 법선 방향입니다.</p><p class="note">E2 3D 형상의 측면·다축 CAM은 아직 지원하지 않습니다. 가공 시뮬레이션은 2.5D 편집기에서 수행하세요.</p></aside></main><div class="footer">OCCT / Replicad 1.1.0 · 형상 커널은 첫 진입 시 약 23MB를 불러옵니다. <a href="./licenses/README.txt" target="_blank">오픈소스 안내 ↗</a></div><input id="file" type="file" accept=".json" hidden><dialog id="shortcut-help"><h2>편집 단축키</h2><p>${SHORTCUT_HELP}</p><button id="close-help">닫기</button></dialog>`;
$("#back").href =
  query.get("embedded") === "1" ? "/cad-cam" : `./index.html?${query}`;
$("#back").target = query.get("embedded") === "1" ? "_parent" : "_self";
const viewer = new Viewer($("#viewer"), () => {});
function fail(message, id) {
  $("#error").className = "error";
  $("#error").textContent =
    `${id ? "실패 피처: " + id + "\n" : ""}${message}\n마지막 정상 설계 유지 · 이후 피처 계산 중단`;
}
function field(path, label, type = "number", options) {
  const parts = path.split(".");
  let value = parts.reduce((a, k) => a?.[k], draft);
  const el = document.createElement("label");
  el.innerHTML = `${escape(label)}${
    type === "select"
      ? `<select data-field="${path}">${options
          .map((o) => {
            const [v, l] = Array.isArray(o) ? o : [o, o];
            return `<option value="${escape(v)}" ${v === value ? "selected" : ""}>${escape(l)}</option>`;
          })
          .join("")}</select>`
      : `<input data-field="${path}" aria-label="${escape(label)}" type="${type}" ${type === "number" ? 'step="any"' : ""} value="${escape(value ?? "")}">`
  }`;
  $("#fields").append(el);
  const update = (e) => {
    let obj = draft;
    for (const k of parts.slice(0, -1)) obj = obj[k];
    obj[parts.at(-1)] =
      type === "number" ? Number(e.target.value) : e.target.value;
    const shape = draft.sketch ?? draft;
    if (shape.type === "circle") {
      shape.h = shape.w;
      shape.radius = 0;
    }
    if (path === "sketch.type" || path === "type") {
      const s = draft.sketch ?? draft;
      if (s.type === "profile" && !s.nodes) {
        s.nodes = [
          { id: "p1", point: [-15, -10] },
          { id: "p2", point: [15, -10] },
          { id: "p3", point: [15, 10] },
          { id: "p4", point: [-15, 10] },
        ];
        s.constraints = [];
        s.closed = true;
        syncProfile(s);
      }
      renderForm();
    }
  };
  el.lastElementChild.onchange = update;
  if (type !== "select") el.lastElementChild.oninput = update;
}
function renderForm() {
  $("#fields").innerHTML = "";
  $("#profile-ui").innerHTML = "";
  $("#form-title").textContent = labels[draft.kind ?? "base"];
  $("#delete").hidden = selected === "base";
  if (draft.kind) field("name", "피처 이름", "text");
  const idx = model.operations.findIndex((f) => f.id === selected),
    previous = idx < 0 ? model.operations : model.operations.slice(0, idx);
  if (["add", "cut", "fillet", "shell", "mirror"].includes(draft.kind)) {
    field("plane", "작업 평면", "select", ["XY", "XZ", "YZ"]);
    field("referenceId", "기준 피처", "select", [
      ["world", "원점 평면"],
      ["base", "기본 돌출"],
      ...previous.map((f) => [f.id, f.name]),
    ]);
    field("offset", "평면 이동 (mm)");
  }
  if (!draft.kind || ["add", "cut"].includes(draft.kind)) {
    const prefix = draft.kind ? "sketch." : "",
      s = draft.sketch ?? draft;
    field(prefix + "type", "스케치 형상", "select", [
      ["rect", "사각형"],
      ["circle", "원"],
      ["slot", "슬롯"],
      ["profile", "자유 윤곽"],
    ]);
    field(prefix + "x", "U 위치");
    field(prefix + "y", "V 위치");
    if (s.type !== "profile") {
      field(prefix + "w", "너비 / 지름");
      if (s.type !== "circle") field(prefix + "h", "높이");
    }
    if (s.type === "rect") field(prefix + "radius", "코너 반경");
    field(prefix + "angle", "스케치 회전 (°)");
    field(
      draft.kind ? "amount" : "height",
      draft.kind === "cut" ? "파내기 거리" : "돌출 높이",
    );
    if (s.type === "profile") profileUI(s);
  }
  if (draft.kind === "fillet") {
    field("scope", "모서리 범위", "select", [
      ["plane", "선택 평면의 모서리"],
      ["all", "모든 모서리"],
    ]);
    field("radius", "필렛 반경");
  }
  if (draft.kind === "shell") field("thickness", "안쪽 벽 두께");
  if (["pattern", "mirror"].includes(draft.kind))
    field(
      "sourceId",
      "복제할 피처",
      "select",
      previous
        .filter((f) => ["add", "cut"].includes(f.kind))
        .map((f) => [f.id, f.name]),
    );
  if (draft.kind === "pattern") {
    field("mode", "배열 방식", "select", [
      ["linear", "직선"],
      ["circular", "원형"],
    ]);
    field("axis", "축", "select", ["X", "Y", "Z"]);
    field("count", "총 개수");
    field("spacing", "직선 간격");
    field("angle", "원형 간격 (°)");
    for (let i = 0; i < 3; i++)
      field("center." + i, "회전 중심 " + ["X", "Y", "Z"][i]);
  }
}
function profileUI(s) {
  const container = $("#profile-ui");
  container.innerHTML =
    '<h3>자유 스케치 좌표</h3><svg id="sketch" viewBox="-50 -35 100 70" aria-label="자유 스케치 그리기"></svg><div class="actions"><button id="clear-points">새 윤곽 그리기</button><button id="close-points">윤곽 닫기</button></div><div class="points"></div><h3>스케치 구속</h3><select id="constraint-kind"><option value="horizontal">수평</option><option value="vertical">수직</option><option value="coincident">일치</option><option value="length">길이</option><option value="radius">원호 반경</option><option value="fix">점 고정</option></select><div class="fields"><label>점 A<input id="ca" type="number" value="1" min="1"></label><label>점 B<input id="cb" type="number" value="2" min="1"></label><label>치수<input id="cv" type="number" value="20" step="any"></label></div><div class="actions"><button id="add-constraint">구속 추가</button><button id="clear-constraints">구속 지우기</button><button id="arc-segment">점 A의 선 ↔ 원호</button></div><div id="constraints" class="note"></div><p class="note">새 윤곽: 작업면을 클릭해 점을 추가한 뒤 닫으세요. 좌표 입력은 mm. 점 A의 선을 원호로 바꾸고 경유 좌표를 편집할 수 있습니다. 원호 반경은 시작점에 적용합니다.</p>';
  let drawing = !s.closed;
  function paint() {
    let ring = s.nodes.map((n) => n.point);
    try {
      if (s.nodes.length >= 2) {
        syncProfile(s);
        ring = profileRing({ ...s, x: 0, y: 0 });
      }
    } catch {}
    const pts = ring.map((p) => `${p[0]},${-p[1]}`).join(" ");
    $("#sketch").innerHTML =
      `<path d="M-50 0H50M0-35V35" stroke="#ddd" stroke-width=".3"/><polygon points="${pts}" fill="#92a8ad44" stroke="#1F2D3D" stroke-width=".5"/>` +
      s.nodes
        .map(
          (n, i) =>
            `<circle cx="${n.point[0]}" cy="${-n.point[1]}" r="1"/><text x="${n.point[0] + 1}" y="${-n.point[1] - 1}" font-size="3">${i + 1}</text>`,
        )
        .join("");
    $(".points").innerHTML = s.nodes
      .map(
        (n, i) =>
          `<div class="row"><span>${i + 1}${n.arcVia ? " ⌒" : ""}</span><input aria-label="점 ${i + 1} U" data-point="${i}" data-axis="0" type="number" step="any" value="${n.point[0]}"><input aria-label="점 ${i + 1} V" data-point="${i}" data-axis="1" type="number" step="any" value="${n.point[1]}"></div>${n.arcVia ? `<div class="row"><span>경유</span><input aria-label="원호 ${i + 1} U" data-point="${i}" data-via="1" data-axis="0" type="number" step="any" value="${n.arcVia[0]}"><input aria-label="원호 ${i + 1} V" data-point="${i}" data-via="1" data-axis="1" type="number" step="any" value="${n.arcVia[1]}"></div>` : ""}`,
      )
      .join("");
    $(".points")
      .querySelectorAll("input")
      .forEach((el) => {
        el.oninput = () => {
          s.nodes[Number(el.dataset.point)][
            el.dataset.via ? "arcVia" : "point"
          ][Number(el.dataset.axis)] = Number(el.value);
        };
        el.onchange = () => {
          el.oninput();
          paint();
        };
      });
    $("#constraints").textContent = (s.constraints ?? [])
      .map(
        (c) =>
          `${c.type} ${c.a}${c.b ? " → " + c.b : ""}${c.value ? " = " + c.value : ""}`,
      )
      .join("\n");
  }
  $("#clear-points").onclick = () => {
    s.nodes = [];
    s.closed = false;
    s.constraints = [];
    drawing = true;
    paint();
  };
  $("#close-points").onclick = () => {
    try {
      syncProfile(s);
      s.closed = true;
      drawing = false;
      paint();
    } catch (e) {
      fail(e.message);
    }
  };
  $("#sketch").onclick = (e) => {
    if (!drawing || s.nodes.length >= 64) return;
    const box = e.currentTarget.getBoundingClientRect();
    s.nodes.push({
      id: "p" + (s.nodes.length + 1),
      point: [
        Math.round((((e.clientX - box.left) / box.width) * 100 - 50) * 2) / 2,
        Math.round((35 - ((e.clientY - box.top) / box.height) * 70) * 2) / 2,
      ],
    });
    paint();
  };
  $("#arc-segment").onclick = () => {
    try {
      const i = Number($("#ca").value) - 1,
        n = s.nodes[i],
        b = s.nodes[(i + 1) % s.nodes.length];
      if (!n || !b) throw Error("점 번호를 확인하세요.");
      if (n.arcVia) delete n.arcVia;
      else {
        const dx = b.point[0] - n.point[0],
          dy = b.point[1] - n.point[1],
          len = Math.hypot(dx, dy);
        if (len < 0.001) throw Error("서로 다른 두 점이 필요합니다.");
        n.arcVia = [
          (n.point[0] + b.point[0]) / 2 - (dy / len) * 5,
          (n.point[1] + b.point[1]) / 2 + (dx / len) * 5,
        ];
      }
      paint();
    } catch (e) {
      fail(e.message);
    }
  };
  $("#clear-constraints").onclick = () => {
    s.constraints = [];
    paint();
  };
  $("#add-constraint").onclick = () => {
    try {
      const a = s.nodes[Number($("#ca").value) - 1],
        b = s.nodes[Number($("#cb").value) - 1],
        type = $("#constraint-kind").value;
      if (!a || (!["fix", "radius"].includes(type) && !b))
        throw Error("존재하는 점 번호를 선택하세요.");
      const c = { type, a: a.id };
      if (!["fix", "radius"].includes(type)) c.b = b.id;
      if (["length", "radius"].includes(type)) c.value = Number($("#cv").value);
      if (type === "fix") c.target = [...a.point];
      s.constraints ??= [];
      s.constraints.push(c);
      paint();
    } catch (e) {
      fail(e.message);
    }
  };
  paint();
}
function render() {
  $("#name").value = model.name;
  $("#tree").innerHTML = [
    { id: "base", name: "기본 돌출" },
    ...model.operations,
  ]
    .map(
      (f, i) =>
        `<button data-select="${escape(f.id)}" class="${selected === f.id ? "active" : ""}">${String(i + 1).padStart(2, "0")} ${escape(f.name)}<small>${escape(f.id)} · ${labels[f.kind ?? "base"]}</small></button>`,
    )
    .join("");
  $("#tree")
    .querySelectorAll("button")
    .forEach((b) => (b.onclick = () => select(b.dataset.select)));
  select(selected);
  renderUndo();
}
function select(id) {
  draftHistory.clear();
  selected = model.operations.some((f) => f.id === id) ? id : "base";
  draft = clone(
    selected === "base"
      ? model.base
      : model.operations.find((f) => f.id === selected),
  );
  $("#tree")
    .querySelectorAll("button")
    .forEach((b) =>
      b.classList.toggle("active", b.dataset.select === selected),
    );
  renderForm();
  renderUndo();
}
function getWorker() {
  if (worker) return worker;
  worker = new Worker(new URL("./part.worker.js", import.meta.url), {
    type: "module",
  });
  const currentWorker = worker;
  worker.onmessage = ({ data }) => {
    if (worker !== currentWorker) return;
    if (data.revision !== revision) return;
    clearTimeout(timer);
    busy = false;
    $("#cancel").hidden = true;
    $("#apply").disabled = false;
    if (data.error) {
      fail(data.error, data.featureId);
      $("#status").textContent = "재계산 실패";
      pending = null;
      renderUndo();
      return;
    }
    if (data.export) {
      download(data.bytes, `${model.name}.${data.export}`);
      $("#status").textContent = "내보내기 준비 완료";
      return;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(data.mesh.vertices, 3),
    );
    g.setAttribute(
      "normal",
      new THREE.Float32BufferAttribute(data.mesh.normals, 3),
    );
    g.setIndex(data.mesh.triangles);
    viewer.setGeometry(g);
    if (pending.mode === "edit") {
      undo.push(clone(model));
      undo = undo.slice(-30);
      redo = [];
    } else if (pending.mode === "undo") {
      redo.push(clone(model));
      undo.pop();
    } else if (pending.mode === "redo") {
      undo.push(clone(model));
      redo.pop();
    }
    model = pending.model;
    acceptedRevision = revision;
    selected = pending.selected ?? selected;
    pending = null;
    try {
      localStorage.setItem(key, JSON.stringify(model));
    } catch {
      fail("브라우저 저장 공간이 부족합니다. 설계 파일을 저장하세요.");
    }
    $("#measure").textContent =
      `체적 ${data.info.volume.toFixed(1)} mm³ · ${(data.milliseconds / 1000).toFixed(2)}초`;
    $("#status").textContent = `${model.operations.length} 피처 재계산 완료`;
    $("#error").textContent = "";
    $("#error").className = "";
    render();
    if (data.info.bounds) {
      const [a, b] = data.info.bounds;
      viewer.fit({
        x: (a[0] + b[0]) / 2,
        y: (a[1] + b[1]) / 2,
        w: b[0] - a[0],
        h: b[1] - a[1],
        height: b[2] - a[2],
        type: "rect",
        radius: 0,
      });
    }
  };
  worker.onerror = () => {
    clearTimeout(timer);
    busy = false;
    $("#cancel").hidden = true;
    pending = null;
    worker.terminate();
    worker = null;
    acceptedRevision = 0;
    $("#apply").disabled = false;
    fail("3D 커널 초기화 오류입니다. 다시 적용하거나 새로고침하세요.");
    renderUndo();
  };
  return worker;
}
function renderUndo() {
  $("#undo").disabled =
    busy || (draftScope() ? !draftHistory.canUndo : !undo.length);
  $("#redo").disabled =
    busy || (draftScope() ? !draftHistory.canRedo : !redo.length);
  const affected = dependentFeatures(model.operations, selected);
  $("#delete-impact").textContent = affected.length
    ? `참조하는 피처: ${affected.map((f) => f.name).join(", ")}. 이 피처들을 먼저 삭제해야 합니다.`
    : "";
}
function restoreDraft(next) {
  if (!next) return;
  draft = next;
  $("#error").textContent = "";
  renderForm();
  renderUndo();
  $("#status").textContent = "진행 중 편집 복구 · 확정 설계 유지";
}
function undoEdit() {
  if (busy) return;
  if (draftScope()) {
    restoreDraft(draftHistory.undo(draftState()));
    return;
  }
  if (undo.length) submit(clone(undo.at(-1)), "undo", "base");
}
function redoEdit() {
  if (busy) return;
  if (draftScope()) {
    restoreDraft(draftHistory.redo(draftState()));
    return;
  }
  if (redo.length) submit(clone(redo.at(-1)), "redo", "base");
}
const draftEvents = new WeakMap();
for (const type of ["input", "change", "click"]) {
  document.addEventListener(
    type,
    (e) => {
      if (!busy && e.target.closest?.("#fields, #profile-ui"))
        draftEvents.set(e, { before: draftState(), selected });
    },
    true,
  );
  document.addEventListener(type, (e) => {
    const snapshot = draftEvents.get(e);
    if (!snapshot || busy || snapshot.selected !== selected) return;
    draftHistory.record(
      snapshot.before,
      draftState(),
      type === "input" ? e.target : null,
    );
    renderUndo();
  });
}
document.addEventListener("focusout", () => draftHistory.endGroup());
function submit(candidate, mode = "edit", id = selected) {
  if (busy) return;
  try {
    validatePart(candidate);
  } catch (e) {
    fail(e.message);
    return;
  }
  busy = true;
  $("#cancel").hidden = false;
  revision++;
  pending = { model: clone(candidate), mode, selected: id };
  $("#apply").disabled = true;
  renderUndo();
  $("#status").textContent = "3D 형상 재계산 중…";
  getWorker().postMessage({ revision, model: candidate });
  timer = setTimeout(() => {
    worker.terminate();
    worker = null;
    acceptedRevision = 0;
    busy = false;
    $("#cancel").hidden = true;
    pending = null;
    $("#apply").disabled = false;
    fail("30초 계산 제한을 넘었습니다. 피처나 치수를 줄인 뒤 다시 적용하세요.");
    renderUndo();
  }, 30000);
}
function download(data, name) {
  const url = URL.createObjectURL(new Blob([data]));
  const a = document.createElement("a");
  a.href = url;
  a.download = name.replace(/[\\/:*?"<>|]/g, "_");
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
function cancelEdit() {
  if (!busy) {
    select(selected);
    $("#name").value = model.name;
    $("#error").textContent = "";
    $("#status").textContent = "편집 취소 · 마지막 확정 치수 복원";
    return;
  }
  clearTimeout(timer);
  worker?.terminate();
  worker = null;
  revision++;
  acceptedRevision = 0;
  busy = false;
  pending = null;
  $("#cancel").hidden = true;
  $("#apply").disabled = false;
  $("#status").textContent = "계산 취소 · 마지막 정상 설계 유지";
  select(selected);
  $("#name").value = model.name;
  renderUndo();
}
$("#cancel").onclick = cancelEdit;
$("#discard").onclick = cancelEdit;
$("#apply").onclick = () => {
  try {
    const next = clone(model);
    next.name = $("#name").value;
    if (!draft.kind) {
      draft = prepareSketch(draft);
      next.base = clone(draft);
    } else {
      if (draft.sketch) draft.sketch = prepareSketch(draft.sketch);
      const i = next.operations.findIndex((f) => f.id === draft.id);
      if (i < 0) next.operations.push(clone(draft));
      else next.operations[i] = clone(draft);
    }
    submit(next, "edit", draft.id);
  } catch (e) {
    fail(e.message, draft.id);
  }
};
$("#delete").onclick = () => {
  if (busy || selected === "base") return;
  if (creating()) {
    cancelEdit();
    return;
  }
  const affected = dependentFeatures(model.operations, selected);
  if (affected.length) {
    fail(
      `참조 피처를 먼저 삭제하세요: ${affected.map((f) => f.name).join(", ")}`,
      selected,
    );
    return;
  }
  const next = clone(model);
  next.operations = next.operations.filter((f) => f.id !== selected);
  submit(next, "edit", "base");
};
document.querySelectorAll("[data-new]").forEach(
  (b) =>
    (b.onclick = () => {
      if (busy) return;
      draftHistory.clear();
      const kind = b.dataset.new,
        id = kind + "-" + crypto.randomUUID().slice(0, 8);
      selected = id;
      draft = {
        id,
        name: labels[kind],
        kind,
        plane: "XY",
        referenceId: model.operations.at(-1)?.id ?? "base",
        offset: 0,
      };
      if (["add", "cut"].includes(kind))
        Object.assign(draft, {
          amount: kind === "add" ? 10 : 5,
          sketch: {
            type: "rect",
            x: 0,
            y: 0,
            w: 20,
            h: 16,
            radius: 0,
            angle: 0,
          },
        });
      if (kind === "fillet")
        Object.assign(draft, { radius: 1, scope: "plane" });
      if (kind === "shell") draft.thickness = 2;
      if (["pattern", "mirror"].includes(kind))
        draft.sourceId =
          model.operations.findLast((f) => ["add", "cut"].includes(f.kind))
            ?.id ?? "";
      if (kind === "pattern")
        Object.assign(draft, {
          mode: "linear",
          axis: "X",
          count: 3,
          spacing: 15,
          angle: 30,
          center: [0, 0, 0],
        });
      renderForm();
      renderUndo();
    }),
);
$("#undo").onclick = undoEdit;
$("#redo").onclick = redoEdit;
$("#fit").onclick = () => {
  const box = viewer.part.geometry.boundingBox;
  viewer.part.geometry.computeBoundingBox();
  const { min, max } = viewer.part.geometry.boundingBox;
  viewer.fit({
    type: "rect",
    x: (min.x + max.x) / 2,
    y: (min.y + max.y) / 2,
    w: max.x - min.x,
    h: max.y - min.y,
    height: max.z - min.z,
    radius: 0,
  });
};
$("#new").onclick = () => submit(emptyPart(), "edit", "base");
$("#bracket").onclick = () => submit(bracketExample(), "edit", "base");
$("#shell-example").onclick = () => submit(shellExample(), "edit", "base");
$("#save").onclick = () =>
  download(JSON.stringify(model, null, 2), `${model.name}.part.json`);
$("#open").onclick = () => $("#file").click();
$("#file").onchange = async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  try {
    if (f.size > 250000) throw Error("250KB 이하 파일만 지원합니다.");
    submit(importPart(await f.text()), "edit", "base");
  } catch (err) {
    fail(err.message);
  }
  e.target.value = "";
};
$("#copy-e1").onclick = () => {
  try {
    const text = localStorage.getItem(
      "form-studio-design-v1" + (scope ? ":" + scope : ""),
    );
    if (!text) throw Error("같은 공간에 저장된 2.5D 설계가 없습니다.");
    submit(importPart(text), "edit", "base");
  } catch (e) {
    fail(e.message);
  }
};
for (const format of ["stl", "step"])
  $("#" + format).onclick = () => {
    if (busy) return;
    if (!worker || !acceptedRevision) {
      fail("현재 설계를 다시 적용한 뒤 내보내세요.");
      return;
    }
    worker.postMessage({
      action: "export",
      format,
      revision,
      shapeRevision: acceptedRevision,
    });
  };
$("#help").onclick = () => $("#shortcut-help").showModal();
$("#close-help").onclick = () => $("#shortcut-help").close();
document.addEventListener("keydown", (e) => {
  const command = shortcutCommand(e);
  if (!command) return;
  if ($("#shortcut-help").open) {
    if (command === "cancel") {
      e.preventDefault();
      $("#shortcut-help").close();
    }
    return;
  }
  const actions = {
    undo: undoEdit,
    redo: redoEdit,
    cancel: cancelEdit,
    "undo-point": () => {
      if (draftScope()) undoEdit();
    },
    delete: () => $("#delete").onclick(),
    fit: () => $("#fit").onclick(),
    save: () => $("#save").onclick(),
    help: () => $("#help").onclick(),
  };
  if (command === "undo-point" && !draftScope()) return;
  if (actions[command]) {
    e.preventDefault();
    actions[command]();
  }
});
try {
  const saved = localStorage.getItem(key);
  if (saved) model = importPart(saved);
} catch (e) {
  fail(e.message);
}
render();
submit(model, "initial", "base");
