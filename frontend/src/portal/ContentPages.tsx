// P-03 전체 업무 흐름 · P-04 설명 카드 · P-05 참고 문서(DOC-01)
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { PageTitle, NotFound } from "../shared/components";
import { cards, help, MarkdownContent, contentTitle } from "../shared/content";
import flow from "../../../content/flow-map.json";
import {
  docSections,
  headings,
  popular,
  screenPath,
  searchDocs,
  sectionOf,
  slug,
} from "./docs";
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
  const { card = "wms" } = useParams();
  if (!["wms", "bems", "scm"].includes(card)) return <NotFound />;
  return (
    <>
      <PageTitle
        id="P-04"
        title="설명 카드"
        subtitle="설계 범위와 시스템의 연결 지점"
      />
      <nav className="tabs" aria-label="설명 카드">
        {["wms", "bems", "scm"].map((key) => (
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
  return key ? <DocPage docKey={key} /> : <DocHome />;
}
// 첫 화면에서는 입력하는 대로 거르고, 문서 화면에서는 Enter로 첫 화면 검색으로 간다.
function DocSearch({ live = false }: { live?: boolean }) {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const q = params.get("q") ?? "";
  return (
    <form
      role="search"
      className="doc-search"
      onSubmit={(e) => {
        e.preventDefault();
        const value = String(new FormData(e.currentTarget).get("q") ?? "");
        navigate(`/help?q=${encodeURIComponent(value.trim())}`);
      }}
    >
      <input
        type="search"
        name="q"
        aria-label="문서 검색"
        placeholder="무엇을 찾으세요? 예: 소명, 원단위, LOT"
        {...(live
          ? {
              value: q,
              onChange: (e) =>
                setParams(e.target.value ? { q: e.target.value } : {}, {
                  replace: true,
                }),
            }
          : {})}
      />
    </form>
  );
}
const docLabel = (key: string) => {
  const id = key.split("/")[1] ?? "";
  return /^[pmef]-\d+$/.test(id) ? id.toUpperCase() : undefined;
};
function DocLink({ k, current }: { k: string; current?: boolean }) {
  const id = docLabel(k);
  return (
    <Link to={`/help/${k}`} aria-current={current ? "page" : undefined}>
      {id && <span>{id}</span>}
      {contentTitle(help[k])}
    </Link>
  );
}
function DocHome() {
  const [params] = useSearchParams();
  const q = params.get("q")?.trim() ?? "";
  const sections = docSections(help);
  const results = searchDocs(help, q);
  return (
    <>
      <header className="doc-hero">
        <span className="page-id">P-05</span>
        <h1>참고 문서</h1>
        <p>이 시스템을 무엇으로, 왜 이렇게 만들었는가</p>
      </header>
      <DocSearch live />
      {q ? (
        <section className="panel doc-results" aria-label="검색 결과">
          <h2>
            ‘{q}’ 검색 결과 {results.length}건
          </h2>
          {results.length ? (
            <ul>
              {results.map((r) => (
                <li key={r.key}>
                  <DocLink k={r.key} />
                  <small>{sectionOf(sections, r.key)?.title}</small>
                  {r.snippet && <p>{r.snippet}</p>}
                </li>
              ))}
            </ul>
          ) : (
            <p>일치하는 문서가 없습니다. 띄어쓰기를 바꿔 보세요.</p>
          )}
        </section>
      ) : (
        <div className="doc-sections">
          {sections.map((s) => {
            const keys = s.groups.flatMap((g) => g.keys);
            const picks = [
              ...popular.filter((k) => keys.includes(k)),
              ...keys.filter((k) => !popular.includes(k)),
            ].slice(0, 4);
            const solutions = [...new Set(s.groups.map((g) => g.solution))];
            return (
              <section key={s.key} aria-labelledby={`doc-${s.key}`}>
                <h2 id={`doc-${s.key}`}>{s.title}</h2>
                <p>{s.summary}</p>
                {s.key === "reference" && (
                  <p className="doc-solutions">
                    {solutions.map((name) => {
                      const own = s.groups
                        .filter((g) => g.solution === name)
                        .flatMap((g) => g.keys);
                      return (
                        <Link key={name} to={`/help/${own[0]}`}>
                          {name} <span>{own.length}</span>
                        </Link>
                      );
                    })}
                  </p>
                )}
                <small>많이 찾는 문서</small>
                <ul>
                  {picks.map((k) => (
                    <li key={k}>
                      <DocLink k={k} />
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}
function DocPage({ docKey }: { docKey: string }) {
  const sections = docSections(help);
  const section = sectionOf(sections, docKey);
  const order = section?.groups.flatMap((g) => g.keys) ?? [docKey];
  const index = order.indexOf(docKey);
  const [prev, next] = [order[index - 1], order[index + 1]];
  const toc = headings(help[docKey]);
  const path = screenPath(docKey);
  const wide =
    typeof matchMedia === "function"
      ? matchMedia("(min-width: 801px)").matches
      : true;
  return (
    <div className="doc-layout">
      <aside className="doc-tree">
        <DocSearch />
        <details open={wide}>
          <summary>문서 목록</summary>
          <nav aria-label="문서 목록">
            {sections.map((s) => (
              <div key={s.key}>
                <h2>{s.title}</h2>
                {s.key === "reference" ? (
                  [...new Set(s.groups.map((g) => g.solution))].map((name) => {
                    const groups = s.groups.filter((g) => g.solution === name);
                    return (
                      <details
                        key={name}
                        open={groups.some((g) => g.keys.includes(docKey))}
                      >
                        <summary>{name}</summary>
                        {groups.map((g) => (
                          <div key={g.title}>
                            {g.title !== name && <h3>{g.title}</h3>}
                            <ul>
                              {g.keys.map((k) => (
                                <li key={k}>
                                  <DocLink k={k} current={k === docKey} />
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </details>
                    );
                  })
                ) : (
                  <ul>
                    {s.groups[0].keys.map((k) => (
                      <li key={k}>
                        <DocLink k={k} current={k === docKey} />
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </nav>
        </details>
      </aside>
      <div className="doc-body">
        <nav className="doc-crumbs" aria-label="현재 위치">
          <Link to="/help">참고 문서</Link>
          {section && <span>{section.title}</span>}
          <span aria-current="page">{contentTitle(help[docKey])}</span>
        </nav>
        {path && (
          <Link className="button secondary doc-open" to={path}>
            이 화면 열기 →
          </Link>
        )}
        <div className="panel">
          <MarkdownContent body={help[docKey]} />
        </div>
        <nav className="doc-pager" aria-label="이전·다음 문서">
          {prev ? (
            <Link to={`/help/${prev}`} rel="prev">
              <small>← 이전</small>
              {contentTitle(help[prev])}
            </Link>
          ) : (
            <span />
          )}
          {next && (
            <Link to={`/help/${next}`} rel="next">
              <small>다음 →</small>
              {contentTitle(help[next])}
            </Link>
          )}
        </nav>
      </div>
      {toc.length > 1 && (
        <nav className="doc-toc" aria-label="이 문서 목차">
          <small>이 문서 목차</small>
          <ul>
            {toc.map((h) => (
              <li key={h}>
                <a href={`#${slug(h)}`}>{h.replace(/[*`]/g, "")}</a>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </div>
  );
}
