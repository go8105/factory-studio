// E-21 영업 현황 · E-25 구매 현황 · E-26 재고 현황 (DSN-11 F17·F19·F26·F31).
// 셋 다 조회 계산이다. 저장하는 것이 없다.
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

type Revenue = {
  partnerCode: string;
  partnerName: string;
  itemCode: string;
  itemName: string;
  shippedQty: string;
  supplyAmount: string;
};
type OrderRow = {
  orderNo: string;
  orderedOn: string;
  partnerCode: string;
  partnerName: string;
  itemCode: string;
  orderQty: string;
  shippedQty: string;
  openQty: string;
  status: string;
};

export function SalesStatus() {
  const [period, setPeriod] = useState({ from: monthsAgo(3), to: today() });
  const { data, error, reload } = useLists<
    [
      {
        revenue: Revenue[];
        orders: OrderRow[];
        supplyTotal: string;
        openQtyTotal: string;
      },
    ]
  >([`/sales-status?date_from=${period.from}&date_to=${period.to}`]);
  if (moduleOff(error)) return <ModuleOff />;
  const body = data?.[0] as unknown as
    | {
        revenue: Revenue[];
        orders: OrderRow[];
        supplyTotal: string;
        openQtyTotal: string;
      }
    | undefined;
  return (
    <div className="page-fill">
      <PageTitle
        id="E-21"
        title="영업 현황"
        help="erp/e-21"
        actions={
          <Period
            from={period.from}
            to={period.to}
            set={(patch) => setPeriod({ ...period, ...patch })}
          />
        }
      />
      <p className="muted" role="note">
        기간 안에 인식한 매출과, 그 기간에 받은 수주의 출하 진행입니다. 취소한
        매출·수주는 빼고 셉니다. 저장하지 않고 조회할 때마다 계산합니다.
      </p>
      <ErrorNotice error={error} retry={reload} />
      {!body ? (
        <Loading />
      ) : (
        <>
          <section className="section-block">
            <div className="section-heading">
              <h2>거래처·품목별 매출</h2>
              <strong>{won(body.supplyTotal)}</strong>
            </div>
            <DataTable
              rows={body.revenue.map((r, id) => ({ ...r, id }))}
              columns={[
                {
                  key: "partnerCode",
                  label: "거래처",
                  render: (r) => `${r.partnerCode} ${r.partnerName}`,
                },
                {
                  key: "itemCode",
                  label: "품목",
                  render: (r) => `${r.itemCode} ${r.itemName}`,
                },
                {
                  key: "shippedQty",
                  label: "출하 수량",
                  render: (r) => Number(r.shippedQty).toLocaleString(),
                },
                {
                  key: "supplyAmount",
                  label: "공급가액",
                  render: (r) => won(r.supplyAmount),
                },
              ]}
              caption="거래처·품목별 매출"
              offset={0}
              total={body.revenue.length}
              limit={body.revenue.length || 1}
              onPage={() => undefined}
              empty="그 기간에 인식한 매출이 없습니다."
            />
          </section>
          <section className="section-block">
            <div className="section-heading">
              <h2>수주 대비 출하</h2>
              <strong>
                미출하 {Number(body.openQtyTotal).toLocaleString()}
              </strong>
            </div>
            <DataTable
              rows={body.orders.map((r, id) => ({ ...r, id }))}
              columns={[
                { key: "orderNo", label: "수주 번호" },
                { key: "orderedOn", label: "수주일" },
                {
                  key: "partnerCode",
                  label: "거래처",
                  render: (r) => `${r.partnerCode} ${r.partnerName}`,
                },
                { key: "itemCode", label: "품목" },
                {
                  key: "orderQty",
                  label: "수주",
                  render: (r) => Number(r.orderQty).toLocaleString(),
                },
                {
                  key: "shippedQty",
                  label: "출하",
                  render: (r) => Number(r.shippedQty).toLocaleString(),
                },
                {
                  key: "openQty",
                  label: "미출하",
                  render: (r) => Number(r.openQty).toLocaleString(),
                },
              ]}
              caption="수주 대비 출하"
              offset={0}
              total={body.orders.length}
              limit={body.orders.length || 1}
              onPage={() => undefined}
              empty="그 기간에 받은 수주가 없습니다."
            />
          </section>
        </>
      )}
    </div>
  );
}

type PurchaseRow = {
  poNo: string;
  orderedOn: string;
  partnerCode: string;
  partnerName: string;
  status: string;
  totalAmount: string;
  invoicedAmount: string;
  receiptState: "NONE" | "PARTIAL" | "COMPLETE" | "UNKNOWN";
};
const RECEIPT: Record<string, { label: string; tone: string }> = {
  NONE: { label: "미입고", tone: "normal" },
  PARTIAL: { label: "부분", tone: "warning" },
  COMPLETE: { label: "완료", tone: "normal" },
  UNKNOWN: { label: "모름", tone: "normal" },
};

