// P-02 앱 런처: 정보는 필요할 때 열고, 첫 화면은 운영 중인 솔루션에 집중한다.
// 17개가 되어도 읽히도록 분야별 묶음으로 보인다(ROADMAP-01 §4). 운영 중인 솔루션만 타일이고, 빈 묶음은 숨긴다.
import "./Home.css";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, type Module } from "../shared/api";
import { Badge, ErrorNotice, Loading } from "../shared/components";
import systems from "../../../content/systems.json";
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
  {
    key: "qms",
    name: "품질관리",
    description: "검사 기준에서 판정, 보류와 처분까지",
    to: "/qms",
  },
  {
    key: "wms",
    name: "창고관리",
    description: "창고·위치 재고 원장, 입출고 반영과 조정까지",
    to: "/wms",
  },
  {
    key: "bems",
    name: "건물관리",
    description: "공용 에너지 분해, 공조 운전·설정값·경보까지",
    to: "/bems",
  },
  {
    key: "spc",
    name: "공정관리",
    description: "측정 부분군에서 관리도, 이상 조치와 공정능력까지",
    to: "/spc",
  },
] as const;
/** 솔루션 수를 목록 길이에서 만든다 — 솔루션이 늘어도 문구를 고치지 않는다. */
const COUNTS = [
  "",
  "한",
  "두",
  "세",
  "네",
  "다섯",
  "여섯",
  "일곱",
  "여덟",
  "아홉",
  "열",
  "열한",
  "열두",
  "열세",
  "열네",
  "열다섯",
  "열여섯",
  "열일곱",
];
export const solutionCount = COUNTS[solutions.length];
const fieldOf = (key: string) =>
  systems.systems.find((s) => s.id === key)?.field ?? "";
export const solutionGroups = systems.fields
  .map((field) => ({
    field,
    items: solutions.filter((s) => fieldOf(s.key) === field),
  }))
  .filter((g) => g.items.length > 0);
const planned = systems.systems.filter((s) => s.status === "planned").length;
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
      ) : kind === "fems" ? (
        <path d="m24 4-10 24h8l-4 16 16-24h-8z" fill="#a68951" />
      ) : kind === "bems" ? (
        <>
          <path d="M8 42V10h20v32Z" fill="#4f6272" />
          <path d="M28 42V20h12v22Z" fill="#a0a6af" />
          <path
            d="M13 16h4m3 0h4M13 23h4m3 0h4M13 30h4m3 0h4"
            stroke="var(--surface)"
            strokeWidth="2.5"
          />
          <path
            d="M31 27c2-2 4 2 6 0m-6 6c2-2 4 2 6 0"
            fill="none"
            stroke="var(--surface)"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </>
      ) : kind === "spc" ? (
        <>
          <rect x="6" y="6" width="36" height="36" rx="4" fill="#4d5d6c" />
          <path
            d="M10 16h28M10 32h28"
            stroke="#a0a6af"
            strokeWidth="1.8"
            strokeDasharray="3 3"
          />
          <path
            d="m11 28 6-5 5 3 6-8 5 3 4-4"
            fill="none"
            stroke="var(--surface)"
            strokeWidth="2.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      ) : kind === "wms" ? (
        <>
          <path d="M6 42V18L24 8l18 10v24h-6V24H12v18Z" fill="#6b6f5c" />
          <rect x="15" y="27" width="8" height="7" fill="#a0a6af" />
          <rect x="25" y="27" width="8" height="7" fill="#a69574" />
          <rect x="20" y="35" width="8" height="7" fill="#a0a6af" />
        </>
      ) : (
        <>
          <path
            d="M24 5 40 11v12c0 10-7 17-16 20C15 40 8 33 8 23V11Z"
            fill="#5d6f7e"
          />
          <path
            d="m17 24 5 5 9-10"
            fill="none"
            stroke="var(--surface)"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
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
          <h1>제조 현장의 올인원 시스템</h1>
          <p>하나의 공간에서 만나는 {solutionCount} 가지 독립 솔루션</p>
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
          <h2>{solutionCount} 시스템은 어떻게 이어지는가</h2>
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
            <div className="home-groups">
              {solutionGroups.map((group) => (
                <section
                  key={group.field}
                  className="home-group"
                  aria-label={group.field}
                >
                  <h2 className="home-group-title">{group.field}</h2>
                  <div className="launcher-grid">
                    {group.items.map((s) => {
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
                            if (
                              !e.currentTarget.contains(document.activeElement)
                            )
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
                            <h3>
                              {s.key.toUpperCase()} <span>{s.name}</span>
                            </h3>
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
                </section>
              ))}
            </div>
          )
        )}
      </section>
      <section className="excluded home-roadmap">
        <span className="eyebrow">ROADMAP</span>
        <h2>앞으로 만들 것</h2>
        <p>
          제조 IT 카탈로그의 나머지 {planned}개 시스템을 하나씩 만듭니다. 순서와
          연결 지점은 계층 아키텍처에서 볼 수 있습니다.
        </p>
        <div>
          <Link to="/flow?view=arch">계층 아키텍처에서 보기 →</Link>
        </div>
      </section>
    </div>
  );
}
