// F-08 요금 산정 — 월마다 그 달의 요금제를 적용, 개정 월에서 구간이 나뉜다 (FS-018h)
// 조회 시 계산하며 저장하지 않는다. TOU 요금제면 시각마다 그 시간의 요율을 적용한다(DSN-15 Q1).
import { useEffect, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  Badge,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
export type LoadBand = "OFF_PEAK" | "MID" | "PEAK";
export const LOAD_BAND_LABEL: Record<LoadBand, string> = {
  OFF_PEAK: "경부하",
  MID: "중간부하",
  PEAK: "최대부하",
};
type Segment = {
  month: string;
  usage: string;
  tariff: {
    tariffCode: string;
    name: string;
    tariffKind: "FLAT" | "TOU";
    contractKw: string | null;
    basicCharge: string;
    usageRate: string;
    effectiveFrom: string;
    effectiveTo: string | null;
  } | null;
  basicCharge: string | null;
  usageCharge: string | null;
  amount: string | null;
  loadBands?: { loadBand: LoadBand; usage: string; charge: string }[];
};
export type BillingSource = {
  energySourceId: number;
  sourceCode: string;
  name: string;
  unit: string;
  status: "CALCULATED" | "TARIFF_MISSING" | "NOT_BILLABLE";
  usage: string;
  total: string | null;
  segments: Segment[];
};
export type BillingData = {
  period: {
    from: string;
    to: string;
    dateFrom: string;
    dateTo: string;
    monthToDate: boolean;
  } | null;
  sources: BillingSource[];
  total: string;
  currency: string;
  complete: boolean;
};
const won = (value: string | null) =>
  value === null ? "—" : `${Number(value).toLocaleString("ko-KR")}원`;
const num = (value: string) =>
  Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 1 });
export function SourceBilling({ source }: { source: BillingSource }) {
  if (source.status === "NOT_BILLABLE")
    return (
      <section className="panel" aria-label={`${source.name} 요금`}>
        <h2>{source.name}</h2>
        <p className="muted">
          요금 부과 대상이 아닙니다(사내 생산 유틸리티). 사용량{" "}
          {num(source.usage)} {source.unit}
        </p>
      </section>
    );
  return (
    <section className="panel" aria-label={`${source.name} 요금`}>
      <h2>
        {source.name} · {won(source.total)}
        {source.status === "TARIFF_MISSING" && (
          <>
            {" "}
            <Badge tone="issue">요금제 없는 달 제외</Badge>
          </>
        )}
      </h2>
      <div className="table-scroll">
        <table className="emission-table">
          <caption>월별 적용 요금제</caption>
          <thead>
            <tr>
              <th scope="col">월</th>
              <th scope="col" className="num">
                요금
              </th>
              <th scope="col">요금제</th>
              <th scope="col" className="num">
                기본요금
              </th>
              <th scope="col">사용량 × 단가</th>
            </tr>
          </thead>
          <tbody>
            {source.segments.map((s) => (
              <tr key={s.month}>
                <th scope="row">{s.month}</th>
                <td className="num">
                  {s.amount === null ? "요금제 없음" : won(s.amount)}
                </td>
                <td>
                  {s.tariff ? (
                    <>
                      {s.tariff.tariffCode} ({s.tariff.effectiveFrom} ~{" "}
                      {s.tariff.effectiveTo ?? "계속"})
                      {s.tariff.tariffKind === "TOU" && (
                        <>
                          {" "}
                          <Badge tone="normal">시간대별</Badge>
                        </>
                      )}
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="num">
                  {won(s.basicCharge)}
                  {s.tariff?.tariffKind === "TOU" && s.tariff.contractKw && (
                    <small className="muted">
                      {" "}
                      계약 {num(s.tariff.contractKw)} kW
                    </small>
                  )}
                </td>
                <td>
                  {num(s.usage)} {source.unit}
                  {s.tariff?.tariffKind === "TOU" ? (
                    <> = {won(s.usageCharge)}</>
                  ) : (
                    s.tariff &&
                    ` × ${num(s.tariff.usageRate)}원 = ${won(s.usageCharge)}`
                  )}
                  {s.loadBands && (
                    // 부하 구분별 소계. 어느 시간대가 요금을 끌어올렸는지 여기서 보인다.
                    <ul className="rank-list">
                      {s.loadBands.map((b) => (
                        <li key={b.loadBand}>
                          <span>{LOAD_BAND_LABEL[b.loadBand]}</span>
                          <span>
                            {num(b.usage)} {source.unit} · {won(b.charge)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
export function Billing() {
  const { fail } = useSession();
  const [draft, setDraft] = useState({ from: "", to: "" });
  const [applied, setApplied] = useState({ from: "", to: "" });
  const [data, setData] = useState<BillingData>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setData(undefined);
    const params = applied.from
      ? `?${new URLSearchParams(applied).toString()}`
      : "";
    api<BillingData>(`/api/v1/fems/billing${params}`, {
      signal: controller.signal,
    })
      .then((r) => {
        setData(r.data);
        if (r.data.period && !applied.from)
          setDraft({ from: r.data.period.from, to: r.data.period.to });
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [applied, reload]);
  function submit(event: FormEvent) {
    event.preventDefault();
    setApplied(draft);
  }
  if (
    error instanceof ApiError &&
    error.error.details?.reason === "MODULE_DISABLED"
  )
    return (
      <EmptyState
        reason="FEMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const fieldErrors =
    error instanceof ApiError && error.error.code === "VALIDATION_FAILED"
      ? ((error.error.details?.fields ?? {}) as Record<string, string>)
      : {};
  return (
    <>
      <PageTitle
        id="F-08"
        title="요금 산정"
        subtitle="기본요금 + 사용량 × 단가 · 조회 시 계산하며 저장하지 않습니다"
        help="fems/f-08"
      />
      <form
        className="filter-bar"
        aria-label="요금 산정 조건"
        onSubmit={submit}
      >
        <label>
          시작월
          <input
            type="month"
            value={draft.from}
            aria-invalid={!!fieldErrors.from}
            onChange={(e) => setDraft({ ...draft, from: e.target.value })}
          />
        </label>
        <label>
          종료월
          <input
            type="month"
            value={draft.to}
            aria-invalid={!!fieldErrors.to}
            onChange={(e) => setDraft({ ...draft, to: e.target.value })}
          />
        </label>
        <button type="submit">조회</button>
      </form>
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!data ? (
        !error && <Loading delay={300} />
      ) : !data.period || !data.sources.length ? (
        <EmptyState
          reason="이 기간에는 계측값이 없어 요금을 계산할 수 없습니다."
          to="/fems/readings"
          action="계측값 보기"
        />
      ) : (
        <>
          <section className="stat-tile" aria-label="예상 요금 합계">
            <p>
              예상 요금 합계 · {data.period.from} ~ {data.period.to}
            </p>
            <strong>
              {Number(data.total).toLocaleString("ko-KR")} <span>원</span>
            </strong>
            {!data.complete && (
              <Badge tone="warning">요금제 없는 달은 합계에서 빠졌습니다</Badge>
            )}
            <small>
              월마다 그 달에 적용되는 요금제를 씁니다. 기본요금은 월 단위로 전액
              부과합니다.
              {data.period.monthToDate &&
                ` ${data.period.to}은 ${data.period.dateTo}까지 누계 사용량 기준입니다.`}
            </small>
          </section>
          {data.sources.map((s) => (
            <SourceBilling key={`${s.energySourceId}-${s.unit}`} source={s} />
          ))}
        </>
      )}
    </>
  );
}
