// E-09 매출채권 현황 · E-12 매입채무 현황 — 잔액·상태는 서버가 조회 때 계산, 행을 펼치면 소명 이력
import { Fragment, useState } from "react";
import {
  Badge,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
import {
  labels,
  ModuleOff,
  moduleOff,
  PARTNERS,
  useLists,
  won,
  type Partner,
} from "./common";
import { RECEIVABLE, toOpen, type OpenItem, type Side } from "./settlement";

export const RV_STATUS: Record<
  OpenItem["status"],
  [string, "normal" | "warning" | "issue"]
> = {
  OPEN: ["미회수", "issue"],
  PARTIAL: ["일부회수", "warning"],
  CLOSED: ["회수완료", "normal"],
};
const PV_STATUS: typeof RV_STATUS = {
  OPEN: ["미지급", "issue"],
  PARTIAL: ["일부지급", "warning"],
  CLOSED: ["지급완료", "normal"],
};
const sum = (rows: OpenItem[], key: "amount" | "appliedAmount" | "balance") =>
  String(rows.reduce((total, r) => total + Number(r[key]), 0));

export function Receivables({ side = RECEIVABLE }: { side?: Side }) {
  const receivable = side === RECEIVABLE;
  const STATUS = receivable ? RV_STATUS : PV_STATUS;
  const { data, error, reload } = useLists<
    [Record<string, unknown>[], Partner[]]
  >([side.openPath, PARTNERS]);
  const [partnerId, setPartnerId] = useState(0);
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<number>();

  if (moduleOff(error)) return <ModuleOff />;
  const all = data?.[0].map(toOpen(side));
  const partners = data?.[1] ?? [];
  const name = labels(partners, []);
  const rows = (all ?? []).filter(
    (r) =>
      (!partnerId || r.partnerId === partnerId) &&
      (!status || r.status === status),
  );
  const title = receivable ? "매출채권 현황" : "매입채무 현황";

  return (
    <>
      <PageTitle
        id={receivable ? "E-09" : "E-12"}
        title={title}
        subtitle={`${side.source}${side.item}의 원금·소명액·잔액과 ${receivable ? "회수" : "지급"} 상태를 봅니다`}
        help={receivable ? "erp/e-09" : "erp/e-12"}
      />
      <p className="muted">
        잔액과 상태는 저장하지 않고 조회할 때 원금 − 소명액으로 계산합니다.
        취소된 {side.source}의 {side.item}은 빠집니다. 만기 기준이 없는{" "}
        {side.item}이 있어 연령분석(aging)은 이번 범위에서 제공하지 않습니다.
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
                {partners
                  .filter((p) => p.partnerKind === side.partnerKind)
                  .map((p) => (
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
                {Object.entries(STATUS).map(([key, [label]]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {rows.length === 0 ? (
            <EmptyState
              reason={`조건에 맞는 ${side.item}이 없습니다. ${side.source}을 확정하면 ${side.item}이 생깁니다.`}
              to={side.sourcePath}
              action={`${side.source}로`}
            />
          ) : (
            <div className="table-scroll">
              <table>
                <caption>{title.replace("현황", "목록")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{side.doc}</th>
                    <th scope="col">관리</th>
                    <th scope="col">거래처</th>
                    <th scope="col" className="num">
                      원금
                    </th>
                    <th scope="col" className="num">
                      소명액
                    </th>
                    <th scope="col" className="num">
                      잔액
                    </th>
                    <th scope="col">상태</th>
                    <th scope="col">만기</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <Fragment key={r.id}>
                      <tr>
                        <td>{r.doc}</td>
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
                        <td className="num">{won(r.amount)}</td>
                        <td className="num">{won(r.appliedAmount)}</td>
                        <td className="num">{won(r.balance)}</td>
                        <td>
                          <Badge tone={STATUS[r.status][1]}>
                            {STATUS[r.status][0]}
                          </Badge>
                        </td>
                        <td>{r.dueDate ?? "미설정"}</td>
                      </tr>
                      {open === r.id && (
                        <tr>
                          <td colSpan={8}>
                            {r.applications.length ? (
                              <ul aria-label={`${r.doc} 소명 이력`}>
                                {r.applications.map((a) => (
                                  <li key={a.id}>
                                    {a.moneyNo} · {won(a.amount)} ·{" "}
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
                    <td className="num">{won(sum(rows, "amount"))}</td>
                    <td className="num">{won(sum(rows, "appliedAmount"))}</td>
                    <td className="num">{won(sum(rows, "balance"))}</td>
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
