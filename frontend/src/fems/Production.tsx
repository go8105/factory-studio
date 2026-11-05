// F-05 생산량 등록 — 원단위의 분모. 확정은 불변, 정정은 새 버전(초안)으로 (FS-018i)
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError, MutationKeys } from "../shared/api";
import {
  Badge,
  DataTable,
  DateRange,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
const BASE = "/api/v1/fems/production-records";
const LIMIT = 20;
export type ProductionRecord = {
  id: number;
  sourceKey: string;
  versionNo: number;
  equipmentId: number;
  equipmentCode: string;
  equipmentName: string;
  itemCode: string;
  startDate: string;
  endDate: string;
  productionQty: string;
  unit: string;
  status: "draft" | "confirmed";
  confirmedAt: string | null;
  isLatest: boolean;
  isEffective: boolean;
};
type Equipment = { id: number; equipmentCode: string; name: string };
type Draft = {
  equipmentId: string;
  itemCode: string;
  startDate: string;
  endDate: string;
  productionQty: string;
  unit: string;
};
const EMPTY: Draft = {
  equipmentId: "",
  itemCode: "",
  startDate: "",
  endDate: "",
  productionQty: "",
  unit: "EA",
};
export function StatusBadge({ row }: { row: ProductionRecord }) {
  if (row.status === "draft") return <Badge tone="warning">초안</Badge>;
  return row.isEffective ? (
    <Badge tone="normal">확정 · 원단위 반영</Badge>
  ) : (
    <Badge tone="normal">확정 · 이전 버전</Badge>
  );
}
function fieldErrors(error: unknown): Record<string, string> {
  return error instanceof ApiError &&
    error.error.code === "VALIDATION_FAILED" &&
    error.error.details?.fields
    ? (error.error.details.fields as Record<string, string>)
    : {};
}
export function Production() {
  const { session, fail } = useSession();
  const keys = useRef(new MutationKeys());
  // F51. 가져온 행은 초안이고 확정은 아래 목록에서 사람이 한다.
  const [importMonth, setImportMonth] = useState("");
  const [importing, setImporting] = useState(false);
  const [importNote, setImportNote] = useState<string>();
  const [equipments, setEquipments] = useState<Equipment[]>([]);
  const [rows, setRows] = useState<ProductionRecord[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [history, setHistory] = useState(false);
  const [status, setStatus] = useState("");
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  // 패널: 닫힘(null) · 새 등록({ row: null }) · 초안 수정({ row })
  const [panel, setPanel] = useState<{ row: ProductionRecord | null } | null>(
    null,
  );
  const editing = panel?.row ?? null;
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [initial, setInitial] = useState<Draft>(EMPTY);
  const [saveError, setSaveError] = useState<unknown>();
  const [confirmDelete, setConfirmDelete] = useState<number>();
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState("");
  const handle = (e: unknown) => {
    if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
  };
  useEffect(() => {
    api<Equipment[]>("/api/v1/fems/equipments?limit=200")
      .then((r) => setEquipments(r.data))
      .catch(handle);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    const params = new URLSearchParams({
      offset: String(offset),
      limit: String(LIMIT),
    });
    if (history) params.set("includeHistory", "true");
    if (status) params.set("status", status);
    api<ProductionRecord[]>(`${BASE}?${params}`, { signal: controller.signal })
      .then((r) => {
        setRows(r.data);
        setTotal(r.page?.total ?? 0);
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        setLoadError(e);
        handle(e);
      });
    return () => controller.abort();
  }, [offset, history, status, reload]);
  const dirty =
    !!panel &&
    (Object.keys(draft) as (keyof Draft)[]).some(
      (k) => draft[k] !== initial[k],
    );
  const guard = useDiscardGuard(dirty);
  function openPanel(row: ProductionRecord | null) {
    const values = row
      ? {
          equipmentId: String(row.equipmentId),
          itemCode: row.itemCode,
          startDate: row.startDate,
          endDate: row.endDate,
          productionQty: String(Number(row.productionQty)),
          unit: row.unit,
        }
      : EMPTY;
    setPanel({ row });
    setDraft(values);
    setInitial(values);
    setSaveError(undefined);
  }
  function closePanel() {
    setPanel(null);
    setSaveError(undefined);
  }
  async function importFromMes() {
    if (!importMonth || !session?.csrfToken) return;
    setImporting(true);
    setSaveError(undefined);
    setImportNote(undefined);
    try {
      const r = await api<{ imported: number; skipped: string[] }>(
        `${BASE}/import`,
        {
          method: "POST",
          body: { month: importMonth },
          csrf: session.csrfToken,
          key: `import-${importMonth}-${Date.now()}`,
        },
      );
      setReload((n) => n + 1);
      setImportNote(
        `${importMonth}: ${r.data.imported}건을 초안으로 가져왔습니다.` +
          (r.data.skipped.length
            ? ` 건너뛴 ${r.data.skipped.length}건 — ${r.data.skipped.slice(0, 3).join(" ")}`
            : ""),
      );
    } catch (e) {
      setSaveError(e);
      handle(e);
    } finally {
      setImporting(false);
    }
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
      const r = await api<ProductionRecord>(path, {
        method,
        body,
        csrf: session?.csrfToken,
        key: keys.current.get(operation),
      });
      keys.current.complete(operation);
      setReload((n) => n + 1);
      return r.data;
    } catch (e) {
      // 응답 불확실(0·5xx)이면 키를 남겨 같은 요청으로 재확인한다.
      if (e instanceof ApiError && e.status > 0 && e.status < 500)
        keys.current.complete(operation);
      setSaveError(e);
      handle(e);
      return undefined;
    } finally {
      setPending(false);
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const payload = {
      ...draft,
      equipmentId: Number(draft.equipmentId),
      itemCode: draft.itemCode.trim().toUpperCase(),
    };
    const body = editing
      ? Object.fromEntries(
          Object.entries(payload).filter(([k, v]) => {
            const before = {
              equipmentId: editing.equipmentId,
              itemCode: editing.itemCode,
              startDate: editing.startDate,
              endDate: editing.endDate,
              productionQty: String(Number(editing.productionQty)),
              unit: editing.unit,
            }[k as keyof Draft];
            return before !== v;
          }),
        )
      : payload;
    if (editing && !Object.keys(body).length) {
      setDone("변경한 항목이 없습니다.");
      return;
    }
    const operation = `${editing ? `update:${editing.id}` : "create"}:${JSON.stringify(body)}`;
    const saved = await send(
      operation,
      editing ? `${BASE}/${editing.id}` : BASE,
      editing ? "PATCH" : "POST",
      body,
    );
    if (saved) {
      closePanel();
      setDone(
        `${saved.sourceKey} v${saved.versionNo} 초안을 저장했습니다. 확정해야 원단위에 반영됩니다.`,
      );
    }
  }
  async function act(row: ProductionRecord, action: "confirm" | "revise") {
    if (pending) return;
    const saved = await send(
      `${action}:${row.id}`,
      `${BASE}/${row.id}/${action}`,
      "POST",
    );
    if (!saved) return;
    if (action === "revise") {
      openPanel(saved);
      setDone(
        `${saved.sourceKey} v${saved.versionNo} 정정 초안을 만들었습니다.`,
      );
    } else {
      // 확정한 초안은 더 고칠 수 없으므로 열려 있던 수정 패널을 닫는다.
      if (editing?.id === row.id) closePanel();
      setDone(`${saved.sourceKey} v${saved.versionNo}을 확정했습니다.`);
    }
  }
  async function remove(row: ProductionRecord) {
    if (pending) return;
    await send(`delete:${row.id}`, `${BASE}/${row.id}`, "DELETE");
    setConfirmDelete(undefined);
    if (editing?.id === row.id) closePanel();
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
  const errors = fieldErrors(saveError);
  const revision = !!editing && editing.versionNo > 1;
  // 좁은 화면에서도 상태와 작업 버튼이 먼저 보이도록 원천 키 다음에 둔다.
  const columns: Column<ProductionRecord>[] = [
    {
      key: "sourceKey",
      label: "원천 키",
      render: (r) => `${r.sourceKey} · v${r.versionNo}`,
    },
    { key: "status", label: "상태", render: (r) => <StatusBadge row={r} /> },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        r.status === "draft" ? (
          confirmDelete === r.id ? (
            <span className="row-actions">
              <button
                className="secondary"
                disabled={pending}
                onClick={() => void remove(r)}
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
                aria-pressed={editing?.id === r.id}
                onClick={() => guard.guard(() => openPanel(r))}
              >
                수정
              </button>
              <button
                className="link-button"
                disabled={pending}
                onClick={() => void act(r, "confirm")}
              >
                확정
              </button>
              <button
                className="link-button"
                onClick={() => setConfirmDelete(r.id)}
              >
                삭제
              </button>
            </span>
          )
        ) : r.isLatest ? (
          <button
            className="link-button"
            disabled={pending}
            onClick={() => guard.guard(() => void act(r, "revise"))}
          >
            정정
          </button>
        ) : (
          "—"
        ),
    },
    {
      key: "productionQty",
      label: "생산량",
      render: (r) =>
        `${Number(r.productionQty).toLocaleString("ko-KR")} ${r.unit}`,
    },
    {
      key: "equipmentCode",
      label: "설비",
      render: (r) => `${r.equipmentCode} ${r.equipmentName}`,
    },
    { key: "itemCode", label: "품목" },
    {
      key: "startDate",
      label: "기간",
      render: (r) => <DateRange from={r.startDate} to={r.endDate} />,
    },
  ];
  const panelError = Object.keys(errors).length ? undefined : saveError;
  // 목록+등록 패널 기준 화면(UI-02): 목록을 넓게 두고, 등록·수정·정정은 같은 오른쪽 패널에서 한다.
  return (
    <div className="page-fill">
      <PageTitle
        id="F-05"
        title="생산량 등록"
        subtitle="원단위의 분모 · 확정한 기록은 바꾸지 않고 새 버전으로 정정합니다"
        help="fems/f-05"
        actions={
          <>
            <label>
              가져올 월
              <input
                type="month"
                value={importMonth}
                onChange={(e) => setImportMonth(e.target.value)}
              />
            </label>
            <button
              type="button"
              className="secondary"
              disabled={!importMonth || importing}
              onClick={() => void importFromMes()}
            >
              MES에서 가져오기
            </button>
            <button
              type="button"
              aria-pressed={!!panel && !editing}
              onClick={() => guard.guard(() => openPanel(null))}
            >
              생산량 등록
            </button>
          </>
        }
      />
      {importNote && <p role="status">{importNote}</p>}
      <p className="muted" role="note">
        MES를 쓰는 환경이라면 생산실적에서 자동으로 넘어오는 값입니다. FEMS는
        독립 솔루션이라 여기서 직접 입력하고, 품목은 코드 문자열로 받습니다.
        시드의 MES:로 시작하는 기록은 MES 실행에서 파생된 예시입니다.
      </p>
      {!panel && <ErrorNotice error={panelError} />}
      {done && <p role="status">{done}</p>}
      <div className="split-view fill">
        <section className="fill">
          <div className="filter-bar">
            <label>
              상태
              <select
                value={status}
                onChange={(e) => {
                  setOffset(0);
                  setStatus(e.target.value);
                }}
              >
                <option value="">전체</option>
                <option value="draft">초안</option>
                <option value="confirmed">확정</option>
              </select>
            </label>
            <label className="inline-check">
              <input
                type="checkbox"
                checked={history}
                onChange={(e) => {
                  setOffset(0);
                  setHistory(e.target.checked);
                }}
              />
              이전 버전 포함
            </label>
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
              caption="생산량 기록"
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason="조건에 맞는 생산량 기록이 없습니다. 새 기록을 등록할 수 있습니다."
                  action="생산량 등록"
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
                ? `${editing.sourceKey} v${editing.versionNo} 초안 수정`
                : "생산량 등록 (초안)"
            }
            guard={guard}
            onClose={closePanel}
            onSubmit={(e) => void submit(e)}
            actions={
              <>
                <button type="submit" disabled={pending} aria-busy={pending}>
                  {editing ? "초안 저장" : "초안 등록"}
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
            {revision && (
              <p className="muted">
                정정 버전은 설비·품목·단위를 바꿀 수 없습니다. 다른 기록이면
                새로 등록하세요.
              </p>
            )}
            <div className="field">
              <label htmlFor="production-equipment">설비</label>
              <select
                id="production-equipment"
                value={draft.equipmentId}
                required
                disabled={revision}
                aria-invalid={!!errors.equipmentId}
                onChange={(e) =>
                  setDraft({ ...draft, equipmentId: e.target.value })
                }
              >
                <option value="">선택</option>
                {equipments.map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.equipmentCode} {q.name}
                  </option>
                ))}
              </select>
              {errors.equipmentId && <small>{errors.equipmentId}</small>}
            </div>
            <Field
              label="품목 코드"
              value={draft.itemCode}
              required
              disabled={revision}
              maxLength={40}
              error={errors.itemCode}
              onChange={(e) =>
                setDraft({ ...draft, itemCode: e.target.value.toUpperCase() })
              }
            />
            <div className="field-row">
              <Field
                label="시작일"
                type="date"
                value={draft.startDate}
                required
                error={errors.startDate}
                onChange={(e) =>
                  setDraft({ ...draft, startDate: e.target.value })
                }
              />
              <Field
                label="종료일 (포함)"
                type="date"
                value={draft.endDate}
                required
                error={errors.endDate}
                onChange={(e) =>
                  setDraft({ ...draft, endDate: e.target.value })
                }
              />
            </div>
            <div className="field-row">
              <Field
                label="생산량"
                inputMode="decimal"
                value={draft.productionQty}
                required
                pattern="\d+(\.\d{1,3})?"
                title="0 이상, 소수 3자리까지"
                error={errors.productionQty}
                onChange={(e) =>
                  setDraft({ ...draft, productionQty: e.target.value })
                }
              />
              <Field
                label="단위"
                value={draft.unit}
                required
                disabled={revision}
                maxLength={10}
                error={errors.unit}
                onChange={(e) => setDraft({ ...draft, unit: e.target.value })}
              />
            </div>
          </FormPanel>
        )}
      </div>
    </div>
  );
}
