// M-10 사업장·공간 — MES 전용 사업장과 그 안의 공간 (FS-020a)
import { useState, type FormEvent } from "react";
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
import {
  changed,
  fieldErrors,
  MesOrder,
  ModuleOff,
  moduleOff,
  useLists,
  useSend,
  type Place,
  type Site,
} from "./common";

const KINDS = { building: "건물", zone: "구역", workcenter: "작업장" };
type SiteDraft = { siteCode: string; name: string; timezone: string };
type PlaceDraft = Omit<Place, "id">;

type Panel =
  { type: "site"; row: Site | null } | { type: "place"; row: Place | null };

const EMPTY_SITE: SiteDraft = {
  siteCode: "",
  name: "",
  timezone: "Asia/Seoul",
};

const EMPTY_PLACE: PlaceDraft = {
  siteId: 0,
  parentLocationId: null,
  locationCode: "",
  name: "",
  kind: "workcenter",
};

export function Sites() {
  const { data, error, reload } = useLists<[Site[], Place[]]>([
    "/sites",
    "/locations",
  ]);
  const {
    send,
    pending,
    error: saveError,
    setError,
    deleteButtons,
  } = useSend(reload);

  const [panel, setPanel] = useState<Panel | null>(null);
  const [siteDraft, setSiteDraft] = useState<SiteDraft>(EMPTY_SITE);
  const [siteInitial, setSiteInitial] = useState<SiteDraft>(EMPTY_SITE);
  const [placeDraft, setPlaceDraft] = useState<PlaceDraft>(EMPTY_PLACE);
  const [placeInitial, setPlaceInitial] = useState<PlaceDraft>(EMPTY_PLACE);

  const siteDirty =
    panel?.type === "site" &&
    (Object.keys(siteDraft) as (keyof SiteDraft)[]).some(
      (k) => siteDraft[k] !== siteInitial[k],
    );
  const placeDirty =
    panel?.type === "place" &&
    (Object.keys(placeDraft) as (keyof PlaceDraft)[]).some(
      (k) => placeDraft[k] !== placeInitial[k],
    );
  const guard = useDiscardGuard(siteDirty || placeDirty);

  if (moduleOff(error)) return <ModuleOff />;
  const [sites, places] = data ?? [undefined, []];

  const errors = fieldErrors(saveError);

  function openSitePanel(row: Site | null) {
    const values: SiteDraft = row
      ? { siteCode: row.siteCode, name: row.name, timezone: row.timezone }
      : EMPTY_SITE;
    setPanel({ type: "site", row });
    setSiteDraft(values);
    setSiteInitial(values);
    setError(undefined);
  }

  function openPlacePanel(row: Place | null) {
    const values: PlaceDraft = row
      ? { ...row }
      : {
          siteId: sites?.[0]?.id ?? 0,
          parentLocationId: null,
          locationCode: "",
          name: "",
          kind: "workcenter",
        };
    setPanel({ type: "place", row });
    setPlaceDraft(values);
    setPlaceInitial(values);
    setError(undefined);
  }

  function closePanel() {
    setPanel(null);
    setError(undefined);
  }

  async function submitSite(event: FormEvent) {
    event.preventDefault();
    if (pending || panel?.type !== "site") return;
    const editing = panel.row;
    const draft = {
      siteCode: siteDraft.siteCode.trim().toUpperCase(),
      name: siteDraft.name.trim(),
      timezone: siteDraft.timezone.trim(),
    };
    const body = editing ? changed(draft, editing) : draft;
    if (editing && !Object.keys(body).length) return;
    const ok = await send(
      editing ? `/sites/${editing.id}` : "/sites",
      editing ? "PATCH" : "POST",
      body,
    );
    if (ok) closePanel();
  }

  async function submitPlace(event: FormEvent) {
    event.preventDefault();
    if (pending || panel?.type !== "place") return;
    const editing = panel.row;
    const draft = {
      siteId: placeDraft.siteId,
      parentLocationId: placeDraft.parentLocationId,
      locationCode: placeDraft.locationCode.trim().toUpperCase(),
      name: placeDraft.name.trim(),
      kind: placeDraft.kind,
    };
    const body = editing ? changed(draft, editing) : draft;
    if (editing && !Object.keys(body).length) return;
    const ok = await send(
      editing ? `/locations/${editing.id}` : "/locations",
      editing ? "PATCH" : "POST",
      body,
    );
    if (ok) closePanel();
  }

  const siteName = (id: number) => sites?.find((s) => s.id === id)?.name ?? id;
  const placeCode = (id: number | null) =>
    id === null ? "-" : (places.find((p) => p.id === id)?.locationCode ?? id);

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
            onClick={() => guard.guard(() => openSitePanel(r))}
          >
            수정
          </button>
          {deleteButtons(`site:${r.id}`, `/sites/${r.id}`)}
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
            onClick={() => guard.guard(() => openPlacePanel(r))}
          >
            수정
          </button>
          {deleteButtons(`place:${r.id}`, `/locations/${r.id}`)}
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

  return (
    <div className="page-fill">
      <PageTitle
        id="M-10"
        title="사업장·공간"
        subtitle="생산 거점과 그 안의 건물·구역·작업장을 관리합니다"
        help="mes/m-10"
      />
      <MesOrder />
      <p className="muted" role="note">
        MES 전용 기준정보입니다. FEMS의 사업장·공간과 코드가 같아도 별개
        데이터입니다.
      </p>
      {!panel && (
        <ErrorNotice
          error={Object.keys(errors).length ? undefined : saveError}
        />
      )}
      <ErrorNotice error={error} retry={reload} />
      {!sites ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="section-block">
              <div className="section-heading">
                <h2>사업장</h2>
                <button
                  type="button"
                  className="secondary"
                  aria-pressed={panel?.type === "site" && !panel.row}
                  onClick={() => guard.guard(() => openSitePanel(null))}
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
                    onAction={() => guard.guard(() => openSitePanel(null))}
                  />
                }
              />
            </div>
            <div className="section-block">
              <div className="section-heading">
                <h2>공간</h2>
                <button
                  type="button"
                  className="secondary"
                  disabled={sites.length === 0}
                  aria-pressed={panel?.type === "place" && !panel.row}
                  onClick={() => guard.guard(() => openPlacePanel(null))}
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
                    reason={
                      sites.length === 0
                        ? "사업장을 먼저 등록해야 공간을 등록할 수 있습니다."
                        : "등록된 공간이 없습니다. 첫 공간을 등록하세요."
                    }
                    action={sites.length === 0 ? "사업장 등록" : "공간 등록"}
                    onAction={() =>
                      guard.guard(() =>
                        sites.length === 0
                          ? openSitePanel(null)
                          : openPlacePanel(null),
                      )
                    }
                  />
                }
              />
            </div>
          </section>
          {panel?.type === "site" && (
            <FormPanel
              key={panel.row?.id ?? "new-site"}
              title={panel.row ? `${panel.row.siteCode} 수정` : "사업장 등록"}
              guard={guard}
              onClose={closePanel}
              onSubmit={(e) => void submitSite(e)}
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
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <Field
                label="사업장 코드"
                value={siteDraft.siteCode}
                required
                maxLength={30}
                pattern="[A-Z][A-Z0-9_\-]{1,29}"
                title="영문 대문자로 시작하는 2~30자 (대문자·숫자·_·-)"
                error={errors.siteCode}
                onChange={(e) =>
                  setSiteDraft({
                    ...siteDraft,
                    siteCode: e.target.value.toUpperCase(),
                  })
                }
              />
              <Field
                label="사업장명"
                value={siteDraft.name}
                required
                maxLength={100}
                error={errors.name}
                onChange={(e) =>
                  setSiteDraft({ ...siteDraft, name: e.target.value })
                }
              />
              <Field
                label="시간대"
                value={siteDraft.timezone}
                required
                maxLength={60}
                placeholder="Asia/Seoul"
                error={errors.timezone}
                onChange={(e) =>
                  setSiteDraft({ ...siteDraft, timezone: e.target.value })
                }
              />
            </FormPanel>
          )}
          {panel?.type === "place" && (
            <FormPanel
              key={panel.row?.id ?? "new-place"}
              title={panel.row ? `${panel.row.locationCode} 수정` : "공간 등록"}
              guard={guard}
              onClose={closePanel}
              onSubmit={(e) => void submitPlace(e)}
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
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <div className="field">
                <label htmlFor="place-site">사업장</label>
                <select
                  id="place-site"
                  value={placeDraft.siteId || sites[0]?.id || 0}
                  disabled={!!panel.row}
                  onChange={(e) =>
                    setPlaceDraft({
                      ...placeDraft,
                      siteId: Number(e.target.value),
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
                  공간의 소속 사업장은 수정할 수 없습니다.
                </p>
              )}
              <Field
                label="공간 코드"
                value={placeDraft.locationCode}
                required
                maxLength={30}
                pattern="[A-Z][A-Z0-9_\-]{1,29}"
                title="영문 대문자로 시작하는 2~30자 (대문자·숫자·_·-)"
                error={errors.locationCode}
                onChange={(e) =>
                  setPlaceDraft({
                    ...placeDraft,
                    locationCode: e.target.value.toUpperCase(),
                  })
                }
              />
              <Field
                label="공간명"
                value={placeDraft.name}
                required
                maxLength={100}
                error={errors.name}
                onChange={(e) =>
                  setPlaceDraft({ ...placeDraft, name: e.target.value })
                }
              />
              <div className="field">
                <label htmlFor="place-kind">종류</label>
                <select
                  id="place-kind"
                  value={placeDraft.kind}
                  onChange={(e) =>
                    setPlaceDraft({
                      ...placeDraft,
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
                <label htmlFor="place-parent">상위 공간 (선택)</label>
                <select
                  id="place-parent"
                  value={placeDraft.parentLocationId ?? ""}
                  onChange={(e) =>
                    setPlaceDraft({
                      ...placeDraft,
                      parentLocationId: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                >
                  <option value="">상위 공간 없음 (최상위)</option>
                  {places
                    .filter((p) => p.id !== panel.row?.id)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.locationCode})
                      </option>
                    ))}
                </select>
              </div>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
