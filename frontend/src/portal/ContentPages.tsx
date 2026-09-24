// P-03 전체 업무 흐름 · P-04 설명 카드 · P-05 도움말
import { Link, useParams } from "react-router-dom";
import { PageTitle, NotFound } from "../shared/components";
import { cards, help, MarkdownContent, contentTitle } from "../shared/content";
import flow from "../../../content/flow-map.json";
export function FlowMap() {
  return (
    <>
      <PageTitle
        id="P-03"
        title="전체 업무 흐름"
        subtitle="판매계획에서 시작하는 MTS(재고생산) 흐름"
      />
      <p className="flow-legend">
        <span>━ 구현 범위 · 업무 안내 연결</span>
        <span>┄ 설명 카드 범위</span>
      </p>
      <div className="flow-map">
        {flow.nodes.map((n, index) => (
          <section
            key={n.id}
            className={`flow-node ${n.kind === "card" ? "dashed" : ""}`}
            id={`node-${n.id}`}
          >
            <Link
              to={
                n.kind === "card" ? `/cards/${n.module}` : `/help/${n.helpKey}`
              }
            >
              <span className="eyebrow">
                {String(index + 1).padStart(2, "0")} / {n.module.toUpperCase()}
              </span>
              <h2>{n.label}</h2>
              <small>{n.kind === "card" ? "설명 카드" : "업무 안내"} ↗</small>
            </Link>
            <ul aria-label={`${n.label} 연결`}>
              {flow.edges
                .filter((e) => e.from === n.id)
                .map((e) => (
                  <li key={e.to} className={e.kind === "card" ? "dashed" : ""}>
                    <a href={`#node-${e.to}`}>
                      → {flow.nodes.find((target) => target.id === e.to)?.label}
                    </a>
                    <span>{e.label}</span>
                  </li>
                ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
export function Cards() {
  const { card = "qms" } = useParams();
  if (!["qms", "wms", "bems", "scm"].includes(card)) return <NotFound />;
  return (
    <>
      <PageTitle
        id="P-04"
        title="설명 카드"
        subtitle="설계 범위와 시스템의 연결 지점"
      />
      <nav className="tabs" aria-label="설명 카드">
        {["qms", "wms", "bems", "scm"].map((key) => (
          <Link
            aria-current={key === card ? "page" : undefined}
            to={`/cards/${key}`}
            key={key}
          >
            {key.toUpperCase()}
          </Link>
        ))}
      </nav>
      <div className="panel">
        {card === "scm" ? (
          <h2>SCM 공급망관리</h2>
        ) : (
          <MarkdownContent body={cards[card]} />
        )}
      </div>
    </>
  );
}
export function Help() {
  const { "*": key } = useParams();
  if (key && !Object.hasOwn(help, key)) return <NotFound />;
  return (
    <>
      <PageTitle
        id="P-05"
        title="도움말"
        subtitle="화면별 업무 안내와 공통 이용 규칙"
      />
      {key ? (
        <>
          <Link className="back-link" to="/help">
            ← 도움말 전체 목록
          </Link>
          <div className="panel">
            <MarkdownContent body={help[key]} />
          </div>
        </>
      ) : (
        <>
          <Link className="common-help" to="/help/common">
            공통 이용 안내 <span>오류 · 세션 만료 · 네트워크 · 접근성 →</span>
          </Link>
          <div className="help-grid">
            {[
              ["portal", "포털"],
              ["mes", "MES 생산관리"],
              ["erp", "ERP 경영관리"],
              ["fems", "FEMS 에너지관리"],
            ].map(([prefix, title]) => (
              <section key={prefix} className="panel">
                <h2>{title}</h2>
                <ul>
                  {Object.entries(help)
                    .filter(([k]) => k.startsWith(prefix + "/"))
                    .map(([k, body]) => (
                      <li key={k}>
                        <Link to={`/help/${k}`}>
                          <span>{k.split("/")[1].toUpperCase()}</span>
                          {contentTitle(body)}
                        </Link>
                      </li>
                    ))}
                </ul>
              </section>
            ))}
          </div>
        </>
      )}
    </>
  );
}
