// F-04 배출량 현황 — 조회 시 계산, 저장하지 않는다 (FS-018d)
// 배출계수(EMISSION)만 쓴다. 1차에너지 환산계수(PRIMARY)와 다른 계수다.
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
type Factor = {
  kind: "EMISSION";
  year: string;
  value: string;
  unit: string;
  source: string;
};
type Quantity = { quantity: string; unit: string };
export type EmissionSource = {
  energySourceId: number;
  sourceCode: string;
  name: string;
  sourceKind: string;
  status: "CALCULATED" | "NOT_APPLICABLE" | "FACTOR_MISSING" | "UNIT_MISMATCH";
  consumption: Quantity;
  excludedReadings: number;
  emission: string | null;
  segments: {
    year: string;
    consumption: Quantity;
    factor: Factor | null;
    emission: string | null;
  }[];
};
export type EmissionResult = {
  period: { from: string; to: string } | null;
  sources: EmissionSource[];
  totalEmission: string | null;
  unit: string;
  complete: boolean;
};
export const STATUS = {
  CALCULATED: ["계산됨", "normal"],
  NOT_APPLICABLE: ["대상 아님", "normal"],
  FACTOR_MISSING: ["계수 없음 · 계산 불가", "issue"],
  UNIT_MISMATCH: ["계수 단위 불일치 · 계산 불가", "issue"],
} as const;
const num = (value: string, digits = 3) =>
  Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits });
export function EmissionBasis({ source }: { source: EmissionSource }) {
  if (source.status === "NOT_APPLICABLE")
    return (
      <p className="muted">
        {source.name}은(는) 에너지가 아니어서 배출 산정 대상이 아닙니다.
      </p>
    );
  return (
    <details className="basis-panel">
      <summary>근거</summary>
      <table>
        <caption>연도별 배출계수 적용</caption>
        <thead>
          <tr>
            <th scope="col">연도</th>
            <th scope="col" className="num">
              소비량
            </th>
            <th scope="col">배출계수</th>
            <th scope="col">출처</th>
            <th scope="col" className="num">
              배출량
            </th>
          </tr>
        </thead>
        <tbody>
          {source.segments.map((s) => (
            <tr key={s.year}>
              <td>{s.year}</td>
              <td className="num">
                {num(s.consumption.quantity)} {s.consumption.unit}
              </td>
              <td>
                {s.factor ? `${s.factor.value} ${s.factor.unit}` : "없음"}
              </td>
              <td>{s.factor?.source ?? "—"}</td>
              <td className="num">
                {s.emission === null ? "계산 불가" : num(s.emission, 6)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {source.excludedReadings > 0 && (
        <p className="muted">
          결측 {source.excludedReadings}건은 소비량에서 제외했습니다.
        </p>
      )}
    </details>
  );
}
export function Emissions() {
  const { fail } = useSession();
  const [draft, setDraft] = useState({ from: "", to: "" });
  const [applied, setApplied] = useState({ from: "", to: "" });
  const [result, setResult] = useState<EmissionResult>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setResult(undefined);
    const params = applied.from
      ? `?${new URLSearchParams(applied).toString()}`
      : "";
    api<EmissionResult>(`/api/v1/fems/emissions${params}`, {
      signal: controller.signal,
    })
      .then((r) => {
        setResult(r.data);
        if (r.data.period && !applied.from) setDraft(r.data.period);
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
        id="F-04"
        title="배출량 현황"
        subtitle="에너지 소비량 × 배출계수 · 조회 시 계산하며 저장하지 않습니다"
        help="fems/f-04"
      />
      <form
        className="filter-bar"
        aria-label="배출량 조회 조건"
        onSubmit={submit}
      >
        <label>
          시작일
          <input
            type="date"
            value={draft.from}
            aria-invalid={!!fieldErrors.from}
            onChange={(e) => setDraft({ ...draft, from: e.target.value })}
          />
        </label>
        <label>
          종료일
          <input
            type="date"
            value={draft.to}
            aria-invalid={!!fieldErrors.to}
            onChange={(e) => setDraft({ ...draft, to: e.target.value })}
          />
        </label>
        <button type="submit">조회</button>
      </form>
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!result ? (
        !error && <Loading delay={300} />
      ) : !result.sources.length ? (
        <EmptyState
          reason="이 기간에는 계측값이 없어 배출량을 계산할 수 없습니다."
          to="/fems/readings"
          action="계측값 보기"
        />
      ) : (
        <>
          <section className="stat-tile" aria-label="총 배출량">
            <p>총 배출량</p>
            <strong>
              {num(result.totalEmission ?? "0")} <span>{result.unit}</span>
            </strong>
            {!result.complete && (
              <Badge tone="warning">
                일부 에너지원은 계산 불가 · 합계에서 빠졌습니다
              </Badge>
            )}
            <small>
              배출계수(EMISSION)를 에너지원별로 적용해 합했습니다. 1차에너지
              환산계수와 다른 계수입니다.
            </small>
          </section>
          <div className="table-scroll">
            <table className="emission-table">
              <caption>에너지원별 배출량</caption>
              <thead>
                <tr>
                  <th scope="col">에너지원</th>
                  <th scope="col" className="num">
                    소비량
                  </th>
                  <th scope="col" className="num">
                    배출량 (tCO2eq)
                  </th>
                  <th scope="col">상태</th>
                  <th scope="col">근거</th>
                </tr>
              </thead>
              <tbody>
                {result.sources.map((s) => (
                  <tr key={`${s.energySourceId}-${s.consumption.unit}`}>
                    <th scope="row">{s.name}</th>
                    <td className="num">
                      {num(s.consumption.quantity)} {s.consumption.unit}
                    </td>
                    <td className="num">
                      {s.emission === null
                        ? s.status === "NOT_APPLICABLE"
                          ? "—"
                          : "계산 불가"
                        : num(s.emission)}
                    </td>
                    <td>
                      <Badge tone={STATUS[s.status][1]}>
                        {STATUS[s.status][0]}
                      </Badge>
                    </td>
                    <td>
                      <EmissionBasis source={s} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
