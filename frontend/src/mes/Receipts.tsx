// M-09 완제품 입고 — 닫힌 PALLET을 입고하고, 입고한 PALLET 번호를 ERP 출하에 옮겨 적게 돕는다 (FS-020f)
import { useState } from "react";
import {
  Badge,
  DataTable,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import { fieldErrors, ModuleOff, moduleOff, useLists, useSend } from "./common";
import type { PackingUnit } from "./Packing";

type Receipt = {
  id: number;
  packingUnitId: number;
  packingNo: string;
  itemId: number | null;
  totalQty: string;
  receivedAt: string;
  unitStatus: string;
};
type Item = { id: number; itemCode: string; name: string };

const num = (v: string) => Number(v).toLocaleString();

export function Receipts() {
  const { data, error, reload } = useLists<[PackingUnit[], Receipt[], Item[]]>([
    "/packing-units",
    "/finished-goods-receipts",
    "/items",
  ]);
  const { send, pending, error: saveError } = useSend(reload);
  const [copied, setCopied] = useState<string>();

  if (moduleOff(error)) return <ModuleOff />;
  const [units, receipts, items] = data ?? [undefined, [], []];
  const errors = fieldErrors(saveError);
  const itemCode = (id: number | null) =>
    id === null
      ? "-"
      : (items.find((i) => i.id === id)?.itemCode ?? String(id));
  const waiting = (units ?? []).filter(
    (u) => u.packingKind === "PALLET" && u.status === "closed",
  );

  async function copy(no: string) {
    try {
      await navigator.clipboard.writeText(no);
      setCopied(no);
    } catch {
      setCopied(undefined);
    }
  }

  const waitingColumns: Column<PackingUnit>[] = [
    { key: "packingNo", label: "PALLET" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          disabled={pending}
          onClick={() =>
            void send("/finished-goods-receipts", "POST", {
              packingUnitId: r.id,
            })
          }
        >
          입고
        </button>
      ),
    },
    { key: "itemId", label: "품목", render: (r) => itemCode(r.itemId) },
    {
      key: "totalQty",
      label: "수량",
      render: (r) => `${num(r.totalQty)} ${r.unit ?? ""}`,
    },
    { key: "childIds", label: "BOX", render: (r) => String(r.childIds.length) },
  ];
  const receiptColumns: Column<Receipt>[] = [
    { key: "packingNo", label: "PALLET" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-label={`${r.packingNo} 번호 복사`}
          onClick={() => void copy(r.packingNo)}
        >
          {copied === r.packingNo ? "복사됨" : "번호 복사"}
        </button>
      ),
    },
    { key: "itemId", label: "품목", render: (r) => itemCode(r.itemId) },
    { key: "totalQty", label: "수량", render: (r) => num(r.totalQty) },
    {
      key: "unitStatus",
      label: "상태",
      render: (r) =>
        r.unitStatus === "shipped" ? <Badge>출하</Badge> : <Badge>입고</Badge>,
    },
    {
      key: "receivedAt",
      label: "입고일",
      render: (r) => new Date(r.receivedAt).toLocaleDateString("ko-KR"),
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="M-09"
        title="완제품 입고"
        subtitle="닫힌 PALLET을 완제품으로 입고합니다"
        help="mes/m-09"
      />
      <p className="notice" role="note">
        입고는 PALLET 단위로만 합니다. ERP는 MES와 독립이라 출하 화면에 입고
        PALLET이 자동으로 뜨지 않습니다. 번호를 복사해 ERP 출하에 직접
        입력하세요. 입고 뒤에는 포장 구성을 바꾸거나 입고를 취소할 수 없습니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!units ? (
        !error && <Loading delay={300} />
      ) : (
        <>
          <section>
            <h2>입고할 PALLET</h2>
            <DataTable
              rows={waiting}
              columns={waitingColumns}
              caption="입고할 PALLET"
              offset={0}
              total={waiting.length}
              limit={waiting.length || 1}
              onPage={() => undefined}
              empty={
                <p className="muted">
                  닫힌 PALLET이 없습니다. 패킹 화면에서 PALLET을 닫으면 여기에
                  나옵니다.
                </p>
              }
            />
          </section>
          <section>
            <h2>입고 내역</h2>
            <DataTable
              rows={receipts}
              columns={receiptColumns}
              caption="입고 내역"
              offset={0}
              total={receipts.length}
              limit={receipts.length || 1}
              onPage={() => undefined}
              empty={<p className="muted">입고 내역이 없습니다.</p>}
            />
          </section>
        </>
      )}
    </div>
  );
}
