// E-09 매출채권 현황 — 잔액·상태는 서버가 조회 때 계산, 행을 펼치면 소명 이력 (FS-019e)
import { Fragment, useState } from "react";
import {
  Badge,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
import {
  customers,
  labels,
  ModuleOff,
  moduleOff,
  PARTNERS,
  useLists,
  won,
  type Partner,
} from "./common";

export type Application = {
  id: number;
  receiptId: number;
  receivableId: number;
  amount: string;
  appliedAt: string;
  receiptNo: string;
  shipmentNo: string;
};
export type Receivable = {
  id: number;
  salesRecordId: number;
  partnerId: number;
  amount: string;
  appliedAmount: string;
  balance: string;
  status: "OPEN" | "PARTIAL" | "CLOSED";
  dueDate: string | null;
  recognizedAt: string;
  shipmentNo: string;
  applications: Application[];
};
export const RV_STATUS: Record<
  Receivable["status"],
  [string, "normal" | "warning" | "issue"]
> = {
  OPEN: ["미회수", "issue"],
  PARTIAL: ["일부회수", "warning"],
  CLOSED: ["회수완료", "normal"],
};
const sum = (rows: Receivable[], key: "amount" | "appliedAmount" | "balance") =>
  String(rows.reduce((total, r) => total + Number(r[key]), 0));

export function Receivables() {
  const { data, error, reload } = useLists<[Receivable[], Partner[]]>([
    "/receivables",
    PARTNERS,
  ]);
  const [partnerId, setPartnerId] = useState(0);
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<number>();

  if (moduleOff(error)) return <ModuleOff />;
  const [all, partners] = data ?? [undefined, []];
  const name = labels(partners, []);
  const rows = (all ?? []).filter(
    (r) =>
      (!partnerId || r.partnerId === partnerId) &&
      (!status || r.status === status),
  );

  return (
    <>
      <PageTitle
        id="E-09"
        title="매출채권 현황"
        subtitle="매출채권의 원금·소명액·잔액과 회수 상태를 봅니다"
        help="erp/e-09"
      />
      <p className="muted">
        잔액과 상태는 저장하지 않고 조회할 때 원금 − 소명액으로 계산합니다.
        취소된 매출의 채권은 빠집니다. 만기 기준이 없는 채권이 있어
        연령분석(aging)은 이번 범위에서 제공하지 않습니다.
      </p>
      <ErrorNotice error={error} retry={reload} />
      {!all ? (
        !error && <Loading />
      ) : (
        <>
          <div className="filter-bar">
            <label>
              거래처
              <select
                value={partnerId || ""}
                onChange={(e) => setPartnerId(Number(e.target.value))}
              >
                <option value="">전체</option>
                {customers(partners).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.partnerCode} {p.partnerName}
                  </option>
                ))}
              </select>
            </label>
            <label>
              상태
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                <option value="">전체</option>
                {Object.entries(RV_STATUS).map(([key, [label]]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {rows.length === 0 ? (
            <EmptyState
              reason="조건에 맞는 매출채권이 없습니다. 출하를 확정하면 채권이 생깁니다."
              to="/erp/shipments"
              action="출하로"
            />
          ) : (
            <div className="table-scroll">
              <table>
                <caption>매출채권 목록</caption>
                <thead>
                  <tr>
                    <th scope="col">매출(출하번호)</th>
                    <th scope="col">관리</th>
                    <th scope="col">거래처</th>
                    <th scope="col">원금</th>
                    <th scope="col">소명액</th>
                    <th scope="col">잔액</th>
                    <th scope="col">상태</th>
                    <th scope="col">만기</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <Fragment key={r.id}>
                      <tr>
                        <td>{r.shipmentNo}</td>
                        <td>
                          <button
                            type="button"
                            className="link-button"
                            aria-expanded={open === r.id}
                            onClick={() =>
                              setOpen(open === r.id ? undefined : r.id)
                            }
                          >
                            소명 {r.applications.length}
                          </button>
                        </td>
                        <td>{name.partner(r.partnerId)}</td>
                        <td>{won(r.amount)}</td>
                        <td>{won(r.appliedAmount)}</td>
                        <td>{won(r.balance)}</td>
                        <td>
                          <Badge tone={RV_STATUS[r.status][1]}>
                            {RV_STATUS[r.status][0]}
                          </Badge>
                        </td>
                        <td>{r.dueDate ?? "미설정"}</td>
                      </tr>
                      {open === r.id && (
                        <tr>
                          <td colSpan={8}>
                            {r.applications.length ? (
                              <ul aria-label={`${r.shipmentNo} 소명 이력`}>
                                {r.applications.map((a) => (
                                  <li key={a.id}>
                                    {a.receiptNo} · {won(a.amount)} ·{" "}
                                    {new Date(a.appliedAt).toLocaleString()}
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <span className="muted">
                                소명 이력이 없습니다.
                              </span>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row">합계</th>
                    <td />
                    <td />
                    <td>{won(sum(rows, "amount"))}</td>
                    <td>{won(sum(rows, "appliedAmount"))}</td>
                    <td>{won(sum(rows, "balance"))}</td>
                    <td />
                    <td />
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}
