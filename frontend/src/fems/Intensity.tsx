// F-06 원단위 분석 — 생산 1단위당 에너지와 기준선 비교 (FS-018j)
// 에너지원이 다르면 원단위를 단위별로 따로 내고, 합계는 1차에너지(TOE) 환산 후 값만 보여 준다.
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
type Quantity = { quantity: string; unit: string };
export type IntensityRecord = {
  id: number;
  sourceKey: string;
  versionNo: number;
  equipmentCode: string;
  equipmentName: string;
  itemCode: string;
  startDate: string;
  endDate: string;
  productionQty: string;
  unit: string;
  energy: Quantity[];
  intensity: { value: string; unit: string }[];
  toePerUnit: string | null;
  status: "CALCULATED" | "NO_PRODUCTION" | "NO_ENERGY";
};
export type IntensityItem = {
  itemCode: string;
  lots: string[];
  energy: Quantity;
  output: Quantity;
  intensity: string | null;
  intensityUnit: string;
  status: "CALCULATED" | "NO_PRODUCTION";
  baseline: {
    code: string;
    value: string;
    unit: string;
    periodFrom: string;
    periodTo: string;
  } | null;
  changeRate: string | null;
};
export type IntensityData = {
  period: { from: string; to: string } | null;
  records: IntensityRecord[];
  items: IntensityItem[];
};
const num = (value: string, digits = 3) =>
  Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits });
// 원단위가 기준선보다 크면 같은 1개를 만드는 데 에너지를 더 쓴 것이다.
export function ChangeBadge({ rate }: { rate: string | null }) {
  if (rate === null) return <>—</>;
  const value = Number(rate);
  if (value === 0) return <Badge tone="normal">기준선과 같음</Badge>;
  return value > 0 ? (
    <Badge tone="warning">+{num(rate, 1)}% 악화</Badge>
  ) : (
    <Badge tone="normal">{num(rate, 1)}% 개선</Badge>
  );
}
export function RecordStatus({ record }: { record: IntensityRecord }) {
  if (record.status === "NO_PRODUCTION")
    return <Badge tone="warning">생산량 없음 · 계산 불가</Badge>;
  if (record.status === "NO_ENERGY")
    return <Badge tone="warning">배분 결과 없음</Badge>;
  return <Badge tone="normal">계산됨</Badge>;
}
export function Intensity() {
  const { fail } = useSession();
  const [draft, setDraft] = useState({ from: "", to: "" });
  const [applied, setApplied] = useState({ from: "", to: "" });
  const [data, setData] = useState<IntensityData>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setData(undefined);
    const params = applied.from
      ? `?${new URLSearchParams(applied).toString()}`
      : "";
    api<IntensityData>(`/api/v1/fems/intensity${params}`, {
      signal: controller.signal,
    })
      .then((r) => {
        setData(r.data);
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
        id="F-06"
        title="원단위 분석"
        subtitle="제품 1단위당 에너지 · 기준선 대비 증감"
        help="fems/f-06"
      />
      <p className="muted" role="note">
        원단위 = 생산 구간에 포함된 설비 일별 배분의 합 ÷ 생산량. 원천 키별 최신
        확정 버전만 쓰고 초안은 뺍니다. 기간에 일부만 걸친 기록은 비례 추정하지
        않고 제외합니다.
      </p>
      <form
        className="filter-bar"
        aria-label="원단위 조회 조건"
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
      {!data ? (
        !error && <Loading delay={300} />
      ) : !data.period || !data.records.length ? (
        <EmptyState
          reason="이 기간에 확정된 생산량 기록이 없어 원단위를 계산할 수 없습니다."
          to="/fems/production"
          action="생산량 등록"
        />
      ) : (
        <>
          <section className="panel" aria-label="품목 원단위">
            <h2>품목 원단위 · 기준선 비교</h2>
            <p className="muted">
              검사(최종 공정)까지 끝난 LOT만 묶습니다. 분자는 LOT 전 공정 설비의
              전력, 분모는 검사 양품입니다. 직접 입력(MAN-) 기록은 LOT 정보가
              없어 아래 기록별 원단위에만 나옵니다.
            </p>
            {data.items.length ? (
              <div className="table-scroll">
                <table className="emission-table">
                  <caption>확정 기준선과 비교 (초안 기준선 제외)</caption>
                  <thead>
                    <tr>
                      <th scope="col">품목</th>
                      <th scope="col">원단위</th>
                      <th scope="col">기준선 대비</th>
                      <th scope="col">기준선</th>
                      <th scope="col">근거</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((i) => (
                      <tr key={i.itemCode}>
                        <th scope="row">{i.itemCode}</th>
                        <td>
                          {i.intensity === null
                            ? "생산량 없음"
                            : `${num(i.intensity)} ${i.intensityUnit}`}
                        </td>
                        <td>
                          <ChangeBadge rate={i.changeRate} />
                        </td>
                        <td>
                          {i.baseline
                            ? `${num(i.baseline.value)} ${i.baseline.unit} (${i.baseline.code}, ${i.baseline.periodFrom}~${i.baseline.periodTo})`
                            : "확정 기준선 없음"}
                        </td>
                        <td>
                          <details className="basis-panel">
                            <summary>근거</summary>
                            <dl>
                              <div>
                                <dt>LOT</dt>
                                <dd>{i.lots.join(", ")}</dd>
                              </div>
                              <div>
                                <dt>전 공정 전력</dt>
                                <dd>
                                  {num(i.energy.quantity, 1)} {i.energy.unit}
                                </dd>
                              </div>
                              <div>
                                <dt>검사 양품</dt>
                                <dd>
                                  {num(i.output.quantity, 0)} {i.output.unit}
                                </dd>
                              </div>
                            </dl>
                          </details>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted">
                이 기간 안에 검사까지 끝난 LOT가 없습니다. 기간을 넓혀 보세요.
              </p>
            )}
          </section>
          <section className="panel" aria-label="기록별 원단위">
            <h2>기록별 원단위</h2>
            <div className="table-scroll">
              <table className="emission-table">
                <caption>
                  {data.period.from} ~ {data.period.to} · 에너지원별로 따로,
                  TOE는 1차에너지 환산 후 값
                </caption>
                <thead>
                  <tr>
                    <th scope="col">원천 키</th>
                    <th scope="col">원단위</th>
                    <th scope="col">상태</th>
                    <th scope="col">TOE 환산</th>
                    <th scope="col">생산량</th>
                    <th scope="col">설비·기간</th>
                  </tr>
                </thead>
                <tbody>
                  {data.records.map((r) => (
                    <tr key={r.id}>
                      <th scope="row">
                        {r.sourceKey} · v{r.versionNo}
                      </th>
                      <td>
                        {r.intensity.length
                          ? r.intensity
                              .map((i) => `${num(i.value)} ${i.unit}`)
                              .join(" · ")
                          : "—"}
                      </td>
                      <td>
                        <RecordStatus record={r} />
                      </td>
                      <td>
                        {r.toePerUnit === null
                          ? "—"
                          : `${num(r.toePerUnit, 6)} TOE/${r.unit}`}
                      </td>
                      <td>
                        {num(r.productionQty, 0)} {r.unit}
                      </td>
                      <td>
                        {r.equipmentCode} ·{" "}
                        {r.startDate === r.endDate
                          ? r.startDate
                          : `${r.startDate}~${r.endDate}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </>
  );
}
