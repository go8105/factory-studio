// C-03 작업지시 — 접수 → 진행 → 완료/취소 (UI-02 L 패턴 + DetailPanel wide, FS-029 D47).
// 완료·취소 뒤에는 바꿀 수 없다. MTBF·MTTR이 여기 찍힌 시각들로 계산되기 때문이다.
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
import { useApiSend } from "../shared/hooks";
import { fieldErrors, moduleOff, useGet } from "./hooks";
import {
  CAUSE_LABEL,
  CMMS,
  WO_KIND_LABEL,
  WO_SOURCE_LABEL,
  WO_STATUS_LABEL,
  WO_STATUS_TONE,
  duration,
  money,
  time,
  type AssetNode,
  type Cause,
  type FailureCode,
  type Technician,
  type Vendor,
  type WorkOrder,
} from "./common";

function OrderDetail({
  order,
  onChanged,
}: {
  order: WorkOrder;
  onChanged: () => void;
}) {
  const detail = useGet<WorkOrder>(`/work-orders/${order.id}`);
  const technicians = useGet<Technician[]>("/technicians?active=true");
  const vendors = useGet<Vendor[]>("/vendors?active=true");
  const actions = useGet<FailureCode[]>(
    "/failure-codes?kind=ACTION&active=true",
  );
  const [minutes, setMinutes] = useState("30");
  const [note, setNote] = useState("");
  const [cause, setCause] = useState<Cause>("WEAR");
  const [action, setAction] = useState("");
  const [actionCodeId, setActionCodeId] = useState("");
  const [vendorId, setVendorId] = useState("");
  const [externalCost, setExternalCost] = useState("");
  const [reason, setReason] = useState("");
  const { send, pending, error } = useApiSend(CMMS, () => {
    detail.reload();
    onChanged();
  });
  const errors = fieldErrors(error);
  if (!detail.data)
    return detail.error ? <ErrorNotice error={detail.error} /> : <Loading />;
  const row = detail.data;
  const logs = row.logs ?? [];
  const totalMinutes = logs.reduce((sum, l) => sum + l.minutes, 0);
  const open = row.status === "REQUESTED" || row.status === "IN_PROGRESS";
  const send1 = (path: string, body: unknown) => () =>
    void send(`/work-orders/${row.id}/${path}`, "POST", body);
  return (
    <>
      <p className="muted">
        {row.assetCode} · {row.assetName} · {WO_KIND_LABEL[row.kind]} ·{" "}
        {WO_SOURCE_LABEL[row.source]} ·{" "}
        <Badge tone={WO_STATUS_TONE[row.status]}>
          {WO_STATUS_LABEL[row.status]}
        </Badge>
      </p>
      {row.sourceSummary && (
        <p role="note" className="muted">
          원천 기록: {row.sourceSummary}
        </p>
      )}
      {row.description && <p>{row.description}</p>}
      <dl className="spc-figures">
        <dt>접수</dt>
        <dd>{time(row.requestedAt)}</dd>
        {row.failureAt && (
          <>
            <dt>고장</dt>
            <dd>{time(row.failureAt)}</dd>
          </>
        )}
        {row.startedAt && (
          <>
            <dt>시작</dt>
            <dd>{time(row.startedAt)}</dd>
          </>
        )}
        {row.completedAt && (
          <>
            <dt>완료</dt>
            <dd>{time(row.completedAt)}</dd>
          </>
        )}
        {row.restoredAt && (
          <>
            <dt>복구</dt>
            <dd>{time(row.restoredAt)}</dd>
          </>
        )}
        {row.symptomCode && (
          <>
            <dt>증상</dt>
            <dd>
              {row.symptomCode} {row.symptomName}
            </dd>
          </>
        )}
        <dt>담당</dt>
        <dd>{row.technicianName ?? "미정"}</dd>
      </dl>
      <section>
        <h3>작업 기록</h3>
        {logs.length ? (
          <>
            <ul className="spc-trend">
              {logs.map((log) => (
                <li key={log.id}>
                  <strong>{time(log.loggedAt)}</strong>
                  <span>{duration(log.minutes)}</span>
                  <small className="muted">
                    {log.technicianName ?? "담당 미정"}
                    {log.note && ` · ${log.note}`}
                  </small>
                </li>
              ))}
            </ul>
            <p className="muted">
              합계 {duration(totalMinutes)} — 인건비의 근거입니다.
            </p>
          </>
        ) : (
          <p className="muted">작업 기록이 없습니다.</p>
        )}
      </section>
      <ErrorNotice error={Object.keys(errors).length ? undefined : error} />
      {row.status === "REQUESTED" && (
        <form
          className="spc-resolve"
          onSubmit={(e) => {
            e.preventDefault();
            send1("start", {})();
          }}
        >
          <div className="field">
            <label htmlFor="wo-tech">담당 정비원</label>
            <select
              id="wo-tech"
              value={String(row.technicianId ?? "")}
              onChange={(e) =>
                void send(`/work-orders/${row.id}/start`, "POST", {
                  technicianId: e.target.value ? Number(e.target.value) : null,
                })
              }
            >
              <option value="">미정</option>
              {technicians.data?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" disabled={pending} aria-busy={pending}>
            작업 시작
          </button>
        </form>
      )}
      {row.status === "IN_PROGRESS" && (
        <>
          <form
            className="spc-resolve"
            onSubmit={(e) => {
              e.preventDefault();
              void send(`/work-orders/${row.id}/logs`, "POST", {
                minutes: Number(minutes),
                note: note || null,
              }).then(() => setNote(""));
            }}
          >
            <h3>작업 기록 추가</h3>
            <Field
              label="걸린 시간(분)"
              type="number"
              min={1}
              max={1440}
              value={minutes}
              required
              error={errors.minutes}
              onChange={(e) => setMinutes(e.target.value)}
            />
            <Field
              label="한 일(선택)"
              value={note}
              maxLength={300}
              onChange={(e) => setNote(e.target.value)}
            />
            <button type="submit" disabled={pending} aria-busy={pending}>
              기록 추가
            </button>
          </form>
          <form
            className="spc-resolve"
            onSubmit={(e) => {
              e.preventDefault();
              send1("complete", {
                causeCategory: cause,
                action,
                actionCodeId: actionCodeId ? Number(actionCodeId) : null,
                vendorId: vendorId ? Number(vendorId) : null,
                externalCost: externalCost || null,
              })();
            }}
          >
            <h3>완료 처리</h3>
            <p role="note" className="muted">
              완료하면 바꿀 수 없습니다. 복구 시각은 지금으로 찍힙니다.
            </p>
            <div className="field">
              <label htmlFor="wo-cause">원인 분류</label>
              <select
                id="wo-cause"
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
              <label htmlFor="wo-action-code">조치 코드(선택)</label>
              <select
                id="wo-action-code"
                value={actionCodeId}
                onChange={(e) => setActionCodeId(e.target.value)}
              >
                <option value="">없음</option>
                {actions.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} {c.name}
                  </option>
                ))}
              </select>
            </div>
            <Field
              label="조치 내용"
              value={action}
              required
              minLength={2}
              maxLength={500}
              error={errors.action}
              onChange={(e) => setAction(e.target.value)}
            />
            <div className="field">
              <label htmlFor="wo-vendor">외주 업체(선택)</label>
              <select
                id="wo-vendor"
                value={vendorId}
                aria-invalid={!!errors.vendorId}
                onChange={(e) => setVendorId(e.target.value)}
              >
                <option value="">직접 수리</option>
                {vendors.data?.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
              {errors.vendorId && <small>{errors.vendorId}</small>}
            </div>
            {vendorId && (
              <Field
                label="외주 비용"
                value={externalCost}
                inputMode="decimal"
                pattern="\d{1,16}(\.\d{1,2})?"
                error={errors.externalCost}
                onChange={(e) => setExternalCost(e.target.value)}
              />
            )}
            <button type="submit" disabled={pending} aria-busy={pending}>
              완료 처리
            </button>
          </form>
        </>
      )}
      {open && (
        <form
          className="spc-resolve"
          onSubmit={(e) => {
            e.preventDefault();
            send1("cancel", { reason })();
          }}
        >
          <h3>취소</h3>
          <p role="note" className="muted">
            취소하면 그 신호를 다시 전환할 수 있습니다.
          </p>
          <Field
            label="취소 사유"
            value={reason}
            required
            minLength={2}
            maxLength={300}
            error={errors.reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <button
            type="submit"
            className="secondary"
            disabled={pending}
            aria-busy={pending}
          >
            작업지시 취소
          </button>
        </form>
      )}
      {row.status === "COMPLETED" && (
        <p>
          원인 {row.causeCategory && CAUSE_LABEL[row.causeCategory]} · 조치{" "}
          {row.action}
          {row.actionCode && ` (${row.actionCode})`}
          {row.vendorName &&
            ` · 외주 ${row.vendorName} ${money(row.externalCost)}`}
        </p>
      )}
      {row.status === "CANCELLED" && (
        <p className="muted">
          취소 {row.cancelledAt && time(row.cancelledAt)} · 사유{" "}
          {row.cancelReason}
        </p>
      )}
    </>
  );
}

