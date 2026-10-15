// W-10 LOT·보류 — LOT 목록·원장 집계 재고·상세·등록 (DSN-13 F13·F36·F38·F53).
// LOT 수량은 wms.lot에 저장하지 않고 원장(stock_move) 합계로 계산한다(AGENTS §3).
// 보류 걸기·해제 기능은 다음 단계(B-3)에서 구현하며, 이번 단계에서는 상태 표시만 제공한다.
import { useEffect, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  Badge,
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import {
  fieldErrors,
  LOT_ORIGIN_LABEL,
  ModuleOff,
  moduleOff,
  num,
  PURPOSE_LABEL,
  time,
  useLists,
  useSend,
  WMS,
  type Item,
  type LotHold,
  type LotOrigin,
  type LotRow,
  type LotStatus,
} from "./common";

type LotDraft = {
  itemId: number | "";
  lotNo: string;
  receivedOn: string;
  expiryDate: string;
  supplierLotNo: string;
  origin: LotOrigin;
};

function todayIso(): string {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

const EMPTY_DRAFT: LotDraft = {
  itemId: "",
  lotNo: "",
  receivedOn: todayIso(),
  expiryDate: "",
  supplierLotNo: "",
  origin: "RECEIPT",
};

const LIMIT = 50;

export function Lots() {
  const { fail } = useSession();
  const { data: itemData, error: itemError } = useLists<[Item[]]>(["/items"]);
  const items = itemData?.[0] ?? [];

  // 페이징 및 필터 상태
  const [offset, setOffset] = useState(0);
  const [itemFilter, setItemFilter] = useState<number | "">("");
  const [statusFilter, setStatusFilter] = useState<LotStatus | "">("");
  const [keyword, setKeyword] = useState("");
  const [expiredOnly, setExpiredOnly] = useState(false);

  // LOT 목록 데이터 상태
  const [envelope, setEnvelope] = useState<{
    data: LotRow[];
    page?: { offset: number; limit: number; total: number };
  }>();
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<unknown>();
  const [reloadTrigger, setReloadTrigger] = useState(0);

  // 패널 상태
  const [panel, setPanel] = useState<
    { kind: "create" } | { kind: "detail"; id: number } | null
  >(null);

  // 상세 단건 데이터
  const [detailLot, setDetailLot] = useState<LotRow>();
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<unknown>();

  // 등록 폼 상태
  const [draft, setDraft] = useState<LotDraft>(EMPTY_DRAFT);
  const [initialDraft, setInitialDraft] = useState<LotDraft>(EMPTY_DRAFT);
  const {
    send,
    pending: savePending,
    error: saveError,
    setError: setSaveError,
  } = useSend(() => setReloadTrigger((v) => v + 1));

  const guard = useDiscardGuard(
    panel?.kind === "create" &&
      JSON.stringify(draft) !== JSON.stringify(initialDraft),
  );

  const errors = fieldErrors(saveError);

  // 목록 조회
  useEffect(() => {
    const controller = new AbortController();
    setListLoading(true);
    setListError(undefined);

    const params = new URLSearchParams({
      offset: String(offset),
      limit: String(LIMIT),
    });
    if (itemFilter) params.set("item_id", String(itemFilter));
    if (statusFilter) params.set("status", statusFilter);
    if (keyword.trim()) params.set("keyword", keyword.trim());
    if (expiredOnly) params.set("expired_only", "true");

    api<LotRow[]>(`${WMS}/lots?${params.toString()}`, {
      signal: controller.signal,
    })
      .then((res) => {
        setEnvelope(res);
        setListLoading(false);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setListError(err);
        setListLoading(false);
        if (err instanceof ApiError && [401, 410].includes(err.status))
          fail(err);
      });

    return () => controller.abort();
  }, [
    offset,
    itemFilter,
    statusFilter,
    keyword,
    expiredOnly,
    reloadTrigger,
    fail,
  ]);

  // 상세 조회
  useEffect(() => {
    if (panel?.kind !== "detail") {
      setDetailLot(undefined);
      return;
    }
    const controller = new AbortController();
    setDetailLoading(true);
    setDetailError(undefined);

    api<LotRow>(`${WMS}/lots/${panel.id}`, { signal: controller.signal })
      .then((res) => {
        setDetailLot(res.data);
        setDetailLoading(false);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setDetailError(err);
        setDetailLoading(false);
        if (err instanceof ApiError && [401, 410].includes(err.status))
          fail(err);
      });

    return () => controller.abort();
  }, [panel, fail]);

  if (moduleOff(itemError) || moduleOff(listError)) return <ModuleOff />;

  function openCreate() {
    const init: LotDraft = {
      ...EMPTY_DRAFT,
      receivedOn: todayIso(),
    };
    setDraft(init);
    setInitialDraft(init);
    setSaveError(undefined);
    setPanel({ kind: "create" });
  }

  function openDetail(id: number) {
    setPanel({ kind: "detail", id });
  }

  function handleItemChange(itemIdNum: number | "") {
    if (!itemIdNum) {
      setDraft((prev) => ({ ...prev, itemId: "" }));
      return;
    }
    const selectedItem = items.find((i) => i.id === itemIdNum);
    let nextExpiry = draft.expiryDate;
    if (selectedItem?.shelfLifeDays && draft.receivedOn && !draft.expiryDate) {
      const recDate = new Date(draft.receivedOn);
      recDate.setDate(recDate.getDate() + selectedItem.shelfLifeDays);
      const y = recDate.getFullYear();
      const m = String(recDate.getMonth() + 1).padStart(2, "0");
      const d = String(recDate.getDate()).padStart(2, "0");
      nextExpiry = `${y}-${m}-${d}`;
    }
    setDraft((prev) => ({
      ...prev,
      itemId: itemIdNum,
      expiryDate: nextExpiry,
    }));
  }

  async function submitCreate(e: FormEvent) {
    e.preventDefault();
    if (!draft.itemId) return;

    const saved = await send("/lots", "POST", {
      itemId: draft.itemId,
      lotNo: draft.lotNo.trim().toUpperCase(),
      receivedOn: draft.receivedOn,
      expiryDate: draft.expiryDate ? draft.expiryDate : null,
      supplierLotNo: draft.supplierLotNo.trim() || null,
      origin: draft.origin,
    });
    if (saved) {
      setPanel(null);
    }
  }

  const columns: Column<LotRow>[] = [
    { key: "lotNo", label: "LOT 번호" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={panel?.kind === "detail" && panel.id === r.id}
          onClick={() => guard.guard(() => openDetail(r.id))}
        >
          상세
        </button>
      ),
    },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <>
          {r.status === "AVAILABLE" && <Badge>가용</Badge>}
          {r.status === "HOLD" && (
            <span title={r.currentHoldReason || "보류 중"}>
              <Badge tone="issue">보류</Badge>
            </span>
          )}
          {r.status === "EXPIRED" && <Badge tone="issue">만료</Badge>}
        </>
      ),
    },
    {
      key: "itemCode",
      label: "품목",
      render: (r) => (
        <span>
          <strong>{r.itemCode}</strong> {r.itemName}
        </span>
      ),
    },
    {
      key: "itemClass",
      label: "분류",
      render: (r) => PURPOSE_LABEL[r.itemClass],
    },
    {
      key: "qtyOnHand",
      label: "현재고 (원장)",
      render: (r) => (
        <strong>
          {num(r.qtyOnHand)} {r.baseUnit}
        </strong>
      ),
    },
    { key: "receivedOn", label: "입고일" },
    {
      key: "expiryDate",
      label: "유효기간",
      render: (r) =>
        r.expiryDate ? (
          <span>
            {r.expiryDate} {r.isExpired && <Badge tone="issue">만료</Badge>}
          </span>
        ) : (
          "—"
        ),
    },
    {
      key: "supplierLotNo",
      label: "공급처 LOT",
      render: (r) => r.supplierLotNo || "—",
    },
    {
      key: "origin",
      label: "출처",
      render: (r) => LOT_ORIGIN_LABEL[r.origin],
    },
  ];

  const rows = envelope?.data ?? [];
  const total = envelope?.page?.total ?? 0;

  return (
    <div className="page-fill">
      <PageTitle
        id="W-10"
        title="LOT·보류"
        subtitle="품목별 LOT 번호와 유효기간·보류 상태를 관리하고 원장 재고를 확인합니다"
        help="wms/w-10"
        actions={
          <button
            type="button"
            aria-pressed={panel?.kind === "create"}
            onClick={() => guard.guard(openCreate)}
          >
            LOT 등록
          </button>
        }
      />

      <div className="filter-bar" role="search" aria-label="LOT 검색 필터">
        <div className="filter-group">
          <label htmlFor="lot-item-filter">품목</label>
          <select
            id="lot-item-filter"
            value={itemFilter}
            onChange={(e) => {
              setItemFilter(e.target.value ? Number(e.target.value) : "");
              setOffset(0);
            }}
          >
            <option value="">전체 품목</option>
            {items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.itemCode} ({i.name})
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="lot-status-filter">상태</label>
          <select
            id="lot-status-filter"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as LotStatus | "");
              setOffset(0);
            }}
          >
            <option value="">전체 상태</option>
            <option value="AVAILABLE">가용</option>
            <option value="HOLD">보류</option>
            <option value="EXPIRED">만료</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="lot-search-keyword">검색어</label>
          <input
            id="lot-search-keyword"
            type="search"
            placeholder="품목코드·명, LOT 번호, 공급처 LOT"
            value={keyword}
            onChange={(e) => {
              setKeyword(e.target.value);
              setOffset(0);
            }}
          />
        </div>

        <label className="inline-check">
          <input
            type="checkbox"
            checked={expiredOnly}
            onChange={(e) => {
              setExpiredOnly(e.target.checked);
              setOffset(0);
            }}
          />
          만료만 보기
        </label>
      </div>

      <ErrorNotice
        error={listError}
        retry={() => setReloadTrigger((v) => v + 1)}
      />

      {listLoading && !envelope ? (
        <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={rows}
              columns={columns}
              caption="LOT 목록"
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason="등록된 LOT이 없습니다. LOT을 등록하거나 입고 전표를 작성하세요."
                  action="LOT 등록"
                  onAction={() => guard.guard(openCreate)}
                />
              }
            />
          </section>

          {panel?.kind === "create" && (
            <FormPanel
              title="LOT 등록"
              guard={guard}
              onClose={() => setPanel(null)}
              onSubmit={(e) => void submitCreate(e)}
              actions={
                <>
                  <button
                    type="submit"
                    disabled={
                      savePending || !draft.itemId || !draft.lotNo.trim()
                    }
                    aria-busy={savePending}
                  >
                    등록
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => setPanel(null))}
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />

              <div className="field">
                <label htmlFor="lot-form-item">품목</label>
                <select
                  id="lot-form-item"
                  value={draft.itemId}
                  required
                  onChange={(e) =>
                    handleItemChange(
                      e.target.value ? Number(e.target.value) : "",
                    )
                  }
                >
                  <option value="">품목을 선택하세요</option>
                  {items.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.itemCode} ({i.name}) · {PURPOSE_LABEL[i.itemClass]}
                      {i.lotTracked ? " [LOT추적]" : ""}
                    </option>
                  ))}
                </select>
                {errors.item_id && (
                  <p className="field-error" role="alert">
                    {errors.item_id}
                  </p>
                )}
              </div>

              <Field
                label="LOT 번호"
                value={draft.lotNo}
                required
                maxLength={60}
                placeholder="예: LOT-20261015-001"
                error={errors.lot_no}
                onChange={(e) =>
                  setDraft({ ...draft, lotNo: e.target.value.toUpperCase() })
                }
              />

              <div className="field-row">
                <Field
                  label="입고일"
                  type="date"
                  value={draft.receivedOn}
                  required
                  error={errors.received_on}
                  onChange={(e) =>
                    setDraft({ ...draft, receivedOn: e.target.value })
                  }
                />
                <Field
                  label="유효기간"
                  type="date"
                  value={draft.expiryDate}
                  error={errors.expiry_date}
                  onChange={(e) =>
                    setDraft({ ...draft, expiryDate: e.target.value })
                  }
                />
              </div>

              <Field
                label="공급처 LOT 번호"
                value={draft.supplierLotNo}
                maxLength={60}
                placeholder="원자재 공급사 번호 (선택)"
                error={errors.supplier_lot_no}
                onChange={(e) =>
                  setDraft({ ...draft, supplierLotNo: e.target.value })
                }
              />

              <div className="field">
                <label htmlFor="lot-form-origin">출처</label>
                <select
                  id="lot-form-origin"
                  value={draft.origin}
                  onChange={(e) =>
                    setDraft({ ...draft, origin: e.target.value as LotOrigin })
                  }
                >
                  <option value="RECEIPT">입고</option>
                  <option value="MES">생산</option>
                  <option value="RETURN">반품</option>
                  <option value="OPENING">기초</option>
                </select>
              </div>

              <p className="muted" role="note">
                LOT 번호 등록 후 입고·이동 전표 작성 시 원장 재고가 자동으로
                집계됩니다.
              </p>
            </FormPanel>
          )}

          {panel?.kind === "detail" && (
            <DetailPanel
              title={detailLot ? `${detailLot.lotNo} 상세` : "LOT 상세"}
              onClose={() => setPanel(null)}
              wide
            >
              <ErrorNotice error={detailError} />
              {detailLoading && !detailLot ? (
                <Loading />
              ) : !detailLot ? (
                <p className="muted">상세 정보를 불러올 수 없습니다.</p>
              ) : (
                <div className="detail-sections">
                  <section className="section-block" aria-label="기본 정보">
                    <h3>기본 정보</h3>
                    <dl className="property-list">
                      <div>
                        <dt>LOT 번호</dt>
                        <dd>
                          <strong>{detailLot.lotNo}</strong>
                        </dd>
                      </div>
                      <div>
                        <dt>품목</dt>
                        <dd>
                          {detailLot.itemCode} {detailLot.itemName} (
                          {PURPOSE_LABEL[detailLot.itemClass]})
                        </dd>
                      </div>
                      <div>
                        <dt>상태</dt>
                        <dd>
                          {detailLot.status === "AVAILABLE" && (
                            <Badge>가용</Badge>
                          )}
                          {detailLot.status === "HOLD" && (
                            <span
                              title={detailLot.currentHoldReason || "보류 중"}
                            >
                              <Badge tone="issue">보류</Badge>
                            </span>
                          )}
                          {detailLot.status === "EXPIRED" && (
                            <Badge tone="issue">만료</Badge>
                          )}
                          {detailLot.currentHoldReason && (
                            <span className="muted">
                              {" "}
                              ({detailLot.currentHoldReason})
                            </span>
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>출처</dt>
                        <dd>{LOT_ORIGIN_LABEL[detailLot.origin]}</dd>
                      </div>
                      <div>
                        <dt>입고일</dt>
                        <dd>{detailLot.receivedOn}</dd>
                      </div>
                      <div>
                        <dt>유효기간</dt>
                        <dd>
                          {detailLot.expiryDate ? (
                            <span>
                              {detailLot.expiryDate}{" "}
                              {detailLot.isExpired && (
                                <Badge tone="issue">만료</Badge>
                              )}
                            </span>
                          ) : (
                            "미지정"
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>공급처 LOT</dt>
                        <dd>{detailLot.supplierLotNo || "—"}</dd>
                      </div>
                      <div>
                        <dt>등록 시각</dt>
                        <dd>{time(detailLot.createdAt)}</dd>
                      </div>
                    </dl>
                  </section>

                  <section
                    className="section-block"
                    aria-label="원장 집계 현재고"
                  >
                    <h3>원장 집계 현재고</h3>
                    <p className="panel-summary-number">
                      총 재고:{" "}
                      <strong>
                        {num(detailLot.qtyOnHand)} {detailLot.baseUnit}
                      </strong>
                    </p>
                    <p className="muted" role="note">
                      재고 수량은 재고 이동 원장(stock_move)의 실시간
                      합계입니다.
                    </p>

                    <h4>위치별 재고 분포</h4>
                    {detailLot.locations && detailLot.locations.length > 0 ? (
                      <table className="compact-table">
                        <thead>
                          <tr>
                            <th scope="col">창고</th>
                            <th scope="col">위치</th>
                            <th scope="col" className="num">
                              현재고
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {detailLot.locations.map((loc) => (
                            <tr key={loc.locationId}>
                              <td>
                                {loc.warehouseCode} ({loc.warehouseName})
                              </td>
                              <td>
                                {loc.locationCode} ({loc.locationName})
                              </td>
                              <td className="num">
                                <strong>
                                  {num(loc.qtyOnHand)} {detailLot.baseUnit}
                                </strong>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <p className="muted">
                        보유 중인 위치가 없습니다 (재고 0 {detailLot.baseUnit}).
                      </p>
                    )}
                  </section>

                  <section className="section-block" aria-label="보류 이력">
                    <h3>보류 상태 및 이력</h3>
                    {detailLot.holds && detailLot.holds.length > 0 ? (
                      <table className="compact-table">
                        <thead>
                          <tr>
                            <th scope="col">구분</th>
                            <th scope="col">보류일시</th>
                            <th scope="col">해제일시</th>
                            <th scope="col">사유</th>
                            <th scope="col">상태</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detailLot.holds.map((h: LotHold) => (
                            <tr key={h.id}>
                              <td>{h.source}</td>
                              <td>{time(h.heldAt)}</td>
                              <td>{h.releasedAt ? time(h.releasedAt) : "—"}</td>
                              <td>{h.reason}</td>
                              <td>
                                {h.isActive ? (
                                  <Badge tone="issue">보류 중</Badge>
                                ) : (
                                  <Badge>해제됨</Badge>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <p className="muted">보류 이력이 없습니다.</p>
                    )}

                    <p
                      className="notice"
                      role="note"
                      style={{ marginTop: "1rem" }}
                    >
                      보류 설정 및 해제 기능은 다음 단계(B-3)에서 제공됩니다.
                    </p>
                  </section>
                </div>
              )}
            </DetailPanel>
          )}
        </div>
      )}
    </div>
  );
}
