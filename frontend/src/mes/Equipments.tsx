// M-11 설비 — MES 전용 설비 목록 + 등록/수정 패널 (FS-020a)
import { useState, type FormEvent } from "react";
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
import {
  changed,
  fieldErrors,
  MesOrder,
  ModuleOff,
  moduleOff,
  useLists,
  useSend,
  type Equipment,
  type Place,
} from "./common";

type Draft = Omit<Equipment, "id">;

export function Equipments() {
  const { data, error, reload } = useLists<[Equipment[], Place[]]>([
    "/equipments",
    "/locations",
  ]);
  const {
    send,
    pending,
    error: saveError,
    setError,
    deleteButtons,
  } = useSend(reload);
  const [editing, setEditing] = useState<Equipment | null>(null);
  const [draft, setDraft] = useState<Draft>();

  if (moduleOff(error)) return <ModuleOff />;
  const [rows, places] = data ?? [undefined, []];
  const d: Draft = draft ?? {
    locationId: places[0]?.id ?? 0,
    equipmentCode: "",
    name: "",
    equipmentType: "",
    isActive: true,
  };
  const errors = fieldErrors(saveError);

  function edit(row: Equipment | null) {
    setEditing(row);
    setDraft(row ? { ...row } : undefined);
    setError(undefined);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const clean = {
      locationId: d.locationId,
      equipmentCode: d.equipmentCode.trim().toUpperCase(),
      name: d.name.trim(),
      equipmentType: d.equipmentType.trim(),
      isActive: d.isActive,
    };
    const body = editing ? changed(clean, editing) : clean;
    if (editing && !Object.keys(body).length) return;
    const ok = await send(
      editing ? `/equipments/${editing.id}` : "/equipments",
      editing ? "PATCH" : "POST",
      body,
    );
    if (ok) edit(null);
  }

  const placeName = (id: number) => places.find((p) => p.id === id)?.name ?? id;
  const columns: Column<Equipment>[] = [
    { key: "equipmentCode", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button type="button" className="link-button" onClick={() => edit(r)}>
            수정
          </button>
          {deleteButtons(`eq:${r.id}`, `/equipments/${r.id}`)}
        </span>
      ),
    },
    { key: "name", label: "설비명" },
    { key: "equipmentType", label: "유형" },
    {
      key: "locationId",
      label: "공간",
      render: (r) => placeName(r.locationId),
    },
    {
      key: "isActive",
      label: "사용",
      render: (r) =>
        r.isActive ? "사용" : <Badge tone="warning">사용 안 함</Badge>,
    },
  ];

  return (
    <>
      <PageTitle
        id="M-11"
        title="설비"
        subtitle="공정을 수행하는 설비를 관리합니다"
        help="mes/m-11"
      />
      <MesOrder />
      <p className="muted">
        MES 전용 설비입니다. FEMS 설비와 코드가 같아도 별개 데이터입니다. 사용
        안 함인 설비에는 공정 실행을 배정하지 않습니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!rows ? (
        !error && <Loading />
      ) : places.length === 0 ? (
        <EmptyState
          reason="등록된 공간이 없습니다. 설비는 공간에 놓입니다."
          to="/mes/sites"
          action="사업장·공간 화면으로"
        />
      ) : (
        <div className="master-grid">
          <section>
            <DataTable
              rows={rows}
              columns={columns}
              caption="설비 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="등록된 설비가 없습니다. 우측 폼에서 첫 설비를 등록하세요."
                  to="#equipment-form"
                  action="설비 등록"
                />
              }
            />
          </section>
          <form
            id="equipment-form"
            className="panel"
            aria-label={editing ? "설비 수정" : "설비 등록"}
            onSubmit={(e) => void submit(e)}
          >
            <h2>{editing ? `${editing.equipmentCode} 수정` : "설비 등록"}</h2>
            <Field
              label="설비 코드"
              value={d.equipmentCode}
              required
              maxLength={30}
              pattern="[A-Z][A-Z0-9_\-]{1,29}"
              title="영문 대문자로 시작하는 2~30자 (대문자·숫자·_·-)"
              error={errors.equipmentCode}
              onChange={(e) =>
                setDraft({ ...d, equipmentCode: e.target.value.toUpperCase() })
              }
            />
            <Field
              label="설비명"
              value={d.name}
              required
              maxLength={100}
              error={errors.name}
              onChange={(e) => setDraft({ ...d, name: e.target.value })}
            />
            <Field
              label="설비 유형"
              value={d.equipmentType}
              required
              maxLength={40}
              placeholder="예: INJ"
              error={errors.equipmentType}
              onChange={(e) =>
                setDraft({ ...d, equipmentType: e.target.value })
              }
            />
            <div className="field">
              <label htmlFor="equipment-location">공간</label>
              <select
                id="equipment-location"
                value={d.locationId}
                onChange={(e) =>
                  setDraft({ ...d, locationId: Number(e.target.value) })
                }
              >
                {places.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.locationCode})
                  </option>
                ))}
              </select>
              {errors.locationId && <small>{errors.locationId}</small>}
            </div>
            <label className="inline-check">
              <input
                type="checkbox"
                checked={d.isActive}
                onChange={(e) => setDraft({ ...d, isActive: e.target.checked })}
              />
              사용
            </label>
            <div className="form-actions">
              <button type="submit" disabled={pending}>
                {editing ? "저장" : "등록"}
              </button>
              {editing && (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => edit(null)}
                >
                  취소
                </button>
              )}
            </div>
          </form>
        </div>
      )}
    </>
  );
}
