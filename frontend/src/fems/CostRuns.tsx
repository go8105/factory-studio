// F-22 에너지 비용 배분 — 그 달 청구 총액을 설비·부서·품목으로 나눈다 (DSN-15 F43·Q4)
// 확정한 배분만 ERP가 참고로 읽는다. 초안은 지금 계산한 값이다.
import { useState } from "react";
import { api } from "../shared/api";
import { Badge, ErrorNotice, Loading, PageTitle } from "../shared/components";
import { useApiLists, useApiSend } from "../shared/hooks";

type Status = "draft" | "confirmed" | "superseded";
const STATUS_LABEL: Record<Status, string> = {
  draft: "초안",
  confirmed: "확정",
  superseded: "대체됨",
};
type Run = {
  id: number;
  costMonth: string;
  version: number;
  status: Status;
  confirmedAt: string | null;
};
type Line = {
  equipmentCode: string;
  equipmentName: string;
  sourceCode: string;
  departmentCode: string | null;
  itemCode: string | null;
  quantity: string;
  unit: string;
  cost: string;
};
type Detail = Run & {
  lines: Line[];
  total: string;
  byDepartment: { departmentCode: string; cost: string }[];
  unallocatedCost?: string;
  coverage?: { days: number; expectedDays: number; partial: boolean };
};

const won = (v: string) =>
  `${Number(v).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}원`;
const qty = (v: string) =>
  Number(v).toLocaleString("ko-KR", { maximumFractionDigits: 1 });

export function CostRuns() {
  const lists = useApiLists<[Run[]]>("/api/v1/fems", ["/cost-runs"]);
  const { send, pending, error } = useApiSend("/api/v1/fems", lists.reload);
  const [month, setMonth] = useState("");
  const [picked, setPicked] = useState<number>();
  const [detail, setDetail] = useState<Detail>();
  const [done, setDone] = useState<string>();

  const [runs] = lists.data ?? [];

  async function show(id: number) {
    setPicked(id);
    // 조회는 쓰기 훅이 아니라 api로 — 쓰기 훅은 CSRF·멱등 키를 붙이고 목록을 다시 불러온다.
    const r = await api<Detail>(`/api/v1/fems/cost-runs/${id}`).catch(
      () => undefined,
    );
    if (r?.data) setDetail(r.data);
  }
  async function create() {
    const r = await send<Detail>("/cost-runs", "POST", { month });
    if (r?.id) {
      setDetail(r);
      setPicked(r.id);
      setDone(
        `${r.costMonth} 초안을 만들었습니다.` +
          (r.coverage?.partial
            ? ` 계측은 ${r.coverage.days}일/${r.coverage.expectedDays}일분입니다.`
            : ""),
      );
    }
  }
  async function confirm(row: Run) {
    const r = await send<Detail>(`/cost-runs/${row.id}/confirm`, "POST");
    if (r?.id) {
      setDetail((d) => (d?.id === r.id ? { ...d, ...r } : d));
      setDone(`${row.costMonth} v${row.version}을(를) 확정했습니다.`);
    }
  }

  return (
    <>
      <PageTitle
        id="F-22"
        title="에너지 비용 배분"
        subtitle="그 달 청구 총액을 설비·부서·품목으로 나눕니다"
        help="fems/f-22"
      />
      <ErrorNotice error={error} />
      {done && <p role="status">{done}</p>}
      <div className="filter-bar">
        <label>
          배분 월
          <input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={pending || !month}
          onClick={() => void create()}
        >
          초안 만들기
        </button>
      </div>
      <p className="muted" role="note">
        비용 = 그 달 요금 × 설비 배분량 ÷ 사업장 사용량입니다.{" "}
        <strong>설비별 부하 시간대는 따로 반영하지 않고 평균 요율</strong>로
        나눕니다 — 배분이 일 단위라 설비의 시간별 사용 모양이 없습니다. 설비에
        배분되지 않은 공용 비용은 설비에 넣지 않고 따로 보입니다. 확정한 배분만
        ERP 원가 화면이 참고로 읽고, ERP의 배부 기준은 생산량 그대로입니다.
      </p>
      {!runs ? (
        !lists.error && <Loading delay={300} />
      ) : runs.length === 0 ? (
        <p className="muted">배분이 없습니다. 월을 골라 초안을 만드세요.</p>
      ) : (
        <div className="table-scroll">
          <table aria-label="배분 목록">
            <thead>
              <tr>
                <th scope="col">월</th>
                <th scope="col">버전</th>
                <th scope="col">상태</th>
                <th scope="col">관리</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <th scope="row">{r.costMonth}</th>
                  <td>v{r.version}</td>
                  <td>
                    <Badge
                      tone={r.status === "confirmed" ? "normal" : "warning"}
                    >
                      {STATUS_LABEL[r.status]}
                    </Badge>
                  </td>
                  <td>
                    <span className="row-actions">
                      <button
                        type="button"
                        className="link-button"
                        aria-pressed={picked === r.id}
                        onClick={() => void show(r.id)}
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
      )}
      {detail && (
        <div className="dashboard-grid has-lead">
          <section className="panel" aria-label="설비별 비용">
            <h2>
              {detail.costMonth} v{detail.version} · 설비 합계{" "}
              {won(detail.total)}
            </h2>
            {detail.coverage?.partial && (
              <p className="field-error" role="note">
                계측이 {detail.coverage.days}일분뿐이라{" "}
                <strong>달 전체의 비용이 아닙니다.</strong>
              </p>
            )}
            {detail.unallocatedCost !== undefined && (
              <p className="muted">
                설비에 배분되지 않은 공용 비용 {won(detail.unallocatedCost)}
              </p>
            )}
            <div className="table-scroll">
              <table aria-label="설비별 비용">
                <thead>
                  <tr>
                    <th scope="col">설비</th>
                    <th scope="col">에너지원</th>
                    <th scope="col">부서</th>
                    <th scope="col">주 품목</th>
                    <th scope="col" className="num">
                      배분량
                    </th>
                    <th scope="col" className="num">
                      비용
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {detail.lines.map((l) => (
                    <tr key={`${l.equipmentCode}-${l.sourceCode}`}>
                      <td>
                        {l.equipmentCode} {l.equipmentName}
                      </td>
                      <td>{l.sourceCode}</td>
                      <td>{l.departmentCode ?? "미지정"}</td>
                      <td>{l.itemCode ?? "—"}</td>
                      <td className="num">
                        {qty(l.quantity)} {l.unit}
                      </td>
                      <td className="num">{won(l.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="panel" aria-label="부서별 비용">
            <h2>부서별</h2>
            <ul className="rank-list">
              {detail.byDepartment.map((d) => (
                <li key={d.departmentCode}>
                  <span>{d.departmentCode}</span>
                  <span>{won(d.cost)}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </>
  );
}
