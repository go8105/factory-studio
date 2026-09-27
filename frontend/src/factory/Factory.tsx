import { visionAt } from "./vision";
import {
  Component,
  Suspense,
  lazy,
  useEffect,
  useCallback,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Canvas } from "@react-three/fiber";
import { PCFShadowMap } from "three";
import { Link } from "react-router-dom";
import {
  START,
  OFFICE_START,
  stations,
  type Direction,
  type Point,
  type View,
} from "./world";
import "./Factory.css";
const Scene = lazy(() => import("./Scene"));
export class SceneBoundary extends Component<
  { children: ReactNode; onFailure?: () => void },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onFailure?.();
  }
  render() {
    return this.state.failed ? (
      <div className="factory-fallback" role="alert">
        <h2>3D 화면을 열지 못했습니다</h2>
        <p>
          브라우저의 그래픽 가속 설정을 확인하거나 다른 브라우저에서 다시 열어
          주세요. 아래 공간 설명은 계속 볼 수 있습니다.
        </p>
        <button onClick={() => this.setState({ failed: false })}>
          다시 시도
        </button>
        <Link to="/home">앱 런처로</Link>
      </div>
    ) : (
      this.props.children
    );
  }
}
const keyMap: Record<string, Direction> = {
  KeyW: "up",
  ArrowUp: "up",
  KeyS: "down",
  ArrowDown: "down",
  KeyA: "left",
  ArrowLeft: "left",
  KeyD: "right",
  ArrowRight: "right",
};
export default function Factory() {
  const [immersive, setImmersive] = useState(false);
  const [target, setTarget] = useState<number | null>(null);
  const [inspect, setInspect] = useState(0);
  function enterInspection() {
    setImmersive(true);
    setExterior(false);
    setWalking(false);
    setView("ground");
    setSelected(null);
    setTarget(null);
    position.current = { x: 4, y: 0, z: 4.6 };
    setReset((n) => n + 1);
  }
  function leaveInspection() {
    keys.current.clear();
    setImmersive(false);
    setFocused(true);
    setReset((n) => n + 1);
  }
  const [exterior, setExterior] = useState(true);
  const [vision, setVision] = useState(() => visionAt(0));
  const [fault, setFault] = useState(false);
  const [focused, setFocused] = useState(false);
  const [view, setView] = useState<View>("all");
  const [walking, setWalking] = useState(false);
  const [animated, setAnimated] = useState(
    () => !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
  );
  const [reset, setReset] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [ready, setReady] = useState(false);
  const markReady = useCallback(() => setReady(true), []);
  const [contextLost, setContextLost] = useState(false);
  const position = useRef<Point>({ ...START });
  const keys = useRef(new Set<Direction>());
  const stage = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const release = (e: KeyboardEvent) => keys.current.delete(keyMap[e.code]);
    const clear = () => keys.current.clear();
    window.addEventListener("keyup", release);
    window.addEventListener("blur", clear);
    document.addEventListener("visibilitychange", clear);
    return () => {
      window.removeEventListener("keyup", release);
      window.removeEventListener("blur", clear);
      document.removeEventListener("visibilitychange", clear);
    };
  }, []);
  useEffect(() => {
    keys.current.clear();
    if (walking || immersive) stage.current?.focus();
  }, [walking, immersive, reset]);
  useEffect(() => {
    if (!immersive) return;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
    };
  }, [immersive]);
  function viewpoint(next: View) {
    setExterior(false);
    setFocused(false);
    setView(next);
    position.current = { ...(next === "office" ? OFFICE_START : START) };
    setReset((n) => n + 1);
  }
  function toggleWalk() {
    setExterior(false);
    setWalking(!walking);
    if (!walking)
      position.current = { ...(view === "office" ? OFFICE_START : START) };
  }
  return (
    <div
      className={`factory-page${immersive ? " factory-immersive" : ""}`}
      role={immersive ? "dialog" : undefined}
      aria-modal={immersive || undefined}
      aria-label={immersive ? "1인칭 비전검사 체험" : undefined}
      onKeyDown={(e) => {
        if (!immersive) return;
        if (e.key === "Escape") {
          e.stopPropagation();
          leaveInspection();
        }
        if (e.key === "Tab") {
          const items = Array.from(
            e.currentTarget.querySelectorAll<HTMLElement>(
              'button:not(:disabled), a[href], [tabindex="0"]',
            ),
          ).filter((item) => item.getClientRects().length > 0);
          const first = items[0];
          const last = items[items.length - 1];
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first?.focus();
          }
        }
      }}
    >
      <div className="factory-heading">
        <div>
          <h1>공장, 한눈에 그리고 한 걸음씩</h1>
          <p>사무실에서 생산 현장까지, 제조가 이루어지는 공간을 둘러보세요.</p>
        </div>
        <span className="factory-demo">
          3D 합성 시연 · 실시간 설비 정보 아님
        </span>
      </div>
      <div className="factory-controls">
        <div
          className="factory-building-switch"
          role="group"
          aria-label="건물 표시"
        >
          <button
            aria-pressed={exterior}
            onClick={() => {
              setExterior(true);
              setWalking(false);
              setFocused(false);
              setReset((n) => n + 1);
            }}
          >
            건물 외관
          </button>
          <button
            aria-pressed={!exterior}
            onClick={() => {
              setExterior(false);
              setView("all");
              setFocused(false);
              setReset((n) => n + 1);
            }}
          >
            내부 펼쳐보기
          </button>
          <span>
            {exterior
              ? "사무동 · 생산동 · 하역장 · 옥상 공조 설비"
              : "지붕과 전면·오른쪽 외벽을 열어 내부를 표시합니다."}
          </span>
        </div>
        <div className="factory-toolbar" aria-label="공장 보기 설정">
          <div className="factory-tabs" role="group" aria-label="층 선택">
            {(
              [
                ["all", "전체"],
                ["ground", "1층 현장"],
                ["office", "2층 사무실"],
              ] as const
            ).map(([value, title]) => (
              <button
                key={value}
                aria-pressed={view === value}
                onClick={() => viewpoint(value)}
              >
                {title}
              </button>
            ))}
          </div>
          <div className="factory-actions">
            <button
              className="primary inspection-enter"
              onClick={enterInspection}
            >
              1인칭 비전검사 체험
            </button>
            {immersive && (
              <>
                <span className="factory-demo">
                  합성 시연 · 실시간 계측 아님
                </span>
                <button onClick={leaveInspection}>체험 나가기</button>
              </>
            )}
            <button
              className="primary"
              aria-pressed={walking}
              onClick={toggleWalk}
            >
              {walking ? "전체 조감도로" : "걸어서 둘러보기"}
            </button>
            <button
              aria-pressed={!animated}
              onClick={() => setAnimated(!animated)}
            >
              {animated ? "시연 일시정지" : "시연 재생"}
            </button>
            <button
              onClick={() => {
                setFocused(false);
                position.current = immersive
                  ? { x: 4, y: 0, z: 4.6 }
                  : { ...(view === "office" ? OFFICE_START : START) };
                setReset((n) => n + 1);
              }}
            >
              시점 초기화
            </button>
          </div>
        </div>
      </div>
      <p id="factory-controls" className="factory-instructions">
        {immersive
          ? "드래그로 시선 이동 · WASD / 방향키로 이동 · 설비 클릭 또는 정면을 향해 E · Esc 나가기"
          : walking
            ? "노란 조끼가 나입니다. 화면을 선택한 뒤 WASD·방향키 또는 이동 버튼으로 걸어보세요. 계단으로 2층 이동 · Esc 조감도"
            : "마우스로 드래그하여 회전 · 휠로 확대 / 축소 · 터치로 회전 · 설비를 선택하면 공정 설명"}
      </p>
      <div
        className={`factory-view factory-workspace${immersive && selected !== null ? " has-inspector" : ""}`}
      >
        <div
          ref={stage}
          className={`factory-stage${exterior ? " factory-exterior" : ""}`}
          tabIndex={0}
          role="region"
          aria-label="3D 공장 탐색"
          aria-describedby="factory-controls"
          onKeyDown={(e) => {
            if ((!walking && !immersive) || e.target !== stage.current) return;
            if (keyMap[e.code]) {
              e.preventDefault();
              keys.current.add(keyMap[e.code]);
            }
            if (e.code === "KeyE" && immersive && !e.repeat)
              setInspect((n) => n + 1);
            if (e.code === "Escape" && !immersive) setWalking(false);
          }}
          onBlur={() => keys.current.clear()}
          onPointerDown={(e) => {
            if (e.target instanceof HTMLCanvasElement && (walking || immersive))
              stage.current?.focus();
          }}
        >
          <SceneBoundary onFailure={() => setReady(true)}>
            {contextLost ? (
              <div role="alert" className="factory-fallback">
                <p>그래픽 연결이 끊겼습니다.</p>
                <button
                  onClick={() => {
                    setContextLost(false);
                    setReady(false);
                  }}
                >
                  3D 다시 열기
                </button>
              </div>
            ) : (
              <Canvas
                shadows={{ type: PCFShadowMap }}
                dpr={[1, 1.5]}
                camera={{
                  position: [23, 22, 28],
                  fov: 43,
                  near: 0.1,
                  far: 150,
                }}
                gl={{ antialias: true }}
                onCreated={({ gl }) => {
                  gl.domElement.addEventListener(
                    "webglcontextlost",
                    (e) => {
                      e.preventDefault();
                      setContextLost(true);
                    },
                    { once: true },
                  );
                }}
                fallback={
                  <div className="factory-fallback">
                    이 브라우저에서는 3D 그래픽을 사용할 수 없습니다. 아래 공간
                    설명을 확인해 주세요.
                  </div>
                }
              >
                <Suspense fallback={null}>
                  <Scene
                    immersive={immersive}
                    inspect={inspect}
                    onTarget={setTarget}
                    onReady={markReady}
                    exterior={exterior}
                    fault={fault}
                    focused={focused}
                    onSnapshot={setVision}
                    view={view}
                    walking={walking}
                    animated={animated}
                    position={position}
                    keys={keys}
                    reset={reset}
                    onSelect={setSelected}
                  />
                </Suspense>
              </Canvas>
            )}
          </SceneBoundary>
          {!ready && !contextLost && (
            <span className="factory-loading" role="status">
              3D 공간 준비 중…
            </span>
          )}
          <div className="factory-view-badge" aria-live="polite">
            {immersive
              ? "FIRST PERSON · 비전검사 구역"
              : exterior
                ? "EXTERIOR · 공장 외관"
                : walking
                  ? "WALK · 자유 이동"
                  : "CUTAWAY · 내부 둘러보기"}
          </div>
          {immersive && (
            <>
              <span
                className={`factory-reticle${target !== null ? " active" : ""}`}
                aria-hidden="true"
              />
              <button
                className="factory-inspect-target"
                disabled={target === null}
                onClick={() => setInspect((n) => n + 1)}
              >
                {target === null
                  ? "설비를 향해 바라보세요"
                  : `${stations[target].name} · 상태 확인 (E)`}
              </button>
            </>
          )}
          {(walking || immersive) && (
            <div className="factory-pad" role="group" aria-label="캐릭터 이동">
              {(
                [
                  ["up", "↑", "앞으로"],
                  ["left", "←", "왼쪽으로"],
                  ["down", "↓", "뒤로"],
                  ["right", "→", "오른쪽으로"],
                ] as const
              ).map(([direction, arrow, label]) => (
                <button
                  key={direction}
                  className={`pad-${direction}`}
                  aria-label={label}
                  onPointerDown={(e) => {
                    e.preventDefault();
                    e.currentTarget.setPointerCapture(e.pointerId);
                    keys.current.add(direction);
                  }}
                  onPointerUp={() => keys.current.delete(direction)}
                  onPointerCancel={() => keys.current.delete(direction)}
                  onLostPointerCapture={() => keys.current.delete(direction)}
                  onKeyDown={(e) => {
                    if (e.key === " " || e.key === "Enter") {
                      e.preventDefault();
                      keys.current.add(direction);
                    }
                  }}
                  onKeyUp={() => keys.current.delete(direction)}
                >
                  {arrow}
                </button>
              ))}
            </div>
          )}
        </div>
        {immersive && selected !== null && selected !== 1 && (
          <section className="vision-panel" aria-label="공정 설명">
            <button
              onClick={() => {
                setSelected(null);
                stage.current?.focus();
              }}
            >
              상세 닫기
            </button>
            <h2>{stations[selected].name}</h2>
            <p>{stations[selected].detail}</p>
            <p>이 공정의 계측값은 아직 연결되지 않았습니다.</p>
          </section>
        )}
        {selected === 1 && (
          <section className="vision-panel" aria-label="비전검사 설비 상세">
            <button
              className="inspector-close"
              onClick={() => {
                setSelected(null);
                stage.current?.focus();
              }}
            >
              상세 닫기
            </button>
            <div>
              <span className="eyebrow">VISION CELL / DEMO-02</span>
              <h2>비전검사 설비</h2>
              <p>
                카메라·링 조명으로 검사하는 가상 설비입니다. 아래 수치는 반복
                시연이며 MES 실적에 저장되지 않습니다.
              </p>
            </div>
            <dl>
              <div>
                <dt>설비 상태</dt>
                <dd data-testid="vision-phase">
                  {fault ? "이상 정지" : !animated ? "일시정지" : vision.phase}
                </dd>
              </div>
              <div>
                <dt>최근 판정</dt>
                <dd>{vision.result}</dd>
              </div>
              <div>
                <dt>검사 수량</dt>
                <dd data-testid="vision-count">{vision.inspected}개</dd>
              </div>
              <div>
                <dt>불합격</dt>
                <dd>{vision.rejected}개</dd>
              </div>
            </dl>
            <dl className="vision-settings">
              <div>
                <dt>검사 주기 · 설정</dt>
                <dd>
                  6.0 <small>s</small>
                </dd>
              </div>
              <div>
                <dt>카메라 노출 · 설정</dt>
                <dd>
                  8.0 <small>ms</small>
                </dd>
              </div>
              <div>
                <dt>링 조명</dt>
                <dd>
                  {animated && !fault && vision.scanning ? "점등" : "대기"}
                </dd>
              </div>
              <div>
                <dt>합격 수량</dt>
                <dd>{vision.inspected - vision.rejected}개</dd>
              </div>
            </dl>
            <p className="vision-source">
              데이터 출처: 브라우저 시뮬레이션 · 설정값은 시연용 고정값
            </p>
            <div className="factory-actions">
              <button
                className="vision-overview"
                onClick={() => {
                  setExterior(false);
                  setWalking(false);
                  setView("ground");
                  setFocused(true);
                  setReset((n) => n + 1);
                }}
              >
                설비 가까이 보기
              </button>
              <button aria-pressed={fault} onClick={() => setFault(!fault)}>
                {fault ? "이상 해제" : "이상 상황 시연"}
              </button>
              <Link to="/mes">MES에서 업무 확인 →</Link>
            </div>
            <p>
              MES 링크는 업무 대시보드로 이동합니다. 시연 설비와 실제 업무
              레코드는 연결되지 않습니다.
            </p>
          </section>
        )}
      </div>
      <section className="factory-work-links" aria-label="공간과 업무 연결">
        <Link to="/mes">
          <span>01 / 생산 현장</span>
          <strong>MES · 생산 업무</strong>
          <small>작업지시부터 공정 실행·실적까지 →</small>
        </Link>
        <Link to="/erp">
          <span>02 / 사무실</span>
          <strong>ERP · 영업 업무</strong>
          <small>거래처·품목과 영업 업무 화면으로 →</small>
        </Link>
        <Link to="/fems">
          <span>03 / 설비 에너지</span>
          <strong>FEMS · 에너지 관리</strong>
          <small>계측값과 에너지 분석 화면으로 →</small>
        </Link>
      </section>
      <div className="factory-bottom">
        <section className="factory-process">
          <span className="eyebrow">PROCESS LINE / 1F</span>
          <h2>세 공정이 하나의 흐름으로</h2>
          <div className="factory-process-buttons">
            {stations.map((s, i) => (
              <button
                key={s.name}
                aria-pressed={selected === i}
                onClick={() => setSelected(i)}
              >
                {s.name}
                <span aria-hidden="true"> →</span>
              </button>
            ))}
          </div>
          <p aria-live="polite">
            {selected === null
              ? "설비 또는 공정 이름을 선택하세요. 제품의 이동과 직원의 점검 동작은 반복 시연입니다."
              : stations[selected].detail}
          </p>
        </section>
        <section className="factory-spaces">
          <h2>공간 안내</h2>
          <p>
            <strong>1층 현장사무실</strong> 노트북 작업자 1명, 바코드 프린터
          </p>
          <p>
            <strong>1층 생산 현장</strong> 설비 3대, 키오스크 3대, 비전검사
            장치, 순회 직원 1명
          </p>
          <p>
            <strong>2층 사무실</strong> 책상과 노트북, 근무 직원 2명
          </p>
        </section>
      </div>
    </div>
  );
}
