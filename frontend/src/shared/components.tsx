import {
  useEffect,
  useId,
  useState,
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
}: {
  reason: string;
  to: string;
  action: string;
}) {
  return (
    <div className="empty">
      <p>{reason}</p>
      <Link to={to}>{action} →</Link>
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
}: {
  id: string;
  title: string;
  subtitle?: string;
  help?: string;
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
      <Link
        className="help-link"
        aria-label={`${title} 도움말`}
        to={`/help/${help}`}
      >
        ? 도움말
      </Link>
    </div>
  );
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
};
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
}: {
  rows: T[];
  columns: Column<T>[];
  caption: string;
  offset: number;
  total: number;
  limit: number;
  onPage: (offset: number) => void;
  empty?: ReactNode;
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
  // 숫자 열은 오른쪽 정렬한다. id 열은 행 작업(관리) 열이므로 제외한다.
  const isNumber = (v: unknown) =>
    typeof v === "number" ||
    (typeof v === "string" && /^-?\d+(\.\d+)?$/.test(v));
  const numeric = new Set(
    columns
      .filter(
        (c) =>
          c.key !== "id" &&
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
    <section>
      <div className="table-toolbar">
        <p>
          총 <strong>{total.toLocaleString()}</strong>건 · 열 정렬은 현재 페이지
          기준
        </p>
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
                    // 렌더러가 없는 긴 글자는 줄이고 전체 값은 title로 보여 준다.
                    const long = !c.render && text.length > 28;
                    return (
                      <td
                        key={c.key}
                        className={
                          numeric.has(c.key) ? "num" : long ? "clip" : undefined
                        }
                        title={long ? text : undefined}
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
      {/* 한 페이지뿐이면 페이지 이동을 숨긴다. */}
      {total > limit && (
        <nav className="pagination" aria-label={`${caption} 페이지`}>
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
      )}
    </section>
  );
}
