import { Link } from "react-router-dom";
import { ErrorNotice, Loading } from "../shared/components";
import { useGet } from "../gw/common";
import { Status } from "../gw/ui";
type Result = {
  enabled: boolean;
  approval: {
    id: string;
    documentNo: string;
    status: string;
    contentChanged: boolean;
    statusChanged: boolean;
    currentStatus: string;
  } | null;
};
export function GwApproval({ invoiceId }: { invoiceId: number }) {
  const query = useGet<Result>(
    `/api/v1/erp/purchase-invoices/${invoiceId}/gw-approval`,
  );
  const d = query.data;
  return (
    <section className="card">
      <h3>GW 결재</h3>
      <ErrorNotice error={query.error} />
      {!d && !query.error ? (
        <Loading />
      ) : d && !d.enabled ? (
        <p>결재 조회 불가 · GW 꺼짐</p>
      ) : d?.approval ? (
        <>
          <Link to={"/gw/documents?open=" + d.approval.id}>
            {d.approval.documentNo}
          </Link>{" "}
          <Status value={d.approval.status} />
          {d.approval.contentChanged && (
            <p>
              {d.approval.status === "APPROVED" ? "과거 상신본 승인 · " : ""}
              원문 내용 변경
            </p>
          )}
          {d.approval.statusChanged && (
            <p>
              원문 상태 변경 ·{" "}
              {d.approval.currentStatus === "cancelled" ? "취소" : "확정"}
            </p>
          )}
        </>
      ) : (
        d && <p>결재 기록 없음</p>
      )}
      <p className="muted">
        상신본에 대한 검토 기록이며 ERP 확정·취소를 제어하지 않습니다.
      </p>
    </section>
  );
}
