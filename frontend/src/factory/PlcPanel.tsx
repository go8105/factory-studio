import { PlcHandshake, plcSignals, type PlcState } from "./plcHandshake";
const phases = {
  ready: "Ready · 준비",
  busy: "Busy · 검사 중",
  done: "Done · 결과 확인 대기",
  fault: "Fault · 인터락",
};
const faults = {
  INSPECTION_TIMEOUT: "검사 응답 300ms 초과",
  ACK_TIMEOUT: "PLC 결과 확인 1000ms 초과",
  ENGINE_ERROR: "검사 엔진 오류",
};
export default function PlcPanel({
  plc,
  state,
  enabled,
  active,
  onEnabled,
}: {
  plc: PlcHandshake;
  state: PlcState;
  enabled: boolean;
  active: boolean;
  onEnabled: (enabled: boolean) => void;
}) {
  return (
    <section className="plc-panel" aria-label="가상 PLC 핸드셰이크">
      <div className="lab-toolbar">
        <h2>가상 PLC 핸드셰이크</h2>
        <label>
          <input
            type="checkbox"
            checked={enabled}
            disabled={active || state.phase === "fault"}
            onChange={(e) => onEnabled(e.target.checked)}
          />{" "}
          PLC 모드 사용
        </label>
      </div>
      <p>
        브라우저 내부 신호 교환 시뮬레이션입니다. 실제 PLC·통신 드라이버·안전
        제어는 연결하지 않았습니다.
      </p>
      {enabled && (
        <>
          <p>
            <strong data-testid="plc-phase">{phases[state.phase]}</strong> ·
            Recipe_ID: RUN_SNAPSHOT (배치 시작 레시피)
          </p>
          <div className="plc-signals">
            {Object.entries(plcSignals(state)).map(([name, on]) => (
              <div
                key={name}
                className={
                  on
                    ? `plc-signal is-on${name === "Interlock" ? " is-alarm" : ""}`
                    : "plc-signal"
                }
                data-testid={`plc-${name}`}
              >
                <span aria-hidden="true" />
                {name}
                <strong>{on ? "ON" : "OFF"}</strong>
              </div>
            ))}
          </div>
          <p>
            PLC → 비전: Ready 요청·Trigger·Recipe_ID / 비전 → PLC:
            Ready·Busy·Done·OK/NG·Interlock
          </p>
          <p>
            Defect_Code: {state.result === "NG" ? "DARK_REGION" : "NONE"} ·
            Alarm_Code: {state.fault ?? "NONE"}
          </p>
          {state.fault && (
            <p role="alert">
              {faults[state.fault]}: 신규 검사 차단. PLC 리셋 후 새 배치를
              시작하세요. 장애는 제품 NG로 집계하지 않습니다.
            </p>
          )}
          <div className="run-actions">
            <button
              disabled={state.phase === "fault"}
              onClick={() => plc.inject("delay")}
            >
              다음 검사 지연 주입
            </button>
            <button
              disabled={state.phase === "fault"}
              onClick={() => plc.inject("missingAck")}
            >
              다음 결과 확인 누락
            </button>
            <button
              disabled={state.injection === "none"}
              onClick={() => plc.inject("none")}
            >
              주입 취소
            </button>
            <button
              disabled={state.phase !== "done"}
              onClick={() => plc.acknowledge()}
            >
              PLC 결과 확인
            </button>
            <button
              disabled={state.phase !== "busy" && state.phase !== "done"}
              onClick={() => plc.duplicateTrigger()}
            >
              중복 트리거 주입
            </button>
            <button
              disabled={active || state.phase !== "fault"}
              onClick={() => plc.reset()}
            >
              PLC 리셋
            </button>
          </div>
          <p>
            예약:{" "}
            {state.injection === "delay"
              ? "다음 검사 응답 450ms 지연"
              : state.injection === "missingAck"
                ? "다음 자동 결과 확인 생략"
                : "없음"}{" "}
            · 1회 소비
          </p>
          <p>
            정상: Trigger → Busy → 결과/Done → 자동 확인 → Ready. 검사 제한
            300ms, 확인 제한 1000ms. 정상 표시 지연 80ms와 자동 확인 대기
            120ms는 검사 처리 시간에 포함하지 않습니다.
          </p>
          <p>
            PLC 모드의 완료 수는 결과 확인까지 끝난 거래 수입니다. 확인 타임아웃
            시 Done과 판정은 리셋까지 유지되며, 해당 거래는 배치 수량에서
            제외합니다.
          </p>
          <details open={state.phase === "fault"}>
            <summary>신호 이벤트 로그 · {state.events.length}건</summary>
            <ol className="plc-events">
              {state.events.map((event, i) => (
                <li key={i}>
                  <time>{event.at.slice(11, 23)} UTC</time> · {event.event}
                  <small>{event.inspectionId ?? "요청 없음"}</small>
                </li>
              ))}
            </ol>
          </details>
        </>
      )}
    </section>
  );
}
