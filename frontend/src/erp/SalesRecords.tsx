// E-07 매출 — 출하 확정으로 생긴 매출 조회와 취소(소명 0행·발급완료 아님) (FS-019d)
import { useState } from "react";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  fieldErrors,
  labels,
  ModuleOff,
  moduleOff,
  PARTNERS,
  useLists,
  useSend,
  won,
  type Partner,
} from "./common";

export type Sale = {
  id: number;
  shipmentNo: string;
  orderNo: string;
  partnerId: number;
  supplyAmount: string;
  taxAmount: string;
  totalAmount: string;
  recognizedAt: string;
  cancelledAt: string | null;
  cancelReason: string | null;
  dueDate: string | null;
  appliedAmount: string;
  taxInvoiceId: number | null;
  taxInvoiceStatus: "pending" | "issued" | null;
  cancelBlockedReason:
    "ALREADY_CANCELLED" | "INVOICE_ISSUED" | "RECEIPT_APPLIED" | null;
};

// 막힌 이유를 버튼 툴팁에 쓴다(FS-008a E-07). 문구는 서버 409 메시지와 같다.
const BLOCKED = {
  ALREADY_CANCELLED: "이미 취소된 매출입니다.",
  INVOICE_ISSUED: "세금계산서가 발급완료라 취소할 수 없습니다.",
  RECEIPT_APPLIED:
    "수금 소명이 있어 취소할 수 없습니다. 소명을 먼저 취소하세요.",
};
export const INVOICE = { pending: "발급대기", issued: "발급완료" };

export function SalesRecords() {
  const { data, error, reload } = useLists<[Sale[], Partner[]]>([
    "/sales-records",
    PARTNERS,
  ]);
  const { send, pending, error: saveError, setError } = useSend(reload);
  const [cancelId, setCancelId] = useState<number>();
  const [reason, setReason] = useState("");

  if (moduleOff(error)) return <ModuleOff />;
  const [sales, partners] = data ?? [undefined, []];
  const name = labels(partners, []);
  const errors = fieldErrors(saveError);
  const target = sales?.find((s) => s.id === cancelId);

  async function cancel() {
    if (!target || pending) return;
    const saved = await send(`/sales-records/${target.id}/cancel`, "POST", {
      reason: reason.trim(),
    });
    if (saved) {
      setCancelId(undefined);
      setReason("");
    }
  }

  const columns: Column<Sale>[] = [
    { key: "shipmentNo", label: "출하번호" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          disabled={!!r.cancelBlockedReason}
          title={
            r.cancelBlockedReason
              ? BLOCKED[r.cancelBlockedReason]
              : "매출을 취소합니다"
          }
          onClick={() => {
            setCancelId(r.id);
            setError(undefined);
          }}
        >
          취소
        </button>
      ),
    },
    { key: "orderNo", label: "수주" },
    {
      key: "partnerId",
      label: "거래처",
      render: (r) => name.partner(r.partnerId),
    },
    {
      key: "recognizedAt",
      label: "매출일",
      render: (r) => new Date(r.recognizedAt).toLocaleDateString(),
    },
    {
      key: "supplyAmount",
      label: "공급가액",
      render: (r) => won(r.supplyAmount),
    },
    { key: "taxAmount", label: "세액", render: (r) => won(r.taxAmount) },
    { key: "totalAmount", label: "합계", render: (r) => won(r.totalAmount) },
    {
      key: "appliedAmount",
      label: "소명액",
      render: (r) => won(r.appliedAmount),
    },
    {
      key: "taxInvoiceStatus",
      label: "세금계산서",
      render: (r) => (r.taxInvoiceStatus ? INVOICE[r.taxInvoiceStatus] : "-"),
    },
    {
      key: "cancelledAt",
      label: "상태",
      render: (r) =>
        r.cancelledAt ? (
          <Badge tone="issue">취소 · {r.cancelReason}</Badge>
        ) : (
          <Badge>유효</Badge>
        ),
    },
  ];

  return (
    <>
      <PageTitle
        id="E-07"
        title="매출"
        subtitle="출하 확정으로 인식된 매출을 보고, 조건이 맞으면 취소합니다"
        help="erp/e-07"
      />
      <p className="muted">
        매출은 출하를 확정할 때 자동으로 생기고 금액은 바꿀 수 없습니다(KRW).
        매출채권도 함께 생기며 수기로 등록하지 않습니다. 취소는 수금 소명이 없고
        세금계산서가 발급완료가 아닐 때만 됩니다. 발급대기 계산서는 함께
        지워지고, 출하는 되돌리지 않습니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!sales ? (
        !error && <Loading />
      ) : (
        <>
          <DataTable
            rows={sales}
            columns={columns}
            caption="매출 목록"
            offset={0}
            total={sales.length}
            limit={sales.length || 1}
            onPage={() => undefined}
            empty={
              <EmptyState
                reason="인식된 매출이 없습니다. E-06 출하에서 출하를 확정하면 생깁니다."
                to="/erp/shipments"
                action="출하로"
              />
            }
          />
          {target && (
            <section className="panel" aria-label="매출 취소">
              <h2>{target.shipmentNo} 매출 취소</h2>
              <p className="muted">
                합계 {won(target.totalAmount)}
                {target.taxInvoiceStatus === "pending" &&
                  " · 발급대기 세금계산서도 함께 삭제됩니다"}
              </p>
              <div className="form-actions">
                <Field
                  label="취소 사유"
                  value={reason}
                  maxLength={300}
                  error={errors.reason}
                  onChange={(e) => setReason(e.target.value)}
                />
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setCancelId(undefined)}
                >
                  닫기
                </button>
                <button
                  type="button"
                  disabled={pending || !reason.trim()}
                  onClick={() => void cancel()}
                >
                  매출 취소 확정
                </button>
              </div>
            </section>
          )}
        </>
      )}
    </>
  );
}
