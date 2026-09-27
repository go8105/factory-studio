// E-14 분개 미리보기 — 독립 화면이자 E-07·E-10·E-11·E-13의 공통 패널. 저장하지 않는다 (FS-019g)
import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  DataTable,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import { ERP, ModuleOff, moduleOff, useLists, won } from "./common";

export type JournalKind = "SALES" | "PURCHASE" | "RECEIPT" | "PAYMENT";
type Line = {
  lineNo: number;
  entrySide: "DEBIT" | "CREDIT";
  accountCode: string;
  accountName: string;
  amountBasis: string;
  amount: string;
};
type Preview = {
  kind: JournalKind;
  doc: string;
  lines: Line[];
  debitTotal: string;
  creditTotal: string;
  unapplied: string | null;
};
export const KIND: Record<JournalKind, string> = {
  SALES: "매출 인식",
  RECEIPT: "수금",
  PURCHASE: "매입",
  PAYMENT: "지급",
};

/** 분개 1세트. 수금·지급은 소명 행 id, 매출·매입은 원천 id를 받는다. */
export function JournalPanel({
  kind,
  id,
  onClose,
}: {
  kind: JournalKind;
  id: number;
  onClose?: () => void;
}) {
  const { fail } = useSession();
  const [preview, setPreview] = useState<Preview>();
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    const controller = new AbortController();
    const param =
      kind === "SALES" || kind === "PURCHASE" ? "sourceId" : "applyId";
    setPreview(undefined);
    setError(undefined);
    api<Preview>(`${ERP}/journal-preview?kind=${kind}&${param}=${id}`, {
      signal: controller.signal,
    })
      .then((r) => setPreview(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [kind, id]);

  const rows = (preview?.lines ?? []).map((l) => ({ ...l, id: l.lineNo }));
  const columns: Column<(typeof rows)[number]>[] = [
    {
      key: "accountName",
      label: "차변",
      render: (r) =>
        r.entrySide === "DEBIT" ? `${r.accountName} ${won(r.amount)}` : "",
    },
    {
      key: "entrySide",
      label: "대변",
      render: (r) =>
        r.entrySide === "CREDIT" ? `${r.accountName} ${won(r.amount)}` : "",
    },
    { key: "amountBasis", label: "금액 기준" },
  ];
  return (
    <section className="panel" aria-label="분개 미리보기">
      <h2>
        분개 미리보기 · {KIND[kind]}
        {preview ? ` · ${preview.doc}` : ""}
      </h2>
      <ErrorNotice error={error} />
      {!preview ? (
        !error && <Loading />
      ) : (
        <>
          <DataTable
            rows={rows}
            columns={columns}
            caption={`${KIND[kind]} 분개`}
            offset={0}
            total={rows.length}
            limit={rows.length || 1}
            onPage={() => undefined}
          />
          <p>
            차변 합계 {won(preview.debitTotal)} · 대변 합계{" "}
            {won(preview.creditTotal)}
          </p>
          {preview.unapplied !== null && Number(preview.unapplied) > 0 && (
            <p className="notice">
              미소명 잔여 {won(preview.unapplied)}은 분개하지 않습니다.
              선수금·선급금 계정이 없어 받을 곳이 없으므로 표 밖에 따로
              적습니다.
            </p>
          )}
        </>
      )}
      <p className="muted">
        계산해서 보여 줄 뿐 저장하지 않습니다. 전표 확정·총계정원장·결산은 1차
        범위에서 제외했습니다.
      </p>
      {onClose && (
        <div className="form-actions">
          <button type="button" className="secondary" onClick={onClose}>
            닫기
          </button>
        </div>
      )}
    </section>
  );
}

type Row = Record<string, unknown> & { id: number };

/** 독립 화면: 거래 유형과 대상을 골라 공통 패널을 연다. */
export function Journal() {
  const { data, error, reload } = useLists<[Row[], Row[], Row[], Row[]]>([
    "/sales-records",
    "/purchase-invoices",
    "/receipts",
    "/payments",
  ]);
  const [kind, setKind] = useState<JournalKind>("SALES");
  const [id, setId] = useState(0);

  if (moduleOff(error)) return <ModuleOff />;
  const [sales, purchases, receipts, payments] = data ?? [[], [], [], []];
  // 대상: 유효 매출, 확정 매입, 수금·지급의 소명 행
  const applies = (monies: Row[], noKey: string) =>
    monies.flatMap((m) =>
      (m.applications as Row[]).map((a) => ({
        id: a.id,
        label: `${String(m[noKey])} → ${String(a.shipmentNo ?? a.invoiceNo)} · ${won(String(a.amount))}`,
      })),
    );
  const options = {
    SALES: sales
      .filter((s) => !s.cancelledAt)
      .map((s) => ({
        id: s.id,
        label: `${String(s.shipmentNo)} · ${won(String(s.totalAmount))}`,
      })),
    PURCHASE: purchases
      .filter((p) => p.status === "confirmed")
      .map((p) => ({
        id: p.id,
        label: `${String(p.invoiceNo)} · ${won(String(p.totalAmount))}`,
      })),
    RECEIPT: applies(receipts, "receiptNo"),
    PAYMENT: applies(payments, "paymentNo"),
  }[kind];

  return (
    <div className="page-fill">
      <PageTitle
        id="E-14"
        title="분개 미리보기"
        subtitle="거래가 어떤 분개가 되는지 분개 규칙(E-18)으로 계산해 봅니다"
        help="erp/e-14"
      />
      <p className="muted" role="note">
        수금·지급은 거래 건이 아니라 소명 1행이 분개 1세트입니다. 그래서
        과입금·과지급도 예외 없이 소명된 금액만 분개됩니다. 매출·수금·매입·지급
        화면의 &quot;분개&quot; 버튼도 같은 패널을 엽니다.
      </p>
      <ErrorNotice error={error} retry={reload} />
      {!data ? (
        !error && <Loading delay={300} />
      ) : (
        <>
          <div className="filter-bar">
            <label>
              거래 유형
              <select
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value as JournalKind);
                  setId(0);
                }}
              >
                {Object.entries(KIND).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              대상
              <select
                value={id || ""}
                onChange={(e) => setId(Number(e.target.value))}
              >
                <option value="">선택</option>
                {options.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {id ? (
            <JournalPanel kind={kind} id={id} />
          ) : (
            <p className="muted">거래 유형과 대상을 고르면 분개가 나옵니다.</p>
          )}
        </>
      )}
    </div>
  );
}
