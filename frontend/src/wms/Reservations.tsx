import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Badge,
  DataTable,
  DetailPanel,
  FormPanel,
  Field,
  Loading,
  PageTitle,
  useDiscardGuard,
} from "../shared/components";
import { ModuleOff, moduleOff, num, type Item, type StockRow } from "./common";
import {
  OperationError,
  comparison,
  states,
  useWmsCommand,
  useWmsQuery,
  type Page,
  type Reservation,
  type ReservationSources,
} from "./operations";
import "./Operations.css";
export function Reservations() {
  const [params, setParams] = useSearchParams();
  const query = new URLSearchParams(params);
  query.delete("open");
  const list = useWmsQuery<Page<Reservation>>(`/reservations?${query}`);
  const items = useWmsQuery<Item[]>("/items");
  const open = params.get("open");
  const detail = useWmsQuery<Reservation>(
    open && open !== "new" ? `/reservations/${open}` : null,
  );
  const set = (name: string, value: string) =>
    setParams((p) => {
      if (value) p.set(name, value);
      else p.delete(name);
      if (name !== "open" && name !== "page") p.delete("page");
      return p;
    });
  const refresh = () => {
    list.reload();
    detail.reload();
  };
  if (moduleOff(list.error)) return <ModuleOff />;
  return (
    <div className="page-fill">
      <PageTitle
        id="W-09"
        title="출고 예약"
        subtitle="정상 재고를 예약하고 ERP 확정 출하와 전량 대조하여 소진합니다"
        help="wms/w-09"
      />
      <div className="filter-bar">
        <label>
          상태
          <select
            value={params.get("status") ?? ""}
            onChange={(e) => set("status", e.target.value)}
          >
            <option value="">전체</option>
            {["ACTIVE", "RELEASED", "CONSUMED"].map((s) => (
              <option key={s} value={s}>
                {states[s]}
              </option>
            ))}
          </select>
        </label>
        <label>
          품목
          <select
            value={params.get("itemCode") ?? ""}
            onChange={(e) => set("itemCode", e.target.value)}
          >
            <option value="">전체</option>
            {items.data?.map((x) => (
              <option key={x.id} value={x.itemCode}>
                {x.itemCode}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input
            type="checkbox"
            checked={params.get("shortageOnly") === "true"}
            onChange={(e) =>
              set("shortageOnly", e.target.checked ? "true" : "")
            }
          />
          예약 부족만
        </label>
        <button onClick={() => set("open", "new")}>예약 등록</button>
      </div>
      <OperationError error={list.error ?? items.error} retry={list.reload} />
      {list.data ? (
        <DataTable
          caption="출고 예약"
          rows={list.data.rows}
          columns={[
            { key: "reservationNo", label: "번호" },
            { key: "shipmentOrderRef", label: "참고 출하지시" },
            {
              key: "status",
              label: "상태",
              render: (r) => <Badge>{states[r.status]}</Badge>,
            },
            {
              key: "shortage",
              label: "예약 부족",
              render: (r) =>
                Number(r.shortage) > 0 ? "부족 있음 · 상세 확인" : "—",
            },
            {
              key: "id",
              label: "관리",
              render: (r) => (
                <button
                  className="link-button"
                  onClick={() => set("open", String(r.id))}
                >
                  상세
                </button>
              ),
            },
          ]}
          offset={(list.data.page - 1) * 50}
          limit={50}
          total={list.data.total}
          onPage={(offset) => set("page", String(Math.floor(offset / 50) + 1))}
        />
      ) : (
        !list.error && <Loading />
      )}
      <OperationError error={detail.error} retry={detail.reload} />
      {open === "new" && (
        <ReservationForm
          close={() => set("open", "")}
          saved={(r) => {
            list.reload();
            set("open", String(r.id));
          }}
        />
      )}
      {open && open !== "new" && detail.data && items.data && (
        <ReservationDetail
          key={`${detail.data.id}:${detail.data.version}`}
          row={detail.data}
          items={items.data}
          close={() => set("open", "")}
          refresh={refresh}
          changed={(row) => {
            detail.accept(row);
            refresh();
          }}
        />
      )}
    </div>
  );
}
function ReservationForm({
  close,
  saved,
}: {
  close: () => void;
  saved: (r: Reservation) => void;
}) {
  const stock = useWmsQuery<{ rows: StockRow[] }>("/stock");
  const sources = useWmsQuery<ReservationSources>("/reservation-sources");
  const [businessKey, setBusiness] = useState("");
  const [shipmentOrderRef, setRef] = useState("");
  const [lines, setLines] = useState([{ key: "", quantity: "" }]);
  const [dirty, setDirty] = useState(false);
  const guard = useDiscardGuard(dirty);
  const command = useWmsCommand();
  const rows =
    stock.data?.rows.filter(
      (r) =>
        (r.locationType ?? "NORMAL") === "NORMAL" &&
        (r.itemClass === "RAW" || r.lotNo),
    ) ?? [];
  const key = (r: StockRow) => `${r.itemId}:${r.locationId}:${r.lotNo ?? ""}`;
  return (
    <FormPanel
      wide
      title="예약 등록"
      guard={guard}
      onClose={close}
      onSubmit={(e) => {
        e.preventDefault();
        void command
          .send<Reservation>("/reservations", {
            businessKey,
            shipmentOrderRef: shipmentOrderRef || null,
            lines: lines.map((l) => {
              const r = rows.find((r) => key(r) === l.key)!;
              return {
                itemId: r.itemId,
                locationId: r.locationId,
                lotNo: r.lotNo,
                quantity: l.quantity,
              };
            }),
          })
          .then((r) => {
            if (r) {
              setDirty(false);
              saved(r);
            } else stock.reload();
          });
      }}
      actions={
        <button
          disabled={
            command.pending ||
            lines.some((l) => !rows.some((r) => key(r) === l.key))
          }
          type="submit"
        >
          예약 등록
        </button>
      }
    >
      <OperationError
        error={command.error ?? stock.error ?? sources.error}
        retry={stock.reload}
      />
      <fieldset
        className="wms-operation-fields"
        disabled={command.pending}
        onChange={() => setDirty(true)}
      >
        <Field
          required
          label="업무 중복 방지 번호"
          value={businessKey}
          maxLength={100}
          onChange={(e) => setBusiness(e.target.value)}
        />
        <Field
          label="ERP 출하지시 참고 번호 (선택)"
          list="wms-shipment-orders"
          value={shipmentOrderRef}
          maxLength={40}
          onChange={(e) => setRef(e.target.value)}
        />
        <datalist id="wms-shipment-orders">
          {sources.data?.orders.map((o) => (
            <option key={o.shipmentOrderNo} value={o.shipmentOrderNo}>
              {o.status}
            </option>
          ))}
        </datalist>
        <p>
          참고 번호는 자동 출고 약속이 아닙니다. ERP를 꺼도 수동 예약·해제는
          가능합니다. 격리 재고는 예약 대상에서 제외됩니다.
        </p>
        {lines.map((l, i) => {
          const r = rows.find((r) => key(r) === l.key);
          return (
            <fieldset className="wms-operation-line" key={i}>
              <legend>예약 명세 {i + 1}</legend>
              <label>
                품목·위치·LOT
                <select
                  required
                  value={l.key}
                  onChange={(e) =>
                    setLines((xs) =>
                      xs.map((x, j) =>
                        i === j ? { ...x, key: e.target.value } : x,
                      ),
                    )
                  }
                >
                  <option value="">선택</option>
                  {rows.map((r) => (
                    <option key={key(r)} value={key(r)}>
                      {r.itemCode} · {r.locationCode} · {r.lotNo ?? "원자재"} ·
                      가용 {num(r.available)} {r.unit}
                    </option>
                  ))}
                </select>
              </label>
              {r && (
                <p>
                  현재고 {num(r.onHand)} · 예약 {num(r.reservedQty)} · 예약 가능{" "}
                  {num(r.available)} {r.unit}
                </p>
              )}
              <Field
                label="예약 수량"
                required
                inputMode="decimal"
                value={l.quantity}
                onChange={(e) =>
                  setLines((xs) =>
                    xs.map((x, j) =>
                      i === j ? { ...x, quantity: e.target.value } : x,
                    ),
                  )
                }
              />
              <button
                type="button"
                className="link-button"
                disabled={lines.length === 1}
                onClick={() => {
                  setDirty(true);
                  setLines((xs) => xs.filter((_, j) => i !== j));
                }}
              >
                명세 {i + 1} 삭제
              </button>
            </fieldset>
          );
        })}
        <button
          className="secondary"
          type="button"
          disabled={lines.length >= 100}
          onClick={() => {
            setDirty(true);
            setLines((xs) => [...xs, { key: "", quantity: "" }]);
          }}
        >
          명세 추가
        </button>
        <button type="button" className="secondary" onClick={stock.reload}>
          최신 가용 수량 확인
        </button>
      </fieldset>
    </FormPanel>
  );
}
function ReservationDetail({
  row,
  items,
  close,
  refresh,
  changed,
}: {
  row: Reservation;
  items: Item[];
  close: () => void;
  refresh: () => void;
  changed: (row: Reservation) => void;
}) {
  const [reason, setReason] = useState("");
  const [source, setSource] = useState("");
  const sources = useWmsQuery<ReservationSources>("/reservation-sources");
  const preview = useWmsQuery<{
    matches: boolean;
    negativeWarnings: {
      itemCode: string;
      lotNo: string;
      after: string;
      unit: string;
    }[];
  }>(
    source
      ? `/reservations/${row.id}/shipment-preview?sourceKey=${encodeURIComponent(source)}`
      : null,
  );
  const command = useWmsCommand();
  const guard = useDiscardGuard(!!reason || !!source);
  const fg = row.lines.every(
    (l) => items.find((x) => x.id === l.itemId)?.itemClass === "FG",
  );
  async function act(action: string, body: object) {
    const r = await command.send<Reservation>(
      `/reservations/${row.id}/${action}`,
      { expectedVersion: row.version, ...body },
    );
    if (r) {
      setReason("");
      setSource("");
      changed(r);
    } else {
      sources.reload();
      preview.reload();
    }
  }
  const selected = sources.data?.shipments.find((s) => s.sourceKey === source);
  return (
    <DetailPanel wide title={row.reservationNo} onClose={close} guard={guard}>
      <Badge>{states[row.status]}</Badge>
      <p>
        참고 출하지시 {row.shipmentOrderRef ?? "없음"} ·{" "}
        {comparison[row.shipmentOrderComparison.state] ??
          row.shipmentOrderState}
      </p>
      {row.shipmentOrderComparison.lines.map((l) => (
        <p key={l.itemCode}>
          {l.itemCode}: 예약 {num(l.reservedQty)} / 지시 {num(l.orderQty)}{" "}
          {l.unit}
        </p>
      ))}
      {row.lines.map((l) => (
        <section className="wms-operation-line" key={l.id}>
          <h3>
            {items.find((x) => x.id === l.itemId)?.itemCode} ·{" "}
            {l.lotNo ?? "원자재"}
          </h3>
          <p>
            예약 명세 {num(l.quantity)} · 현재고 {num(l.onHand)} · 활성 예약{" "}
            {num(l.reservedQty)} · 예약 가능 {num(l.available)}{" "}
            {items.find((x) => x.id === l.itemId)?.baseUnit}
          </p>
          {Number(l.reservationShortage) > 0 && (
            <p role="status">
              예약 부족 {num(l.reservationShortage)}{" "}
              {items.find((x) => x.id === l.itemId)?.baseUnit}
            </p>
          )}
        </section>
      ))}
      <OperationError error={command.error ?? sources.error} retry={refresh} />
      <button
        className="secondary"
        disabled={command.pending}
        onClick={refresh}
      >
        서버 상태 다시 확인
      </button>
      {row.status === "ACTIVE" && (
        <fieldset disabled={command.pending} className="wms-operation-fields">
          <section>
            <Field
              label="예약 해제 사유"
              value={reason}
              maxLength={300}
              onChange={(e) => setReason(e.target.value)}
            />
            <p>해제는 원장을 바꾸지 않고 예약 가능 수량만 복원합니다.</p>
            <button
              disabled={!reason.trim()}
              onClick={() => void act("release", { reason })}
            >
              예약 해제
            </button>
          </section>
          {fg ? (
            <section>
              <h3>ERP 출하 연결·반영</h3>
              <p>
                ERP에서 먼저 출하를 확정하세요. 품목·수량·LOT·참고지시가 전량
                일치해야 소진합니다.
              </p>
              <label>
                확정 출하
                <select
                  disabled={!sources.data?.enabled}
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                >
                  <option value="">선택</option>
                  {sources.data?.shipments.map((s) => (
                    <option key={s.sourceKey} value={s.sourceKey}>
                      {s.shipmentNo} · {s.shipmentOrderNo}
                    </option>
                  ))}
                </select>
              </label>
              {!sources.data?.enabled && (
                <p>ERP 조회 불가 · 수동 예약 해제는 가능합니다.</p>
              )}
              {selected?.lines.map((l, i) => (
                <p key={i}>
                  {l.itemCode} {l.qty} {l.unit} · 팔레트{" "}
                  {l.packingNo ?? "미지정"}
                </p>
              ))}
              <OperationError error={preview.error} retry={preview.reload} />
              {preview.data?.matches && (
                <div role="status">
                  <p>전량 대조 일치. 반영 시 서버가 다시 검사합니다.</p>
                  {preview.data.negativeWarnings.map((w, i) => (
                    <p key={i}>
                      반영 후 음수 예상: {w.itemCode} {w.lotNo} {w.after}{" "}
                      {w.unit}
                    </p>
                  ))}
                </div>
              )}
              <button
                disabled={
                  !source ||
                  !preview.data?.matches ||
                  !!preview.error ||
                  !selected
                }
                onClick={() =>
                  void act("consume-shipment", { sourceKey: source })
                }
              >
                출하 연결·반영 확정
              </button>
              <p>
                <Link to="/wms/sources">기존 원천 반영</Link>을 별도로 실행하면
                예약은 남습니다. 자동으로 대신 반영하지 않습니다.
              </p>
            </section>
          ) : (
            <p>
              원자재 예약은 등록·해제만 지원하며 고객 출하 연결 대상이 아닙니다.
            </p>
          )}
        </fieldset>
      )}
      {row.reason && <p>사유: {row.reason}</p>}
      {row.shipmentSourceKey && <p>소진 출하: {row.shipmentSourceKey}</p>}
      {row.stockDocumentId && (
        <Link to={`/wms/documents?open=${row.stockDocumentId}`}>
          출고 전표 보기
        </Link>
      )}{" "}
      <Link to="/wms/stock">재고 확인</Link>
    </DetailPanel>
  );
}
