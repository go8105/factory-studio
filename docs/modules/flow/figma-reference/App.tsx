import { useMemo, useState } from "react"

type IconName = "activity" | "board" | "calendar" | "check" | "chevron" | "clock" | "dots" | "filter" | "gantt" | "grid" | "home" | "inbox" | "menu" | "plus" | "search" | "settings" | "star" | "table" | "team"

type Status = "대기" | "진행 중" | "검토" | "완료"
type GroupId = string

type Group = {
  id: GroupId
  title: string
  color: string
  text: string
}

type Board = {
  id: string
  title: string
  favorite: boolean
  color: string
}

type Task = {
  id: number
  group: GroupId
  title: string
  owner: string
  initials: string
  status: Status
  start: string
  end: string
  progress: number
  parentId?: number
}

const initialGroups: Group[] = [
  {
    id: "plan" as const,
    title: "계획 · 검토",
    color: "bg-blue-500",
    text: "text-blue-700",
  },
  {
    id: "execute" as const,
    title: "실행 · 검증",
    color: "bg-violet-500",
    text: "text-violet-700",
  },
  {
    id: "finish" as const,
    title: "완료 · 공유",
    color: "bg-emerald-500",
    text: "text-emerald-700",
  },
]

const initialTasks: Task[] = [
  {
    id: 1,
    group: "plan",
    title: "현장 요구사항 정리",
    owner: "김현우",
    initials: "김",
    status: "완료",
    start: "10.01",
    end: "10.05",
    progress: 100,
  },
  {
    id: 2,
    group: "plan",
    title: "개선 범위 및 일정 확정",
    owner: "박서연",
    initials: "박",
    status: "검토",
    start: "10.04",
    end: "10.08",
    progress: 80,
  },
  {
    id: 3,
    group: "execute",
    title: "장비 점검 및 시운전",
    owner: "이도윤",
    initials: "이",
    status: "진행 중",
    start: "10.10",
    end: "10.21",
    progress: 35,
  },
  {
    id: 4,
    group: "execute",
    title: "점검 체크리스트 작성",
    owner: "김현우",
    initials: "김",
    status: "진행 중",
    start: "10.10",
    end: "10.14",
    progress: 55,
    parentId: 3,
  },
  {
    id: 5,
    group: "execute",
    title: "센서 데이터 정합성 확인",
    owner: "최지우",
    initials: "최",
    status: "대기",
    start: "10.15",
    end: "10.18",
    progress: 0,
    parentId: 3,
  },
  {
    id: 6,
    group: "finish",
    title: "운영 매뉴얼 배포",
    owner: "박서연",
    initials: "박",
    status: "대기",
    start: "10.22",
    end: "10.25",
    progress: 0,
  },
  {
    id: 7,
    group: "finish",
    title: "개선 결과 리뷰",
    owner: "이도윤",
    initials: "이",
    status: "대기",
    start: "10.28",
    end: "10.30",
    progress: 0,
  },
]

const initialBoards: Board[] = [
  {
    id: "facility",
    title: "설비 개선 프로젝트",
    favorite: true,
    color: "bg-blue-400",
  },
  {
    id: "weekly",
    title: "팀 주간 업무",
    favorite: true,
    color: "bg-violet-400",
  },
  {
    id: "meeting",
    title: "회의 후속 업무",
    favorite: false,
    color: "bg-amber-400",
  },
  {
    id: "issues",
    title: "이슈 관리",
    favorite: false,
    color: "bg-rose-400",
  },
]

const statusStyles: Record<Status, string> = {
  대기: "bg-slate-100 text-slate-600",
  "진행 중": "bg-blue-50 text-blue-700",
  검토: "bg-amber-50 text-amber-700",
  완료: "bg-emerald-50 text-emerald-700",
}

const statusOrder: Status[] = ["대기", "진행 중", "검토", "완료"]

