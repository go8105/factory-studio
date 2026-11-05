// S-10 층별 비교 — 설비·LOT별로 부분군을 갈라 평균과 능력을 견준다 (UI-02 L 패턴, 조회 전용, DSN-17 Q6 F45).
// 전체로 보면 괜찮은데 어느 설비만 치우쳐 있는 경우를 찾는다. 작업자 축은 MES에 정보가 없어 없다.
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  CharacteristicSelect,
  JUDGEMENT_LABEL,
  JUDGEMENT_TONE,
  ModuleOff,
  moduleOff,
  num,
  spec,
  useCharacteristic,
  useGet,
  type Characteristic,
  type Stratum,
  type StratumBy,
} from "./common";

type StrataData = {
  characteristic: Characteristic;
  by: StratumBy;
  minimum: number;
  overallMean: string | null;
  groups: Stratum[];
};

const monthAgo = () =>
  new Date(Date.now() - 60 * 86_400_000).toISOString().slice(0, 10);

export function Strata() {
  const list = useGet<Characteristic[]>("/characteristics");
  const { current, select, query } = useCharacteristic(list.data);
  const [by, setBy] = useState<StratumBy>("equipment");
  const [from, setFrom] = useState(monthAgo());
  const [to, setTo] = useState("");
  const [applied, setApplied] = useState({ from: monthAgo(), to: "" });
  const data = useGet<StrataData>(
    current
      ? `/characteristics/${current.id}/strata?by=${by}&from=${applied.from}${applied.to ? `&to=${applied.to}` : ""}`
      : null,
  );
  if (moduleOff(list.error) || moduleOff(data.error)) return <ModuleOff />;
  const digits = (current?.decimals ?? 3) + 1;
  const columns: Column<Stratum>[] = [
    { key: "group", label: by === "equipment" ? "설비" : "LOT" },
    { key: "subgroupCount", label: "부분군" },
    {
      key: "mean",
      label: "평균 X̄",
      render: (g) => num(g.mean, digits),
    },
    {
      key: "shift",
      label: "전체 평균과의 차이",
      render: (g) =>
        g.shift == null
          ? "—"
          : `${Number(g.shift) > 0 ? "+" : ""}${num(g.shift, digits)}`,
    },
    {
      key: "cpk",
      label: "Cpk",
      render: (g) =>
        g.cpk == null ? (
          <span className="muted">
            부분군 {data.data?.minimum ?? 20}개 미만 — 계산 안 함
          </span>
        ) : (
          <>
            {num(g.cpk, 2)}{" "}
            {g.judgement && (
              <Badge tone={JUDGEMENT_TONE[g.judgement]}>
                {JUDGEMENT_LABEL[g.judgement]}
              </Badge>
            )}
          </>
        ),
    },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="S-10"
        title="층별 비교"
        subtitle="설비·LOT별로 갈라 평균과 능력을 견줍니다"
        help="spc/s-10"
      />
      <ErrorNotice
        error={list.error ?? data.error}
        retry={() => data.reload()}
      />
      {!list.data ? (
        !list.error && <Loading />
      ) : !list.data.length ? (
        <EmptyState
          reason="관리 특성이 없습니다."
          to="/spc/characteristics"
          action="관리 특성 등록"
        />
      ) : (
        <>
          <form
            className="filter-bar"
            onSubmit={(e) => {
              e.preventDefault();
              setApplied({ from, to });
            }}
          >
            <CharacteristicSelect
              list={list.data}
              value={current?.id}
              onChange={select}
            />
            <label>
              기준
              <select
                value={by}
                onChange={(e) => setBy(e.target.value as StratumBy)}
              >
                <option value="equipment">설비별</option>
                <option value="lot">LOT별</option>
              </select>
            </label>
            <label>
              시작
              <input
                type="date"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
              />
            </label>
            <label>
              종료
              <input
                type="date"
                value={to}
                onChange={(e) => setTo(e.target.value)}
              />
            </label>
            <button type="submit">조회</button>
            <Link to={`/spc/capability${query}`}>공정능력 →</Link>
          </form>
          {!data.data ? (
            !data.error && <Loading />
          ) : (
            <>
              <p className="muted">
                규격 {spec(data.data.characteristic)}
                {data.data.overallMean != null &&
                  ` · 전체 평균 ${num(data.data.overallMean, digits)}`}
              </p>
              <DataTable
                rows={data.data.groups}
                columns={columns}
                caption={by === "equipment" ? "설비별 비교" : "LOT별 비교"}
                offset={0}
                total={data.data.groups.length}
                limit={data.data.groups.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="이 기간에 유효 부분군이 없습니다."
                    to={`/spc/measure${query}`}
                    action="측정 입력"
                  />
                }
              />
            </>
          )}
        </>
      )}
    </div>
  );
}
