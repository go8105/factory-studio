// F-09 사업장·공간 — 사업장 목록·패널과 공간 목록·패널 (FS-018m)
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

const SITES = "/api/v1/fems/sites";
const LOCATIONS = "/api/v1/fems/locations";

export type Site = {
  id: number;
  siteCode: string;
  name: string;
  timezone: string;
};

export type Place = {
  id: number;
  siteId: number;
  parentLocationId: number | null;
  locationCode: string;
  name: string;
  kind: "building" | "zone" | "workcenter";
};

const KINDS = { building: "건물", zone: "구역", workcenter: "작업장" };

type SiteDraft = { siteCode: string; name: string; timezone: string };
type PlaceDraft = {
  siteId: number;
  parentLocationId: number | null;
  locationCode: string;
  name: string;
  kind: Place["kind"];
};

function fieldErrors(error: unknown): Record<string, string> {
  return error instanceof ApiError &&
    error.error.code === "VALIDATION_FAILED" &&
    error.error.details?.fields
    ? (error.error.details.fields as Record<string, string>)
    : {};
}

/** 수정 시 바뀐 값만 보낸다. */
function changed(draft: object, current: object) {
  return Object.fromEntries(
    Object.entries(draft).filter(
      ([k, v]) => (current as Record<string, unknown>)[k] !== v,
    ),
  );
}

