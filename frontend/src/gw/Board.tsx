import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { GwLink as Link } from "./common";
import {
  DataTable,
  EmptyState,
  DetailPanel,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
} from "../shared/components";
import {
  useGet,
  useSend,
  useRole,
  time,
  labels,
  companyPath,
  type Page,
  type Post,
} from "./common";
import { Events, RoleBar, Status } from "./ui";
import { Comments, Audience } from "./Collaboration";
export function Board() {
  const { person } = useRole();
  return <BoardSpace key={person} />;
}
function BoardSpace() {
  const { person, busy, companyId } = useRole();
  const [q, setQ] = useSearchParams();
  const [create, setCreate] = useState(false);
  const open = q.get("open");
  const offset = Math.max(0, Number(q.get("offset")) || 0);
  const query = new URLSearchParams(q);
  query.delete("open");
  if (!query.has("status")) query.set("status", "PUBLISHED");
  if (query.get("status") === "all") query.delete("status");
  query.set("limit", "20");
  query.set("offset", String(offset));
  if (person) query.set("personId", person);
  const list = useGet<Page<Post>>("/posts?" + query);
  const change = (k: string, v: string) => {
    const n = new URLSearchParams(q);
    if (v) n.set(k, v);
    else n.delete(k);
    if (k !== "offset") n.delete("offset");
    setQ(n);
  };
  return (
    <div className="page-fill">
      <PageTitle
        id="G-05"
        title="공지·자유 게시판"
        help="gw/g-05"
        actions={
          <button disabled={!person || busy} onClick={() => setCreate(true)}>
            새 글
          </button>
        }
      />
      <div className="split-view fill">
        <section className="fill" inert={!!busy}>
          {!open && !create && <RoleBar />}
          <div className="gw-filters">
            <Field
              label="글 검색"
              value={q.get("search") ?? ""}
              onChange={(e) => change("search", e.target.value)}
            />
            <label>
              게시판
              <select
                aria-label="게시판"
                value={q.get("boardKind") ?? ""}
                onChange={(e) => change("boardKind", e.target.value)}
              >
                <option value="">전체 게시판</option>
                <option value="NOTICE">공지</option>
                <option value="FREE">자유</option>
              </select>
            </label>
            <label>
              상태
              <select
                aria-label="상태"
                value={q.get("status") ?? "PUBLISHED"}
                onChange={(e) => change("status", e.target.value)}
              >
                {["PUBLISHED", "DRAFT", "WITHDRAWN", "all"].map((s) => (
                  <option key={s} value={s}>
                    {labels[s] ?? "전체"}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <input
                type="checkbox"
                disabled={!person}
                checked={q.get("mine") === "true"}
                onChange={(e) => change("mine", e.target.checked ? "true" : "")}
              />
              내 글만
            </label>
          </div>
          <ErrorNotice error={list.error} />
          {list.data ? (
            <DataTable
              rows={list.data.rows}
              columns={[
                { key: "postNo", label: "번호" },
                {
                  key: "title",
                  label: "제목",
                  render: (p) => (
                    <button
                      className="link-button"
                      onClick={() => change("open", p.id)}
                    >
                      {p.title}
                    </button>
                  ),
                },
                {
                  key: "boardKind",
                  label: "게시판",
                  render: (p) => labels[p.boardKind],
                },
                { key: "authorName", label: "작성 담당자" },
                {
                  key: "status",
                  label: "상태",
                  render: (p) => <Status value={p.status} />,
                },
                {
                  key: "publishedAt",
                  label: "게시 시각",
                  render: (p) => time(p.publishedAt),
                },
              ]}
              caption="게시글"
              offset={offset}
              limit={20}
              total={list.data.total}
              onPage={(n) => change("offset", String(n))}
              empty={
                <EmptyState
                  reason="조건에 맞는 게시글이 없습니다. 게시판·상태·검색어를 확인하세요."
                  to={companyPath("/gw/dashboard", companyId)}
                  action="GW 업무로 돌아가기"
                />
              }
            />
          ) : (
            !list.error && <Loading />
          )}
        </section>
        {create && (
          <PostEditor
            close={() => setCreate(false)}
            done={(p) => {
              setCreate(false);
              change("open", p.id);
              list.reload();
            }}
          />
        )}
        {open && !create && (
          <PostDetail
            key={open}
            id={open}
            close={() => change("open", "")}
            done={(p) => {
              change("open", p.id);
              list.reload();
            }}
          />
        )}
      </div>
    </div>
  );
}
function PostEditor({
  value,
  close,
  done,
}: {
  value?: Post;
  close: () => void;
  done: (p: Post) => void;
}) {
  const role = useRole();
  const { person } = role;
  const [kind, setKind] = useState(value?.boardKind ?? "FREE");
  const [title, setTitle] = useState(value?.title ?? "");
  const [body, setBody] = useState(value?.body ?? "");
  const [visibility, setVisibility] = useState(
    value?.visibility ?? "WORKSPACE",
  );
  const [org, setOrg] = useState(value?.audienceOrgId ?? "");
  const req = useSend();
  const guard = useDiscardGuard(true);
  async function submit(e: FormEvent) {
    e.preventDefault();
    const p = await req.send<Post>(
      "/posts" + (value ? "/" + value.id : ""),
      value ? "PATCH" : "POST",
      {
        actingPersonId: person,
        title,
        body,
        visibility,
        audienceOrgId: org || null,
        ...(value ? { expectedVersion: value.version } : { boardKind: kind }),
      },
    );
    if (p) done(p);
  }
  return (
    <FormPanel
      title={value ? "글 초안 편집" : "새 글"}
      wide
      guard={guard}
      onClose={() => {
        if (!req.pending) close();
      }}
      onSubmit={(e) => void submit(e)}
      actions={<button disabled={req.pending}>초안 저장</button>}
    >
      <RoleBar guard={guard} pending={req.pending} />
      <ErrorNotice error={req.error} />
      <fieldset disabled={req.pending}>
        {!value && (
          <label>
            게시판
            <select
              aria-label="게시판"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              <option value="FREE">자유</option>
              {(role.companyId === undefined ||
                role.roles?.includes("BOARD_PUBLISHER")) && (
                <option value="NOTICE">공지 (공지 게시 권한)</option>
              )}
            </select>
          </label>
        )}
        {kind === "NOTICE" && (
          <Audience
            visibility={visibility}
            org={org}
            onChange={(v, o) => {
              setVisibility(v);
              setOrg(o);
            }}
          />
        )}
        <Field
          label="제목"
          required
          maxLength={200}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <label>
          본문
          <textarea
            required
            maxLength={10000}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </label>
        <p className="muted">
          본문은 일반 텍스트입니다. 저장 후 상세에서 게시하세요. 게시한 글은 새
          정정 글로 수정합니다.
        </p>
      </fieldset>
    </FormPanel>
  );
}
function PostDetail({
  id,
  close,
  done,
}: {
  id: string;
  close: () => void;
  done: (p: Post) => void;
}) {
  const { person } = useRole();
  const query = useGet<Post>(
    "/posts/" + id + (person ? "?personId=" + person : ""),
  );
  const req = useSend();
  const [edit, setEdit] = useState(false);
  const [action, setAction] = useState("");
  const [reason, setReason] = useState("");
  const [commentDirty, setCommentDirty] = useState(false);
  const guard = useDiscardGuard(!!action || !!reason || commentDirty);
  const p = query.data;
  const saved = (v: Post) => {
    query.setData(v);
    setEdit(false);
    setAction("");
    setReason("");
    done(v);
  };
  async function commit(e: FormEvent) {
    e.preventDefault();
    if (!p) return;
    const result = await req.send<Post>(`/posts/${id}/${action}`, "POST", {
      actingPersonId: person,
      expectedVersion: p.version,
      ...(action === "withdraw" ? { reason } : {}),
    });
    if (result) saved(result);
  }
  if (edit && p)
    return <PostEditor value={p} close={() => setEdit(false)} done={saved} />;
  return (
    <DetailPanel
      title={p?.postNo ?? "게시글 상세"}
      wide
      guard={guard}
      onClose={() => {
        if (!req.pending) close();
      }}
    >
      <RoleBar guard={guard} pending={req.pending} />
      <ErrorNotice error={query.error} />
      <ErrorNotice error={req.error} />
      <button
        disabled={req.pending}
        onClick={() =>
          guard.guard(() => {
            setAction("");
            setReason("");
            query.reload();
          })
        }
      >
        서버 상태 다시 확인
      </button>
      {p ? (
        <>
          <h2>
            {p.title} <Status value={p.status} />
          </h2>
          <p>
            {labels[p.boardKind]} · {p.authorName} · {time(p.publishedAt)}
          </p>
          <p className="gw-body">{p.body}</p>
          {p.withdrawReason && <p>철회 사유: {p.withdrawReason}</p>}
          <div className="gw-actions">
            {p.availableActions.map((a) => (
              <button
                key={a}
                disabled={req.pending}
                onClick={() => (a === "edit" ? setEdit(true) : setAction(a))}
              >
                {labels[a]}
              </button>
            ))}
          </div>
          {action && (
            <form onSubmit={(e) => void commit(e)}>
              <h3>{labels[action]} 확인</h3>
              <p>
                {p.postNo} · {p.title} · {p.authorName}. 기존 게시글과 이력은
                보존됩니다.
              </p>
              {action === "withdraw" && (
                <Field
                  label="철회 사유"
                  required
                  minLength={2}
                  maxLength={500}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              )}
              <button disabled={req.pending}>확정</button>{" "}
              <button
                type="button"
                disabled={req.pending}
                onClick={() => {
                  setAction("");
                  setReason("");
                }}
              >
                취소
              </button>
            </form>
          )}
          <div className="gw-actions">
            {p.previousPostId && (
              <Link to={"/gw/board?open=" + p.previousPostId}>이전 글</Link>
            )}
            {p.successor && (
              <Link to={"/gw/board?open=" + p.successor.id}>
                정정 {p.successor.postNo}
              </Link>
            )}
          </div>
          <Events rows={p.events} />
          {p.status !== "DRAFT" && (
            <Comments kind="POST" id={p.id} onDirty={setCommentDirty} />
          )}
        </>
      ) : (
        !query.error && <Loading />
      )}
    </DetailPanel>
  );
}
