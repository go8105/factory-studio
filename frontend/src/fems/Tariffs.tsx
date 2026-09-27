// F-14 요금제 — FEMS 에너지원별 단일 요금제 목록 + 등록/수정 패널 (FS-018)
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

const BASE = "/api/v1/fems/tariffs";
const SOURCES_BASE = "/api/v1/fems/energy-sources";
const LIMIT = 20;

export type Tariff = {
  id: number;
  energySourceId: number;
  tariffCode: string;
  name: string;
  contractType: string | null;
  basicCharge: string;
  usageRate: string;
  currency: string;
  effectiveFrom: string;
  effectiveTo: string | null;
  createdAt: string;
};

export type EnergySource = {
  id: number;
  sourceCode: string;
  name: string;
  measureUnit: string;
};

type Draft = {
  energySourceId: number;
  tariffCode: string;
  name: string;
  contractType: string;
  basicCharge: string;
  usageRate: string;
  effectiveFrom: string;
  effectiveTo: string;
};

const EMPTY: Draft = {
  energySourceId: 0,
  tariffCode: "",
  name: "",
  contractType: "",
  basicCharge: "",
  usageRate: "",
  effectiveFrom: "",
  effectiveTo: "",
};

function formatMoney(amount: string | number) {
  const n = Number(amount);
  if (Number.isNaN(n)) return String(amount);
  return n.toLocaleString();
}

function fieldErrors(error: unknown): Record<string, string> {
  return error instanceof ApiError &&
    error.error.code === "VALIDATION_FAILED" &&
    error.error.details?.fields
    ? (error.error.details.fields as Record<string, string>)
    : {};
}

function getOverlapConflicts(error: unknown): Array<{
  id: number;
  tariffCode: string;
  effectiveFrom: string;
  effectiveTo: string | null;
}> {
  if (
    error instanceof ApiError &&
    error.error.code === "PRECONDITION_NOT_MET" &&
    error.error.details?.reason === "PERIOD_OVERLAP"
  ) {
    return (error.error.details.conflicts ?? []) as Array<{
      id: number;
      tariffCode: string;
      effectiveFrom: string;
      effectiveTo: string | null;
    }>;
  }
  return [];
}

function cleanDraft(draft: Draft): Record<string, unknown> {
  return {
    energySourceId: draft.energySourceId,
    tariffCode: draft.tariffCode.trim().toUpperCase(),
    name: draft.name.trim(),
    contractType: draft.contractType.trim() ? draft.contractType.trim() : null,
    basicCharge: draft.basicCharge.trim(),
    usageRate: draft.usageRate.trim(),
    effectiveFrom: draft.effectiveFrom.trim(),
    effectiveTo: draft.effectiveTo.trim() ? draft.effectiveTo.trim() : null,
  };
}

