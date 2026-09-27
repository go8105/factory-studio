// Q-06 불량 유형 — 목록 + 등록·수정 패널(UI-02 S 패턴). 쓰인 유형은 지우지 않고 사용 안 함으로 바꾼다.
import { useState, type FormEvent } from "react";
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
import {
  fieldErrors,
  ModuleOff,
  moduleOff,
  useLists,
  useSend,
  type DefectType,
} from "./common";

type Draft = { code: string; name: string; isActive: boolean };
const EMPTY: Draft = { code: "", name: "", isActive: true };

export function DefectTypes() {
  const { data, error, reload } = useLists<[DefectType[]]>(["/defect-types"]);
  const { send, pending, error: saveError, deleteButtons } = useSend(reload);
  const [panel, setPanel] = useState<{ row: DefectType | null } | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [initial, setInitial] = useState<Draft>(EMPTY);
  const guard = useDiscardGuard(
    !!panel && JSON.stringify(draft) !== JSON.stringify(initial),
  );
  if (moduleOff(error)) return <ModuleOff />;
  const rows = data?.[0];
  const editing = panel?.row ?? null;
  const errors = fieldErrors(saveError);

  function open(row: DefectType | null) {
    const values = row
      ? { code: row.code, name: row.name, isActive: row.isActive }
      : EMPTY;
    setPanel({ row });
    setDraft(values);
    setInitial(values);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    const saved = editing
      ? await send(`/defect-types/${editing.id}`, "PATCH", {
          name: draft.name,
          isActive: draft.isActive,
        })
      : await send("/defect-types", "POST", {
          ...draft,
          code: draft.code.trim().toUpperCase(),
        });
    if (saved) setPanel(null);
  }

  const columns: Column<DefectType>[] = [
    { key: "code", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={editing?.id === r.id}
            onClick={() => guard.guard(() => open(r))}
          >
            수정
          </button>
          {deleteButtons(`d:${r.id}`, `/defect-types/${r.id}`)}
        </span>
      ),
    },
    { key: "name", label: "이름" },
    {
      key: "isActive",
      label: "사용",
      render: (r) =>
        r.isActive ? (
          <Badge>사용</Badge>
        ) : (
          <Badge tone="warning">사용 안 함</Badge>
        ),
    },
    { key: "usedCount", label: "쓰인 측정값" },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="Q-06"
        title="불량 유형"
        subtitle="불합격 항목에 붙이는 불량 유형입니다. 대시보드 사유 집계에 쓰입니다"
        help="qms/q-06"
        actions={
          <button
            type="button"
            aria-pressed={!!panel && !editing}
            onClick={() => guard.guard(() => open(null))}
          >
            불량 유형 등록
          </button>
        }
      />
      <p className="muted" role="note">
        코드는 MES 불량 사유 코드와 같게 쓰면 대조하기 쉽습니다. 코드가 같을 뿐
        두 시스템의 데이터는 연결되지 않습니다.
      </p>
      {!panel && (
        <ErrorNotice
          error={Object.keys(errors).length ? undefined : saveError}
        />
      )}
      <ErrorNotice error={error} retry={reload} />
      {!rows ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={rows}
              columns={columns}
              caption="불량 유형 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="등록된 불량 유형이 없습니다. 불합격 항목에 붙일 유형을 먼저 등록하세요."
                  action="불량 유형 등록"
                  onAction={() => guard.guard(() => open(null))}
                />
              }
            />
          </section>
          {panel && (
            <FormPanel
              key={editing?.id ?? "new"}
              title={editing ? `${editing.code} 수정` : "불량 유형 등록"}
              guard={guard}
              onClose={() => setPanel(null)}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    {editing ? "저장" : "등록"}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => setPanel(null))}
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
                label="코드"
                value={draft.code}
                required
                disabled={!!editing}
                maxLength={30}
                pattern="[A-Z][A-Z0-9_]{1,29}"
                title="영문 대문자로 시작하는 2~30자 (대문자·숫자·_)"
                error={errors.code}
                onChange={(e) =>
                  setDraft({ ...draft, code: e.target.value.toUpperCase() })
                }
              />
              <Field
                label="이름"
                value={draft.name}
                required
                maxLength={100}
                error={errors.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
              <label className="inline-check">
                <input
                  type="checkbox"
                  checked={draft.isActive}
                  onChange={(e) =>
                    setDraft({ ...draft, isActive: e.target.checked })
                  }
                />
                사용
              </label>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
