// F-13 환산·배출계수 — 환산(PRIMARY)과 배출(EMISSION)을 탭으로 나눈 목록 + 등록/수정 패널 (FS-018k)
import { useEffect, useRef, useState, type FormEvent } from "react";
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
import { MasterOrder } from "./EnergySources";

const BASE = "/api/v1/fems/energy-factors";
const SOURCES_BASE = "/api/v1/fems/energy-sources";
const LIMIT = 20;

type Kind = "PRIMARY" | "EMISSION";

export type Factor = {
  id: number;
  energySourceId: number;
  factorKind: Kind;
  effectiveYear: string;
  factorValue: string;
  factorUnit: string;
  sourceNote: string;
  createdAt: string;
};

type Source = {
  id: number;
  sourceCode: string;
  name: string;
  sourceKind: string;
  measureUnit: string;
};

const KINDS: Record<Kind, { label: string; unit: string; use: string }> = {
  PRIMARY: {
    label: "1차에너지 환산계수",
    unit: "TOE/",
    use: "에너지원이 다른 사용량을 TOE로 바꿔 합산할 때만 씁니다.",
  },
  EMISSION: {
    label: "온실가스 배출계수",
    unit: "tCO2eq/",
    use: "에너지원별 사용량에 곱해 배출량을 구합니다. 환산값(TOE)에는 곱하지 않습니다.",
  },
};

type Draft = {
  energySourceId: number;
  effectiveYear: string;
  factorValue: string;
  sourceNote: string;
};

function fieldErrors(error: unknown): Record<string, string> {
  return error instanceof ApiError &&
    error.error.code === "VALIDATION_FAILED" &&
    error.error.details?.fields
    ? (error.error.details.fields as Record<string, string>)
    : {};
}