function Icon({
  name,
  className = "size-5",
}: {
  name: IconName
  className?: string
}) {
  const common = {
    className,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  }
  const paths: Record<IconName, React.ReactNode> = {
    activity: (
      <>
        <path d="M3 12h4l2-7 4 14 2-7h6" />
      </>
    ),
    board: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M9 4v16M15 4v16" />
      </>
    ),
    calendar: (
      <>
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M16 3v4M8 3v4M3 10h18" />
      </>
    ),
    check: (
      <>
        <path d="m5 12 4 4L19 6" />
      </>
    ),
    chevron: (
      <>
        <path d="m9 18 6-6-6-6" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    dots: (
      <>
        <circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" />
        <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
        <circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" />
      </>
    ),
    filter: (
      <>
        <path d="M4 6h16M7 12h10M10 18h4" />
      </>
    ),
    gantt: (
      <>
        <path d="M4 6h7v4H4zM9 14h11v4H9z" />
      </>
    ),
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    home: (
      <>
        <path d="m3 11 9-8 9 8" />
        <path d="M5 10v10h14V10M9 20v-6h6v6" />
      </>
    ),
    inbox: (
      <>
        <path d="M4 5h16l1 14H3L4 5Z" />
        <path d="M3.5 14h5l1.5 2h4l1.5-2h5" />
      </>
    ),
    menu: (
      <>
        <path d="M4 7h16M4 12h16M4 17h16" />
      </>
    ),
    plus: (
      <>
        <path d="M12 5v14M5 12h14" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-4-4" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H3v-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6V3h4v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
      </>
    ),
    star: (
      <>
        <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-2.9-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3Z" />
      </>
    ),
    table: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M3 10h18M8 4v16" />
      </>
    ),
    team: (
      <>
        <circle cx="9" cy="9" r="3" />
        <circle cx="17" cy="8" r="2" />
        <path d="M3 20c.5-4 2.5-6 6-6s5.5 2 6 6M15 13c3.5 0 5.5 1.7 6 5" />
      </>
    ),
  }
  return <svg {...common}>{paths[name]}</svg>
}

