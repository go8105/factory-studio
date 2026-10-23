// Q-08 시정·예방 조치 — 목록 + 상세(완료·유효성 확인) + 수정 (DSN-14 F32).
// 조치는 부적합 보고에 속한다. 새 조치는 Q-07 부적합 보고 상세에서 만든다.
import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
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
import {
  CAPA_KIND,
  CAPA_STATUS,
  CapaBadge,
  fieldErrors,
  ModuleOff,
  moduleOff,
  QMS,
  time,
  useSend,
  type Capa,
  type CapaKind,
  type CapaStatus,
} from "./common";

type Draft = {
  kind: CapaKind;
  rootCause: string;
  action: string;
  ownerName: string;
  dueOn: string;
};
type Verify = { effective: boolean; note: string };
const VERIFY_BLANK: Verify = { effective: true, note: "" };
type Panel = { kind: "detail" | "form" | "verify"; id: number };

export function Capas() {
  const { fail } = useSession();
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState<Capa[]>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [detail, setDetail] = useState<Capa>();
  const [draft, setDraft] = useState<Draft>();
  const [initial, setInitial] = useState<Draft>();
  const [verify, setVerify] = useState<Verify>(VERIFY_BLANK);
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
      : panel?.kind === "verify"
        ? verify.note !== ""
        : false;
  const guard = useDiscardGuard(dirty);

  useEffect(() => {
    const controller = new AbortController();
    api<Capa[]>(`${QMS}/capas${status ? `?status=${status}` : ""}`, {
      signal: controller.signal,
    })
      .then((r) => !controller.signal.aborted && setRows(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [status, reload]);

  // Q-07에서 ?open=id로 넘어오면 그 조치를 연다.
  const open = params.get("open");
  useEffect(() => {
    if (!open) return;
    setParams({}, { replace: true });
    void openDetail(Number(open));
  }, [open]);

  if (moduleOff(error)) return <ModuleOff />;
  const errors = fieldErrors(saveError);

  async function openDetail(id: number) {
    setSaveError(undefined);
    const r = await api<Capa>(`${QMS}/capas/${id}`);
    setDetail(r.data);
    setPanel({ kind: "detail", id });
  }
  function openForm(row: Capa) {
    const values: Draft = {
      kind: row.kind,
      rootCause: row.rootCause,
      action: row.action,
      ownerName: row.ownerName,
      dueOn: row.dueOn,
    };
    setDraft(values);
    setInitial(values);
    setSaveError(undefined);
    setPanel({ kind: "form", id: row.id });
  }

  async function submitEdit(event: FormEvent) {
    event.preventDefault();
    if (!detail || !draft) return;
    const saved = await send<Capa>(`/capas/${detail.id}`, "PATCH", draft);
    if (saved) {
      setDone(`${saved.capaNo} 저장했습니다.`);
      await openDetail(detail.id);
    }
  }
  async function complete() {
    if (!detail) return;
    const saved = await send<Capa>(`/capas/${detail.id}/completion`, "POST");
    if (saved) {
      setDone(`${saved.capaNo} 완료`);
      await openDetail(detail.id);
    }
  }
  async function submitVerify(event: FormEvent) {
    event.preventDefault();
    if (!detail) return;
    const saved = await send<Capa>(`/capas/${detail.id}/verification`, "POST", {
      effective: verify.effective,
      note: verify.note,
    });
    if (saved) {
      setDone(`${saved.capaNo} ${CAPA_STATUS[saved.status]}`);
      await openDetail(detail.id);
    }
  }

  const columns: Column<Capa>[] = [
    { key: "capaNo", label: "조치 번호" },
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
    { key: "ncrNo", label: "부적합" },
    { key: "kind", label: "종류", render: (r) => CAPA_KIND[r.kind] },
    { key: "itemCode", label: "품목" },
    { key: "ownerName", label: "담당" },
    { key: "dueOn", label: "기한" },
    {
      key: "status",
      label: "상태",
      render: (r) => <CapaBadge status={r.status} />,
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="Q-08"
        title="시정·예방 조치"
        subtitle="부적합의 근본 원인과 대책을 세우고 유효성을 확인합니다"
        help="qms/q-08"
      />
      <p className="muted" role="note">
        <strong>진행 → 완료 → 유효성 확인</strong> 순서입니다. 무효로 확인하면
        되돌리지 않고 <Link to="/qms/ncrs">부적합 보고</Link>에서 새 조치를
        만듭니다. 새 조치도 부적합 보고 상세에서 만듭니다.
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
                  {(Object.keys(CAPA_STATUS) as CapaStatus[]).map((s) => (
                    <option key={s} value={s}>
                      {CAPA_STATUS[s]}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <DataTable
              rows={rows}
              columns={columns}
              caption="시정·예방 조치 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="조치가 없습니다. 부적합 보고 상세에서 조치를 만듭니다."
                  to="/qms/ncrs"
                  action="부적합 보고로"
                />
              }
            />
          </section>

          {panel?.kind === "detail" && detail && (
            <DetailPanel
              key={`detail-${detail.id}`}
              title={`${detail.capaNo} · ${CAPA_KIND[detail.kind]} 조치`}
              onClose={() => setPanel(null)}
              actions={
                <>
                  {detail.status === "OPEN" && (
                    <>
                      <button type="button" onClick={() => openForm(detail)}>
                        수정
                      </button>
                      <button
                        type="button"
                        disabled={pending}
                        onClick={() => void complete()}
                      >
                        완료
                      </button>
                    </>
                  )}
                  {detail.status === "DONE" && (
                    <button
                      type="button"
                      onClick={() => {
                        setVerify(VERIFY_BLANK);
                        setSaveError(undefined);
                        setPanel({ kind: "verify", id: detail.id });
                      }}
                    >
                      유효성 확인
                    </button>
                  )}
                </>
              }
            >
              <ErrorNotice error={saveError} />
              <p>
                <CapaBadge status={detail.status} /> 부적합{" "}
                <Link to="/qms/ncrs">{detail.ncrNo}</Link> · {detail.itemCode} ·
                담당 {detail.ownerName} · 기한 {detail.dueOn}
              </p>
              {detail.doneAt && (
                <p className="muted">
                  완료 {time(detail.doneAt)}
                  {detail.verifiedAt && ` · 확인 ${time(detail.verifiedAt)}`}
                </p>
              )}
              <h3>근본 원인</h3>
              <p className="wrap">{detail.rootCause}</p>
              <h3>대책</h3>
              <p className="wrap">{detail.action}</p>
              {detail.verificationNote && (
                <>
                  <h3>유효성 확인</h3>
                  <p className="wrap">{detail.verificationNote}</p>
                </>
              )}
              {detail.status === "INEFFECTIVE" && (
                <p className="muted">
                  무효로 확인한 조치입니다. 부적합 보고에서 새 조치를 만드세요.
                </p>
              )}
            </DetailPanel>
          )}

          {panel?.kind === "form" && detail && draft && (
            <FormPanel
              key={`form-${detail.id}`}
              title={`${detail.capaNo} 수정`}
              guard={guard}
              onClose={() => void openDetail(detail.id)}
              onSubmit={(e) => void submitEdit(e)}
              actions={
                <button type="submit" disabled={pending} aria-busy={pending}>
                  저장
                </button>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <div className="field">
                <label htmlFor="edit-kind">종류</label>
                <select
                  id="edit-kind"
                  value={draft.kind}
                  onChange={(e) =>
                    setDraft({ ...draft, kind: e.target.value as CapaKind })
                  }
                >
                  {(Object.keys(CAPA_KIND) as CapaKind[]).map((k) => (
                    <option key={k} value={k}>
                      {CAPA_KIND[k]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="edit-cause">근본 원인</label>
                <textarea
                  id="edit-cause"
                  required
                  minLength={2}
                  maxLength={1000}
                  rows={3}
                  value={draft.rootCause}
                  aria-invalid={!!errors.rootCause}
                  onChange={(e) =>
                    setDraft({ ...draft, rootCause: e.target.value })
                  }
                />
                {errors.rootCause && <small>{errors.rootCause}</small>}
              </div>
              <div className="field">
                <label htmlFor="edit-action">대책</label>
                <textarea
                  id="edit-action"
                  required
                  minLength={2}
                  maxLength={1000}
                  rows={3}
                  value={draft.action}
                  aria-invalid={!!errors.action}
                  onChange={(e) =>
                    setDraft({ ...draft, action: e.target.value })
                  }
                />
                {errors.action && <small>{errors.action}</small>}
              </div>
              <div className="field">
                <label htmlFor="edit-owner">담당</label>
                <input
                  id="edit-owner"
                  required
                  maxLength={60}
                  value={draft.ownerName}
                  aria-invalid={!!errors.ownerName}
                  onChange={(e) =>
                    setDraft({ ...draft, ownerName: e.target.value })
                  }
                />
                {errors.ownerName && <small>{errors.ownerName}</small>}
              </div>
              <div className="field">
                <label htmlFor="edit-due">기한</label>
                <input
                  id="edit-due"
                  type="date"
                  required
                  value={draft.dueOn}
                  aria-invalid={!!errors.dueOn}
                  onChange={(e) =>
                    setDraft({ ...draft, dueOn: e.target.value })
                  }
                />
                {errors.dueOn && <small>{errors.dueOn}</small>}
              </div>
            </FormPanel>
          )}

          {panel?.kind === "verify" && detail && (
            <FormPanel
              key={`verify-${detail.id}`}
              title={`${detail.capaNo} 유효성 확인`}
              guard={guard}
              onClose={() => void openDetail(detail.id)}
              onSubmit={(e) => void submitVerify(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    확인
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      guard.guard(() => void openDetail(detail.id))
                    }
                  >
                    조치 상세로
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <p className="muted">확인한 뒤에는 되돌릴 수 없습니다.</p>
              <fieldset className="field">
                <legend>판정</legend>
                {[true, false].map((effective) => (
                  <label key={String(effective)} className="inline-check">
                    <input
                      type="radio"
                      name="capa-effective"
                      checked={verify.effective === effective}
                      onChange={() => setVerify({ ...verify, effective })}
                    />
                    {effective ? "유효" : "무효"}
                  </label>
                ))}
              </fieldset>
              <div className="field">
                <label htmlFor="verify-note">확인 내용</label>
                <textarea
                  id="verify-note"
                  required
                  minLength={2}
                  maxLength={500}
                  rows={3}
                  value={verify.note}
                  aria-invalid={!!errors.note}
                  onChange={(e) =>
                    setVerify({ ...verify, note: e.target.value })
                  }
                />
                <small>
                  대책이 실제로 들었는지 적습니다(재발 여부·확인 방법).
                </small>
                {errors.note && <small>{errors.note}</small>}
              </div>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
