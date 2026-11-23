// E-32 원장(총계정·계정별·거래처) (DSN-11 F51·F52).
// 왼쪽은 잔액이 움직인 계정·거래처, 오른쪽은 고른 하나의 명세다. 저장하는 것이 없다.
import { useState } from "react";
import {
  Badge,
  DataTable,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
import {
  ModuleOff,
  moduleOff,
  monthsAgo,
  Period,
  today,
  useLists,
  won,
} from "./common";

type Balance = {
  id: number;
  accountId?: number;
  partnerId?: number;
  accountCode?: string;
  accountName?: string;
  partnerCode?: string;
  partnerName?: string;
  opening: string;
  debit: string;
  credit: string;
  closing: string;
};
type Line = {
  id: number;
  entryDate: string;
  entryNo: string;
  status: string;
  description: string | null;
  accountCode: string;
  accountName: string;
  partnerCode: string | null;
  side: "DEBIT" | "CREDIT";
  amount: string;
  memo: string | null;
  balance: string;
};
type Ledger = {
  opening: string;
  closing: string;
  debit: string;
  credit: string;
  lines: Line[];
};

// 잔액은 차변 양수로 온다. 사람에게는 방향을 붙여 보여 준다.
export const sided = (value: string) => {
  const amount = Number(value);
  if (!amount) return "0원";
  return `${Math.abs(amount).toLocaleString()}원 (${amount > 0 ? "차" : "대"})`;
};

export function Books() {
  const [kind, setKind] = useState<"account" | "partner">("account");
  const [period, setPeriod] = useState({ from: monthsAgo(3), to: today() });
  const [picked, setPicked] = useState<number>();
  const range = `date_from=${period.from}&date_to=${period.to}`;
  const { data, error, reload } = useLists<[{ rows: Balance[] }, Balance[]]>([
    `/trial-balance?${range}`,
    `/ledger/partners?${range}`,
  ]);
  const detail = useLists<[Ledger]>(
    picked
      ? [
          `/ledger?${range}&${kind === "account" ? "account_id" : "partner_id"}=${picked}`,
        ]
      : [],
  );
  if (moduleOff(error)) return <ModuleOff />;
  const accounts = (data?.[0]?.rows ?? []).map((r) => ({
    ...r,
    id: r.accountId!,
  }));
  const partners = (data?.[1] ?? []).map((r) => ({ ...r, id: r.partnerId! }));
  const rows = kind === "account" ? accounts : partners;
  const ledger = detail.data?.[0];

  function choose(next: "account" | "partner") {
    setKind(next);
    setPicked(undefined);
  }

  return (
    <div className="page-fill">
      <PageTitle
        id="E-32"
        title="원장"
        help="erp/e-32"
        actions={
          <Period
            from={period.from}
            to={period.to}
            set={(patch) => {
              setPeriod({ ...period, ...patch });
              setPicked(undefined);
            }}
          />
        }
      />
      <p className="muted" role="note">
        확정한 전표와 기초 잔액에서 그때그때 셉니다. 역분개한 원 전표도 반대
        전표와 함께 남아 서로 상쇄됩니다. 기간 앞의 움직임은 회계연도 1월
        1일부터 셉니다 — 그 앞은 기초 잔액(E-35)이 책임집니다.
      </p>
      <ErrorNotice error={error} retry={reload} />
      <ErrorNotice error={detail.error} retry={detail.reload} />
      {!data ? (
        <Loading />
      ) : (
        <div className="split-view fill">
          <section className="section-block fill">
            <DataTable
              rows={rows}
              leading={
                <span className="row-actions">
                  <button
                    type="button"
                    className="link-button"
                    aria-pressed={kind === "account"}
                    onClick={() => choose("account")}
                  >
                    계정별
                  </button>
                  <button
                    type="button"
                    className="link-button"
                    aria-pressed={kind === "partner"}
                    onClick={() => choose("partner")}
                  >
                    거래처별
                  </button>
                </span>
              }
              columns={[
                {
                  key: "accountCode",
                  label: kind === "account" ? "계정" : "거래처",
                  render: (r) => (
                    <button
                      type="button"
                      className="link-button"
                      aria-pressed={r.id === picked}
                      onClick={() => setPicked(r.id)}
                    >
                      {kind === "account"
                        ? `${r.accountCode} ${r.accountName}`
                        : `${r.partnerCode} ${r.partnerName}`}
                    </button>
                  ),
                },
                {
                  key: "opening",
                  label: "기초",
                  render: (r) => sided(r.opening),
                },
                { key: "debit", label: "차변", render: (r) => won(r.debit) },
                { key: "credit", label: "대변", render: (r) => won(r.credit) },
                {
                  key: "closing",
                  label: "기말",
                  render: (r) => sided(r.closing),
                },
              ]}
              caption={kind === "account" ? "계정별 잔액" : "거래처별 잔액"}
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty="이 기간에 움직인 잔액이 없습니다."
            />
          </section>
          <section className="section-block fill">
            {!picked ? (
              <p className="muted">왼쪽에서 하나를 고르면 명세를 봅니다.</p>
            ) : !ledger ? (
              <Loading />
            ) : (
              <>
                <div className="section-heading">
                  <h2>명세</h2>
                  <strong>
                    기초 {sided(ledger.opening)} → 기말 {sided(ledger.closing)}
                  </strong>
                </div>
                <DataTable
                  rows={ledger.lines}
                  columns={[
                    { key: "entryDate", label: "일자" },
                    {
                      key: "entryNo",
                      label: "전표",
                      render: (r) => (
                        <>
                          {r.entryNo}
                          {r.status === "reversed" && (
                            <Badge tone="warning">역분개됨</Badge>
                          )}
                        </>
                      ),
                    },
                    {
                      key: "accountCode",
                      label: "상대",
                      render: (r) =>
                        kind === "account"
                          ? (r.partnerCode ?? "—")
                          : `${r.accountCode} ${r.accountName}`,
                    },
                    {
                      key: "amount",
                      label: "차변",
                      render: (r) => (r.side === "DEBIT" ? won(r.amount) : "—"),
                    },
                    {
                      key: "side",
                      label: "대변",
                      render: (r) =>
                        r.side === "CREDIT" ? won(r.amount) : "—",
                    },
                    {
                      key: "balance",
                      label: "잔액",
                      render: (r) => sided(r.balance),
                    },
                    { key: "description", label: "적요", wrap: true },
                  ]}
                  caption="원장 명세"
                  offset={0}
                  total={ledger.lines.length}
                  limit={ledger.lines.length || 1}
                  onPage={() => undefined}
                  empty="이 기간에 움직임이 없습니다. 기초 잔액만 있습니다."
                />
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
