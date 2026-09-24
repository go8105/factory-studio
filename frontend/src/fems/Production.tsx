// F-05 생산량 등록 — 원단위의 분모. 확정은 불변, 정정은 새 버전(초안)으로 (FS-018i)
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError, MutationKeys } from "../shared/api";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
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
  const [equipments, setEquipments] = useState<Equipment[]>([]);
  const [rows, setRows] = useState<ProductionRecord[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [history, setHistory] = useState(false);
  const [status, setStatus] = useState("");
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [editing, setEditing] = useState<ProductionRecord | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
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
  function startEdit(row: ProductionRecord | null) {
    setEditing(row);
    setDraft(
      row
        ? {
            equipmentId: String(row.equipmentId),
            itemCode: row.itemCode,
            startDate: row.startDate,
            endDate: row.endDate,
            productionQty: String(Number(row.productionQty)),
            unit: row.unit,
          }
        : EMPTY,
    );
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
      startEdit(null);
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
      startEdit(saved);
      setDone(
        `${saved.sourceKey} v${saved.versionNo} 정정 초안을 만들었습니다.`,
      );
    } else setDone(`${saved.sourceKey} v${saved.versionNo}을 확정했습니다.`);
  }
  async function remove(row: ProductionRecord) {
    if (pending) return;
    await send(`delete:${row.id}`, `${BASE}/${row.id}`, "DELETE");
    setConfirmDelete(undefined);
    if (editing?.id === row.id) startEdit(null);
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
              <button className="link-button" onClick={() => startEdit(r)}>
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
            onClick={() => void act(r, "revise")}
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
      render: (r) =>
        r.startDate === r.endDate
          ? r.startDate
          : `${r.startDate} ~ ${r.endDate}`,
    },
  ];
  return (
    <>
      <PageTitle
        id="F-05"
        title="생산량 등록"
        subtitle="원단위의 분모 · 확정한 기록은 바꾸지 않고 새 버전으로 정정합니다"
        help="fems/f-05"
      />
      <p className="muted" role="note">
        MES를 쓰는 환경이라면 생산실적에서 자동으로 넘어오는 값입니다. FEMS는
        독립 솔루션이라 여기서 직접 입력하고, 품목은 코드 문자열로 받습니다.
        시드의 MES:로 시작하는 기록은 MES 실행에서 파생된 예시입니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      {done && <p role="status">{done}</p>}
      <div className="master-grid">
        <section>
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
                  reason="조건에 맞는 생산량 기록이 없습니다. 오른쪽에서 새 기록을 등록할 수 있습니다."
                  to="#production-form"
                  action="생산량 등록"
                />
              }
            />
          )}
        </section>
        <form
          id="production-form"
          className="panel"
          onSubmit={(e) => void submit(e)}
          aria-label={editing ? "생산량 초안 수정" : "생산량 등록"}
        >
          <h2>
            {editing
              ? `${editing.sourceKey} v${editing.versionNo} 초안 수정`
              : "생산량 등록 (초안)"}
          </h2>
          {revision && (
            <p className="muted">
              정정 버전은 설비·품목·단위를 바꿀 수 없습니다. 다른 기록이면 새로
              등록하세요.
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
          <Field
            label="시작일"
            type="date"
            value={draft.startDate}
            required
            error={errors.startDate}
            onChange={(e) => setDraft({ ...draft, startDate: e.target.value })}
          />
          <Field
            label="종료일 (포함)"
            type="date"
            value={draft.endDate}
            required
            error={errors.endDate}
            onChange={(e) => setDraft({ ...draft, endDate: e.target.value })}
          />
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
          <div className="row-actions">
            <button type="submit" disabled={pending}>
              {editing ? "초안 저장" : "초안 등록"}
            </button>
            {editing && (
              <button
                type="button"
                className="secondary"
                onClick={() => startEdit(null)}
              >
                새로 등록
              </button>
            )}
          </div>
        </form>
      </div>
    </>
  );
}
