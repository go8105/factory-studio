// B-09 피크 감축 — FEMS 진행 피크 경보 → 감축안 제안 → 승인·실행 → 경보 해제 후 복귀
// (UI-03 L+DetailPanel wide 패턴). 자동 제어는 없다(DSN-16 Q2): 승인해야 제어 명령이 나간다.
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
  RevealAnchor,
  ScreenIntro,
  type Column,
} from "../shared/components";
import {
  actionText,
  ModuleOff,
  moduleOff,
  num,
  PLAN_STATUS,
  time,
  useGet,
  useSend,
  type DemandPlan,
  type PeakAlarm,
  type PlanStep,
} from "./common";

type Tab = "alarms" | "plans";
const OPEN_STATES: DemandPlan["status"][] = ["PROPOSED", "EXECUTED"];

const statusBadge = (s: DemandPlan["status"]) =>
  s === "PROPOSED" ? (
    <Badge tone="issue">{PLAN_STATUS[s]}</Badge>
  ) : s === "REJECTED" ? (
    <Badge tone="warning">{PLAN_STATUS[s]}</Badge>
  ) : (
    <Badge>{PLAN_STATUS[s]}</Badge>
  );

export function Peak() {
  const [tab, setTab] = useState<Tab>("alarms");
  const alarms = useGet<{ femsEnabled: boolean; rows: PeakAlarm[] }>(
    "/peak-alarms",
  );
  const plans = useGet<DemandPlan[]>("/demand-plans");
  const [openId, setOpenId] = useState<number | null>(null);
  const detail = useGet<DemandPlan>(openId ? `/demand-plans/${openId}` : null);
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const refresh = () => {
    alarms.reload();
    plans.reload();
    detail.reload();
  };
  const { send, pending, error: saveError, setError } = useSend(refresh);
  if (moduleOff(alarms.error) || moduleOff(plans.error)) return <ModuleOff />;
  const femsOff = alarms.data?.femsEnabled === false;

  async function propose(alarm: PeakAlarm) {
    setMessage("");
    const plan = await send<DemandPlan>("/demand-plans", "POST", {
      alarmRef: alarm.alarmRef,
    });
    if (plan) {
      setTab("plans");
      setOpenId(plan.id);
      setMessage(
        `${plan.planNo} 감축안을 만들었습니다. 승인해야 제어 명령이 나갑니다.`,
      );
    }
  }
  async function decide(path: string, done: string) {
    if (!openId) return;
    setMessage("");
    const plan = await send<DemandPlan>(
      `/demand-plans/${openId}/${path}`,
      "POST",
      { note: note || undefined },
    );
    if (plan) {
      setNote("");
      setMessage(done);
    }
  }

  const alarmColumns: Column<PeakAlarm & { id: string }>[] = [
    { key: "raisedAt", label: "발생 시각", render: (a) => time(a.raisedAt) },
    {
      key: "alarmRef",
      label: "관리",
      render: (a) =>
        a.planId ? (
          <button
            type="button"
            className="link-button"
            onClick={() => {
              setTab("plans");
              setOpenId(a.planId);
            }}
          >
            감축안 보기
          </button>
        ) : (
          <button
            type="button"
            disabled={pending || a.overKw === null}
            onClick={() => void propose(a)}
          >
            감축안 만들기
          </button>
        ),
    },
    { key: "ruleCode", label: "규칙" },
    { key: "ruleName", label: "이름" },
    {
      key: "peakValue",
      label: "측정 피크",
      render: (a) => `${num(a.peakValue)} kW`,
    },
    {
      key: "threshold",
      label: "한계",
      render: (a) => `계약전력의 ${num(Number(a.threshold) * 100, 0)}%`,
    },
    {
      key: "overKw",
      label: "줄일 양",
      render: (a) =>
        a.overKw === null ? (
          <Badge tone="warning">모름</Badge>
        ) : (
          `${num(a.overKw)} kW`
        ),
    },
  ];
  const planColumns: Column<DemandPlan>[] = [
    { key: "planNo", label: "감축안" },
    {
      key: "id",
      label: "관리",
      render: (p) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={openId === p.id}
          onClick={() => {
            setOpenId(p.id);
            setMessage("");
            setError(undefined);
          }}
        >
          상세
        </button>
      ),
    },
    {
      key: "proposedAt",
      label: "제안 시각",
      render: (p) => time(p.proposedAt),
    },
    { key: "femsAlarmRef", label: "FEMS 경보" },
    {
      key: "targetReductionKw",
      label: "목표 감축",
      render: (p) => `${num(p.targetReductionKw)} kW`,
    },
    {
      key: "expectedKw",
      label: "예상 감축",
      render: (p) => `${num(p.expectedKw)} kW`,
    },
    { key: "status", label: "상태", render: (p) => statusBadge(p.status) },
  ];
  const stepColumns: Column<PlanStep & { id: number }>[] = [
    { key: "seq", label: "순서" },
    { key: "hvacCode", label: "공조기" },
    { key: "curtailPriority", label: "감축 우선순위" },
    { key: "action", label: "동작", render: (s) => actionText(s) },
    {
      key: "expectedKw",
      label: "예상 감축",
      render: (s) => `${num(s.expectedKw)} kW`,
    },
    {
      key: "commandId",
      label: "실행 명령",
      render: (s) => (s.commandId ? "냈음" : "—"),
    },
    {
      key: "restoreCommandId",
      label: "복귀 명령",
      render: (s) => (s.restoreCommandId ? "냈음" : "—"),
    },
  ];

  const plan = detail.data?.id === openId ? detail.data : undefined;
  const alarmRows = (alarms.data?.rows ?? []).map((a) => ({
    ...a,
    id: a.alarmRef,
  }));

  return (
    <div className="page-fill">
      <PageTitle
        id="B-09"
        title="피크 감축"
        subtitle="FEMS 피크 경보에 맞춰 공조기 감축안을 만들고, 승인하면 제어 명령을 냅니다"
        help="bems/b-09"
      />
      <ScreenIntro>
        자동 제어는 하지 않습니다. 감축안은 <strong>제안</strong>일 뿐이고,
        담당자가 승인해야 제어 명령이 나갑니다. 감축은 수동 명령과 같은 규칙으로
        다음 <Link to="/bems/schedules">스케줄</Link> 경계까지 유지되고, FEMS
        경보가 해제된 뒤 복귀를 승인하면 스케줄 운전으로 돌아갑니다.
      </ScreenIntro>
      <div className="tabs" role="tablist">
        {(
          [
            ["alarms", "피크 경보"],
            ["plans", "감축안"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            aria-pressed={tab === k}
            className={tab === k ? "active" : ""}
            onClick={() => setTab(k)}
          >
            {label}
          </button>
        ))}
      </div>
      <p role="status">{message}</p>
      <ErrorNotice error={saveError} />
      <ErrorNotice error={alarms.error ?? plans.error} retry={refresh} />
      {femsOff ? (
        <EmptyState
          reason="FEMS를 사용하지 않도록 설정해 피크 경보를 읽을 수 없습니다. 감축안은 FEMS 경보에서 시작합니다."
          to="/workspace"
          action="내 공간으로"
        />
      ) : tab === "alarms" ? (
        !alarms.data ? (
          !alarms.error && <Loading />
        ) : (
          <DataTable
            rows={alarmRows}
            columns={alarmColumns}
            caption="진행 중인 피크 경보"
            offset={0}
            total={alarmRows.length}
            limit={alarmRows.length || 1}
            onPage={() => undefined}
            empty={
              <EmptyState
                reason="진행 중인 피크 경보가 없습니다. FEMS 에너지 경보에서 지금 점검을 누르면 판정합니다."
                to="/fems/alarms"
                action="FEMS 경보로"
              />
            }
          />
        )
      ) : (
        <div className="split-view fill">
          <section className="fill">
            {!plans.data ? (
              !plans.error && <Loading />
            ) : (
              <DataTable
                rows={plans.data}
                columns={planColumns}
                caption="감축안 목록"
                offset={0}
                total={plans.data.length}
                limit={plans.data.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="감축안이 없습니다. 피크 경보에서 감축안을 만드세요."
                    action="피크 경보로"
                    onAction={() => setTab("alarms")}
                  />
                }
              />
            )}
          </section>
          <RevealAnchor when={openId} />
          {openId && (
            <DetailPanel
              wide
              title={plan ? `${plan.planNo} 감축안` : "감축안"}
              onClose={() => setOpenId(null)}
            >
              {!plan ? (
                <Loading />
              ) : (
                <>
                  <p>
                    상태 <strong>{PLAN_STATUS[plan.status]}</strong> · 목표{" "}
                    {num(plan.targetReductionKw)} kW · 예상{" "}
                    {num(
                      (plan.steps ?? []).reduce(
                        (sum, s) => sum + Number(s.expectedKw),
                        0,
                      ),
                    )}{" "}
                    kW · FEMS 경보 {plan.femsAlarmRef}
                  </p>
                  {plan.decisionNote && (
                    <p className="muted">의견: {plan.decisionNote}</p>
                  )}
                  <DataTable
                    rows={plan.steps ?? []}
                    columns={stepColumns}
                    caption="감축 단계"
                    offset={0}
                    total={(plan.steps ?? []).length}
                    limit={(plan.steps ?? []).length || 1}
                    onPage={() => undefined}
                  />
                  {OPEN_STATES.includes(plan.status) && (
                    <>
                      <Field
                        label="의견(선택)"
                        value={note}
                        maxLength={300}
                        onChange={(e) => setNote(e.target.value)}
                      />
                      <div className="row-actions">
                        {plan.status === "PROPOSED" ? (
                          <>
                            <button
                              type="button"
                              disabled={pending}
                              onClick={() =>
                                void decide(
                                  "approve",
                                  "승인했습니다. 단계마다 제어 명령을 냈습니다.",
                                )
                              }
                            >
                              승인하고 실행
                            </button>
                            <button
                              type="button"
                              className="secondary"
                              disabled={pending}
                              onClick={() =>
                                void decide("reject", "반려했습니다.")
                              }
                            >
                              반려
                            </button>
                          </>
                        ) : (
                          <button
                            type="button"
                            disabled={pending || plan.alarmOpen !== false}
                            title={
                              plan.alarmOpen
                                ? "피크 경보가 아직 진행 중입니다"
                                : undefined
                            }
                            onClick={() =>
                              void decide(
                                "restore",
                                "복귀했습니다. 공조기가 스케줄 운전으로 돌아갑니다.",
                              )
                            }
                          >
                            복귀 승인
                          </button>
                        )}
                      </div>
                      {plan.status === "EXECUTED" && (
                        <p className="muted">
                          {plan.alarmOpen === null
                            ? "FEMS가 꺼져 있어 경보 상태를 알 수 없습니다."
                            : plan.alarmOpen
                              ? "FEMS 피크 경보가 해제되면 복귀할 수 있습니다."
                              : "경보가 해제됐습니다. 복귀를 승인하세요."}
                        </p>
                      )}
                    </>
                  )}
                </>
              )}
            </DetailPanel>
          )}
        </div>
      )}
    </div>
  );
}
