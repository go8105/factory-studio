// 공통 엔진 — 기준정보 화면(목록 + 등록/수정 패널) (DSN-01 C, W0-5)
//
// 화면은 "무엇을 보여줄지"만 선언하고, 아래가 공통으로 처리한다:
// 목록 조회·쪽수·조건, 등록/수정 패널, 바뀐 항목만 PATCH, 삭제 확정, 멱등 키(응답 불확실 시 보존),
// 입력 칸별 오류, 솔루션을 끈 공간 안내, 저장하지 않은 입력 보호.
//
// 특수한 화면(전표·3D·관리도)은 이 엔진을 쓰지 않고 직접 만든다.
import {
  useEffect,
  useId,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { useSession } from "../app/session";
import { ApiError, api } from "./api";
import { fieldErrors, moduleOff, useApiSend } from "./hooks";
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
} from "./components";

/** 코드 입력 검사. 브라우저의 pattern은 v 플래그라 문자 클래스 안의 '-'를 반드시 escape한다. */
export const CODE_PATTERN = String.raw`[A-Z0-9][A-Z0-9_\-]{0,29}`;

/** 입력 칸 한 개. 더 복잡한 입력은 spec.extra로 직접 넣는다. */
export type MasterField<Draft> =
  | {
      kind: "text";
      key: keyof Draft & string;
      label: string;
      required?: boolean;
      maxLength?: number;
      pattern?: string;
      title?: string;
      /** 입력을 대문자로 바꾼다(코드 칸). */
      upper?: boolean;
    }
  | {
      kind: "select";
      key: keyof Draft & string;
      label: string;
      options: readonly string[] | Record<string, string>;
      note?: string;
    }
  | {
      kind: "number";
      key: keyof Draft & string;
      label: string;
      required?: boolean;
      min?: number;
      max?: number;
      note?: string;
    }
  | {
      kind: "time";
      key: keyof Draft & string;
      label: string;
      required?: boolean;
    }
  | { kind: "check"; key: keyof Draft & string; label: string };

export type MasterSpec<Row extends { id: number | string }, Draft> = {
  /** 화면 ID·제목·도움말 경로 (PageTitle과 같은 ID를 쓴다) */
  id: string;
  title: string;
  subtitle?: string;
  help: string;
  /** API 경로. 목록 GET, 등록 POST, 수정 PATCH/{id}, 삭제 DELETE/{id} */
  base: string;
  limit?: number;
  allowDelete?: boolean;
  onSaved?: () => void;
  reloadKey?: number;
  search?: boolean;
  updateBody?: (changes: Record<string, unknown>, row: Row) => unknown;
  /** 등록할 때의 빈 값 */
  blank: Draft;
  columns: Column<Row>[];
  fields: MasterField<Draft>[];
  /** 목록 위 안내(등록 순서 등) */
  intro?: ReactNode;
  /** 조건 체크박스 한 개 (예: 사용 중만 → "active=true") */
  filter?: { label: string; query: string };
  /** 폼 아래에 직접 넣는 입력 */
  extra?: (draft: Draft, set: (values: Partial<Draft>) => void) => ReactNode;
  labels: {
    /** 등록 버튼·등록 패널 제목 */
    create: string;
    caption: string;
    emptyReason: string;
    editTitle: (row: Row) => string;
    deleted: (row: Row) => string;
    /** 솔루션을 끈 공간에서 보여줄 안내 */
    moduleOff: string;
  };
};

function SelectField({
  label,
  value,
  options,
  note,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly string[] | Record<string, string>;
  note?: string;
  onChange: (value: string) => void;
}) {
  const id = useId();
  const entries: [string, string][] = Array.isArray(options)
    ? options.map((option) => [option, option])
    : Object.entries(options as Record<string, string>);
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        value={value}
        aria-describedby={note ? `${id}-note` : undefined}
        onChange={(event) => onChange(event.target.value)}
      >
        {entries.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
      {note && <small id={`${id}-note`}>{note}</small>}
    </div>
  );
}

/** spec을 바꿔 가며 쓰려면(탭 등) `key`를 함께 준다 — 목록·입력 상태가 그대로 남는다. */
export function MasterScreen<
  Row extends { id: number | string },
  Draft extends Record<string, unknown>,
