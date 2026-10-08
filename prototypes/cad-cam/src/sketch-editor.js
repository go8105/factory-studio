import {
  asProfile,
  transformWire,
  trimWire,
  extendWire,
  offsetWire,
  measureEntity,
  constrain,
  free,
} from "./sketch-edit.js";
import { profileRing, syncProfile } from "./profile.js";
import { validateShape } from "./model.js";
import { DraftHistory, shortcutCommand } from "./editor-commands.js";
import "./sketch-style.css";
import { solveSketch } from "./sketch-constraints.js";
const esc = (s) =>
  String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const uid = () => "p-" + crypto.randomUUID().slice(0, 12);
export function openSketchEditor(input, onApply) {
  if (document.querySelector("#professional-sketch")) return;
  let shape = asProfile(input),
    wireIndex = -1,
    ids = new Set(),
    tool = "select",
    via = null,
    gesture = null,
    closed = false;
  const history = new DraftHistory(50),
    dialog = document.createElement("dialog");
  dialog.id = "professional-sketch";
  dialog.innerHTML = `<div class="sk-head"><h2>전문 스케치 · mm</h2><button data-cmd="cancel">취소 · Esc</button></div><p>외곽과 내부 경계를 편집한 뒤 적용하세요. Shift 다중 선택 · 점/경유점 드래그 · Ctrl/⌘+Z. 원·슬롯·둥근 사각형은 원호를 유지합니다.</p><div class="sk-layout"><section><div class="sk-tools"><button data-tool="select">선택</button><button data-tool="line">연속 선</button><button data-tool="arc">연속 3점 원호</button><button data-cmd="all">모두 선택</button><button data-cmd="close">윤곽 닫기</button><button data-cmd="clear">새로 그리기</button><button data-cmd="undo">실행 취소</button><button data-cmd="redo">다시 실행</button></div><svg class="sk-canvas" viewBox="-50 -40 100 80" aria-label="전문 스케치 작업면" tabindex="0"></svg><output class="sk-measure"></output><p class="sk-status" role="status"></p><p class="sk-error" role="alert"></p></section><aside><label>편집 경계<select class="sk-wire"></select></label><div class="sk-tools"><button data-cmd="hole">내부 경계 추가</button><button data-cmd="remove-hole">내부 경계 삭제</button></div><label>격자 간격 (mm)<input class="sk-grid" type="number" min="0" step="any" value="1"></label><label><input class="sk-snap" type="checkbox" checked>끝점 스냅</label><div class="sk-point"></div><h3>선택점 변형</h3><label>이동 U<input class="sk-du" type="number" step="any" value="0"></label><label>이동 V<input class="sk-dv" type="number" step="any" value="0"></label><label>중심 U<input class="sk-cu" type="number" step="any" value="0"></label><label>중심 V<input class="sk-cv" type="number" step="any" value="0"></label><label>회전 각도 (°)<input class="sk-deg" type="number" step="any" value="90"></label><div class="sk-tools"><button data-cmd="move">이동</button><button data-cmd="copy">내부 경계로 복사</button><button data-cmd="rotate">회전</button><button data-cmd="mirror-u">U축 반사</button><button data-cmd="mirror-v">V축 반사</button></div><h3>윤곽 편집</h3><label>자르기 비율<input class="sk-ratio" type="number" step="any" value="0.25"></label><label>연장 / 오프셋 (mm)<input class="sk-amount" type="number" step="any" value="2"></label><div class="sk-tools"><button data-cmd="trim">선택 엔티티 자르기</button><button data-cmd="extend">끝점 연장</button><button data-cmd="offset">볼록 직선 오프셋</button></div><h3>치수·구속</h3><label>구속 종류<select class="sk-kind"><option value="length">거리 치수</option><option value="horizontal">수평</option><option value="vertical">수직</option><option value="coincident">일치</option><option value="radius">원호 반경</option><option value="fix">점 고정</option></select></label><label>치수 (mm)<input class="sk-value" type="number" step="any" value="20"></label><div class="sk-tools"><button data-cmd="constraint">구속 추가</button><button data-cmd="free">구속 해제</button></div><div class="sk-constraints"></div></aside></div><div class="sk-foot"><span>열린 윤곽은 적용할 수 없습니다. 내부 경계는 최대8개.</span><button data-cmd="apply">스케치 적용</button></div>`;
  document.body.append(dialog);
  const $ = (s) => dialog.querySelector(s),
    canvas = $(".sk-canvas"),
    wire = () => (wireIndex < 0 ? shape : shape.holes[wireIndex]),
    num = (c) => Number($(c).value);
  const snapshot = () => ({
    shape: structuredClone(shape),
    wireIndex,
    via: structuredClone(via),
    tool,
    ids: [...ids],
  });
  function restore(state) {
    if (!state) return;
    shape = state.shape;
    wireIndex = state.wireIndex;
    ids = new Set(state.ids);
    via = state.via;
    tool = state.tool;
    paint();
  }
  function done() {
    if (closed) return;
    closed = true;
    document.removeEventListener("keydown", key, true);
    dialog.close();
    dialog.remove();
  }
  function error(e) {
    $(".sk-error").textContent = e.message ?? String(e);
  }
  function mutate(fn) {
    const before = snapshot();
    try {
      fn();
      syncProfile(wire());
      history.record(before, snapshot());
      $(".sk-error").textContent = "";
      paint();
    } catch (e) {
      shape = before.shape;
      wireIndex = before.wireIndex;
      via = before.via;
      tool = before.tool;
      ids = new Set(before.ids);
      error(e);
      paint();
    }
  }
  function replace(s) {
    if (wireIndex < 0) shape = s;
    else shape.holes[wireIndex] = s;
  }
  function paintSvg() {
    const s = wire(),
      all = [shape, ...(shape.holes ?? [])];
    canvas.innerHTML =
      `<path d="M-200 0H200M0-200V200" stroke="#ddd" stroke-width=".2"/>` +
      all
        .map((w) => {
          let pts = [];
          try {
            pts = profileRing({ ...w, x: 0, y: 0 });
          } catch {
            pts = w.nodes.map((n) => n.point);
          }
          return `<${w.closed ? "polygon" : "polyline"} points="${pts.map((p) => `${p[0]},${-p[1]}`).join(" ")}" fill="${w.closed ? "#1f2d3d0a" : "none"}" stroke="${w === s ? "#1F2D3D" : "#9da3a8"}" stroke-width=".5"/>`;
        })
        .join("") +
      s.nodes
        .map(
          (n, i) =>
            `<circle data-point="${esc(n.id)}" cx="${n.point[0]}" cy="${-n.point[1]}" r="1.1" fill="${ids.has(n.id) ? "#b37d43" : "#1f2d3d"}"/><text x="${n.point[0] + 1.5}" y="${-n.point[1] - 1}" font-size="2.5" pointer-events="none">${i + 1}</text>${n.arcVia ? `<line x1="${n.point[0]}" y1="${-n.point[1]}" x2="${n.arcVia[0]}" y2="${-n.arcVia[1]}" stroke="#b37d43" stroke-width=".2"/><circle data-point="${esc(n.id)}" data-via="1" cx="${n.arcVia[0]}" cy="${-n.arcVia[1]}" r=".9" fill="#b37d43"/>` : ""}`,
        )
        .join("");
    if (via)
      canvas.innerHTML += `<circle cx="${via[0]}" cy="${-via[1]}" r="1" fill="#b37d43"/>`;
    const selected = s.nodes.filter((n) => ids.has(n.id)),
      m = measureEntity(s, selected[0]?.id);
    $(".sk-measure").textContent =
      `${ids.size}점 선택${selected.length === 2 ? " · 두 점 거리 " + Math.hypot(...selected[0].point.map((v, k) => v - selected[1].point[k])).toFixed(3) + " mm" : ""}${m ? " · " + m.kind + " 길이 " + m.length.toFixed(3) + (m.radius ? " · 반경 " + m.radius.toFixed(3) : "") + " mm" : ""}`;
  }
  function paint() {
    $(".sk-wire").innerHTML = [
      [-1, "외곽"],
      ...(shape.holes ?? []).map((_, i) => [i, `내부 경계 ${i + 1}`]),
    ]
      .map(
        ([i, label]) =>
          `<option value="${i}" ${i === wireIndex ? "selected" : ""}>${label}</option>`,
      )
      .join("");
    const s = wire(),
      n = s.nodes.find((n) => ids.has(n.id));
    $(".sk-point").innerHTML = n
      ? `<h3>점 ${esc(n.id)}</h3><label>점 U<input data-coord="0" type="number" step="any" value="${n.point[0]}"></label><label>점 V<input data-coord="1" type="number" step="any" value="${n.point[1]}"></label>`
      : "";
    $(".sk-point")
      .querySelectorAll("input")
      .forEach(
        (el) =>
          (el.onchange = () =>
            mutate(() => {
              free(s);
              n.point[Number(el.dataset.coord)] = Number(el.value);
              if (!Number.isFinite(Number(el.value)))
                throw Error("유효한 좌표를 입력하세요.");
            })),
      );
    $(".sk-constraints").textContent = (s.constraints ?? [])
      .map(
        (c) =>
          `${c.type} ${c.a}${c.b ? " → " + c.b : ""}${c.value ? " = " + c.value : ""}`,
      )
      .join("\n");
    $('[data-cmd="undo"]').disabled = !history.canUndo;
    $('[data-cmd="redo"]').disabled = !history.canRedo;
    $('[data-cmd="remove-hole"]').disabled = wireIndex < 0;
    dialog
      .querySelectorAll("[data-tool]")
      .forEach((b) => b.classList.toggle("active", b.dataset.tool === tool));
    $(".sk-status").textContent =
      `${s.closed ? "닫힌" : "열린"} 와이어 · ${s.nodes.length}점 · ${tool === "arc" ? (via ? "원호 끝점을 클릭하세요." : "원호 경유점, 끝점 순서로 클릭하세요.") : tool === "line" ? "다음 끝점을 클릭하세요." : "점 선택 또는 드래그"}`;
    paintSvg();
  }
  function fit() {
    const pts = [shape, ...(shape.holes ?? [])].flatMap((w) =>
      w.nodes.flatMap((n) => [n.point, ...(n.arcVia ? [n.arcVia] : [])]),
    );
    if (!pts.length) {
      canvas.setAttribute("viewBox", "-50 -40 100 80");
      return;
    }
    const minX = Math.min(...pts.map((p) => p[0])) - 8,
      maxX = Math.max(...pts.map((p) => p[0])) + 8,
      minY = Math.min(...pts.map((p) => p[1])) - 8,
      maxY = Math.max(...pts.map((p) => p[1])) + 8;
    canvas.setAttribute(
      "viewBox",
      `${minX} ${-maxY} ${Math.max(20, maxX - minX)} ${Math.max(20, maxY - minY)}`,
    );
  }
  function point(e, exclude) {
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(
      canvas.getScreenCTM().inverse(),
    );
    let q = [p.x, -p.y];
    if ($(".sk-snap").checked) {
      const radius =
        8 / Math.hypot(canvas.getScreenCTM().a, canvas.getScreenCTM().b);
      const n = wire().nodes.find(
        (n) =>
          n.id !== exclude &&
          Math.hypot(...n.point.map((v, k) => v - q[k])) < radius,
      );
      if (n) return [...n.point];
    }
    const step = num(".sk-grid");
    if (Number.isFinite(step) && step > 0)
      q = q.map((v) => Math.round(v / step) * step);
    return q;
  }
  canvas.onpointerdown = (e) => {
    const target = e.target.closest("[data-point]");
    if (tool === "select") {
      if (!target) {
        ids.clear();
        paint();
        return;
      }
      const id = target.dataset.point;
      if (e.shiftKey) {
        if (ids.has(id)) ids.delete(id);
        else ids.add(id);
      } else if (!ids.has(id)) {
        ids = new Set([id]);
      }
      gesture = {
        before: snapshot(),
        id,
        via: !!target.dataset.via,
        start: point(e, id),
        moved: false,
      };
      canvas.setPointerCapture(e.pointerId);
      paint();
      return;
    }
    mutate(() => {
      const s = wire();
      free(s);
      if (s.closed)
        throw Error("새로 그리기 또는 자르기로 와이어를 먼저 여세요.");
      if (s.nodes.length >= 64) throw Error("최대64점입니다.");
      const p = point(e);
      if (!s.nodes.length) {
        s.nodes.push({ id: uid(), point: p });
        return;
      }
      if (tool === "arc" && !via) {
        via = p;
        return;
      }
      if (tool === "arc") {
        s.nodes.at(-1).arcVia = via;
        via = null;
      }
      s.nodes.push({ id: uid(), point: p });
    });
  };
  canvas.onpointermove = (e) => {
    if (!gesture) return;
    try {
      const s = wire();
      free(s);
      const original =
          gesture.before.wireIndex < 0
            ? gesture.before.shape
            : gesture.before.shape.holes[gesture.before.wireIndex],
        p = point(e, gesture.id);
      gesture.moved = true;
      if (gesture.via) s.nodes.find((n) => n.id === gesture.id).arcVia = p;
      else
        for (const n of s.nodes)
          if (ids.has(n.id)) {
            const old = original.nodes.find((x) => x.id === n.id),
              du = p[0] - gesture.start[0],
              dv = p[1] - gesture.start[1];
            n.point = old.point.map((v, k) => v + (k ? dv : du));
            if (old.arcVia)
              n.arcVia = old.arcVia.map((v, k) => v + (k ? dv : du));
          }
      syncProfile(s);
      paintSvg();
    } catch (e) {
      shape = gesture.before.shape;
      wireIndex = gesture.before.wireIndex;
      gesture = null;
      error(e);
      paint();
    }
  };
  canvas.onpointerup = () => {
    if (!gesture) return;
    history.record(gesture.before, snapshot());
    gesture = null;
    paint();
  };
  canvas.onpointercancel = () => {
    if (gesture) {
      shape = gesture.before.shape;
      wireIndex = gesture.before.wireIndex;
      gesture = null;
      paint();
    }
  };
  $(".sk-wire").onchange = (e) => {
    wireIndex = Number(e.target.value);
    ids.clear();
    via = null;
    tool = "select";
    fit();
    paint();
  };
  dialog.onclick = (e) => {
    const t = e.target.closest("[data-tool]");
    if (t) {
      tool = t.dataset.tool;
      via = null;
      paint();
      return;
    }
    const command = e.target.closest("[data-cmd]")?.dataset.cmd;
    if (!command) return;
    const s = wire(),
      a = [...ids][0];
    if (command === "cancel") {
      done();
      return;
    }
    if (command === "undo") {
      restore(history.undo(snapshot()));
      return;
    }
    if (command === "redo") {
      restore(history.redo(snapshot()));
      return;
    }
    if (command === "all") {
      ids = new Set(s.nodes.map((n) => n.id));
      paint();
      return;
    }
    if (command === "apply") {
      try {
        shape = constrainForApply(shape);
        validateShape(shape);
        onApply(structuredClone(shape));
        done();
      } catch (e) {
        error(e);
      }
      return;
    }
    mutate(() => {
      if (command === "clear") {
        free(s);
        s.nodes = [];
        s.closed = false;
        ids.clear();
        tool = "line";
        via = null;
      } else if (command === "close") {
        if (s.nodes.length < 2) throw Error("두 점 이상 그린 뒤 닫으세요.");
        s.closed = true;
        via = null;
        tool = "select";
      } else if (command === "hole") {
        if ((shape.holes ?? []).length >= 8)
          throw Error("내부 경계는 최대8개입니다.");
        shape.holes ??= [];
        shape.holes.push({
          type: "profile",
          x: 0,
          y: 0,
          w: 1,
          h: 1,
          radius: 0,
          angle: 0,
          closed: false,
          nodes: [],
          constraints: [],
        });
        wireIndex = shape.holes.length - 1;
        tool = "line";
        ids.clear();
      } else if (command === "remove-hole") {
        shape.holes.splice(wireIndex, 1);
        wireIndex = -1;
        ids.clear();
      } else if (command === "free") s.constraints = [];
      else if (command === "constraint") {
        if (wireIndex >= 0)
          throw Error(
            "내부 경계의 치수는 좌표로 편집하세요. 구속 해석은 외곽만 지원합니다.",
          );
        const kind = $(".sk-kind").value,
          chosen = s.nodes.filter((n) => ids.has(n.id));
        if (chosen.length !== (["fix", "radius"].includes(kind) ? 1 : 2))
          throw Error("이 구속에 필요한 1점 또는 2점을 선택하세요.");
        const c = { type: kind, a: chosen[0].id };
        if (chosen[1]) c.b = chosen[1].id;
        if (kind === "fix") c.target = [...chosen[0].point];
        if (["length", "radius"].includes(kind)) c.value = num(".sk-value");
        replace(constrain(s, c));
      } else if (command === "move")
        replace(transformWire(s, ids, "move", [num(".sk-du"), num(".sk-dv")]));
      else if (["rotate", "mirror-u", "mirror-v"].includes(command))
        replace(
          transformWire(s, ids, command, [
            num(".sk-cu"),
            num(".sk-cv"),
            num(".sk-deg"),
          ]),
        );
      else if (command === "copy") {
        if (ids.size !== s.nodes.length || !s.closed)
          throw Error("닫힌 와이어의 모든 점을 선택하세요.");
        if ((shape.holes ?? []).length >= 8)
          throw Error("내부 경계는 최대8개입니다.");
        const duplicate = transformWire(
          { ...s, constraints: [] },
          ids,
          "move",
          [num(".sk-du"), num(".sk-dv")],
        );
        delete duplicate.holes;
        duplicate.nodes.forEach((n) => (n.id = uid()));
        duplicate.constraints = [];
        duplicate.x = duplicate.y = duplicate.angle = 0;
        shape.holes ??= [];
        shape.holes.push(duplicate);
        wireIndex = shape.holes.length - 1;
        ids = new Set(duplicate.nodes.map((n) => n.id));
      } else if (command === "trim") replace(trimWire(s, a, num(".sk-ratio")));
      else if (command === "extend")
        replace(extendWire(s, a, num(".sk-amount")));
      else if (command === "offset") replace(offsetWire(s, num(".sk-amount")));
    });
  };
  function key(e) {
    if (!dialog.open) return;
    const c = shortcutCommand(e);
    if (!c) return; // Native text editing and IME stay in their input.
    e.preventDefault();
    e.stopImmediatePropagation(); // No parent model command may run behind a modal draft.
    if (c === "cancel") done();
    else if (c === "undo" || c === "undo-point")
      restore(history.undo(snapshot()));
    else if (c === "redo") restore(history.redo(snapshot()));
    else if (c === "fit") {
      fit();
      paint();
    } else if (c === "save")
      error("스케치를 적용한 뒤 설계 저장을 사용하세요.");
    else if (c === "delete")
      error("선택 엔티티 자르기 또는 내부 경계 삭제를 사용하세요.");
    else if (c === "help")
      error("Shift 다중 선택 · Ctrl/⌘+Z 실행 취소 · F 전체 보기 · Esc 취소");
  }
  document.addEventListener("keydown", key, true);
  dialog.oncancel = (e) => {
    e.preventDefault();
    done();
  };
  dialog.showModal();
  fit();
  paint();
}
function constrainForApply(s) {
  return s.constraints?.length ? solveSketch(s).sketch : s;
}
