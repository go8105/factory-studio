// P-02 앱 런처
import "./Home.css";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, type Module } from "../shared/api";
import {
  Badge,
  ErrorNotice,
  LineIcon,
  Loading,
  PageTitle,
} from "../shared/components";
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
];
export function Home() {
  const { session, fail } = useSession();
  const [modules, setModules] = useState<Module[]>();
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    let active = true;
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
  }, [session?.generationId]);
  return (
    <>
      <PageTitle
        id="P-02"
        title="제조 현장의 세 시스템"
        subtitle="하나의 공간에서 만나는 세 가지 독립 솔루션"
      />
      <div className="workspace-strip">
        <Badge>
          {session?.actorKind === "GUEST" ? "게스트 공간" : "내 공간"}
        </Badge>
        <span>
          공간 {session?.workspaceId} · 데이터 세대 {session?.generationId}
        </span>
        <Link to="/workspace">공간 관리 →</Link>
      </div>
      <Link to="/flow" className="flow-banner">
        <div>
          <span className="eyebrow">THE BIG PICTURE</span>
          <h2>세 시스템은 어떻게 이어지는가</h2>
          <p>판매계획에서 생산·출하·매출까지 전체 흐름 보기</p>
        </div>
        <span className="big-arrow" aria-hidden="true">
          ↗
        </span>
      </Link>
      <div className="section-heading">
        <h2>솔루션 둘러보기</h2>
        <span>네 솔루션 모두 화면으로 연결됩니다</span>
      </div>
      <ErrorNotice error={error} />
      {!modules ? (
        <Loading />
      ) : (
        <div className="launcher-grid">
          {solutions.map((s) => {
            const enabled = modules.some(
              (m) => m.moduleKey === s.key && m.enabled,
            );
            return (
              <Link
                key={s.key}
                to={enabled ? s.to : "/workspace"}
                className={`launcher-app ${enabled ? "" : "disabled"}`}
              >
                <span className="launcher-icon">
                  <LineIcon kind={s.key} />
                </span>
                <h3>
                  {s.key.toUpperCase()} <span>{s.name}</span>
                </h3>
                <p>{s.description}</p>
                <div className="launcher-status">
                  <Badge tone={enabled ? "normal" : "warning"}>
                    {enabled ? "사용 중" : "사용 꺼짐"}
                  </Badge>
                  <span>{enabled ? "업무 안내" : "내 공간에서 켜기"} →</span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
      <section className="excluded">
        <span className="eyebrow">SCOPE & BOUNDARIES</span>
        <h2>아직 만들지 않은 것</h2>
        <p>
          설계 범위에서 의도적으로 제외했습니다. 이유와 연결 지점을 확인해
          보세요.
        </p>
        <div>
          {["WMS 물류", "BEMS 건물", "SCM 공급망"].map((s) => (
            <Link key={s} to={`/cards/${s.split(" ")[0].toLowerCase()}`}>
              {s} →
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
