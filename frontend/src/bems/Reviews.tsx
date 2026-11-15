// B-13 월간 건물 보고서 — 초안 작성 → 확정(스냅샷) → 인쇄 (UI-03 L+DetailPanel wide 패턴).
// 비용은 확정한 배분만 가져온다. 확정본은 EIP가 monthly_summary로 읽는다.
import { useState } from "react";
import { Link } from "react-router-dom";
import {
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
import { snapshotBadge } from "./Costs";
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
  type EnergyReview,
} from "./common";

const thisMonth = () => new Date().toISOString().slice(0, 7);

export function Reviews() {
  const [month, setMonth] = useState(thisMonth());
  const [issues, setIssues] = useState("");
  const list = useGet<EnergyReview[]>("/reviews");
  const [openId, setOpenId] = useState<number | null>(null);
  const detail = useGet<EnergyReview>(openId ? `/reviews/${openId}` : null);
  const [message, setMessage] = useState("");
  const refresh = () => {
    list.reload();
    detail.reload();
  };
  const { send, pending, error: saveError, setError } = useSend(refresh);
  if (moduleOff(list.error)) return <ModuleOff />;

  async function draft() {
    setMessage("");
    const review = await send<EnergyReview>("/reviews", "POST", {
      month,
      issues: issues || undefined,
    });
    if (review) {
      setOpenId(review.id);
      setIssues("");
      setMessage(
        `${review.reviewMonth} 보고서 초안을 만들었습니다(버전 ${review.version}).`,
      );
    }
  }
  async function confirm() {
    if (!openId) return;
    setMessage("");
    const review = await send<EnergyReview>(
      `/reviews/${openId}/confirm`,
      "POST",
    );
    if (review) setMessage("확정했습니다. 확정본은 EIP 경영 요약이 읽습니다.");
  }

  const columns: Column<EnergyReview>[] = [
    { key: "reviewMonth", label: "보고 월" },
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
    { key: "totalKwh", label: "공용 kWh", render: (r) => num(r.totalKwh, 0) },
    {
      key: "euiKwhPerM2",
      label: "원단위 kWh/㎡",
      render: (r) => num(r.euiKwhPerM2, 4),
    },
    {
      key: "targetAchievement",
      label: "달성률",
      render: (r) => percent(r.targetAchievement),
    },
    { key: "totalCost", label: "비용", render: (r) => money(r.totalCost) },
  ];
  const review = detail.data?.id === openId ? detail.data : undefined;

  return (
    <div className="page-fill">
      <PageTitle
        id="B-13"
        title="월간 건물 보고서"
        subtitle="공용 사용량·원단위·목표 달성률·비용·쾌적 시간 비율을 한 장으로 남깁니다"
        help="bems/b-13"
        actions={
          <>
            <Field
              label="보고 월"
              type="month"
              value={month}
              onChange={(e) => setMonth(e.target.value || thisMonth())}
            />
            <button
              type="button"
              disabled={pending}
              onClick={() => void draft()}
            >
              초안 작성
            </button>
          </>
        }
      />
      <ScreenIntro>
        비용은 <Link to="/bems/costs">확정한 배분</Link>만 가져옵니다 — 초안
        비용은 보고서에 싣지 않습니다. 같은 달의 옛 초안은 새 초안이 지우고,
        확정본은 새 버전을 확정할 때 대체됩니다.
      </ScreenIntro>
      <Field
        label="주요 이슈·조치(선택)"
        value={issues}
        maxLength={2000}
        onChange={(e) => setIssues(e.target.value)}
      />
      <p role="status">{message}</p>
      <ErrorNotice error={saveError} />
      <ErrorNotice error={list.error} retry={refresh} />
      {!list.data ? (
        !list.error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={list.data}
              columns={columns}
              caption="월간 건물 보고서 목록"
              offset={0}
              total={list.data.length}
              limit={list.data.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="보고서가 없습니다. 월을 고르고 초안을 만드세요."
                  to="/bems/energy"
                  action="건물 에너지로"
                />
              }
            />
          </section>
          <RevealAnchor when={openId} />
          {openId && (
            <DetailPanel
              wide
              title={
                review
                  ? `${review.reviewMonth} 보고서 v${review.version}`
                  : "보고서"
              }
              onClose={() => setOpenId(null)}
              actions={
                <>
                  {review?.status === "draft" && (
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() => void confirm()}
                    >
                      확정
                    </button>
                  )}
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => window.print()}
                  >
                    인쇄
                  </button>
                </>
              }
            >
              {!review ? (
                <Loading />
              ) : (
                <>
                  <p>
                    상태 <strong>{SNAPSHOT_LABEL[review.status]}</strong>
                    {review.confirmedAt
                      ? ` · 확정 ${time(review.confirmedAt)}`
                      : ""}
                  </p>
                  <dl className="summary-list">
                    <dt>공용 사용량</dt>
                    <dd>{num(review.totalKwh, 0)} kWh</dd>
                    <dt>원단위</dt>
                    <dd>{num(review.euiKwhPerM2, 4)} kWh/㎡</dd>
                    <dt>목표 달성률</dt>
                    <dd>{percent(review.targetAchievement)}</dd>
                    <dt>공용 비용</dt>
                    <dd>{money(review.totalCost)}</dd>
                    <dt>쾌적 시간 비율</dt>
                    <dd>{percent(review.comfortRatio)}</dd>
                  </dl>
                  <h3>주요 이슈·조치</h3>
                  <p>{review.issues || "적은 내용이 없습니다."}</p>
                </>
              )}
            </DetailPanel>
          )}
        </div>
      )}
    </div>
  );
}
