import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  defaultRecipe,
  fixture,
  HEIGHT,
  inspect,
  roiBox,
  samples,
  WIDTH,
  type Recipe,
  type Sample,
} from "./inspection";
import "./VisionLab.css";
export default function VisionLab() {
  const [sample, setSample] = useState<Sample>("foreign");
  const [recipe, setRecipe] = useState<Recipe>({ ...defaultRecipe });
  const [binary, setBinary] = useState(false);
  const canvas = useRef<HTMLCanvasElement>(null);
  const request = useMemo(
    () => ({ version: 1 as const, sample, recipe }),
    [sample, recipe],
  );
  const result = useMemo(() => inspect(request), [request]);
  const roi = roiBox(recipe.roi);
  useEffect(() => {
    const ctx = canvas.current?.getContext("2d");
    if (!ctx) return;
    const { pixels } = fixture(sample);
    const image = ctx.createImageData(WIDTH, HEIGHT);
    pixels.forEach((v, i) => {
      const value = binary ? (v < recipe.threshold ? 255 : 0) : v;
      image.data.set([value, value, value, 255], i * 4);
    });
    ctx.putImageData(image, 0, 0);
  }, [sample, binary, recipe.threshold]);
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
            직접 만든 가상 표면 이미지로 검사 조건을 비교합니다.
            실장비·OpenCV·AI 추론은 연결하지 않았습니다.
          </p>
        </div>
        <Link to="/factory">3D 공장으로 돌아가기</Link>
      </header>
      <div className="lab-grid">
        <section className="lab-image" aria-label="검사 이미지">
          <div className="lab-toolbar">
            <strong>{samples[sample]} 샘플 · 160 × 100 px</strong>
            <button aria-pressed={binary} onClick={() => setBinary(!binary)}>
              {binary ? "원본 보기" : "이진화 보기"}
            </button>
          </div>
          <div className="lab-picture">
            <canvas
              ref={canvas}
              width={WIDTH}
              height={HEIGHT}
              aria-label="합성 검사 이미지"
            />
            <svg
              viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              role="img"
              aria-label={`검출 영역 ${result.regions.length}개`}
            >
              <rect
                {...roi}
                fill="none"
                stroke="#327394"
                strokeWidth="1"
                strokeDasharray="3 2"
              />
              {result.regions.map((r, i) => (
                <rect
                  key={i}
                  x={r.x}
                  y={r.y}
                  width={r.width}
                  height={r.height}
                  fill="none"
                  stroke="#be4d43"
                  strokeWidth="0.8"
                />
              ))}
            </svg>
          </div>
          <p>
            파란 점선: 검사 영역 · 붉은 테두리: 검출 영역. 이진화 화면의 흰색은
            임계값보다 어두운 후보 픽셀입니다.
          </p>
          <div className="lab-result" role="status">
            <strong>{result.status}</strong>
            <span>
              검출 {result.regions.length}개 · 총{" "}
              {result.regions.reduce((sum, r) => sum + r.area, 0)} px²
            </span>
          </div>
          <p>
            {result.status === "NG"
              ? "최소 면적 이상의 어두운 연결 영역이 검출되었습니다. 실제 불량인지는 정답과 비교하세요."
              : "현재 검사 영역과 조건에서 검출 영역이 없습니다. 결함이 없다는 보장은 아닙니다."}
          </p>
          <dl className="lab-metrics">
            <div>
              <dt>오검출 픽셀</dt>
              <dd>{result.falsePixels}</dd>
            </div>
            <div>
              <dt>미검출 픽셀</dt>
              <dd>{result.missedPixels}</dd>
            </div>
            <div>
              <dt>영역 밖 결함 픽셀</dt>
              <dd>{result.excludedPixels}</dd>
            </div>
          </dl>
          <p>
            정답 마스크 대비 픽셀 수입니다. 미검출은 검사 영역 안에서만
            계산하며, 영역 밖 결함은 별도로 표시합니다.
          </p>
        </section>
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
    </main>
  );
}
