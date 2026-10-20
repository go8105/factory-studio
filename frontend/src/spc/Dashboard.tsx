// S-01 SPC 대시보드 — KPI 4개 + 특성 카드(최근 20점 X̄·Cpk·미조치) (UI-02 D 패턴, F-01 기준).
import { Link } from "react-router-dom";
import { Badge, ErrorNotice, Loading, PageTitle } from "../shared/components";
import {
  JUDGEMENT_LABEL,
  JUDGEMENT_TONE,
  ModuleOff,
  moduleOff,
  num,
  spec,
  Spark,
  useGet,
  type Characteristic,
  type Judgement,
  type Limit,
} from "./common";

type Card = Characteristic & {
  recent: { measuredAt: string; xbar: string }[];
  limit: Limit | null;
  capability: { cpk: string | null; judgement: Judgement | null } | null;
};
type DashboardData = {
  characteristicCount: number;
  openSignals: number;
  openSignalCharacteristics: number;
  capability: Record<Judgement, number>;
  weekSubgroups: number;
  weekSpecViolations: number;
  cards: Card[];
};

function Tile({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <section className="stat-tile" aria-label={label}>
      <p>{label}</p>
      <strong>{value}</strong>
      <small>{note}</small>
    </section>
  );
}

export function Dashboard() {
  const { data, error, reload } = useGet<DashboardData>("/dashboard");
  if (moduleOff(error)) return <ModuleOff />;
  return (
    <>
      <PageTitle
        id="S-01"
        title="SPC 대시보드"
        subtitle="관리 특성별 최근 추이·미조치 이상·공정능력·규격 이탈"
        help="spc/s-01"
      />
      <ErrorNotice error={error} retry={() => reload()} />
      {!data ? (
        !error && <Loading delay={300} />
      ) : (
        <>
          <div className="kpi-grid">
            <Tile
              label="관리 특성"
              value={String(data.characteristicCount)}
              note="사용 중"
            />
            <Tile
              label="미조치 이상"
              value={`${data.openSignals}건`}
              note={`${data.openSignalCharacteristics}개 특성`}
            />
            <Tile
              label="공정능력"
              value={`충분 ${data.capability.CAPABLE}`}
              note={`주의 ${data.capability.MARGINAL} · 부족 ${data.capability.INCAPABLE} (Cpk 1.33·1.00 기준)`}
            />
            <Tile
              label="최근 7일 부분군"
              value={String(data.weekSubgroups)}
              note="유효 부분군"
            />
            <Tile
              label="최근 7일 규격 이탈"
              value={`${data.weekSpecViolations}건`}
              note="관리 이탈과 별개(개별 측정값)"
            />
          </div>
          <div className="spc-cards">
            {data.cards.map((c) => (
              <Link
                key={c.id}
                to={`/spc/chart?c=${c.id}`}
                className="spc-card"
                aria-label={`${c.itemCode} ${c.processCode} ${c.name} 관리도`}
              >
                <div className="spc-card-head">
                  <strong>
                    {c.itemCode} · {c.processCode} · {c.name}
                  </strong>
                  <span>
                    {c.openSignals > 0 && (
                      <Badge tone="issue">미조치 {c.openSignals}</Badge>
                    )}{" "}
                    {!c.limit ? (
                      <Badge tone="warning">한계 미게시</Badge>
                    ) : !c.capability?.judgement ? (
                      <Badge>표본 부족</Badge>
                    ) : (
                      <Badge tone={JUDGEMENT_TONE[c.capability.judgement]}>
                        Cpk {num(c.capability.cpk, 2)}{" "}
                        {JUDGEMENT_LABEL[c.capability.judgement]}
                      </Badge>
                    )}
                  </span>
                </div>
                <Spark
                  values={c.recent.map((r) => Number(r.xbar))}
                  limit={c.limit}
                />
                <small className="muted">
                  규격 {spec(c)} · 부분군 {c.subgroupCount} · 관리도 보기 →
                </small>
              </Link>
            ))}
          </div>
        </>
      )}
    </>
  );
}
