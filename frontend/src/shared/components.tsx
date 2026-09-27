import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  type InputHTMLAttributes,
} from "react";
import { Link } from "react-router-dom";
import { ApiError } from "./api";
export function Loading({
  label = "불러오고 있습니다",
  delay = 0,
}: {
  label?: string;
  delay?: number;
}) {
  const [visible, setVisible] = useState(delay === 0);
  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(true), delay);
    return () => window.clearTimeout(timer);
  }, [delay]);
  return visible ? (
    <p className="loading" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </p>
  ) : null;
}
export function EmptyState({
  reason,
  to,
  action,
  onAction,
}: {
  reason: string;
  to?: string;
  action: string;
  /** 링크 대신 같은 화면의 행동(예: 등록 패널 열기)을 실행한다. */
  onAction?: () => void;
}) {
  return (
    <div className="empty">
      <p>{reason}</p>
      {onAction ? (
        <button type="button" className="link-button" onClick={onAction}>
          {action} →
        </button>
      ) : (
        <Link to={to ?? "/home"}>{action} →</Link>
      )}
    </div>
  );
}
export function ErrorNotice({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  if (!error) return null;
  const issue =
    error instanceof ApiError
      ? error.error
      : { code: "UNEXPECTED_ERROR", message: "요청을 처리하지 못했습니다." };
  return (
    <div className="notice" role="alert">
      <strong>{issue.message}</strong>
      <small>{issue.code}</small>
      {issue.details && Object.keys(issue.details).length > 0 && (
        <dl>
          {Object.entries(issue.details).map(([key, value]) => (
            <div key={key}>
              <dt>
                {key === "references"
                  ? "참조처별 건수"
                  : key === "fields"
                    ? "입력 항목"
                    : key === "conflicts"
                      ? "겹치는 기록"
                      : key}
              </dt>
              <dd>
                {key === "references" && Array.isArray(value) ? (
                  <ul>
                    {(value as { label: string; count: number }[]).map((r) => (
                      <li key={r.label}>
                        {r.label} {r.count.toLocaleString()}건
                      </li>
                    ))}
                  </ul>
                ) : key === "conflicts" && Array.isArray(value) ? (
                  <ul>
                    {(value as Record<string, unknown>[]).map((c, i) => (
                      <li key={String(c.id ?? i)}>
                        {Object.entries(c)
                          .filter(([k]) => k !== "id")
                          .map(([, v]) => String(v ?? "계속"))
                          .join(" · ")}
                      </li>
                    ))}
                  </ul>
                ) : typeof value === "object" ? (
                  JSON.stringify(value)
                ) : (
                  String(value)
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {retry && (
        <button className="secondary" onClick={retry}>
          다시 시도
        </button>
      )}
    </div>
  );
}
export function SessionExpired({ workspace = false }: { workspace?: boolean }) {
  return (
    <section className="panel">
      <h1>
        {workspace
          ? "게스트 공간 이용이 만료되었습니다"
          : "세션이 만료되었습니다"}
      </h1>
      <p>저장되지 않은 입력은 저장되지 않았습니다. 다시 접속해 주세요.</p>
      <Link className="button" to="/">
        진입 화면으로
      </Link>
      <Link className="text-link" to="/help/common">
        공통 이용 안내
      </Link>
    </section>
  );
}
export function Field({
  label,
  error,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        {...props}
        id={id}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-error` : undefined}
      />
      {error && <small id={`${id}-error`}>{error}</small>}
    </div>
  );
}
export function Badge({
  children,
  tone = "normal",
}: {
  children: ReactNode;
  tone?: "normal" | "warning" | "issue";
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function PageTitle({
  id,
  title,
  subtitle,
  help = `portal/${id.toLowerCase()}`,
  actions,
}: {
  id: string;
  title: string;
  subtitle?: string;
  help?: string;
  /** 화면의 주요 행동(등록 버튼·조회 월 등). 도움말 왼쪽에 둔다. */
  actions?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <div className="page-title-row">
          <h1>{title}</h1>
          <span className="page-id">{id}</span>
        </div>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <div className="page-actions">
        {actions}
        <Link
          className="help-link"
          aria-label={`${title} 도움말`}
          to={`/help/${help}`}
        >
          ? 도움말
        </Link>
      </div>
    </div>
  );
}
/** 목록에서 고른 상세가 화면 아래쪽(60% 밑)에 열리면 보이도록 스크롤한다. 이미 보이면 움직이지 않는다.
 *  when은 선택한 행(또는 id). 행 객체면 id가 바뀔 때만 반응한다. */
export function RevealAnchor({ when }: { when: unknown }) {
  const ref = useRef<HTMLDivElement>(null);
  const key =
    when && typeof when === "object" && "id" in when
      ? (when as { id: unknown }).id
      : when;
  useEffect(() => {
    const el = ref.current;
    if (!key || !el) return;
    const top = el.getBoundingClientRect().top;
    if (top > window.innerHeight * 0.6 || top < 0)
      el.scrollIntoView?.({ block: "start", behavior: "smooth" });
  }, [key]);
  return <div ref={ref} className="reveal-anchor" aria-hidden="true" />;
}
export function NotFound() {
  return (
    <section className="panel">
      <span className="eyebrow">404 · NOT_FOUND</span>
      <h1>페이지를 찾을 수 없습니다</h1>
      <EmptyState
        reason="주소를 확인하거나 홈으로 이동해 주세요."
        to="/home"
        action="홈으로"
      />
    </section>
  );
}
export function LineIcon({ kind }: { kind: string }) {
  return (
    <svg
      width="38"
      height="38"
      viewBox="0 0 40 40"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      {kind === "mes" ? (
        <>
          <path d="M5 33V17l10 5V13l10 6V7h7v26H5Z" />
          <path d="M10 28h4m5 0h4m5 0h4" />
        </>
      ) : kind === "erp" ? (
        <>
          <rect x="9" y="5" width="23" height="30" rx="2" />
          <path d="M15 12h11M15 18h11M15 24h4m4 0h3M15 30h11" />
        </>
      ) : (
        <>
          <path d="m23 4-14 20h11l-3 12 15-21H21l2-11Z" />
        </>
      )}
    </svg>
  );
}
export type Column<T> = {
  key: keyof T & string;
  label: string;
  render?: (row: T) => ReactNode;
  /** 설명·메모처럼 줄바꿈해 읽는 열. 기본은 한 줄(수량·단위·배지·코드). */
  wrap?: boolean;
};
/** 날짜 범위. 칸이 좁으면 시작일과 "~ 종료일"이 두 줄로 나뉜다. 같은 날이면 하나만 쓴다. */
export function DateRange({ from, to }: { from: string; to: string }) {
  return from === to ? (
    <>{from}</>
  ) : (
    <span className="date-range">
      <span>{from}</span> <span>~ {to}</span>
    </span>
  );
}
export function Pagination({
  offset,
  total,
  limit,
  onPage,
  label,
}: {
  offset: number;
  total: number;
  limit: number;
  onPage: (offset: number) => void;
  label: string;
}) {
  // 한 페이지뿐이면 페이지 이동을 숨긴다.
  if (total <= limit) return null;
  return (
    <nav className="pagination" aria-label={label}>
      <button
        onClick={() => onPage(Math.max(0, offset - limit))}
        disabled={offset === 0}
      >
        이전
      </button>
      <span>
        {Math.floor(offset / limit) + 1} /{" "}
        {Math.max(1, Math.ceil(total / limit))}
      </span>
      <button
        onClick={() => onPage(offset + limit)}
        disabled={offset + limit >= total}
      >
        다음
      </button>
    </nav>
  );
}
export function csvText<T>(rows: T[], columns: Column<T>[]) {
  const cell = (value: unknown) => {
    const s = String(value ?? "");
    return `"${(/^[=+@\-\t\r]/.test(s) ? "'" + s : s).replaceAll('"', '""')}"`;
  };
  return (
    "\uFEFF" +
    [
      columns.map((c) => cell(c.label)).join(","),
      ...rows.map((r) => columns.map((c) => cell(r[c.key])).join(",")),
    ].join("\r\n")
  );
}
export function DataTable<T extends { id: number }>({
  rows,
  columns,
  caption,
  offset,
  total,
  limit,
  onPage,
  empty,
  leading,
}: {
  rows: T[];
  columns: Column<T>[];
  caption: string;
  offset: number;
  total: number;
  limit: number;
  onPage: (offset: number) => void;
  empty?: ReactNode;
  /** 결과 수 왼쪽에 둘 보기 전환 등. */
  leading?: ReactNode;
}) {
  const [sort, setSort] = useState<{ key: keyof T; desc: boolean }>();
  const ordered = [...rows].sort((a, b) =>
    !sort
      ? 0
      : (typeof a[sort.key] === "number" && typeof b[sort.key] === "number"
          ? Number(a[sort.key]) - Number(b[sort.key])
          : String(a[sort.key] ?? "").localeCompare(
              String(b[sort.key] ?? ""),
              "ko",
            )) * (sort.desc ? -1 : 1),
  );
  // 숫자 열은 오른쪽 정렬한다. id 열(행 작업)과 *Id 참조 열(이름으로 표시)은 제외한다.
  const isNumber = (v: unknown) =>
    typeof v === "number" ||
    (typeof v === "string" && /^-?\d+(\.\d+)?$/.test(v));
  const numeric = new Set(
    columns
      .filter(
        (c) =>
          c.key !== "id" &&
          !c.key.endsWith("Id") &&
          rows.some((r) => r[c.key] != null) &&
          rows.every((r) => r[c.key] == null || isNumber(r[c.key])),
      )
      .map((c) => c.key),
  );
  function download() {
    const url = URL.createObjectURL(
      new Blob([csvText(ordered, columns)], { type: "text/csv;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "factory-studio-records.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <section className="data-table fill">
      <div className="table-toolbar">
        <div className="table-toolbar-lead">
          {leading}
          <p>
            총 <strong>{total.toLocaleString()}</strong>건 · 열 정렬은 현재
            페이지 기준
          </p>
        </div>
        <button
          className="secondary"
          onClick={download}
          disabled={!rows.length}
        >
          현재 페이지 CSV
        </button>
      </div>
      {rows.length ? (
        <div className="table-scroll">
          <table>
            <caption>{caption}</caption>
            <thead>
              <tr>
                {columns.map((c) => (
                  <th
                    key={c.key}
                    scope="col"
                    className={numeric.has(c.key) ? "num" : undefined}
                    aria-sort={
                      sort?.key === c.key
                        ? sort.desc
                          ? "descending"
                          : "ascending"
                        : "none"
                    }
                  >
                    <button
                      onClick={() =>
                        setSort({
                          key: c.key,
                          desc: sort?.key === c.key && !sort.desc,
                        })
                      }
                    >
                      {c.label} <span>↕</span>
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ordered.map((row) => (
                <tr key={row.id}>
                  {columns.map((c) => {
                    const text = String(row[c.key] ?? "—");
                    // 렌더러가 없는 긴 글자는 줄인다. 칸에 포커스(탭·터치)하거나 올리면 전체 값이 펼쳐진다.
                    const long = !c.render && !c.wrap && text.length > 28;
                    return (
                      <td
                        key={c.key}
                        className={
                          numeric.has(c.key)
                            ? "num"
                            : c.wrap
                              ? "wrap"
                              : long
                                ? "clip"
                                : undefined
                        }
                        title={long ? text : undefined}
                        tabIndex={long ? 0 : undefined}
                      >
                        {c.render ? c.render(row) : text}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        (empty ?? (
          <EmptyState
            reason="아직 기록된 작업이 없습니다. 작업을 실행한 뒤 다시 확인할 수 있습니다."
            to="/home"
            action="앱 런처로"
          />
        ))
      )}
      <Pagination
        offset={offset}
        total={total}
        limit={limit}
        onPage={onPage}
        label={`${caption} 페이지`}
      />
    </section>
  );
}

/** 저장하지 않은 변경 보호. guard(action)은 변경이 없으면 바로 실행하고, 있으면 확인을 기다린다.
 *  변경이 있는 동안 새로고침·탭 닫기도 브라우저가 확인한다. */
export function useDiscardGuard(dirty: boolean) {
  const [pending, setPending] = useState<() => void>();
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  return {
    pending: !!pending,
    guard: (action: () => void) =>
      dirty ? setPending(() => action) : action(),
    discard: () => {
      setPending(undefined);
      pending?.();
    },
    keep: () => setPending(undefined),
  };
}
export type DiscardGuard = ReturnType<typeof useDiscardGuard>;
// 패널 겹침 기준. styles.css의 .form-panel 미디어 쿼리와 같다(기본 1599px, 넓은 패널 1919px).
const OVERLAY = "(max-width: 1599px)";
const OVERLAY_WIDE = "(max-width: 1919px)";
const FOCUSABLE =
  'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])';
const NO_GUARD: DiscardGuard = {
  pending: false,
  guard: (action) => action(),
  discard: () => {},
  keep: () => {},
};
/** 목록 옆 오른쪽 패널의 공통 틀(UI-02·UI-03). 열 때만 렌더링한다.
 *  넓은 화면은 목록 오른쪽에 붙고, 좁은 화면은 겹쳐 열린다(포커스 가둠·배경 클릭 닫기).
 *  열리면 첫 입력(없으면 닫기 버튼)으로, 닫히면 연 버튼으로 포커스가 돌아간다. Esc·✕·배경은 guard를 거쳐 닫는다. */
function SidePanel({
  title,
  onClose,
  onSubmit,
  guard = NO_GUARD,
  actions,
  wide = false,
  children,
}: {
  title: string;
  onClose: () => void;
  onSubmit?: (event: FormEvent) => void;
  guard?: DiscardGuard;
  actions?: ReactNode;
  wide?: boolean;
  children: ReactNode;
}) {
  const id = useId();
  const ref = useRef<HTMLElement>(null);
  const query = wide ? OVERLAY_WIDE : OVERLAY;
  const [overlay] = useState(() => window.matchMedia?.(query).matches ?? false);
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const body = ref.current?.querySelector(".form-panel-body");
    (
      body?.querySelector<HTMLElement>(
        "input:not(:disabled), select:not(:disabled), textarea:not(:disabled)",
      ) ?? ref.current?.querySelector<HTMLElement>("button")
    )?.focus();
    return () => {
      // 연 버튼이 목록 갱신으로 사라졌으면 본문으로 돌아간다.
      const back = opener?.isConnected
        ? opener
        : document.getElementById("main");
      back?.focus({ preventScroll: true });
    };
  }, []);
  useEffect(() => {
    if (guard.pending)
      ref.current?.querySelector<HTMLElement>("[data-keep]")?.focus();
  }, [guard.pending]);
  const requestClose = () => guard.guard(onClose);
  function onKeyDown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      e.stopPropagation();
      if (guard.pending) guard.keep();
      else requestClose();
      return;
    }
    if (e.key !== "Tab" || !window.matchMedia?.(query).matches) return;
    const items = [
      ...(ref.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []),
    ];
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last?.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first?.focus();
    }
  }
  const foot = guard.pending ? (
    <>
      <p role="alert">저장하지 않은 변경이 있습니다.</p>
      <button type="button" className="secondary" onClick={guard.discard}>
        변경 버리기
      </button>
      <button
        type="button"
        className="link-button"
        data-keep
        onClick={guard.keep}
      >
        계속 편집
      </button>
    </>
  ) : (
    actions
  );
  const inner = (
    <>
      <div className="form-panel-body">{children}</div>
      {foot && <div className="form-panel-foot">{foot}</div>}
    </>
  );
  return (
    <>
      <div
        className="form-panel-backdrop"
        aria-hidden="true"
        onClick={requestClose}
      />
      <section
        ref={ref}
        className={wide ? "form-panel wide" : "form-panel"}
        role="dialog"
        aria-modal={overlay || undefined}
        aria-labelledby={id}
        onKeyDown={onKeyDown}
      >
        <div className="form-panel-head">
          <h2 id={id}>{title}</h2>
          <button
            type="button"
            className="sidebar-toggle"
            aria-label="패널 닫기"
            onClick={requestClose}
          >
            ✕
          </button>
        </div>
        {onSubmit ? (
          <form onSubmit={onSubmit} aria-labelledby={id}>
            {inner}
          </form>
        ) : (
          <div className="form-panel-content">{inner}</div>
        )}
      </section>
    </>
  );
}
/** 등록·수정 패널(UI-02). 저장·취소는 actions, 미저장 보호는 guard. */
export function FormPanel(props: {
  title: string;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
  guard: DiscardGuard;
  actions: ReactNode;
  wide?: boolean;
  children: ReactNode;
}) {
  return <SidePanel {...props} />;
}
/** 읽기 전용 상세·부모-자식 상세·행 편집 패널(UI-03). 패널 자체는 폼이 아니다 —
 *  안의 편집 영역(행 편집기·전환 폼)은 각자 폼을 둔다. 편집 중 변경이 있으면 guard를 넘긴다.
 *  wide는 명세 여러 줄·자식 표처럼 넓은 내용(640px). 1920px 이상에서만 목록 옆에 붙는다. */
export function DetailPanel(props: {
  title: string;
  onClose: () => void;
  guard?: DiscardGuard;
  actions?: ReactNode;
  wide?: boolean;
  children: ReactNode;
}) {
  return <SidePanel {...props} />;
}
