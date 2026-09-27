// F-10 설비 — FEMS 기준정보 설비 목록 + 등록/수정 패널 (FS-018a)
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
import { MasterOrder } from "./EnergySources";

const BASE = "/api/v1/fems/equipments";
const LOCATIONS_BASE = "/api/v1/fems/locations";
const LIMIT = 20;

export type Equipment = {
  id: number;
  locationId: number;
  equipmentCode: string;
  name: string;
  equipmentType: string;
  isActive: boolean;
  createdAt: string;
};

export type Location = {
  id: number;
  locationCode: string;
  name: string;
  kind: string;
};

type Draft = Omit<Equipment, "id" | "createdAt">;

const EMPTY: Draft = {
  equipmentCode: "",
  name: "",
  equipmentType: "",
  locationId: 0,
  isActive: true,
};

function fieldErrors(error: unknown): Record<string, string> {
  return error instanceof ApiError &&
    error.error.code === "VALIDATION_FAILED" &&
    error.error.details?.fields
    ? (error.error.details.fields as Record<string, string>)
    : {};
}

export function Equipments() {
  const { session, fail } = useSession();
  const keys = useRef(new MutationKeys());
  const [rows, setRows] = useState<Equipment[]>();
  const [locations, setLocations] = useState<Location[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [activeOnly, setActiveOnly] = useState(false);
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [panel, setPanel] = useState<{ row: Equipment | null } | null>(null);
  const editing = panel?.row ?? null;
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [initial, setInitial] = useState<Draft>(EMPTY);
  const [saveError, setSaveError] = useState<unknown>();
  const [confirmDelete, setConfirmDelete] = useState<number>();
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    api<Location[]>(LOCATIONS_BASE, { signal: controller.signal })
      .then((r) => {
        setLocations(r.data);
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
    api<Equipment[]>(
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

  function openPanel(row: Equipment | null) {
    const defaultLoc = locations && locations.length > 0 ? locations[0].id : 0;
    const values: Draft = row
      ? {
          equipmentCode: row.equipmentCode,
          name: row.name,
          equipmentType: row.equipmentType,
          locationId: row.locationId,
          isActive: row.isActive,
        }
      : { ...EMPTY, locationId: defaultLoc };
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

  async function remove(row: Equipment) {
    if (pending) return;
    const ok = await send(`delete:${row.id}`, `${BASE}/${row.id}`, "DELETE");
    setConfirmDelete(undefined);
    if (ok) {
      if (editing?.id === row.id) closePanel();
      setDone(`${row.name} 설비를 삭제했습니다.`);
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

  if (locations && locations.length === 0) {
    return (
      <>
        <PageTitle
          id="F-10"
          title="설비"
          subtitle="공간별 에너지 소비 설비를 관리합니다"
          help="fems/f-10"
        />
        <MasterOrder />
        <EmptyState
          reason="등록된 공간이 없습니다. 설비는 공간이 먼저 등록되어 있어야 합니다."
          to="/help/fems/f-09"
          action="공간 안내 보기"
        />
      </>
    );
  }

  const errors = fieldErrors(saveError);
  const locationMap = new Map((locations ?? []).map((l) => [l.id, l.name]));

  const columns: Column<Equipment>[] = [
    { key: "equipmentCode", label: "코드" },
    { key: "name", label: "설비명" },
    { key: "equipmentType", label: "설비 유형" },
    {
      key: "locationId",
      label: "설치 공간",
      render: (r) => locationMap.get(r.locationId) ?? String(r.locationId),
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
        id="F-10"
        title="설비"
        subtitle="공간별 에너지 소비 설비를 관리합니다"
        help="fems/f-10"
        actions={
          <button
            type="button"
            aria-pressed={!!panel && !editing}
            onClick={() => guard.guard(() => openPanel(null))}
          >
            설비 등록
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
              사용 중인 설비만
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
              caption="설비 목록"
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason="등록된 설비가 없습니다. 계측기는 설비가 있어야 등록할 수 있습니다."
                  action="설비 등록"
                  onAction={() => guard.guard(() => openPanel(null))}
                />
              }
            />
          )}
        </section>
        {panel && (
          <FormPanel
            key={editing?.id ?? "new"}
            title={editing ? `${editing.name} 수정` : "설비 등록"}
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
              label="설비 코드"
              value={draft.equipmentCode}
              required
              maxLength={30}
              pattern="[A-Z][A-Z0-9_\-]{1,29}"
              title="영문 대문자로 시작하는 2~30자 (대문자·숫자·_·-)"
              error={errors.equipmentCode}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  equipmentCode: e.target.value.toUpperCase(),
                })
              }
            />
            <Field
              label="설비명"
              value={draft.name}
              required
              maxLength={100}
              error={errors.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
            <Field
              label="설비 유형"
              value={draft.equipmentType}
              required
              maxLength={40}
              error={errors.equipmentType}
              onChange={(e) =>
                setDraft({ ...draft, equipmentType: e.target.value })
              }
            />
            <div className="field">
              <label htmlFor="location-id">설치 공간</label>
              <select
                id="location-id"
                value={draft.locationId}
                aria-invalid={Boolean(errors.locationId)}
                onChange={(e) =>
                  setDraft({ ...draft, locationId: Number(e.target.value) })
                }
              >
                {(locations ?? []).map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name} ({loc.locationCode})
                  </option>
                ))}
              </select>
              {errors.locationId && <small>{errors.locationId}</small>}
            </div>
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
