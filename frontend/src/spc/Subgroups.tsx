// S-06 부분군 기록 — 검색·무효 처리(TX-S4) (UI-02 L 패턴 + DetailPanel).
// 무효로 하면 그 부분군의 이상 기록도 무효가 된다. 뒤 부분군의 판정 결과는 다시 계산하지 않는다(13장 4).
import { useState, type FormEvent } from "react";
import {
  Badge,
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import {
  fieldErrors,
  label,
  ModuleOff,
  moduleOff,
  num,
  time,
  useGet,
  useSend,
  type Characteristic,
  type Subgroup,
} from "./common";

const SOURCE_LABEL: Record<Subgroup["source"], string> = {
  SEED: "시드",
  MANUAL: "입력",
  MES: "MES",
  FILE: "파일",
};

export function Subgroups() {
  const chars = useGet<Characteristic[]>("/characteristics");
  const [characteristic, setCharacteristic] = useState("");
  const [lot, setLot] = useState("");
  const [status, setStatus] = useState("");
  const [applied, setApplied] = useState("");
  const list = useGet<Subgroup[]>(`/subgroups${applied}`);
  const [open, setOpen] = useState<Subgroup | null>(null);
  const [reason, setReason] = useState("");
  const { send, pending, error, setError } = useSend(() => list.reload());
  const guard = useDiscardGuard(!!open && reason.trim() !== "");
  if (moduleOff(list.error) || moduleOff(chars.error)) return <ModuleOff />;
  const errors = fieldErrors(error);
  const name = (id: number) => {
    const c = chars.data?.find((x) => x.id === id);
    return c ? label(c) : "—";
  };

  function search(event: FormEvent) {
    event.preventDefault();
    const q = new URLSearchParams();
    if (characteristic) q.set("characteristicId", characteristic);
    if (lot.trim()) q.set("lotNo", lot.trim());
    if (status) q.set("status", status);
    setApplied(q.toString() ? `?${q}` : "");
  }
  async function voidIt(event: FormEvent) {
    event.preventDefault();
    if (!open) return;
    const r = await send<Subgroup & { voidedSignals: number }>(
      `/subgroups/${open.id}/void`,
      "POST",
      { reason },
    );
    if (r) {
      setOpen(r);
      setReason("");
    }
  }
  const columns: Column<Subgroup>[] = [
    {
      key: "measuredAt",
      label: "측정 시각",
      render: (s) => time(s.measuredAt),
    },
    {
      key: "id",
      label: "관리",
      render: (s) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={open?.id === s.id}
          onClick={() =>
            guard.guard(() => {
              setOpen(s);
              setReason("");
              setError(undefined);
            })
          }
        >
          {s.status === "valid" ? "상세 · 무효 처리" : "상세"}
        </button>
      ),
    },
    {
      key: "characteristicId",
      label: "특성",
      render: (s) => name(s.characteristicId),
    },
    { key: "lotNo", label: "LOT" },
    { key: "equipmentCode", label: "설비" },
    {
      key: "measurements",
      label: "측정값",
      render: (s) => s.measurements.map((v) => num(v, 4)).join(" · "),
    },
    {
      key: "xbar",
      label: "X̄ · I",
      render: (s) => num(s.xbar, 4),
    },
    {
      key: "r",
      label: "R · MR",
      render: (s) => num(s.r, 4),
    },
    {
      key: "source",
      label: "출처",
      render: (s) => SOURCE_LABEL[s.source],
    },
    {
      key: "status",
      label: "상태",
      render: (s) =>
        s.status === "valid" ? (
          <Badge>유효</Badge>
        ) : (
          <Badge tone="warning">무효</Badge>
        ),
    },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="S-06"
        title="부분군 기록"
        subtitle="기록한 측정값을 찾아보고, 잘못 넣은 부분군을 무효로 합니다"
        help="spc/s-06"
      />
      <ErrorNotice
        error={list.error ?? chars.error}
        retry={() => list.reload()}
      />
      <form className="filter-bar" onSubmit={search}>
        <label>
          특성
          <select
            value={characteristic}
            onChange={(e) => setCharacteristic(e.target.value)}
          >
            <option value="">전체</option>
            {chars.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {label(c)}
              </option>
            ))}
          </select>
        </label>
        <label>
          LOT
          <input value={lot} onChange={(e) => setLot(e.target.value)} />
        </label>
        <label>
          상태
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">전체</option>
            <option value="valid">유효</option>
            <option value="void">무효</option>
          </select>
        </label>
        <button type="submit">조회</button>
      </form>
      {!list.data ? (
        !list.error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={list.data}
              columns={columns}
              caption="부분군(최근 500건)"
              offset={0}
              total={list.data.length}
              limit={list.data.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="조건에 맞는 부분군이 없습니다."
                  to="/spc/measure"
                  action="측정 입력"
                />
              }
            />
          </section>
          {open && (
            <DetailPanel
              title={`${open.lotNo} ${time(open.measuredAt)} 부분군`}
              guard={guard}
              onClose={() => setOpen(null)}
            >
              <p>
                {name(open.characteristicId)} · {open.equipmentCode} · X̄{" "}
                {num(open.xbar, 4)} · R {num(open.r, 4)}
              </p>
              <p className="muted">
                값 {open.measurements.map((v) => num(v, 4)).join(" · ")}
                {open.note && ` · 메모 ${open.note}`}
              </p>
              {open.status === "void" ? (
                <p className="muted">
                  무효 {open.voidedAt && time(open.voidedAt)} · 사유{" "}
                  {open.voidReason}
                </p>
              ) : (
                <form onSubmit={(e) => void voidIt(e)}>
                  <p role="note" className="muted">
                    무효로 하면 이 부분군에서 생긴 이상 기록도 무효가 되고,
                    관리도·공정능력 계산에서 빠집니다. 뒤 부분군의 판정 결과는
                    그대로 남습니다.
                  </p>
                  <ErrorNotice
                    error={Object.keys(errors).length ? undefined : error}
                  />
                  <Field
                    label="무효 사유"
                    value={reason}
                    required
                    minLength={2}
                    maxLength={200}
                    error={errors.reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    무효 처리
                  </button>
                </form>
              )}
            </DetailPanel>
          )}
        </div>
      )}
    </div>
  );
}
