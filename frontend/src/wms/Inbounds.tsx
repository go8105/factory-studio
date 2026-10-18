import { useEffect, useState } from "react";
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
import {
  ModuleOff,
  moduleOff,
  num,
  time,
  type Item,
  type Location,
  type Source,
  type Warehouse,
} from "./common";
import {
  OperationError,
  noticeKinds,
  remainder,
  states,
  useWmsCommand,
  useWmsQuery,
  type Inbound,
  type NoticeKind,
  type Page,
} from "./operations";
import "./Operations.css";

type DraftLine = {
  itemId: string;
  lotNo: string;
  expectedQty: string;
  normalLocationId: string;
  quarantineLocationId: string;
};
const emptyLine = (): DraftLine => ({
  itemId: "",
  lotNo: "",
  expectedQty: "",
  normalLocationId: "",
  quarantineLocationId: "",
});
export function Inbounds() {
  const [params, setParams] = useSearchParams();
  const query = new URLSearchParams(params);
  query.delete("open");
  const list = useWmsQuery<Page<Inbound>>(`/inbound-notices?${query}`);
  const houses = useWmsQuery<Warehouse[]>("/warehouses");
  const items = useWmsQuery<Item[]>("/items");
  const open = params.get("open");
  const detail = useWmsQuery<Inbound>(
    open && open !== "new" ? `/inbound-notices/${open}` : null,
  );
  const set = (name: string, value: string) =>
    setParams((p) => {
      if (value) p.set(name, value);
      else p.delete(name);
      if (name !== "open" && name !== "page") p.delete("page");
      return p;
    });
  const close = () => set("open", "");
  const refresh = () => {
    list.reload();
    detail.reload();
  };
  if (moduleOff(list.error)) return <ModuleOff />;
  return (
    <div className="page-fill">
      <PageTitle
        id="W-08"
        title="입고 예정·검수"
        subtitle="도착은 상태만 기록합니다. 검수 확정 때 정상·격리 재고를 반영합니다"
        help="wms/w-08"
      />
      <div className="filter-bar">
        <label>
          구분
          <select
            value={params.get("noticeKind") ?? ""}
            onChange={(e) => set("noticeKind", e.target.value)}
          >
            <option value="">전체</option>
            {(["PURCHASE", "PO", "SALES_RETURN", "SUBCONTRACT"] as const).map(
              (k) => (
                <option key={k} value={k}>
                  {noticeKinds[k]}
                </option>
              ),
            )}
          </select>
        </label>
        <label>
          상태
          <select
            value={params.get("status") ?? ""}
            onChange={(e) => set("status", e.target.value)}
          >
            <option value="">전체</option>
            {["PLANNED", "ARRIVED", "INSPECTED", "CANCELLED"].map((s) => (
              <option key={s} value={s}>
                {states[s]}
              </option>
            ))}
          </select>
        </label>
        <label>
          창고
          <select
            value={params.get("warehouseId") ?? ""}
            onChange={(e) => set("warehouseId", e.target.value)}
          >
            <option value="">전체</option>
            {houses.data?.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name}
              </option>
            ))}
          </select>
        </label>
        <Field
          label="예정일 시작"
          type="date"
          value={params.get("expectedFrom") ?? ""}
          onChange={(e) => set("expectedFrom", e.target.value)}
        />
        <Field
          label="예정일 끝"
          type="date"
          value={params.get("expectedTo") ?? ""}
          onChange={(e) => set("expectedTo", e.target.value)}
        />
        <button onClick={() => set("open", "new")}>입고 예정 등록</button>
      </div>
      <OperationError
        error={list.error ?? houses.error ?? items.error}
        retry={list.reload}
      />
      {list.data ? (
        <DataTable
          caption="입고 예정"
          rows={list.data.rows}
          columns={[
            { key: "noticeNo", label: "번호" },
            {
              key: "noticeKind",
              label: "구분",
              render: (r) => (
                <Badge
                  tone={r.noticeKind === "SALES_RETURN" ? "issue" : "normal"}
                >
                  {noticeKinds[r.noticeKind] ?? r.noticeKind}
                </Badge>
              ),
            },
            { key: "expectedOn", label: "예정일" },
            { key: "vehicleNo", label: "차량" },
            {
              key: "status",
              label: "상태",
              render: (r) => <Badge>{states[r.status]}</Badge>,
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
      {open === "new" && houses.data && items.data && (
        <NoticeForm
          key="new"
          houses={houses.data}
          items={items.data}
          onClose={close}
          onSaved={(n) => {
            list.reload();
            set("open", String(n.id));
          }}
        />
      )}
      {open && open !== "new" && detail.data && houses.data && items.data && (
        <NoticeDetail
          key={`${detail.data.id}:${detail.data.version}`}
          row={detail.data}
          houses={houses.data}
          items={items.data}
          close={close}
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
function NoticeForm({
  row,
  houses,
  items,
  onClose,
  onSaved,
}: {
  row?: Inbound;
  houses: Warehouse[];
  items: Item[];
  onClose: () => void;
  onSaved: (row: Inbound) => void;
}) {
  const [businessKey, setBusiness] = useState(row?.businessKey ?? "");
  const [noticeKind, setNoticeKind] = useState<NoticeKind>(
    row?.noticeKind ?? "PURCHASE",
  );
  const [warehouseId, setWarehouse] = useState(
    String(
      row?.warehouseId ??
        houses.find((h) => h.isActive && h.purpose === "RAW")?.id ??
        houses.find((h) => h.isActive)?.id ??
        "",
    ),
  );
  const [expectedOn, setDate] = useState(
    row?.expectedOn ??
      new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Seoul" }),
  );
  const [vehicleNo, setVehicle] = useState(row?.vehicleNo ?? "");
  const [partnerRef, setPartner] = useState(row?.partnerRef ?? "");
  const [lines, setLines] = useState<DraftLine[]>(
    row?.lines.map((l) => ({
      itemId: String(l.itemId),
      lotNo: l.lotNo ?? "",
      expectedQty: l.expectedQty,
      normalLocationId: String(l.normalLocationId),
      quarantineLocationId: l.quarantineLocationId
        ? String(l.quarantineLocationId)
        : "",
    })) ?? [emptyLine()],
  );
  const [dirty, setDirty] = useState(false);
  const guard = useDiscardGuard(dirty);
  const locations = useWmsQuery<Location[]>(
    warehouseId ? `/warehouses/${warehouseId}/locations` : null,
  );
  const command = useWmsCommand();
  const wh = houses.find((h) => h.id === Number(warehouseId));
  useEffect(() => {
    if (row || !locations.data || locations.data.length === 0) return;
    const receivingLoc = locations.data.find(
      (x) => x.isActive && x.locationType === "RECEIVING",
    );
    const defaultLoc =
      receivingLoc ??
      locations.data.find(
        (x) => x.isActive && x.isDefault && x.locationType === "NORMAL",
      ) ??
      locations.data.find((x) => x.isActive && x.locationType === "NORMAL");
    if (!defaultLoc) return;
    setLines((xs) =>
      xs.map((l) => {
        const valid = locations.data?.some(
          (loc) => String(loc.id) === l.normalLocationId,
        );
        return valid && l.normalLocationId
          ? l
          : { ...l, normalLocationId: String(defaultLoc.id) };
      }),
    );
  }, [locations.data, row]);
  const update = (i: number, patch: Partial<DraftLine>) => {
    setDirty(true);
    setLines((xs) => xs.map((x, j) => (i === j ? { ...x, ...patch } : x)));
  };
  return (
    <FormPanel
      wide
      title={row ? `${row.noticeNo} 편집` : "입고 예정 등록"}
      guard={guard}
      onClose={onClose}
      onSubmit={(e) => {
        e.preventDefault();
        void command
          .send<Inbound>(
            row ? `/inbound-notices/${row.id}` : "/inbound-notices",
            {
              ...(row ? { expectedVersion: row.version } : { businessKey }),
              warehouseId: Number(warehouseId),
              noticeKind,
              expectedOn,
              vehicleNo: vehicleNo || null,
              partnerRef: partnerRef || null,
              lines: lines.map((l) => ({
                itemId: Number(l.itemId),
                lotNo: l.lotNo || null,
                expectedQty: l.expectedQty,
                normalLocationId: Number(l.normalLocationId),
                quarantineLocationId: l.quarantineLocationId
                  ? Number(l.quarantineLocationId)
                  : null,
              })),
            },
            row ? "PATCH" : "POST",
          )
          .then((n) => {
            if (n) {
              setDirty(false);
              onSaved(n);
            }
          });
      }}
      actions={
        <button disabled={command.pending} type="submit">
          {row ? "예정 저장" : "예정 등록"}
        </button>
      }
    >
      <OperationError error={command.error ?? locations.error} />
      <fieldset
        disabled={command.pending}
        className="wms-operation-fields"
        onChange={() => setDirty(true)}
      >
        <Field
          label="업무 중복 방지 번호"
          value={businessKey}
          maxLength={100}
          required
          disabled={!!row}
          onChange={(e) => setBusiness(e.target.value)}
        />
        <label>
          입고 구분
          <select
            required
            value={noticeKind}
            onChange={(e) => setNoticeKind(e.target.value as NoticeKind)}
          >
            {(["PURCHASE", "PO", "SALES_RETURN", "SUBCONTRACT"] as const).map(
              (k) => (
                <option key={k} value={k}>
                  {noticeKinds[k]}
                </option>
              ),
            )}
          </select>
        </label>
        <label>
          창고
          <select
            required
            value={warehouseId}
            onChange={(e) => {
              setWarehouse(e.target.value);
              setLines([emptyLine()]);
            }}
          >
            {houses
              .filter((h) => h.isActive)
              .map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name}
                </option>
              ))}
          </select>
        </label>
        <Field
          label="예정일"
          type="date"
          value={expectedOn}
          required
          onChange={(e) => setDate(e.target.value)}
        />
        <Field
          label="차량"
          value={vehicleNo}
          maxLength={40}
          onChange={(e) => setVehicle(e.target.value)}
        />
        <Field
          label="공급처 참고 코드"
          value={partnerRef}
          maxLength={100}
          onChange={(e) => setPartner(e.target.value)}
        />
        <p className="muted">
          도착 후에는 예정 내용을 바꿀 수 없습니다. 수량은 각 품목의 기본 단위로
          입력합니다.
        </p>
        {lines.map((l, i) => {
          const selectedItem = items.find(
            (x) => String(x.id) === String(l.itemId),
          );
          const isLotTracked = Boolean(selectedItem?.lotTracked);
          return (
            <fieldset key={i} className="wms-operation-line">
              <legend>입고 명세 {i + 1}</legend>
              <label>
                품목
                <select
                  required
                  value={l.itemId}
                  onChange={(e) => {
                    const newItem = items.find(
                      (x) => String(x.id) === e.target.value,
                    );
                    update(i, {
                      itemId: e.target.value,
                      lotNo: newItem?.lotTracked ? l.lotNo : "",
                    });
                  }}
                >
                  <option value="">선택</option>
                  {items
                    .filter((x) => x.isActive && x.itemClass === wh?.purpose)
                    .map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.itemCode} · {x.baseUnit}
                      </option>
                    ))}
                </select>
              </label>
              {isLotTracked && (
                <Field
                  label="LOT"
                  required
                  value={l.lotNo}
                  maxLength={50}
                  onChange={(e) => update(i, { lotNo: e.target.value })}
                />
              )}
              <Field
                label="예정 수량"
                required
                inputMode="decimal"
                value={l.expectedQty}
                onChange={(e) => update(i, { expectedQty: e.target.value })}
              />
              {(["normalLocationId", "quarantineLocationId"] as const).map(
                (key) => (
                  <label key={key}>
                    {key === "normalLocationId" ? "정상 위치" : "격리 위치"}
                    <select
                      required={key === "normalLocationId"}
                      value={l[key]}
                      onChange={(e) => update(i, { [key]: e.target.value })}
                    >
                      <option value="">
                        {key === "normalLocationId" ? "선택" : "사용 안 함"}
                      </option>
                      {locations.data
                        ?.filter(
                          (x) =>
                            x.isActive &&
                            (key === "normalLocationId"
                              ? (x.locationType ?? "NORMAL") === "NORMAL" ||
                                x.locationType === "RECEIVING"
                              : (x.locationType ?? "NORMAL") === "QUARANTINE"),
                        )
                        .map((x) => (
                          <option key={x.id} value={x.id}>
                            {x.code} {x.name}
                            {x.locationType === "RECEIVING" ? " [입고장]" : ""}
                          </option>
                        ))}
                    </select>
                  </label>
                ),
              )}
              <button
                type="button"
                className="link-button"
                disabled={lines.length === 1}
                onClick={() => {
                  setDirty(true);
                  setLines((xs) => xs.filter((_, j) => j !== i));
                }}
              >
                명세 {i + 1} 삭제
              </button>
            </fieldset>
          );
        })}
        <button
          type="button"
          className="secondary"
          disabled={lines.length >= 100}
          onClick={() => {
            setDirty(true);
            setLines((xs) => [...xs, emptyLine()]);
          }}
        >
          명세 추가
        </button>
      </fieldset>
    </FormPanel>
  );
}
function NoticeDetail({
  row,
  houses,
  items,
  close,
  refresh,
  changed,
}: {
  row: Inbound;
  houses: Warehouse[];
  items: Item[];
  close: () => void;
  refresh: () => void;
  changed: (row: Inbound) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [reason, setReason] = useState("");
  const [source, setSource] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [values, setValues] = useState(
    row.lines.map((l) => ({
      lineId: l.id,
      acceptedQty: l.acceptedQty ?? l.expectedQty,
      quarantinedQty: l.quarantinedQty ?? "0",
      reason: l.reason ?? "",
    })),
  );
  const [dirty, setDirty] = useState(false);
  const guard = useDiscardGuard(dirty);
  const command = useWmsCommand();
  const sources = useWmsQuery<{ disabled: boolean; rows: Source[] }>(
    "/sources?kind=ERP_PURCHASE&state=all",
  );
  const locations = useWmsQuery<Location[]>(
    `/warehouses/${row.warehouseId}/locations`,
  );
  const mutable = row.status === "PLANNED" || row.status === "ARRIVED";
  async function act(action: string, body: object = {}) {
    const result = await command.send<Inbound>(
      `/inbound-notices/${row.id}/${action}`,
      { expectedVersion: row.version, ...body },
    );
    if (result) {
      setDirty(false);
      changed(result);
    }
  }
  if (editing)
    return (
      <NoticeForm
        row={row}
        houses={houses}
        items={items}
        onClose={() => setEditing(false)}
        onSaved={(saved) => {
          setEditing(false);
          changed(saved);
        }}
      />
    );
  const sourceDisabled = sources.data?.disabled || !sources.data;
  const inspection = values.map((v, i) => ({
    ...v,
    shortageQty: remainder(
      row.lines[i].expectedQty,
      v.acceptedQty,
      v.quarantinedQty,
    ),
  }));
  return (
    <DetailPanel title={row.noticeNo} wide guard={guard} onClose={close}>
      <Badge>{states[row.status]}</Badge>{" "}
      <Badge tone={row.noticeKind === "SALES_RETURN" ? "issue" : "normal"}>
        {noticeKinds[row.noticeKind] ?? row.noticeKind}
      </Badge>
      <p>
        구분 {noticeKinds[row.noticeKind] ?? row.noticeKind} · 예정{" "}
        {row.expectedOn} · {row.vehicleNo || "차량 미지정"}
      </p>
      <p>
        도착 {row.arrivedAt ? time(row.arrivedAt) : "—"} · 검수{" "}
        {row.inspectedAt ? time(row.inspectedAt) : "—"}
      </p>
      <p>
        원천: {row.sourceClaim?.sourceKey ?? "수동 입고"} ·{" "}
        {row.sourceState === "unavailable"
          ? "ERP 조회 불가"
          : row.sourceState === "cancelled"
            ? "매입 취소됨"
            : (row.sourceClaim?.status ?? "미연결")}
      </p>
      {row.sourceState === "cancelled" && (
        <p role="alert">
          ERP 매입이 취소됐습니다. 검수 재고는 자동 취소되지 않습니다.{" "}
          <Link to="/wms/documents">실물 정정 전표</Link>에서 처리하세요.
        </p>
      )}
      <OperationError error={command.error ?? sources.error} retry={refresh} />
      <button
        className="secondary"
        disabled={command.pending}
        onClick={refresh}
      >
        서버 상태 다시 확인
      </button>
      <p className="muted">
        응답이 불확실하면 서버 상태를 다시 확인하세요. 같은 입력으로 재시도하면
        중복 반영하지 않습니다.
      </p>
      <fieldset disabled={command.pending} className="wms-operation-fields">
        {row.status === "PLANNED" && (
          <div className="row-actions">
            <button onClick={() => setEditing(true)}>예정 편집</button>
            <button onClick={() => void act("arrive")}>도착 처리</button>
            <Link to={`/factory?inbound=${row.id}`}>3D 트럭 보기</Link>
          </div>
        )}
        {row.lines.map((l, i) => {
          const item = items.find((x) => x.id === l.itemId);
          const v = values[i];
          return (
            <fieldset className="wms-operation-line" key={l.id}>
              <legend>
                {item?.itemCode} · {item?.baseUnit}{" "}
                {l.lotNo ? `· LOT ${l.lotNo}` : ""}
              </legend>
              <p>
                예정 {num(l.expectedQty)} · 정상 위치{" "}
                {locations.data?.find((x) => x.id === l.normalLocationId)?.code}{" "}
                · 격리 위치{" "}
                {locations.data?.find((x) => x.id === l.quarantineLocationId)
                  ?.code ?? "없음"}
              </p>
              {row.status === "ARRIVED" ? (
                <>
                  <div className="wms-quantity-grid">
                    {(["acceptedQty", "quarantinedQty"] as const).map((k) => (
                      <Field
                        key={k}
                        label={k === "acceptedQty" ? "합격" : "격리"}
                        value={v[k]}
                        inputMode="decimal"
                        onChange={(e) => {
                          setDirty(true);
                          setConfirm(false);
                          setValues((xs) =>
                            xs.map((x, j) =>
                              i === j ? { ...x, [k]: e.target.value } : x,
                            ),
                          );
                        }}
                      />
                    ))}
                    <p>
                      부족{" "}
                      {inspection[i].shortageQty === null
                        ? "수량 오류"
                        : num(inspection[i].shortageQty!)}{" "}
                      {item?.baseUnit}
                    </p>
                  </div>
                  <Field
                    label="검수 사유"
                    value={v.reason}
                    maxLength={300}
                    onChange={(e) => {
                      setDirty(true);
                      setConfirm(false);
                      setValues((xs) =>
                        xs.map((x, j) =>
                          i === j ? { ...x, reason: e.target.value } : x,
                        ),
                      );
                    }}
                  />
                </>
              ) : (
                row.status === "INSPECTED" && (
                  <p>
                    합격 {num(l.acceptedQty ?? "0")} · 격리{" "}
                    {num(l.quarantinedQty ?? "0")} · 부족{" "}
                    {num(l.shortageQty ?? "0")} · {l.reason}
                  </p>
                )
              )}
            </fieldset>
          );
        })}
        {row.status === "ARRIVED" && (
          <>
            {row.sourceClaim && sourceDisabled && (
              <p role="status">
                ERP를 켜야 연결 원천을 검증하고 확정할 수 있습니다.
              </p>
            )}
            {!confirm ? (
              <button
                disabled={
                  inspection.some((l) => l.shortageQty === null) ||
                  (!!row.sourceClaim && !!sourceDisabled)
                }
                onClick={() => setConfirm(true)}
              >
                검수 결과 확인
              </button>
            ) : (
              <section className="panel" role="status">
                <p>확정 후 검수 수량은 수정할 수 없습니다.</p>
                {inspection.map((v, i) => (
                  <p key={v.lineId}>
                    {items.find((x) => x.id === row.lines[i].itemId)?.itemCode}:
                    정상 +{v.acceptedQty} · 격리 +{v.quarantinedQty} · 부족{" "}
                    {v.shortageQty}{" "}
                    {items.find((x) => x.id === row.lines[i].itemId)?.baseUnit}
                  </p>
                ))}
                {inspection.every(
                  (v) =>
                    Number(v.acceptedQty) === 0 &&
                    Number(v.quarantinedQty) === 0,
                ) && <p>입고 재고 0, 검수 완료 기록만 생성합니다.</p>}
                <button
                  onClick={() => void act("inspect", { lines: inspection })}
                >
                  검수 확정
                </button>
                <button className="secondary" onClick={() => setConfirm(false)}>
                  입력으로 돌아가기
                </button>
              </section>
            )}
          </>
        )}
        {!row.sourceClaim && row.status !== "CANCELLED" && (
          <section>
            <h3>
              {row.status === "INSPECTED"
                ? "ERP 매입 대사 연결 · 추가 입고 없음"
                : "ERP 매입 연결"}
            </h3>
            <p>
              예정 수량과 환산 수량이 일치하는 미반영 매입만 연결할 수 있습니다.
            </p>
            <label>
              확정 매입
              <select
                value={source}
                disabled={!!sourceDisabled}
                onChange={(e) => setSource(e.target.value)}
              >
                <option value="">선택</option>
                {sources.data?.rows
                  ?.filter((s) => s.state === "pending")
                  .map((s) => (
                    <option key={s.sourceKey} value={s.sourceKey}>
                      {s.sourceRef} ·{" "}
                      {s.lines
                        .map((l) => `${l.itemCode} ${l.qty} ${l.unit}`)
                        .join(", ")}
                    </option>
                  ))}
              </select>
            </label>
            {sourceDisabled && (
              <p>ERP 꺼짐 또는 원천 조회 중입니다. 수동 입고는 가능합니다.</p>
            )}
            <button
              disabled={!source || !!sourceDisabled}
              onClick={() => void act("source-link", { sourceKey: source })}
            >
              매입 연결
            </button>
          </section>
        )}
        {mutable && (
          <section>
            <Field
              label="취소·연결 해제 사유"
              value={reason}
              maxLength={300}
              onChange={(e) => setReason(e.target.value)}
            />
            {row.sourceClaim && (
              <button
                disabled={!reason.trim()}
                className="secondary"
                onClick={() => void act("source-unlink", { reason })}
              >
                매입 연결 해제
              </button>
            )}
            <button
              disabled={!reason.trim()}
              className="secondary"
              onClick={() => void act("cancel", { reason })}
            >
              입고 예정 취소
            </button>
          </section>
        )}
        {row.stockDocumentId && (
          <Link to={`/wms/documents?open=${row.stockDocumentId}`}>
            검수 전표 보기
          </Link>
        )}{" "}
        <Link to="/wms/stock">재고 확인</Link>
      </fieldset>
    </DetailPanel>
  );
}
