// S-08 규격 이탈 — 개별 측정값이 규격(LSL·USL)을 벗어난 기록 (UI-02 L 패턴, DSN-17 Q4).
// 관리 이탈(이상·조치)과 다른 것이다: 관리 한계는 공정이 평소와 다른지, 규격은 제품이 쓸 수 있는지를 본다.
// 그래서 한계를 게시하기 전에도 기록되고, 조치 대상이 아니라 QMS 부적합 보고 후보로 넘어간다.
import { useState, type FormEvent } from "react";
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
  label,
  ModuleOff,
  moduleOff,
  num,
  SIDE_LABEL,
  time,
  useGet,
  type Characteristic,
  type SpecViolation,
} from "./common";

export function Violations() {
  const chars = useGet<Characteristic[]>("/characteristics");
  const [characteristic, setCharacteristic] = useState("");
  const [lot, setLot] = useState("");
  const [status, setStatus] = useState("open");
  const [applied, setApplied] = useState("?status=open");
  const list = useGet<SpecViolation[]>(`/spec-violations${applied}`);
  if (moduleOff(list.error) || moduleOff(chars.error)) return <ModuleOff />;

  function search(event: FormEvent) {
    event.preventDefault();
    const q = new URLSearchParams();
    if (characteristic) q.set("characteristicId", characteristic);
    if (lot.trim()) q.set("lotNo", lot.trim());
    if (status) q.set("status", status);
    setApplied(q.toString() ? `?${q}` : "");
  }
  const columns: Column<SpecViolation>[] = [
    { key: "detectedAt", label: "탐지", render: (v) => time(v.detectedAt) },
    { key: "lotNo", label: "LOT" },
    { key: "equipmentCode", label: "설비" },
    {
      key: "characteristicName",
      label: "특성",
      render: (v) =>
        `${v.itemCode} · ${v.processCode} · ${v.characteristicName}`,
    },
    { key: "seq", label: "순번", render: (v) => `${v.seq}번째` },
    {
      key: "value",
      label: "측정값",
      render: (v) => `${num(v.value, 4)} ${v.unit}`,
    },
    {
      key: "side",
      label: "이탈",
      render: (v) => (
        <Badge tone={v.status === "void" ? "normal" : "issue"}>
          {SIDE_LABEL[v.side]}
        </Badge>
      ),
    },
    {
      key: "limitValue",
      label: "규격 한계",
      render: (v) => `${num(v.limitValue, 4)} ${v.unit}`,
    },
    {
      key: "status",
      label: "상태",
      render: (v) =>
        v.status === "open" ? (
          <Badge tone="warning">유효</Badge>
        ) : (
          <Badge>무효</Badge>
        ),
    },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="S-08"
        title="규격 이탈"
        subtitle="개별 측정값이 규격을 벗어난 기록. 관리 한계 이탈과는 다릅니다"
        help="spc/s-08"
      />
      <ErrorNotice
        error={list.error ?? chars.error}
        retry={() => list.reload()}
      />
      <p role="note" className="muted">
        규격 이탈은 제품이 쓸 수 있는 범위를 벗어난 것이라 관리 한계를 게시하기
        전에도 기록됩니다. 조치는 QMS 부적합 보고에서 다루고, 부분군을 무효로
        하면 여기서도 무효가 됩니다.
      </p>
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
            <option value="open">유효</option>
            <option value="void">무효</option>
            <option value="">전체</option>
          </select>
        </label>
        <button type="submit">조회</button>
      </form>
      {!list.data ? (
        !list.error && <Loading />
      ) : (
        <DataTable
          rows={list.data}
          columns={columns}
          caption="규격 이탈(최근 500건)"
          offset={0}
          total={list.data.length}
          limit={list.data.length || 1}
          onPage={() => undefined}
          empty={
            <EmptyState
              reason="조건에 맞는 규격 이탈이 없습니다."
              to="/spc/subgroups"
              action="부분군 기록"
            />
          }
        />
      )}
    </div>
  );
}
