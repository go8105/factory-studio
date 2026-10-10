import { FANUC_REVIEW_PROFILE } from "./nc-controller.js";
import { NC_LIMITS } from "./nc-parser.js";
export function createNCPostReview(getContext, doc = document) {
  const panel = doc.createElement("details");
  panel.innerHTML = `<summary>NC 파일 출력 · FANUC 검토용</summary><p>기종 미정 · 장비 실행용 아님. 원본 또는 확인된 G4 변경 후보를 재해석해 출력합니다. G4 P는 밀리초 정수, H/D 보정은 미지원입니다. 실제 장비 호환·안전 검증은 별도입니다.</p><label>프로그램 번호 (1~7999)<input data-post-program type="number" min="1" max="7999" step="1" value="1001"></label><label>출력 대상 번호 (0: 원본)<input data-post-number type="number" min="0" max="13" step="1" value="0"></label><label class="check"><input data-post-confirm type="checkbox">초기 G54 좌표·단위·기본 상태와 공구표를 장비에서 별도로 확인해야 함을 이해했습니다</label><button data-post-prepare>검증·미리보기</button><button data-post-cancel disabled>검증 취소</button><p data-post-status role="status">현재 NC 해석 후 출력 대상을 선택하세요.</p><pre data-post-preview></pre><button data-post-save disabled>검증된 NC 저장 (.review.nc)</button><button data-post-manifest disabled>출력 검증 JSON 저장</button>`;
  doc.querySelector(".review-results").append(panel);
  const el = (s) => panel.querySelector(`[data-post-${s}]`);
  let worker, timer, prepared, fingerprint;
  const key = () =>
    JSON.stringify([
      getContext(),
      el("number").value,
      el("program").value,
      el("confirm").checked,
    ]);
  function reset() {
    worker?.terminate();
    worker = null;
    clearTimeout(timer);
    prepared = null;
    el("prepare").disabled = false;
    el("cancel").disabled = true;
    el("save").disabled = true;
    el("manifest").disabled = true;
    el("preview").textContent = "";
  }
  doc.addEventListener("input", () => {
    reset();
    el("status").textContent = "입력 변경 · 다시 검증하세요.";
  });
  // Model/STEP/example/proposal actions can invalidate without an input event.
  doc.addEventListener(
    "click",
    (e) => {
      if (!panel.contains(e.target)) {
        reset();
        el("status").textContent = "분석/선택 변경 · 다시 검증하세요.";
      }
    },
    true,
  );
  doc.addEventListener("visibilitychange", () => {
    if (doc.hidden) {
      reset();
      el("status").textContent = "탭 비활성 · 출력 검증 취소";
    }
  });
  el("cancel").onclick = () => {
    reset();
    el("status").textContent = "검증 취소";
  };
  el("prepare").onclick = () => {
    reset();
    if (!el("confirm").checked || !getContext().nc) {
      el("status").textContent = "현재 NC 해석과 환경 조건 확인이 필요합니다.";
      return;
    }
    fingerprint = key();
    const w = new Worker(new URL("./nc-post-worker.js", import.meta.url), {
      type: "module",
    });
    worker = w;
    el("prepare").disabled = true;
    el("cancel").disabled = false;
    el("status").textContent = "원본 해시·최신 후보·출력 재해석 검증 중…";
    const fail = (message) => {
      if (worker !== w) return;
      reset();
      el("status").textContent = message;
    };
    w.onerror = () => fail("출력 Worker 오류 · 다시 검증하세요");
    timer = setTimeout(
      () => fail("30초 검증 상한 초과"),
      NC_LIMITS.milliseconds,
    );
    w.onmessage = ({ data }) => {
      if (worker !== w) return;
      if (fingerprint !== key()) {
        fail("입력이 변경되었습니다. 다시 검증하세요.");
        return;
      }
      if (data.error) {
        fail(data.error);
        return;
      }
      w.terminate();
      worker = null;
      clearTimeout(timer);
      prepared = data.result;
      el("prepare").disabled = false;
      el("cancel").disabled = true;
      el("save").disabled = false;
      el("manifest").disabled = false;
      el("status").textContent =
        `재해석 보존 확인 · ${prepared.manifest.moves}이동 · 변경 ${prepared.manifest.changes.length}행 · post ${prepared.manifest.post} · 실장비 미검증`;
      el("preview").textContent =
        prepared.text.slice(0, 6000) +
        (prepared.text.length > 6000
          ? "\n…미리보기 생략 (저장 파일은 전체)"
          : "");
    };
    w.postMessage({
      ...getContext(),
      number: Number(el("number").value),
      profile: FANUC_REVIEW_PROFILE,
      programNumber: Number(el("program").value),
    });
  };
  function save(manifest) {
    if (!prepared || fingerprint !== key()) {
      reset();
      el("status").textContent = "입력 변경 · 다시 검증하세요.";
      return;
    }
    const base = `fanuc-review-O${prepared.manifest.programNumber}-${prepared.manifest.outputHash.slice(0, 12)}-${prepared.manifest.number ? `candidate-${prepared.manifest.number}` : "original"}`;
    const url = URL.createObjectURL(
      new Blob(
        [manifest ? JSON.stringify(prepared.manifest, null, 2) : prepared.text],
        { type: manifest ? "application/json" : "text/plain;charset=utf-8" },
      ),
    );
    const a = doc.createElement("a");
    a.href = url;
    a.download = base + (manifest ? ".verification.json" : ".review.nc");
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  el("save").onclick = () => save(false);
  el("manifest").onclick = () => save(true);
  return { reset };
}