export function WorkOrders() {
  const [status, setStatus] = useState("");
  const list = useGet<WorkOrder[]>(
    `/work-orders${status ? `?status=${status}` : ""}`,
  );
  const assets = useGet<AssetNode[]>("/assets/tree");
  const technicians = useGet<Technician[]>("/technicians?active=true");
  const symptoms = useGet<FailureCode[]>(
    "/failure-codes?kind=SYMPTOM&active=true",
  );
  const [open, setOpen] = useState<WorkOrder | null>(null);
  const [draft, setDraft] = useState<{
    assetId: string;
    title: string;
    description: string;
    technicianId: string;
    symptomCodeId: string;
  } | null>(null);
  const { send, pending, error, setError } = useApiSend(CMMS, () =>
    list.reload(),
  );
  const guard = useDiscardGuard(!!draft && draft.title.trim() !== "");
  if (moduleOff(list.error))
    return (
      <EmptyState
        reason="CMMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const errors = fieldErrors(error);
  function start() {
    guard.guard(() => {
      setOpen(null);
      setError(undefined);
      setDraft({
        assetId: String(assets.data?.find((a) => a.isActive)?.id ?? ""),
        title: "",
        description: "",
        technicianId: "",
        symptomCodeId: "",
      });
    });
  }
  async function create(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    const saved = await send<WorkOrder>("/work-orders", "POST", {
      assetId: Number(draft.assetId),
      title: draft.title,
      description: draft.description || null,
      technicianId: draft.technicianId ? Number(draft.technicianId) : null,
      symptomCodeId: draft.symptomCodeId ? Number(draft.symptomCodeId) : null,
    });
    if (saved) {
      setDraft(null);
      setOpen(saved);
    }
  }
  const columns: Column<WorkOrder>[] = [
    { key: "woNo", label: "번호" },
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
              setError(undefined);
            })
          }
        >
          상세
        </button>
      ),
    },
    {
      key: "assetCode",
      label: "설비",
      render: (r) => `${r.assetCode} ${r.assetName}`,
    },
    { key: "title", label: "제목" },
    { key: "kind", label: "구분", render: (r) => WO_KIND_LABEL[r.kind] },
    {
      key: "source",
      label: "출처",
      render: (r) => WO_SOURCE_LABEL[r.source],
    },
    {
      key: "technicianName",
      label: "담당",
      render: (r) => r.technicianName ?? "—",
    },
    { key: "requestedAt", label: "접수", render: (r) => time(r.requestedAt) },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={WO_STATUS_TONE[r.status]}>
          {WO_STATUS_LABEL[r.status]}
        </Badge>
      ),
    },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="C-03"
        title="작업지시"
        subtitle="고장을 접수하고 진행·완료까지 기록합니다"
        help="cmms/c-03"
        actions={
          <button
            type="button"
            aria-pressed={!!draft}
            disabled={!assets.data?.length}
            title={
              !assets.data?.length ? "설비 대장이 비어 있습니다." : undefined
            }
            onClick={start}
          >
            고장 접수
          </button>
        }
      />
      <ErrorNotice error={list.error} retry={() => list.reload()} />
      <div className="filter-bar">
        <label>
          상태
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">전체</option>
            <option value="REQUESTED">접수</option>
            <option value="IN_PROGRESS">진행</option>
            <option value="COMPLETED">완료</option>
            <option value="CANCELLED">취소</option>
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
              caption="작업지시(최근 500건)"
              offset={0}
              total={list.data.length}
              limit={list.data.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="작업지시가 없습니다. 고장을 접수하거나 전환 대기 신호에서 가져오세요."
                  to="/cmms/signals"
                  action="전환 대기 신호"
                />
              }
            />
          </section>
          {draft ? (
            <FormPanel
              title="고장 접수"
              guard={guard}
              onClose={() => setDraft(null)}
              onSubmit={(e) => void create(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    접수
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
              <div className="field">
                <label htmlFor="wo-asset">설비</label>
                <select
                  id="wo-asset"
                  value={draft.assetId}
                  aria-invalid={!!errors.assetId}
                  onChange={(e) =>
                    setDraft({ ...draft, assetId: e.target.value })
                  }
                >
                  {assets.data
                    ?.filter((a) => a.isActive)
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.code} {a.name}
                      </option>
                    ))}
                </select>
                {errors.assetId && <small>{errors.assetId}</small>}
              </div>
              <Field
                label="제목"
                value={draft.title}
                required
                maxLength={200}
                error={errors.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              />
              <Field
                label="상세(선택)"
                value={draft.description}
                maxLength={1000}
                onChange={(e) =>
                  setDraft({ ...draft, description: e.target.value })
                }
              />
              <div className="field">
                <label htmlFor="wo-symptom">증상 코드(선택)</label>
                <select
                  id="wo-symptom"
                  value={draft.symptomCodeId}
                  aria-invalid={!!errors.symptomCodeId}
                  onChange={(e) =>
                    setDraft({ ...draft, symptomCodeId: e.target.value })
                  }
                >
                  <option value="">없음</option>
                  {symptoms.data?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.code} {c.name}
                    </option>
                  ))}
                </select>
                {errors.symptomCodeId && <small>{errors.symptomCodeId}</small>}
              </div>
              <div className="field">
                <label htmlFor="wo-new-tech">담당 정비원(선택)</label>
                <select
                  id="wo-new-tech"
                  value={draft.technicianId}
                  onChange={(e) =>
                    setDraft({ ...draft, technicianId: e.target.value })
                  }
                >
                  <option value="">미정</option>
                  {technicians.data?.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>
            </FormPanel>
          ) : (
            open && (
              <DetailPanel
                wide
                title={`${open.woNo} ${open.title}`}
                guard={guard}
                onClose={() => setOpen(null)}
              >
                <OrderDetail
                  key={open.id}
                  order={open}
                  onChanged={() => list.reload()}
                />
              </DetailPanel>
            )
          )}
        </div>
      )}
    </div>
  );
}
