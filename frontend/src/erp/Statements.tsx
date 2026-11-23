// E-34 재무제표(재무상태표·손익계산서·제조원가명세서) (DSN-11 F55·F56).
// 같은 계정 집계 하나에서 셋을 본다. 저장하는 것이 없다.
import { useState } from "react";
import {
  DataTable,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
import { ModuleOff, moduleOff, Period, today, useLists, won } from "./common";

type Line = {
  level: number;
  label: string;
  amount: string;
  subtotal?: boolean;
};
type Body = {
  balanceSheet: Line[];
  incomeStatement: Line[];
  manufacturingCost: Line[];
  assets: string;
  liabilities: string;
  equity: string;
  netIncome: string;
  difference: string;
};
const TABS: [keyof Body, string, string][] = [
  ["balanceSheet", "재무상태표", "기말 잔액입니다."],
  ["incomeStatement", "손익계산서", "기간 발생액입니다."],
  [
    "manufacturingCost",
    "제조원가명세서",
    "재공품·제품 대체 전표가 아직 없어(원가는 1i) 당기총제조비용까지만 봅니다.",
  ],
];

export function Statements() {
  const [tab, setTab] = useState<keyof Body>("balanceSheet");
  const [period, setPeriod] = useState({
    from: today().slice(0, 4) + "-01-01",
    to: today(),
  });
  const { data, error, reload } = useLists<[Body]>([
    `/statements?date_from=${period.from}&date_to=${period.to}`,
  ]);
  if (moduleOff(error)) return <ModuleOff />;
  const body = data?.[0] as unknown as Body | undefined;
  const lines = (body?.[tab] ?? []) as Line[];
  const note = TABS.find(([key]) => key === tab)?.[2] ?? "";
  return (
    <div className="page-fill">
      <PageTitle
        id="E-34"
        title="재무제표"
        help="erp/e-34"
        actions={
          <Period
            from={period.from}
            to={period.to}
            set={(patch) => setPeriod({ ...period, ...patch })}
          />
        }
      />
      <p className="muted" role="note">
        계정 분류(E-18)로 묶습니다. {note} 금액은 분류의 방향으로 셉니다 —
        그래서 감가상각누계액이 유형자산에서, 매출환입이 매출액에서 빠집니다.
      </p>
      <ErrorNotice error={error} retry={reload} />
      {!body ? (
        <Loading />
      ) : (
        <>
          {Number(body.difference) !== 0 && (
            <p className="notice" role="alert">
              자산이 부채·자본과 {won(body.difference)}만큼 어긋납니다. 전표를
              확인하세요.
            </p>
          )}
          <DataTable
            rows={lines.map((l, id) => ({ ...l, id }))}
            leading={
              <span className="row-actions">
                {TABS.map(([key, name]) => (
                  <button
                    key={key}
                    type="button"
                    className="link-button"
                    aria-pressed={tab === key}
                    onClick={() => setTab(key)}
                  >
                    {name}
                  </button>
                ))}
              </span>
            }
            columns={[
              {
                key: "label",
                label: "구분",
                render: (r) => (
                  <span style={{ paddingLeft: `${r.level * 1.2}rem` }}>
                    {r.level === 0 || r.subtotal ? (
                      <strong>{r.label}</strong>
                    ) : (
                      r.label
                    )}
                  </span>
                ),
              },
              {
                key: "amount",
                label: "금액",
                render: (r) =>
                  r.level === 0 || r.subtotal ? (
                    <strong>{won(r.amount)}</strong>
                  ) : (
                    won(r.amount)
                  ),
              },
            ]}
            caption={TABS.find(([key]) => key === tab)?.[1] ?? ""}
            offset={0}
            total={lines.length}
            limit={lines.length || 1}
            onPage={() => undefined}
            empty="이 기간에 움직인 계정이 없습니다."
          />
          <div className="section-heading">
            <h2>요약</h2>
            <strong>
              자산 {won(body.assets)} · 부채 {won(body.liabilities)} · 자본{" "}
              {won(body.equity)} · 당기순이익 {won(body.netIncome)}
            </strong>
          </div>
        </>
      )}
    </div>
  );
}
