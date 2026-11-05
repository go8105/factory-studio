// W-13 생산 불출 — 작업지시 소요 자재를 보관 칸에서 라인 칸으로 옮긴다 (DSN-13 F25, Q4·Q5).
// LOT 배정은 저장하지 않는다. 목록·상세는 미리보기를, 확정은 그때의 재고로 다시 계산한다.
// 확정하면 PRODUCTION_ISSUE 재고 전표가 생기고, MES 자재 투입은 라인 재고에서 차감한다.
import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useSession } from "../app/session";
import { api } from "../shared/api";
import {
  Badge,
  DataTable,
  DetailPanel,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  fieldErrors,
  ISSUE_STATUS_LABEL,
  num,
  time,
  useLists,
  WMS,
  type IssueRequest,
  type IssueRequestStatus,
  type Item,
  type Location,
  type Warehouse,
} from "./common";

const LIMIT = 50;

const tone = (status: IssueRequestStatus) =>
  status === "ISSUED" ? "normal" : status === "OPEN" ? "warning" : "issue";

export function Issues() {
  const { session } = useSession();
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");
  const statusFilter =
    (params.get("status") as IssueRequestStatus | null) ?? "";
  const warehouseFilter = params.get("warehouseId") ?? "";

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.set("page", "1");
    setParams(next);
  };

  const { data: meta } = useLists<[Warehouse[], Item[]]>([
    "/warehouses",
    "/items",
  ]);

  const query = new URLSearchParams({
    page: String(page),
    pageSize: String(LIMIT),
  });
  if (statusFilter) query.set("status", statusFilter);
  if (warehouseFilter) query.set("warehouseId", warehouseFilter);

  const { data: envelope, reload } = useLists<
    [{ rows: IssueRequest[]; total: number }]
  >([`/issue-requests?${query.toString()}`]);

  const [selected, setSelected] = useState<IssueRequest | null>(null);
  const [issued, setIssued] = useState<Record<number, string>>({});
  const [cancelReason, setCancelReason] = useState("");
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<unknown>();

  // 새 요청 폼. 위치는 창고별로만 조회할 수 있어 고른 창고의 칸을 그때 불러온다.
  const [creating, setCreating] = useState(false);
  const [formWarehouseId, setFormWarehouseId] = useState("");
  const [locations, setLocations] = useState<Location[]>([]);
  const [lineLocationId, setLineLocationId] = useState("");
  const [workOrderNo, setWorkOrderNo] = useState("");
  const [draft, setDraft] = useState<{ itemId: string; qty: string }[]>([
    { itemId: "", qty: "" },
  ]);

  useEffect(() => {
    setLineLocationId("");
    if (!formWarehouseId) {
      setLocations([]);
      return;
    }
    const stop = new AbortController();
    api<Location[]>(`${WMS}/warehouses/${formWarehouseId}/locations`, {
      signal: stop.signal,
    })
      .then((res) => !stop.signal.aborted && setLocations(res.data ?? []))
      .catch(() => !stop.signal.aborted && setLocations([]));
    return () => stop.abort();
  }, [formWarehouseId]);

  useEffect(() => {
    if (!selected) return;
    setIssued(
      Object.fromEntries(selected.lines.map((l) => [l.id, String(l.qty)])),
    );
    setCancelReason("");
    setActionError(undefined);
  }, [selected?.id]);

  if (!meta || !envelope) return <Loading />;

  const warehouses = meta[0] ?? [];
  const items = meta[1] ?? [];
  const rows = envelope[0]?.rows ?? [];
  const total = envelope[0]?.total ?? 0;
  const errors = fieldErrors(actionError);

  // 설계상 도착 위치는 라인(LINE)이다. 시드에 LINE 칸이 없을 수 있어 NORMAL도 허용한다.
  const lineCandidates = locations.filter(
    (l) =>
      l.isActive && (l.locationType === "LINE" || l.locationType === "NORMAL"),
  );
  const hasLine = lineCandidates.some((l) => l.locationType === "LINE");

  async function send(path: string, body: unknown) {
    setPending(true);
    setActionError(undefined);
    try {
      const res = await api<IssueRequest>(`${WMS}/issue-requests${path}`, {
        method: "POST",
        csrf: session?.csrfToken,
        key: crypto.randomUUID(),
        body,
      });
      setSelected(res.data);
      reload();
      return res.data;
    } catch (err) {
      setActionError(err);
      return null;
    } finally {
      setPending(false);
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    const lines = draft
      .filter((d) => d.itemId && d.qty)
      .map((d) => ({ itemId: Number(d.itemId), qty: d.qty }));
    if (!lineLocationId || lines.length === 0) return;
    const made = await send("", {
      lineLocationId: Number(lineLocationId),
      workOrderNo: workOrderNo || null,
      lines,
    });
    if (made) {
      setCreating(false);
      setDraft([{ itemId: "", qty: "" }]);
      setWorkOrderNo("");
    }
  }

  const columns: Column<IssueRequest>[] = [
    {
      key: "requestNo",
      label: "요청 번호",
      render: (r) => <strong>{r.requestNo}</strong>,
    },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={tone(r.status)}>{ISSUE_STATUS_LABEL[r.status]}</Badge>
      ),
    },
    {
      key: "workOrderNo",
      label: "작업지시",
      render: (r) => r.workOrderNo ?? <span className="muted">-</span>,
    },
    {
      key: "lineLocationCode",
      label: "라인 위치",
      render: (r) => (
        <span>
          {r.lineLocationCode}{" "}
          <span className="muted">{r.lineLocationName}</span>
          {r.lineLocationType !== "LINE" && (
            <>
              {" "}
              <Badge tone="warning">라인 아님</Badge>
            </>
          )}
        </span>
      ),
    },
    {
      key: "lineCount",
      label: "자재",
      render: (r) => `${r.lineCount}건`,
    },
    {
      key: "shortages",
      label: "부족",
      render: (r) =>
        r.shortages.length ? (
          <Badge tone="issue">부족 {r.shortages.length}건</Badge>
        ) : (
          <span className="muted">-</span>
        ),
    },
    { key: "createdAt", label: "등록 일시", render: (r) => time(r.createdAt) },
    {
      key: "id",
      label: "작업",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          onClick={() => setSelected(r)}
        >
          상세
        </button>
      ),
    },
  ];

  return (
    <div className="wms-issues">
      <PageTitle
        id="W-13"
        title="W-13 생산 불출"
        subtitle="작업지시에 필요한 자재를 보관 칸에서 라인 칸으로 옮깁니다. LOT은 유효기간이 빠른 것부터 배정합니다."
      />

      {creating && formWarehouseId && !hasLine && (
        <p role="note" className="notice">
          라인(LINE) 칸이 없어 일반 보관 칸으로 불출합니다. W-06에서 라인 칸을
          만들 수 있습니다.
        </p>
      )}

      <div
        className="filter-bar"
        style={{
          display: "flex",
          gap: "0.5rem",
          flexWrap: "wrap",
          marginBottom: "1rem",
        }}
      >
        <label>
          상태
          <select
            aria-label="상태 필터"
            value={statusFilter}
            onChange={(e) => setParam("status", e.target.value)}
          >
            <option value="">전체 상태</option>
            <option value="OPEN">대기</option>
            <option value="ISSUED">불출 완료</option>
            <option value="CANCELLED">취소</option>
          </select>
        </label>
        <label>
          창고
          <select
            aria-label="창고 필터"
            value={warehouseFilter}
            onChange={(e) => setParam("warehouseId", e.target.value)}
          >
            <option value="">전체 창고</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.code} · {w.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => setCreating((v) => !v)}>
          {creating ? "닫기" : "불출 요청"}
        </button>
        <button type="button" className="secondary-button" onClick={reload}>
          새로고침
        </button>
      </div>

      {creating && (
        <form
          aria-label="생산 불출 요청"
          onSubmit={handleCreate}
          className="card"
        >
          <ErrorNotice error={actionError} />
          <label>
            창고
            <select
              value={formWarehouseId}
              onChange={(e) => setFormWarehouseId(e.target.value)}
              required
            >
              <option value="">선택</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} · {w.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            라인 위치
            <select
              value={lineLocationId}
              onChange={(e) => setLineLocationId(e.target.value)}
              required
            >
              <option value="">선택</option>
              {lineCandidates.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.code} {l.name}
                  {l.locationType === "LINE" ? " [라인]" : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            작업지시 번호
            <input
              value={workOrderNo}
              onChange={(e) => setWorkOrderNo(e.target.value)}
              maxLength={40}
              placeholder="MES 작업지시 번호 (선택)"
            />
          </label>
          {draft.map((d, i) => (
            <div key={i} style={{ display: "flex", gap: "0.5rem" }}>
              <label>
                자재 {i + 1}
                <select
                  value={d.itemId}
                  onChange={(e) =>
                    setDraft((rowsDraft) =>
                      rowsDraft.map((x, n) =>
                        n === i ? { ...x, itemId: e.target.value } : x,
                      ),
                    )
                  }
                >
                  <option value="">선택</option>
                  {items.map((it) => (
                    <option key={it.id} value={it.id}>
                      {it.itemCode} · {it.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                수량
                <input
                  value={d.qty}
                  onChange={(e) =>
                    setDraft((rowsDraft) =>
                      rowsDraft.map((x, n) =>
                        n === i ? { ...x, qty: e.target.value } : x,
                      ),
                    )
                  }
                  inputMode="decimal"
                />
              </label>
            </div>
          ))}
          <button
            type="button"
            className="secondary-button"
            onClick={() => setDraft((d) => [...d, { itemId: "", qty: "" }])}
          >
            자재 추가
          </button>
          <button type="submit" disabled={pending}>
            요청 등록
          </button>
        </form>
      )}

      <DataTable
        caption="생산 불출 목록"
        rows={rows}
        columns={columns}
        offset={(page - 1) * LIMIT}
        limit={LIMIT}
        total={total}
        onPage={(offset) =>
          setParam("page", String(Math.floor(offset / LIMIT) + 1))
        }
      />

      {selected && (
        <DetailPanel
          title={selected.requestNo}
          onClose={() => setSelected(null)}
          wide
        >
          <ErrorNotice error={actionError} />
          <div style={{ display: "grid", gap: "0.75rem" }}>
            <div>
              <strong>상태: </strong>
              <Badge tone={tone(selected.status)}>
                {ISSUE_STATUS_LABEL[selected.status]}
              </Badge>
            </div>
            <div>
              <strong>라인 위치: </strong>
              {selected.lineLocationCode} {selected.lineLocationName}
              {selected.lineLocationType !== "LINE" && " (라인 칸 아님)"}
            </div>
            <div>
              <strong>작업지시: </strong>
              {selected.workOrderNo ?? "-"}
            </div>

            <div className="table-scroll">
              <table aria-label="불출 자재">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>품목</th>
                    <th>요청 수량</th>
                    <th>
                      {selected.status === "OPEN" ? "불출 수량" : "불출됨"}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {selected.lines.map((l) => (
                    <tr key={l.id}>
                      <td>#{l.lineNo}</td>
                      <td>
                        {l.itemCode}{" "}
                        <span className="muted">· {l.itemName}</span>
                      </td>
                      <td>
                        {num(l.qty)} {l.baseUnit}
                      </td>
                      <td>
                        {selected.status === "OPEN" ? (
                          <input
                            aria-label={`${l.itemCode} 불출 수량`}
                            value={issued[l.id] ?? ""}
                            inputMode="decimal"
                            onChange={(e) =>
                              setIssued((m) => ({
                                ...m,
                                [l.id]: e.target.value,
                              }))
                            }
                          />
                        ) : l.issuedQty ? (
                          `${num(l.issuedQty)} ${l.baseUnit}`
                        ) : (
                          <span className="muted">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {selected.status === "OPEN" &&
              selected.allocationPreview.length > 0 && (
                <div role="note" className="notice">
                  <strong>배정 미리보기 (유효기간 빠른 순)</strong>
                  <ul>
                    {selected.allocationPreview.map((a, i) => (
                      <li key={i}>
                        {a.locationCode} {a.locationName} · LOT{" "}
                        {a.lotNo ?? "미지정"} · {num(a.qty)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

            {selected.shortages.length > 0 && (
              <div role="alert" className="notice error">
                <strong>가용 재고가 모자랍니다</strong>
                <ul>
                  {selected.shortages.map((s) => (
                    <li key={s.itemId}>
                      품목{" "}
                      {items.find((i) => i.id === s.itemId)?.itemCode ??
                        s.itemId}{" "}
                      · 요청 {num(s.requestedQty)} · 가용 {num(s.availableQty)}{" "}
                      · 부족 {num(s.shortageQty)}
                    </li>
                  ))}
                </ul>
                보류·만료 LOT은 배정에서 빠집니다. W-10에서 보류를 풀 수
                있습니다.
              </div>
            )}

            {selected.status === "ISSUED" && (
              <>
                <div>
                  <strong>불출 일시: </strong>
                  {time(selected.issuedAt ?? "")}
                </div>
                {selected.stockDocumentId && (
                  <div>
                    <strong>재고 전표: </strong>
                    <Link
                      to={`/wms/documents?open=${selected.stockDocumentId}`}
                    >
                      {selected.stockDocumentNo ?? "전표 보기"}
                    </Link>
                  </div>
                )}
              </>
            )}

            {selected.status === "CANCELLED" && (
              <div>
                <strong>취소 사유: </strong>
                {selected.cancelReason}
              </div>
            )}

            {selected.status === "OPEN" && (
              <>
                <button
                  type="button"
                  disabled={pending}
                  onClick={() =>
                    send(`/${selected.id}/confirm`, {
                      lines: selected.lines.map((l) => ({
                        lineId: l.id,
                        issuedQty: issued[l.id] ?? String(l.qty),
                      })),
                    })
                  }
                >
                  불출 확정
                </button>
                <label>
                  취소 사유
                  <input
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    maxLength={300}
                  />
                  {errors.cancelReason && (
                    <span className="field-error">{errors.cancelReason}</span>
                  )}
                </label>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={pending || !cancelReason.trim()}
                  onClick={() =>
                    send(`/${selected.id}/cancel`, {
                      cancelReason: cancelReason,
                    })
                  }
                >
                  불출 취소
                </button>
              </>
            )}
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
