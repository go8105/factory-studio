import { Link } from "react-router-dom";
import type { Dispatch } from "react";
import { cncPhases, cncPose, type CncAction, type CncState } from "./cnc";
export default function CncPanel({
  state,
  dispatch,
  enabled,
  onClose,
  onFocus,
}: {
  state: CncState;
  dispatch: Dispatch<CncAction>;
  enabled: boolean;
  onClose: () => void;
  onFocus: () => void;
}) {
  const pose = cncPose(state);
  const labels = {
    idle: "준비",
    running: "운전 중",
    paused: "일시정지",
    fault: "오류 정지",
    complete: "가공 완료",
  };
  const locations = {
    input: "소재 받침",
    gripper: "로봇 그리퍼",
    jig: "CNC 지그",
    output: "검사 대기 위치",
  };
  return (
    <section className="vision-panel cnc-panel" aria-label="CNC 설비 상세">
      <button className="inspector-close" onClick={onClose}>
        상세 닫기
      </button>
      <Link to="/help/portal/cnc-cell">CNC 사용 도움말</Link>
      <span className="eyebrow">ROBOT + CNC / DEMO-01</span>
      <h2>로봇 연동 CNC 가공 셀</h2>
      <p>
        알루미늄 사각 소재를 로봇으로 투입하고 포켓·체결 구멍을 가공합니다. 한
        번 시작할 때 1개를 처리합니다.
      </p>
      <dl>
        <div>
          <dt>설비 상태</dt>
          <dd data-testid="cnc-mode">
            {state.mode === "running" && !enabled
              ? "시연 대기"
              : labels[state.mode]}
          </dd>
        </div>
        <div>
          <dt>현재 단계</dt>
          <dd data-testid="cnc-phase">
            {state.mode === "idle" ? "시작 대기" : cncPhases[state.phase][0]}
          </dd>
        </div>
        <div>
          <dt>소재 위치</dt>
          <dd data-testid="cnc-location">{locations[pose.location]}</dd>
        </div>
        <div>
          <dt>가공 완료</dt>
          <dd data-testid="cnc-count">{state.completed}개</dd>
        </div>
        <div>
          <dt>종료 후 보류</dt>
          <dd data-testid="cnc-held">{state.held}개</dd>
        </div>
        <div>
          <dt>형상</dt>
          <dd>{pose.machined ? "포켓·구멍 가공품" : "사각 원소재"}</dd>
        </div>
      </dl>
      <p role="status">{state.message}</p>
      {!enabled && (
        <p>
          3D 준비·내부 보기·시연 재생 상태에서 동작합니다. 탭을 숨기면
          일시정지됩니다.
        </p>
      )}
      <div className="factory-actions">
        <button onClick={onFocus}>CNC 가까이 보기</button>
        <button
          disabled={
            !enabled || !(state.mode === "idle" || state.mode === "complete")
          }
          onClick={() => dispatch({ type: "start" })}
        >
          CNC 1개 시작
        </button>
        <button
          disabled={state.mode !== "running"}
          onClick={() => dispatch({ type: "pause" })}
        >
          CNC 일시정지
        </button>
        <button
          disabled={!enabled || state.mode !== "paused" || state.alarm}
          onClick={() => dispatch({ type: "resume" })}
        >
          CNC 재개
        </button>
        <button
          disabled={state.mode !== "running" && state.mode !== "paused"}
          onClick={() => dispatch({ type: "stop" })}
        >
          CNC 종료·소재 보류
        </button>
        <button
          disabled={state.mode !== "running" && state.mode !== "paused"}
          onClick={() => dispatch({ type: "fault" })}
        >
          모의 CNC 오류
        </button>
        <button
          disabled={state.mode !== "fault"}
          onClick={() => dispatch({ type: "clear" })}
        >
          CNC 오류 해제
        </button>
      </div>
      <details>
        <summary>동작 순서와 모의 인터락</summary>
        <p>
          집기 → 투입 → 로봇 퇴피 → 고정 → 문 닫기 → 가공 → 주축 정지 → 문 열기
          → 고정 해제 → 꺼내기 → 배출
        </p>
        <ul>
          <li>
            문:{" "}
            {pose.door === 1 ? "닫힘" : pose.door === 0 ? "열림" : "이동 중"}
          </li>
          <li>소재 고정: {pose.clamped ? "고정" : "해제"}</li>
          <li>로봇 퇴피: {pose.clear ? "확인" : "미확인"}</li>
          <li>주축: {pose.spindle && enabled ? "가동" : "정지"}</li>
        </ul>
        <p>
          오류 해제 후 재개를 눌러야 복구됩니다. 종료한 진행 소재는 완료 수에
          포함하지 않습니다.
        </p>
      </details>
      <p className="vision-source">
        브라우저 합성 시연 · 실제 안전 제어·절삭 해석·치수 검사 아님. 가공
        수량은 비전검사·MES·재고와 아직 연결되지 않습니다. 화면을 나가면
        초기화됩니다.
      </p>
    </section>
  );
}
