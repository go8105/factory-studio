// E-23 발주서 (DSN-11 F22). 입고 진행은 WMS에서 읽어 그때그때 보여 준다.
import { Badge } from "../shared/components";
import { won } from "./common";
import { DocumentScreen, type Doc, type Row } from "./document";
type Receipt = {
  state: "NONE" | "PARTIAL" | "COMPLETE" | "UNKNOWN";
  orderedQty?: string;
  receivedQty?: string;
  lines: {
    lineNo: number;
    itemCode: string;
    orderedQty: string;
    receivedQty: string;
    openQty: string;
  }[];
};
type Order = Doc & {
  poNo: string;
  orderedOn: string;
  dueOn: string | null;
  partnerId: number;
  partnerCode: string;
  partnerName: string;
  totalAmount: string;
  receipt: Receipt;
};
const RECEIPT: Record<Receipt["state"], { label: string; tone: string }> = {
  NONE: { label: "미입고", tone: "normal" },
  PARTIAL: { label: "부분 입고", tone: "warning" },
  COMPLETE: { label: "입고 완료", tone: "normal" },
  UNKNOWN: { label: "모름(WMS 조회 불가)", tone: "normal" },
};
const today = () => new Date().toISOString().slice(0, 10);
export function PurchaseOrders() {
  return (
    <DocumentScreen<Order>
      id="E-23"
      title="발주서"
      path="/purchase-orders"
      note="확정한 발주는 명세를 고치지 않습니다 — 바꾸려면 취소하고 다시 냅니다. 입고 진행은 ERP가 저장하지 않고 WMS 입고(검수 완료분)를 발주번호로 읽어 그때그때 맞댑니다. WMS를 끄면, 또는 이 공간에서 WMS를 아직 한 번도 열지 않아 예시가 복사되지 않았으면 '모름'입니다 — 입고가 없다는 뜻이 아닙니다."
      blank={{ orderedOn: today() }}
      extraPaths={[
        "/departments?limit=200",
        "/projects?limit=200",
        "/purchase-requests",
      ]}
      columns={() => [
        { key: "poNo", label: "발주 번호" },
        { key: "orderedOn", label: "발주일" },
        {
          key: "partnerCode",
          label: "공급처",
          render: (o) => `${o.partnerCode} ${o.partnerName}`,
        },
        { key: "dueOn", label: "납기", render: (o) => o.dueOn ?? "—" },
        {
          key: "totalAmount",
          label: "합계",
          render: (o) => won(o.totalAmount),
        },
        {
          key: "receipt",
          label: "입고",
          render: (o) => (
            <Badge tone={RECEIPT[o.receipt.state].tone as never}>
              {RECEIPT[o.receipt.state].label}
            </Badge>
          ),
        },
      ]}
      detail={(order) => (
        <p role="note">
          입고 {RECEIPT[order.receipt.state].label}
          {order.receipt.state !== "UNKNOWN" && order.receipt.receivedQty
            ? ` — 발주 ${order.receipt.orderedQty} 중 ${order.receipt.receivedQty} 도착`
            : ""}
        </p>
      )}
      form={(draft, set, lists, errors) => (
        <>
          <label>
            공급처
            <select
              value={String(draft.partnerId ?? "")}
              onChange={(e) => set({ partnerId: Number(e.target.value) })}
            >
              <option value="">선택하세요</option>
              {lists.partners
                .filter(
                  (p) =>
                    ["SUPPLIER", "BOTH"].includes(p.partnerKind) && p.isActive,
                )
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.partnerCode} {p.partnerName}
                  </option>
                ))}
            </select>
          </label>
          {errors.partnerId && <small role="alert">{errors.partnerId}</small>}
          <label>
            발주일
            <input
              type="date"
              value={String(draft.orderedOn ?? "")}
              onChange={(e) => set({ orderedOn: e.target.value })}
            />
          </label>
          <label>
            납기
            <input
              type="date"
              value={String(draft.dueOn ?? "")}
              onChange={(e) => set({ dueOn: e.target.value || undefined })}
            />
          </label>
          {errors.dueOn && <small role="alert">{errors.dueOn}</small>}
          <PickerRow
            label="부서"
            rows={lists.extras[0] ?? []}
            value={draft.departmentId}
            onChange={(id) => set({ departmentId: id })}
          />
          <PickerRow
            label="프로젝트"
            rows={lists.extras[1] ?? []}
            value={draft.projectId}
            onChange={(id) => set({ projectId: id })}
          />
        </>
      )}
      lineItems={(items) =>
        items.filter((i) => !["finished", "semi_finished"].includes(i.itemType))
      }
      extraActions={(order, send, extras) =>
        order.status === "draft" ? (
          <LoadRequest order={order} send={send} requests={extras[2] ?? []} />
        ) : order.status === "confirmed" ? (
          <button
            type="button"
            onClick={() =>
              void send(`/purchase-orders/${order.id}/close`, "POST")
            }
          >
            종결
          </button>
        ) : null
      }
    />
  );
}
function PickerRow({
  label,
  rows,
  value,
  onChange,
}: {
  label: string;
  rows: Row[];
  value: unknown;
  onChange: (id: number | undefined) => void;
}) {
  return (
    <label>
      {label}
      <select
        value={String(value ?? "")}
        onChange={(e) =>
          onChange(e.target.value ? Number(e.target.value) : undefined)
        }
      >
        <option value="">지정 안 함</option>
        {rows.map((r) => (
          <option key={r.id} value={r.id}>
            {r.code} {r.name}
          </option>
        ))}
      </select>
    </label>
  );
}
function LoadRequest({
  order,
  send,
  requests,
}: {
  order: Order;
  send: (path: string, method: string, body?: unknown) => Promise<unknown>;
  requests: Row[];
}) {
  // 확정했고 아직 발주되지 않은 요청만 고를 수 있다.
  const open = requests.filter((r) => r.status === "confirmed");
  return (
    <label>
      확정 요청 불러오기
      <select
        defaultValue=""
        onChange={(e) => {
          if (!e.target.value) return;
          void send(`/purchase-orders/${order.id}/load-request`, "POST", {
            requestId: Number(e.target.value),
          });
          e.target.value = "";
        }}
      >
        <option value="">
          {open.length ? "요청 선택" : "확정한 요청이 없습니다"}
        </option>
        {open.map((r) => (
          <option key={r.id} value={r.id}>
            {String(r.requestNo)} ({String(r.requestedOn)})
          </option>
        ))}
      </select>
    </label>
  );
}
