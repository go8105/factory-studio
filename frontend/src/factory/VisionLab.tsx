import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  defaultRecipe,
  inspect,
  samples,
  type Recipe,
  type Sample,
} from "./inspection";
import "./VisionLab.css";
import InspectionView from "./InspectionView";
import NativeSingle from "./NativeSingle";
import VisionRun from "./VisionRun";
export default function VisionLab() {
  const [sample, setSample] = useState<Sample>("foreign");
  const [recipe, setRecipe] = useState<Recipe>({ ...defaultRecipe });
  const [mode, setMode] = useState<"teach" | "run">("teach");
  const request = useMemo(
    () => ({ version: 1 as const, sample, recipe }),
    [sample, recipe],
  );
  const result = useMemo(() => inspect(request), [request]);
  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify({ request, result }, null, 2)], {
        type: "application/json",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `vision-${sample}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <main className="vision-lab">
      <header>
        <div>
          <span className="eyebrow">VISION LAB · SYNTHETIC</span>
          <h1>합성 이미지 검사실</h1>
          <p>
            직접 만든 가상 표면 이미지로 검사 조건을 비교합니다. 브라우저 검사와
            서버 C++ OpenCV 검사를 체험합니다. 실장비는 연결하지 않았습니다.
          </p>
        </div>
        <div>
          <Link to="/help/portal/vision-lab">검사실 사용 도움말</Link> ·{" "}
          <Link to="/factory">3D 공장으로 돌아가기</Link>
        </div>
      </header>
      <nav className="lab-mode" aria-label="검사 모드">
        <button
          aria-pressed={mode === "teach"}
          onClick={() => setMode("teach")}
        >
          레시피 설정
        </button>
        <button aria-pressed={mode === "run"} onClick={() => setMode("run")}>
          연속 검사
        </button>
      </nav>
      <div hidden={mode !== "teach"}>
        <div className="lab-grid">
          <InspectionView request={request} result={result} />
          <aside className="lab-controls" aria-label="검사 조건">
            <h2>검사 레시피</h2>
            <label>
              합성 샘플
              <select
                value={sample}
                onChange={(e) => setSample(e.target.value as Sample)}
              >
                {Object.entries(samples).map(([id, name]) => (
                  <option value={id} key={id}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              검사 영역
              <select
                value={recipe.roi}
                onChange={(e) =>
                  setRecipe({ ...recipe, roi: e.target.value as Recipe["roi"] })
                }
              >
                <option value="full">전체 표면</option>
                <option value="center">중앙 영역</option>
              </select>
            </label>
            <label>
              이진화 임계값: {recipe.threshold}
              <input
                aria-label="이진화 임계값"
                type="range"
                min="0"
                max="255"
                value={recipe.threshold}
                onChange={(e) =>
                  setRecipe({ ...recipe, threshold: Number(e.target.value) })
                }
              />
            </label>
            <label>
              최소 면적: {recipe.minArea} px²
              <input
                aria-label="최소 면적"
                type="range"
                min="1"
                max="200"
                value={recipe.minArea}
                onChange={(e) =>
                  setRecipe({ ...recipe, minArea: Number(e.target.value) })
                }
              />
            </label>
            <button onClick={() => setRecipe({ ...defaultRecipe })}>
              조건 초기화
            </button>
            <button onClick={download}>레시피·결과 JSON 저장</button>
            <details>
              <summary>비교 방법과 샘플 안내</summary>
              <ol>
                <li>이물 샘플의 기본 조건에서는 결함 2개를 검출합니다.</li>
                <li>최소 면적을 100으로 높이면 작은 결함을 놓칩니다.</li>
                <li>
                  조명 변화에서 임계값을 130으로 높이면 그림자도 검출합니다.
                </li>
                <li>중앙 영역을 선택하면 오른쪽 결함은 검사에서 제외됩니다.</li>
              </ol>
              <p>
                현재 조건은 샘플을 바꿔도 유지됩니다. 정상 샘플의 작은 잡음
                4픽셀은 결함이 아닙니다. 결과는 저장 버튼으로만 내려받으며
                서버·MES에 기록하지 않습니다.
              </p>
            </details>
          </aside>
        </div>
      </div>
      {mode === "teach" && (
        <NativeSingle key={JSON.stringify(request)} request={request} />
      )}
      <VisionRun recipe={recipe} visible={mode === "run"} />
    </main>
  );
}
