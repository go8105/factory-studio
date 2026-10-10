import { useEffect, useRef, useState } from "react";
import { useSession } from "../app/session";
import { api, MutationKeys } from "../shared/api";
import { ErrorNotice } from "../shared/components";
import "./Projects.css";
import { Link } from "react-router-dom";

type Member = { id: number; name: string; active: boolean; role: string };
type Board = {
  id: number;
  name: string;
  description: string;
  template: string;
  version: number;
  archived_at: string | null;
};
type Group = {
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
  hidden: [],
};
const columnLabels: Record<string, string> = {
  assignees: "담당자",
  status: "상태",
  priority: "중요도",
  dates: "일정",
  progress: "진행률",
};
const defaultColumns = Object.keys(columnLabels);
const prefix = "/api/v1/gw/projects";
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
  const [taskForm, setTaskForm] = useState<{
    group: number;
    parent: number | null;
  }>();
  const [taskTitle, setTaskTitle] = useState("");
  const [groupName, setGroupName] = useState("");
  const [childrenCollapsed, setChildrenCollapsed] = useState<number[]>([]);
  const [editingTitle, setEditingTitle] = useState<number>();
  const [editingComment, setEditingComment] = useState<{
    id: number;
    version: number;
    body: string;
  }>();
  const [zoom, setZoom] = useState(1);
  const [historyOffset, setHistoryOffset] = useState(0);
  const keys = useRef(new MutationKeys());
  const epoch = useRef(0);
  const detailEpoch = useRef(0);
  useEffect(() => {
    if (!selected && !createBoard && !taskForm) return;
    const previous = document.activeElement as HTMLElement | null;
    const modal = document.querySelector<HTMLElement>(".project-modal");
    modal?.querySelector<HTMLElement>("input,textarea,select,button")?.focus();
    const handle = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !pending) {
        detailEpoch.current++;
        setSelected(undefined);
        setCreateBoard(false);
        setTaskForm(undefined);
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
  }, [!!selected, createBoard, !!taskForm, pending]);
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
        setCid(r.data[0]?.id);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e);
      });
    return () => controller.abort();
  }, [session]);
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
    if (!cid || pending) return false;
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
      keys.current.complete(operation);
      setError(undefined);
      await load();
      return true;
    } catch (e) {
      setError(e);
      return false;
    } finally {
      setPending(false);
    }
  }
  async function update(t: Task, patch: Record<string, unknown>) {
    const ok = await mutate("task-update", { ...payload(t), ...patch });
    if (ok && selected?.id === t.id) setSelected(undefined);
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
        t.title.toLowerCase().includes(pref.search.toLowerCase()) &&
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
  const leaves = tasks.filter((t) => !t.aggregate);
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
    ) : (
      <span className={`project-status ${t.status}`}>
        {states[t.status]}
        {t.aggregate ? " · 집계" : ""}
      </span>
    );
  }
  function title(t: Task) {
    return (
      <button className="project-task-title" onClick={() => void openTask(t)}>
        {t.parent_id ? "↳ " : t.aggregate ? "▾ " : ""}
        {t.title}
        {late(t) && <small> · 지연</small>}
      </button>
    );
  }
  if (session?.actorKind !== "MEMBER")
    return (
      <section className="projects">
        <h1>프로젝트·업무</h1>
        <p>회사 공동 보드는 로그인한 회사 회원만 사용할 수 있습니다.</p>
        <ProjectDemo />
      </section>
    );
  return (
    <section className="projects">
      <header>
        <div>
          <h1>{myTasks ? "내 업무" : "프로젝트·업무"}</h1>
          <Link to={myTasks ? "/help/gw/g-15" : "/help/gw/g-14"}>? 도움말</Link>
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
      {!!error && <ErrorNotice error={error} retry={() => void load()} />}{" "}
      {!companies.length && !error && (
        <p>연결된 회사가 없습니다. 회사 관리자에게 계정 등록을 요청하세요.</p>
      )}
      {data && (
        <div className="project-workspace">
          <aside className="project-boards">
            <h2>업무 보드</h2>
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
                    {b.name}
                    {b.archived_at ? " · 보관" : ""}
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
            {(data.allowCreate || data.companyOwner) && (
              <button onClick={() => setCreateBoard(true)}>
                ＋ 보드 만들기
              </button>
            )}
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
                    void mutate("settings", { allowCreate: e.target.checked })
                  }
                />{" "}
                구성원 보드 생성 허용
              </label>
            )}
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
                  {data.board && owner && (
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
                  )}
                </div>
                {data.board?.archived_at && (
                  <p>보관된 보드입니다. 복구 후 편집할 수 있습니다.</p>
                )}
                {data.board && (
                  <p>
                    {data.board.description} ·{" "}
                    {editable ? "편집 가능" : "조회 권한"}
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
                        {v}
                      </button>
                    ))}
                  </nav>
                )}
                <div className="project-tools">
                  <input
                    aria-label="업무 검색"
                    placeholder="업무 검색"
                    value={pref.search}
                    onChange={(e) =>
                      setPref({ ...pref, search: e.target.value })
                    }
                  />
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
                    onChange={(e) => setPref({ ...pref, sort: e.target.value })}
                  >
                    <option value="position">업무 순서</option>
                    <option value="due">마감일</option>
                    <option value="title">제목</option>
                  </select>
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
                        내 담당
                      </label>
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
                    </>
                  )}
                </div>
                <div className="project-summary">
                  <span>
                    업무 <b>{leaves.length}</b>
                  </span>
                  <span>
                    완료{" "}
                    <b>{leaves.filter((t) => t.status === "DONE").length}</b>
                  </span>
                  <span>
                    지연 <b>{leaves.filter(late).length}</b>
                  </span>
                </div>
                {(pref.view === "table" || myTasks) && (
                  <>
                    {!myTasks && (
                      <div className="project-columns">
                        열 표시{" "}
                        <details>
                          <summary>열 순서</summary>
                          {(pref.columns ?? defaultColumns).map((k, i) => (
                            <span key={k}>
                              {columnLabels[k]}
                              <button
                                aria-label={`${columnLabels[k]} 열 앞으로`}
                                disabled={!i}
                                onClick={() => {
                                  const cols = [
                                    ...(pref.columns ?? defaultColumns),
                                  ];
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
                                  const cols = [
                                    ...(pref.columns ?? defaultColumns),
                                  ];
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
                      </div>
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
                      : (data.groups ?? [])
                    ).map((g) => (
                      <section key={g.id} className="project-group">
                        <h3 style={{ borderLeftColor: g.color }}>
                          <button
                            onClick={() =>
                              setCollapsed(
                                collapsed.includes(g.id)
                                  ? collapsed.filter((id) => id !== g.id)
                                  : [...collapsed, g.id],
                              )
                            }
                          >
                            {collapsed.includes(g.id) ? "▸" : "▾"} {g.name}
                          </button>
                          {editable && (
                            <>
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
                            </>
                          )}
                        </h3>
                        <div className="project-group-summary">
                          {Object.entries(states).map(([k, label]) => {
                            const count = leaves.filter(
                              (t) =>
                                (myTasks || t.group_id === g.id) &&
                                t.status === k,
                            ).length;
                            return count ? (
                              <span key={k} className={`project-status ${k}`}>
                                {label} {count}
                              </span>
                            ) : null;
                          })}
                          <span>
                            진행률{" "}
                            {(() => {
                              const list = leaves.filter(
                                (t) =>
                                  (myTasks || t.group_id === g.id) &&
                                  t.status !== "CANCELLED",
                              );
                              return list.length
                                ? Math.round(
                                    list.reduce((n, t) => n + t.progress, 0) /
                                      list.length,
                                  ) + "%"
                                : "대상 없음";
                            })()}
                          </span>
                        </div>
                        {editable && (
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
                        {!collapsed.includes(g.id) && (
                          <div className="project-table">
                            <table>
                              <thead>
                                <tr>
                                  <th>업무</th>
                                  {myTasks && <th>보드</th>}
                                  {(pref.columns ?? defaultColumns)
                                    .filter((k) => !pref.hidden.includes(k))
                                    .map((k) => (
                                      <th key={k}>{columnLabels[k]}</th>
                                    ))}
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
                                      <td>
                                        {t.aggregate && (
                                          <button
                                            aria-label={`${t.title} 하위 업무 접기`}
                                            onClick={() =>
                                              setChildrenCollapsed(
                                                childrenCollapsed.includes(t.id)
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
                                            defaultValue={t.title}
                                            onKeyDown={(e) => {
                                              if (e.key === "Escape") {
                                                e.currentTarget.dataset.cancelled =
                                                  "true";
                                                e.currentTarget.blur();
                                              }
                                              if (e.key === "Enter")
                                                e.currentTarget.blur();
                                            }}
                                            onBlur={(e) => {
                                              if (
                                                !e.currentTarget.dataset
                                                  .cancelled &&
                                                e.target.value.trim() &&
                                                e.target.value.trim() !==
                                                  t.title
                                              )
                                                void update(t, {
                                                  title: e.target.value.trim(),
                                                });
                                              setEditingTitle(undefined);
                                            }}
                                          />
                                        ) : (
                                          title(t)
                                        )}
                                        {editable && (
                                          <button
                                            aria-label={`${t.title} 제목 편집`}
                                            onClick={() =>
                                              setEditingTitle(t.id)
                                            }
                                          >
                                            편집
                                          </button>
                                        )}
                                      </td>
                                      {myTasks && <td>{t.board_name}</td>}
                                      {(pref.columns ?? defaultColumns)
                                        .filter((k) => !pref.hidden.includes(k))
                                        .map((k) => (
                                          <td key={k}>
                                            {k === "assignees"
                                              ? t.assignees
                                                  ?.map(
                                                    (a) =>
                                                      a.display_name +
                                                      (a.active
                                                        ? ""
                                                        : " (비활성)"),
                                                  )
                                                  .join(", ") || "미지정"
                                              : k === "status"
                                                ? state(t)
                                                : k === "priority"
                                                  ? priorities[t.priority]
                                                  : k === "dates"
                                                    ? `${t.starts_on ?? "미정"} → ${t.ends_on ?? "미정"}`
                                                    : `${t.progress}%`}
                                          </td>
                                        ))}
                                    </tr>
                                  ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                        {editable && (
                          <button
                            onClick={() => {
                              setTaskTitle("");
                              setTaskForm({ group: g.id, parent: null });
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
                {editable && (
                  <form
                    className="project-tools"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void mutate("group-create", {
                        boardId: bid,
                        name: groupName,
                        color: "#658ab1",
                        position: (data.groups?.length ?? 0) + 1,
                      }).then((ok) => {
                        if (ok) setGroupName("");
                      });
                    }}
                  >
                    <input
                      required
                      maxLength={120}
                      aria-label="새 그룹 이름"
                      placeholder="새 그룹 이름"
                      value={groupName}
                      onChange={(e) => setGroupName(e.target.value)}
                    />
                    <button disabled={pending}>＋ 그룹 추가</button>
                  </form>
                )}
                {data.board && owner && (
                  <details>
                    <summary>보드 설정·구성원 권한</summary>
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
      {taskForm && (
        <div
          className="project-modal"
          role="dialog"
          aria-modal="true"
          aria-label="업무 추가"
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void mutate("task-create", {
                boardId: bid,
                groupId: taskForm.group,
                parentId: taskForm.parent,
                title: taskTitle,
                position: (data?.tasks?.length ?? 0) + 1,
              }).then((ok) => {
                if (ok) setTaskForm(undefined);
              });
            }}
          >
            <h2>{taskForm.parent ? "하위 업무" : "업무"} 추가</h2>
            {taskForm.parent && (
              <p>상위 업무의 상태·기간·진행률은 하위 업무 집계로 바뀝니다.</p>
            )}
            <input
              required
              autoFocus
              maxLength={250}
              aria-label="업무 제목"
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
            />
            <button disabled={pending}>추가</button>
            <button
              type="button"
              disabled={pending}
              onClick={() => setTaskForm(undefined)}
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
                members={data?.members ?? []}
                pending={pending}
                save={(patch) => void update(selected, patch)}
              />
            ) : (
              <p>
                {selected.description} · {states[selected.status]} ·{" "}
                {selected.progress}%
              </p>
            )}
            {editable && !selected.parent_id && (
              <button
                onClick={() => {
                  setTaskTitle("");
                  setTaskForm({
                    group: selected.group_id,
                    parent: selected.id,
                  });
                  setSelected(undefined);
                }}
              >
                ＋ 하위 업무
              </button>
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
function TaskEditor({
  task,
  members,
  pending,
  save,
}: {
  task: Task;
  members: Member[];
  pending: boolean;
  save: (patch: Record<string, unknown>) => void;
}) {
  const [draft, setDraft] = useState(payload(task));
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
      <label>
        담당자
        <select
          multiple
          value={draft.assignees.map(String)}
          onChange={(e) =>
            setDraft({
              ...draft,
              assignees: Array.from(e.target.selectedOptions, (o) =>
                Number(o.value),
              ),
            })
          }
        >
          {members
            .filter((m) => m.active || draft.assignees.includes(m.id))
            .map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
                {m.active ? "" : " (비활성)"}
              </option>
            ))}
        </select>
      </label>
      <label>
        상태
        <select
          disabled={task.aggregate}
          value={draft.status}
          onChange={(e) => setDraft({ ...draft, status: e.target.value })}
        >
          {Object.entries(states).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <label>
        중요도
        <select
          value={draft.priority}
          onChange={(e) => setDraft({ ...draft, priority: e.target.value })}
        >
          {Object.entries(priorities).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <label>
        시작일
        <input
          type="date"
          disabled={task.aggregate}
          value={draft.startsOn ?? ""}
          onChange={(e) =>
            setDraft({ ...draft, startsOn: e.target.value || null })
          }
        />
      </label>
      <label>
        종료일
        <input
          type="date"
          disabled={task.aggregate}
          value={draft.endsOn ?? ""}
          onChange={(e) =>
            setDraft({ ...draft, endsOn: e.target.value || null })
          }
        />
      </label>
      <label>
        진행률
        <input
          type="number"
          min={0}
          max={100}
          disabled={task.aggregate}
          value={draft.progress}
          onChange={(e) =>
            setDraft({ ...draft, progress: Number(e.target.value) })
          }
        />
      </label>
      <label>
        순서
        <input
          type="number"
          min={0}
          value={draft.position}
          onChange={(e) =>
            setDraft({ ...draft, position: Number(e.target.value) })
          }
        />
      </label>
      <label>
        <input
          type="checkbox"
          checked={draft.archived}
          onChange={(e) => setDraft({ ...draft, archived: e.target.checked })}
        />{" "}
        업무 보관
      </label>
      {task.aggregate && (
        <p>상태·기간·진행률은 하위 업무에서 자동 집계합니다.</p>
      )}
      <button disabled={pending}>저장</button>
    </form>
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
