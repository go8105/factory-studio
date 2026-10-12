import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useSession } from "../app/session";
import { api, MutationKeys } from "../shared/api";
import { MenuIcon } from "../shared/MenuIcon";
import { ErrorNotice } from "../shared/components";
import "./Projects.css";
import { Link, useSearchParams } from "react-router-dom";

type Member = { id: number; name: string; active: boolean; role: string };
type Board = {
  id: number;
  name: string;
  description: string;
  template: string;
  version: number;
  archived_at: string | null;
};
type Column = {
  id: number;
  name: string;
  kind: string;
  position: number;
  width: number;
  options: { labels?: string[] };
  builtin_key?: string | null;
  version: number;
  archived_at: string | null;
  deleted_at: string | null;
};
type Cell = {
  id: number;
  task_id: number;
  column_id: number;
  value: unknown;
  version: number;
};
type Group = {
  archived_at?: string | null;
  deleted_at?: string | null;
  id: number;
  name: string;
  color: string;
  position: number;
  version: number;
};
type Task = {
  id: number;
  board_id: number;
  group_id: number;
  parent_id: number | null;
  title: string;
  description: string;
  status: string;
  priority: string;
  starts_on: string | null;
  ends_on: string | null;
  progress: number;
  position: number;
  version: number;
  archived_at: string | null;
  aggregate?: boolean;
  assignees: { user_id: number; display_name: string; active: boolean }[];
  board_name?: string;
  overdue?: boolean;
};
type Preference = {
  view: string;
  search: string;
  status: string;
  mine: boolean;
  sort: string;
  hidden: string[];
  columns?: string[];
};
type Overview = {
  company: { id: number; name: string; timezone: string };
  userId: number;
  companyOwner: boolean;
  members: Member[];
  boards: Board[];
  favorites: number[];
  allowCreate: boolean;
  board?: Board;
  role?: string;
  columns?: Column[];
  cells?: Cell[];
  groups?: Group[];
  tasks?: Task[];
  preference?: { settings: Preference }[];
  boardMembers?: { user_id: number; role: string }[];
  nextOffset?: number | null;
};
type Detail = {
  comments: {
    id: number;
    user_id: number;
    body: string;
    version: number;
    deleted_at: string | null;
    updated_at: string | null;
  }[];
  events: { id: number; action: string; created_at: string; user_id: number }[];
};
const states: Record<string, string> = {
  WAITING: "대기",
  WORKING: "진행 중",
  REVIEW: "검토",
  BLOCKED: "보류",
  DONE: "완료",
  CANCELLED: "취소",
};
const priorities: Record<string, string> = {
  LOW: "낮음",
  NORMAL: "보통",
  HIGH: "높음",
  URGENT: "긴급",
};
const initial: Preference = {
  view: "table",
  search: "",
  status: "",
  mine: false,
  sort: "position",
  hidden: ["priority"],
};
const columnLabels: Record<string, string> = {
  assignees: "담당자",
  status: "상태",
  dates: "일정",
  progress: "진행률",
  priority: "중요도",
};
const defaultColumns = Object.keys(columnLabels);
const prefix = "/api/v1/flow";
function payload(t: Task) {
  return {
    boardId: t.board_id,
    id: t.id,
    version: t.version,
    groupId: t.group_id,
    parentId: t.parent_id,
    title: t.title,
    description: t.description,
    status: t.status,
    priority: t.priority,
    startsOn: t.starts_on,
    endsOn: t.ends_on,
    progress: t.progress,
    position: t.position,
    archived: !!t.archived_at,
    assignees: t.assignees.map((a) => a.user_id),
  };
}
export function Projects({ myTasks = false }: { myTasks?: boolean }) {
  const { session } = useSession();
  const [query, setQuery] = useSearchParams();
  const requestedCompany = Number(query.get("companyId"));
  const requestedBoard = Number(query.get("boardId"));
  const [companies, setCompanies] = useState<{ id: number; name: string }[]>(
    [],
  );
  const [cid, setCid] = useState<number>();
  const [bid, setBid] = useState<number>();
  const [data, setData] = useState<Overview>();
  const [mineTasks, setMineTasks] = useState<Task[]>([]);
  const [error, setError] = useState<unknown>();
  const [pending, setPending] = useState(false);
  const [pref, setPref] = useState(initial);
  const [selected, setSelected] = useState<Task>();
  const [detail, setDetail] = useState<Detail>();
  const [comment, setComment] = useState("");
  const [collapsed, setCollapsed] = useState<number[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [createBoard, setCreateBoard] = useState(false);
  const [boardName, setBoardName] = useState("");
  const [template, setTemplate] = useState("PROJECT");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [editingGroup, setEditingGroup] = useState<number>();
  const [columnForm, setColumnForm] = useState<Column | "new">();
  const [childrenCollapsed, setChildrenCollapsed] = useState<number[]>([]);
  const [editingTitle, setEditingTitle] = useState<number>();
  const [titleDraft, setTitleDraft] = useState("");
  const [editingComment, setEditingComment] = useState<{
    id: number;
    version: number;
    body: string;
  }>();
  const [zoom, setZoom] = useState(1);
  const [historyOffset, setHistoryOffset] = useState(0);
  const keys = useRef(new MutationKeys());
  const mutationBusy = useRef(false);
  const epoch = useRef(0);
  const detailEpoch = useRef(0);
  useEffect(() => {
    if (!selected && !createBoard && !columnForm) return;
    const previous = document.activeElement as HTMLElement | null;
    const modal = document.querySelector<HTMLElement>(".project-modal");
    modal?.querySelector<HTMLElement>("input,textarea,select,button")?.focus();
    const handle = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !pending) {
        detailEpoch.current++;
        setSelected(undefined);
        setCreateBoard(false);
        setColumnForm(undefined);
      }
      if (e.key === "Tab" && modal) {
        const controls = Array.from(
          modal.querySelectorAll<HTMLElement>(
            "button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled)",
          ),
        );
        const first = controls[0],
          last = controls[controls.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", handle);
    return () => {
      document.removeEventListener("keydown", handle);
      previous?.focus();
    };
  }, [!!selected, createBoard, !!columnForm, pending]);
  const editable =
    !!data?.role &&
    ["EDITOR", "OWNER"].includes(data.role) &&
    !data.board?.archived_at;
  const owner = data?.role === "OWNER" || data?.companyOwner;
  useEffect(() => {
    const controller = new AbortController();
    if (session?.actorKind !== "MEMBER") return;
    api<{ id: number; name: string }[]>(prefix + "/companies", {
      signal: controller.signal,
    })
      .then((r) => {
        setCompanies(r.data);
        const chosen =
          r.data.find((c) => c.id === requestedCompany) ?? r.data[0];
        setCid(chosen?.id);
        if (chosen?.id === requestedCompany && requestedBoard > 0)
          setBid(requestedBoard);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e);
      });
    return () => controller.abort();
  }, [session]);
  useEffect(() => {
    if (!cid) return;
    const next = new URLSearchParams(query);
    next.set("companyId", String(cid));
    if (bid) next.set("boardId", String(bid));
    else next.delete("boardId");
    if (next.toString() !== query.toString()) setQuery(next, { replace: true });
  }, [cid, bid, query, setQuery]);
  async function load(company = cid, boardId = bid) {
    if (!company) return;
    const ticket = ++epoch.current;
    try {
      const r = await api<Overview>(
        `${prefix}?companyId=${company}${boardId ? `&boardId=${boardId}` : ""}`,
      );
      if (ticket !== epoch.current) return;
      let combined = r.data;
      // 네 보기에서 같은 업무를 표시하도록 부모 단위 페이지를 읽는다.
      while (combined.nextOffset != null) {
        const next = await api<Overview>(
          `${prefix}?companyId=${company}&boardId=${boardId}&offset=${combined.nextOffset}`,
        );
        if (ticket !== epoch.current) return;
        combined = {
          ...combined,
          tasks: [...(combined.tasks ?? []), ...(next.data.tasks ?? [])],
          cells: [...(combined.cells ?? []), ...(next.data.cells ?? [])],
          nextOffset: next.data.nextOffset,
        };
      }
      setData(combined);
      if (myTasks) {
        const tasks = await api<Task[]>(
          `${prefix}/my-tasks?companyId=${company}`,
        );
        if (ticket === epoch.current) setMineTasks(tasks.data);
      }
      setError(undefined);
    } catch (e) {
      if (ticket === epoch.current) setError(e);
    }
  }
  useEffect(() => {
    setData(undefined);
    setSelected(undefined);
    setDetail(undefined);
    setPref(initial);
    void load(cid, bid);
    return () => {
      epoch.current++;
    };
  }, [cid, bid, myTasks]);
  useEffect(() => {
    if (data?.preference) setPref(data.preference[0]?.settings ?? initial);
  }, [data?.board?.id]);
  async function mutate(op: string, body: unknown) {
    if (!cid || mutationBusy.current) return false;
    mutationBusy.current = true;
    setPending(true);
    const operation = JSON.stringify([cid, op, body]);
    try {
      const response = await api<{ id: number }>(
        `${prefix}/${op}?companyId=${cid}`,
        {
          method: "POST",
          body,
          csrf: session?.csrfToken,
          key: keys.current.get(operation),
        },
      );
      if (op === "board-create") setBid(response.data.id);
      if (op === "task-create") {
        setTitleDraft((body as { title: string }).title);
        setEditingTitle(response.data.id);
      }
      if (op === "group-create") setEditingGroup(response.data.id);
      keys.current.complete(operation);
      setError(undefined);
      await load();
      return true;
    } catch (e) {
      setError(e);
      return false;
    } finally {
      mutationBusy.current = false;
      setPending(false);
    }
  }
  async function addTask(group: number, parent: number | null = null) {
    if (!editable || mutationBusy.current) return;
    const ok = await mutate("task-create", {
      boardId: bid,
      groupId: group,
      parentId: parent,
      title: parent ? "새 하위 업무" : "새 업무",
      position: Math.max(0, ...(data?.tasks ?? []).map((t) => t.position)) + 1,
    });
    if (ok) {
      setCollapsed((ids) => ids.filter((id) => id !== group));
      setChildrenCollapsed((ids) => ids.filter((id) => id !== parent));
      setPref((current) => ({
        ...current,
        view: "table",
        search: "",
        status: "",
        mine: false,
      }));
    }
  }
  async function update(t: Task, patch: Record<string, unknown>) {
    const ok = await mutate("task-update", { ...payload(t), ...patch });
    if (ok && selected?.id === t.id) setSelected(undefined);
    return ok;
  }
  async function openTask(t: Task) {
    const ticket = ++detailEpoch.current;
    setSelected(t);
    setEditingComment(undefined);
    setHistoryOffset(0);
    setDetail(undefined);
    try {
      const r = await api<Detail>(
        `${prefix}/detail?companyId=${cid}&boardId=${t.board_id}&taskId=${t.id}`,
      );
      if (ticket === detailEpoch.current) setDetail(r.data);
    } catch (e) {
      if (ticket === detailEpoch.current) setError(e);
    }
  }
  const tasks = (myTasks ? mineTasks : (data?.tasks ?? []))
    .filter(
      (t) =>
        (showArchived || !t.archived_at) &&
        (myTasks ||
          !data?.groups?.some(
            (g) => g.id === t.group_id && (g.archived_at || g.deleted_at),
          )) &&
        `${t.title} ${t.assignees.map((a) => a.display_name).join(" ")}`
          .toLowerCase()
          .includes(pref.search.toLowerCase()) &&
        (!pref.status || t.status === pref.status) &&
        (!pref.mine || t.assignees?.some((a) => a.user_id === data?.userId)),
    )
    .sort((a, b) =>
      pref.sort === "title"
        ? a.title.localeCompare(b.title)
        : pref.sort === "due"
          ? (a.ends_on ?? "9999").localeCompare(b.ends_on ?? "9999")
          : a.position - b.position || a.id - b.id,
    );
  const orderedColumns =
    pref.columns ??
    [...defaultColumns].sort((a, b) => {
      const key = (k: string) =>
        (
          ({ assignees: "assignee", dates: "timeline" }) as Record<
            string,
            string
          >
        )[k] ?? k;
      return (
        (data?.columns?.find((c) => c.builtin_key === key(a))?.position ??
          defaultColumns.indexOf(a)) -
        (data?.columns?.find((c) => c.builtin_key === key(b))?.position ??
          defaultColumns.indexOf(b))
      );
    });
  const leaves = tasks.filter((t) => !t.aggregate);
  const summaryTasks = (myTasks ? mineTasks : (data?.tasks ?? [])).filter(
    (t) =>
      !t.archived_at &&
      t.status !== "CANCELLED" &&
      !data?.groups?.some(
        (g) => g.id === t.group_id && (g.archived_at || g.deleted_at),
      ),
  );
  const summaryLeaves = summaryTasks.filter((t) => !t.aggregate);
  const summaryProgress = summaryLeaves.length
    ? Math.round(
        summaryLeaves.reduce((n, t) => n + t.progress, 0) /
          summaryLeaves.length,
      )
    : 0;
  const today = data
    ? new Intl.DateTimeFormat("sv-SE", {
        timeZone: data.company.timezone,
      }).format(new Date())
    : "";
  const late = (t: Task) =>
    !!t.ends_on &&
    t.ends_on < today &&
    !["DONE", "CANCELLED"].includes(t.status);
  function state(t: Task) {
    return editable && !t.aggregate ? (
      <span className={`flow-status-control project-status ${t.status}`}>
        <span aria-hidden="true">● {states[t.status]}</span>
        <select
          aria-label={`${t.title} 상태`}
          className={`project-status ${t.status}`}
          value={t.status}
          disabled={pending}
          onChange={(e) => void update(t, { status: e.target.value })}
        >
          {Object.entries(states).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </span>
    ) : (
      <span className={`project-status ${t.status}`}>
        ● {states[t.status]}
        {t.aggregate ? " · 집계" : ""}
      </span>
    );
  }
  function title(t: Task, inline = false) {
    return (
      <button
        className="project-task-title"
        onClick={() => {
          if (inline && editable) {
            setTitleDraft(t.title);
            setEditingTitle(t.id);
          } else void openTask(t);
        }}
      >
        {!inline && (t.parent_id ? "↳ " : t.aggregate ? "▾ " : "")}
        {t.title}
        {late(t) && <small> · 지연</small>}
      </button>
    );
  }
  if (session?.actorKind !== "MEMBER")
    return (
      <section className="projects">
        <h1>프로젝트·업무</h1>
        <Link to={myTasks ? "/help/flow/f-01" : "/help/flow/f-02"}>
          ? 도움말
        </Link>
        <p>회사 공동 보드는 로그인한 회사 회원만 사용할 수 있습니다.</p>
        <ProjectDemo />
      </section>
    );
  return (
    <section
      className={`projects flow-board ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}
    >
      <header>
        <div>
          <h1>
            <span className="flow-breadcrumb-parent">프로젝트 보드</span>
            <span aria-hidden="true"> › </span>
            {myTasks ? "내 업무" : (data?.board?.name ?? "내 보드")}
          </h1>
          <Link to={myTasks ? "/help/flow/f-01" : "/help/flow/f-02"}>
            ? 도움말
          </Link>
          <p>담당자·일정·진행 상황을 회사 구성원과 함께 관리하세요.</p>
        </div>
        <label>
          회사{" "}
          <select
            aria-label="회사"
            value={cid ?? ""}
            disabled={pending}
            onChange={(e) => {
              setBid(undefined);
              setCid(Number(e.target.value));
            }}
          >
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </header>
      {columnForm && (
        <div
          className="project-modal"
          role="dialog"
          aria-modal="true"
          aria-label="자유 컬럼 설정"
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              const kind = String(f.get("kind"));
              void mutate(
                columnForm === "new" ? "column-create" : "column-update",
                {
                  boardId: bid,
                  ...(columnForm === "new"
                    ? {}
                    : { id: columnForm.id, version: columnForm.version }),
                  name: f.get("name"),
                  kind,
                  position: Number(f.get("position")),
                  width: Number(f.get("width")),
                  options:
                    kind === "STATUS"
                      ? {
                          labels: String(f.get("labels"))
                            .split(",")
                            .map((x) => x.trim())
                            .filter(Boolean),
                        }
                      : {},
                },
              ).then((ok) => {
                if (ok) setColumnForm(undefined);
              });
            }}
          >
            <h2>{columnForm === "new" ? "컬럼 추가" : "컬럼 편집"}</h2>
            <label>
              열 이름
              <input
                name="name"
                required
                maxLength={120}
                defaultValue={columnForm === "new" ? "" : columnForm.name}
              />
            </label>
            <label>
              유형
              <select
                name="kind"
                defaultValue={columnForm === "new" ? "TEXT" : columnForm.kind}
                disabled={columnForm !== "new"}
              >
                {columnForm !== "new" && columnForm.kind === "BUILTIN" && (
                  <option value="BUILTIN">기본 업무 필드</option>
                )}
                {Object.entries({
                  TEXT: "텍스트",
                  NUMBER: "숫자",
                  DATE: "날짜",
                  STATUS: "상태",
                  CHECKBOX: "체크박스",
                  TIMELINE: "기간",
                }).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
              {columnForm !== "new" && (
                <input type="hidden" name="kind" value={columnForm.kind} />
              )}
            </label>
            <label>
              순서
              <input
                name="position"
                type="number"
                min="0"
                required
                defaultValue={
                  columnForm === "new"
                    ? (data?.columns?.length ?? 0)
                    : columnForm.position
                }
              />
            </label>
            <label>
              너비
              <input
                name="width"
                type="number"
                min="80"
                max="600"
                required
                defaultValue={columnForm === "new" ? 160 : columnForm.width}
              />
            </label>
            <label>
              상태 이름 (쉼표로 구분)
              <input
                name="labels"
                defaultValue={
                  columnForm === "new"
                    ? "대기, 진행 중, 완료"
                    : columnForm.options.labels?.join(", ")
                }
              />
            </label>
            <button disabled={pending}>저장</button>
            <button
              type="button"
              disabled={pending}
              onClick={() => setColumnForm(undefined)}
            >
              취소
            </button>
          </form>
        </div>
      )}
      {!!error && <ErrorNotice error={error} retry={() => void load()} />}{" "}
      {!companies.length && !error && (
        <p>연결된 회사가 없습니다. 회사 관리자에게 계정 등록을 요청하세요.</p>
      )}
      {data && (
        <div className="project-workspace">
          <aside className="project-boards">
            <div className="flow-sidebar-brand">
              <span aria-hidden="true">
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.7"
                >
                  <path d="M2 12h4l3-8 4 16 3-8h6" />
                </svg>
              </span>
              <strong>
                Factory Flow<small>통합 업무 공간</small>
              </strong>
              <button
                aria-label="사이드바 접기"
                onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              >
                ◧
              </button>
            </div>
            <nav className="flow-sidebar-nav">
              <Link title="홈" to="/work-os/boards">
                <svg
                  aria-hidden="true"
                  viewBox="0 0 24 24"
                  width="20"
                  height="20"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.7"
                >
                  <path d="m3 10 9-7 9 7M5 9v12h14V9M9 21v-8h6v8" />
                </svg>
                <span className="nav-name">홈</span>
              </Link>
              <Link title="내 업무" to="/work-os/my-tasks">
                <svg
                  aria-hidden="true"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.7"
                >
                  <path d="M4 5h16v14H4ZM4 14h4l2 3h4l2-3h4" />
                </svg>
                <span className="nav-name">내 업무</span>
              </Link>
              <Link
                title="도움말"
                to={myTasks ? "/help/flow/f-01" : "/help/flow/f-02"}
              >
                <span aria-hidden="true">?</span>
                <span className="nav-name">도움말</span>
              </Link>
              <Link title="전체 솔루션" to="/home">
                <MenuIcon kind="grid" />
                <span className="nav-name">전체 솔루션</span>
              </Link>
            </nav>
            <h2>즐겨찾기</h2>
            {data.boards
              .filter((b) => data.favorites.includes(b.id) && !b.archived_at)
              .map((b) => (
                <div
                  key={`favorite-${b.id}`}
                  className={b.id === bid ? "selected" : ""}
                >
                  <button title={b.name} onClick={() => setBid(b.id)}>
                    <span aria-hidden="true" className="flow-board-dot">
                      ★
                    </span>
                    <span className="nav-name">{b.name}</span>
                  </button>
                </div>
              ))}
            <h2 className="flow-board-list-heading">
              내 보드
              {(data.allowCreate || data.companyOwner) && (
                <button
                  aria-label="보드 만들기"
                  title="보드 만들기"
                  onClick={() => setCreateBoard(true)}
                >
                  ＋
                </button>
              )}
            </h2>
            {data.boards
              .filter((b) => showArchived || !b.archived_at)
              .sort(
                (a, b) =>
                  Number(data.favorites.includes(b.id)) -
                  Number(data.favorites.includes(a.id)),
              )
              .map((b) => (
                <div key={b.id} className={b.id === bid ? "selected" : ""}>
                  <button
                    title={b.name}
                    onClick={() => {
                      setBid(b.id);
                      setSelected(undefined);
                    }}
                    disabled={pending}
                  >
                    <span aria-hidden="true" className="flow-board-dot">
                      ●
                    </span>
                    <span className="nav-name">
                      {b.name}
                      {b.archived_at ? " · 보관" : ""}
                    </span>
                  </button>
                  <button
                    className={`project-star ${data.favorites.includes(b.id) ? "on" : ""}`}
                    aria-label={`${b.name} 즐겨찾기`}
                    aria-pressed={data.favorites.includes(b.id)}
                    disabled={pending}
                    onClick={() =>
                      void mutate("favorite", {
                        boardId: b.id,
                        selected: !data.favorites.includes(b.id),
                      })
                    }
                  >
                    {data.favorites.includes(b.id) ? "★" : "☆"}
                  </button>
                </div>
              ))}
            <details className="flow-sidebar-settings">
              <summary aria-label="보드 설정">···</summary>
              <div>
                {" "}
                <label>
                  <input
                    type="checkbox"
                    checked={showArchived}
                    onChange={(e) => setShowArchived(e.target.checked)}
                  />{" "}
                  보관 항목 보기
                </label>
                {data.companyOwner && (
                  <label>
                    <input
                      type="checkbox"
                      disabled={pending}
                      checked={data.allowCreate}
                      onChange={(e) =>
                        void mutate("settings", {
                          allowCreate: e.target.checked,
                        })
                      }
                    />{" "}
                    구성원 보드 생성 허용
                  </label>
                )}
              </div>
            </details>
            <footer className="flow-sidebar-footer">
              <span>
                {data.members.find((m) => m.id === data.userId)?.name ??
                  "로그인 사용자"}
              </span>
              <Link title="사용자 관리" to="/hr/users">
                사용자 관리
              </Link>
              <Link title="내 공간" to="/workspace">
                내 공간
              </Link>
            </footer>
          </aside>
          <div className="project-main">
            {!data.board && !myTasks ? (
              <div className="project-empty">
                <h2>회사 업무를 보드로 묶어보세요.</h2>
                <p>
                  프로젝트 WBS, 팀 업무, 이슈, 회의 후속 업무 중 템플릿을 선택해
                  시작할 수 있습니다.
                </p>
              </div>
            ) : (
              <>
                <div className="project-board-header">
                  <h2>
                    {myTasks ? "참여한 보드의 내 담당 업무" : data.board?.name}
                  </h2>
                  {data.board && (
                    <button
                      className={`project-star flow-heading-star ${data.favorites.includes(data.board!.id) ? "on" : ""}`}
                      aria-label="현재 보드 즐겨찾기"
                      aria-pressed={data.favorites.includes(data.board!.id)}
                      disabled={pending}
                      onClick={() =>
                        void mutate("favorite", {
                          boardId: bid,
                          selected: !data.favorites.includes(data.board!.id),
                        })
                      }
                    >
                      {data.favorites.includes(data.board!.id) ? "★" : "☆"}
                    </button>
                  )}
                  {data.board && owner && (
                    <button
                      className="flow-share"
                      onClick={() => {
                        const settings = document.getElementById(
                          "flow-board-settings",
                        );
                        if (settings?.hasAttribute("open"))
                          settings.removeAttribute("open");
                        else settings?.setAttribute("open", "");
                        settings?.scrollIntoView({ behavior: "smooth" });
                      }}
                    >
                      공유
                    </button>
                  )}
                  {data.board && owner && (
                    <button
                      className="flow-archive-board"
                      disabled={pending}
                      onClick={() =>
                        void mutate("board-update", {
                          boardId: bid,
                          name: data.board!.name,
                          description: data.board!.description,
                          version: data.board!.version,
                          archived: !data.board!.archived_at,
                        })
                      }
                    >
                      {data.board.archived_at ? "보드 복구" : "보드 보관"}
                    </button>
                  )}
                </div>
                {data.board?.archived_at && (
                  <p>보관된 보드입니다. 복구 후 편집할 수 있습니다.</p>
                )}
                {data.board && (
                  <p className="flow-board-description">
                    {data.board.description ||
                      "업무를 그룹으로 묶어 팀과 함께 관리하세요."}
                  </p>
                )}
                {!myTasks && (
                  <nav className="project-tabs">
                    {Object.entries({
                      table: "메인 테이블",
                      kanban: "칸반",
                      calendar: "캘린더",
                      gantt: "간트",
                    }).map(([k, v]) => (
                      <button
                        key={k}
                        aria-pressed={pref.view === k}
                        onClick={() => setPref({ ...pref, view: k })}
                      >
                        <svg
                          aria-hidden="true"
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.6"
                        >
                          <rect x="4" y="4" width="16" height="16" rx="2" />
                          <path
                            d={
                              k === "table"
                                ? "M4 10h16M10 4v16"
                                : k === "kanban"
                                  ? "M9 4v16M15 4v16"
                                  : k === "calendar"
                                    ? "M4 10h16M8 2v5M16 2v5"
                                    : "M7 9h6M11 14h6"
                            }
                          />
                        </svg>
                        {v}
                      </button>
                    ))}
                  </nav>
                )}
                <div className="project-tools">
                  {editable && (
                    <button
                      className="flow-new-task"
                      disabled={
                        pending ||
                        !data.groups?.some(
                          (g) => !g.archived_at && !g.deleted_at,
                        )
                      }
                      onClick={() => {
                        const g = data.groups?.find(
                          (g) => !g.archived_at && !g.deleted_at,
                        );
                        if (g) {
                          void addTask(g.id);
                        }
                      }}
                    >
                      ＋ 새 업무
                    </button>
                  )}
                  <input
                    aria-label="업무 검색"
                    placeholder="업무 또는 담당자 검색"
                    value={pref.search}
                    onChange={(e) =>
                      setPref({ ...pref, search: e.target.value })
                    }
                  />
                  <details className="flow-filter">
                    <summary>
                      <svg
                        aria-hidden="true"
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.7"
                      >
                        <path d="M4 6h16M7 12h10M10 18h4" />
                      </svg>
                      필터
                    </summary>
                    <select
                      aria-label="상태 필터"
                      value={pref.status}
                      onChange={(e) =>
                        setPref({ ...pref, status: e.target.value })
                      }
                    >
                      <option value="">모든 상태</option>
                      {Object.entries(states).map(([k, v]) => (
                        <option key={k} value={k}>
                          {v}
                        </option>
                      ))}
                    </select>
                    <select
                      aria-label="정렬"
                      value={pref.sort}
                      onChange={(e) =>
                        setPref({ ...pref, sort: e.target.value })
                      }
                    >
                      <option value="position">업무 순서</option>
                      <option value="due">마감일</option>
                      <option value="title">제목</option>
                    </select>
                  </details>
                  {!myTasks && (
                    <>
                      <label>
                        <input
                          type="checkbox"
                          checked={pref.mine}
                          onChange={(e) =>
                            setPref({ ...pref, mine: e.target.checked })
                          }
                        />{" "}
                        <svg
                          aria-hidden="true"
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.7"
                        >
                          <circle cx="9" cy="7" r="3" />
                          <path d="M3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6M18 13a5 5 0 0 1 3 5v3" />
                        </svg>
                        내 업무만
                      </label>
                      <details className="flow-view-actions">
                        <summary aria-label="보기 메뉴">···</summary>
                        <div>
                          <button
                            disabled={pending}
                            onClick={() =>
                              void mutate("preference", {
                                boardId: bid,
                                settings: pref,
                              })
                            }
                          >
                            보기 저장
                          </button>
                          <button onClick={() => void load()}>새로고침</button>
                        </div>
                      </details>
                    </>
                  )}
                  <span className="flow-visible-count">
                    표시 중 {tasks.length}개
                  </span>
                </div>
                <div className="project-summary">
                  <span>
                    전체 업무<b>{summaryTasks.length}</b>
                  </span>
                  <span>
                    진행 중
                    <b>
                      {
                        summaryTasks.filter((t) =>
                          ["WORKING", "REVIEW"].includes(t.status),
                        ).length
                      }
                    </b>
                  </span>
                  <span>
                    완료
                    <b>
                      {summaryTasks.filter((t) => t.status === "DONE").length}
                    </b>
                  </span>
                  <span>
                    전체 진행률<b>{summaryProgress}%</b>
                    <progress max="100" value={summaryProgress} />
                  </span>
                </div>
                {(pref.view === "table" || myTasks) && (
                  <>
                    {!myTasks && (
                      <details className="project-column-menu">
                        <summary>열 관리</summary>
                        <div className="project-columns">
                          열 표시{" "}
                          <details>
                            <summary>열 순서</summary>
                            {orderedColumns.map((k, i) => (
                              <span key={k}>
                                {columnLabels[k]}
                                <button
                                  aria-label={`${columnLabels[k]} 열 앞으로`}
                                  disabled={!i}
                                  onClick={() => {
                                    const cols = [...orderedColumns];
                                    [cols[i - 1], cols[i]] = [
                                      cols[i],
                                      cols[i - 1],
                                    ];
                                    setPref({ ...pref, columns: cols });
                                  }}
                                >
                                  ←
                                </button>
                                <button
                                  aria-label={`${columnLabels[k]} 열 뒤로`}
                                  disabled={i === 4}
                                  onClick={() => {
                                    const cols = [...orderedColumns];
                                    [cols[i + 1], cols[i]] = [
                                      cols[i],
                                      cols[i + 1],
                                    ];
                                    setPref({ ...pref, columns: cols });
                                  }}
                                >
                                  →
                                </button>
                              </span>
                            ))}
                          </details>
                          {["assignees", "priority", "progress"].map((k, i) => (
                            <label key={k}>
                              <input
                                type="checkbox"
                                checked={!pref.hidden.includes(k)}
                                onChange={(e) =>
                                  setPref({
                                    ...pref,
                                    hidden: e.target.checked
                                      ? pref.hidden.filter((h) => h !== k)
                                      : [...pref.hidden, k],
                                  })
                                }
                              />
                              {["담당자", "중요도", "진행률"][i]}
                            </label>
                          ))}
                          {owner && (
                            <button onClick={() => setColumnForm("new")}>
                              ＋ 컬럼 추가
                            </button>
                          )}
                          {(data.columns ?? [])
                            .filter((c) => c.kind !== "BUILTIN")
                            .map((c) => (
                              <span key={c.id}>
                                {c.name}
                                {owner && (
                                  <>
                                    <button onClick={() => setColumnForm(c)}>
                                      편집
                                    </button>
                                    <button
                                      disabled={pending}
                                      onClick={() =>
                                        void mutate("column-state", {
                                          boardId: bid,
                                          id: c.id,
                                          version: c.version,
                                          state:
                                            c.deleted_at || c.archived_at
                                              ? "restore"
                                              : "delete",
                                        })
                                      }
                                    >
                                      {c.deleted_at || c.archived_at
                                        ? "복구"
                                        : "삭제"}
                                    </button>
                                  </>
                                )}
                              </span>
                            ))}
                        </div>
                      </details>
                    )}
                    {(myTasks
                      ? [
                          {
                            id: 0,
                            name: "내 담당 업무",
                            color: "#658ab1",
                            position: 0,
                            version: 1,
                          },
                        ]
                      : (data.groups ?? []).filter(
                          (g) =>
                            showArchived || (!g.archived_at && !g.deleted_at),
                        )
                    ).map((g) => (
                      <section
                        key={g.id}
                        className={`project-group ${collapsed.includes(g.id) ? "is-collapsed" : ""}`}
                      >
                        <h3
                          style={{ borderLeftColor: g.color, color: g.color }}
                        >
                          <button
                            onClick={() =>
                              setCollapsed(
                                collapsed.includes(g.id)
                                  ? collapsed.filter((id) => id !== g.id)
                                  : [...collapsed, g.id],
                              )
                            }
                          >
                            {collapsed.includes(g.id) ? "▸" : "▾"}
                          </button>
                          {editingGroup === g.id ? (
                            <input
                              autoFocus
                              aria-label="그룹 이름 바로 편집"
                              defaultValue={g.name}
                              maxLength={120}
                              onKeyDown={(e) => {
                                if (e.key === "Escape") {
                                  e.currentTarget.dataset.cancelled = "true";
                                  e.currentTarget.blur();
                                }
                                if (e.key === "Enter") e.currentTarget.blur();
                              }}
                              onBlur={(e) => {
                                if (
                                  !e.currentTarget.dataset.cancelled &&
                                  e.target.value.trim() &&
                                  e.target.value.trim() !== g.name
                                )
                                  void mutate("group-update", {
                                    boardId: bid,
                                    id: g.id,
                                    version: g.version,
                                    name: e.target.value.trim(),
                                    color: g.color,
                                    position: g.position,
                                  });
                                setEditingGroup(undefined);
                              }}
                            />
                          ) : (
                            <button
                              disabled={!owner || pending}
                              className="flow-group-name"
                              onClick={() => setEditingGroup(g.id)}
                            >
                              {g.name}
                            </button>
                          )}
                          <small>
                            {tasks.filter((t) => t.group_id === g.id).length}
                          </small>
                          {owner && editable && (
                            <details className="flow-group-actions">
                              <summary aria-label={`${g.name} 그룹 메뉴`}>
                                ···
                              </summary>
                              <div>
                                <button
                                  disabled={pending}
                                  onClick={() =>
                                    void mutate("group-duplicate", {
                                      boardId: bid,
                                      id: g.id,
                                      version: g.version,
                                    })
                                  }
                                >
                                  이 그룹 복제
                                </button>
                                <button
                                  disabled={pending}
                                  onClick={() =>
                                    void mutate("group-update", {
                                      boardId: bid,
                                      id: g.id,
                                      version: g.version,
                                      name: g.name,
                                      color: g.color,
                                      position: Math.max(0, g.position - 1),
                                    })
                                  }
                                >
                                  ↑
                                </button>
                                <button
                                  disabled={pending}
                                  onClick={() =>
                                    void mutate("group-update", {
                                      boardId: bid,
                                      id: g.id,
                                      version: g.version,
                                      name: g.name,
                                      color: g.color,
                                      position: g.position + 1,
                                    })
                                  }
                                >
                                  ↓
                                </button>
                                <label>
                                  그룹 색상
                                  <input
                                    aria-label={`${g.name} 그룹 색상`}
                                    type="color"
                                    defaultValue={g.color}
                                    disabled={pending}
                                    onChange={(e) =>
                                      void mutate("group-update", {
                                        boardId: bid,
                                        id: g.id,
                                        version: g.version,
                                        name: g.name,
                                        color: e.target.value,
                                        position: g.position,
                                      })
                                    }
                                  />
                                </label>
                                {["archive", "delete", "restore"].map(
                                  (state) => (
                                    <button
                                      key={state}
                                      disabled={pending}
                                      onClick={() =>
                                        void mutate("group-state", {
                                          boardId: bid,
                                          id: g.id,
                                          version: g.version,
                                          state,
                                        })
                                      }
                                    >
                                      {
                                        {
                                          archive: "그룹 보관",
                                          delete: "그룹 삭제",
                                          restore: "그룹 복구",
                                        }[state]
                                      }
                                    </button>
                                  ),
                                )}
                              </div>
                            </details>
                          )}
                        </h3>
                        {owner && editable && (
                          <details>
                            <summary>그룹 이름·색상 편집</summary>
                            <form
                              onSubmit={(e) => {
                                e.preventDefault();
                                const f = new FormData(e.currentTarget);
                                void mutate("group-update", {
                                  boardId: bid,
                                  id: g.id,
                                  version: g.version,
                                  name: f.get("name"),
                                  color: f.get("color"),
                                  position: g.position,
                                });
                              }}
                            >
                              <input
                                name="name"
                                aria-label="그룹 이름"
                                required
                                defaultValue={g.name}
                                maxLength={120}
                              />
                              <input
                                name="color"
                                aria-label="그룹 색상"
                                type="color"
                                defaultValue={g.color}
                              />
                              <button disabled={pending}>그룹 저장</button>
                            </form>
                          </details>
                        )}
                        {!collapsed.includes(g.id) &&
                          !g.archived_at &&
                          !g.deleted_at && (
                            <div className="project-table">
                              <table>
                                <thead>
                                  <tr>
                                    <th>업무명</th>
                                    {myTasks && <th>보드</th>}
                                    {orderedColumns
                                      .filter((k) => !pref.hidden.includes(k))
                                      .map((k) => (
                                        <th key={k}>
                                          <button
                                            disabled={!owner}
                                            onClick={() => {
                                              const builtin =
                                                data.columns?.find(
                                                  (c) =>
                                                    c.builtin_key ===
                                                      (
                                                        {
                                                          assignees: "assignee",
                                                          dates: "timeline",
                                                        } as Record<
                                                          string,
                                                          string
                                                        >
                                                      )[k] ||
                                                    c.builtin_key === k,
                                                );
                                              if (builtin)
                                                setColumnForm(builtin);
                                            }}
                                          >
                                            {data.columns?.find(
                                              (c) =>
                                                c.builtin_key ===
                                                ((
                                                  {
                                                    assignees: "assignee",
                                                    dates: "timeline",
                                                  } as Record<string, string>
                                                )[k] ?? k),
                                            )?.name ?? columnLabels[k]}
                                          </button>
                                        </th>
                                      ))}
                                    {(data.columns ?? [])
                                      .filter(
                                        (c) =>
                                          c.kind !== "BUILTIN" &&
                                          !c.archived_at &&
                                          !c.deleted_at,
                                      )
                                      .map((c) => (
                                        <th
                                          key={c.id}
                                          style={{ minWidth: c.width }}
                                        >
                                          <button
                                            disabled={!owner}
                                            onClick={() => setColumnForm(c)}
                                          >
                                            {c.name}
                                          </button>
                                        </th>
                                      ))}
                                    {(owner || editable) && (
                                      <th>
                                        <button
                                          aria-label="컬럼 추가"
                                          disabled={!owner}
                                          onClick={() => setColumnForm("new")}
                                        >
                                          ＋
                                        </button>
                                      </th>
                                    )}
                                  </tr>
                                </thead>
                                <tbody>
                                  {tasks
                                    .filter(
                                      (t) =>
                                        (myTasks || t.group_id === g.id) &&
                                        (!t.parent_id ||
                                          !childrenCollapsed.includes(
                                            t.parent_id,
                                          )),
                                    )
                                    .sort((a, b) => {
                                      const pa =
                                          tasks.find(
                                            (t) => t.id === a.parent_id,
                                          ) ?? a,
                                        pb =
                                          tasks.find(
                                            (t) => t.id === b.parent_id,
                                          ) ?? b;
                                      return (
                                        pa.position - pb.position ||
                                        pa.id - pb.id ||
                                        (a.parent_id ? 1 : 0) -
                                          (b.parent_id ? 1 : 0) ||
                                        a.position - b.position
                                      );
                                    })
                                    .map((t) => (
                                      <tr key={t.id}>
                                        <td
                                          className={
                                            t.parent_id ? "flow-subitem" : ""
                                          }
                                        >
                                          <input
                                            type="checkbox"
                                            aria-label={`${t.title} 완료`}
                                            checked={t.status === "DONE"}
                                            disabled={
                                              !editable ||
                                              pending ||
                                              t.aggregate
                                            }
                                            onChange={(e) =>
                                              void update(t, {
                                                status: e.target.checked
                                                  ? "DONE"
                                                  : "WAITING",
                                                progress: e.target.checked
                                                  ? 100
                                                  : 0,
                                              })
                                            }
                                          />
                                          {editable && !t.parent_id && (
                                            <button
                                              className="flow-subitem-add"
                                              disabled={pending}
                                              aria-label={`${t.title} 하위 업무 추가`}
                                              onClick={() => {
                                                void addTask(g.id, t.id);
                                              }}
                                            >
                                              ＋
                                            </button>
                                          )}
                                          {t.aggregate && (
                                            <button
                                              aria-label={`${t.title} 하위 업무 접기`}
                                              onClick={() =>
                                                setChildrenCollapsed(
                                                  childrenCollapsed.includes(
                                                    t.id,
                                                  )
                                                    ? childrenCollapsed.filter(
                                                        (id) => id !== t.id,
                                                      )
                                                    : [
                                                        ...childrenCollapsed,
                                                        t.id,
                                                      ],
                                                )
                                              }
                                            >
                                              {childrenCollapsed.includes(t.id)
                                                ? "▸"
                                                : "▾"}
                                            </button>
                                          )}
                                          {editingTitle === t.id ? (
                                            <input
                                              autoFocus
                                              maxLength={250}
                                              aria-label="업무 제목 바로 편집"
                                              value={titleDraft}
                                              disabled={pending}
                                              onChange={(e) =>
                                                setTitleDraft(e.target.value)
                                              }
                                              onKeyDown={(e) => {
                                                if (e.nativeEvent.isComposing)
                                                  return;
                                                if (e.key === "Escape") {
                                                  e.currentTarget.dataset.cancelled =
                                                    "true";
                                                  setEditingTitle(undefined);
                                                }
                                                if (e.key === "Enter") {
                                                  e.preventDefault();
                                                  e.currentTarget.blur();
                                                }
                                              }}
                                              onBlur={(e) => {
                                                if (
                                                  e.currentTarget.dataset
                                                    .cancelled ||
                                                  mutationBusy.current
                                                )
                                                  return;
                                                const value =
                                                  e.target.value.trim();
                                                if (!value) return;
                                                if (value === t.title) {
                                                  setEditingTitle(undefined);
                                                  return;
                                                }
                                                void mutate("task-update", {
                                                  ...payload(t),
                                                  title: value,
                                                }).then((ok) => {
                                                  if (ok)
                                                    setEditingTitle(undefined);
                                                });
                                              }}
                                            />
                                          ) : (
                                            title(t, true)
                                          )}
                                        </td>
                                        {myTasks && <td>{t.board_name}</td>}
                                        {orderedColumns
                                          .filter(
                                            (k) => !pref.hidden.includes(k),
                                          )
                                          .map((k) => (
                                            <td key={k}>
                                              {k === "status" ? (
                                                state(t)
                                              ) : (
                                                <BuiltinCell
                                                  key={`${t.id}-${k}-${t.version}`}
                                                  task={t}
                                                  kind={k}
                                                  members={data.members}
                                                  disabled={
                                                    !editable || pending
                                                  }
                                                  pending={pending}
                                                  save={(patch) =>
                                                    update(t, patch)
                                                  }
                                                />
                                              )}
                                            </td>
                                          ))}
                                        {(data.columns ?? [])
                                          .filter(
                                            (c) =>
                                              c.kind !== "BUILTIN" &&
                                              !c.archived_at &&
                                              !c.deleted_at,
                                          )
                                          .map((c) => {
                                            const cell = data.cells?.find(
                                              (v) =>
                                                v.task_id === t.id &&
                                                v.column_id === c.id,
                                            );
                                            return (
                                              <td key={c.id}>
                                                <CustomCell
                                                  key={`${c.id}-${cell?.version ?? 0}`}
                                                  column={c}
                                                  value={cell?.value}
                                                  disabled={
                                                    !editable || pending
                                                  }
                                                  save={(value) =>
                                                    void mutate("cell-update", {
                                                      boardId: bid,
                                                      taskId: t.id,
                                                      taskVersion: t.version,
                                                      columnId: c.id,
                                                      columnVersion: c.version,
                                                      version:
                                                        cell?.version ?? 0,
                                                      value,
                                                    })
                                                  }
                                                />
                                              </td>
                                            );
                                          })}
                                        {(owner || editable) && (
                                          <td>
                                            {editable && (
                                              <RowMenu
                                                task={t}
                                                pending={pending}
                                                openDetail={() =>
                                                  void openTask(t)
                                                }
                                                save={(patch) =>
                                                  update(t, patch)
                                                }
                                              />
                                            )}
                                          </td>
                                        )}
                                      </tr>
                                    ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                        {editable &&
                          !collapsed.includes(g.id) &&
                          !g.archived_at &&
                          !g.deleted_at && (
                            <button
                              disabled={pending}
                              onClick={() => {
                                void addTask(g.id);
                              }}
                            >
                              ＋ 업무 추가
                            </button>
                          )}
                      </section>
                    ))}
                  </>
                )}
                {!myTasks && pref.view === "kanban" && (
                  <div className="project-kanban">
                    {Object.entries(states).map(([k, v]) => (
                      <section
                        key={k}
                        onDragOver={(e) => {
                          if (editable) e.preventDefault();
                        }}
                        onDrop={(e) => {
                          e.preventDefault();
                          const t = tasks.find(
                            (t) =>
                              t.id ===
                              Number(e.dataTransfer.getData("text/plain")),
                          );
                          if (editable && t && !t.aggregate)
                            void update(t, { status: k });
                        }}
                      >
                        <h3>{v}</h3>
                        {leaves
                          .filter((t) => t.status === k)
                          .map((t) => (
                            <article
                              key={t.id}
                              draggable={editable}
                              onDragStart={(e) =>
                                e.dataTransfer.setData(
                                  "text/plain",
                                  String(t.id),
                                )
                              }
                            >
                              {title(t)}
                              <p>
                                {t.assignees
                                  .map((a) => a.display_name)
                                  .join(", ") || "담당자 미지정"}
                              </p>
                              <p>{t.ends_on ?? "마감 미정"}</p>
                              {state(t)}
                            </article>
                          ))}
                      </section>
                    ))}
                  </div>
                )}
                {!myTasks && pref.view === "calendar" && (
                  <>
                    <label>
                      월{" "}
                      <input
                        type="month"
                        value={month}
                        onChange={(e) => setMonth(e.target.value)}
                      />
                    </label>
                    <div className="project-calendar">
                      {["일", "월", "화", "수", "목", "금", "토"].map((day) => (
                        <b key={day}>{day}</b>
                      ))}
                      {Array.from(
                        { length: new Date(month + "-01T12:00:00").getDay() },
                        (_, i) => (
                          <div key={"blank" + i} />
                        ),
                      )}
                      {Array.from(
                        {
                          length: new Date(
                            Number(month.slice(0, 4)),
                            Number(month.slice(5)),
                            0,
                          ).getDate(),
                        },
                        (_, i) => {
                          const day = `${month}-${String(i + 1).padStart(2, "0")}`;
                          return (
                            <div key={day}>
                              <b>{i + 1}</b>
                              {leaves
                                .filter((t) =>
                                  t.starts_on && t.ends_on
                                    ? t.starts_on <= day && t.ends_on >= day
                                    : t.starts_on === day || t.ends_on === day,
                                )
                                .map((t) => (
                                  <div key={t.id}>
                                    {title(t)}
                                    <small>
                                      {t.starts_on === day
                                        ? "시작"
                                        : t.ends_on === day
                                          ? "마감"
                                          : "진행 기간"}
                                    </small>
                                  </div>
                                ))}
                            </div>
                          );
                        },
                      )}
                    </div>
                    <p>
                      날짜 미정:{" "}
                      {leaves
                        .filter((t) => !t.starts_on && !t.ends_on)
                        .map((t) => t.title)
                        .join(", ") || "없음"}
                    </p>
                  </>
                )}
                {!myTasks && pref.view === "gantt" && (
                  <>
                    <label>
                      월{" "}
                      <input
                        type="month"
                        value={month}
                        onChange={(e) => setMonth(e.target.value)}
                      />
                    </label>
                    <p>1일 ───────── 10일 ───────── 20일 ───────── 월말</p>
                    <label>
                      확대
                      <input
                        aria-label="간트 확대"
                        type="range"
                        min="1"
                        max="3"
                        step="0.5"
                        value={zoom}
                        onChange={(e) => setZoom(Number(e.target.value))}
                      />
                    </label>
                    <div className="project-gantt">
                      <div style={{ minWidth: 650 * zoom }}>
                        {tasks
                          .filter(
                            (t) =>
                              t.starts_on &&
                              t.ends_on &&
                              t.starts_on.slice(0, 7) <= month &&
                              t.ends_on.slice(0, 7) >= month,
                          )
                          .map((t) => {
                            const days = new Date(
                              Number(month.slice(0, 4)),
                              Number(month.slice(5)),
                              0,
                            ).getDate();
                            const start =
                              t.starts_on!.slice(0, 7) < month
                                ? 1
                                : Number(t.starts_on!.slice(8));
                            const end =
                              t.ends_on!.slice(0, 7) > month
                                ? days
                                : Number(t.ends_on!.slice(8));
                            return (
                              <div className="project-track" key={t.id}>
                                {title(t)}
                                <div style={{ position: "relative" }}>
                                  {today.slice(0, 7) === month && (
                                    <i
                                      aria-label="오늘선"
                                      className="project-today-line"
                                      style={{
                                        left: `${((Number(today.slice(8)) - 1) / days) * 100}%`,
                                      }}
                                    />
                                  )}
                                  <span
                                    style={{
                                      marginLeft: `${((start - 1) / days) * 100}%`,
                                      width: `${((end - start + 1) / days) * 100}%`,
                                    }}
                                  >
                                    {t.progress}%
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                      </div>
                    </div>
                    <p>
                      기간 미정:{" "}
                      {tasks
                        .filter((t) => !t.starts_on || !t.ends_on)
                        .map((t) => t.title)
                        .join(", ") || "없음"}
                    </p>
                  </>
                )}
                {owner && editable && (
                  <button
                    className="flow-new-group"
                    disabled={pending}
                    onClick={() =>
                      void mutate("group-create", {
                        boardId: bid,
                        name: "새 그룹",
                        color: "#40566b",
                        position: (data.groups?.length ?? 0) + 1,
                      })
                    }
                  >
                    ＋ 새 그룹 추가하기
                  </button>
                )}
                {data.board && owner && (
                  <details
                    id="flow-board-settings"
                    className="flow-board-settings"
                  >
                    <summary>보드 설정·구성원 권한</summary>
                    <button
                      disabled={pending}
                      onClick={() =>
                        void mutate("board-update", {
                          boardId: bid,
                          name: data.board!.name,
                          description: data.board!.description,
                          version: data.board!.version,
                          archived: !data.board!.archived_at,
                        })
                      }
                    >
                      {data.board.archived_at ? "보드 복구" : "보드 보관"}
                    </button>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        const f = new FormData(e.currentTarget);
                        void mutate("board-update", {
                          boardId: bid,
                          name: f.get("name"),
                          description: f.get("description"),
                          version: data.board!.version,
                          archived: !!data.board!.archived_at,
                        });
                      }}
                    >
                      <label>
                        보드 이름
                        <input
                          name="name"
                          required
                          defaultValue={data.board.name}
                          maxLength={120}
                        />
                      </label>
                      <label>
                        설명
                        <textarea
                          name="description"
                          maxLength={5000}
                          defaultValue={data.board.description}
                        />
                      </label>
                      <button disabled={pending}>보드 설정 저장</button>
                    </form>
                    <p>
                      회사 회원은 기본 조회 권한입니다. 소유자 또는 편집자로
                      지정할 수 있습니다.
                    </p>
                    {data.members
                      .filter((m) => m.active)
                      .map((m) => (
                        <div key={m.id}>
                          {m.name}
                          <button
                            disabled={pending}
                            onClick={() =>
                              void mutate("member", {
                                boardId: bid,
                                userId: m.id,
                                role: "EDITOR",
                              })
                            }
                          >
                            편집자 지정
                          </button>
                          <button
                            disabled={pending}
                            onClick={() =>
                              void mutate("member", {
                                boardId: bid,
                                userId: m.id,
                                role: "OWNER",
                              })
                            }
                          >
                            소유자 지정
                          </button>
                          <button
                            disabled={pending}
                            onClick={() =>
                              void mutate("member", {
                                boardId: bid,
                                userId: m.id,
                                role: "VIEWER",
                              })
                            }
                          >
                            조회만
                          </button>
                        </div>
                      ))}
                  </details>
                )}
              </>
            )}
          </div>
        </div>
      )}
      {createBoard && (
        <div
          className="project-modal"
          role="dialog"
          aria-modal="true"
          aria-label="보드 만들기"
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void mutate("board-create", {
                name: boardName,
                template,
                description: "",
              }).then((ok) => {
                if (ok) {
                  setCreateBoard(false);
                  setBoardName("");
                }
              });
            }}
          >
            <h2>업무 보드 만들기</h2>
            <label>
              이름
              <input
                autoFocus
                required
                maxLength={120}
                value={boardName}
                onChange={(e) => setBoardName(e.target.value)}
              />
            </label>
            <label>
              템플릿
              <select
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
              >
                {Object.entries({
                  PROJECT: "프로젝트 WBS",
                  TEAM: "팀 업무",
                  ISSUE: "이슈 관리",
                  MEETING: "회의 후속 업무",
                }).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <button disabled={pending}>만들기</button>
            <button
              type="button"
              disabled={pending}
              onClick={() => setCreateBoard(false)}
            >
              취소
            </button>
            {!!error && <ErrorNotice error={error} />}
          </form>
        </div>
      )}
      {selected && (
        <div
          className="project-modal"
          role="dialog"
          aria-modal="true"
          aria-label="업무 상세"
        >
          <div className="project-detail">
            <button
              disabled={pending}
              onClick={() => {
                detailEpoch.current++;
                setSelected(undefined);
              }}
            >
              닫기
            </button>
            <h2>{selected.title}</h2>
            {!myTasks && editable ? (
              <TaskEditor
                key={selected.id + ":" + selected.version}
                task={selected}
                pending={pending}
                save={(patch) => void update(selected, patch)}
              />
            ) : (
              <p>
                {selected.description} · {states[selected.status]} ·{" "}
                {selected.progress}%
              </p>
            )}
            <div>
              {(selected.description.match(/https?:\/\/[^\s<>"']+/g) ?? []).map(
                (url) => (
                  <p key={url}>
                    <a href={url} target="_blank" rel="noreferrer">
                      {url}
                    </a>
                  </p>
                ),
              )}
            </div>
            <h3>댓글</h3>
            {detail?.comments.map((c) => (
              <article key={c.id}>
                <b>
                  {data?.members.find((m) => m.id === c.user_id)?.name ??
                    "이전 구성원"}
                </b>
                {editable && c.user_id === data?.userId && !c.deleted_at && (
                  <button
                    onClick={() =>
                      setEditingComment({
                        id: c.id,
                        version: c.version,
                        body: c.body,
                      })
                    }
                  >
                    내 댓글 수정
                  </button>
                )}
                <p>
                  {c.deleted_at ? "삭제된 댓글" : c.body}
                  {c.updated_at ? " (수정됨)" : ""}
                </p>
                {editable && c.user_id === data?.userId && !c.deleted_at && (
                  <button
                    disabled={pending}
                    onClick={() =>
                      void mutate("comment-update", {
                        boardId: selected.board_id,
                        taskId: selected.id,
                        id: c.id,
                        version: c.version,
                        body: c.body,
                        deleted: true,
                      }).then((ok) => {
                        if (ok) void openTask(selected);
                      })
                    }
                  >
                    내 댓글 삭제
                  </button>
                )}
              </article>
            ))}
            {editingComment && editable && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void mutate("comment-update", {
                    boardId: selected.board_id,
                    taskId: selected.id,
                    ...editingComment,
                    deleted: false,
                  }).then((ok) => {
                    if (ok) {
                      setEditingComment(undefined);
                      void openTask(selected);
                    }
                  });
                }}
              >
                <textarea
                  aria-label="댓글 수정"
                  value={editingComment.body}
                  onChange={(e) =>
                    setEditingComment({
                      ...editingComment,
                      body: e.target.value,
                    })
                  }
                  required
                  maxLength={5000}
                />
                <button disabled={pending}>댓글 수정 저장</button>
                <button
                  type="button"
                  onClick={() => setEditingComment(undefined)}
                >
                  취소
                </button>
              </form>
            )}
            {editable && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void mutate("comment-create", {
                    boardId: selected.board_id,
                    taskId: selected.id,
                    body: comment,
                  }).then((ok) => {
                    if (ok) {
                      setComment("");
                      void openTask(selected);
                    }
                  });
                }}
              >
                <textarea
                  required
                  maxLength={5000}
                  aria-label="댓글"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                />
                <button disabled={pending}>댓글 등록</button>
              </form>
            )}
            <h3>변경 이력</h3>
            {detail?.events.map((e) => (
              <p key={e.id}>
                {e.action} · {new Date(e.created_at).toLocaleString("ko-KR")} ·{" "}
                {data?.members.find((m) => m.id === e.user_id)?.name ??
                  "이전 구성원"}
              </p>
            ))}
            {detail &&
              (detail.comments.length >= 50 || detail.events.length >= 50) && (
                <button
                  disabled={pending}
                  onClick={() => {
                    const offset = historyOffset + 50;
                    const ticket = detailEpoch.current;
                    void api<Detail>(
                      `${prefix}/detail?companyId=${cid}&boardId=${selected.board_id}&taskId=${selected.id}&offset=${offset}`,
                    )
                      .then((r) => {
                        if (ticket === detailEpoch.current) {
                          setHistoryOffset(offset);
                          setDetail({
                            comments: [...detail.comments, ...r.data.comments],
                            events: [...detail.events, ...r.data.events],
                          });
                        }
                      })
                      .catch(setError);
                  }}
                >
                  이전 댓글·이력 더 보기
                </button>
              )}
            {!!error && <ErrorNotice error={error} />}
          </div>
        </div>
      )}
    </section>
  );
}
function RowMenu({
  task,
  pending,
  openDetail,
  save,
}: {
  task: Task;
  pending: boolean;
  openDetail: () => void;
  save: (patch: Record<string, unknown>) => Promise<boolean>;
}) {
  const [position, setPosition] = useState<{ top: number; left: number }>();
  useEffect(() => {
    if (!position) return;
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPosition(undefined);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [position]);
  return (
    <div className="flow-row-actions">
      <button
        aria-label={`${task.title} 업무 메뉴`}
        aria-expanded={!!position}
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setPosition(
            position
              ? undefined
              : {
                  top: Math.max(
                    8,
                    Math.min(r.bottom + 4, window.innerHeight - 180),
                  ),
                  left: Math.max(
                    8,
                    Math.min(r.right - 250, window.innerWidth - 260),
                  ),
                },
          );
        }}
      >
        ···
      </button>
      {position &&
        createPortal(
          <div
            className="flow-board flow-menu-portal"
            onKeyDown={(e) => {
              if (e.key === "Escape") setPosition(undefined);
            }}
          >
            <button
              className="flow-cell-backdrop"
              aria-label="업무 메뉴 닫기"
              onClick={() => setPosition(undefined)}
            />
            <div
              className="flow-row-menu"
              style={{ position: "fixed", ...position, zIndex: 1001 }}
            >
              <button
                disabled={pending}
                aria-label={`${task.title} 업데이트`}
                onClick={() => {
                  setPosition(undefined);
                  openDetail();
                }}
              >
                상세·업데이트
              </button>
              <button
                disabled={pending}
                onClick={() =>
                  void save({ archived: !task.archived_at }).then((ok) => {
                    if (ok) setPosition(undefined);
                  })
                }
              >
                {task.archived_at
                  ? "업무 복구"
                  : task.parent_id
                    ? "하위 업무 삭제"
                    : "업무 삭제"}
              </button>
              <small>
                {task.aggregate && !task.archived_at
                  ? "삭제 시 하위 업무도 함께 보관됩니다. "
                  : ""}
                삭제한 업무는 보관 항목에서 복구할 수 있습니다.
              </small>
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
function BuiltinCell({
  task,
  kind,
  members,
  disabled,
  pending,
  save,
}: {
  task: Task;
  kind: string;
  members: Member[];
  disabled: boolean;
  pending: boolean;
  save: (patch: Record<string, unknown>) => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const [draft, setDraft] = useState(payload(task));
  useEffect(() => {
    if (!open) return;
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [open]);
  const aggregate =
    !!task.aggregate && (kind === "dates" || kind === "progress");
  const label = `${task.title} ${columnLabels[kind]}`;
  const display =
    kind === "assignees" ? (
      <span className="flow-people">
        {task.assignees.length
          ? task.assignees.map((a) => (
              <span className="flow-person" key={a.user_id}>
                <span className="flow-avatar" aria-hidden="true">
                  {a.display_name.slice(0, 1)}
                </span>
                {a.display_name}
                {!a.active && " (비활성)"}
              </span>
            ))
          : "미지정"}
      </span>
    ) : kind === "priority" ? (
      priorities[task.priority]
    ) : kind === "dates" ? (
      <span className="flow-date">
        {task.starts_on?.slice(5).replace("-", ".") ?? "미정"} -{" "}
        {task.ends_on?.slice(5).replace("-", ".") ?? "미정"}
      </span>
    ) : (
      <span className={`flow-progress ${task.status === "DONE" ? "done" : ""}`}>
        <progress aria-label={label} max={100} value={task.progress} />
        <span>{task.progress}%</span>
      </span>
    );
  if (disabled || aggregate)
    return (
      <span title={aggregate ? "하위 업무에서 자동 집계합니다." : undefined}>
        {display}
      </span>
    );
  if (kind === "priority")
    return (
      <span className="flow-status-control flow-priority">
        <span aria-hidden="true">{display}</span>
        <select
          aria-label={label}
          value={task.priority}
          disabled={pending}
          onChange={(e) => void save({ priority: e.target.value })}
        >
          {Object.entries(priorities).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </span>
    );
  return (
    <div className="flow-cell-editor">
      <button
        className="flow-cell-trigger"
        aria-label={`${label} 수정`}
        aria-expanded={open}
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setPosition({
            top: Math.max(8, Math.min(r.bottom + 4, window.innerHeight - 240)),
            left: Math.max(8, Math.min(r.left, window.innerWidth - 270)),
          });
          setDraft(payload(task));
          setOpen(!open);
        }}
      >
        {display}
      </button>
      {open &&
        createPortal(
          <div
            className="flow-board flow-cell-portal"
            style={{ position: "fixed", ...position, zIndex: 1000 }}
          >
            <button
              className="flow-cell-backdrop"
              aria-label="셀 편집 닫기"
              onClick={() => setOpen(false)}
            />
            <form
              className="flow-cell-popover"
              aria-label={`${label} 편집`}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  e.stopPropagation();
                  setOpen(false);
                }
              }}
              onSubmit={(e) => {
                e.preventDefault();
                const patch =
                  kind === "assignees"
                    ? { assignees: draft.assignees }
                    : kind === "dates"
                      ? {
                          startsOn:
                            new FormData(e.currentTarget).get("startsOn") ||
                            null,
                          endsOn:
                            new FormData(e.currentTarget).get("endsOn") || null,
                        }
                      : {
                          progress: draft.progress,
                          status:
                            draft.progress === 100
                              ? "DONE"
                              : task.status === "DONE"
                                ? "WORKING"
                                : task.status,
                        };
                void save(patch).then((ok) => {
                  if (ok) setOpen(false);
                });
              }}
            >
              {kind === "assignees" ? (
                <fieldset>
                  <legend>담당자</legend>
                  {members
                    .filter((m) => m.active || draft.assignees.includes(m.id))
                    .map((m) => (
                      <label key={m.id}>
                        <input
                          type="checkbox"
                          disabled={pending}
                          checked={draft.assignees.includes(m.id)}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              assignees: e.target.checked
                                ? [...draft.assignees, m.id]
                                : draft.assignees.filter((id) => id !== m.id),
                            })
                          }
                        />
                        {m.name}
                        {!m.active && " (비활성)"}
                      </label>
                    ))}
                </fieldset>
              ) : kind === "dates" ? (
                <>
                  <label>
                    시작일
                    <input
                      aria-label={`${task.title} 시작일`}
                      name="startsOn"
                      type="date"
                      disabled={pending}
                      value={draft.startsOn ?? ""}
                      max={draft.endsOn ?? undefined}
                      onChange={(e) =>
                        setDraft({ ...draft, startsOn: e.target.value || null })
                      }
                    />
                  </label>
                  <label>
                    종료일
                    <input
                      aria-label={`${task.title} 종료일`}
                      name="endsOn"
                      type="date"
                      disabled={pending}
                      value={draft.endsOn ?? ""}
                      min={draft.startsOn ?? undefined}
                      onChange={(e) =>
                        setDraft({ ...draft, endsOn: e.target.value || null })
                      }
                    />
                  </label>
                </>
              ) : (
                <label>
                  진행률
                  <input
                    aria-label={`${task.title} 진행률 입력`}
                    type="number"
                    min={0}
                    max={100}
                    required
                    disabled={pending}
                    value={draft.progress}
                    onChange={(e) =>
                      setDraft({ ...draft, progress: Number(e.target.value) })
                    }
                  />
                </label>
              )}
              <div>
                <button disabled={pending}>적용</button>
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => setOpen(false)}
                >
                  취소
                </button>
              </div>
            </form>
          </div>,
          document.body,
        )}
    </div>
  );
}
function TaskEditor({
  task,
  pending,
  save,
}: {
  task: Task;
  pending: boolean;
  save: (patch: Record<string, unknown>) => void;
}) {
  const [draft, setDraft] = useState({
    title: task.title,
    description: task.description,
  });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save(draft);
      }}
    >
      <label>
        제목
        <input
          required
          maxLength={250}
          value={draft.title}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
        />
      </label>
      <label>
        설명·참고 링크
        <textarea
          maxLength={10000}
          value={draft.description}
          onChange={(e) => setDraft({ ...draft, description: e.target.value })}
        />
      </label>
      <button disabled={pending}>저장</button>
    </form>
  );
}
function CustomCell({
  column,
  value,
  disabled,
  save,
}: {
  column: Column;
  value: unknown;
  disabled: boolean;
  save: (v: unknown) => void;
}) {
  const [draft, setDraft] = useState(value ?? "");
  if (column.kind === "CHECKBOX")
    return (
      <input
        aria-label={column.name}
        type="checkbox"
        checked={value === true}
        disabled={disabled}
        onChange={(e) => save(e.target.checked)}
      />
    );
  if (column.kind === "STATUS")
    return (
      <select
        aria-label={column.name}
        disabled={disabled}
        value={String(value ?? "")}
        onChange={(e) => save(e.target.value || null)}
      >
        <option value="">미정</option>
        {column.options.labels?.map((x) => (
          <option key={x}>{x}</option>
        ))}
      </select>
    );
  if (column.kind === "TIMELINE") {
    const v = draft as { start?: string; end?: string };
    return (
      <form
        className="flow-cell-period"
        onSubmit={(e) => {
          e.preventDefault();
          save(v.start && v.end ? v : null);
        }}
      >
        <input
          aria-label={`${column.name} 시작`}
          type="date"
          value={v.start ?? ""}
          disabled={disabled}
          onChange={(e) => setDraft({ ...v, start: e.target.value })}
        />
        <input
          aria-label={`${column.name} 종료`}
          type="date"
          value={v.end ?? ""}
          disabled={disabled}
          onChange={(e) => setDraft({ ...v, end: e.target.value })}
        />
        <button disabled={disabled}>적용</button>
      </form>
    );
  }
  return (
    <input
      aria-label={column.name}
      disabled={disabled}
      type={
        column.kind === "NUMBER"
          ? "number"
          : column.kind === "DATE"
            ? "date"
            : "text"
      }
      maxLength={4000}
      value={String(draft)}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.currentTarget.dataset.cancelled = "true";
          setDraft(value ?? "");
          e.currentTarget.blur();
        }
        if (e.key === "Enter") e.currentTarget.blur();
      }}
      onBlur={(e) => {
        if (e.currentTarget.dataset.cancelled) {
          delete e.currentTarget.dataset.cancelled;
          return;
        }
        const v =
          draft === ""
            ? null
            : column.kind === "NUMBER"
              ? Number(draft)
              : draft;
        if (v !== value) save(v);
      }}
    />
  );
}

function ProjectDemo() {
  const [state, setState] = useState("WAITING");
  return (
    <div className="project-empty">
      <h2>합성 업무 체험</h2>
      <p>예제 프로젝트 → 계획·검토 → 요구사항 정리</p>
      <label>
        상태
        <select value={state} onChange={(e) => setState(e.target.value)}>
          {Object.entries(states).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <p>회사 데이터에 저장되지 않습니다.</p>
    </div>
  );
}
