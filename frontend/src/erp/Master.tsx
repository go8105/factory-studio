import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { useSession } from "../app/session";
import { api, ApiError, MutationKeys } from "../shared/api";
import {
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
export type Row = {
  id: number;
  [key: string]: string | number | boolean | null;
};
export type InputField = {
  key: string;
  label: string;
  type?: "text" | "number" | "checkbox" | "month" | "date";
  options?: [string, string][];
  nullable?: boolean;
  initial?: string | number | boolean | null;
  lookup?: { path: string; code: string; name: string };
  maxLength?: number;
};
export async function allRows(
  path: string,
  signal: AbortSignal,
): Promise<Row[]> {
  const rows: Row[] = [];
  for (let offset = 0; ; offset += 200) {
    const r = await api<Row[]>(`${path}?offset=${offset}&limit=200`, {
      signal,
    });
    rows.push(...r.data);
    if (rows.length >= (r.page?.total ?? rows.length)) return rows;
  }
}
export function Master({
  id,
  title,
  path,
  fields,
  extraColumns = [],
  columns: shown,
  readOnly = false,
  deletable = true,
  embedded = false,
  note,
  children,
}: {
  id: string;
  title: string;
  path: string;
  fields: InputField[];
  extraColumns?: InputField[];
  /** 표에 세울 입력 항목 키. 비우면 전부 — 상세가 많은 마스터는 표를 좁히고 패널에서 본다. */
  columns?: string[];
  readOnly?: boolean;
  /** 삭제가 없는 마스터(계정과목은 사용 여부만 끈다). 단추를 숨긴다. */
  deletable?: boolean;
  embedded?: boolean;
  note?: string;
  children?: ReactNode;
}) {
  const { session, fail } = useSession();
  const keys = useRef(new MutationKeys());
  const initial = () =>
    Object.fromEntries(
      fields.map((f) => [
        f.key,
        f.initial ?? (f.nullable ? null : f.type === "checkbox" ? true : ""),
      ]),
    ) as Omit<Row, "id">;
  const [rows, setRows] = useState<Row[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [editing, setEditing] = useState<Row | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [draft, setDraft] = useState(initial);
  const [lookups, setLookups] = useState<Record<string, Row[]>>({});
  const [error, setError] = useState<unknown>();
  const [saveError, setSaveError] = useState<unknown>();
  const [pending, setPending] = useState(false);
  const [deleting, setDeleting] = useState<Row>();
  const [done, setDone] = useState("");

  const dirty =
    panelOpen &&
    (editing
      ? Object.keys(draft).some((k) => draft[k] !== editing[k])
      : Object.entries(draft).some(([k, v]) => {
          const init = initial()[k];
          return v !== init && v !== "" && v !== null;
        }));
  const guard = useDiscardGuard(dirty);

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    api<Row[]>(`${path}?offset=${offset}&limit=20`, {
      signal: controller.signal,
    })
      .then((r) => {
        setRows(r.data);
        setTotal(r.page?.total ?? r.data.length);
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          setError(e);
          if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
        }
      });
    return () => controller.abort();
  }, [path, offset, reload]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all(
      fields
        .filter((f) => f.lookup)
        .map(
          async (f) =>
            [f.key, await allRows(f.lookup!.path, controller.signal)] as const,
        ),
    )
      .then((entries) => setLookups(Object.fromEntries(entries)))
      .catch((e) => {
        if (!controller.signal.aborted) {
          setError(e);
          if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
        }
      });
    return () => controller.abort();
  }, [fields, reload]);

  function openCreate() {
    setEditing(null);
    setDraft(initial());
    setSaveError(undefined);
    setDone("");
    setPanelOpen(true);
  }

  function edit(row: Row | null) {
    setEditing(row);
    setDraft(
      row
        ? Object.fromEntries(fields.map((f) => [f.key, row[f.key]]))
        : initial(),
    );
    setSaveError(undefined);
    setDone("");
    setPanelOpen(true);
  }

  function closePanel() {
    setPanelOpen(false);
    setEditing(null);
    setDraft(initial());
    setSaveError(undefined);
  }

  async function send(method: string, target: string, body?: unknown) {
    if (pending) return false;
    setPending(true);
    setSaveError(undefined);
    setDone("");
    const operation = `${method}:${target}:${JSON.stringify(body)}`;
    try {
      await api(target, {
        method,
        body,
        csrf: session?.csrfToken,
        key: keys.current.get(operation),
      });
      keys.current.complete(operation);
      setReload((n) => n + 1);
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status > 0 && e.status < 500)
        keys.current.complete(operation);
      setSaveError(e);
      if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      return false;
    } finally {
      setPending(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const body = editing
      ? Object.fromEntries(
          Object.entries(draft).filter(([k, v]) => editing[k] !== v),
        )
      : draft;
    if (editing && !Object.keys(body).length) {
      setDone("변경한 항목이 없습니다.");
      return;
    }
    if (
      await send(
        editing ? "PATCH" : "POST",
        editing ? `${path}/${editing.id}` : path,
        body,
      )
    ) {
      closePanel();
      setDone("저장했습니다.");
    }
  }

  if (
    error instanceof ApiError &&
    error.error.details?.reason === "MODULE_DISABLED"
  )
    return (
      <EmptyState
        reason="ERP를 사용하지 않도록 설정했습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );

  const problems =
    saveError instanceof ApiError
      ? ((saveError.error.details?.fields ?? {}) as Record<string, string>)
      : {};

  const columns: Column<Row>[] = [
    ...(shown ? fields.filter((f) => shown.includes(f.key)) : fields),
    ...extraColumns,
  ].map((f) => ({
    key: f.key,
    label: f.label,
    render: (r) => {
      const value = r[f.key];
      if (f.type === "checkbox") return value ? "사용" : "사용 안 함";
      if (f.lookup) {
        const row = lookups[f.key]?.find((x) => x.id === value);
        return row
          ? `${row[f.lookup.code]} · ${row[f.lookup.name]}`
          : String(value ?? "—");
      }
      return (
        f.options?.find(([k]) => k === String(value))?.[1] ??
        String(value ?? "—")
      );
    },
  }));

  if (!readOnly)
    columns.splice(1, 0, {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            disabled={pending}
            onClick={() => guard.guard(() => edit(r))}
          >
            수정
          </button>
          {deletable && (
            <button
              type="button"
              className="link-button"
              disabled={pending}
              onClick={() => {
                setDeleting(r);
                setSaveError(undefined);
              }}
            >
              삭제
            </button>
          )}
        </span>
      ),
    });

  const formPanel = panelOpen && !readOnly && (
    <FormPanel
      key={editing ? String(editing.id) : "new"}
      title={`${title} ${editing ? "수정" : "등록"}`}
      guard={guard}
      onClose={closePanel}
      onSubmit={(e) => void submit(e)}
      actions={
        <>
          <button type="submit" disabled={pending} aria-busy={pending}>
            {editing ? "저장" : "등록"}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => guard.guard(closePanel)}
          >
            취소
          </button>
        </>
      }
    >
      <ErrorNotice error={saveError} />
      <fieldset className="field" disabled={pending}>
        {fields.map((f) => {
          const error = problems[f.key] ?? problems[`body.${f.key}`];
          const inputId = `${id}-${f.key}`;
          if (f.options || f.lookup)
            return (
              <div className="field" key={f.key}>
                <label htmlFor={inputId}>{f.label}</label>
                <select
                  id={inputId}
                  required={!f.nullable}
                  aria-invalid={!!error}
                  aria-describedby={error ? `${inputId}-error` : undefined}
                  value={String(draft[f.key] ?? "")}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      [f.key]: f.lookup
                        ? e.target.value
                          ? Number(e.target.value)
                          : f.nullable
                            ? null
                            : ""
                        : e.target.value === "" && f.nullable
                          ? null
                          : e.target.value,
                    })
                  }
                >
                  <option value="">선택하세요</option>
                  {(
                    f.options ??
                    lookups[f.key]?.map((r) => [
                      String(r.id),
                      `${r[f.lookup!.code]} · ${r[f.lookup!.name]}`,
                    ]) ??
                    []
                  ).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
                {error && <small id={`${inputId}-error`}>{error}</small>}
              </div>
            );
          if (f.type === "checkbox")
            return (
              <div className="field" key={f.key}>
                <label className="inline-check" htmlFor={inputId}>
                  <input
                    id={inputId}
                    type="checkbox"
                    checked={Boolean(draft[f.key])}
                    onChange={(e) =>
                      setDraft({ ...draft, [f.key]: e.target.checked })
                    }
                  />
                  {f.label}
                </label>
                {error && <small>{error}</small>}
              </div>
            );
          return (
            <Field
              key={f.key}
              label={f.label}
              error={error}
              type={f.type ?? "text"}
              required={!f.nullable}
              maxLength={f.maxLength}
              min={f.type === "number" ? 0 : undefined}
              value={String(draft[f.key] ?? "")}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  [f.key]:
                    e.target.value === "" && f.nullable
                      ? null
                      : f.type === "number"
                        ? Number(e.target.value)
                        : e.target.value,
                })
              }
            />
          );
        })}
      </fieldset>
    </FormPanel>
  );

  const deletingDialog = deleting && (
    <section className="panel" aria-label="삭제 확인">
      <p>선택한 항목을 삭제할까요? 참조 중이면 삭제할 수 없습니다.</p>
      <button
        disabled={pending}
        onClick={async () => {
          if (await send("DELETE", `${path}/${deleting.id}`)) {
            if (editing?.id === deleting.id) edit(null);
            setDeleting(undefined);
            setOffset(0);
            setDone("삭제했습니다.");
          }
        }}
      >
        삭제 확인
      </button>
      <button disabled={pending} onClick={() => setDeleting(undefined)}>
        취소
      </button>
    </section>
  );

  if (embedded) {
    return (
      <div className="section-block">
        <div className="section-heading">
          <h2>{title}</h2>
          {!readOnly && (
            <button
              type="button"
              aria-pressed={panelOpen}
              onClick={() => guard.guard(openCreate)}
            >
              {title} 등록
            </button>
          )}
        </div>
        <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
        {!panelOpen && <ErrorNotice error={saveError} />}
        {done && <p role="status">{done}</p>}
        {deletingDialog}
        {!rows && !error ? (
          <Loading />
        ) : (
          rows && (
            <DataTable
              rows={rows}
              columns={columns}
              caption={title}
              offset={offset}
              total={total}
              limit={20}
              onPage={setOffset}
              empty="등록된 정보가 없습니다."
            />
          )
        )}
        {formPanel}
      </div>
    );
  }

  return (
    <div className="page-fill">
      <PageTitle
        id={id}
        title={title}
        help={`erp/${id.toLowerCase()}`}
        actions={
          !readOnly && (
            <button
              type="button"
              aria-pressed={panelOpen}
              onClick={() => guard.guard(openCreate)}
            >
              {title} 등록
            </button>
          )
        }
      />
      {note && (
        <p className="muted" role="note">
          {note}
        </p>
      )}
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!panelOpen && <ErrorNotice error={saveError} />}
      {done && <p role="status">{done}</p>}
      {deletingDialog}
      {!rows && !error ? (
        <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="section-block">
              {rows && (
                <DataTable
                  rows={rows}
                  columns={columns}
                  caption={title}
                  offset={offset}
                  total={total}
                  limit={20}
                  onPage={setOffset}
                  empty="등록된 정보가 없습니다."
                />
              )}
            </div>
            {children}
          </section>
          {formPanel}
        </div>
      )}
    </div>
  );
}
