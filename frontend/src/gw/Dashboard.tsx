import { GwLink as Link } from "./common";
import { ErrorNotice, Loading, PageTitle } from "../shared/components";
import { useGet, useRole, type Document, type Post } from "./common";
import { NoRole, RoleBar, Status } from "./ui";
type Summary = {
  needsPerson: boolean;
  drafts: number;
  inReview: number;
  pending: number;
  closed: number;
  recentDocuments: Document[];
  recentPosts: Post[];
};
export function Dashboard() {
  const { person } = useRole();
  const result = useGet<Summary>(
    person ? "/dashboard?personId=" + person : null,
  );
  const d = result.data;
  return (
    <>
      <PageTitle
        id="G-01"
        title="업무 현황"
        help="gw/g-01"
        subtitle="기안 → 병렬 결재·합의·위임 → 기록 보관"
      />
      <RoleBar />
      {!person ? (
        <NoRole />
      ) : (
        <>
          <ErrorNotice error={result.error} />
          {!d && !result.error ? (
            <Loading />
          ) : (
            d && (
              <>
                <div className="gw-kpis">
                  {[
                    ["내 초안", d.drafts, "/gw/drafts?status=DRAFT"],
                    ["내 진행", d.inReview, "/gw/drafts?status=IN_REVIEW"],
                    ["현재 결재 대기", d.pending, "/gw/pending"],
                    ["내 기안 종결", d.closed, "/gw/drafts"],
                  ].map(([name, count, path]) => (
                    <Link className="card" key={name} to={String(path)}>
                      <span>{name}</span>
                      <strong>{count}</strong>
                    </Link>
                  ))}
                </div>
                <section className="card">
                  <h2>최근 종결 문서</h2>
                  {d.recentDocuments.length ? (
                    d.recentDocuments.map((x) => (
                      <p key={x.id}>
                        <Link to={"/gw/documents?open=" + x.id}>
                          {x.documentNo} · {x.title}
                        </Link>{" "}
                        <Status value={x.status} />
                      </p>
                    ))
                  ) : (
                    <p>
                      종결된 문서가 없습니다. 기안함에서 새 기안을 시작하세요.
                    </p>
                  )}
                </section>
                <section className="card">
                  <h2>최근 게시글</h2>
                  {d.recentPosts.length ? (
                    d.recentPosts.map((p) => (
                      <p key={p.id}>
                        <Link to={"/gw/board?open=" + p.id}>{p.title}</Link>
                      </p>
                    ))
                  ) : (
                    <p>게시글이 없습니다.</p>
                  )}
                </section>
              </>
            )
          )}
        </>
      )}
    </>
  );
}
