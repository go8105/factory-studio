// S-05 이상·조치 — 이상 기록 목록 + 상세(주변 점·조치 TX-S3) (UI-02 L 패턴 + DetailPanel).
import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Badge,
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import {
  CAUSE_LABEL,
  CHART_LABEL,
  ControlChart,
  fieldErrors,
  ModuleOff,
  moduleOff,
  num,
  RULE_LABEL,
  RULE_TEXT,
  STATUS_LABEL,
  time,
  useGet,
  useSend,
  type Cause,
  type ChartData,
  type Signal,
} from "./common";

const tone = (s: Signal["status"]) =>
  s === "open" ? "issue" : s === "void" ? "warning" : "normal";

function Around({ signal }: { signal: Signal }) {
  const day = 86_400_000;
  const from = new Date(Date.parse(signal.detectedAt) - 4 * day)
    .toISOString()
    .slice(0, 10);
  const to = new Date(Date.parse(signal.detectedAt) + 2 * day)
    .toISOString()
    .slice(0, 10);
  const { data } = useGet<ChartData>(
    `/characteristics/${signal.characteristicId}/chart?from=${from}&to=${to}`,
  );
  if (!data) return <Loading />;
  const index = data.points.findIndex((p) => p.id === signal.subgroupId);
  const points = data.points.slice(Math.max(0, index - 10), index + 11);
  return (
    <ControlChart kind={signal.chart} data={{ ...data, points }} height={150} />
  );
}

export function Signals() {
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState(params.get("signal") ? "" : "open");
  const list = useGet<Signal[]>(`/signals${status ? `?status=${status}` : ""}`);
  const [open, setOpen] = useState<Signal | null>(null);
  const [cause, setCause] = useState<Cause>("MACHINE");
  const [action, setAction] = useState("");
  const { send, pending, error, setError } = useSend(() => list.reload());
  const guard = useDiscardGuard(!!open && action.trim() !== "");
  const wanted = Number(params.get("signal"));
  useEffect(() => {
    if (!wanted || !list.data) return;
    const found = list.data.find((s) => s.id === wanted);
    if (found) setOpen(found);
  }, [wanted, list.data]);
  if (moduleOff(list.error)) return <ModuleOff />;
  const errors = fieldErrors(error);

  function show(s: Signal) {
    guard.guard(() => {
      setOpen(s);
      setAction("");
      setError(undefined);
      const copy = new URLSearchParams(params);
      copy.set("signal", String(s.id));
      setParams(copy, { replace: true });
    });
  }
  async function resolve(event: FormEvent) {
    event.preventDefault();
    if (!open) return;
    const r = await send<Signal>(`/signals/${open.id}/resolve`, "POST", {
      causeCategory: cause,
      action,
    });
    if (r) {
      setOpen(r);
      setAction("");
    }
  }
  const columns: Column<Signal>[] = [
    {
      key: "detectedAt",
      label: "발생 시각",
      render: (s) => time(s.detectedAt),
    },
    {
      key: "id",
      label: "관리",
      render: (s) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={open?.id === s.id}
          onClick={() => show(s)}
        >
          {s.status === "open" ? "상세 · 조치" : "상세"}
        </button>
      ),
    },
    {
      key: "characteristicName",
      label: "특성",
      render: (s) =>
        `${s.itemCode} · ${s.processCode} · ${s.characteristicName}`,
    },
    { key: "lotNo", label: "LOT" },
    { key: "equipmentCode", label: "설비" },
    { key: "chart", label: "관리도", render: (s) => CHART_LABEL[s.chart] },
    { key: "rule", label: "규칙", render: (s) => RULE_LABEL[s.rule] },
    { key: "value", label: "값", render: (s) => num(s.value, 4) },
    {
      key: "status",
      label: "상태",
      render: (s) => (
        <Badge tone={tone(s.status)}>{STATUS_LABEL[s.status]}</Badge>
      ),
    },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="S-05"
        title="이상·조치"
        subtitle="관리도 규칙에 걸린 점과 그 원인·조치를 기록합니다"
        help="spc/s-05"
      />
      <p role="note" className="muted">
        미조치 이상이 있는 LOT는 QMS 검사 대기·검사 화면에 &quot;SPC 이상&quot;
        배지로 보입니다. QMS 판정은 바꾸지 않습니다.{" "}
        <Link to="/qms/pending">QMS 검사 대기 →</Link>
      </p>
      <ErrorNotice error={list.error} retry={() => list.reload()} />
      <div className="filter-bar">
        <label>
          상태
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="open">미조치</option>
            <option value="resolved">조치 완료</option>
            <option value="void">무효</option>
            <option value="">전체</option>
          </select>
        </label>
      </div>
      {!list.data ? (
        !list.error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={list.data}
              columns={columns}
              caption="이상 기록"
              offset={0}
              total={list.data.length}
              limit={list.data.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="조건에 맞는 이상 기록이 없습니다."
                  to="/spc/chart"
                  action="관리도로"
                />
              }
            />
          </section>
          {open && (
            <DetailPanel
              wide
              title={`${open.lotNo} ${CHART_LABEL[open.chart]} 이상`}
              guard={guard}
              onClose={() => setOpen(null)}
            >
              <p>
                <strong>{RULE_LABEL[open.rule]}</strong> —{" "}
                {RULE_TEXT[open.rule]}
              </p>
              <p className="muted">
                {open.itemCode} · {open.processCode} · {open.characteristicName}{" "}
                · {open.equipmentCode} · 발생 {time(open.detectedAt)} · 한계 v
                {open.limitVersion} ·{" "}
                <Badge tone={tone(open.status)}>
                  {STATUS_LABEL[open.status]}
                </Badge>
              </p>
              <Around signal={open} />
              {open.status === "resolved" && (
                <p>
                  원인 {open.causeCategory && CAUSE_LABEL[open.causeCategory]} ·
                  조치 {open.action} ·{" "}
                  {open.resolvedAt && time(open.resolvedAt)}
                </p>
              )}
              {open.status === "void" && (
                <p className="muted">
                  부분군을 무효 처리해 이 이상도 무효가 되었습니다(
                  {open.voidedAt && time(open.voidedAt)}).
                </p>
              )}
              {open.status === "open" && (
                <form className="spc-resolve" onSubmit={(e) => void resolve(e)}>
                  <ErrorNotice
                    error={Object.keys(errors).length ? undefined : error}
                  />
                  <div className="field">
                    <label htmlFor="spc-cause">원인 분류</label>
                    <select
                      id="spc-cause"
                      value={cause}
                      onChange={(e) => setCause(e.target.value as Cause)}
                    >
                      {(Object.keys(CAUSE_LABEL) as Cause[]).map((k) => (
                        <option key={k} value={k}>
                          {CAUSE_LABEL[k]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="spc-action">조치 내용</label>
                    <textarea
                      id="spc-action"
                      value={action}
                      required
                      minLength={2}
                      maxLength={500}
                      aria-invalid={!!errors.action}
                      onChange={(e) => setAction(e.target.value)}
                    />
                    {errors.action && <small>{errors.action}</small>}
                  </div>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    조치 완료
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
