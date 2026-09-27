import { useEffect, useState, useSyncExternalStore } from "react";
import { samples, type Recipe } from "./inspection";
import { InspectionRun, runSummary, sequence } from "./inspectionRun";
import InspectionView from "./InspectionView";
const labels = {
  idle: "준비",
  running: "검사 중",
  paused: "일시정지",
  completed: "배치 완료",
  stopped: "종료",
  error: "검사 오류",
};
export default function VisionRun({
  recipe,
  visible,
}: {
  recipe: Recipe;
  visible: boolean;
}) {
  const [runner] = useState(() => new InspectionRun(recipe));
  const state = useSyncExternalStore(runner.subscribe, runner.snapshot);
  const [interval, setInterval] = useState(500);
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => () => runner.stop(), [runner]);
  useEffect(() => {
    if (!visible) runner.pause();
  }, [runner, visible]);
  useEffect(() => {
    const hide = () => {
      if (document.hidden) runner.pause();
    };
    document.addEventListener("visibilitychange", hide);
    return () => document.removeEventListener("visibilitychange", hide);
  }, [runner]);
  const summary = runSummary(state.records);
  const active = state.status === "running" || state.status === "paused";
  const record =
    state.records.find((r) => r.inspectionId === selected) ??
    state.records.at(-1);
  function download() {
    const url = URL.createObjectURL(
      new Blob(
        [
          JSON.stringify(
            { ...state, source: "synthetic-browser-v1", sequence, summary },
            null,
            2,
          ),
        ],
        { type: "application/json" },
      ),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `vision-run-${state.runId}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <section hidden={!visible} aria-label="연속 검사 관제">
      <div className="run-controls">
        <div className="lab-toolbar">
          <h2>
            연속 검사{" "}
            <span className="run-badge" role="status">
              {labels[state.status]}
            </span>
          </h2>
          <label>
            투입 목표 간격{" "}
            <select
              aria-label="투입 목표 간격"
              value={interval}
              disabled={active}
              onChange={(e) => setInterval(Number(e.target.value))}
            >
              <option value={500}>500 ms</option>
              <option value={200}>200 ms</option>
            </select>
          </label>
        </div>
        <p>
          정상 → 이물 → 정상 → 조명 변화, 5회 반복 · 기존 샘플 3종으로 총 20회
          검사합니다.
        </p>
        <div className="run-actions">
          <button
            disabled={active}
            onClick={() => {
              setSelected(null);
              runner.start(recipe, interval);
            }}
          >
            새 배치 시작
          </button>
          <button
            disabled={state.status !== "running"}
            onClick={() => runner.pause()}
          >
            일시정지
          </button>
          <button
            disabled={state.status !== "paused"}
            onClick={() => runner.resume()}
          >
            재개
          </button>
          <button disabled={!active} onClick={() => runner.stop()}>
            배치 종료
          </button>
          <button disabled={!state.records.length} onClick={download}>
            배치 JSON 저장
          </button>
        </div>
        <p>
          시작 시 레시피를 고정합니다. 설정 모드 이동·탭 숨김 시 일시정지하며
          진행 중 결과까지 반영합니다. 새 배치는 이전 이력을 교체합니다.
        </p>
        {state.runId && (
          <p>
            배치 조건: 임계값 {state.recipe.threshold} · 최소 면적{" "}
            {state.recipe.minArea} px² ·{" "}
            {state.recipe.roi === "full" ? "전체 표면" : "중앙 영역"} · 목표
            간격 {state.intervalMs} ms
          </p>
        )}
        {state.error && <p role="alert">{state.error}</p>}
        <dl className="run-metrics">
          <div>
            <dt>검사 완료</dt>
            <dd data-testid="run-count">{summary.completed} / 20</dd>
          </div>
          <div>
            <dt>OK / NG</dt>
            <dd>
              {summary.ok} / {summary.ng}
            </dd>
          </div>
          <div>
            <dt>검사 합격률</dt>
            <dd>
              {summary.passRate === null
                ? "—"
                : `${summary.passRate.toFixed(1)}%`}
            </dd>
          </div>
          <div>
            <dt>평균 검사 처리 시간</dt>
            <dd>
              {summary.averageMs === null
                ? "—"
                : `${summary.averageMs.toFixed(3)} ms`}
            </dd>
          </div>
        </dl>
        <p>
          합격률은 OK ÷ 완료 수입니다. 미검출도 OK가 될 수 있습니다. 처리 시간은
          브라우저 검사 함수 실행만 측정하며 투입 대기·화면 렌더링을 제외합니다.
          실장비 성능이나 생산 수율이 아닙니다.
        </p>
      </div>
      <div className="lab-grid run-grid">
        <div>
          {record ? (
            <>
              <div className="lab-toolbar">
                <strong>
                  {selected ? "이력 재조회" : "최근 검사"} · #{record.sequence}{" "}
                  · {record.inspectionMs.toFixed(3)} ms
                </strong>
                <button disabled={!selected} onClick={() => setSelected(null)}>
                  최근 검사 보기
                </button>
              </div>
              <InspectionView request={record.request} result={record.result} />
              <p>
                검사 시각: {record.completedAt} · 판정 조건: 픽셀 값 &lt;{" "}
                {record.request.recipe.threshold}, 연결 면적 ≥{" "}
                {record.request.recipe.minArea} px²
              </p>
              <ul className="run-regions">
                {record.result.regions.map((r, i) => (
                  <li key={i}>
                    영역 {i + 1}: ({r.x}, {r.y}) · {r.width} × {r.height} px ·{" "}
                    {r.area} px² ≥ {record.request.recipe.minArea} px²
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <div className="lab-image">
              <h2>검사 대기</h2>
              <p>레시피 설정에서 조건을 조정한 뒤 새 배치를 시작하세요.</p>
            </div>
          )}
        </div>
        <aside className="lab-controls">
          <h2>NG 이력 · {summary.ng}건</h2>
          <p>항목을 선택하면 당시 이미지와 판정 조건을 표시합니다.</p>
          <div className="run-history">
            {state.records
              .filter((r) => r.result.status === "NG")
              .map((r) => (
                <button
                  key={r.inspectionId}
                  aria-pressed={selected === r.inspectionId}
                  onClick={() => setSelected(r.inspectionId)}
                >
                  #{r.sequence} · {samples[r.request.sample]} · NG
                  <br />
                  <small>
                    {r.result.regions.length}개 영역 ·{" "}
                    {r.inspectionMs.toFixed(3)} ms
                  </small>
                </button>
              ))}
          </div>
          {!summary.ng && <p>NG 기록이 없습니다.</p>}
          <h3>샘플별 NG / 완료</h3>
          <ul>
            {Object.entries(samples).map(([id, label]) => (
              <li key={id}>
                {label}:{" "}
                {
                  state.records.filter(
                    (r) => r.request.sample === id && r.result.status === "NG",
                  ).length
                }{" "}
                / {state.records.filter((r) => r.request.sample === id).length}
              </li>
            ))}
          </ul>
          <h3>정답 대비 누적 픽셀</h3>
          <p>
            오검출 {state.records.reduce((n, r) => n + r.result.falsePixels, 0)}{" "}
            · 미검출{" "}
            {state.records.reduce((n, r) => n + r.result.missedPixels, 0)} ·
            영역 밖{" "}
            {state.records.reduce((n, r) => n + r.result.excludedPixels, 0)}
          </p>
          <p>
            조명 변화 샘플에도 이물이 포함됩니다. 샘플별 집계는 불량 원인 분류가
            아닙니다. 기록은 현재 화면 메모리에만 보관합니다.
          </p>
        </aside>
      </div>
    </section>
  );
}
