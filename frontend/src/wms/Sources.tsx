// W-03 원천 반영 — MES·ERP 확정 기록을 읽기 전용으로 조회해 재고 원장에 반영한다(FS-024 D14, UI-02 L 패턴).
// 행 "반영" 또는 "미반영 모두 반영". 원천마다 따로 커밋되므로 반영 불가 한 건이 다른 건을 막지 않는다.
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  BLOCK_LABEL,
  KIND_LABEL,
  ModuleOff,
  moduleOff,
  num,
  time,
  useSend,
  WMS,
  type Source,
  type SourceKind,
  type SourceState,
} from "./common";

type Listing = {
  kind: SourceKind;
  disabled: boolean;
  sourceModule?: string;
  rows: Source[];
};
type SyncResult = {
  results: { sourceKey: string; state: string; reason?: { code: string } }[];
  synced: number;
  blocked: number;
  deferred?: number;
  inspected?: number;
};
const STATE: Record<SourceState, [string, "normal" | "warning" | "issue"]> = {
  pending: ["미반영", "warning"],
  blocked: ["반영 불가", "issue"],
  synced: ["반영됨", "normal"],
  cancel_pending: ["취소 미반영", "warning"],
  reversed: ["취소 반영됨", "normal"],
  cancelled: ["반영 전 취소", "normal"],
  inspection_pending: ["검수 대기", "warning"],
  inspected: ["검수 완료", "normal"],
  inspected_cancelled: ["검수 후 원천 취소", "issue"],
};
const ACTIONABLE = new Set<SourceState>(["pending", "cancel_pending"]);

