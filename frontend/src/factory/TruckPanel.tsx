import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ModuleOff, moduleOff, type Item } from "../wms/common";
import {
  OperationError,
  states,
  useWmsCommand,
  useWmsQuery,
  type Inbound,
  type Page,
} from "../wms/operations";
import { Loading } from "../shared/components";
export default function TruckPanel({
  enabled,
  onProgress,
}: {
  enabled: boolean;
  onProgress: (n: number | null) => void;
}) {
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [locked, setLocked] = useState(false);
  const selected = params.get("inbound") ?? "";
  const list = useWmsQuery<Page<Inbound>>(
    `/inbound-notices?page=${page}&pageSize=50`,
  );
  if (moduleOff(list.error)) return <ModuleOff />;
  return (
    <section className="factory-truck-panel panel" aria-label="트럭 입고 시연">
      <h2>트럭 입고 · WMS 연결</h2>
      <p>
        합성 차량 시연입니다. 도착 상태만 저장하며 재고는 검수 확정 때
        증가합니다.
      </p>
      <OperationError error={list.error} retry={list.reload} />
      <label>
        입고 예정
        <select
          disabled={locked}
          value={selected}
          onChange={(e) =>
            setParams((p) => {
              if (e.target.value) p.set("inbound", e.target.value);
              else p.delete("inbound");
              return p;
            })
          }
        >
          <option value="">선택</option>
          {selected &&
            !list.data?.rows.some((n) => String(n.id) === selected) && (
              <option value={selected}>선택한 예정 {selected}</option>
            )}
          {list.data?.rows.map((n) => (
            <option value={n.id} key={n.id}>
              {n.noticeNo} · {n.vehicleNo ?? "차량 미지정"} · {states[n.status]}
            </option>
          ))}
        </select>
      </label>
      <div className="row-actions">
        <button
          disabled={locked || page === 1}
          onClick={() => setPage((p) => p - 1)}
        >
          이전 예정
        </button>
        <button
          disabled={locked || !list.data || page * 50 >= list.data.total}
          onClick={() => setPage((p) => p + 1)}
        >
          다음 예정
        </button>
      </div>
      {selected && (
        <TruckArrival
          key={selected}
          id={selected}
          enabled={enabled}
          onProgress={onProgress}
          onLock={setLocked}
        />
      )}
      <Link to="/wms/inbounds">WMS 입고 예정·검수 열기</Link>
      <Link to="/help/portal/wms-flow">업무 흐름 도움말</Link>
      {list.data?.total === 0 && (
        <p>입고 예정이 없습니다. WMS에서 먼저 등록하세요.</p>
      )}
    </section>
  );
}
function TruckArrival({
  id,
  enabled,
  onProgress,
  onLock,
}: {
  id: string;
  enabled: boolean;
  onProgress: (n: number | null) => void;
  onLock: (b: boolean) => void;
}) {
  const notice = useWmsQuery<Inbound>(`/inbound-notices/${id}`);
  const items = useWmsQuery<Item[]>("/items");
  const command = useWmsCommand();
  const [phase, setPhase] = useState<
    "idle" | "driving" | "saving" | "uncertain"
  >("idle");
  const progress = useRef(0);
  const version = useRef(0);
  const saving = useRef(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      onProgress(null);
      onLock(false);
    };
  }, [onProgress, onLock]);
  useEffect(() => {
    if (notice.data && phase === "idle")
      onProgress(["ARRIVED", "INSPECTED"].includes(notice.data.status) ? 1 : 0);
  }, [notice.data, phase, onProgress]);
  useEffect(() => {
    if (phase !== "driving" || !enabled) return;
    let frame = 0,
      last = performance.now();
    function step(now: number) {
      const dt = Math.min(now - last, 100);
      last = now;
      if (!document.hidden)
        progress.current = Math.min(1, progress.current + dt / 4000);
      onProgress(progress.current);
      if (progress.current >= 1) setPhase("saving");
      else frame = requestAnimationFrame(step);
    }
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [phase, enabled, onProgress]);
  useEffect(() => {
    if (phase !== "saving" || saving.current) return;
    saving.current = true;
    void command
      .send<Inbound>(`/inbound-notices/${id}/arrive`, {
        expectedVersion: version.current,
      })
      .then((n) => {
        saving.current = false;
        if (!alive.current) return;
        onLock(false);
        if (n) {
          notice.accept(n);
          setPhase("idle");
          notice.reload();
        } else setPhase("uncertain");
      });
  }, [phase]);
  if (!notice.data)
    return (
      <>
        <OperationError error={notice.error} retry={notice.reload} />
        {!notice.error && <Loading />}
      </>
    );
  const n = notice.data;
  return (
    <>
      <p role="status">
        {phase === "driving"
          ? enabled
            ? "트럭 진입 중…"
            : "시연 일시정지"
          : phase === "saving"
            ? "도착 상태 저장 중…"
            : phase === "uncertain"
              ? "도착 저장 확인 필요"
              : states[n.status]}
      </p>
      <p>
        {n.noticeNo} · 예정 {n.expectedOn} ·{" "}
        {n.lines
          .map(
            (l) =>
              `${items.data?.find((x) => x.id === l.itemId)?.itemCode ?? "품목 조회 중"} ${l.expectedQty} ${items.data?.find((x) => x.id === l.itemId)?.baseUnit ?? ""}`,
          )
          .join(", ")}
      </p>
      <OperationError error={command.error} />
      {n.status === "PLANNED" && (
        <button
          disabled={!enabled || phase === "driving" || phase === "saving"}
          onClick={() => {
            version.current = n.version;
            onLock(true);
            if (phase === "uncertain") setPhase("saving");
            else {
              progress.current = 0;
              setPhase("driving");
            }
          }}
        >
          {phase === "uncertain"
            ? "같은 도착 요청 다시 확인"
            : "트럭 도착 시연"}
        </button>
      )}
      {!enabled && <p>공장 외관에서 시연 재생과 3D 준비를 확인하세요.</p>}
      <button
        className="secondary"
        disabled={phase === "driving" || phase === "saving"}
        onClick={() => {
          setPhase("idle");
          notice.reload();
        }}
      >
        서버 상태 다시 조회
      </button>
      {["ARRIVED", "INSPECTED"].includes(n.status) && (
        <Link to={`/wms/inbounds?open=${n.id}`}>도착 기록·검수 열기</Link>
      )}
    </>
  );
}
