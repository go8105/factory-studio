// B-06 설비 경보 탭 — 공조기 이상(명령 연속 거부·연속 운전) 경보와 규칙 (DSN-16 F32).
// 발생·해제는 1시간 진행의 판정으로만 일어나고, 확인은 사람이 한다(환경 경보와 같은 수명).
// CMMS 전환 대기 신호는 환경 경보만 읽는다(DSN-21 Q4) — 설비 경보는 BEMS 안에서만 본다.
import { useState, type FormEvent } from "react";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import {
  CONDITION_LABEL,
  CONDITION_UNIT,
  fieldErrors,
  num,
  SEVERITY_LABEL,
  STATUS_LABEL,
  time,
  useGet,
  useLists,
  useSend,
  type EquipmentAlarm,
  type EquipmentRule,
  type HvacUnit,
} from "./common";

type Draft = {
  code: string;
  condition: EquipmentRule["condition"];
  hvacUnitId: string;
  threshold: string;
  severity: EquipmentRule["severity"];
  isActive: boolean;
};
const EMPTY: Draft = {
  code: "",
  condition: "LONG_RUN",
  hvacUnitId: "",
  threshold: "12",
  severity: "WARNING",
  isActive: true,
};
const severityBadge = (s: EquipmentRule["severity"]) => (
  <Badge tone={s === "CRITICAL" ? "issue" : "warning"}>
    {SEVERITY_LABEL[s]}
  </Badge>
);
const conditionText = (r: Pick<EquipmentRule, "condition" | "threshold">) =>
  `${CONDITION_LABEL[r.condition]} ${num(r.threshold, 0)}${CONDITION_UNIT[r.condition]} 이상`;

