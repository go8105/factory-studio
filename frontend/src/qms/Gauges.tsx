// Q-11 계측기·교정 — 목록 + 계측기 상세(교정 이력) + 등록/수정·교정 등록 (DSN-14 F61·F62).
// 교정 도래는 저장하지 않는다. 마지막 교정의 다음 기한에서 파생해 보여 준다.
import { useEffect, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import { CODE_PATTERN } from "../shared/master";
import {
  DueBadge,
  fieldErrors,
  GAUGE_STATUS,
  GaugeStatusBadge,
  ModuleOff,
  moduleOff,
  QMS,
  ResultBadge,
  useSend,
  type Gauge,
  type GaugeStatus,
} from "./common";

type Draft = {
  code: string;
  name: string;
  gaugeKind: string;
  measureRange: string;
  resolution: string;
  calibrationCycleDays: string;
  status: GaugeStatus;
};
const BLANK: Draft = {
  code: "",
  name: "",
  gaugeKind: "",
  measureRange: "",
  resolution: "",
  calibrationCycleDays: "365",
  status: "ACTIVE",
};
type CalDraft = {
  calibratedOn: string;
  nextDueOn: string;
  result: "PASS" | "FAIL";
  agency: string;
  certificateNo: string;
};
const CAL_BLANK: CalDraft = {
  calibratedOn: "",
  nextDueOn: "",
  result: "PASS",
  agency: "",
  certificateNo: "",
};
type Panel = { kind: "detail" | "form" | "calibrate"; id: number | null };

export function Gauges() {
  const { fail } = useSession();
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState<Gauge[]>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [detail, setDetail] = useState<Gauge>();
  const [draft, setDraft] = useState<Draft>(BLANK);
  const [initial, setInitial] = useState<Draft>(BLANK);
  const [cal, setCal] = useState<CalDraft>(CAL_BLANK);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [done, setDone] = useState("");
  const {
    send,
    pending,
    error: saveError,
    setError: setSaveError,
  } = useSend(() => setReload((n) => n + 1));
  const dirty =
    panel?.kind === "form"
      ? JSON.stringify(draft) !== JSON.stringify(initial)
      : panel?.kind === "calibrate"
        ? JSON.stringify(cal) !== JSON.stringify(CAL_BLANK)
        : false;
  const guard = useDiscardGuard(dirty);

  useEffect(() => {
    const controller = new AbortController();
    api<Gauge[]>(
      `${QMS}/gauges?limit=100${status ? `&status=${status}` : ""}`,
      {
        signal: controller.signal,
      },
    )
      .then((r) => !controller.signal.aborted && setRows(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [status, reload]);

  if (moduleOff(error)) return <ModuleOff />;
  const errors = fieldErrors(saveError);

  async function openDetail(id: number) {
    setSaveError(undefined);
    setConfirmDelete(false);
    const r = await api<Gauge>(`${QMS}/gauges/${id}`);
    setDetail(r.data);
    setPanel({ kind: "detail", id });
  }
  function openForm(row: Gauge | null) {
    const values: Draft = row
      ? {
          code: row.code,
          name: row.name,
          gaugeKind: row.gaugeKind,
          measureRange: row.measureRange ?? "",
          resolution: row.resolution ?? "",
          calibrationCycleDays: String(row.calibrationCycleDays),
          status: row.status,
        }
      : BLANK;
    setDraft(values);
    setInitial(values);
    setSaveError(undefined);
    setPanel({ kind: "form", id: row?.id ?? null });
  }
  function openCalibrate() {
    if (!detail) return;
    setCal(CAL_BLANK);
    setSaveError(undefined);
    setPanel({ kind: "calibrate", id: detail.id });
  }

  async function submitGauge(event: FormEvent) {
    event.preventDefault();
    const body = {
      name: draft.name,
      gaugeKind: draft.gaugeKind,
      measureRange: draft.measureRange.trim() || null,
      resolution: draft.resolution.trim() || null,
      calibrationCycleDays: Number(draft.calibrationCycleDays),
      status: draft.status,
    };
    const saved = panel?.id
      ? await send<Gauge>(`/gauges/${panel.id}`, "PATCH", body)
      : await send<Gauge>("/gauges", "POST", { ...body, code: draft.code });
    if (saved) {
      setDone(`${saved.code} 저장했습니다.`);
      await openDetail(saved.id);
    }
  }
  async function submitCalibration(event: FormEvent) {
    event.preventDefault();
    if (!detail) return;
    const saved = await send<{ gaugeStatus: GaugeStatus }>(
      `/gauges/${detail.id}/calibrations`,
      "POST",
      {
        calibratedOn: cal.calibratedOn,
        nextDueOn: cal.nextDueOn || null,
        result: cal.result,
        agency: cal.agency.trim() || null,
        certificateNo: cal.certificateNo.trim() || null,
      },
    );
    if (saved) {
      setDone(
        `교정을 기록했습니다. 계측기 상태: ${GAUGE_STATUS[saved.gaugeStatus]}`,
      );
      await openDetail(detail.id);
    }
  }
  async function remove() {
    if (!detail) return;
    const gone = await send(`/gauges/${detail.id}`, "DELETE");
    if (gone !== undefined) {
      setDone(`${detail.code}을(를) 삭제했습니다.`);
      setPanel(null);
      setDetail(undefined);
    }
  }

  const columns: Column<Gauge>[] = [
    { key: "code", label: "번호" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={panel?.id === r.id}
          onClick={() => guard.guard(() => void openDetail(r.id))}
        >
          상세
        </button>
      ),
    },
    { key: "name", label: "이름" },
    { key: "gaugeKind", label: "종류" },
    {
      key: "calibrationCycleDays",
      label: "교정 주기",
      render: (r) => `${r.calibrationCycleDays}일`,
    },
    {
      key: "status",
      label: "상태",
      render: (r) => <GaugeStatusBadge status={r.status} />,
    },
    {
      key: "nextDueOn",
      label: "교정 도래",
      render: (r) => <DueBadge gauge={r} />,
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="Q-11"
        title="계측기·교정"
        subtitle="계측기 대장과 교정 이력을 관리하고 교정 도래를 봅니다"
        help="qms/q-11"
      />
      <p className="muted" role="note">
        <strong>교정 도래는 마지막 교정의 다음 기한에서 계산합니다.</strong>{" "}
        기한이 30일 이내면 임박, 지났으면 기한 경과로 표시합니다. 표시일 뿐
        검사를 막지는 않습니다. 교정 결과가 불합격이면 계측기가 수리 중이 되고,
        수리 중인 계측기가 합격하면 다시 사용 중이 됩니다.
      </p>
      {done && <p role="status">{done}</p>}
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!rows ? (
        !error && <Loading delay={300} />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="filter-bar">
              <label>
                상태
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value="">전체</option>
                  <option value="ACTIVE">사용 중</option>
                  <option value="REPAIR">수리 중</option>
                  <option value="RETIRED">폐기</option>
                </select>
              </label>
              <button
                type="button"
                onClick={() => guard.guard(() => openForm(null))}
              >
                계측기 등록
              </button>
            </div>
            <DataTable
              rows={rows}
              columns={columns}
              caption="계측기 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="등록한 계측기가 없습니다. 계측기를 등록하면 교정 이력을 남길 수 있습니다."
                  action="계측기 등록"
                  onAction={() => guard.guard(() => openForm(null))}
                />
              }
            />
          </section>

          {panel?.kind === "detail" && detail && (
            <DetailPanel
              key={`detail-${detail.id}`}
              title={`${detail.code} ${detail.name}`}
              onClose={() => setPanel(null)}
              actions={
                <>
                  <button type="button" onClick={() => openForm(detail)}>
                    수정
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={openCalibrate}
                    disabled={detail.status === "RETIRED"}
                  >
                    교정 등록
                  </button>
                  {confirmDelete ? (
                    <button
                      type="button"
                      className="secondary"
                      disabled={pending}
                      onClick={() => void remove()}
                    >
                      삭제 확정
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => setConfirmDelete(true)}
                    >
                      삭제
                    </button>
                  )}
                </>
              }
            >
              <ErrorNotice error={saveError} />
              <p>
                <GaugeStatusBadge status={detail.status} /> {detail.gaugeKind} ·
                교정 주기 {detail.calibrationCycleDays}일
              </p>
              <p className="muted">
                측정 범위 {detail.measureRange ?? "—"} · 분해능{" "}
                {detail.resolution ?? "—"}
              </p>
              <p>
                교정 도래: <DueBadge gauge={detail} />
              </p>
              {detail.status === "RETIRED" && (
                <p className="muted">
                  폐기한 계측기에는 교정을 기록할 수 없습니다.
                </p>
              )}
              <div className="section-block">
                <DataTable
                  rows={detail.calibrations ?? []}
                  columns={[
                    { key: "calibratedOn", label: "교정일" },
                    { key: "nextDueOn", label: "다음 기한" },
                    {
                      key: "result",
                      label: "결과",
                      render: (c) => <ResultBadge result={c.result} />,
                    },
                    {
                      key: "agency",
                      label: "기관",
                      render: (c) => c.agency ?? "—",
                    },
                    {
                      key: "certificateNo",
                      label: "성적서",
                      render: (c) => c.certificateNo ?? "—",
                    },
                  ]}
                  caption="교정 이력"
                  offset={0}
                  total={detail.calibrations?.length ?? 0}
                  limit={detail.calibrations?.length || 1}
                  onPage={() => undefined}
                  empty={
                    <p className="muted">
                      교정 기록이 없습니다. 교정 등록으로 첫 기록을 남기세요.
                    </p>
                  }
                />
              </div>
            </DetailPanel>
          )}

          {panel?.kind === "form" && (
            <FormPanel
              key={`form-${panel.id ?? "new"}`}
              title={panel.id ? "계측기 수정" : "계측기 등록"}
              guard={guard}
              onClose={() =>
                panel.id ? void openDetail(panel.id) : setPanel(null)
              }
              onSubmit={(e) => void submitGauge(e)}
              actions={
                <button type="submit" disabled={pending} aria-busy={pending}>
                  저장
                </button>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              {!panel.id && (
                <div className="field">
                  <label htmlFor="gauge-code">계측기 번호</label>
                  <input
                    id="gauge-code"
                    required
                    maxLength={30}
                    pattern={CODE_PATTERN}
                    title="영문 대문자·숫자로 시작하는 1~30자"
                    value={draft.code}
                    aria-invalid={!!errors.code}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        code: e.target.value.toUpperCase(),
                      })
                    }
                  />
                  {errors.code && <small>{errors.code}</small>}
                </div>
              )}
              <div className="field">
                <label htmlFor="gauge-name">계측기명</label>
                <input
                  id="gauge-name"
                  required
                  maxLength={100}
                  value={draft.name}
                  aria-invalid={!!errors.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
                {errors.name && <small>{errors.name}</small>}
              </div>
              <div className="field">
                <label htmlFor="gauge-kind">종류</label>
                <input
                  id="gauge-kind"
                  required
                  maxLength={40}
                  placeholder="버니어 캘리퍼스"
                  value={draft.gaugeKind}
                  aria-invalid={!!errors.gaugeKind}
                  onChange={(e) =>
                    setDraft({ ...draft, gaugeKind: e.target.value })
                  }
                />
                {errors.gaugeKind && <small>{errors.gaugeKind}</small>}
              </div>
              <div className="field">
                <label htmlFor="gauge-range">측정 범위 (선택)</label>
                <input
                  id="gauge-range"
                  maxLength={60}
                  placeholder="0~150 mm"
                  value={draft.measureRange}
                  onChange={(e) =>
                    setDraft({ ...draft, measureRange: e.target.value })
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="gauge-resolution">분해능 (선택)</label>
                <input
                  id="gauge-resolution"
                  maxLength={30}
                  placeholder="0.01 mm"
                  value={draft.resolution}
                  onChange={(e) =>
                    setDraft({ ...draft, resolution: e.target.value })
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="gauge-cycle">교정 주기(일)</label>
                <input
                  id="gauge-cycle"
                  type="number"
                  required
                  min={1}
                  max={1825}
                  value={draft.calibrationCycleDays}
                  aria-invalid={!!errors.calibrationCycleDays}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      calibrationCycleDays: e.target.value,
                    })
                  }
                />
                <small>
                  교정 기한을 비워 두면 이 주기로 다음 기한을 정합니다.
                </small>
              </div>
              <div className="field">
                <label htmlFor="gauge-status">상태</label>
                <select
                  id="gauge-status"
                  value={draft.status}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      status: e.target.value as GaugeStatus,
                    })
                  }
                >
                  {(
                    Object.keys(GAUGE_STATUS) as (keyof typeof GAUGE_STATUS)[]
                  ).map((s) => (
                    <option key={s} value={s}>
                      {GAUGE_STATUS[s]}
                    </option>
                  ))}
                </select>
              </div>
            </FormPanel>
          )}

          {panel?.kind === "calibrate" && detail && (
            <FormPanel
              key={`cal-${detail.id}`}
              title={`${detail.code} 교정 등록`}
              guard={guard}
              onClose={() => void openDetail(detail.id)}
              onSubmit={(e) => void submitCalibration(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    기록
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      guard.guard(() => void openDetail(detail.id))
                    }
                  >
                    계측기 상세로
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <div className="field">
                <label htmlFor="cal-on">교정일</label>
                <input
                  id="cal-on"
                  type="date"
                  required
                  value={cal.calibratedOn}
                  aria-invalid={!!errors.calibratedOn}
                  onChange={(e) =>
                    setCal({ ...cal, calibratedOn: e.target.value })
                  }
                />
                {errors.calibratedOn && <small>{errors.calibratedOn}</small>}
              </div>
              <div className="field">
                <label htmlFor="cal-due">다음 기한 (선택)</label>
                <input
                  id="cal-due"
                  type="date"
                  value={cal.nextDueOn}
                  aria-invalid={!!errors.nextDueOn}
                  onChange={(e) =>
                    setCal({ ...cal, nextDueOn: e.target.value })
                  }
                />
                <small>
                  비워 두면 교정 주기 {detail.calibrationCycleDays}일로
                  정합니다.
                </small>
                {errors.nextDueOn && <small>{errors.nextDueOn}</small>}
              </div>
              <fieldset className="field">
                <legend>결과</legend>
                {(["PASS", "FAIL"] as const).map((r) => (
                  <label key={r} className="inline-check">
                    <input
                      type="radio"
                      name="cal-result"
                      checked={cal.result === r}
                      onChange={() => setCal({ ...cal, result: r })}
                    />
                    {r === "PASS" ? "합격" : "불합격 (수리 중으로)"}
                  </label>
                ))}
              </fieldset>
              <div className="field">
                <label htmlFor="cal-agency">교정 기관 (선택)</label>
                <input
                  id="cal-agency"
                  maxLength={100}
                  value={cal.agency}
                  onChange={(e) => setCal({ ...cal, agency: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="cal-cert">성적서 번호 (선택)</label>
                <input
                  id="cal-cert"
                  maxLength={60}
                  value={cal.certificateNo}
                  onChange={(e) =>
                    setCal({ ...cal, certificateNo: e.target.value })
                  }
                />
              </div>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
