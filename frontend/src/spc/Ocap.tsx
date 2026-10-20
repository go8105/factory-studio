// S-09 이상 대응 절차(OCAP) — 이상이 났을 때 무엇부터 볼지 미리 정해 두는 점검 항목 (UI-03 S 패턴).
// 적용 범위가 비면 '모든 것'이다: 특성이 비면 모든 특성, 규칙이 비면 모든 규칙에 붙는다.
// 기록이 생긴 항목은 적용 범위를 바꿀 수 없다 — 지난 점검이 무엇을 본 것인지 흐려지기 때문이다.
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
  CAUSE_LABEL,
  fieldErrors,
  label,
  ModuleOff,
  moduleOff,
  ocapScope,
  RULE_LABEL,
  useGet,
  useSend,
  type Cause,
  type Characteristic,
  type OcapItem,
  type RuleNo,
} from "./common";

type Draft = {
  characteristicId: string;
  ruleNo: string;
  seq: string;
  checkText: string;
  causeCategory: string;
  isActive: boolean;
};
const blank: Draft = {
  characteristicId: "",
  ruleNo: "",
  seq: "1",
  checkText: "",
  causeCategory: "",
  isActive: true,
};

export function Ocap() {
  const list = useGet<OcapItem[]>("/ocap-items");
  const chars = useGet<Characteristic[]>("/characteristics");
  const [edit, setEdit] = useState<OcapItem | "new" | null>(null);
  const [draft, setDraft] = useState<Draft>(blank);
  const [initial, setInitial] = useState<Draft>(blank);
  const { send, pending, error, setError } = useSend(() => list.reload());
  const guard = useDiscardGuard(
    !!edit && JSON.stringify(draft) !== JSON.stringify(initial),
  );
  if (moduleOff(list.error)) return <ModuleOff />;
  const errors = fieldErrors(error);
  const inUse = edit !== null && edit !== "new" && edit.checkCount > 0;

  function start(target: OcapItem | "new") {
    const values: Draft =
      target === "new"
        ? { ...blank, seq: String((list.data?.length ?? 0) + 1) }
        : {
            characteristicId: target.characteristicId
              ? String(target.characteristicId)
              : "",
            ruleNo: target.ruleNo ? String(target.ruleNo) : "",
            seq: String(target.seq),
            checkText: target.checkText,
            causeCategory: target.causeCategory ?? "",
            isActive: target.isActive,
          };
    guard.guard(() => {
      setEdit(target);
      setDraft(values);
      setInitial(values);
      setError(undefined);
    });
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!edit) return;
    const scope = {
      characteristicId: draft.characteristicId
        ? Number(draft.characteristicId)
        : null,
      ruleNo: draft.ruleNo ? Number(draft.ruleNo) : null,
    };
    const common = {
      seq: Number(draft.seq),
      checkText: draft.checkText,
      causeCategory: draft.causeCategory || null,
    };
    const saved =
      edit === "new"
        ? await send("/ocap-items", "POST", { ...scope, ...common })
        : await send(`/ocap-items/${edit.id}`, "PATCH", {
            ...common,
            isActive: draft.isActive,
            ...(inUse ? {} : scope),
          });
    if (saved) setEdit(null);
  }
  const columns: Column<OcapItem>[] = [
    { key: "seq", label: "순서" },
    {
      key: "id",
      label: "관리",
      render: (i) => (
        <button type="button" className="link-button" onClick={() => start(i)}>
          수정
        </button>
      ),
    },
    { key: "characteristicId", label: "적용 범위", render: ocapScope },
    { key: "checkText", label: "점검 내용" },
    {
      key: "causeCategory",
      label: "해당 원인",
      render: (i) =>
        i.causeCategory ? (
          CAUSE_LABEL[i.causeCategory]
        ) : (
          <span className="muted">—</span>
        ),
    },
    { key: "checkCount", label: "점검 기록" },
    {
      key: "isActive",
      label: "사용",
      render: (i) =>
        i.isActive ? (
          <Badge>사용</Badge>
        ) : (
          <Badge tone="warning">사용 안 함</Badge>
        ),
    },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="S-09"
        title="이상 대응 절차"
        subtitle="이상이 났을 때 순서대로 확인할 점검 항목을 미리 정해 둡니다"
        help="spc/s-09"
        actions={
          <button
            type="button"
            aria-pressed={edit === "new"}
            onClick={() => start("new")}
          >
            항목 등록
          </button>
        }
      />
      <ErrorNotice error={list.error} retry={() => list.reload()} />
      <p role="note" className="muted">
        이상이 생기면 그 특성·규칙에 해당하는 항목이 S-05 이상 상세에 점검표로
        뜨고, <strong>모두 기록해야 조치를 닫을 수 있습니다.</strong> 문제
        있음(NG)으로 적은 항목의 해당 원인은 조치 원인으로 제안됩니다.
      </p>
      {!list.data ? (
        !list.error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={list.data}
              columns={columns}
              caption="점검 항목"
              offset={0}
              total={list.data.length}
              limit={list.data.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="점검 항목이 없습니다. 없으면 점검 없이 바로 조치할 수 있습니다."
                  action="항목 등록"
                  onAction={() => start("new")}
                />
              }
            />
          </section>
          {edit && (
            <FormPanel
              key={edit === "new" ? "new" : edit.id}
              title={edit === "new" ? "점검 항목 등록" : "점검 항목 수정"}
              guard={guard}
              onClose={() => setEdit(null)}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    {edit === "new" ? "등록" : "저장"}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => setEdit(null))}
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : error}
              />
              {inUse && (
                <p role="note" className="muted">
                  점검 기록이 있어 적용 범위는 바꿀 수 없습니다. 바꾸려면 사용을
                  끄고 새 항목을 만드세요.
                </p>
              )}
              <div className="field">
                <label htmlFor="ocap-char">관리 특성</label>
                <select
                  id="ocap-char"
                  value={draft.characteristicId}
                  disabled={inUse}
                  onChange={(e) =>
                    setDraft({ ...draft, characteristicId: e.target.value })
                  }
                >
                  <option value="">모든 특성</option>
                  {chars.data?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {label(c)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="ocap-rule">판정 규칙</label>
                <select
                  id="ocap-rule"
                  value={draft.ruleNo}
                  disabled={inUse}
                  onChange={(e) =>
                    setDraft({ ...draft, ruleNo: e.target.value })
                  }
                >
                  <option value="">모든 규칙</option>
                  {(Object.keys(RULE_LABEL) as unknown as RuleNo[])
                    .map(Number)
                    .map((n) => (
                      <option key={n} value={n}>
                        {RULE_LABEL[n as RuleNo]}
                      </option>
                    ))}
                </select>
              </div>
              <Field
                label="순서"
                type="number"
                min={1}
                max={99}
                value={draft.seq}
                error={errors.seq}
                onChange={(e) => setDraft({ ...draft, seq: e.target.value })}
              />
              <Field
                label="점검 내용"
                value={draft.checkText}
                required
                minLength={2}
                maxLength={300}
                error={errors.checkText}
                onChange={(e) =>
                  setDraft({ ...draft, checkText: e.target.value })
                }
              />
              <div className="field">
                <label htmlFor="ocap-cause">해당 원인(선택)</label>
                <select
                  id="ocap-cause"
                  value={draft.causeCategory}
                  onChange={(e) =>
                    setDraft({ ...draft, causeCategory: e.target.value })
                  }
                >
                  <option value="">없음</option>
                  {(Object.keys(CAUSE_LABEL) as Cause[]).map((k) => (
                    <option key={k} value={k}>
                      {CAUSE_LABEL[k]}
                    </option>
                  ))}
                </select>
              </div>
              {edit !== "new" && (
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
              )}
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
