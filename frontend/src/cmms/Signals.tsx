// C-02 전환 대기 신호 — BEMS 환경 경보·SPC 설비 이상을 고장 작업지시로 바꾼다 (FS-029 D48).
// 전환해도 원천 상태는 바뀌지 않는다. 해제·조치는 저쪽에서 따로 한다.
// 신호 1건당 취소되지 않은 작업지시 1건이고, 취소하면 다시 전환할 수 있다.
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import { useApiSend } from "../shared/hooks";
import { fieldErrors, moduleOff, useGet } from "./hooks";
import {
  CMMS,
  WO_SOURCE_LABEL,
  time,
  type AssetNode,
  type PendingSignal,
  type SignalBoard,
  type WorkOrder,
} from "./common";

export function Signals() {
  const board = useGet<SignalBoard>("/signals");
  const assets = useGet<AssetNode[]>("/assets/tree");
  const [picked, setPicked] = useState<PendingSignal | null>(null);
  const [assetId, setAssetId] = useState("");
  const [done, setDone] = useState("");
  const { send, pending, error, setError } = useApiSend(CMMS, () => {
    board.reload();
  });
  const guard = useDiscardGuard(false);
  if (moduleOff(board.error))
    return (
      <EmptyState
        reason="CMMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const errors = fieldErrors(error);
  const live = (assets.data ?? []).filter((a) => a.isActive);

  function choose(signal: PendingSignal) {
    setError(undefined);
    setDone("");
    setPicked(signal);
    setAssetId(String(signal.suggestedAssetId ?? live[0]?.id ?? ""));
  }
  async function convert(event: FormEvent) {
    event.preventDefault();
    if (!picked) return;
    const saved = await send<WorkOrder>("/signals/convert", "POST", {
      source: picked.source,
      sourceRef: picked.sourceRef,
      summary: picked.summary,
      assetId: Number(assetId),
      detectedAt: picked.detectedAt,
    });
    if (saved) {
      setDone(`${saved.woNo} 작업지시를 만들었습니다.`);
      setPicked(null);
    }
  }
  const columns: Column<PendingSignal>[] = [
    { key: "detectedAt", label: "발생", render: (s) => time(s.detectedAt) },
    {
      key: "source",
      label: "출처",
      render: (s) => WO_SOURCE_LABEL[s.source],
    },
    { key: "summary", label: "내용" },
    {
      key: "severity",
      label: "등급",
      render: (s) =>
        s.severity ? (
          <Badge tone={s.severity === "CRITICAL" ? "issue" : "warning"}>
            {s.severity === "CRITICAL" ? "심각" : "경고"}
          </Badge>
        ) : (
          <span className="muted">—</span>
        ),
    },
    {
      key: "suggestedAssetCode",
      label: "추천 설비",
      render: (s) =>
        s.suggestedAssetCode ?? (
          <span className="muted">대장에 없음 — 직접 고르세요</span>
        ),
    },
    {
      key: "id",
      label: "관리",
      render: (s) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={picked?.id === s.id}
          disabled={!live.length}
          onClick={() => choose(s)}
        >
          작업지시로
        </button>
      ),
    },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="C-02"
        title="전환 대기 신호"
        subtitle="BEMS 경보·SPC 이상 중 아직 작업지시가 되지 않은 것"
        help="cmms/c-02"
      />
      <ErrorNotice error={board.error} retry={() => board.reload()} />
      <p role="status">{done}</p>
      <p role="note" className="muted">
        전환해도 <strong>원천 상태는 바뀌지 않습니다</strong> — 경보 해제는
        BEMS에서, 이상 조치는 SPC에서 따로 합니다. 신호 하나로는 작업지시를 한
        건만 만들 수 있고, 그 작업지시를 취소하면 여기에 다시 나타납니다.
      </p>
      {board.data && (
        <>
          {!board.data.sources.bems && (
            <p role="note" className="muted">
              BEMS를 사용하지 않도록 설정해 환경 경보는 보이지 않습니다.
            </p>
          )}
          {!board.data.sources.spc && (
            <p role="note" className="muted">
              SPC를 사용하지 않도록 설정해 설비 이상은 보이지 않습니다.
            </p>
          )}
          {!live.length && (
            <p role="note" className="muted">
              설비 대장이 비어 있어 전환할 수 없습니다.{" "}
              <Link to="/cmms/assets">설비 대장 →</Link>
            </p>
          )}
        </>
      )}
      {!board.data ? (
        !board.error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={board.data.signals}
              columns={columns}
              caption="전환 대기 신호"
              offset={0}
              total={board.data.signals.length}
              limit={board.data.signals.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="전환할 신호가 없습니다. 모두 작업지시가 되었거나 원천에 경보·이상이 없습니다."
                  to="/cmms/work-orders"
                  action="작업지시"
                />
              }
            />
          </section>
          {picked && (
            <FormPanel
              title="작업지시로 전환"
              guard={guard}
              onClose={() => setPicked(null)}
              onSubmit={(e) => void convert(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    전환
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setPicked(null)}
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : error}
              />
              <p>{picked.summary}</p>
              <p className="muted">
                {WO_SOURCE_LABEL[picked.source]} · {time(picked.detectedAt)}
              </p>
              <div className="field">
                <label htmlFor="sig-asset">작업할 설비</label>
                <select
                  id="sig-asset"
                  value={assetId}
                  aria-invalid={!!errors.assetId}
                  onChange={(e) => setAssetId(e.target.value)}
                >
                  {live.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} {a.name}
                    </option>
                  ))}
                </select>
                <small>
                  {picked.suggestedAssetCode
                    ? "경보 구역·설비 코드로 찾은 추천입니다. 바꿀 수 있습니다."
                    : "원천 코드가 대장에 없어 직접 골라야 합니다."}
                </small>
                {errors.assetId && <small>{errors.assetId}</small>}
              </div>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
