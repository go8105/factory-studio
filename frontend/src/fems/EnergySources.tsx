// F-11 에너지원 — FEMS 기준정보 목록 + 등록/수정 패널 패턴의 기준 구현 (FS-018a)
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
const BASE = "/api/v1/fems/energy-sources";
const LIMIT = 20;
export type EnergySource = {
  id: number;
  sourceCode: string;
  name: string;
  sourceKind: string;
  measureUnit: string;
  isBillable: boolean;
  isActive: boolean;
  createdAt: string;
};
type Draft = Omit<EnergySource, "id" | "createdAt">;
const KINDS = {
  ELECTRIC: "전기",
  FUEL: "연료",
  HEAT: "열",
  UTILITY: "유틸리티",
};
const UNITS = ["kWh", "Nm3", "m3", "ton"];
const EMPTY: Draft = {
  sourceCode: "",
  name: "",
  sourceKind: "ELECTRIC",
  measureUnit: "kWh",
  isBillable: true,
  isActive: true,
};
// 기준정보 공통: 등록 순서 안내 (FS-008a FEMS §2)
export function MasterOrder() {
  return (
    <ol className="master-order" aria-label="기준정보 등록 순서">
      <li>사업장 → 공간 → 설비</li>
      <li>에너지원</li>
      <li>계측기 → 채널 (설비·에너지원 필요)</li>
    </ol>
  );
}
function fieldErrors(error: unknown): Record<string, string> {
  return error instanceof ApiError &&
    error.error.code === "VALIDATION_FAILED" &&
    error.error.details?.fields
    ? (error.error.details.fields as Record<string, string>)
    : {};
}
export function EnergySources() {
  const { session, fail } = useSession();
  const keys = useRef(new MutationKeys());
  const [rows, setRows] = useState<EnergySource[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [activeOnly, setActiveOnly] = useState(false);
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [editing, setEditing] = useState<EnergySource | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [saveError, setSaveError] = useState<unknown>();
  const [confirmDelete, setConfirmDelete] = useState<number>();
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    api<EnergySource[]>(
      `${BASE}?offset=${offset}&limit=${LIMIT}${activeOnly ? "&active=true" : ""}`,
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
  }, [offset, activeOnly, reload]);
  function startEdit(row: EnergySource | null) {
    setEditing(row);
    setDraft(row ? { ...row } : EMPTY);
    setSaveError(undefined);
    setDone("");
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
      // 응답 불확실(0·5xx)이면 키를 남겨 같은 요청으로 재확인한다.
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
    const body = editing
      ? Object.fromEntries(
          Object.entries(draft).filter(
            ([k, v]) => editing[k as keyof Draft] !== v,
          ),
        )
      : draft;
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
      startEdit(null);
      setDone(editing ? "수정했습니다." : "등록했습니다.");
    }
  }
  async function remove(row: EnergySource) {
    if (pending) return;
    const ok = await send(`delete:${row.id}`, `${BASE}/${row.id}`, "DELETE");
    setConfirmDelete(undefined);
    if (ok) {
      if (editing?.id === row.id) startEdit(null);
      setDone(`${row.name} 에너지원을 삭제했습니다.`);
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
  const errors = fieldErrors(saveError);
  const columns: Column<EnergySource>[] = [
    { key: "sourceCode", label: "코드" },
    { key: "name", label: "에너지원명" },
    {
      key: "sourceKind",
      label: "구분",
      render: (r) => KINDS[r.sourceKind as keyof typeof KINDS] ?? r.sourceKind,
    },
    { key: "measureUnit", label: "계측 단위" },
    {
      key: "isBillable",
      label: "요금 부과",
      render: (r) => (r.isBillable ? "부과" : "미부과"),
    },
    {
      key: "isActive",
      label: "사용",
      render: (r) => (
        <Badge tone={r.isActive ? "normal" : "warning"}>
          {r.isActive ? "사용" : "사용 안 함"}
        </Badge>
      ),
    },
    {
      key: "id",
      label: "관리",
      render: (r) =>
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
              onClick={() => setConfirmDelete(r.id)}
            >
              삭제
            </button>
          </span>
        ),
    },
  ];
  return (
    <>
      <PageTitle
        id="F-11"
        title="에너지원"
        subtitle="전력·가스·용수를 같은 구조로 관리합니다"
        help="fems/f-11"
      />
      <MasterOrder />
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <div className="master-grid">
        <section>
          <label className="inline-check">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(e) => {
                setOffset(0);
                setActiveOnly(e.target.checked);
              }}
            />
            사용 중인 에너지원만
          </label>
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
              caption="에너지원 목록"
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason="등록된 에너지원이 없습니다. 계측기·계수·요금제는 에너지원이 있어야 등록할 수 있습니다."
                  to="#energy-source-form"
                  action="에너지원 등록"
                />
              }
            />
          )}
        </section>
        <form
          id="energy-source-form"
          className="panel"
          onSubmit={(e) => void submit(e)}
          aria-label={editing ? "에너지원 수정" : "에너지원 등록"}
        >
          <h2>{editing ? `${editing.name} 수정` : "에너지원 등록"}</h2>
          <Field
            label="에너지원 코드"
            value={draft.sourceCode}
            required
            maxLength={20}
            pattern="[A-Z][A-Z0-9_]{1,19}"
            title="영문 대문자로 시작하는 2~20자 (대문자·숫자·_)"
            error={errors.sourceCode}
            onChange={(e) =>
              setDraft({ ...draft, sourceCode: e.target.value.toUpperCase() })
            }
          />
          <Field
            label="에너지원명"
            value={draft.name}
            required
            maxLength={50}
            error={errors.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />
          <div className="field">
            <label htmlFor="source-kind">에너지 구분</label>
            <select
              id="source-kind"
              value={draft.sourceKind}
              onChange={(e) =>
                setDraft({ ...draft, sourceKind: e.target.value })
              }
            >
              {Object.entries(KINDS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="measure-unit">계측 단위</label>
            <select
              id="measure-unit"
              value={draft.measureUnit}
              aria-describedby="measure-unit-note"
              onChange={(e) =>
                setDraft({ ...draft, measureUnit: e.target.value })
              }
            >
              {UNITS.map((u) => (
                <option key={u}>{u}</option>
              ))}
            </select>
            <small id="measure-unit-note">
              계측기·계수·요금제가 참조 중이면 단위를 바꿀 수 없습니다.
            </small>
          </div>
          <label className="inline-check">
            <input
              type="checkbox"
              checked={draft.isBillable}
              onChange={(e) =>
                setDraft({ ...draft, isBillable: e.target.checked })
              }
            />
            요금 부과 대상
          </label>
          <label className="inline-check">
            <input
              type="checkbox"
              checked={draft.isActive}
              onChange={(e) =>
                setDraft({ ...draft, isActive: e.target.checked })
              }
            />
            사용 (끄면 새 입력에서 제외, 기존 기록은 유지)
          </label>
          {done && <p role="status">{done}</p>}
          <div className="row-actions">
            <button type="submit" disabled={pending}>
              {editing ? "수정 저장" : "등록"}
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
