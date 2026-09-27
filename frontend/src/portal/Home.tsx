// P-02 앱 런처: 정보는 필요할 때 열고, 첫 화면은 세 솔루션에 집중한다.
import "./Home.css";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, type Module } from "../shared/api";
import { Badge, ErrorNotice, Loading } from "../shared/components";
export const solutions = [
  {
    key: "mes",
    name: "생산관리",
    description: "계획에서 실적, 패킹과 입고까지",
    to: "/mes",
  },
  {
    key: "erp",
    name: "경영관리",
    description: "수주에서 출하, 매출과 수금까지",
    to: "/erp",
  },
  {
    key: "fems",
    name: "에너지관리",
    description: "계측에서 원단위, 목표와 요금까지",
    to: "/fems",
  },
] as const;
// 사용자 제공 Figma 시제품의 SVG 모양을 홈에만 적용한다.
function AppIcon({ kind }: { kind: (typeof solutions)[number]["key"] }) {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      {kind === "mes" ? (
        <>
          <path d="M8 20 24 10 40 20V40H8Z" fill="#405653" />
          <path d="M18 28h12v12H18z" fill="var(--surface)" />
          <path
            d="M10 24h6v4h-6zm22 0h6v4h-6z"
            fill="var(--surface)"
            opacity=".7"
          />
        </>
      ) : kind === "erp" ? (
        <>
          <rect x="6" y="6" width="16" height="16" rx="3" fill="#596577" />
          <rect x="26" y="6" width="16" height="16" rx="3" fill="#a0a6af" />
          <rect x="6" y="26" width="16" height="16" rx="3" fill="#a0a6af" />
          <rect x="26" y="26" width="16" height="16" rx="3" fill="#a69574" />
        </>
      ) : (
        <path d="m24 4-10 24h8l-4 16 16-24h-8z" fill="#a68951" />
      )}
    </svg>
  );
}
export function Home() {
  const { session, fail } = useSession();
  const [modules, setModules] = useState<Module[]>();
  const [error, setError] = useState<unknown>();
  const [detail, setDetail] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    setError(undefined);
    api<Module[]>("/workspace/modules")
      .then((r) => {
        if (active) setModules(r.data);
      })
      .catch((e) => {
        if (active) {
          setError(e);
          fail(e);
        }
      });
    return () => {
      active = false;
    };
  }, [session?.generationId, reload]);
  return (
    <div className="home-launcher">
      <div className="home-hero">
        <div>
          <span className="home-eyebrow">YOUR WORKSPACE</span>
          <h1>제조 현장의 세 시스템</h1>
          <p>하나의 공간에서 만나는 세 가지 독립 솔루션</p>
        </div>
        <div className="home-context">
          <Link to="/workspace" className="home-space">
            <span>
              {session?.actorKind === "GUEST" ? "게스트 공간" : "내 공간"}
              <span aria-hidden="true"> ↗</span>
            </span>
            <small>
              공간 {session?.workspaceId} · 데이터 세대 {session?.generationId}
            </small>
          </Link>
          <Link to="/help/portal/p-02" className="home-help">
            런처 도움말
          </Link>
        </div>
      </div>
      <Link to="/flow" className="home-flow">
        <div>
          <span className="home-eyebrow">THE BIG PICTURE</span>
          <h2>세 시스템은 어떻게 이어지는가</h2>
          <p>판매계획에서 생산·출하·매출까지 전체 흐름 보기</p>
        </div>
        <span className="home-flow-action">
          전체 흐름 보기 <span aria-hidden="true">→</span>
        </span>
      </Link>
      <section aria-label="솔루션 둘러보기" className="home-solutions">
        <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
        {!modules && !error ? (
          <Loading />
        ) : (
          modules && (
            <div className="launcher-grid">
              {solutions.map((s) => {
                const enabled = modules.some(
                  (m) => m.moduleKey === s.key && m.enabled,
                );
                const expanded = detail === s.key;
                const descriptionId = `launcher-description-${s.key}`;
                return (
                  <div
                    key={s.key}
                    className="launcher-item"
                    onPointerEnter={(e) => {
                      if (e.pointerType === "mouse") setDetail(s.key);
                    }}
                    onPointerLeave={(e) => {
                      if (!e.currentTarget.contains(document.activeElement))
                        setDetail(null);
                    }}
                    onBlur={(e) => {
                      if (!e.currentTarget.contains(e.relatedTarget))
                        setDetail(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") {
                        e.stopPropagation();
                        setDetail(null);
                      }
                    }}
                  >
                    <Link
                      to={enabled ? s.to : "/workspace"}
                      className={`launcher-app ${enabled ? "" : "disabled"}`}
                      aria-describedby={descriptionId}
                      onFocus={() => setDetail(s.key)}
                    >
                      <span className="launcher-icon">
                        <AppIcon kind={s.key} />
                      </span>
                      <h2>
                        {s.key.toUpperCase()} <span>{s.name}</span>
                      </h2>
                    </Link>
                    <button
                      type="button"
                      className="launcher-info"
                      aria-label={`${s.key.toUpperCase()} 상세 안내`}
                      aria-expanded={expanded}
                      aria-controls={descriptionId}
                      onClick={() => setDetail(expanded ? null : s.key)}
                    >
                      i
                    </button>
                    <div
                      id={descriptionId}
                      className="launcher-detail"
                      hidden={!expanded}
                    >
                      <Badge tone={enabled ? "normal" : "warning"}>
                        {enabled ? "사용 중" : "사용 꺼짐"}
                      </Badge>
                      <p>{s.description}</p>
                      <span className="launcher-destination">
                        {enabled ? "앱 열기" : "내 공간에서 켜기"}{" "}
                        <span aria-hidden="true">→</span>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )
        )}
      </section>
    </div>
  );
}
