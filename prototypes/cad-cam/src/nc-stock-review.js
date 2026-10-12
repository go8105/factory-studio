import stepSample from "../examples/cnc_CAD13_2026-10-07_target.step?raw";
import { transformMesh, meshBounds } from "./nc-stock.js";
export function createStockReview(
  viewer,
  getNC,
  selectLine,
  onChange = () => {},
) {
  const panel = document.createElement("details");
  panel.className = "stock-panel";
  panel.open = true;
  const axes = ["X", "Y", "Z"];
  panel.innerHTML = `<summary>소재 · 공구 · STEP 정합</summary><p class="muted">G54 공구 끝점 기준 · mm. 보정 명령 H/D는 아직 미지원. 평엔드밀·수평/수직 면의 상면 형상 검토만 지원합니다.</p>
  <label>소재 이름<input id="material" value="검토용 알루미늄"></label><p>소재 최소 좌표 (mm)</p><div class="xyz">${axes.map((a) => `<label>${a}<input id="stock-${a}" type="number" value="0" step="any"></label>`).join("")}</div><p>소재 크기 (mm)</p><div class="xyz">${axes.map((a, i) => `<label>${a}<input id="size-${a}" type="number" value="${i === 2 ? 8 : 20}" step="any"></label>`).join("")}</div>
  <h3>공구표 · 평엔드밀</h3><div id="tool-rows"></div><button id="add-tool">공구 추가</button><p class="muted">지름·날 길이 mm. H/D는 참조 기록만, 보정 계산은 미지원입니다.</p><label>NC 시작 시 활성 T (미정은 빈칸)<input id="initial-tool" type="number" step="1" placeholder="미정"></label>
  <button id="step-load">목표 STEP 열기</button><button id="step-sample">STEP 예제</button><input id="step-file" type="file" accept=".step,.stp" hidden><p id="step-info">STEP 미선택 · 서버 전송 없음</p><p>STEP→G54 평행 이동 (mm)</p><div class="xyz">${axes.map((a) => `<label>${a}<input id="offset-${a}" type="number" value="0" step="any"></label>`).join("")}</div><label>Z축 회전 (도)<input id="angle" type="number" value="0" step="any"></label><label>격자 간격 (mm)<input id="pitch" type="number" value="1" step="0.1" min="0.1" max="10"></label><label class="check"><input id="aligned" type="checkbox">STEP 치수와 G54 좌표 정합을 확인했습니다</label><label class="check"><input id="top-confirmed" type="checkbox">바닥부터 이어지는 단일 상면 형상입니다</label><div class="buttons"><button id="stock-analyze">소재 검토 실행</button><button id="stock-cancel" disabled>소재 검토 취소</button></div><p id="stock-status" role="status">NC·STEP·공구를 연결하세요.</p><p class="muted">STEP10MiB · 커널 준비90초/형상·소재30초 · 20,000삼각형 · 40,000셀. 격자보다 작은 특징·홀더/지그/장비 이동 제외. 검출 0은 안전 보증이 아닙니다.</p>`;
  document.querySelector(".inputs").append(panel);
  const output = document.createElement("section");
  output.className = "stock-output";
  output.innerHTML =
    '<h2>소재 검토 결과</h2><pre id="stock-report">결과 없음 · 시간/kWh 미정</pre><div id="contact-lines"></div><p class="muted">점 표시: 청록=목표 근처 · 황토=잔삭 · 갈색=과절삭. 셀 중심/원호 현 근사이며 실물 품질 판정이 아닙니다.</p>';
  document.querySelector("#detail").before(output);
  const $ = (id) => document.getElementById(id),
    number = (id) => ($(id).value.trim() === "" ? NaN : Number($(id).value));
  let reference = null,
    analysis = null,
    worker = null,
    revision = 0,
    timer;
  function addTool(t = {}) {
    const row = document.createElement("div");
    row.className = "tool-row";
    for (const [key, label] of [
      ["t", "T 번호"],
      ["diameter", "지름"],
      ["flute", "날 길이"],
      ["h", "H 참조"],
      ["d", "D 참조"],
    ]) {
      const wrapper = document.createElement("label");
      wrapper.textContent = label;
      const input = document.createElement("input");
      input.type = "number";
      input.step = ["t", "h", "d"].includes(key) ? "1" : "any";
      input.dataset.tool = key;
      input.value = t[key] ?? "";
      wrapper.append(input);
      row.append(wrapper);
    }
    const remove = document.createElement("button");
    remove.textContent = "공구 삭제";
    remove.onclick = () => {
      row.remove();
      panel.dispatchEvent(new Event("input", { bubbles: true }));
    };
    row.append(remove);
    $("tool-rows").append(row);
  }
  addTool({ t: 1, diameter: 4, flute: 15, h: 1, d: 1 });
  $("add-tool").onclick = () => {
    if ($("tool-rows").children.length >= 100) {
      $("stock-status").textContent = "공구100개 상한";
      return;
    }
    addTool();
    panel.dispatchEvent(new Event("input", { bubbles: true }));
  };
  function setup() {
    return {
      stock: {
        material: $("material").value,
        min: axes.map((a) => number("stock-" + a)),
        size: axes.map((a) => number("size-" + a)),
      },
      tools: [...panel.querySelectorAll(".tool-row")].map((row) => {
        const value = (key) => {
          const input = row.querySelector(`[data-tool="${key}"]`);
          return input.value.trim() === "" ? null : Number(input.value);
        };
        return {
          type: "flat",
          t: value("t"),
          diameter: value("diameter"),
          flute: value("flute"),
          h: value("h"),
          d: value("d"),
        };
      }),
      initialTool:
        $("initial-tool").value.trim() === "" ? null : number("initial-tool"),
      transform: {
        offset: axes.map((a) => number("offset-" + a)),
        angle: number("angle"),
      },
      pitch: number("pitch"),
      aligned: $("aligned").checked,
      topSurfaceConfirmed: $("top-confirmed").checked,
    };
  }
  function geometry() {
    try {
      const s = setup();
      viewer.setReference(
        reference ? transformMesh(reference.mesh, s.transform) : null,
        s.stock,
        analysis,
      );
    } catch {
      viewer.setReference(null, null, null);
    }
  }
  function cancel() {
    revision++;
    worker?.terminate();
    worker = null;
    clearTimeout(timer);
    $("stock-cancel").disabled = true;
    $("stock-analyze").disabled = false;
    $("step-load").disabled = false;
    $("step-sample").disabled = false;
  }
  function resetNC(reconfirm = false) {
    onChange();
    if (reconfirm) {
      $("aligned").checked = false;
      $("stock-status").textContent =
        "NC 변경 · 이전 검토 무효화, 좌표 정합을 다시 확인하세요.";
    }

    if (worker?.step) {
      reference = null;
      $("step-info").textContent = "STEP 읽기 취소 · 다시 여세요";
    }
    cancel();
    analysis = null;
    $("stock-report").textContent = "결과 없음 · 시간/kWh 미정";
    $("contact-lines").replaceChildren();
    geometry();
  }
  panel.addEventListener("input", (e) => {
    if (e.target.id === "step-file") return;
    const pendingSTEP = worker?.step;
    if (pendingSTEP) {
      reference = null;
      $("step-info").textContent = "STEP 읽기 취소 · 다시 여세요";
    }
    resetNC();
    if (!["aligned", "top-confirmed"].includes(e.target.id)) {
      $("aligned").checked = false;
      $("top-confirmed").checked = false;
    }
    $("stock-status").textContent = "설정 변경 · 이전 검토 무효화";
  });
  $("step-load").onclick = () => $("step-file").click();
  function start(makeWorker, data, done) {
    cancel();
    const own = revision,
      w = makeWorker();
    worker = w;
    w.step = !!data.file;
    $("stock-cancel").disabled = false;
    $("stock-analyze").disabled = true;
    $("step-load").disabled = true;
    $("step-sample").disabled = true;
    const reject = (text) => {
      if (worker !== w || own !== revision) return;
      const step = w.step;
      cancel();
      if (step) {
        reference = null;
        $("step-info").textContent = "STEP 읽기 실패 · 다시 여세요";
      }
      analysis = null;
      $("stock-status").textContent = text;
    };
    timer = setTimeout(
      () =>
        reject(
          w.step
            ? "STEP 커널 준비90초 상한 초과 · 네트워크/파일을 확인하고 다시 시도하세요"
            : "30초 상한 초과 · 결과 없음",
        ),
      w.step ? 90000 : 30000,
    );
    w.onerror = () => reject("Worker 오류 · 결과 없음");
    w.onmessage = ({ data }) => {
      if (worker !== w || data.revision !== own) return;
      if (data.progress) {
        $("stock-status").textContent = data.progress;
        if (data.phase === "read") {
          clearTimeout(timer);
          timer = setTimeout(
            () => reject("STEP 형상 읽기30초 상한 초과"),
            30000,
          );
        }
        return;
      }
      if (data.error) {
        reject(data.error);
        return;
      }
      cancel();
      done(data);
    };
    w.postMessage({ ...data, revision: own });
  }
  function loadStep(file) {
    resetNC();
    reference = null;
    geometry();
    $("aligned").checked = false;
    $("top-confirmed").checked = false;
    $("step-info").textContent = "STEP 읽는 중…";
    if (file.size > 10 * 1024 * 1024) {
      $("step-info").textContent = "STEP10MiB 상한 초과";
      return;
    }
    $("stock-status").textContent = "STEP 커널 읽기 중…";
    start(
      () =>
        new Worker(new URL("./nc-step.worker.js", import.meta.url), {
          type: "module",
        }),
      { file },
      (data) => {
        reference = data.reference;
        const bounds = meshBounds(reference.mesh);
        $("step-info").textContent =
          `${reference.fileName} · 체적 ${reference.volume.toFixed(3)} mm³ · 원본 mm 경계 [${bounds[0].map((v) => v.toFixed(2))}]→[${bounds[1].map((v) => v.toFixed(2))}]`;
        $("stock-status").textContent = "STEP 읽기 완료 · 좌표 정합 확인 필요";
        geometry();
      },
    );
  }
  $("step-file").onchange = (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (file) loadStep(file);
  };
  $("step-sample").onclick = () =>
    loadStep(
      new File([stepSample], "cnc_CAD13_2026-10-07_target.step", {
        type: "application/step",
      }),
    );
  $("stock-analyze").onclick = () => {
    resetNC();
    try {
      const nc = getNC(),
        s = setup();
      if (!nc?.complete) throw Error("전체 해석된 NC 필요");
      if (!reference) throw Error("단일 Solid STEP 필요");
      if (!s.aligned || !s.topSurfaceConfirmed)
        throw Error("STEP/G54 정합·상면 확인 전 비교 차단");
      $("stock-status").textContent = "소재 검토 중…";
      start(
        () =>
          new Worker(new URL("./nc-stock.worker.js", import.meta.url), {
            type: "module",
          }),
        {
          nc: {
            complete: nc.complete,
            segments: nc.segments,
            sourceHash: nc.sourceHash,
          },
          reference,
          setup: s,
        },
        (data) => {
          analysis = data.analysis;
          onChange();
          $("stock-status").textContent =
            "상면 근사 검토 완료 · 기계 안전 판정 아님";
          $("stock-report").textContent =
            `제거 ${analysis.removed.toFixed(3)} mm³\n잔삭 ${analysis.remaining.toFixed(3)} mm³ / 최대 ${analysis.maxRemaining.toFixed(3)} mm\n과절삭 ${analysis.overcut.toFixed(3)} mm³ / 최대 ${analysis.maxOvercut.toFixed(3)} mm\n급속 소재 접촉 후보 ${analysis.rapidContactLines.length}행\n격자 ${analysis.grid.nx}×${analysis.grid.ny} · 공차 기준 ${analysis.tolerance}mm\n목표 격자 체적 오차 ${(analysis.targetVolumeError * 100).toFixed(2)}%\n시간·소비는 별도 장비 모델에서 계산`;
          for (const line of analysis.rapidContactLines) {
            const b = document.createElement("button");
            b.textContent = `${line}행 급속 접촉`;
            b.onclick = () => selectLine(line);
            $("contact-lines").append(b);
          }
          geometry();
        },
      );
    } catch (error) {
      $("stock-status").textContent = error.message;
    }
  };
  $("stock-cancel").onclick = () => {
    const step = worker?.step;
    resetNC();
    if (step) {
      reference = null;
      $("step-info").textContent = "STEP 읽기 취소";
      geometry();
    }
    $("stock-status").textContent = "사용자가 소재 검토 취소";
  };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && worker) {
      e.preventDefault();
      $("stock-cancel").click();
    }
  });
  geometry();
  return {
    analysis: () => analysis,
    resetNC,
    export: () => ({
      setup: (() => {
        try {
          return setup();
        } catch {
          return null;
        }
      })(),
      analysis,
      reference: reference
        ? {
            fileName: reference.fileName,
            sourceHash: reference.sourceHash,
            volume: reference.volume,
            bounds: meshBounds(reference.mesh),
          }
        : null,
    }),
  };
}
