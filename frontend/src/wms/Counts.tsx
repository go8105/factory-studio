// W-14 재고 실사 · W-15 재고 마감 (DSN-13 F35·F39, Q6).
// 실사를 시작하면 그 시점 장부 수량을 굳히고, 그 위치의 재고 이동을 막는다(실사 잠금).
// 차이 = 실사 − 장부는 저장하지 않고 조회할 때 계산한다. 차이가 있는 줄만 CYCLE_COUNT 전표로 조정한다.
// 마감한 달에는 재고 전표를 만들 수 없다. 마감 후 발견한 차이는 다음 달에 조정한다.
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useSession } from "../app/session";
import { api } from "../shared/api";
import {
  Badge,
  DataTable,
  DetailPanel,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  COUNT_STATUS_LABEL,
  num,
  time,
  useLists,
  WMS,
  type CountOrder,
  type CountStatus,
  type StockPeriod,
  type Warehouse,
} from "./common";

const LIMIT = 50;

const tone = (status: CountStatus) =>
  status === "ADJUSTED"
    ? "normal"
    : status === "CANCELLED"
      ? "issue"
      : "warning";

export function Counts() {
  const { session } = useSession();
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");
  const statusFilter = (params.get("status") as CountStatus | null) ?? "";

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.set("page", "1");
    setParams(next);
  };

  const query = new URLSearchParams({
    page: String(page),
    pageSize: String(LIMIT),
  });
  if (statusFilter) query.set("status", statusFilter);

  const { data, reload } = useLists<
    [Warehouse[], { rows: CountOrder[]; total: number }, StockPeriod[]]
  >(["/warehouses", `/count-orders?${query.toString()}`, "/stock-periods"]);

  const [selected, setSelected] = useState<CountOrder | null>(null);
  const [counted, setCounted] = useState<Record<number, string>>({});
  const [newWarehouse, setNewWarehouse] = useState("");
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<unknown>();

  useEffect(() => {
    if (!selected) return;
    setCounted(
      Object.fromEntries(
        selected.lines.map((l) => [l.id, l.countedQty ?? l.bookQty]),
      ),
    );
    setActionError(undefined);
  }, [selected?.id]);

  if (!data) return <Loading />;

  const warehouses = data[0] ?? [];
  const rows = data[1]?.rows ?? [];
  const total = data[1]?.total ?? 0;
  const periods = data[2] ?? [];

  async function send<T>(path: string, body: unknown): Promise<T | null> {
    setPending(true);
    setActionError(undefined);
    try {
      const res = await api<T>(`${WMS}${path}`, {
        method: "POST",
        csrf: session?.csrfToken,
        key: crypto.randomUUID(),
        body,
      });
      reload();
      return res.data;
    } catch (err) {
      setActionError(err);
      return null;
    } finally {
      setPending(false);
    }
  }

  const columns: Column<CountOrder>[] = [
    {
      key: "countNo",
      label: "실사 번호",
      render: (r) => <strong>{r.countNo}</strong>,
    },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={tone(r.status)}>{COUNT_STATUS_LABEL[r.status]}</Badge>
      ),
    },
    {
      key: "warehouseCode",
      label: "창고",
      render: (r) => `${r.warehouseCode} · ${r.warehouseName}`,
    },
    {
      key: "kind",
      label: "종류",
      render: (r) => (r.kind === "FULL" ? "전수" : "순환"),
    },
    {
      key: "lineCount",
      label: "진행",
      render: (r) => `${r.countedCount} / ${r.lineCount}`,
    },
    {
      key: "diffCount",
      label: "차이",
      render: (r) =>
        r.diffCount ? (
          <Badge tone="issue">{r.diffCount}건</Badge>
        ) : (
          <span className="muted">없음</span>
        ),
    },
    { key: "createdAt", label: "시작 일시", render: (r) => time(r.createdAt) },
    {
      key: "id",
      label: "작업",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          onClick={() => setSelected(r)}
        >
          상세
        </button>
      ),
    },
  ];

  return (
    <div className="wms-counts">
      <PageTitle
        id="W-14"
        title="W-14 재고 실사 · W-15 재고 마감"
        subtitle="실사를 시작하면 그 시점 장부 수량이 굳고 해당 위치의 재고 이동이 멈춥니다. 차이가 있는 줄만 조정 전표로 반영합니다."
      />

      <div
        className="filter-bar"
        style={{
          display: "flex",
          gap: "0.5rem",
          flexWrap: "wrap",
          marginBottom: "1rem",
        }}
      >
        <label>
          상태
          <select
            aria-label="상태 필터"
            value={statusFilter}
            onChange={(e) => setParam("status", e.target.value)}
          >
            <option value="">전체 상태</option>
            <option value="OPEN">실사 중</option>
            <option value="COUNTED">실사 완료</option>
            <option value="ADJUSTED">조정 완료</option>
            <option value="CANCELLED">취소</option>
          </select>
        </label>
        <label>
          새 실사 창고
          <select
            aria-label="새 실사 창고"
            value={newWarehouse}
            onChange={(e) => setNewWarehouse(e.target.value)}
          >
            <option value="">선택</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.code} · {w.name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={pending || !newWarehouse}
          onClick={async () => {
            const made = await send<CountOrder>("/count-orders", {
              warehouseId: Number(newWarehouse),
              kind: "FULL",
            });
            if (made) setSelected(made);
          }}
        >
          전수 실사 시작
        </button>
        <button type="button" className="secondary-button" onClick={reload}>
          새로고침
        </button>
      </div>

      <ErrorNotice error={!selected ? actionError : undefined} />

      <DataTable
        caption="재고 실사 목록"
        rows={rows}
        columns={columns}
        offset={(page - 1) * LIMIT}
        limit={LIMIT}
        total={total}
        onPage={(offset) =>
          setParam("page", String(Math.floor(offset / LIMIT) + 1))
        }
      />

      <section style={{ marginTop: "2rem" }}>
        <h2>W-15 재고 마감</h2>
        <p className="muted">
          마감한 달에는 재고 전표를 만들 수 없습니다. 마감 후 발견한 차이는 다음
          달에 조정합니다. 마감 순서는 WMS 재고 마감 → ERP 원가 → ERP 회계
          마감입니다.
        </p>
        <table aria-label="재고 월 마감">
          <thead>
            <tr>
              <th>월</th>
              <th>전표</th>
              <th>상태</th>
              <th>마감 일시</th>
              <th>작업</th>
            </tr>
          </thead>
          <tbody>
            {periods.map((p) => (
              <tr key={p.periodMonth}>
                <td>{p.periodMonth}</td>
                <td>{p.documentCount}건</td>
                <td>
                  <Badge tone={p.status === "closed" ? "normal" : "warning"}>
                    {p.status === "closed" ? "마감" : "열림"}
                  </Badge>
                </td>
                <td>{p.closedAt ? time(p.closedAt) : "-"}</td>
                <td>
                  <button
                    type="button"
                    className="link-button"
                    disabled={pending}
                    onClick={() =>
                      send(
                        p.status === "closed"
                          ? "/stock-periods/reopen"
                          : "/stock-periods/close",
                        { periodMonth: p.periodMonth },
                      )
                    }
                  >
                    {p.status === "closed" ? "마감 해제" : "마감"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {selected && (
        <DetailPanel
          title={selected.countNo}
          onClose={() => setSelected(null)}
          wide
        >
          <ErrorNotice error={actionError} />
          <div style={{ display: "grid", gap: "0.75rem" }}>
            <div>
              <strong>상태: </strong>
              <Badge tone={tone(selected.status)}>
                {COUNT_STATUS_LABEL[selected.status]}
              </Badge>
            </div>
            <div>
              <strong>창고: </strong>
              {selected.warehouseCode} · {selected.warehouseName}
            </div>
            <div>
              <strong>장부 기준 시각: </strong>
              {time(selected.snapshotAt)}
            </div>

            <div className="table-scroll">
              <table aria-label="실사 명세">
                <thead>
                  <tr>
                    <th>위치</th>
                    <th>품목</th>
                    <th>LOT</th>
                    <th>장부</th>
                    <th>실사</th>
                    <th>차이</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.lines.map((l) => (
                    <tr key={l.id}>
                      <td>
                        {l.locationCode}{" "}
                        <span className="muted">{l.locationName}</span>
                      </td>
                      <td>
                        {l.itemCode}{" "}
                        <span className="muted">· {l.itemName}</span>
                      </td>
                      <td>{l.lotNo ?? <span className="muted">-</span>}</td>
                      <td>
                        {num(l.bookQty)} {l.baseUnit}
                      </td>
                      <td>
                        {selected.status === "OPEN" ||
                        selected.status === "COUNTED" ? (
                          <input
                            aria-label={`${l.itemCode} 실사 수량`}
                            value={counted[l.id] ?? ""}
                            inputMode="decimal"
                            onChange={(e) =>
                              setCounted((m) => ({
                                ...m,
                                [l.id]: e.target.value,
                              }))
                            }
                          />
                        ) : (
                          (l.countedQty && num(l.countedQty)) || "-"
                        )}
                      </td>
                      <td>
                        {l.diffQty === null ? (
                          <span className="muted">-</span>
                        ) : Number(l.diffQty) === 0 ? (
                          <span className="muted">0</span>
                        ) : (
                          <Badge tone="issue">{num(l.diffQty)}</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {selected.status === "ADJUSTED" && (
              <div>
                <strong>조정 전표: </strong>
                {selected.stockDocumentId ? (
                  <Link to={`/wms/documents?open=${selected.stockDocumentId}`}>
                    {selected.stockDocumentNo ?? "전표 보기"}
                  </Link>
                ) : (
                  <span className="muted">
                    차이가 없어 전표를 만들지 않았습니다
                  </span>
                )}
              </div>
            )}

            {(selected.status === "OPEN" || selected.status === "COUNTED") && (
              <>
                <button
                  type="button"
                  disabled={pending}
                  onClick={async () => {
                    const next = await send<CountOrder>(
                      `/count-orders/${selected.id}/count`,
                      {
                        lines: selected.lines.map((l) => ({
                          lineId: l.id,
                          countedQty: counted[l.id] ?? l.bookQty,
                        })),
                      },
                    );
                    if (next) setSelected(next);
                  }}
                >
                  실사 수량 저장
                </button>
                {selected.status === "COUNTED" && (
                  <button
                    type="button"
                    disabled={pending}
                    onClick={async () => {
                      const next = await send<CountOrder>(
                        `/count-orders/${selected.id}/adjust`,
                        {},
                      );
                      if (next) setSelected(next);
                    }}
                  >
                    차이 조정 확정
                  </button>
                )}
                <button
                  type="button"
                  className="secondary-button"
                  disabled={pending}
                  onClick={async () => {
                    const next = await send<CountOrder>(
                      `/count-orders/${selected.id}/cancel`,
                      {},
                    );
                    if (next) setSelected(next);
                  }}
                >
                  실사 취소
                </button>
              </>
            )}
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
