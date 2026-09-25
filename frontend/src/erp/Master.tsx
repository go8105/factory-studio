import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError, MutationKeys } from "../shared/api";
import {
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
export type Row = {
  id: number;
  [key: string]: string | number | boolean | null;
};
export type InputField = {
  key: string;
  label: string;
  type?: "text" | "number" | "checkbox" | "month";
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
  readOnly = false,
  embedded = false,
  note,
}: {
  id: string;
  title: string;
  path: string;
  fields: InputField[];
  extraColumns?: InputField[];
  readOnly?: boolean;
  embedded?: boolean;
  note?: string;
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
  const [draft, setDraft] = useState(initial);
  const [lookups, setLookups] = useState<Record<string, Row[]>>({});
  const [error, setError] = useState<unknown>();
  const [saveError, setSaveError] = useState<unknown>();
  const [pending, setPending] = useState(false);
  const [deleting, setDeleting] = useState<Row>();
  const [done, setDone] = useState("");
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
  function edit(row: Row | null) {
    setEditing(row);
    setDraft(
      row
        ? Object.fromEntries(fields.map((f) => [f.key, row[f.key]]))
        : initial(),
    );
    setSaveError(undefined);
    setDone("");
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
      edit(null);
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
  const columns: Column<Row>[] = [...fields, ...extraColumns].map((f) => ({
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
        <div className="actions">
          <button disabled={pending} onClick={() => edit(r)}>
            수정
          </button>
          <button
            disabled={pending}
            onClick={() => {
              setDeleting(r);
              setSaveError(undefined);
            }}
          >
            삭제
          </button>
        </div>
      ),
    });
  return (
    <>
      {embedded ? (
        <h2>{title}</h2>
      ) : (
        <PageTitle
          id={id}
          title={title}
          help={`/help/erp/${id.toLowerCase()}`}
        />
      )}
      {note && <p className="notice">{note}</p>}
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
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
      <ErrorNotice error={saveError} />
      {done && <p role="status">{done}</p>}
      {deleting && (
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
      )}
      {!readOnly && (
        <form
          className="panel"
          onSubmit={submit}
          aria-label={`${title} ${editing ? "수정" : "등록"}`}
        >
          <h2>{editing ? "수정" : "등록"}</h2>
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
                      required
                      aria-invalid={!!error}
                      aria-describedby={error ? `${inputId}-error` : undefined}
                      value={String(draft[f.key] ?? "")}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          [f.key]: f.lookup
                            ? e.target.value
                              ? Number(e.target.value)
                              : ""
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
            <div className="actions">
              <button type="submit" disabled={pending}>
                {pending ? "저장 중" : "저장"}
              </button>
              {editing && (
                <button type="button" onClick={() => edit(null)}>
                  새로 등록
                </button>
              )}
            </div>
          </fieldset>
        </form>
      )}
    </>
  );
}
