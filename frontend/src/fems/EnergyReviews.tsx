// F-20 월간 에너지 검토 — 그 달 스냅샷을 확정하고 인쇄한다 (DSN-15 F33·Q5)
// 초안은 지금 계산한 값이고, 확정은 그 값을 그대로 굳힌다. 고치려면 새 초안을 만든다.
import { useState } from "react";
import {
  Badge,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
} from "../shared/components";
import { useApiLists, useApiSend } from "../shared/hooks";

type Status = "draft" | "confirmed" | "superseded";
const STATUS_LABEL: Record<Status, string> = {
  draft: "초안",
  confirmed: "확정",
  superseded: "대체됨",
};
type Review = {
  id: number;
  reviewMonth: string;
  version: number;
  status: Status;
  primaryEnergyToe: string;
  energyCost: string;
  emissionTco2e: string;
  targetAchievement: string | null;
  issues: string | null;
  confirmedAt: string | null;
};
type Created = Review & {
  coverage: { days: number; expectedDays: number; partial: boolean };
};

const num = (v: string, digits = 1) =>
  Number(v).toLocaleString("ko-KR", { maximumFractionDigits: digits });

export function EnergyReviews() {
  const lists = useApiLists<[Review[]]>("/api/v1/fems", ["/energy-reviews"]);
  const { send, pending, error } = useApiSend("/api/v1/fems", lists.reload);
  const [month, setMonth] = useState("");
  const [issues, setIssues] = useState("");
  const [picked, setPicked] = useState<number>();
  const [done, setDone] = useState<string>();

  const [reviews] = lists.data ?? [];
  const shown = reviews?.find((r) => r.id === picked) ?? reviews?.[0];

  async function create() {
    const r = await send<Created>("/energy-reviews", "POST", {
      month,
      issues: issues.trim() || null,
    });
    if (r?.id) {
      setPicked(r.id);
      setIssues("");
      setDone(
        `${r.reviewMonth} 초안을 만들었습니다.` +
          (r.coverage.partial
            ? ` 계측은 ${r.coverage.days}일/${r.coverage.expectedDays}일분입니다.`
            : ""),
      );
    }
  }
  async function confirm(row: Review) {
    const r = await send<Review>(`/energy-reviews/${row.id}/confirm`, "POST");
    if (r?.id)
      setDone(`${row.reviewMonth} v${row.version}을(를) 확정했습니다.`);
  }

  return (
    <>
      <PageTitle
        id="F-20"
        title="월간 에너지 검토"
        subtitle="그 달 사용·비용·배출·목표 달성을 스냅샷으로 확정하고 인쇄합니다"
        help="fems/f-20"
        actions={
          shown && (
            <button type="button" onClick={() => window.print()}>
              보고서 인쇄
            </button>
          )
        }
      />
      <ErrorNotice error={error} />
      {done && <p role="status">{done}</p>}
      <div className="filter-bar">
        <label>
          검토 월
          <input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          />
        </label>
        <Field
          label="주요 이슈"
          value={issues}
          maxLength={1800}
          onChange={(e) => setIssues(e.target.value)}
        />
        <button
          type="button"
          disabled={pending || !month}
          onClick={() => void create()}
        >
          초안 만들기
        </button>
      </div>
      <p className="muted" role="note">
        초안은 <strong>지금 계산한 값</strong>이고, 확정은 그 값을 그대로
        굳힙니다. 확정한 검토는 바꾸지 않고, 고치려면 새 초안을 만들어
        확정하세요 — 옛 확정본은 대체됨이 됩니다. 계수나 요금제가 빠진
        에너지원이 있으면 부분 합계를 남기지 않으려고 초안을 만들지 않습니다.
      </p>
      {!reviews ? (
        !lists.error && <Loading delay={300} />
      ) : reviews.length === 0 ? (
        <p className="muted">검토가 없습니다. 월을 골라 초안을 만드세요.</p>
      ) : (
        <>
          <div className="table-scroll">
            <table aria-label="검토 목록">
              <thead>
                <tr>
                  <th scope="col">월</th>
                  <th scope="col">버전</th>
                  <th scope="col">상태</th>
                  <th scope="col" className="num">
                    1차에너지(toe)
                  </th>
                  <th scope="col" className="num">
                    비용(원)
                  </th>
                  <th scope="col" className="num">
                    배출(tCO2e)
                  </th>
                  <th scope="col">관리</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map((r) => (
                  <tr key={r.id}>
                    <th scope="row">{r.reviewMonth}</th>
                    <td>v{r.version}</td>
                    <td>
                      <Badge
                        tone={r.status === "confirmed" ? "normal" : "warning"}
                      >
                        {STATUS_LABEL[r.status]}
                      </Badge>
                    </td>
                    <td className="num">{num(r.primaryEnergyToe, 2)}</td>
                    <td className="num">{num(r.energyCost, 0)}</td>
                    <td className="num">{num(r.emissionTco2e, 2)}</td>
                    <td>
                      <span className="row-actions">
                        <button
                          type="button"
                          className="link-button"
                          aria-pressed={shown?.id === r.id}
                          onClick={() => setPicked(r.id)}
                        >
                          보기
                        </button>
                        {r.status === "draft" && (
                          <button
                            type="button"
                            className="link-button"
                            disabled={pending}
                            onClick={() => void confirm(r)}
                          >
                            확정
                          </button>
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {shown && (
            <section className="panel print-area" aria-label="검토 보고서">
              <h2>
                {shown.reviewMonth} 월간 에너지 검토 · v{shown.version}{" "}
                <Badge
                  tone={shown.status === "confirmed" ? "normal" : "warning"}
                >
                  {STATUS_LABEL[shown.status]}
                </Badge>
              </h2>
              <p className="print-only">
                {shown.confirmedAt
                  ? `확정 ${shown.confirmedAt.slice(0, 10)}`
                  : "확정 전 초안입니다"}
              </p>
              <ul className="rank-list">
                <li>
                  <span>1차에너지</span>
                  <span>{num(shown.primaryEnergyToe, 2)} toe</span>
                </li>
                <li>
                  <span>에너지 비용</span>
                  <span>{num(shown.energyCost, 0)}원</span>
                </li>
                <li>
                  <span>배출량</span>
                  <span>{num(shown.emissionTco2e, 2)} tCO2e</span>
                </li>
                <li>
                  <span>목표 달성률</span>
                  <span>
                    {/* 목표가 없으면 0%가 아니라 낼 수 없는 값이다. */}
                    {shown.targetAchievement === null
                      ? "목표 없음"
                      : `${num(shown.targetAchievement, 1)} %`}
                  </span>
                </li>
              </ul>
              {shown.issues && (
                <p className="wrap">주요 이슈: {shown.issues}</p>
              )}
            </section>
          )}
        </>
      )}
    </>
  );
}