function Sidebar({
  open,
  onClose,
  boards,
  activeBoard,
  onSelectBoard,
  onAddBoard,
}: {
  open: boolean
  onClose: () => void
  boards: Board[]
  activeBoard: string
  onSelectBoard: (id: string) => void
  onAddBoard: (title: string) => void
}) {
  const [isAdding, setIsAdding] = useState(false)
  const [newBoardTitle, setNewBoardTitle] = useState("")
  const favorites = boards.filter((board) => board.favorite)

  const submitBoard = () => {
    const title = newBoardTitle.trim()
    if (!title) return
    onAddBoard(title)
    setNewBoardTitle("")
    setIsAdding(false)
  }

  const renderBoard = (board: Board, favorite = false) => (
    <button
      key={`${favorite ? "favorite" : "board"}-${board.id}`}
      onClick={() => {
        onSelectBoard(board.id)
        onClose()
      }}
      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition ${
        activeBoard === board.id
          ? "bg-slate-900 font-medium text-white shadow-sm"
          : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
      }`}
    >
      {favorite ? (
        <Icon
          name="star"
          className={`size-3.5 ${
            activeBoard === board.id
              ? "fill-current text-amber-400"
              : "fill-current text-amber-400"
          }`}
        />
      ) : (
        <span className={`size-2 rounded-full ${board.color}`} />
      )}
      <span className="truncate">{board.title}</span>
    </button>
  )

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-slate-950/30 lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-16 items-center border-b border-slate-100 px-5">
          <div className="flex size-9 items-center justify-center rounded-xl bg-slate-900 text-white">
            <Icon name="activity" />
          </div>
          <div className="ml-3">
            <div className="text-sm font-bold tracking-tight text-slate-950">
              Factory Flow
            </div>
            <div className="text-[11px] text-slate-400">통합 업무 공간</div>
          </div>
          <button
            className="ml-auto text-slate-400 lg:hidden"
            onClick={onClose}
            aria-label="사이드바 닫기"
          >
            <Icon name="menu" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-5">
          <div className="space-y-1">
            <SidebarItem icon="home" label="홈" />
            <SidebarItem icon="inbox" label="내 업무" badge="5" />
            <SidebarItem icon="grid" label="전체 솔루션" />
          </div>

          {favorites.length > 0 && (
            <>
              <div className="mt-7 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                즐겨찾기
              </div>
              <div className="mt-2 space-y-1">
                {favorites.map((board) => renderBoard(board, true))}
              </div>
            </>
          )}

          <div className="mt-7 flex items-center justify-between px-3">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              내 보드
            </span>
            <button
              className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              onClick={() => setIsAdding(true)}
              aria-label="보드 추가"
            >
              <Icon name="plus" className="size-4" />
            </button>
          </div>
          <div className="mt-2 space-y-1">
            {boards.map((board) => renderBoard(board))}
            {isAdding && (
              <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 py-2">
                <span className="size-2 shrink-0 rounded-full bg-blue-500" />
                <input
                  autoFocus
                  value={newBoardTitle}
                  onChange={(event) => setNewBoardTitle(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") event.currentTarget.blur()
                    if (event.key === "Escape") {
                      setNewBoardTitle("")
                      setIsAdding(false)
                    }
                  }}
                  onBlur={() => {
                    if (newBoardTitle.trim()) submitBoard()
                    else setIsAdding(false)
                  }}
                  className="min-w-0 flex-1 bg-transparent text-sm text-slate-800 outline-none"
                  placeholder="보드 이름 입력"
                />
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-slate-100 p-3">
          <button className="flex w-full items-center gap-3 rounded-xl p-2 text-left hover:bg-slate-50">
            <div className="flex size-9 items-center justify-center rounded-full bg-warm-gray text-sm font-bold text-indigo-slate">
              김
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-slate-800">
                김현우
              </div>
              <div className="truncate text-xs text-slate-400">생산관리팀</div>
            </div>
            <Icon name="settings" className="size-4 text-slate-400" />
          </button>
        </div>
      </aside>
    </>
  )
}

function SidebarItem({
  icon,
  label,
  badge,
}: {
  icon: IconName
  label: string
  badge?: string
}) {
  return (
    <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-500 transition hover:bg-slate-50 hover:text-slate-900">
      <Icon name={icon} className="size-4.5" />
      <span>{label}</span>
      {badge && (
        <span className="ml-auto rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-700">
          {badge}
        </span>
      )}
    </button>
  )
}

function StatusButton({
  status,
  onChange,
}: {
  status: Status
  onChange: () => void
}) {
  return (
    <button
      onClick={onChange}
      className={`inline-flex min-w-20 items-center justify-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition hover:brightness-95 ${statusStyles[status]}`}
    >
      <span
        className={`size-1.5 rounded-full ${
          status === "완료"
            ? "bg-emerald-500"
            : status === "진행 중"
              ? "bg-blue-500"
              : status === "검토"
                ? "bg-amber-500"
                : "bg-slate-400"
        }`}
      />
      {status}
    </button>
  )
}

function TableView({
  groups,
  tasks,
  collapsed,
  editingGroupId,
  onToggleGroup,
  onStatus,
  onAdd,
  onAddSubtask,
  onRenameGroup,
  onRenameTask,
  onEditingGroup,
}: {
  groups: Group[]
  tasks: Task[]
  collapsed: GroupId[]
  editingGroupId: GroupId | null
  onToggleGroup: (group: GroupId) => void
  onStatus: (id: number) => void
  onAdd: (group: GroupId) => number
  onAddSubtask: (group: GroupId, parentId: number) => number
  onRenameGroup: (id: GroupId, title: string) => void
  onRenameTask: (id: number, title: string) => void
  onEditingGroup: (id: GroupId | null) => void
}) {
  const [editingTaskId, setEditingTaskId] = useState<number | null>(null)

  return (
    <div className="space-y-4">
      {groups.map((group) => {
        const groupTasks = tasks.filter((task) => task.group === group.id)
        const orderedTasks = groupTasks
          .filter((task) => !task.parentId)
          .flatMap((task) => [
            task,
            ...groupTasks.filter((child) => child.parentId === task.id),
          ])
          .concat(
            groupTasks.filter(
              (task) =>
                task.parentId &&
                !groupTasks.some((parent) => parent.id === task.parentId),
            ),
          )
        const isCollapsed = collapsed.includes(group.id)
        return (
          <section
            key={group.id}
            className="overflow-hidden rounded-2xl border border-rice-paper bg-pure-white shadow-sm"
          >
            <div className="flex w-full items-center gap-3 border-b border-slate-100 px-5 py-4 hover:bg-slate-50/70">
              <span className={`h-5 w-1 rounded-full ${group.color}`} />
              <button
                onClick={() => onToggleGroup(group.id)}
                className="rounded p-0.5 hover:bg-slate-100"
                aria-label={`${group.title} ${isCollapsed ? "펼치기" : "접기"}`}
              >
                <Icon
                  name="chevron"
                  className={`size-4 text-slate-400 transition ${
                    isCollapsed ? "" : "rotate-90"
                  }`}
                />
              </button>
              {editingGroupId === group.id ? (
                <input
                  autoFocus
                  value={group.title}
                  onChange={(event) =>
                    onRenameGroup(group.id, event.target.value)
                  }
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === "Escape")
                      onEditingGroup(null)
                  }}
                  onBlur={() => onEditingGroup(null)}
                  className={`min-w-0 flex-1 bg-transparent text-sm font-bold outline-none ${group.text}`}
                />
              ) : (
                <button
                  onClick={() => onEditingGroup(group.id)}
                  className={`min-w-0 truncate rounded px-1 py-0.5 text-left text-sm font-bold hover:bg-slate-100 ${group.text}`}
                  title="클릭하여 그룹 이름 수정"
                >
                  {group.title}
                </button>
              )}
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">
                {groupTasks.length}
              </span>
              <Icon name="dots" className="ml-auto size-4 text-slate-300" />
            </div>
            {!isCollapsed && (
              <>
                <div className="hidden grid-cols-[minmax(260px,1.7fr)_150px_120px_150px_160px_64px] border-b border-slate-100 bg-slate-50/70 px-5 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400 md:grid">
                  <span>업무명</span>
                  <span>담당자</span>
                  <span>상태</span>
                  <span>일정</span>
                  <span>진행률</span>
                  <span />
                </div>
                <div className="divide-y divide-slate-100">
                  {orderedTasks.map((task) => (
                    <div
                      key={task.id}
                      className="group grid gap-3 px-5 py-4 transition hover:bg-slate-50/80 md:grid-cols-[minmax(260px,1.7fr)_150px_120px_150px_160px_64px] md:items-center md:gap-0"
                    >
                      <div
                        className={`flex min-w-0 items-center gap-3 ${
                          task.parentId ? "md:pl-6" : ""
                        }`}
                      >
                        {task.parentId && (
                          <span className="hidden h-5 w-3 rounded-bl-lg border-b border-l border-slate-300 md:block" />
                        )}
                        <button
                          className={`flex size-5 shrink-0 items-center justify-center rounded-md border transition ${
                            task.status === "완료"
                              ? "border-emerald-500 bg-emerald-500 text-white"
                              : "border-slate-300 text-transparent hover:border-blue-500"
                          }`}
                          onClick={() => onStatus(task.id)}
                          aria-label={`${task.title} 상태 변경`}
                        >
                          <Icon name="check" className="size-3.5" />
                        </button>
                        {!task.parentId && (
                          <button
                            onClick={() => {
                              const id = onAddSubtask(group.id, task.id)
                              setEditingTaskId(id)
                            }}
                            className="flex size-6 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400 transition hover:border-blue-500 hover:bg-blue-50 hover:text-blue-700"
                            aria-label={`${task.title}에 하위 업무 추가`}
                            title="하위 업무 추가"
                          >
                            <Icon name="plus" className="size-3.5" />
                          </button>
                        )}
                        {editingTaskId === task.id ? (
                          <input
                            autoFocus
                            value={task.title}
                            onChange={(event) =>
                              onRenameTask(task.id, event.target.value)
                            }
                            onKeyDown={(event) => {
                              if (
                                event.key === "Enter" ||
                                event.key === "Escape"
                              )
                                setEditingTaskId(null)
                            }}
                            onBlur={() => setEditingTaskId(null)}
                            className="min-w-0 flex-1 bg-transparent text-sm font-medium text-slate-800 outline-none"
                          />
                        ) : (
                          <button
                            onClick={() => setEditingTaskId(task.id)}
                            className="min-w-0 truncate text-left text-sm font-medium text-slate-800 hover:underline"
                            title="클릭하여 업무 이름 수정"
                          >
                            {task.title}
                          </button>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="flex size-7 items-center justify-center rounded-full bg-slate-800 text-[11px] font-bold text-white">
                          {task.initials}
                        </div>
                        <span className="text-xs text-slate-600">
                          {task.owner}
                        </span>
                      </div>
                      <div>
                        <StatusButton
                          status={task.status}
                          onChange={() => onStatus(task.id)}
                        />
                      </div>
                      <div className="flex items-center gap-1.5 text-xs text-slate-500">
                        <Icon
                          name="calendar"
                          className="size-3.5 text-slate-400"
                        />
                        {task.start} – {task.end}
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className={`h-full rounded-full ${
                              task.progress === 100
                                ? "bg-emerald-500"
                                : "bg-blue-500"
                            }`}
                            style={{ width: `${task.progress}%` }}
                          />
                        </div>
                        <span className="w-8 text-right text-xs font-medium text-slate-500">
                          {task.progress}%
                        </span>
                      </div>
                      <Icon
                        name="dots"
                        className="hidden size-4 text-slate-300 md:block"
                      />
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => setEditingTaskId(onAdd(group.id))}
                  className="flex w-full items-center gap-2 border-t border-slate-100 px-5 py-3 text-left text-xs font-medium text-slate-400 hover:bg-slate-50 hover:text-blue-600"
                >
                  <Icon name="plus" className="size-4" />
                  업무 추가
                </button>
              </>
            )}
          </section>
        )
      })}
    </div>
  )
}

function KanbanView({
  tasks,
  onStatus,
}: {
  tasks: Task[]
  onStatus: (id: number) => void
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {statusOrder.map((status) => {
        const statusTasks = tasks.filter((task) => task.status === status)
        return (
          <section key={status} className="rounded-2xl bg-slate-100/80 p-3">
            <div className="mb-3 flex items-center px-1">
              <span
                className={`size-2 rounded-full ${
                  status === "완료"
                    ? "bg-emerald-500"
                    : status === "진행 중"
                      ? "bg-blue-500"
                      : status === "검토"
                        ? "bg-amber-500"
                        : "bg-slate-400"
                }`}
              />
              <span className="ml-2 text-sm font-bold text-slate-700">
                {status}
              </span>
              <span className="ml-auto text-xs text-slate-400">
                {statusTasks.length}
              </span>
            </div>
            <div className="space-y-2">
              {statusTasks.map((task) => (
                <button
                  key={task.id}
                  onClick={() => onStatus(task.id)}
                  className="w-full rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
                >
                  <div className="text-sm font-semibold leading-5 text-slate-800">
                    {task.title}
                  </div>
                  <div className="mt-4 flex items-center justify-between">
                    <span className="flex items-center gap-1 text-[11px] text-slate-400">
                      <Icon name="clock" className="size-3.5" />
                      {task.end}
                    </span>
                    <span className="flex size-7 items-center justify-center rounded-full bg-slate-800 text-[10px] font-bold text-white">
                      {task.initials}
                    </span>
                  </div>
                </button>
              ))}
              <button className="flex w-full items-center gap-1 px-2 py-2 text-xs font-medium text-slate-400 hover:text-slate-700">
                <Icon name="plus" className="size-3.5" />
                업무 추가
              </button>
            </div>
          </section>
        )
      })}
    </div>
  )
}

function EmptyView({ type }: { type: "calendar" | "gantt" }) {
  return (
    <div className="flex min-h-96 flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white text-center">
      <div className="flex size-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
        <Icon name={type} className="size-7" />
      </div>
      <div className="mt-4 text-base font-bold text-slate-800">
        {type === "calendar" ? "캘린더 보기" : "간트 보기"}
      </div>
      <p className="mt-2 text-sm text-slate-400">
        업무 일정을 시각화할 준비가 되었습니다.
      </p>
      <button className="mt-5 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">
        보기 설정
      </button>
    </div>
  )
}

export default function App() {
  const [tasks, setTasks] = useState(initialTasks)
  const [groups, setGroups] = useState(initialGroups)
  const [editingGroupId, setEditingGroupId] = useState<GroupId | null>(null)
  const [boards, setBoards] = useState(initialBoards)
  const [activeBoardId, setActiveBoardId] = useState("facility")
  const [view, setView] = useState<"table" | "board" | "calendar" | "gantt">(
    "table",
  )
  const [query, setQuery] = useState("")
  const [mineOnly, setMineOnly] = useState(false)
  const [collapsed, setCollapsed] = useState<GroupId[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const activeBoard =
    boards.find((board) => board.id === activeBoardId) ?? boards[0]

  const filteredTasks = useMemo(
    () =>
      tasks.filter((task) => {
        const matchesQuery =
          task.title.includes(query) || task.owner.includes(query)
        return matchesQuery && (!mineOnly || task.owner === "김현우")
      }),
    [tasks, query, mineOnly],
  )

  const completed = tasks.filter((task) => task.status === "완료").length
  const inProgress = tasks.filter(
    (task) => task.status === "진행 중" || task.status === "검토",
  ).length
  const overallProgress = Math.round(
    tasks.reduce((sum, task) => sum + task.progress, 0) / tasks.length,
  )

  const cycleStatus = (id: number) => {
    setTasks((current) =>
      current.map((task) => {
        if (task.id !== id) return task
        const nextStatus =
          statusOrder[
            (statusOrder.indexOf(task.status) + 1) % statusOrder.length
          ]
        const progress =
          nextStatus === "완료"
            ? 100
            : nextStatus === "진행 중"
              ? Math.max(task.progress, 25)
              : nextStatus === "검토"
                ? Math.max(task.progress, 80)
                : 0
        return { ...task, status: nextStatus, progress }
      }),
    )
  }

  const addTask = (group: GroupId) => {
    const id = Date.now()
    setTasks((current) => [
      ...current,
      {
        id,
        group,
        title: "새 업무",
        owner: "김현우",
        initials: "김",
        status: "대기",
        start: "10.24",
        end: "10.28",
        progress: 0,
      },
    ])
    return id
  }

  const addSubtask = (group: GroupId, parentId: number) => {
    const id = Date.now()
    setTasks((current) => [
      ...current,
      {
        id,
        group,
        parentId,
        title: "새 하위 업무",
        owner: "김현우",
        initials: "김",
        status: "대기",
        start: "10.24",
        end: "10.28",
        progress: 0,
      },
    ])
    return id
  }

  const addGroup = () => {
    const id = `group-${Date.now()}`
    const groupColors = [
      { color: "bg-blue-500", text: "text-blue-700" },
      { color: "bg-violet-500", text: "text-violet-700" },
      { color: "bg-emerald-500", text: "text-emerald-700" },
      { color: "bg-amber-500", text: "text-amber-700" },
    ]
    const tone = groupColors[groups.length % groupColors.length]
    setGroups((current) => [...current, { id, title: "새 그룹", ...tone }])
    setEditingGroupId(id)
    setCollapsed((current) => current.filter((item) => item !== id))
  }

  const addBoard = (title: string) => {
    const id = `board-${Date.now()}`
    const colors = [
      "bg-blue-400",
      "bg-violet-400",
      "bg-amber-400",
      "bg-rose-400",
    ]
    setBoards((current) => [
      ...current,
      {
        id,
        title,
        favorite: false,
        color: colors[current.length % colors.length],
      },
    ])
    setActiveBoardId(id)
  }

  const toggleFavorite = () => {
    setBoards((current) =>
      current.map((board) =>
        board.id === activeBoardId
          ? { ...board, favorite: !board.favorite }
          : board,
      ),
    )
  }

  const tabs = [
    { id: "table" as const, label: "메인 테이블", icon: "table" as const },
    { id: "board" as const, label: "칸반", icon: "board" as const },
    { id: "calendar" as const, label: "캘린더", icon: "calendar" as const },
    { id: "gantt" as const, label: "간트", icon: "gantt" as const },
  ]

  return (
    <div className="flex min-h-screen bg-porcelain font-sans text-deep-ink">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        boards={boards}
        activeBoard={activeBoardId}
        onSelectBoard={setActiveBoardId}
        onAddBoard={addBoard}
      />
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-16 items-center border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:px-7">
          <button
            className="mr-3 rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
            onClick={() => setSidebarOpen(true)}
            aria-label="사이드바 열기"
          >
            <Icon name="menu" />
          </button>
          <div className="hidden items-center gap-2 text-xs text-slate-400 sm:flex">
            <span>프로젝트 보드</span>
            <Icon name="chevron" className="size-3" />
            <span className="font-medium text-slate-600">
              {activeBoard.title}
            </span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button className="hidden items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 sm:flex">
              <Icon name="team" className="size-4" />
              공유
            </button>
            <button className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
              <Icon name="search" className="size-5" />
            </button>
            <button className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
              <Icon name="dots" className="size-5" />
            </button>
          </div>
        </header>

        <main className="mx-auto max-w-[1500px] px-4 py-7 md:px-8 md:py-9">
          <section className="flex flex-col justify-between gap-6 xl:flex-row xl:items-end">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold tracking-tight text-slate-950 md:text-3xl">
                  {activeBoard.title}
                </h1>
                <button
                  onClick={toggleFavorite}
                  className={`rounded-lg p-1.5 transition ${
                    activeBoard.favorite
                      ? "text-amber-400"
                      : "text-slate-300 hover:text-slate-500"
                  }`}
                  aria-label="즐겨찾기"
                >
                  <Icon
                    name="star"
                    className={`size-5 ${
                      activeBoard.favorite ? "fill-current" : ""
                    }`}
                  />
                </button>
              </div>
              <p className="mt-2 text-sm text-slate-500">
                설비 점검부터 개선 완료까지, 모든 업무 흐름을 한곳에서
                관리합니다.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:flex">
              <Summary label="전체 업무" value={tasks.length} />
              <Summary label="진행 중" value={inProgress} tone="blue" />
              <Summary label="완료" value={completed} tone="green" />
              <div className="min-w-40 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span>전체 진행률</span>
                  <span className="font-bold text-slate-700">
                    {overallProgress}%
                  </span>
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-blue-500"
                    style={{ width: `${overallProgress}%` }}
                  />
                </div>
              </div>
            </div>
          </section>

          <div className="mt-7 flex gap-1 overflow-x-auto border-b border-slate-200">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setView(tab.id)}
                className={`relative flex shrink-0 items-center gap-2 px-4 py-3 text-sm font-medium transition ${
                  view === tab.id
                    ? "text-slate-950"
                    : "text-slate-400 hover:text-slate-700"
                }`}
              >
                <Icon name={tab.icon} className="size-4" />
                {tab.label}
                {view === tab.id && (
                  <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-blue-600" />
                )}
              </button>
            ))}
          </div>

          <section className="my-5 flex flex-col gap-3 lg:flex-row lg:items-center">
            <button
              onClick={() => addTask("plan")}
              className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
            >
              <Icon name="plus" className="size-4" />새 업무
            </button>
            <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-slate-400 shadow-sm lg:max-w-xs">
              <Icon name="search" className="size-4" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="min-w-0 flex-1 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
                placeholder="업무 또는 담당자 검색"
              />
            </label>
            <button
              onClick={() => setMineOnly((current) => !current)}
              className={`flex items-center justify-center gap-2 rounded-xl border px-3.5 py-2.5 text-sm font-medium transition ${
                mineOnly
                  ? "border-blue-200 bg-blue-50 text-blue-700"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              <Icon name="team" className="size-4" />내 업무만
            </button>
            <button className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
              <Icon name="filter" className="size-4" />
              필터
            </button>
            <div className="hidden flex-1 lg:block" />
            <span className="text-xs text-slate-400">
              표시 중 {filteredTasks.length}개
            </span>
          </section>

          {view === "table" && (
            <>
              <TableView
                groups={groups}
                tasks={filteredTasks}
                collapsed={collapsed}
                editingGroupId={editingGroupId}
                onEditingGroup={setEditingGroupId}
                onToggleGroup={(group) =>
                  setCollapsed((current) =>
                    current.includes(group)
                      ? current.filter((item) => item !== group)
                      : [...current, group],
                  )
                }
                onStatus={cycleStatus}
                onAdd={addTask}
                onAddSubtask={addSubtask}
                onRenameGroup={(id, title) =>
                  setGroups((current) =>
                    current.map((group) =>
                      group.id === id ? { ...group, title } : group,
                    ),
                  )
                }
                onRenameTask={(id, title) =>
                  setTasks((current) =>
                    current.map((task) =>
                      task.id === id ? { ...task, title } : task,
                    ),
                  )
                }
              />
              <button
                onClick={addGroup}
                className="mt-4 flex w-full items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-white/60 px-5 py-4 text-left text-sm font-semibold text-slate-500 transition hover:border-slate-400 hover:bg-white hover:text-slate-900"
              >
                <span className="flex size-7 items-center justify-center rounded-lg bg-slate-100">
                  <Icon name="plus" className="size-4" />
                </span>
                새 그룹 추가하기
              </button>
            </>
          )}
          {view === "board" && (
            <KanbanView tasks={filteredTasks} onStatus={cycleStatus} />
          )}
          {view === "calendar" && <EmptyView type="calendar" />}
          {view === "gantt" && <EmptyView type="gantt" />}
        </main>
      </div>
    </div>
  )
}

function Summary({
  label,
  value,
  tone = "slate",
}: {
  label: string
  value: number
  tone?: "slate" | "blue" | "green"
}) {
  const styles =
    tone === "blue"
      ? "text-blue-600"
      : tone === "green"
        ? "text-emerald-600"
        : "text-slate-900"
  return (
    <div className="min-w-24 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="text-[11px] text-slate-400">{label}</div>
      <div className={`mt-0.5 text-xl font-bold ${styles}`}>{value}</div>
    </div>
  )
}
