// M-10 사업장·공간 — MES 전용 사업장과 그 안의 공간 (FS-020a)
import { useState, type FormEvent } from "react";
import {
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
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
  const [editingSite, setEditingSite] = useState<Site | null>(null);
  const [siteDraft, setSiteDraft] = useState<SiteDraft>();
  const [editingPlace, setEditingPlace] = useState<Place | null>(null);
  const [placeDraft, setPlaceDraft] = useState<PlaceDraft>();

  if (moduleOff(error)) return <ModuleOff />;
  const [sites, places] = data ?? [undefined, []];
  const sDraft = siteDraft ?? {
    siteCode: "",
    name: "",
    timezone: "Asia/Seoul",
  };
  const pDraft: PlaceDraft = placeDraft ?? {
    siteId: sites?.[0]?.id ?? 0,
    parentLocationId: null,
    locationCode: "",
    name: "",
    kind: "workcenter",
  };
  const errors = fieldErrors(saveError);

  function editSite(row: Site | null) {
    setEditingSite(row);
    setSiteDraft(
      row
        ? { siteCode: row.siteCode, name: row.name, timezone: row.timezone }
        : undefined,
    );
    setError(undefined);
  }
  function editPlace(row: Place | null) {
    setEditingPlace(row);
    setPlaceDraft(row ? { ...row } : undefined);
    setError(undefined);
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
    if (editingSite && !Object.keys(body).length) return;
    const ok = await send(
      editingSite ? `/sites/${editingSite.id}` : "/sites",
      editingSite ? "PATCH" : "POST",
      body,
    );
    if (ok) editSite(null);
  }

  async function submitPlace(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const draft = {
      siteId: pDraft.siteId,
      parentLocationId: pDraft.parentLocationId,
      locationCode: pDraft.locationCode.trim().toUpperCase(),
      name: pDraft.name.trim(),
      kind: pDraft.kind,
    };
    // 수정 중에는 사업장이 잠겨 있어 바뀐 값에 들어가지 않는다.
    const body = editingPlace ? changed(draft, editingPlace) : draft;
    if (editingPlace && !Object.keys(body).length) return;
    const ok = await send(
      editingPlace ? `/locations/${editingPlace.id}` : "/locations",
      editingPlace ? "PATCH" : "POST",
      body,
    );
    if (ok) editPlace(null);
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
            onClick={() => editSite(r)}
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
            onClick={() => editPlace(r)}
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
    <>
      <PageTitle
        id="M-10"
        title="사업장·공간"
        subtitle="생산 거점과 그 안의 건물·구역·작업장을 관리합니다"
        help="mes/m-10"
      />
      <MesOrder />
      <p className="muted">
        MES 전용 기준정보입니다. FEMS의 사업장·공간과 코드가 같아도 별개
        데이터입니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!sites ? (
        !error && <Loading />
      ) : (
        <>
          <div className="master-grid">
            <section>
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
                    reason="등록된 사업장이 없습니다. 우측 폼에서 첫 사업장을 등록하세요."
                    to="#site-form"
                    action="사업장 등록"
                  />
                }
              />
            </section>
            <form
              id="site-form"
              className="panel"
              aria-label={editingSite ? "사업장 수정" : "사업장 등록"}
              onSubmit={(e) => void submitSite(e)}
            >
              <h2>
                {editingSite ? `${editingSite.siteCode} 수정` : "사업장 등록"}
              </h2>
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
              <div className="form-actions">
                <button type="submit" disabled={pending}>
                  {editingSite ? "저장" : "등록"}
                </button>
                {editingSite && (
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => editSite(null)}
                  >
                    취소
                  </button>
                )}
              </div>
            </form>
          </div>

          {sites.length === 0 ? (
            <p className="muted">공간은 사업장을 먼저 등록한 뒤 추가합니다.</p>
          ) : (
            <div className="master-grid">
              <section>
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
                      reason="등록된 공간이 없습니다. 설비는 공간에 놓입니다."
                      to="#place-form"
                      action="공간 등록"
                    />
                  }
                />
              </section>
              <form
                id="place-form"
                className="panel"
                aria-label={editingPlace ? "공간 수정" : "공간 등록"}
                onSubmit={(e) => void submitPlace(e)}
              >
                <h2>
                  {editingPlace
                    ? `${editingPlace.locationCode} 수정`
                    : "공간 등록"}
                </h2>
                <div className="field">
                  <label htmlFor="place-site">사업장</label>
                  <select
                    id="place-site"
                    value={pDraft.siteId}
                    disabled={!!editingPlace}
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
                    {places
                      .filter(
                        (p) =>
                          p.siteId === pDraft.siteId &&
                          p.id !== editingPlace?.id,
                      )
                      .map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.locationCode} {p.name}
                        </option>
                      ))}
                  </select>
                  {errors.parentLocationId && (
                    <small>{errors.parentLocationId}</small>
                  )}
                </div>
                <div className="form-actions">
                  <button type="submit" disabled={pending}>
                    {editingPlace ? "저장" : "등록"}
                  </button>
                  {editingPlace && (
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => editPlace(null)}
                    >
                      취소
                    </button>
                  )}
                </div>
              </form>
            </div>
          )}
        </>
      )}
    </>
  );
}
