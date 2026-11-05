// F-21 온실가스 명세서 — 연간 Scope 1·2, 확정하고 인쇄한다 (DSN-15 F35·Q6)
// Scope 1 = 연료, Scope 2 = 전력·열. 합계는 줄의 합이다.
import { useEffect, useState } from "react";
import { api } from "../shared/api";
import { Badge, ErrorNotice, Loading, PageTitle } from "../shared/components";
import { useApiLists, useApiSend } from "../shared/hooks";

type Status = "draft" | "confirmed" | "superseded";
const STATUS_LABEL: Record<Status, string> = {
  draft: "초안",
  confirmed: "확정",
  superseded: "대체됨",
};
type Inventory = {
  id: number;
  inventoryYear: string;
  version: number;
  status: Status;
  scope1Tco2e: string;
  scope2Tco2e: string;
  confirmedAt: string | null;
};
type Line = {
  scope: number;
  equipmentCode: string | null;
  equipmentName: string | null;
  sourceCode: string;
  sourceName: string;
  activityQty: string;
  unit: string;
  factorValue: string;
  emissionTco2e: string;
};
type Detail = Inventory & {
  lines: Line[];
  coverage?: { days: number; expectedDays: number; partial: boolean };
};

const num = (v: string, digits = 2) =>
  Number(v).toLocaleString("ko-KR", { maximumFractionDigits: digits });

export function GhgInventories() {
  const lists = useApiLists<[Inventory[]]>("/api/v1/fems", [
    "/ghg-inventories",
  ]);
  const { send, pending, error } = useApiSend("/api/v1/fems", lists.reload);
  const [year, setYear] = useState("");
  const [picked, setPicked] = useState<number>();
  const [detail, setDetail] = useState<Detail>();
  const [done, setDone] = useState<string>();
  const [version, setVersion] = useState(0);

  const [inventories] = lists.data ?? [];
  const shownId = picked ?? inventories?.[0]?.id;

  useEffect(() => {
    if (!shownId) return;
    const controller = new AbortController();
    api<Detail>(`/api/v1/fems/ghg-inventories/${shownId}`, {
      signal: controller.signal,
    })
      .then((r) => !controller.signal.aborted && setDetail(r.data))
      .catch(() => undefined);
    return () => controller.abort();
  }, [shownId, version, inventories?.length]);

  async function create() {
    const r = await send<Detail>("/ghg-inventories", "POST", { year });
    if (r?.id) {
      setPicked(r.id);
      setVersion((n) => n + 1);
      setDone(
        `${r.inventoryYear} 초안을 만들었습니다.` +
          (r.coverage?.partial
            ? ` 계측은 ${r.coverage.days}일분이라 연 전체가 아닙니다.`
            : ""),
      );
    }
  }
  async function confirm(row: Inventory) {
    const r = await send<Inventory>(
      `/ghg-inventories/${row.id}/confirm`,
      "POST",
    );
    if (r?.id) {
      setVersion((n) => n + 1);
      setDone(`${row.inventoryYear} v${row.version}을(를) 확정했습니다.`);
    }
  }

  const total = detail
    ? Number(detail.scope1Tco2e) + Number(detail.scope2Tco2e)
    : 0;

  return (
    <>
      <PageTitle
        id="F-21"
        title="온실가스 명세서"
        subtitle="연간 Scope 1·2 배출량을 설비·에너지원별로 확정하고 인쇄합니다"
        help="fems/f-21"
        actions={
          detail && (
            <button type="button" onClick={() => window.print()}>
              명세서 인쇄
            </button>
          )
        }
      />
      <ErrorNotice error={error} />
      {done && <p role="status">{done}</p>}
      <div className="filter-bar">
        <label>
          연도
          <input
            inputMode="numeric"
            maxLength={4}
            placeholder="YYYY"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={pending || !/^[0-9]{4}$/.test(year)}
          onClick={() => void create()}
        >
          초안 만들기
        </button>
      </div>
      <p className="muted" role="note">
        <strong>Scope 1은 연료, Scope 2는 전력·열</strong>입니다. 활동량 × 그
        연도의 배출 계수이고, 합계는 줄의 합입니다. 설비에 배분되지 않은
        나머지는
        <strong> 사업장 공용</strong> 줄로 넣어 사업장 합계와 맞춥니다. 확정한
        명세서는 바꾸지 않고, 재산정은 새 버전입니다.
      </p>
      {!inventories ? (
        !lists.error && <Loading delay={300} />
      ) : inventories.length === 0 ? (
        <p className="muted">명세서가 없습니다. 연도를 적어 초안을 만드세요.</p>
      ) : (
        <>
          <div className="table-scroll">
            <table aria-label="명세서 목록">
              <thead>
                <tr>
                  <th scope="col">연도</th>
                  <th scope="col">버전</th>
                  <th scope="col">상태</th>
                  <th scope="col" className="num">
                    Scope 1
                  </th>
                  <th scope="col" className="num">
                    Scope 2
                  </th>
                  <th scope="col">관리</th>
                </tr>
              </thead>
              <tbody>
                {inventories.map((r) => (
                  <tr key={r.id}>
                    <th scope="row">{r.inventoryYear}</th>
                    <td>v{r.version}</td>
                    <td>
                      <Badge
                        tone={r.status === "confirmed" ? "normal" : "warning"}
                      >
                        {STATUS_LABEL[r.status]}
                      </Badge>
                    </td>
                    <td className="num">{num(r.scope1Tco2e)}</td>
                    <td className="num">{num(r.scope2Tco2e)}</td>
                    <td>
                      <span className="row-actions">
                        <button
                          type="button"
                          className="link-button"
                          aria-pressed={shownId === r.id}
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
          {detail && (
            <section className="panel print-area" aria-label="명세서">
              <h2>
                {detail.inventoryYear} 온실가스 명세서 · v{detail.version}{" "}
                <Badge
                  tone={detail.status === "confirmed" ? "normal" : "warning"}
                >
                  {STATUS_LABEL[detail.status]}
                </Badge>
              </h2>
              {detail.coverage?.partial && (
                <p className="field-error" role="note">
                  계측이 {detail.coverage.days}일분뿐이라{" "}
                  <strong>연 전체가 아닙니다.</strong> 이 값을 연간 배출량으로
                  보고하면 안 됩니다.
                </p>
              )}
              <p>
                합계 {num(String(total))} tCO2e · Scope 1{" "}
                {num(detail.scope1Tco2e)} + Scope 2 {num(detail.scope2Tco2e)}
              </p>
              <div className="table-scroll">
                <table aria-label="배출 시설별">
                  <thead>
                    <tr>
                      <th scope="col">Scope</th>
                      <th scope="col">설비</th>
                      <th scope="col">에너지원</th>
                      <th scope="col" className="num">
                        활동량
                      </th>
                      <th scope="col" className="num">
                        계수
                      </th>
                      <th scope="col" className="num">
                        배출(tCO2e)
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.lines.map((l) => (
                      <tr key={`${l.scope}-${l.equipmentCode}-${l.sourceCode}`}>
                        <td>{l.scope}</td>
                        <td>
                          {l.equipmentCode
                            ? `${l.equipmentCode} ${l.equipmentName}`
                            : "사업장 공용"}
                        </td>
                        <td>
                          {l.sourceCode} {l.sourceName}
                        </td>
                        <td className="num">
                          {num(l.activityQty, 1)} {l.unit}
                        </td>
                        <td className="num">{Number(l.factorValue)}</td>
                        <td className="num">{num(l.emissionTco2e, 3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </>
  );
}