>({ spec }: { spec: MasterSpec<Row, Draft> }) {
  const limit = spec.limit ?? 20;
  const { fail } = useSession();
  const [rows, setRows] = useState<Row[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [filtered, setFiltered] = useState(false);
  const [search, setSearch] = useState("");
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [panel, setPanel] = useState<{ row: Row | null } | null>(null);
  const editing = panel?.row ?? null;
  const [draft, setDraft] = useState<Draft>(spec.blank);
  const [initial, setInitial] = useState<Draft>(spec.blank);
  const [confirmDelete, setConfirmDelete] = useState<number | string>();
  const [done, setDone] = useState("");
  // 저장·삭제 요청(CSRF·멱등 키·응답 불확실 시 키 보존)은 공통 훅이 맡는다.
  const {
    send,
    pending,
    error: saveError,
    setError: setSaveError,
  } = useApiSend(spec.base, () => {
    setReload((n) => n + 1);
    spec.onSaved?.();
  });

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    const query =
      (filtered && spec.filter ? `&${spec.filter.query}` : "") +
      (spec.search ? `&search=${encodeURIComponent(search)}` : "");
    api<Row[]>(`${spec.base}?offset=${offset}&limit=${limit}${query}`, {
      signal: controller.signal,
    })
      .then((reply) => {
        if (controller.signal.aborted) return;
        setRows(reply.data);
        setTotal(reply.page?.total ?? 0);
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(error);
        if (error instanceof ApiError && [401, 410].includes(error.status))
          fail(error);
      });
    return () => controller.abort();
  }, [offset, filtered, reload, search, spec.reloadKey]);

  const dirty =
    !!panel &&
    (Object.keys(draft) as (keyof Draft)[]).some(
      (key) => draft[key] !== initial[key],
    );
  const guard = useDiscardGuard(dirty);

  function openPanel(row: Row | null) {
    const values = (row ? { ...row } : spec.blank) as unknown as Draft;
    setPanel({ row });
    setDraft(values);
    setInitial(values);
    setSaveError(undefined);
    setDone("");
  }
  function closePanel() {
    setPanel(null);
    setSaveError(undefined);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const body = editing
      ? Object.fromEntries(
          Object.entries(draft).filter(
            ([key, value]) =>
              (editing as Record<string, unknown>)[key] !== value,
          ),
        )
      : draft;
    if (editing && !Object.keys(body).length) {
      setDone("변경한 항목이 없습니다.");
      return;
    }
    const saved = await send(
      editing ? `/${editing.id}` : "",
      editing ? "PATCH" : "POST",
      editing && spec.updateBody ? spec.updateBody(body, editing) : body,
    );
    if (saved !== undefined) {
      closePanel();
      setDone(editing ? "수정했습니다." : "등록했습니다.");
    }
  }

  async function remove(row: Row) {
    if (pending) return;
    const removed = await send(`/${row.id}`, "DELETE");
    setConfirmDelete(undefined);
    if (removed !== undefined) {
      if (editing?.id === row.id) closePanel();
      setDone(spec.labels.deleted(row));
    }
  }

  if (moduleOff(loadError))
    return (
      <EmptyState
        reason={spec.labels.moduleOff}
        to="/workspace"
        action="내 공간으로"
      />
    );

  const errors = fieldErrors(saveError);
  const panelError = Object.keys(errors).length ? undefined : saveError;
  const columns: Column<Row>[] = [
    ...spec.columns,
    {
      key: "id" as keyof Row & string,
      label: "관리",
      render: (row: Row) =>
        confirmDelete === row.id ? (
          <span className="row-actions">
            <button
              className="secondary"
              disabled={pending}
              onClick={() => void remove(row)}
            >
              삭제 확정
            </button>
            <button
              className="link-button"
              onClick={() => setConfirmDelete(undefined)}
            >
              취소
            </button>
          </span>
        ) : (
          <span className="row-actions">
            <button
              className="link-button"
              aria-pressed={editing?.id === row.id}
              onClick={() => guard.guard(() => openPanel(row))}
            >
              수정
            </button>
            {spec.allowDelete !== false && (
              <button
                className="link-button"
                onClick={() => setConfirmDelete(row.id)}
              >
                삭제
              </button>
            )}
          </span>
        ),
    },
  ];
  const set = (values: Partial<Draft>) => setDraft({ ...draft, ...values });

  return (
    <div className="page-fill">
      <PageTitle
        id={spec.id}
        title={spec.title}
        subtitle={spec.subtitle}
        help={spec.help}
        actions={
          <button
            type="button"
            aria-pressed={!!panel && !editing}
            onClick={() => guard.guard(() => openPanel(null))}
          >
            {spec.labels.create}
          </button>
        }
      />
      {spec.intro}
      {!panel && <ErrorNotice error={panelError} />}
      {done && <p role="status">{done}</p>}
      <div className="split-view fill">
        <section className="fill">
          {spec.search && (
            <Field
              label="검색"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
            />
          )}
          {spec.filter && (
            <div className="filter-bar">
              <label className="inline-check">
                <input
                  type="checkbox"
                  checked={filtered}
                  onChange={(event) => {
                    setOffset(0);
                    setFiltered(event.target.checked);
                  }}
                />
                {spec.filter.label}
              </label>
            </div>
          )}
          <ErrorNotice
            error={loadError}
            retry={() => setReload((n) => n + 1)}
          />
          {!rows ? (
            !loadError && <Loading />
          ) : (
            <DataTable
              rows={rows}
              columns={columns}
              caption={spec.labels.caption}
              offset={offset}
              total={total}
              limit={limit}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason={spec.labels.emptyReason}
                  action={spec.labels.create}
                  onAction={() => guard.guard(() => openPanel(null))}
                />
              }
            />
          )}
        </section>
        {panel && (
          <FormPanel
            key={editing?.id ?? "new"}
            title={
              editing ? spec.labels.editTitle(editing) : spec.labels.create
            }
            guard={guard}
            onClose={closePanel}
            onSubmit={(event) => void submit(event)}
            actions={
              <>
                <button type="submit" disabled={pending} aria-busy={pending}>
                  {editing ? "수정 저장" : "등록"}
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
            <ErrorNotice error={panelError} />
            {spec.fields.map((field) => {
              const value = draft[field.key];
              if (field.kind === "text")
                return (
                  <Field
                    key={field.key}
                    label={field.label}
                    value={String(value ?? "")}
                    required={field.required}
                    maxLength={field.maxLength}
                    pattern={field.pattern}
                    title={field.title}
                    error={errors[field.key]}
                    onChange={(event) =>
                      set({
                        [field.key]: field.upper
                          ? event.target.value.toUpperCase()
                          : event.target.value,
                      } as Partial<Draft>)
                    }
                  />
                );
              if (field.kind === "number" || field.kind === "time")
                return (
                  <Field
                    key={field.key}
                    label={field.label}
                    type={field.kind === "time" ? "time" : "number"}
                    step={field.kind === "time" ? 1 : undefined}
                    value={String(value ?? "")}
                    required={field.required}
                    min={field.kind === "number" ? field.min : undefined}
                    max={field.kind === "number" ? field.max : undefined}
                    error={errors[field.key]}
                    onChange={(event) =>
                      set({
                        [field.key]:
                          field.kind === "number"
                            ? Number(event.target.value)
                            : event.target.value,
                      } as Partial<Draft>)
                    }
                  />
                );
              if (field.kind === "select")
                return (
                  <SelectField
                    key={field.key}
                    label={field.label}
                    value={String(value ?? "")}
                    options={field.options}
                    note={field.note}
                    onChange={(next) =>
                      set({ [field.key]: next } as Partial<Draft>)
                    }
                  />
                );
              return (
                <label className="inline-check" key={field.key}>
                  <input
                    type="checkbox"
                    checked={!!value}
                    onChange={(event) =>
                      set({
                        [field.key]: event.target.checked,
                      } as Partial<Draft>)
                    }
                  />
                  {field.label}
                </label>
              );
            })}
            {spec.extra?.(draft, set)}
          </FormPanel>
        )}
      </div>
    </div>
  );
}
