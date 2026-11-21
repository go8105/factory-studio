// E-20 판매 반품 · E-24 구매 반품 (DSN-11 F16·F25). 두 화면은 규칙이 같아 한 틀을 쓴다.
import { won } from "./common";
import { DocumentScreen, type Doc } from "./document";
type Ret = Doc & {
  returnNo: string;
  returnedOn: string;
  partnerCode: string;
  partnerName: string;
  reason: string;
  totalAmount: string;
};
type Side = {
  id: string;
  title: string;
  path: string;
  sourcePath: string;
  sourceKey: string;
  sourceLabel: string;
  note: string;
};
export const SALES_RETURN: Side = {
  id: "E-20",
  title: "판매 반품",
  path: "/sales-returns",
  sourcePath: "/receivables",
  sourceKey: "salesRecordId",
  sourceLabel: "원 매출",
  note: "원 매출을 고르고 돌려받을 수량을 적습니다. 이미 반품한 수량은 빼고 남은 만큼만 됩니다. 확정하면 그 매출채권이 반품액만큼 줄어듭니다(저장하지 않고 잔액에서 뺍니다). 실물 반입은 WMS가 합니다. 회계 전표는 1e에서 붙습니다.",
};
export const PURCHASE_RETURN: Side = {
  id: "E-24",
  title: "구매 반품",
  path: "/purchase-returns",
  sourcePath: "/payables",
  sourceKey: "purchaseInvoiceId",
  sourceLabel: "원 매입",
  note: "원 매입 전표를 고르고 돌려보낼 수량을 적습니다. 단가는 그때 산 값을 씁니다 — 지금 단가표가 바뀌었어도 소급하지 않습니다. 확정하면 매입채무가 그만큼 줄어듭니다. 실물 반출은 WMS가 합니다.",
};
const today = () => new Date().toISOString().slice(0, 10);
export function Returns({ side }: { side: Side }) {
  return (
    <DocumentScreen<Ret>
      id={side.id}
      title={side.title}
      path={side.path}
      note={side.note}
      blank={{ returnedOn: today(), reason: "" }}
      extraPaths={[side.sourcePath]}
      columns={() => [
        { key: "returnNo", label: "반품 번호" },
        { key: "returnedOn", label: "반품일" },
        {
          key: "partnerCode",
          label: "거래처",
          render: (r) => `${r.partnerCode} ${r.partnerName}`,
        },
        {
          key: "totalAmount",
          label: "합계",
          render: (r) => won(r.totalAmount),
        },
        { key: "reason", label: "사유", wrap: true },
      ]}
      form={(draft, set, lists, errors) => {
        const sources = lists.extras[0] ?? [];
        return (
          <>
            <label>
              {side.sourceLabel}
              <select
                value={String(draft[side.sourceKey] ?? "")}
                onChange={(e) => {
                  const row = sources.find(
                    (s) => String(s[side.sourceKey]) === e.target.value,
                  );
                  set({
                    [side.sourceKey]: Number(e.target.value),
                    partnerId: row?.partnerId,
                  });
                }}
              >
                <option value="">선택하세요</option>
                {sources.map((s) => (
                  <option key={String(s.id)} value={String(s[side.sourceKey])}>
                    {String(s.shipmentNo ?? s.invoiceNo)} · 잔액{" "}
                    {won(String(s.balance))}
                  </option>
                ))}
              </select>
            </label>
            {errors[side.sourceKey] && (
              <small role="alert">{errors[side.sourceKey]}</small>
            )}
            {errors.partnerId && <small role="alert">{errors.partnerId}</small>}
            <label>
              반품일
              <input
                type="date"
                value={String(draft.returnedOn ?? "")}
                onChange={(e) => set({ returnedOn: e.target.value })}
              />
            </label>
            <label>
              사유
              <input
                value={String(draft.reason ?? "")}
                onChange={(e) => set({ reason: e.target.value })}
              />
            </label>
            {errors.reason && <small role="alert">{errors.reason}</small>}
          </>
        );
      }}
    />
  );
}