export function Sources() {
  const { fail } = useSession();
  const navigate = useNavigate();
  const [kind, setKind] = useState<SourceKind>("MES_RECEIPT");
  const [state, setState] = useState<"pending" | "synced" | "all">("pending");
  const [data, setData] = useState<Listing>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const [summary, setSummary] = useState<string>();
  const {
    send,
    pending,
    error: saveError,
  } = useSend(() => setReload((n) => n + 1));
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setData(undefined);
    api<Listing>(`${WMS}/sources?kind=${kind}&state=${state}`, {
      signal: controller.signal,
    })
      .then((r) => !controller.signal.aborted && setData(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [kind, state, reload]);
  if (moduleOff(error)) return <ModuleOff />;

  async function sync(keys: string[]) {
    const result = await send<SyncResult>("/sources/sync", "POST", {
      kind,
      sourceKeys: keys,
    });
    if (!result) return;
    const reasons = result.results
      .filter((r) => r.reason)
      .map((r) => BLOCK_LABEL[r.reason!.code] ?? r.reason!.code);
    setSummary(
      `반영 ${result.synced}` +
        (result.deferred ? ` · 검수 대기 ${result.deferred}` : "") +
        (result.inspected ? ` · 검수 완료 ${result.inspected}` : "") +
        (result.blocked
          ? ` · 반영 불가 ${result.blocked}(${[...new Set(reasons)].join(", ")})`
          : ""),
    );
  }

  const rows = data?.rows ?? [];
  const actionable = rows.filter((r) => ACTIONABLE.has(r.state));
  const columns: Column<Source & { id: number }>[] = [
    { key: "sourceRef", label: "원천 번호" },
    {
      key: "sourceKey",
      label: "관리",
      render: (r) =>
        r.noticeId ? (
          <Link to={`/wms/inbounds?open=${r.noticeId}`}>입고 검수 상세</Link>
        ) : ACTIONABLE.has(r.state) ? (
          <button
            type="button"
            className="link-button"
            disabled={pending}
            onClick={() => void sync([r.sourceKey])}
          >
            {r.state === "cancel_pending" ? "취소 반영" : "반영"}
          </button>
        ) : r.documentId ? (
          <Link
            className="link-button"
            to={`/wms/documents?open=${r.documentId}`}
          >
            {r.documentNo}
          </Link>
        ) : r.state === "blocked" ? (
          <Link className="link-button" to="/wms/items">
            품목·단위로
          </Link>
        ) : (
          "—"
        ),
    },
    {
      key: "occurredAt",
      label: "원천 시각",
      render: (r) => time(r.occurredAt),
    },
    {
      key: "lines",
      label: "품목·수량",
      wrap: true,
      render: (r) =>
        r.lines
          .map(
            (l) =>
              `${l.itemCode} ${num(l.qty)} ${l.unit}` +
              (l.lotNo ? ` (${l.lotNo})` : "") +
              (l.packingNo ? ` · ${l.packingNo}` : ""),
          )
          .join(" · "),
    },
    {
      key: "state",
      label: "상태",
      render: (r) => {
        const [label, tone] = STATE[r.state];
        return (
          <>
            <Badge tone={tone}>{label}</Badge>
            {r.reason && (
              <small className="muted">
                {" "}
                {BLOCK_LABEL[r.reason.code] ?? r.reason.code}
                {r.reason.itemCode ? ` · ${r.reason.itemCode}` : ""}
                {r.reason.unit ? ` ${r.reason.unit}` : ""}
              </small>
            )}
          </>
        );
      },
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="W-03"
        title="원천 반영"
        subtitle="MES·ERP에서 확정된 입출고를 읽어 재고 원장에 반영합니다"
        help="wms/w-03"
        actions={
          actionable.length > 0 && (
            <button
              type="button"
              disabled={pending}
              aria-busy={pending}
              onClick={() => void sync(actionable.map((r) => r.sourceKey))}
            >
              미반영 {actionable.length}건 모두 반영
            </button>
          )
        }
      />
      <p className="muted" role="note">
        MES·ERP 데이터를 읽기만 합니다. WMS는 MES·ERP 기록을 바꾸지 않고, 원천
        번호와 수량을 전표에 복사해 둡니다.
        {kind === "MES_ISSUE" &&
          " 완료된 공정 실행의 투입만 보입니다. 실행 중에는 MES에서 투입을 고칠 수 있기 때문입니다."}
      </p>
      <div className="tabs" role="tablist" aria-label="원천 종류">
        {(Object.keys(KIND_LABEL) as SourceKind[]).map((k) => (
          <button
            key={k}
            type="button"
            aria-pressed={kind === k}
            className={kind === k ? "active" : ""}
            onClick={() => {
              setKind(k);
              setSummary(undefined);
            }}
          >
            {KIND_LABEL[k]}
          </button>
        ))}
      </div>
      <div className="filter-bar">
        <label>
          상태
          <select
            value={state}
            onChange={(e) => setState(e.target.value as typeof state)}
          >
            <option value="pending">미반영</option>
            <option value="synced">반영됨</option>
            <option value="all">전체</option>
          </select>
        </label>
      </div>
      {summary && (
        <p role="status" className="notice">
          {summary}
        </p>
      )}
      <ErrorNotice error={saveError} />
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!data ? (
        !error && <Loading delay={300} />
      ) : data.disabled ? (
        <EmptyState
          reason={`${data.sourceModule?.toUpperCase()}를 사용하지 않도록 설정했습니다. 수동 전표(W-04)로 재고를 관리할 수 있습니다.`}
          action="재고 전표로"
          onAction={() => navigate("/wms/documents")}
        />
      ) : (
        <DataTable
          rows={rows.map((r, i) => ({ ...r, id: i + 1 }))}
          columns={columns}
          caption={`${KIND_LABEL[kind]} 원천`}
          offset={0}
          total={rows.length}
          limit={rows.length || 1}
          onPage={() => undefined}
          empty={
            <EmptyState
              reason={
                state === "pending"
                  ? "반영할 원천이 없습니다. 모두 원장에 들어가 있습니다."
                  : "원천 기록이 없습니다."
              }
              to="/wms/stock"
              action="재고 현황으로"
            />
          }
        />
      )}
    </div>
  );
}
