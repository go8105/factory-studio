// S-11 공정능력 보고서 — 기간의 능력 지표를 그때 계산해 굳힌 스냅샷 (UI-02 L 패턴 + DetailPanel wide, 인쇄).
// S-03은 지금 데이터를 다시 계산해 보여 주지만, 보고서는 만든 시점의 값을 그대로 들고 있다.
// 뒤에 부분군이 늘거나 무효가 되어도 보고서 숫자는 변하지 않는다 — 그래야 남에게 낸 숫자를 다시 설명할 수 있다.
import { useState, type FormEvent } from "react";
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
  JUDGEMENT_LABEL,
  JUDGEMENT_TONE,
  label,
  ModuleOff,
  moduleOff,
  num,
  REPORT_STATUS_LABEL,
  REPORT_STATUS_TONE,
  spec,
  time,
  useGet,
  useSend,
  type CapabilityReport,
  type Characteristic,
  type Judgement,
} from "./common";

const judge = (value: string | null): Judgement | null =>
  value == null
    ? null
    : Number(value) >= 1.33
      ? "CAPABLE"
      : Number(value) >= 1
        ? "MARGINAL"
        : "INCAPABLE";
const today = () => new Date().toISOString().slice(0, 10);
const monthsAgo = (n: number) =>
  new Date(Date.now() - n * 30 * 86_400_000).toISOString().slice(0, 10);

function Figures({ report }: { report: CapabilityReport }) {
  const digits = report.decimals + 2;
  const pairs: [string, string | null, string][] = [
    ["Cp", report.cp, "(USL − LSL) ÷ 6σ(군내)"],
    ["Cpk", report.cpk, "치우침까지 본 여유 · 군내 σ"],
    ["Pp", report.pp, "(USL − LSL) ÷ 6σ(전체)"],
    ["Ppk", report.ppk, "치우침까지 본 여유 · 전체 σ"],
  ];
  return (
    <>
      <div className="kpi-grid">
        {pairs.map(([name, value, note]) => (
          <section className="stat-tile" key={name} aria-label={name}>
            <p>{name}</p>
            <strong>{value == null ? "—" : num(value, 2)}</strong>
            {(name === "Cpk" || name === "Ppk") && judge(value) && (
              <Badge tone={JUDGEMENT_TONE[judge(value)!]}>
                {JUDGEMENT_LABEL[judge(value)!]}
              </Badge>
            )}
            <small>{value == null ? "한쪽 규격 — 계산 안 함" : note}</small>
          </section>
        ))}
      </div>
      <dl className="spc-figures">
        <dt>부분군</dt>
        <dd>{report.subgroupCount}개</dd>
        <dt>평균 μ</dt>
        <dd>{num(report.mean, report.decimals + 1)}</dd>
        <dt>군내 σ (R̄/d2)</dt>
        <dd>{num(report.sigmaWithin, digits)}</dd>
        <dt>전체 σ</dt>
        <dd>{num(report.sigmaOverall, digits)}</dd>
        <dt>왜도</dt>
        <dd>{report.skewness == null ? "—" : num(report.skewness, 2)}</dd>
        <dt>첨도(초과)</dt>
        <dd>{report.kurtosis == null ? "—" : num(report.kurtosis, 2)}</dd>
      </dl>
      <p className="muted">
        왜도·첨도가 0에 가까우면 정규분포에 가깝습니다. 많이 벗어나면 Cp·Cpk를
        그대로 믿기 어렵습니다.
        {Number(report.sigmaOverall) > Number(report.sigmaWithin) &&
          " 군내 σ보다 전체 σ가 큽니다 — 기간 중에 공정이 옮겨 갔다는 뜻이고, Cpk와 Ppk의 차이가 그 관리되지 않은 변동입니다."}
      </p>
    </>
  );
}

