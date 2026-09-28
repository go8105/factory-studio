// B-06 경보 — [경보] 목록 + 상세(확인 TX-B3) · [규칙] 목록 + 폼 (UI-02 L·S 패턴).
// 해제는 관측으로만 일어난다(1시간 진행). 확인은 사람이 보았다는 기록이다.
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  DataTable,
  DetailPanel,
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
  LineChart,
  METRIC_LABEL,
  ModuleOff,
  moduleOff,
  num,
  ruleText,
  SEVERITY_LABEL,
  STATUS_LABEL,
  time,
  UNIT,
  useGet,
  useLists,
  useSend,
  type Alarm,
  type Metric,
  type Rule,
  type Zone,
} from "./common";

type Tab = "alarms" | "rules";
type Draft = {
  zoneId: number;
  metric: Metric;
  comparator: "HIGH" | "LOW";
  threshold: string;
  durationHours: string;
  severity: "WARNING" | "CRITICAL";
  isActive: boolean;
};
type Reading = {
  periodStart: string;
  metric: Metric;
  value: string;
  source: string;
};

function AlarmTrend({ alarm }: { alarm: Alarm }) {
  const from = alarm.raisedAt.slice(0, 10);
  const { data } = useGet<{ readings: Reading[] }>(
    `/environment?zoneId=${alarm.zoneId}&from=${from}`,
  );
  if (!data) return <Loading />;
  const since = Date.parse(alarm.raisedAt) - alarm.durationHours * 3_600_000;
  return (
    <LineChart
      caption={`${METRIC_LABEL[alarm.metric]} 발생 전후`}
      unit={UNIT[alarm.metric]}
      series={{
        label: METRIC_LABEL[alarm.metric],
        points: data.readings
          .filter(
            (r) =>
              r.metric === alarm.metric && Date.parse(r.periodStart) >= since,
          )
          .map((r) => ({
            at: r.periodStart,
            value: Number(r.value),
            simulated: r.source === "SIMULATION",
          })),
      }}
      references={[{ label: "한계값", value: Number(alarm.threshold) }]}
    />
  );
}

const severity = (s: Alarm["severity"]) => (
  <Badge tone={s === "CRITICAL" ? "issue" : "warning"}>
    {SEVERITY_LABEL[s]}
  </Badge>
);