export function Sites() {
  const { session, fail } = useSession();
  const keys = useRef(new MutationKeys());
  const [sites, setSites] = useState<Site[]>();
  const [places, setPlaces] = useState<Place[]>([]);
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  type PanelState =
    { type: "site"; row: Site | null } | { type: "place"; row: Place | null };

  const [panel, setPanel] = useState<PanelState | null>(null);
  const editingSite = panel?.type === "site" ? panel.row : null;
  const editingPlace = panel?.type === "place" ? panel.row : null;
  const [siteDraft, setSiteDraft] = useState<SiteDraft>();
  const [initialSite, setInitialSite] = useState<SiteDraft>();
  const [placeDraft, setPlaceDraft] = useState<PlaceDraft>();
  const [initialPlace, setInitialPlace] = useState<PlaceDraft>();
  const [saveError, setSaveError] = useState<unknown>();
  const [confirmDelete, setConfirmDelete] = useState<string>();
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const signal = controller.signal;
    setLoadError(undefined);
    Promise.all([
      api<Site[]>(SITES, { signal }),
      api<Place[]>(LOCATIONS, { signal }),
    ])
      .then(([s, l]) => {
        setSites(s.data);
        setPlaces(l.data);
      })
      .catch((e) => {
        if (signal.aborted) return;
        setLoadError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [reload]);

  const sDraft = siteDraft ?? {
    siteCode: "",
    name: "",
    timezone: "Asia/Seoul",
  };
  const pDraft = placeDraft ?? {
    siteId: sites?.[0]?.id ?? 0,
    parentLocationId: null,
    locationCode: "",
    name: "",
    kind: "zone" as const,
  };

  const dirty =
    panel?.type === "site" && initialSite
      ? (Object.keys(sDraft) as (keyof SiteDraft)[]).some(
          (k) => sDraft[k] !== initialSite[k],
        )
      : panel?.type === "place" && initialPlace
        ? (Object.keys(pDraft) as (keyof PlaceDraft)[]).some(
            (k) => pDraft[k] !== initialPlace[k],
          )
        : false;
  const guard = useDiscardGuard(dirty);

  function openSite(row: Site | null) {
    const values: SiteDraft = row
      ? { siteCode: row.siteCode, name: row.name, timezone: row.timezone }
      : { siteCode: "", name: "", timezone: "Asia/Seoul" };
    setPanel({ type: "site", row });
    setSiteDraft(values);
    setInitialSite(values);
    setSaveError(undefined);
    setDone("");
  }

  function openPlace(row: Place | null) {
    const values: PlaceDraft = row
      ? {
          siteId: row.siteId,
          parentLocationId: row.parentLocationId,
          locationCode: row.locationCode,
          name: row.name,
          kind: row.kind,
        }
      : {
          siteId: sites?.[0]?.id ?? 0,
          parentLocationId: null,
          locationCode: "",
          name: "",
          kind: "zone",
        };
    setPanel({ type: "place", row });
    setPlaceDraft(values);
    setInitialPlace(values);
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
      setConfirmDelete(undefined);
    }
  }

  async function remove(key: string, path: string) {
    if (pending) return;
    const ok = await send(`delete:${key}`, path, "DELETE");
    if (ok) {
      if (panel?.type === "site" && key === `site:${panel.row?.id}`)
        closePanel();
      if (panel?.type === "place" && key === `place:${panel.row?.id}`)
        closePanel();
      setDone(
        key.startsWith("site:")
          ? "사업장을 삭제했습니다."
          : "공간을 삭제했습니다.",
      );
    }
  }

  async function submitSite(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const draft = {
      siteCode: sDraft.siteCode.trim().toUpperCase(),
      name: sDraft.name.trim(),
      timezone: sDraft.timezone.trim(),
    };
    const body = editingSite ? changed(draft, editingSite) : draft;
    if (editingSite && !Object.keys(body).length) {
      setDone("변경한 항목이 없습니다.");
      return;
    }
    const ok = await send(
      `site:${editingSite?.id ?? "new"}:${JSON.stringify(body)}`,
      editingSite ? `${SITES}/${editingSite.id}` : SITES,
      editingSite ? "PATCH" : "POST",
      body,
    );
    if (ok) {
      closePanel();
      setDone(
        editingSite ? "사업장을 수정했습니다." : "사업장을 등록했습니다.",
      );
    }
  }

  async function submitPlace(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const draft = {
      ...pDraft,
      locationCode: pDraft.locationCode.trim().toUpperCase(),
      name: pDraft.name.trim(),
    };
    // 사업장은 등록 때만 정한다(수정 중에는 잠겨 있어 바뀐 값에 들어가지 않는다).
    const body = editingPlace ? changed(draft, editingPlace) : draft;
    if (editingPlace && !Object.keys(body).length) {
      setDone("변경한 항목이 없습니다.");
      return;
    }
    const ok = await send(
      `place:${editingPlace?.id ?? "new"}:${JSON.stringify(body)}`,
      editingPlace ? `${LOCATIONS}/${editingPlace.id}` : LOCATIONS,
      editingPlace ? "PATCH" : "POST",
      body,
    );
    if (ok) {
      closePanel();
      setDone(editingPlace ? "공간을 수정했습니다." : "공간을 등록했습니다.");
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
  const siteName = (id: number) =>
    sites?.find((s) => s.id === id)?.name ?? String(id);
  const placeCode = (id: number | null) =>
    id === null
      ? "-"
      : (places.find((p) => p.id === id)?.locationCode ?? String(id));
  const deleteButtons = (key: string, path: string) =>
    confirmDelete === key ? (
      <>
        <button
          type="button"
          className="secondary"
          disabled={pending}
          onClick={() => void remove(key, path)}
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
      </>
    ) : (
      <button
        type="button"
        className="link-button"
        onClick={() => {
          setConfirmDelete(key);
          setSaveError(undefined);
        }}
      >
        삭제
      </button>
    );

  const siteColumns: Column<Site>[] = [
    { key: "siteCode", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={panel?.type === "site" && panel.row?.id === r.id}
            onClick={() => guard.guard(() => openSite(r))}
          >
            수정
          </button>
          {deleteButtons(`site:${r.id}`, `${SITES}/${r.id}`)}
        </span>
      ),
    },
    { key: "name", label: "사업장명" },
    { key: "timezone", label: "시간대" },
  ];

  const placeColumns: Column<Place>[] = [
    { key: "locationCode", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={panel?.type === "place" && panel.row?.id === r.id}
            onClick={() => guard.guard(() => openPlace(r))}
          >
            수정
          </button>
          {deleteButtons(`place:${r.id}`, `${LOCATIONS}/${r.id}`)}
        </span>
      ),
    },
    { key: "name", label: "공간명" },
    { key: "kind", label: "종류", render: (r) => KINDS[r.kind] },
    { key: "siteId", label: "사업장", render: (r) => siteName(r.siteId) },
    {
      key: "parentLocationId",
      label: "상위 공간",
      render: (r) => placeCode(r.parentLocationId),
    },
  ];

  const parentChoices = places.filter(
    (p) => p.siteId === pDraft.siteId && p.id !== editingPlace?.id,
  );

  const panelError = Object.keys(errors).length ? undefined : saveError;

  return (
    <div className="page-fill">
      <PageTitle
        id="F-09"
        title="사업장·공간"
        subtitle="사업장과 그 안의 건물·구역·작업장을 관리합니다"
        help="fems/f-09"
      />
      <MasterOrder />
      <p className="muted" role="note">
        FEMS 전용 기준정보입니다. MES의 사업장·공간과 코드가 같아도 별개
        데이터입니다.
      </p>
      {!panel && <ErrorNotice error={panelError} />}
      {done && <p role="status">{done}</p>}
      <ErrorNotice error={loadError} retry={() => setReload((n) => n + 1)} />
      {!sites ? (
        !loadError && <Loading />
      ) : (
        <div className="split-view fill">
          <div
            className="fill"
            style={{
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: "var(--s5)",
            }}
          >
            <section>
              <div className="section-heading">
                <h2>사업장</h2>
                <button
                  type="button"
                  aria-pressed={panel?.type === "site" && !panel.row}
                  onClick={() => guard.guard(() => openSite(null))}
                >
                  사업장 등록
                </button>
              </div>
              <DataTable
                rows={sites}
                columns={siteColumns}
                caption="사업장 목록"
                offset={0}
                total={sites.length}
                limit={sites.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="등록된 사업장이 없습니다. 첫 사업장을 등록하세요."
                    action="사업장 등록"
                    onAction={() => guard.guard(() => openSite(null))}
                  />
                }
              />
            </section>

            {sites.length === 0 ? (
              <p className="muted" role="note">
                공간은 사업장을 먼저 등록한 뒤 추가합니다.
              </p>
            ) : (
              <section>
                <div className="section-heading">
                  <h2>공간</h2>
                  <button
                    type="button"
                    aria-pressed={panel?.type === "place" && !panel.row}
                    onClick={() => guard.guard(() => openPlace(null))}
                  >
                    공간 등록
                  </button>
                </div>
                <DataTable
                  rows={places}
                  columns={placeColumns}
                  caption="공간 목록"
                  offset={0}
                  total={places.length}
                  limit={places.length || 1}
                  onPage={() => undefined}
                  empty={
                    <EmptyState
                      reason="등록된 공간이 없습니다. 설비와 계측기는 공간에 놓입니다."
                      action="공간 등록"
                      onAction={() => guard.guard(() => openPlace(null))}
                    />
                  }
                />
              </section>
            )}
          </div>

          {panel && (
            <FormPanel
              key={panel.type + ":" + (panel.row?.id ?? "new")}
              title={
                panel.type === "site"
                  ? panel.row
                    ? `${panel.row.siteCode} 수정`
                    : "사업장 등록"
                  : panel.row
                    ? `${panel.row.locationCode} 수정`
                    : "공간 등록"
              }
              guard={guard}
              onClose={closePanel}
              onSubmit={(e) =>
                void (panel.type === "site" ? submitSite(e) : submitPlace(e))
              }
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    {panel.row ? "저장" : "등록"}
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
              {panel.type === "site" ? (
                <>
                  <Field
                    label="사업장 코드"
                    value={sDraft.siteCode}
                    required
                    maxLength={30}
                    pattern="[A-Z][A-Z0-9_\-]{1,29}"
                    title="영문 대문자로 시작하는 2~30자 (대문자·숫자·_·-)"
                    error={errors.siteCode}
                    onChange={(e) =>
                      setSiteDraft({
                        ...sDraft,
                        siteCode: e.target.value.toUpperCase(),
                      })
                    }
                  />
                  <Field
                    label="사업장명"
                    value={sDraft.name}
                    required
                    maxLength={100}
                    error={errors.name}
                    onChange={(e) =>
                      setSiteDraft({ ...sDraft, name: e.target.value })
                    }
                  />
                  <Field
                    label="시간대"
                    value={sDraft.timezone}
                    required
                    maxLength={60}
                    placeholder="Asia/Seoul"
                    error={errors.timezone}
                    onChange={(e) =>
                      setSiteDraft({ ...sDraft, timezone: e.target.value })
                    }
                  />
                  <p className="muted">
                    계측·배분·생산량의 날짜 경계를 이 시간대로 정합니다. 기록이
                    있는 사업장은 시간대를 바꿀 수 없습니다.
                  </p>
                </>
              ) : (
                <>
                  <div className="field">
                    <label htmlFor="place-site">사업장</label>
                    <select
                      id="place-site"
                      value={pDraft.siteId}
                      disabled={!!panel.row}
                      onChange={(e) =>
                        setPlaceDraft({
                          ...pDraft,
                          siteId: Number(e.target.value),
                          parentLocationId: null,
                        })
                      }
                    >
                      {sites.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name} ({s.siteCode})
                        </option>
                      ))}
                    </select>
                    {errors.siteId && <small>{errors.siteId}</small>}
                  </div>
                  {panel.row && (
                    <p className="muted">
                      사업장을 바꾸려면 새 공간을 등록하세요.
                    </p>
                  )}
                  <Field
                    label="공간 코드"
                    value={pDraft.locationCode}
                    required
                    maxLength={30}
                    pattern="[A-Z][A-Z0-9_\-]{1,29}"
                    title="영문 대문자로 시작하는 2~30자 (대문자·숫자·_·-)"
                    error={errors.locationCode}
                    onChange={(e) =>
                      setPlaceDraft({
                        ...pDraft,
                        locationCode: e.target.value.toUpperCase(),
                      })
                    }
                  />
                  <Field
                    label="공간명"
                    value={pDraft.name}
                    required
                    maxLength={100}
                    error={errors.name}
                    onChange={(e) =>
                      setPlaceDraft({ ...pDraft, name: e.target.value })
                    }
                  />
                  <div className="field">
                    <label htmlFor="place-kind">종류</label>
                    <select
                      id="place-kind"
                      value={pDraft.kind}
                      onChange={(e) =>
                        setPlaceDraft({
                          ...pDraft,
                          kind: e.target.value as Place["kind"],
                        })
                      }
                    >
                      {Object.entries(KINDS).map(([k, v]) => (
                        <option key={k} value={k}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="place-parent">상위 공간</label>
                    <select
                      id="place-parent"
                      value={pDraft.parentLocationId ?? ""}
                      onChange={(e) =>
                        setPlaceDraft({
                          ...pDraft,
                          parentLocationId: e.target.value
                            ? Number(e.target.value)
                            : null,
                        })
                      }
                    >
                      <option value="">없음</option>
                      {parentChoices.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.locationCode} {p.name}
                        </option>
                      ))}
                    </select>
                    {errors.parentLocationId && (
                      <small>{errors.parentLocationId}</small>
                    )}
                  </div>
                </>
              )}
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