export function PurchaseStatus() {
  const [period, setPeriod] = useState({ from: monthsAgo(3), to: today() });
  const { data, error, reload } = useLists<unknown[][]>([
    `/purchase-status?date_from=${period.from}&date_to=${period.to}`,
  ]);
  if (moduleOff(error)) return <ModuleOff />;
  const body = data?.[0] as unknown as
    | {
        orders: PurchaseRow[];
        orderTotal: string;
        invoicedTotal: string;
        receiptKnown: boolean;
      }
    | undefined;
  return (
    <div className="page-fill">
      <PageTitle
        id="E-25"
        title="구매 현황"
        help="erp/e-25"
        actions={
          <Period
            from={period.from}
            to={period.to}
            set={(patch) => setPeriod({ ...period, ...patch })}
          />
        }
      />
      <p className="muted" role="note">
        발주 대비 입고와 매입입니다. 입고는 WMS가 검수를 마친 수량이고, ERP는
        저장하지 않고 발주번호로 읽어 맞댑니다.
      </p>
      <ErrorNotice error={error} retry={reload} />
      {!body ? (
        <Loading />
      ) : (
        <section className="section-block">
          <div className="section-heading">
            <h2>발주 {won(body.orderTotal)}</h2>
            <strong>매입 {won(body.invoicedTotal)}</strong>
          </div>
          {!body.receiptKnown && (
            <p role="note">
              WMS를 조회할 수 없어 입고 진행을 알 수 없습니다(끄셨거나 이
              공간에서 아직 한 번도 열지 않았습니다). 0건이라는 뜻이 아닙니다.
            </p>
          )}
          <DataTable
            rows={body.orders.map((r, id) => ({ ...r, id }))}
            columns={[
              { key: "poNo", label: "발주 번호" },
              { key: "orderedOn", label: "발주일" },
              {
                key: "partnerCode",
                label: "공급처",
                render: (r) => `${r.partnerCode} ${r.partnerName}`,
              },
              {
                key: "totalAmount",
                label: "발주액",
                render: (r) => won(r.totalAmount),
              },
              {
                key: "invoicedAmount",
                label: "매입액",
                render: (r) => won(r.invoicedAmount),
              },
              {
                key: "receiptState",
                label: "입고",
                render: (r) => (
                  <Badge tone={RECEIPT[r.receiptState].tone as never}>
                    {RECEIPT[r.receiptState].label}
                  </Badge>
                ),
              },
            ]}
            caption="구매 현황"
            offset={0}
            total={body.orders.length}
            limit={body.orders.length || 1}
            onPage={() => undefined}
            empty="그 기간에 낸 발주가 없습니다."
          />
        </section>
      )}
    </div>
  );
}

type StockRow = {
  itemCode: string;
  itemName: string;
  unit: string;
  linked: boolean;
  qtyOnHand: string | null;
  safetyStock: string | null;
  isShort: boolean | null;
};

export function StockStatus() {
  const { data, error, reload } = useLists<unknown[][]>(["/stock-status"]);
  if (moduleOff(error)) return <ModuleOff />;
  const body = data?.[0] as unknown as
    { available: boolean; rows: StockRow[] } | undefined;
  return (
    <div className="page-fill">
      <PageTitle id="E-26" title="재고 현황" help="erp/e-26" />
      <p className="muted" role="note">
        재고는 WMS가 가집니다. ERP는 품목 코드로 읽어 보여 줄 뿐 저장하지
        않습니다. 재고 관리를 끈 품목(무형 등)은 여기 나오지 않습니다.
      </p>
      <ErrorNotice error={error} retry={reload} />
      {!body ? (
        <Loading />
      ) : !body.available ? (
        <p role="note">
          WMS를 조회할 수 없습니다. 사용하지 않도록 설정했거나, 이 공간에서 아직
          한 번도 열지 않아 예시가 복사되지 않았습니다.
        </p>
      ) : (
        <DataTable
          rows={body.rows.map((r, id) => ({ ...r, id }))}
          columns={[
            { key: "itemCode", label: "품목 코드" },
            { key: "itemName", label: "품목명" },
            {
              key: "qtyOnHand",
              label: "재고",
              render: (r) =>
                r.linked
                  ? `${Number(r.qtyOnHand).toLocaleString()} ${r.unit}`
                  : "연결 안 됨",
            },
            {
              key: "safetyStock",
              label: "안전 재고",
              render: (r) =>
                r.safetyStock === null
                  ? "—"
                  : Number(r.safetyStock).toLocaleString(),
            },
            {
              key: "isShort",
              label: "부족",
              render: (r) =>
                r.isShort === null ? (
                  "판단 안 함"
                ) : r.isShort ? (
                  <Badge tone="issue">부족</Badge>
                ) : (
                  <Badge tone="normal">충분</Badge>
                ),
            },
          ]}
          caption="재고 현황"
          offset={0}
          total={body.rows.length}
          limit={body.rows.length || 1}
          onPage={() => undefined}
          empty="재고를 관리하는 품목이 없습니다."
        />
      )}
    </div>
  );
}