export function Alarms() {
  const [tab, setTab] = useState<Tab>("alarms");
  const [status, setStatus] = useState<string>("raised");
  const alarms = useGet<Alarm[]>(`/alarms${status ? `?status=${status}` : ""}`);
  const lists = useLists<[Rule[], Zone[]]>(["/alarm-rules", "/zones"]);
  const [openAlarm, setOpenAlarm] = useState<Alarm | null>(null);
  const [note, setNote] = useState("");
  const [rule, setRule] = useState<Rule | "new" | null>(null);
  const [draft, setDraft] = useState<Draft>();
  const [initial, setInitial] = useState<Draft>();
  const refresh = () => {
    alarms.reload();
    lists.reload();
  };
  const { send, pending, error: saveError, setError } = useSend(refresh);
  const guard = useDiscardGuard(
    (!!rule && JSON.stringify(draft) !== JSON.stringify(initial)) ||
      (!!openAlarm && !!note),
  );
  if (moduleOff(alarms.error) || moduleOff(lists.error)) return <ModuleOff />;
  const [rules, zones] = lists.data ?? [[], []];
  const zoneName = (id: number) => zones.find((z) => z.id === id)?.name ?? "—";
  const errors = fieldErrors(saveError);

  async function acknowledge() {
    if (!openAlarm) return;
    const r = await send<Alarm>(`/alarms/${openAlarm.id}/acknowledge`, "POST", {
      note: note || undefined,
    });
    if (r) {
      setOpenAlarm(r);
      setNote("");
    }
  }
  function openRule(r: Rule | "new") {
    const values: Draft =
      r === "new"
        ? {
            zoneId: zones[0]?.id ?? 0,
            metric: "CO2",
            comparator: "HIGH",
            threshold: "",
            durationHours: "2",
            severity: "WARNING",
            isActive: true,
          }
        : { ...r, durationHours: String(r.durationHours) };
    guard.guard(() => {
      setRule(r);
      setDraft(values);
      setInitial(values);
      setError(undefined);
    });
  }
  async function submitRule(event: FormEvent) {
    event.preventDefault();
    if (!draft || !rule) return;
    const common = {
      threshold: draft.threshold,
      durationHours: Number(draft.durationHours),
      severity: draft.severity,
    };
    const saved =
      rule === "new"
        ? await send("/alarm-rules", "POST", {
            ...common,
            zoneId: draft.zoneId,
            metric: draft.metric,
            comparator: draft.comparator,
          })
        : await send(`/alarm-rules/${rule.id}`, "PATCH", {
            ...common,
            isActive: draft.isActive,
          });
    if (saved) setRule(null);
  }

  const alarmColumns: Column<Alarm>[] = [
    { key: "raisedAt", label: "발생 시각", render: (a) => time(a.raisedAt) },
    {
      key: "id",
      label: "관리",
      render: (a) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={openAlarm?.id === a.id}
          onClick={() =>
            guard.guard(() => {
              setOpenAlarm(a);
              setNote("");
              setError(undefined);
            })
          }
        >
          {a.status === "raised" ? "상세 · 확인" : "상세"}
        </button>
      ),
    },
    { key: "zoneName", label: "구역" },
    { key: "metric", label: "항목", render: (a) => METRIC_LABEL[a.metric] },
    { key: "threshold", label: "규칙", render: (a) => ruleText(a) },
    {
      key: "peakValue",
      label: "최고값",
      render: (a) => `${num(a.peakValue)} ${UNIT[a.metric]}`,
    },
    { key: "severity", label: "등급", render: (a) => severity(a.severity) },
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
  ];
  const ruleColumns: Column<Rule>[] = [
    { key: "zoneId", label: "구역", render: (r) => zoneName(r.zoneId) },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          onClick={() => openRule(r)}
        >
          수정
        </button>
      ),
    },
    { key: "metric", label: "항목", render: (r) => METRIC_LABEL[r.metric] },
    { key: "threshold", label: "조건", render: (r) => ruleText(r) },
    { key: "severity", label: "등급", render: (r) => severity(r.severity) },
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
  const alarmRows = alarms.data;

  return (
    <div className="page-fill">
      <PageTitle
        id="B-06"
        title="경보"
        subtitle="환경 관측이 규칙을 지속 시간 동안 넘으면 발생하고, 돌아오면 해제됩니다"
        help="bems/b-06"
        actions={
          tab === "rules" && (
            <button
              type="button"
              aria-pressed={rule === "new"}
              onClick={() => openRule("new")}
            >
              규칙 등록
            </button>
          )
        }
      />
      <div className="tabs" role="tablist">
        {(
          [
            ["alarms", "경보"],
            ["rules", "규칙"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            aria-pressed={tab === k}
            className={tab === k ? "active" : ""}
            onClick={() =>
              guard.guard(() => {
                setTab(k);
                setOpenAlarm(null);
                setRule(null);
              })
            }
          >
            {label}
          </button>
        ))}
      </div>
      <ErrorNotice error={alarms.error ?? lists.error} retry={refresh} />
      {tab === "alarms" ? (
        <>
          <div className="filter-bar">
            <label>
              상태
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                <option value="raised">확인 대기</option>
                <option value="acknowledged">확인됨</option>
                <option value="cleared">해제됨</option>
                <option value="">전체</option>
              </select>
            </label>
          </div>
          {!alarmRows ? (
            !alarms.error && <Loading />
          ) : (
            <div className="split-view fill">
              <section className="fill">
                <DataTable
                  rows={alarmRows}
                  columns={alarmColumns}
                  caption="경보 목록"
                  offset={0}
                  total={alarmRows.length}
                  limit={alarmRows.length || 1}
                  onPage={() => undefined}
                  empty={
                    <EmptyState
                      reason="조건에 맞는 경보가 없습니다."
                      to="/bems/hvac"
                      action="공조 운전으로"
                    />
                  }
                />
              </section>
              {openAlarm && (
                <DetailPanel
                  wide
                  title={`${openAlarm.zoneName} ${METRIC_LABEL[openAlarm.metric]} 경보`}
                  guard={guard}
                  onClose={() => setOpenAlarm(null)}
                  actions={
                    openAlarm.status === "raised" && (
                      <button
                        type="button"
                        disabled={pending}
                        aria-busy={pending}
                        onClick={() => void acknowledge()}
                      >
                        확인
                      </button>
                    )
                  }
                >
                  <p>
                    규칙 {ruleText(openAlarm)} · {severity(openAlarm.severity)}{" "}
                    · {STATUS_LABEL[openAlarm.status]}
                  </p>
                  <p className="muted">
                    발생 {time(openAlarm.raisedAt)} · 최고{" "}
                    {num(openAlarm.peakValue)} {UNIT[openAlarm.metric]}
                    {openAlarm.acknowledgedAt &&
                      ` · 확인 ${time(openAlarm.acknowledgedAt)}${openAlarm.ackNote ? ` (${openAlarm.ackNote})` : ""}`}
                    {openAlarm.clearedAt &&
                      ` · 해제 ${time(openAlarm.clearedAt)}`}
                  </p>
                  <AlarmTrend alarm={openAlarm} />
                  {openAlarm.status === "raised" && (
                    <Field
                      label="확인 메모(선택)"
                      value={note}
                      maxLength={300}
                      onChange={(e) => setNote(e.target.value)}
                    />
                  )}
                  <ErrorNotice error={saveError} />
                  {openAlarm.status !== "cleared" && (
                    <p className="muted" role="note">
                      해제는 관측으로만 일어납니다. 환기·설정값을 바꾼 뒤 1시간
                      진행으로 해제를 확인하세요.{" "}
                      <Link to="/bems/hvac">공조 운전 →</Link>
                    </p>
                  )}
                </DetailPanel>
              )}
            </div>
          )}
        </>
      ) : !lists.data ? (
        !lists.error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={rules}
              columns={ruleColumns}
              caption="경보 규칙"
              offset={0}
              total={rules.length}
              limit={rules.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="경보 규칙이 없습니다."
                  action="규칙 등록"
                  onAction={() => openRule("new")}
                />
              }
            />
          </section>
          {rule && draft && (
            <FormPanel
              key={rule === "new" ? "new" : rule.id}
              title={rule === "new" ? "경보 규칙 등록" : "경보 규칙 수정"}
              guard={guard}
              onClose={() => setRule(null)}
              onSubmit={(e) => void submitRule(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    {rule === "new" ? "등록" : "저장"}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => setRule(null))}
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
                <label htmlFor="rule-zone">구역</label>
                <select
                  id="rule-zone"
                  value={draft.zoneId}
                  disabled={rule !== "new"}
                  onChange={(e) =>
                    setDraft({ ...draft, zoneId: Number(e.target.value) })
                  }
                >
                  {zones.map((z) => (
                    <option key={z.id} value={z.id}>
                      {z.name}
                    </option>
                  ))}
                </select>
                {errors.zoneId && <small>{errors.zoneId}</small>}
              </div>
              <div className="field">
                <label htmlFor="rule-metric">항목</label>
                <select
                  id="rule-metric"
                  value={draft.metric}
                  disabled={rule !== "new"}
                  onChange={(e) =>
                    setDraft({ ...draft, metric: e.target.value as Metric })
                  }
                >
                  {(Object.keys(METRIC_LABEL) as Metric[]).map((m) => (
                    <option key={m} value={m}>
                      {METRIC_LABEL[m]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="rule-comparator">비교</label>
                <select
                  id="rule-comparator"
                  value={draft.comparator}
                  disabled={rule !== "new"}
                  aria-invalid={!!errors.comparator}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      comparator: e.target.value as Draft["comparator"],
                    })
                  }
                >
                  <option value="HIGH">초과(&gt;)</option>
                  <option value="LOW">미만(&lt;)</option>
                </select>
                {errors.comparator && <small>{errors.comparator}</small>}
              </div>
              <Field
                label={`한계값 (${UNIT[draft.metric]})`}
                value={draft.threshold}
                required
                inputMode="decimal"
                pattern="-?\d{1,6}(\.\d{1,2})?"
                error={errors.threshold}
                onChange={(e) =>
                  setDraft({ ...draft, threshold: e.target.value })
                }
              />
              <Field
                label="지속 시간(시간, 1~24)"
                type="number"
                min={1}
                max={24}
                value={draft.durationHours}
                required
                error={errors.durationHours}
                onChange={(e) =>
                  setDraft({ ...draft, durationHours: e.target.value })
                }
              />
              <div className="field">
                <label htmlFor="rule-severity">등급</label>
                <select
                  id="rule-severity"
                  value={draft.severity}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      severity: e.target.value as Draft["severity"],
                    })
                  }
                >
                  <option value="WARNING">경고</option>
                  <option value="CRITICAL">위험</option>
                </select>
              </div>
              {rule !== "new" && (
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
