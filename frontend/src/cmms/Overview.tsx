// C-01 보전 개요 — 지금 무엇을 해야 하는지 한 화면에 (UI-02 D 패턴).
// 숫자는 모두 조회 계산이다. 저장하지 않으므로 다른 화면에서 고치면 여기도 바뀐다.
import { Link } from "react-router-dom";
import {
  Badge,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
import { moduleOff, useGet } from "./hooks";
import { qty, type Overview as Data } from "./common";

function Tile({
  label,
  value,
  note,
  to,
}: {
  label: string;
  value: string;
  note: string;
  to?: string;
}) {
  const body = (
    <>
      <p>{label}</p>
      <strong>{value}</strong>
      <small>{note}</small>
    </>
  );
  return to ? (
    <Link className="stat-tile" to={to} aria-label={label}>
      {body}
    </Link>
  ) : (
    <section className="stat-tile" aria-label={label}>
      {body}
    </section>
  );
}

export function Overview() {
  const { data, error, reload } = useGet<Data>("/overview");
  if (moduleOff(error))
    return (
      <EmptyState
        reason="CMMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  return (
    <>
      <PageTitle
        id="C-01"
        title="보전 개요"
        subtitle="지금 손봐야 할 것과 다가온 점검"
        help="cmms/c-01"
      />
      <ErrorNotice error={error} retry={() => reload()} />
      {!data ? (
        !error && <Loading delay={300} />
      ) : (
        <>
          <div className="kpi-grid">
            <Tile
              label="미조치 작업지시"
              value={`${data.requested}건`}
              note={`진행 중 ${data.inProgress}건 · 고장 ${data.openBm}건`}
              to="/cmms/work-orders"
            />
            <Tile
              label="전환 대기 신호"
              value={`${data.pendingSignals}건`}
              note={
                data.sources.bems && data.sources.spc
                  ? "BEMS 경보 · SPC 이상"
                  : `${!data.sources.bems ? "BEMS" : "SPC"} 꺼짐 — 일부만 보입니다`
              }
              to="/cmms/signals"
            />
            <Tile
              label="주기 도래 PM"
              value={`${data.duePlans.length}건`}
              note={
                data.unknownPlans
                  ? `${data.unknownPlans}건은 MES 꺼짐으로 판정 불가`
                  : "예정일·사용량이 주기에 닿았습니다"
              }
              to="/cmms/pm-plans"
            />
            <Tile
              label="설비"
              value={`${data.assetCount}대`}
              note={`중요도 A ${data.criticalCount}대`}
              to="/cmms/assets"
            />
          </div>
          <section>
            <h3>주기가 된 예방보전</h3>
            {data.duePlans.length ? (
              <ul className="spc-trend">
                {data.duePlans.map((p) => (
                  <li key={p.id}>
                    <strong>{p.code}</strong>
                    <span>{p.title}</span>
                    <small className="muted">
                      {p.assetCode}
                      {p.dueOn && ` · 예정 ${p.dueOn}`}
                    </small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">주기가 된 계획이 없습니다.</p>
            )}
          </section>
          <section>
            <h3>부족한 예비품</h3>
            {data.shortParts.length ? (
              <ul className="spc-trend">
                {data.shortParts.map((p) => (
                  <li key={p.id}>
                    <strong>{p.code}</strong>
                    <span>
                      {qty(p.qtyOnHand)} / {qty(p.safetyStock)} {p.unit}
                    </span>
                    <Badge tone="issue">부족</Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">
                부족한 예비품이 없습니다. WMS 품목을 잇지 않은 예비품은 재고를
                모르므로 여기 나오지 않습니다.
              </p>
            )}
          </section>
        </>
      )}
    </>
  );
}