export function Factors() {
  const { session, fail } = useSession();
  const keys = useRef(new MutationKeys());
  const [kind, setKind] = useState<Kind>("PRIMARY");
  const [rows, setRows] = useState<Factor[]>();
  const [sources, setSources] = useState<Source[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [panel, setPanel] = useState<{ row: Factor | null } | null>(null);
  const editing = panel?.row ?? null;
  const [draft, setDraft] = useState<Draft>({
    energySourceId: 0,
    effectiveYear: "",
    factorValue: "",
    sourceNote: "",
  });
  const [initial, setInitial] = useState<Draft>({
    energySourceId: 0,
    effectiveYear: "",
    factorValue: "",
    sourceNote: "",
  });
  const [saveError, setSaveError] = useState<unknown>();
  const [confirmDelete, setConfirmDelete] = useState<number>();
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState("");

  // 용수(UTILITY)는 TOE 합산·배출량 계산 대상이 아니라 계수를 등록하지 않는다.
  const usable = (sources ?? []).filter((s) => s.sourceKind !== "UTILITY");

  useEffect(() => {
    const controller = new AbortController();
    api<Source[]>(SOURCES_BASE, { signal: controller.signal })
      .then((r) => {
        setSources(r.data);
        const first = r.data.find((s) => s.sourceKind !== "UTILITY");
        if (first) {
          setDraft((prev) =>
            prev.energySourceId ? prev : { ...prev, energySourceId: first.id },
          );
          setInitial((prev) =>
            prev.energySourceId ? prev : { ...prev, energySourceId: first.id },
          );
        }
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        setLoadError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [reload]);

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    api<Factor[]>(
      `${BASE}?factorKind=${kind}&offset=${offset}&limit=${LIMIT}`,
      { signal: controller.signal },
    )
      .then((r) => {
        setRows(r.data);
        setTotal(r.page?.total ?? 0);
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        setLoadError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [kind, offset, reload]);

  const dirty =
    !!panel &&
    (editing
      ? (Object.keys(draft) as (keyof Draft)[]).some(
          (k) => draft[k] !== initial[k],
        )
      : Boolean(
          draft.effectiveYear.trim() ||
          draft.factorValue.trim() ||
          draft.sourceNote.trim(),
        ));
  const guard = useDiscardGuard(dirty);

  function openPanel(row: Factor | null) {
    const values: Draft = row
      ? {
          energySourceId: row.energySourceId,
          effectiveYear: row.effectiveYear,
          factorValue: row.factorValue,
          sourceNote: row.sourceNote,
        }
      : {
          energySourceId: usable[0]?.id ?? 0,
          effectiveYear: "",
          factorValue: "",
          sourceNote: "",
        };
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

  async function send(
    operation: string,
    path: string,
    method: string,
    body?: unknown,
  ) {
    setPending(true);
    setSaveError(undefined);
    setDone("");
    try {
      await api(path, {
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
    if (pending) return;
    const fields = {
      effectiveYear: draft.effectiveYear.trim(),
      factorValue: draft.factorValue.trim(),
      sourceNote: draft.sourceNote.trim(),
    };
    const body = editing
      ? Object.fromEntries(
          Object.entries(fields).filter(
            ([k, v]) => editing[k as keyof Factor] !== v,
          ),
        )
      : { ...fields, energySourceId: currentSourceId, factorKind: kind };
    if (editing && !Object.keys(body).length) {
      setDone("변경한 항목이 없습니다.");
      return;
    }
    const operation = `${editing ? `update:${editing.id}` : "create"}:${JSON.stringify(body)}`;
    const ok = await send(
      operation,
      editing ? `${BASE}/${editing.id}` : BASE,
      editing ? "PATCH" : "POST",
      body,
    );
    if (ok) {
      closePanel();
      setDone(editing ? "계수를 수정했습니다." : "계수를 등록했습니다.");
    }
  }

  async function remove(row: Factor) {
    if (pending) return;
    const ok = await send(`delete:${row.id}`, `${BASE}/${row.id}`, "DELETE");
    setConfirmDelete(undefined);
    if (ok) {
      if (editing?.id === row.id) closePanel();
      setDone("계수를 삭제했습니다.");
    }
  }

  if (
    loadError instanceof ApiError &&
    loadError.error.details?.reason === "MODULE_DISABLED"
  )
    return (
      <EmptyState
        reason="FEMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );

  if (sources && usable.length === 0)
    return (
      <div className="page-fill">
        <PageTitle
          id="F-13"
          title="환산·배출계수"
          subtitle="에너지원별·연도별 환산계수와 배출계수를 관리합니다"
          help="fems/f-13"
        />
        <MasterOrder />
        <EmptyState
          reason="계수를 등록할 에너지원이 없습니다. 전력·연료·열 에너지원을 먼저 등록하세요."
          to="/fems/energy-sources"
          action="에너지원 화면으로"
        />
      </div>
    );

  const errors = fieldErrors(saveError);
  const sourceMap = new Map((sources ?? []).map((s) => [s.id, s]));
  const currentSourceId = draft.energySourceId || usable[0]?.id || 0;
  const selected = sourceMap.get(currentSourceId);
  const unitPreview = editing
    ? editing.factorUnit
    : selected
      ? KINDS[kind].unit + selected.measureUnit
      : "";

  const columns: Column<Factor>[] = [
    { key: "effectiveYear", label: "적용 연도" },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        confirmDelete === r.id ? (
          <span className="row-actions">
            <button
              type="button"
              className="secondary"
              disabled={pending}
              onClick={() => void remove(r)}
            >
              삭제 확정
            </button>
            <button
              type="button"
              className="link-button"
              onClick={() => setConfirmDelete(undefined)}
            >
              취소
            </button>
          </span>
        ) : (
          <span className="row-actions">
            <button
              type="button"
              className="link-button"
              aria-pressed={editing?.id === r.id}
              onClick={() => guard.guard(() => openPanel(r))}
            >
              수정
            </button>
            <button
              type="button"
              className="link-button"
              onClick={() => {
                setConfirmDelete(r.id);
                setSaveError(undefined);
              }}
            >
              삭제
            </button>
          </span>
        ),
    },
    {
      key: "energySourceId",
      label: "에너지원",
      render: (r) =>
        sourceMap.get(r.energySourceId)?.name ?? String(r.energySourceId),
    },
    { key: "factorValue", label: "계수" },
    { key: "factorUnit", label: "단위" },
    { key: "sourceNote", label: "출처" },
  ];

  const panelError = Object.keys(errors).length ? undefined : saveError;

  const tabs = (
    <div className="tabs" role="tablist">
      {(Object.keys(KINDS) as Kind[]).map((key) => (
        <button
          key={key}
          type="button"
          aria-pressed={kind === key}
          className={kind === key ? "active" : ""}
          onClick={() =>
            guard.guard(() => {
              setKind(key);
              setOffset(0);
              setConfirmDelete(undefined);
              if (panel && !editing) {
                const values: Draft = {
                  energySourceId: draft.energySourceId || usable[0]?.id || 0,
                  effectiveYear: "",
                  factorValue: "",
                  sourceNote: "",
                };
                setDraft(values);
                setInitial(values);
                setSaveError(undefined);
              } else {
                closePanel();
              }
            })
          }
        >
          {KINDS[key].label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="page-fill">
      <PageTitle
        id="F-13"
        title="환산·배출계수"
        subtitle="에너지원별·연도별 환산계수와 배출계수를 관리합니다"
        help="fems/f-13"
        actions={
          <button
            type="button"
            aria-pressed={!!panel && !editing}
            onClick={() => guard.guard(() => openPanel(null))}
          >
            계수 등록
          </button>
        }
      />
      <MasterOrder />
      <p className="muted" role="note">
        {KINDS[kind].use}
      </p>
      {confirmDelete !== undefined && (
        <p className="notice" role="status">
          계수를 지우면 그 연도의 계산은 추정하지 않고 &quot;계수 없음&quot;으로
          표시됩니다.
        </p>
      )}
      {!panel && <ErrorNotice error={panelError} />}
      {done && <p role="status">{done}</p>}
      <div className="split-view fill">
        <section className="fill">
          <ErrorNotice
            error={loadError}
            retry={() => setReload((n) => n + 1)}
          />
          {!rows ? (
            !loadError && <Loading />
          ) : (
            <DataTable
              leading={tabs}
              rows={rows}
              columns={columns}
              caption={`${KINDS[kind].label} 목록`}
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason={`등록된 ${KINDS[kind].label}가 없습니다. 계수가 없는 연도는 계산 불가로 표시됩니다.`}
                  action="계수 등록"
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
              editing
                ? `${editing.effectiveYear}년 계수 수정`
                : `${KINDS[kind].label} 등록`
            }
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
            <ErrorNotice error={panelError} />
            <div className="field">
              <label htmlFor="factor-source">에너지원</label>
              <select
                id="factor-source"
                value={currentSourceId}
                disabled={!!editing}
                onChange={(e) =>
                  setDraft({ ...draft, energySourceId: Number(e.target.value) })
                }
              >
                {(editing ? (sources ?? []) : usable).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.sourceCode})
                  </option>
                ))}
              </select>
              {errors.energySourceId && <small>{errors.energySourceId}</small>}
            </div>
            {editing && (
              <p className="muted">
                에너지원·계수 유형을 바꾸려면 새로 등록하세요.
              </p>
            )}
            <Field
              label="적용 연도"
              value={draft.effectiveYear}
              required
              maxLength={4}
              pattern="[0-9]{4}"
              placeholder="YYYY"
              error={errors.effectiveYear}
              onChange={(e) =>
                setDraft({ ...draft, effectiveYear: e.target.value })
              }
            />
            <Field
              label={`계수 (${unitPreview})`}
              value={draft.factorValue}
              required
              inputMode="decimal"
              title="0보다 큰 수, 소수 6자리까지"
              error={errors.factorValue}
              onChange={(e) =>
                setDraft({ ...draft, factorValue: e.target.value })
              }
            />
            <Field
              label="출처"
              value={draft.sourceNote}
              required
              maxLength={200}
              error={errors.sourceNote}
              onChange={(e) =>
                setDraft({ ...draft, sourceNote: e.target.value })
              }
            />
          </FormPanel>
        )}
      </div>
    </div>
  );
}