export function Tariffs() {
  const { session, fail } = useSession();
  const keys = useRef(new MutationKeys());
  const [rows, setRows] = useState<Tariff[]>();
  const [sources, setSources] = useState<EnergySource[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [sourceFilter, setSourceFilter] = useState<number>();
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [panel, setPanel] = useState<{ row: Tariff | null } | null>(null);
  const editing = panel?.row ?? null;
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [initial, setInitial] = useState<Draft>(EMPTY);
  const [saveError, setSaveError] = useState<unknown>();
  const [confirmDelete, setConfirmDelete] = useState<number>();
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    api<EnergySource[]>(SOURCES_BASE, { signal: controller.signal })
      .then((r) => {
        setSources(r.data);
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
    const filterQuery = sourceFilter ? `&energySourceId=${sourceFilter}` : "";
    api<Tariff[]>(`${BASE}?offset=${offset}&limit=${LIMIT}${filterQuery}`, {
      signal: controller.signal,
    })
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
  }, [offset, sourceFilter, reload]);

  const dirty =
    !!panel &&
    (Object.keys(draft) as (keyof Draft)[]).some(
      (k) => draft[k] !== initial[k],
    );
  const guard = useDiscardGuard(dirty);

  function openPanel(row: Tariff | null) {
    const defaultSource = sources && sources.length > 0 ? sources[0].id : 0;
    const values: Draft = row
      ? {
          energySourceId: row.energySourceId,
          tariffCode: row.tariffCode,
          name: row.name,
          contractType: row.contractType ?? "",
          basicCharge: row.basicCharge,
          usageRate: row.usageRate,
          effectiveFrom: row.effectiveFrom,
          effectiveTo: row.effectiveTo ?? "",
        }
      : { ...EMPTY, energySourceId: defaultSource };
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
    const cleaned = cleanDraft(draft);
    const body = editing
      ? Object.fromEntries(
          Object.entries(cleaned).filter(
            ([k, v]) => editing[k as keyof Tariff] !== v,
          ),
        )
      : cleaned;
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
      setDone(editing ? "요금제를 수정했습니다." : "요금제를 등록했습니다.");
    }
  }

  async function remove(row: Tariff) {
    if (pending) return;
    const ok = await send(`delete:${row.id}`, `${BASE}/${row.id}`, "DELETE");
    setConfirmDelete(undefined);
    if (ok) {
      if (editing?.id === row.id) closePanel();
      setDone(`${row.name} 요금제를 삭제했습니다.`);
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

  if (sources && sources.length === 0) {
    return (
      <div className="page-fill">
        <PageTitle
          id="F-14"
          title="요금제"
          subtitle="에너지원별 단일 요금제를 관리합니다"
          help="fems/f-14"
        />
        <MasterOrder />
        <EmptyState
          reason="등록된 에너지원이 없습니다. 요금제는 에너지원이 먼저 등록되어 있어야 합니다."
          to="/fems/energy-sources"
          action="에너지원 화면으로"
        />
      </div>
    );
  }

  const errors = fieldErrors(saveError);
  const overlapConflicts = getOverlapConflicts(saveError);
  const sourceMap = new Map((sources ?? []).map((s) => [s.id, s.name]));

  const columns: Column<Tariff>[] = [
    { key: "tariffCode", label: "코드" },
    { key: "name", label: "요금제명" },
    {
      key: "energySourceId",
      label: "에너지원",
      render: (r) =>
        sourceMap.get(r.energySourceId) ?? String(r.energySourceId),
    },
    {
      key: "contractType",
      label: "계약종별",
      render: (r) => r.contractType ?? "-",
    },
    {
      key: "basicCharge",
      label: "기본요금 (KRW)",
      render: (r) => formatMoney(r.basicCharge),
    },
    {
      key: "usageRate",
      label: "사용량 단가 (KRW)",
      render: (r) => formatMoney(r.usageRate),
    },
    {
      key: "effectiveFrom",
      label: "적용 기간",
      render: (r) => `${r.effectiveFrom} ~ ${r.effectiveTo ?? "계속 적용"}`,
    },
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
  ];

  const panelError =
    overlapConflicts.length || Object.keys(errors).length
      ? undefined
      : saveError;

  return (
    <div className="page-fill">
      <PageTitle
        id="F-14"
        title="요금제"
        subtitle="에너지원별 단일 요금제를 관리합니다"
        help="fems/f-14"
        actions={
          <button
            type="button"
            aria-pressed={!!panel && !editing}
            onClick={() => guard.guard(() => openPanel(null))}
          >
            요금제 등록
          </button>
        }
      />
      <MasterOrder />
      {!panel && overlapConflicts.length > 0 && (
        <div className="notice" role="alert">
          <strong>적용 기간이 겹치는 요금제가 있습니다.</strong>
          <p>
            겹치는 요금제:{" "}
            {overlapConflicts
              .map(
                (c) =>
                  `${c.tariffCode} (${c.effectiveFrom} ~ ${c.effectiveTo ?? "계속"})`,
              )
              .join(", ")}
          </p>
        </div>
      )}
      {!panel && <ErrorNotice error={panelError} />}
      {done && <p role="status">{done}</p>}
      <div className="split-view fill">
        <section className="fill">
          <div className="filter-bar">
            <label htmlFor="tariff-source-filter">에너지원 필터:</label>
            <select
              id="tariff-source-filter"
              value={sourceFilter ?? ""}
              onChange={(e) => {
                const val = e.target.value ? Number(e.target.value) : undefined;
                setSourceFilter(val);
                setOffset(0);
              }}
            >
              <option value="">전체</option>
              {(sources ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.sourceCode})
                </option>
              ))}
            </select>
          </div>
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
              caption="요금제 목록"
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason="등록된 요금제가 없습니다. 첫 요금제를 등록하세요."
                  action="요금제 등록"
                  onAction={() => guard.guard(() => openPanel(null))}
                />
              }
            />
          )}
        </section>

        {panel && (
          <FormPanel
            key={editing?.id ?? "new"}
            title={editing ? `${editing.name} 수정` : "요금제 등록"}
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
            {overlapConflicts.length > 0 && (
              <div className="notice" role="alert">
                <strong>적용 기간이 겹치는 요금제가 있습니다.</strong>
                <p>
                  겹치는 요금제:{" "}
                  {overlapConflicts
                    .map(
                      (c) =>
                        `${c.tariffCode} (${c.effectiveFrom} ~ ${c.effectiveTo ?? "계속"})`,
                    )
                    .join(", ")}
                </p>
              </div>
            )}
            <ErrorNotice error={panelError} />
            <div className="field">
              <label htmlFor="energy-source-id">에너지원</label>
              <select
                id="energy-source-id"
                value={draft.energySourceId}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    energySourceId: Number(e.target.value),
                  })
                }
              >
                {(sources ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.sourceCode})
                  </option>
                ))}
              </select>
            </div>
            <Field
              label="요금제 코드"
              value={draft.tariffCode}
              required
              maxLength={30}
              pattern="[A-Z][A-Z0-9_\-]{1,29}"
              title="영문 대문자로 시작하는 2~30자 (대문자·숫자·_·-)"
              error={errors.tariffCode}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  tariffCode: e.target.value.toUpperCase(),
                })
              }
            />
            <Field
              label="요금제명"
              value={draft.name}
              required
              maxLength={100}
              error={errors.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
            <Field
              label="계약종별"
              value={draft.contractType}
              maxLength={50}
              error={errors.contractType}
              onChange={(e) =>
                setDraft({ ...draft, contractType: e.target.value })
              }
            />
            <div className="field-row">
              <Field
                label="기본요금 (KRW)"
                value={draft.basicCharge}
                required
                error={errors.basicCharge}
                onChange={(e) =>
                  setDraft({ ...draft, basicCharge: e.target.value })
                }
              />
              <Field
                label="사용량 단가 (KRW)"
                value={draft.usageRate}
                required
                error={errors.usageRate}
                onChange={(e) =>
                  setDraft({ ...draft, usageRate: e.target.value })
                }
              />
            </div>
            <div className="field-row">
              <Field
                label="적용 시작 연월"
                value={draft.effectiveFrom}
                required
                maxLength={7}
                placeholder="YYYY-MM"
                error={errors.effectiveFrom}
                onChange={(e) =>
                  setDraft({ ...draft, effectiveFrom: e.target.value })
                }
              />
              <Field
                label="적용 종료 연월"
                value={draft.effectiveTo}
                maxLength={7}
                placeholder="YYYY-MM (선택)"
                error={errors.effectiveTo}
                onChange={(e) =>
                  setDraft({ ...draft, effectiveTo: e.target.value })
                }
              />
            </div>
          </FormPanel>
        )}
      </div>
    </div>
  );
}
