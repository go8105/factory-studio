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
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
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
  const [panel, setPanel] = useState<{ row: EnergySource | null } | null>(null);
  const editing = panel?.row ?? null;
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [initial, setInitial] = useState<Draft>(EMPTY);
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
  const dirty =
    !!panel &&
    (Object.keys(draft) as (keyof Draft)[]).some(
      (k) => draft[k] !== initial[k],
    );
  const guard = useDiscardGuard(dirty);
  function openPanel(row: EnergySource | null) {
    const values = row ? { ...row } : EMPTY;
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
      closePanel();
      setDone(editing ? "수정했습니다." : "등록했습니다.");
    }
  }
  async function remove(row: EnergySource) {
    if (pending) return;
    const ok = await send(`delete:${row.id}`, `${BASE}/${row.id}`, "DELETE");
    setConfirmDelete(undefined);
    if (ok) {
      if (editing?.id === row.id) closePanel();
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
            <button
              className="link-button"
              aria-pressed={editing?.id === r.id}
              onClick={() => guard.guard(() => openPanel(r))}
            >
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
  const panelError = Object.keys(errors).length ? undefined : saveError;
  return (
    <div className="page-fill">
      <PageTitle
        id="F-11"
        title="에너지원"
        subtitle="전력·가스·용수를 같은 구조로 관리합니다"
        help="fems/f-11"
        actions={
          <button
            type="button"
            aria-pressed={!!panel && !editing}
            onClick={() => guard.guard(() => openPanel(null))}
          >
            에너지원 등록
          </button>
        }
      />
      <MasterOrder />
      {!panel && <ErrorNotice error={panelError} />}
      {done && <p role="status">{done}</p>}
      <div className="split-view fill">
        <section className="fill">
          <div className="filter-bar">
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
              caption="에너지원 목록"
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason="등록된 에너지원이 없습니다. 계측기·계수·요금제는 에너지원이 있어야 등록할 수 있습니다."
                  action="에너지원 등록"
                  onAction={() => guard.guard(() => openPanel(null))}
                />
              }
            />
          )}
        </section>
        {panel && (
          <FormPanel
            key={editing?.id ?? "new"}
            title={editing ? `${editing.name} 수정` : "에너지원 등록"}
            guard={guard}
            onClose={closePanel}
            onSubmit={(e) => void submit(e)}
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
          </FormPanel>
        )}
      </div>
    </div>
  );
}
