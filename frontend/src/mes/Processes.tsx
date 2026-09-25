// M-13 공정 — 공정과 그 공정을 수행할 수 있는 설비(허용 설비) (FS-020a)
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
} from "./common";

export type Process = {
  id: number;
  processCode: string;
  name: string;
  processType: string;
  isActive: boolean;
  equipmentIds: number[];
};
type Draft = Omit<Process, "id">;

export function Processes() {
  const { data, error, reload } = useLists<[Process[], Equipment[]]>([
    "/processes",
    "/equipments",
  ]);
  const {
    send,
    pending,
    error: saveError,
    setError,
    deleteButtons,
  } = useSend(reload);
  const [editing, setEditing] = useState<Process | null>(null);
  const [draft, setDraft] = useState<Draft>();

  if (moduleOff(error)) return <ModuleOff />;
  const [rows, equipments] = data ?? [undefined, []];
  const d: Draft = draft ?? {
    processCode: "",
    name: "",
    processType: "",
    isActive: true,
    equipmentIds: [],
  };
  const errors = fieldErrors(saveError);

  function edit(row: Process | null) {
    setEditing(row);
    setDraft(row ? { ...row, equipmentIds: [...row.equipmentIds] } : undefined);
    setError(undefined);
  }

  function toggle(id: number, on: boolean) {
    const ids = on
      ? [...d.equipmentIds, id]
      : d.equipmentIds.filter((x) => x !== id);
    setDraft({ ...d, equipmentIds: ids.sort((a, b) => a - b) });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const clean = {
      processCode: d.processCode.trim().toUpperCase(),
      name: d.name.trim(),
      processType: d.processType.trim(),
      isActive: d.isActive,
      equipmentIds: d.equipmentIds,
    };
    const body = editing ? changed(clean, editing) : clean;
    if (editing && !Object.keys(body).length) return;
    const ok = await send(
      editing ? `/processes/${editing.id}` : "/processes",
      editing ? "PATCH" : "POST",
      body,
    );
    if (ok) edit(null);
  }

  const code = (id: number) =>
    equipments.find((e) => e.id === id)?.equipmentCode ?? String(id);
  const columns: Column<Process>[] = [
    { key: "processCode", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button type="button" className="link-button" onClick={() => edit(r)}>
            수정
          </button>
          {deleteButtons(`proc:${r.id}`, `/processes/${r.id}`)}
        </span>
      ),
    },
    { key: "name", label: "공정명" },
    { key: "processType", label: "유형" },
    {
      key: "equipmentIds",
      label: "허용 설비",
      render: (r) =>
        r.equipmentIds.length ? (
          r.equipmentIds.map(code).join(", ")
        ) : (
          <Badge tone="warning">없음</Badge>
        ),
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
        id="M-13"
        title="공정"
        subtitle="공정과 그 공정을 수행할 수 있는 설비를 관리합니다"
        help="mes/m-13"
      />
      <MesOrder />
      <p className="muted">
        공정 실행은 허용 설비에서만 시작할 수 있습니다. 허용 설비가 없는 공정은
        실행할 수 없습니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!rows ? (
        !error && <Loading />
      ) : (
        <div className="master-grid">
          <section>
            <DataTable
              rows={rows}
              columns={columns}
              caption="공정 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="등록된 공정이 없습니다. 우측 폼에서 첫 공정을 등록하세요."
                  to="#process-form"
                  action="공정 등록"
                />
              }
            />
          </section>
          <form
            id="process-form"
            className="panel"
            aria-label={editing ? "공정 수정" : "공정 등록"}
            onSubmit={(e) => void submit(e)}
          >
            <h2>{editing ? `${editing.processCode} 수정` : "공정 등록"}</h2>
            <Field
              label="공정 코드"
              value={d.processCode}
              required
              maxLength={30}
              pattern="[A-Z][A-Z0-9_\-]{1,29}"
              title="영문 대문자로 시작하는 2~30자 (대문자·숫자·_·-)"
              error={errors.processCode}
              onChange={(e) =>
                setDraft({ ...d, processCode: e.target.value.toUpperCase() })
              }
            />
            <Field
              label="공정명"
              value={d.name}
              required
              maxLength={100}
              error={errors.name}
              onChange={(e) => setDraft({ ...d, name: e.target.value })}
            />
            <Field
              label="공정 유형"
              value={d.processType}
              required
              maxLength={20}
              placeholder="예: INJ"
              error={errors.processType}
              onChange={(e) => setDraft({ ...d, processType: e.target.value })}
            />
            <fieldset className="field">
              <legend>허용 설비</legend>
              {equipments.length === 0 ? (
                <p className="muted">
                  등록된 설비가 없습니다. 설비 화면에서 먼저 등록하세요.
                </p>
              ) : (
                equipments.map((e) => (
                  <label key={e.id} className="inline-check">
                    <input
                      type="checkbox"
                      checked={d.equipmentIds.includes(e.id)}
                      onChange={(ev) => toggle(e.id, ev.target.checked)}
                    />
                    {e.equipmentCode} {e.name}
                    {!e.isActive && " (사용 안 함)"}
                  </label>
                ))
              )}
              {errors.equipmentIds && <small>{errors.equipmentIds}</small>}
            </fieldset>
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