export function Reports() {
  const chars = useGet<Characteristic[]>("/characteristics");
  const [status, setStatus] = useState("");
  const list = useGet<CapabilityReport[]>(
    `/capability-reports${status ? `?status=${status}` : ""}`,
  );
  const [open, setOpen] = useState<CapabilityReport | null>(null);
  const [draft, setDraft] = useState<{
    characteristicId: string;
    from: string;
    to: string;
    comment: string;
  } | null>(null);
  const [comment, setComment] = useState("");
  const { send, pending, error, setError } = useSend(() => list.reload());
  const guard = useDiscardGuard(!!draft && draft.comment.trim() !== "");
  if (moduleOff(list.error) || moduleOff(chars.error)) return <ModuleOff />;
  const errors = fieldErrors(error);

  function startNew() {
    guard.guard(() => {
      setOpen(null);
      setError(undefined);
      setDraft({
        characteristicId: String(chars.data?.[0]?.id ?? ""),
        from: monthsAgo(3),
        to: today(),
        comment: "",
      });
    });
  }
  async function create(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    const saved = await send<CapabilityReport>("/capability-reports", "POST", {
      characteristicId: Number(draft.characteristicId),
      reportStartOn: draft.from,
      reportEndOn: draft.to,
      comment: draft.comment || null,
    });
    if (saved) {
      setDraft(null);
      setOpen(saved);
    }
  }
  async function confirm(event: FormEvent) {
    event.preventDefault();
    if (!open) return;
    const saved = await send<CapabilityReport>(
      `/capability-reports/${open.id}/confirm`,
      "POST",
      { comment: comment || null },
    );
    if (saved) {
      setOpen(saved);
      setComment("");
    }
  }
  const columns: Column<CapabilityReport>[] = [
    {
      key: "reportEndOn",
      label: "기간",
      render: (r) => `${r.reportStartOn} ~ ${r.reportEndOn}`,
    },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={open?.id === r.id}
          onClick={() =>
            guard.guard(() => {
              setDraft(null);
              setOpen(r);
              setComment("");
              setError(undefined);
            })
          }
        >
          {r.status === "draft" ? "상세 · 확정" : "상세"}
        </button>
      ),
    },
    {
      key: "characteristicName",
      label: "특성",
      render: (r) =>
        `${r.itemCode} · ${r.processCode} · ${r.characteristicName}`,
    },
    { key: "version", label: "버전", render: (r) => `v${r.version}` },
    { key: "subgroupCount", label: "부분군" },
    { key: "cpk", label: "Cpk", render: (r) => num(r.cpk, 2) },
    { key: "ppk", label: "Ppk", render: (r) => num(r.ppk, 2) },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={REPORT_STATUS_TONE[r.status]}>
          {REPORT_STATUS_LABEL[r.status]}
        </Badge>
      ),
    },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="S-11"
        title="공정능력 보고서"
        subtitle="기간의 능력 지표를 그때 계산해 굳힌 스냅샷. 확정하면 바뀌지 않습니다"
        help="spc/s-11"
        actions={
          <button
            type="button"
            aria-pressed={!!draft}
            disabled={!chars.data?.length}
            onClick={startNew}
          >
            보고서 만들기
          </button>
        }
      />
      <ErrorNotice
        error={list.error ?? chars.error}
        retry={() => list.reload()}
      />
      <div className="filter-bar">
        <label>
          상태
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">전체</option>
            <option value="draft">초안</option>
            <option value="confirmed">확정</option>
            <option value="superseded">대체됨</option>
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
              caption="공정능력 보고서"
              offset={0}
              total={list.data.length}
              limit={list.data.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="보고서가 없습니다. 유효 부분군이 20개 이상인 기간으로 만들 수 있습니다."
                  action="보고서 만들기"
                  onAction={startNew}
                />
              }
            />
          </section>
          {draft ? (
            <FormPanel
              title="공정능력 보고서 만들기"
              guard={guard}
              onClose={() => setDraft(null)}
              onSubmit={(e) => void create(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    만들기
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => setDraft(null))}
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : error}
              />
              <p role="note" className="muted">
                만드는 순간의 유효 부분군으로 계산해 굳힙니다. 뒤에 부분군이
                늘거나 무효가 되어도 이 숫자는 바뀌지 않습니다. 다시 계산하려면
                같은 기간으로 한 번 더 만들면 새 버전이 됩니다.
              </p>
              <div className="field">
                <label htmlFor="report-char">관리 특성</label>
                <select
                  id="report-char"
                  value={draft.characteristicId}
                  onChange={(e) =>
                    setDraft({ ...draft, characteristicId: e.target.value })
                  }
                >
                  {chars.data?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {label(c)}
                    </option>
                  ))}
                </select>
              </div>
              <Field
                label="기간 시작"
                type="date"
                value={draft.from}
                required
                error={errors.reportStartOn}
                onChange={(e) => setDraft({ ...draft, from: e.target.value })}
              />
              <Field
                label="기간 끝"
                type="date"
                value={draft.to}
                required
                error={errors.reportEndOn}
                onChange={(e) => setDraft({ ...draft, to: e.target.value })}
              />
              <Field
                label="의견(선택)"
                value={draft.comment}
                maxLength={1000}
                onChange={(e) =>
                  setDraft({ ...draft, comment: e.target.value })
                }
              />
            </FormPanel>
          ) : (
            open && (
              <DetailPanel
                wide
                title={`${open.itemCode} · ${open.processCode} · ${open.characteristicName} v${open.version}`}
                guard={guard}
                onClose={() => setOpen(null)}
              >
                <p className="muted">
                  {open.reportStartOn} ~ {open.reportEndOn} · 규격 {spec(open)}
                  {open.target && ` · 목표 ${Number(open.target)}`} ·{" "}
                  {open.chartType === "I_MR" ? "I-MR" : "X̄-R"} ·{" "}
                  <Badge tone={REPORT_STATUS_TONE[open.status]}>
                    {REPORT_STATUS_LABEL[open.status]}
                  </Badge>
                  {open.confirmedAt && ` · 확정 ${time(open.confirmedAt)}`}
                </p>
                <Figures report={open} />
                {open.comment && <p>의견: {open.comment}</p>}
                {open.status === "draft" ? (
                  <form
                    className="spc-resolve"
                    onSubmit={(e) => void confirm(e)}
                  >
                    <p role="note" className="muted">
                      확정하면 바꿀 수 없습니다. 같은 기간에 이미 확정한
                      보고서가 있으면 그쪽이 대체됨으로 밀립니다.
                    </p>
                    <ErrorNotice
                      error={Object.keys(errors).length ? undefined : error}
                    />
                    <Field
                      label="의견(선택)"
                      value={comment}
                      maxLength={1000}
                      onChange={(e) => setComment(e.target.value)}
                    />
                    <button
                      type="submit"
                      disabled={pending}
                      aria-busy={pending}
                    >
                      확정
                    </button>
                  </form>
                ) : (
                  <p className="muted">
                    {open.status === "confirmed"
                      ? "확정된 보고서입니다. 브라우저 인쇄로 그대로 낼 수 있습니다."
                      : "같은 기간의 새 보고서가 확정되어 대체되었습니다."}
                  </p>
                )}
              </DetailPanel>
            )
          )}
        </div>
      )}
    </div>
  );
}
