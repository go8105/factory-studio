import { useEffect, useRef, useState } from "react";
import {
  fixture,
  HEIGHT,
  WIDTH,
  roiBox,
  samples,
  type InspectionRequest,
  type InspectionResult,
} from "./inspection";
export default function InspectionView({
  request,
  result,
}: {
  request: InspectionRequest;
  result: InspectionResult;
}) {
  const { sample, recipe } = request;
  const [binary, setBinary] = useState(false);
  const canvas = useRef<HTMLCanvasElement>(null);
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
  return (
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
        정답 마스크 대비 픽셀 수입니다. 미검출은 검사 영역 안에서만 계산하며,
        영역 밖 결함은 별도로 표시합니다.
      </p>
    </section>
  );
}
