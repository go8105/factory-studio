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
    if (walking) stage.current?.focus();
  }, [walking, reset]);
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
    <div className="factory-page">
      <div className="factory-heading">
        <div>
          <span className="eyebrow">FACTORY STUDIO / SPATIAL TOUR</span>
          <h1>공장, 한눈에 그리고 한 걸음씩</h1>
          <p>사무실에서 생산 현장까지, 제조가 이루어지는 공간을 둘러보세요.</p>
        </div>
        <span className="factory-demo">
          3D 합성 시연 · 실시간 설비 정보 아님
        </span>
      </div>
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
              position.current = {
                ...(view === "office" ? OFFICE_START : START),
              };
              setReset((n) => n + 1);
            }}
          >
            시점 초기화
          </button>
        </div>
      </div>
      <p id="factory-controls" className="factory-instructions">
        {walking
          ? "노란 조끼가 나입니다. 화면을 선택한 뒤 WASD·방향키 또는 이동 버튼으로 걸어보세요. 계단으로 2층 이동 · Esc 조감도"
          : "마우스로 드래그하여 회전 · 휠로 확대 / 축소 · 터치로 회전 · 설비를 선택하면 공정 설명"}
      </p>
      <div
        ref={stage}
        className={`factory-stage${exterior ? " factory-exterior" : ""}`}
        tabIndex={0}
        role="region"
        aria-label="3D 공장 탐색"
        aria-describedby="factory-controls"
        onKeyDown={(e) => {
          if (!walking || e.target !== stage.current) return;
          if (keyMap[e.code]) {
            e.preventDefault();
            keys.current.add(keyMap[e.code]);
          }
          if (e.code === "Escape") setWalking(false);
        }}
        onBlur={() => keys.current.clear()}
        onPointerDown={(e) => {
          if (e.target instanceof HTMLCanvasElement && walking)
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
              camera={{ position: [23, 22, 28], fov: 43, near: 0.1, far: 150 }}
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
          {exterior
            ? "EXTERIOR · 공장 외관"
            : walking
              ? "WALK · 자유 이동"
              : "CUTAWAY · 내부 둘러보기"}
        </div>
        {walking && (
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
      {selected === 1 && (
        <section className="vision-panel" aria-label="비전검사 설비 상세">
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
          <div className="factory-actions">
            <button
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
