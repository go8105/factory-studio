import { useEffect, useRef, useState } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  demoExplanation,
  isExplanation,
  scenarios,
  type Explanation,
  type Scenario,
} from "./scenarios";

// The parent keys this component by scenario: switching cancels old explanations.
export default function VisionExplanation({
  scenario,
}: {
  scenario: Scenario;
}) {
  const { session, fail } = useSession();
  const [result, setResult] = useState<Explanation>();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  async function explain() {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setPending(true);
    setError("");
    const timeout = window.setTimeout(() => controller.abort("timeout"), 30000);
    try {
      const response = await api<unknown>(
        "/api/v1/factory/vision/explanation",
        {
          method: "POST",
          body: { scenario },
          csrf: session?.csrfToken,
          signal: controller.signal,
        },
      );
      if (controller.signal.aborted) return;
      if (!isExplanation(response.data, scenario))
        throw new Error("Invalid explanation");
      setResult(response.data);
    } catch (e) {
      if (controller.signal.aborted && controller.signal.reason !== "timeout")
        return;
      if (e instanceof ApiError && [401, 410].includes(e.status)) {
        fail(e);
        return;
      }
      if (e instanceof ApiError && e.status === 403) {
        setError(
          "설명 조회 권한을 확인하지 못했습니다. 새로고침 후 다시 시도하세요.",
        );
        return;
      }
      setResult(demoExplanation(scenario, "unavailable"));
    } finally {
      window.clearTimeout(timeout);
      if (
        !controller.signal.aborted ||
        controller.signal.reason === "timeout"
      ) {
        setPending(false);
        request.current = null;
      }
    }
  }
  const reason =
    result?.reason === "not_configured"
      ? "AI가 연결되지 않아 준비된 시나리오 설명을 표시합니다."
      : "AI 응답을 받지 못해 준비된 시나리오 설명을 표시합니다.";
  return (
    <section className="vision-explanation" aria-label="설비 AI 설명">
      <div className="vision-explanation-heading">
        <h3>상태 이해하기</h3>
        <button
          onClick={() => void explain()}
          disabled={pending}
          aria-expanded={!!result}
        >
          {pending ? "분석 중…" : result ? "AI 설명 다시 요청" : "AI 설명"}
        </button>
      </div>
      <p>
        현재 선택한 <strong>{scenarios[scenario].label}</strong> 시나리오의 고정
        비교 구간을 설명합니다. 실시간 검사 누계 분석은 아닙니다.
      </p>
      {pending && (
        <p role="status">
          근거를 확인하고 있습니다. 시나리오는 계속 전환할 수 있습니다.
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {result && (
        <div className="vision-explanation-result">
          <span className={`vision-explanation-source ${result.mode}`}>
            {result.mode === "ai"
              ? "AI 생성 · GPT-6 Astra"
              : "데모 설명 · AI 미연결"}
          </span>
          {result.mode === "demo" && <p>{reason}</p>}
          <p className="vision-explanation-summary">
            {result.narrative.summary}
          </p>
          <h4>확인된 사실</h4>
          <ul>
            {result.evidence.map((text, i) => (
              <li key={i}>{text}</li>
            ))}
          </ul>
          <h4>가능성 · 추가 확인 필요</h4>
          <ul>
            {result.narrative.hypotheses.map((text, i) => (
              <li key={i}>{text}</li>
            ))}
          </ul>
          <h4>다음 확인 항목</h4>
          <ol>
            {result.narrative.checks.map((text, i) => (
              <li key={i}>{text}</li>
            ))}
          </ol>
          <p className="vision-source">
            근거: 합성 시나리오 v1 · 장비 제어 및 업무 데이터 저장 없음
          </p>
        </div>
      )}
    </section>
  );
}
