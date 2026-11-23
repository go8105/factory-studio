// E-33 일계표·월계표·시산표 (DSN-11 F53·F54).
// 계산은 하나다. 범위만 바꾼다 — 하루면 일계표, 한 달이면 월계표, 기간이면 합계잔액시산표.
import { useState } from "react";
import {
  DataTable,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
import { ModuleOff, moduleOff, Period, today, useLists, won } from "./common";
import { sided } from "./Books";

type Row = {
  accountId: number;
  accountCode: string;
  accountName: string;
  accountClass: string;
  opening: string;
  debit: string;
  credit: string;
  debitBalance: string;
  creditBalance: string;
};
type Body = {
  rows: Row[];
  totals: Record<string, string>;
  balanced: boolean;
};
const MODES: [string, string, () => { from: string; to: string }][] = [
  ["day", "일계표", () => ({ from: today(), to: today() })],
  [
    "month",
    "월계표",
    () => ({ from: today().slice(0, 7) + "-01", to: today() }),
  ],
  [
    "range",
    "합계잔액시산표",
    () => ({ from: today().slice(0, 4) + "-01-01", to: today() }),
  ],
];

export function TrialBalance() {
  const [mode, setMode] = useState("month");
  const [period, setPeriod] = useState(MODES[1][2]());
  const { data, error, reload } = useLists<[Body]>([
    `/trial-balance?date_from=${period.from}&date_to=${period.to}`,
  ]);
  if (moduleOff(error)) return <ModuleOff />;
  const body = data?.[0] as unknown as Body | undefined;
  const label = MODES.find(([key]) => key === mode)?.[1] ?? "시산표";
  return (
    <div className="page-fill">
      <PageTitle
        id="E-33"
        title="일계표·월계표·시산표"
        help="erp/e-33"
        actions={
          <Period
            from={period.from}
            to={period.to}
            set={(patch) => {
              setPeriod({ ...period, ...patch });
              setMode("range");
            }}
          />
        }
      />
      <p className="muted" role="note">
        같은 계산을 범위만 바꿔 봅니다. 확정 전표와 기초 잔액에서 그때그때
        셉니다. 차변 합과 대변 합이 다르면 장부가 아니라 전표가 깨진 것이라
        경고를 띄웁니다.
      </p>
      <ErrorNotice error={error} retry={reload} />
      {!body ? (
        <Loading />
      ) : (
        <>
          {!body.balanced && (
            <p className="notice" role="alert">
              차변 합과 대변 합이 맞지 않습니다. 전표를 확인하세요.
            </p>
          )}
          <DataTable
            rows={body.rows.map((r) => ({ ...r, id: r.accountId }))}
            leading={
              <span className="row-actions">
                {MODES.map(([key, name, range]) => (
                  <button
                    key={key}
                    type="button"
                    className="link-button"
                    aria-pressed={mode === key}
                    onClick={() => {
                      setMode(key);
                      setPeriod(range());
                    }}
                  >
                    {name}
                  </button>
                ))}
              </span>
            }
            columns={[
              {
                key: "accountCode",
                label: "계정",
                render: (r) => `${r.accountCode} ${r.accountName}`,
              },
              {
                key: "opening",
                label: "기초",
                render: (r) => sided(r.opening),
              },
              { key: "debit", label: "차변", render: (r) => won(r.debit) },
              { key: "credit", label: "대변", render: (r) => won(r.credit) },
              {
                key: "debitBalance",
                label: "차변 잔액",
                render: (r) =>
                  Number(r.debitBalance) ? won(r.debitBalance) : "—",
              },
              {
                key: "creditBalance",
                label: "대변 잔액",
                render: (r) =>
                  Number(r.creditBalance) ? won(r.creditBalance) : "—",
              },
            ]}
            caption={label}
            offset={0}
            total={body.rows.length}
            limit={body.rows.length || 1}
            onPage={() => undefined}
            empty="이 기간에 움직인 계정이 없습니다."
          />
          <div className="section-heading">
            <h2>{label} 합계</h2>
            <strong>
              차변 {won(body.totals.debit)} · 대변 {won(body.totals.credit)} ·
              차변 잔액 {won(body.totals.debitBalance)} · 대변 잔액{" "}
              {won(body.totals.creditBalance)}
            </strong>
          </div>
        </>
      )}
    </div>
  );
}
