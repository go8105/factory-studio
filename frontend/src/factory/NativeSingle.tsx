import { useEffect, useRef, useState } from "react";
import type { InspectionRequest, InspectionResult } from "./inspection";
import InspectionView from "./InspectionView";
import { useNativeEngine } from "./useNativeEngine";
export default function NativeSingle({
  request,
}: {
  request: InspectionRequest;
}) {
  const engine = useNativeEngine();
  const alive = useRef(true);
  const [output, setOutput] = useState<{
    result: InspectionResult;
    inspectionMs: number;
  } | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  async function run() {
    if (pending) return;
    setPending(true);
    setError("");
    setOutput(null);
    try {
      const result = await engine.execute(request);
      if (alive.current) setOutput(result);
    } catch (e) {
      if (alive.current)
        setError(e instanceof Error ? e.message : "C++ 검사 실패");
    } finally {
      if (alive.current) setPending(false);
    }
  }
  function download() {
    if (!output) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify({ request, ...output }, null, 2)], {
        type: "application/json",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "vision-native.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <section className="run-controls" aria-label="C++ 단건 검사">
      <h2>C++ OpenCV로 같은 조건 검사</h2>
      <p>
        위 설정 화면은 브라우저 검사 결과입니다. 버튼을 누르면 서버의 C++ 엔진을
        실제 호출합니다. 서버에 엔진이 없으면 오류를 표시합니다.
      </p>
      <div className="run-actions">
        <button disabled={pending} onClick={() => void run()}>
          {pending ? "C++ 검사 중…" : "C++ 단건 검사"}
        </button>
        <button disabled={!output} onClick={download}>
          C++ 결과 JSON 저장
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {output && (
        <>
          <p>
            실행 출처: C++ OpenCV · 순수 검사 처리 시간{" "}
            {output.inspectionMs.toFixed(3)} ms
          </p>
          <InspectionView request={request} result={output.result} />
        </>
      )}
    </section>
  );
}
