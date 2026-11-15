// B-12 공용 비용 배분 — 월 계산(초안) → 확정 → 부서별 배분 (UI-03 L+DetailPanel 패턴).
// 비용 = 시간별 공용 사용량 × 그 시각 FEMS 전력 단가. 부서 비율 = 부서 구역 면적 ÷ 부서 지정 구역 면적 합.
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
  ModuleOff,
  moduleOff,
  money,
  num,
  percent,
  SNAPSHOT_LABEL,
  time,
  useGet,
  useSend,
  type CostLine,
  type CostRun,
  type Snapshot,
} from "./common";

const thisMonth = () => new Date().toISOString().slice(0, 7);
export const snapshotBadge = (s: Snapshot) =>
  s === "confirmed" ? (
    <Badge>{SNAPSHOT_LABEL[s]}</Badge>
  ) : s === "draft" ? (
    <Badge tone="issue">{SNAPSHOT_LABEL[s]}</Badge>
  ) : (
    <Badge tone="warning">{SNAPSHOT_LABEL[s]}</Badge>
  );

export function Costs() {
  const [month, setMonth] = useState(thisMonth());
  const runs = useGet<CostRun[]>("/cost-runs");
  const [openId, setOpenId] = useState<number | null>(null);
  const detail = useGet<CostRun>(openId ? `/cost-runs/${openId}` : null);
  const [message, setMessage] = useState("");
  const refresh = () => {
    runs.reload();
    detail.reload();
  };
  const { send, pending, error: saveError, setError } = useSend(refresh);
  if (moduleOff(runs.error)) return <ModuleOff />;

  async function calculate() {
    setMessage("");
    const run = await send<CostRun>("/cost-runs", "POST", { month });
    if (run) {
      setOpenId(run.id);
      setMessage(
        `${run.costMonth} 공용 비용을 계산했습니다(버전 ${run.version} 초안). 확정하면 월간 보고서가 이 비용을 씁니다.`,
      );
    }
  }
  async function confirm() {
    if (!openId) return;
    setMessage("");
    const run = await send<CostRun>(`/cost-runs/${openId}/confirm`, "POST");
    if (run) setMessage("확정했습니다. 같은 달의 옛 확정본은 대체됩니다.");
  }

  const columns: Column<CostRun>[] = [
    { key: "costMonth", label: "배분 월" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={openId === r.id}
          onClick={() => {
            setOpenId(r.id);
            setMessage("");
            setError(undefined);
          }}
        >
          상세
        </button>
      ),
    },
    { key: "version", label: "버전" },
    { key: "status", label: "상태", render: (r) => snapshotBadge(r.status) },
    {
      key: "totalKwh",
      label: "공용 사용량 kWh",
      render: (r) => num(r.totalKwh, 0),
    },
    { key: "totalCost", label: "공용 비용", render: (r) => money(r.totalCost) },
    {
      key: "confirmedAt",
      label: "확정 시각",
      render: (r) => (r.confirmedAt ? time(r.confirmedAt) : "—"),
    },
  ];
  const lineColumns: Column<CostLine>[] = [
    { key: "departmentCode", label: "부서" },
    { key: "areaM2", label: "면적 ㎡", render: (l) => num(l.areaM2, 0) },
    { key: "share", label: "비율", render: (l) => percent(l.share, 2) },
    { key: "cost", label: "배분 비용", render: (l) => money(l.cost) },
  ];
  const run = detail.data?.id === openId ? detail.data : undefined;

  return (
    <div className="page-fill">
      <PageTitle
        id="B-12"
        title="공용 비용 배분"
        subtitle="월 공용 전력 비용을 부서 면적 비율로 나눕니다"
        help="bems/b-12"
        actions={
          <>
            <Field
              label="배분 월"
              type="month"
              value={month}
              onChange={(e) => setMonth(e.target.value || thisMonth())}
            />
            <button
              type="button"
              disabled={pending}
              onClick={() => void calculate()}
            >
              계산
            </button>
          </>
        }
      />
      <ScreenIntro>
        비용은 시간별 공용 사용량에 그 시각 FEMS 전력 단가를 곱해 더합니다. 부서
        비율은 그 부서 구역 면적 ÷ 부서를 지정한 구역 면적 합이므로,{" "}
        <Link to="/bems/zones">구역·계측</Link>에서 사용 부서를 정해야 합니다.
        <strong>
          {" "}
          부서를 지정하지 않은 구역이 있어도 비용은 전액 나눕니다.
        </strong>
      </ScreenIntro>
      <p role="status">{message}</p>
      <ErrorNotice error={saveError} />
      <ErrorNotice error={runs.error} retry={refresh} />
      {!runs.data ? (
        !runs.error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={runs.data}
              columns={columns}
              caption="공용 비용 배분 목록"
              offset={0}
              total={runs.data.length}
              limit={runs.data.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="배분한 달이 없습니다. 월을 고르고 계산을 누르세요."
                  to="/bems/zones"
                  action="구역·계측으로"
                />
              }
            />
          </section>
          <RevealAnchor when={openId} />
          {openId && (
            <DetailPanel
              wide
              title={
                run ? `${run.costMonth} 배분 v${run.version}` : "비용 배분"
              }
              onClose={() => setOpenId(null)}
              actions={
                run?.status === "draft" && (
                  <button
                    type="button"
                    disabled={pending}
                    onClick={() => void confirm()}
                  >
                    확정
                  </button>
                )
              }
            >
              {!run ? (
                <Loading />
              ) : (
                <>
                  <p>
                    상태 <strong>{SNAPSHOT_LABEL[run.status]}</strong> · 공용{" "}
                    {num(run.totalKwh, 0)} kWh · 비용 {money(run.totalCost)}
                  </p>
                  <DataTable
                    rows={run.lines ?? []}
                    columns={lineColumns}
                    caption="부서별 배분"
                    offset={0}
                    total={(run.lines ?? []).length}
                    limit={(run.lines ?? []).length || 1}
                    onPage={() => undefined}
                  />
                  <p className="muted">
                    줄의 합은 공용 비용과 정확히 같습니다(끝수는 마지막 줄이
                    떠안습니다).
                  </p>
                </>
              )}
            </DetailPanel>
          )}
        </div>
      )}
    </div>
  );
}
