// 업무 화면(E-07 매출·E-11 매입)에서 그 문서의 **실제 전표**를 본다.
// E-14 분개 미리보기는 폐지했다 — 이제 전표는 업무 확정과 함께 실제로 생긴다(DSN-11 Q3).
import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import { Badge, DataTable, ErrorNotice, Loading } from "../shared/components";
import { ERP, won } from "./common";

export type SourceKind =
  "sales_record" | "purchase_invoice" | "receipt_apply" | "payment_apply";
type Line = {
  id: number;
  lineNo: number;
  side: "DEBIT" | "CREDIT";
  accountCode: string;
  accountName: string;
  amount: string;
  partnerCode: string | null;
  departmentCode: string | null;
};
type Entry = {
  id: number;
  entryNo: string;
  entryDate: string;
  entryKind: string;
  status: string;
  description: string | null;
  debitTotal: string;
  creditTotal: string;
  lines: Line[];
};
type Found = {
  entry: Entry | null;
  reason: string | null;
  reasonText?: string;
};

export function JournalPanel({
  sourceKind,
  id,
  onClose,
}: {
  sourceKind: SourceKind;
  id: number;
  onClose?: () => void;
}) {
  const { fail } = useSession();
  const [found, setFound] = useState<Found>();
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    const controller = new AbortController();
    setFound(undefined);
    setError(undefined);
    api<Found>(
      `${ERP}/journal-entries/for-source?sourceKind=${sourceKind}&sourceId=${id}`,
      { signal: controller.signal },
    )
      .then((r) => setFound(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [sourceKind, id]);

  return (
    <section className="panel" aria-label="전표">
      <div className="section-heading">
        <h2>이 문서의 전표</h2>
        {onClose && (
          <button type="button" className="link-button" onClick={onClose}>
            닫기
          </button>
        )}
      </div>
      <ErrorNotice error={error} />
      {!found && !error ? (
        <Loading />
      ) : found?.entry ? (
        <>
          <p>
            {found.entry.entryNo} · {found.entry.entryDate} ·{" "}
            <Badge>{found.entry.entryKind}</Badge>
          </p>
          <DataTable
            rows={found.entry.lines}
            columns={[
              {
                key: "side",
                label: "차·대",
                render: (l) => (l.side === "DEBIT" ? "차변" : "대변"),
              },
              {
                key: "accountCode",
                label: "계정",
                render: (l) => `${l.accountCode} ${l.accountName}`,
              },
              { key: "amount", label: "금액", render: (l) => won(l.amount) },
              {
                key: "partnerCode",
                label: "거래처",
                render: (l) => l.partnerCode ?? "—",
              },
            ]}
            caption="전표 라인"
            offset={0}
            total={found.entry.lines.length}
            limit={found.entry.lines.length || 1}
            onPage={() => undefined}
            empty="라인이 없습니다."
          />
          <p>
            차변 {won(found.entry.debitTotal)} · 대변{" "}
            {won(found.entry.creditTotal)}
          </p>
        </>
      ) : (
        <p role="note">
          아직 전표가 없습니다
          {found?.reasonText ? ` — ${found.reasonText}` : "."} 회계 미반영
          현황(E-31)에서 한꺼번에 반영할 수 있습니다.
        </p>
      )}
    </section>
  );
}
