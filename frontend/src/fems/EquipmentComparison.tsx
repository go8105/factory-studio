// F-17 설비 비교 — 같은 종류 설비끼리 원단위 순위 (DSN-15 F27)
// 저장하지 않는다. 종류가 다른 설비는 비교하지 않는다.
import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import { ErrorNotice, Loading, PageTitle } from "../shared/components";

type Row = {
  equipmentId: number;
  equipmentCode: string;
  equipmentName: string;
  energy: string;
  energyUnit: string;
  production: string | null;
  productionUnit: string | null;
  intensity: string | null;
  rank?: number;
};
type Group = { equipmentType: string; ranked: Row[]; unranked: Row[] };
type Comparison = { month: string | null; groups: Group[] };

const num = (v: string, digits = 3) =>
  Number(v).toLocaleString("ko-KR", { maximumFractionDigits: digits });

export function EquipmentComparison() {
  const { fail } = useSession();
  const [month, setMonth] = useState("");
  const [data, setData] = useState<Comparison>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setData(undefined);
    api<Comparison>(
      `/api/v1/fems/equipment-comparison${month ? `?month=${month}` : ""}`,
      { signal: controller.signal },
    )
      .then((r) => !controller.signal.aborted && setData(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [month, reload]);

  return (
    <>
      <PageTitle
        id="F-17"
        title="설비 비교"
        subtitle="같은 종류 설비끼리 원단위를 줄 세웁니다"
        help="fems/f-17"
        actions={
          <label>
            조회 월
            <input
              type="month"
              value={month || data?.month || ""}
              onChange={(e) => e.target.value && setMonth(e.target.value)}
            />
          </label>
        }
      />
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!data ? (
        !error && <Loading delay={300} />
      ) : data.groups.length === 0 ? (
        <p className="muted">이 달에 설비 배분이 없습니다.</p>
      ) : (
        <>
          <p className="muted" role="note">
            원단위 = 설비 배분 에너지 ÷ 그 설비 생산량.{" "}
            <strong>종류가 다른 설비는 비교하지 않습니다</strong> — 사출기와
            검사기의 원단위를 나란히 두면 뜻이 없습니다. 생산량이 없는 설비는
            0위가 아니라 순위 밖입니다.
          </p>
          {data.groups.map((group) => (
            <section
              className="panel"
              key={group.equipmentType}
              aria-label={`${group.equipmentType} 비교`}
            >
              <h2>
                {group.equipmentType} · {group.ranked.length}대
              </h2>
              {group.ranked.length === 0 ? (
                <p className="muted">
                  이 종류에는 원단위를 낼 수 있는 설비가 없습니다.
                </p>
              ) : (
                <div className="table-scroll">
                  <table aria-label={`${group.equipmentType} 원단위 순위`}>
                    <thead>
                      <tr>
                        <th scope="col">순위</th>
                        <th scope="col">설비</th>
                        <th scope="col" className="num">
                          에너지
                        </th>
                        <th scope="col" className="num">
                          생산량
                        </th>
                        <th scope="col" className="num">
                          원단위
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.ranked.map((row) => (
                        <tr key={row.equipmentId}>
                          <th scope="row">{row.rank}</th>
                          <td>
                            {row.equipmentCode} {row.equipmentName}
                          </td>
                          <td className="num">
                            {num(row.energy, 1)} {row.energyUnit}
                          </td>
                          <td className="num">
                            {row.production ? num(row.production, 1) : "—"}{" "}
                            {row.productionUnit}
                          </td>
                          <td className="num">{num(row.intensity!)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {group.unranked.length > 0 && (
                <p className="muted">
                  생산량이 없어 비교하지 못한 설비:{" "}
                  {group.unranked.map((r) => r.equipmentCode).join(", ")}
                </p>
              )}
            </section>
          ))}
        </>
      )}
    </>
  );
}
