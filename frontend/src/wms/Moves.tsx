// W-05 재고 원장 — 확정 이동 줄을 조회한다(UI-02 L 패턴, F-02 기준).
// 품목을 고르면 품목·LOT별 누계를 보여 준다. 원천 번호는 스냅샷이라 다른 솔루션 화면으로 잇지 않는다(D11).
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  DataTable,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  ModuleOff,
  moduleOff,
  num,
  signed,
  time,
  TYPE_LABEL,
  useLists,
  WMS,
  type DocumentType,
  type Item,
  type Move,
  type Warehouse,
} from "./common";

type Filters = {
  from: string;
  to: string;
  itemCode: string;
  lotNo: string;
  warehouseId: string;
  type: string;
};

export function Moves() {
  const { fail } = useSession();
  const [params] = useSearchParams();
  const initial: Filters = {
    from: "",
    to: "",
    itemCode: params.get("itemCode") ?? "",
    lotNo: params.get("lotNo") ?? "",
    warehouseId: "",
    type: "",
  };
  const [draft, setDraft] = useState(initial);
  const [applied, setApplied] = useState(initial);
  const lists = useLists<[Item[], Warehouse[]]>(["/items", "/warehouses"]);
  const [rows, setRows] = useState<Move[]>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams(
      Object.entries(applied).filter(([, v]) => v.trim() !== ""),
    );
    setError(undefined);
    setRows(undefined);
    api<Move[]>(`${WMS}/moves?${query}`, { signal: controller.signal })
      .then((r) => !controller.signal.aborted && setRows(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [applied, reload]);
  if (moduleOff(error) || moduleOff(lists.error)) return <ModuleOff />;
  const [items, warehouses] = lists.data ?? [[], []];
  const running = !!applied.itemCode;

  const columns: Column<Move>[] = [
    { key: "movedAt", label: "일시", render: (r) => time(r.movedAt) },
    {
      key: "documentNo",
      label: "전표",
      render: (r) => (
        <Link
          className="link-button"
          to={`/wms/documents?open=${r.documentId}`}
        >
          {r.documentNo}
        </Link>
      ),
    },
    {
      key: "documentType",
      label: "유형",
      render: (r) => TYPE_LABEL[r.documentType!],
    },
    { key: "sourceRef", label: "원천", render: (r) => r.sourceRef ?? "—" },
    { key: "itemCode", label: "품목" },
    {
      key: "locationCode",
      label: "위치",
      render: (r) =>
        `${r.warehouseCode} ${r.locationCode} · ${r.locationType === "QUARANTINE" ? "격리" : r.locationType === "RECEIVING" ? "입고장" : "정상"}`,
    },
    {
      key: "lotNo",
      label: "LOT",
      render: (r) => r.lotNo ?? (r.itemClass === "FG" ? "(미지정)" : "—"),
    },
    {
      key: "qtyDelta",
      label: "증감",
      render: (r) => (
        <>
          {signed(r.qtyDelta)}
          {r.sourceQty && r.sourceUnit !== r.unit && (
            <small className="muted">
              {" "}
              {num(r.sourceQty)} {r.sourceUnit}
            </small>
          )}
        </>
      ),
    },
    ...(running
      ? [
          {
            key: "running" as const,
            label: "누계",
            render: (r: Move) => num(r.running!),
          },
        ]
      : []),
    { key: "unit", label: "단위" },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="W-05"
        title="재고 원장"
        subtitle="확정 전표의 이동 줄입니다. 품목을 고르면 품목·LOT별 누계를 보여 줍니다"
        help="wms/w-05"
      />
      <form
        className="filter-bar"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied(draft);
        }}
      >
        <label>
          시작일
          <input
            type="date"
            value={draft.from}
            onChange={(e) => setDraft({ ...draft, from: e.target.value })}
          />
        </label>
        <label>
          종료일
          <input
            type="date"
            value={draft.to}
            onChange={(e) => setDraft({ ...draft, to: e.target.value })}
          />
        </label>
        <label>
          품목
          <select
            value={draft.itemCode}
            onChange={(e) => setDraft({ ...draft, itemCode: e.target.value })}
          >
            <option value="">전체</option>
            {items.map((i) => (
              <option key={i.id} value={i.itemCode}>
                {i.itemCode} {i.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          LOT 번호
          <input
            value={draft.lotNo}
            maxLength={50}
            onChange={(e) => setDraft({ ...draft, lotNo: e.target.value })}
          />
        </label>
        <label>
          창고
          <select
            value={draft.warehouseId}
            onChange={(e) =>
              setDraft({ ...draft, warehouseId: e.target.value })
            }
          >
            <option value="">전체</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.code}
              </option>
            ))}
          </select>
        </label>
        <label>
          전표 유형
          <select
            value={draft.type}
            onChange={(e) => setDraft({ ...draft, type: e.target.value })}
          >
            <option value="">전체</option>
            {(Object.keys(TYPE_LABEL) as DocumentType[]).map((t) => (
              <option key={t} value={t}>
                {TYPE_LABEL[t]}
              </option>
            ))}
          </select>
        </label>
        <button type="submit">조회</button>
      </form>
      <ErrorNotice
        error={error ?? lists.error}
        retry={() => setReload((n) => n + 1)}
      />
      {!rows ? (
        !error && <Loading delay={300} />
      ) : (
        <DataTable
          rows={rows}
          columns={columns}
          caption="재고 원장"
          offset={0}
          total={rows.length}
          limit={rows.length || 1}
          onPage={() => undefined}
          empty={
            <EmptyState
              reason="조건에 맞는 이동이 없습니다."
              to="/wms/sources"
              action="원천 반영으로"
            />
          }
        />
      )}
    </div>
  );
}