export function EquipmentAlarms({ view }: { view: "alarms" | "rules" }) {
  const [status, setStatus] = useState("raised");
  const alarms = useGet<EquipmentAlarm[]>(
    `/equipment-alarms${status ? `?status=${status}` : ""}`,
  );
  const lists = useLists<[EquipmentRule[], HvacUnit[]]>([
    "/equipment-alarm-rules",
    "/hvac-units",
  ]);
  const [editing, setEditing] = useState<EquipmentRule | "new" | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [initial, setInitial] = useState<Draft>(EMPTY);
  const [message, setMessage] = useState("");
  const refresh = () => {
    alarms.reload();
    lists.reload();
  };
  const { send, pending, error: saveError, setError } = useSend(refresh);
  const guard = useDiscardGuard(
    !!editing && JSON.stringify(draft) !== JSON.stringify(initial),
  );
  const [rules, units] = lists.data ?? [[], []];
  const errors = fieldErrors(saveError);
  const unitName = (id: number | null) =>
    id === null ? "모든 공조기" : (units.find((u) => u.id === id)?.code ?? "—");

  function open(rule: EquipmentRule | "new") {
    const values: Draft =
      rule === "new"
        ? EMPTY
        : {
            code: rule.code,
            condition: rule.condition,
            hvacUnitId: rule.hvacUnitId ? String(rule.hvacUnitId) : "",
            threshold: rule.threshold,
            severity: rule.severity,
            isActive: rule.isActive,
          };
    guard.guard(() => {
      setEditing(rule);
      setDraft(values);
      setInitial(values);
      setError(undefined);
    });
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const unit = draft.hvacUnitId ? Number(draft.hvacUnitId) : null;
    const saved =
      editing === "new"
        ? await send("/equipment-alarm-rules", "POST", {
            code: draft.code.trim().toUpperCase(),
            condition: draft.condition,
            hvacUnitId: unit,
            threshold: draft.threshold,
            severity: draft.severity,
          })
        : await send(`/equipment-alarm-rules/${editing.id}`, "PATCH", {
            hvacUnitId: unit,
            threshold: draft.threshold,
            severity: draft.severity,
            isActive: draft.isActive,
          });
    if (saved) setEditing(null);
  }
  async function acknowledge(alarm: EquipmentAlarm) {
    setMessage("");
    const r = await send<EquipmentAlarm>(
      `/equipment-alarms/${alarm.id}/acknowledge`,
      "POST",
    );
    if (r)
      setMessage(
        `${alarm.hvacCode} ${CONDITION_LABEL[alarm.condition]} 경보를 확인했습니다. 해제는 조건이 풀릴 때 1시간 진행이 합니다.`,
      );
  }

  const alarmColumns: Column<EquipmentAlarm>[] = [
    { key: "raisedAt", label: "발생 시각", render: (a) => time(a.raisedAt) },
    {
      key: "id",
      label: "관리",
      render: (a) =>
        a.status === "raised" ? (
          <button
            type="button"
            className="link-button"
            disabled={pending}
            onClick={() => void acknowledge(a)}
          >
            확인
          </button>
        ) : (
          "—"
        ),
    },
    { key: "hvacCode", label: "공조기" },
    { key: "hvacName", label: "이름" },
    { key: "condition", label: "조건", render: (a) => conditionText(a) },
    { key: "ruleCode", label: "규칙" },
    {
      key: "severity",
      label: "등급",
      render: (a) => severityBadge(a.severity),
    },
    {
      key: "status",
      label: "상태",
      render: (a) =>
        a.status === "raised" ? (
          <Badge tone="issue">{STATUS_LABEL[a.status]}</Badge>
        ) : (
          <Badge>{STATUS_LABEL[a.status]}</Badge>
        ),
    },
    {
      key: "clearedAt",
      label: "해제 시각",
      render: (a) => (a.clearedAt ? time(a.clearedAt) : "—"),
    },
  ];
  const ruleColumns: Column<EquipmentRule>[] = [
    { key: "code", label: "규칙" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={editing !== "new" && editing?.id === r.id}
          onClick={() => open(r)}
        >
          수정
        </button>
      ),
    },
    {
      key: "hvacUnitId",
      label: "대상",
      render: (r) => unitName(r.hvacUnitId),
    },
    { key: "condition", label: "조건", render: (r) => conditionText(r) },
    {
      key: "severity",
      label: "등급",
      render: (r) => severityBadge(r.severity),
    },
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
  ];

  if (view === "alarms")
    return (
      <>
        <div className="filter-bar">
          <label>
            상태
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="raised">확인 대기</option>
              <option value="acknowledged">확인됨</option>
              <option value="cleared">해제됨</option>
              <option value="">전체</option>
            </select>
          </label>
        </div>
        <p role="status">{message}</p>
        <ErrorNotice error={alarms.error ?? saveError} retry={refresh} />
        {!alarms.data ? (
          !alarms.error && <Loading />
        ) : (
          <DataTable
            rows={alarms.data}
            columns={alarmColumns}
            caption="설비 경보 목록"
            offset={0}
            total={alarms.data.length}
            limit={alarms.data.length || 1}
            onPage={() => undefined}
            empty={
              <EmptyState
                reason="조건에 맞는 설비 경보가 없습니다. 규칙을 두고 1시간 진행하면 판정합니다."
                to="/bems/hvac"
                action="공조 운전으로"
              />
            }
          />
        )}
      </>
    );

  return (
    <>
      <div className="filter-bar">
        <button
          type="button"
          aria-pressed={editing === "new"}
          onClick={() => open("new")}
        >
          설비 규칙 등록
        </button>
      </div>
      {!editing && <ErrorNotice error={saveError} />}
      <ErrorNotice error={lists.error} retry={refresh} />
      {!lists.data ? (
        !lists.error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={rules}
              columns={ruleColumns}
              caption="설비 경보 규칙"
              offset={0}
              total={rules.length}
              limit={rules.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="설비 경보 규칙이 없습니다."
                  action="설비 규칙 등록"
                  onAction={() => open("new")}
                />
              }
            />
          </section>
          {editing && (
            <FormPanel
              key={editing === "new" ? "new" : editing.id}
              title={
                editing === "new"
                  ? "설비 경보 규칙 등록"
                  : `${editing.code} 수정`
              }
              guard={guard}
              onClose={() => setEditing(null)}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    {editing === "new" ? "등록" : "저장"}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => setEditing(null))}
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
                label="규칙 코드"
                value={draft.code}
                required
                disabled={editing !== "new"}
                maxLength={20}
                pattern="[A-Z][A-Z0-9\-]{1,19}"
                title="영문 대문자로 시작하는 2~20자 (대문자·숫자·-)"
                error={errors.code}
                onChange={(e) =>
                  setDraft({ ...draft, code: e.target.value.toUpperCase() })
                }
              />
              <div className="field">
                <label htmlFor="bems-eq-condition">조건</label>
                <select
                  id="bems-eq-condition"
                  value={draft.condition}
                  disabled={editing !== "new"}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      condition: e.target.value as EquipmentRule["condition"],
                    })
                  }
                >
                  {(
                    Object.keys(CONDITION_LABEL) as EquipmentRule["condition"][]
                  ).map((c) => (
                    <option key={c} value={c}>
                      {CONDITION_LABEL[c]}
                    </option>
                  ))}
                </select>
                <small className="muted">
                  {draft.condition === "LONG_RUN"
                    ? "정지한 적이 없으면 얼마나 돌았는지 알 수 없어 경보하지 않습니다"
                    : "적용된 명령이 하나 끼면 연속이 끊깁니다"}
                </small>
              </div>
              <div className="field">
                <label htmlFor="bems-eq-unit">대상 공조기</label>
                <select
                  id="bems-eq-unit"
                  value={draft.hvacUnitId}
                  aria-invalid={!!errors.hvacUnitId}
                  onChange={(e) =>
                    setDraft({ ...draft, hvacUnitId: e.target.value })
                  }
                >
                  <option value="">모든 공조기</option>
                  {units.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.code} {u.name}
                    </option>
                  ))}
                </select>
                {errors.hvacUnitId && <small>{errors.hvacUnitId}</small>}
              </div>
              <Field
                label={`기준 (${CONDITION_UNIT[draft.condition]})`}
                value={draft.threshold}
                required
                inputMode="decimal"
                pattern="\d{1,8}(\.\d{1,2})?"
                error={errors.threshold}
                onChange={(e) =>
                  setDraft({ ...draft, threshold: e.target.value })
                }
              />
              <div className="field">
                <label htmlFor="bems-eq-severity">등급</label>
                <select
                  id="bems-eq-severity"
                  value={draft.severity}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      severity: e.target.value as EquipmentRule["severity"],
                    })
                  }
                >
                  {(
                    Object.keys(SEVERITY_LABEL) as EquipmentRule["severity"][]
                  ).map((s) => (
                    <option key={s} value={s}>
                      {SEVERITY_LABEL[s]}
                    </option>
                  ))}
                </select>
              </div>
              {editing !== "new" && (
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
    </>
  );
}
