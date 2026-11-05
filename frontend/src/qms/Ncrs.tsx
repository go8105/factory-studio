// Q-07 부적합 보고 — 목록 + 상세(연결 조치·종결) + 신규/수정 (DSN-14 F31).
// 발생처마다 근거가 다르다: 수입·출하는 불합격 검사, 공정은 MES 불량, 고객은 클레임(Q-09, 1e).
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
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
  CapaBadge,
  fieldErrors,
  ModuleOff,
  moduleOff,
  NCR_ORIGIN,
  NcrBadge,
  num,
  QMS,
  time,
  useSend,
  type DefectType,
  type Inspection,
  type MesDefect,
  type Ncr,
  type NcrOrigin,
} from "./common";

/** 고객 발생은 클레임에서 만든다 — 여기서는 고르지 못한다. */
const ORIGINS: NcrOrigin[] = ["PROCESS", "OUTGOING", "INCOMING"];
type Draft = {
  origin: NcrOrigin;
  itemCode: string;
  lotNo: string;
  qty: string;
  defectTypeId: string;
  description: string;
  immediateAction: string;
  inspectionId: string;
  sourceRef: string;
};
const BLANK: Draft = {
  origin: "PROCESS",
  itemCode: "",
  lotNo: "",
  qty: "",
  defectTypeId: "",
  description: "",
  immediateAction: "",
  inspectionId: "",
  sourceRef: "",
};
type CapaDraft = {
  kind: "CORRECTIVE" | "PREVENTIVE";
  rootCause: string;
  action: string;
  ownerName: string;
  dueOn: string;
};
const CAPA_BLANK: CapaDraft = {
  kind: "CORRECTIVE",
  rootCause: "",
  action: "",
  ownerName: "",
  dueOn: "",
};
type Sources = {
  mesEnabled: boolean;
  rows: (Inspection | MesDefect)[];
};
type Panel = { kind: "detail" | "form" | "capa"; id: number | null };

const isDefect = (row: Inspection | MesDefect): row is MesDefect =>
  "sourceRef" in row;

export function Ncrs() {
  const { fail } = useSession();
  const [status, setStatus] = useState("OPEN");
  const [rows, setRows] = useState<Ncr[]>();
  const [defectTypes, setDefectTypes] = useState<DefectType[]>([]);
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [detail, setDetail] = useState<Ncr>();
  const [draft, setDraft] = useState<Draft>(BLANK);
  const [initial, setInitial] = useState<Draft>(BLANK);
  const [sources, setSources] = useState<Sources>();
  const [month, setMonth] = useState("");
  const [capa, setCapa] = useState<CapaDraft>(CAPA_BLANK);
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
      : panel?.kind === "capa"
        ? JSON.stringify(capa) !== JSON.stringify(CAPA_BLANK)
        : false;
  const guard = useDiscardGuard(dirty);

  useEffect(() => {
    const controller = new AbortController();
    api<Ncr[]>(`${QMS}/ncrs${status ? `?status=${status}` : ""}`, {
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

  useEffect(() => {
    api<DefectType[]>(`${QMS}/defect-types`)
      .then((r) => setDefectTypes(r.data.filter((d) => d.isActive)))
      .catch(() => setDefectTypes([]));
  }, []);

  // 발생처(또는 달)를 바꾸면 근거 후보를 다시 읽는다.
  useEffect(() => {
    if (panel?.kind !== "form" || panel.id !== null) return;
    const query =
      `origin=${draft.origin}` +
      (draft.origin === "PROCESS" && month ? `&month=${month}` : "");
    setSources(undefined);
    api<Sources>(`${QMS}/ncrs/sources?${query}`)
      .then((r) => setSources(r.data))
      .catch(() => setSources({ mesEnabled: true, rows: [] }));
  }, [panel?.kind, panel?.id, draft.origin, month]);

  if (moduleOff(error)) return <ModuleOff />;
  const errors = fieldErrors(saveError);

  async function openDetail(id: number) {
    setSaveError(undefined);
    const r = await api<Ncr>(`${QMS}/ncrs/${id}`);
    setDetail(r.data);
    setPanel({ kind: "detail", id });
  }
  function openForm(row: Ncr | null) {
    const values: Draft = row
      ? {
          origin: row.origin,
          itemCode: row.itemCode,
          lotNo: row.lotNo ?? "",
          qty: row.qty,
          defectTypeId: row.defectTypeId ? String(row.defectTypeId) : "",
          description: row.description,
          immediateAction: row.immediateAction ?? "",
          inspectionId: row.inspectionId ? String(row.inspectionId) : "",
          sourceRef: row.sourceRef ?? "",
        }
      : BLANK;
    setDraft(values);
    setInitial(values);
    setSaveError(undefined);
    setPanel({ kind: "form", id: row?.id ?? null });
  }

  /** 근거를 고르면 품목·LOT·수량을 그 자리에서 채운다 — 손으로 옮겨 적지 않는다. */
  function pickSource(value: string) {
    const row = sources?.rows.find((r) =>
      isDefect(r) ? r.sourceRef === value : String(r.id) === value,
    );
    if (!row) {
      setDraft({ ...draft, inspectionId: "", sourceRef: "" });
      return;
    }
    if (isDefect(row))
      setDraft({
        ...draft,
        sourceRef: row.sourceRef,
        inspectionId: "",
        itemCode: row.itemCode,
        lotNo: row.lotNo,
        qty: row.defectQty,
      });
    else
      setDraft({
        ...draft,
        inspectionId: String(row.id),
        sourceRef: "",
        itemCode: row.itemCode,
        lotNo: row.lotNo,
        qty: row.sampleQty,
      });
  }

  async function submitNcr(event: FormEvent) {
    event.preventDefault();
    const common = {
      lotNo: draft.lotNo.trim() || null,
      qty: draft.qty,
      defectTypeId: draft.defectTypeId ? Number(draft.defectTypeId) : null,
      description: draft.description,
      immediateAction: draft.immediateAction.trim() || null,
    };
    const saved = panel?.id
      ? await send<Ncr>(`/ncrs/${panel.id}`, "PATCH", common)
      : await send<Ncr>("/ncrs", "POST", {
          ...common,
          origin: draft.origin,
          itemCode: draft.itemCode,
          inspectionId: draft.inspectionId ? Number(draft.inspectionId) : null,
          sourceRef: draft.sourceRef || null,
        });
    if (saved) {
      setDone(`${saved.ncrNo} 저장했습니다.`);
      await openDetail(saved.id);
    }
  }
  async function submitCapa(event: FormEvent) {
    event.preventDefault();
    if (!detail) return;
    const saved = await send<{ capaNo: string }>("/capas", "POST", {
      ncrId: detail.id,
      ...capa,
    });
    if (saved) {
      setDone(`${saved.capaNo} 조치를 만들었습니다.`);
      await openDetail(detail.id);
    }
  }
  async function close() {
    if (!detail) return;
    const saved = await send<Ncr>(`/ncrs/${detail.id}/closure`, "POST");
    if (saved) {
      setDone(`${saved.ncrNo} 종결`);
      await openDetail(detail.id);
    }
  }

  const columns: Column<Ncr>[] = [
    { key: "ncrNo", label: "보고 번호" },
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
    { key: "origin", label: "발생처", render: (r) => NCR_ORIGIN[r.origin] },
    { key: "itemCode", label: "품목" },
    { key: "lotNo", label: "LOT", render: (r) => r.lotNo ?? "—" },
    { key: "qty", label: "수량", render: (r) => num(r.qty) },
    {
      key: "capaCount",
      label: "조치",
      render: (r) =>
        r.capaCount === 0 ? (
          <span className="muted">없음</span>
        ) : (
          `${r.verifiedCount}/${r.capaCount} 확인`
        ),
    },
    { key: "reportedOn", label: "보고일" },
    {
      key: "status",
      label: "상태",
      render: (r) => <NcrBadge status={r.status} />,
    },
  ];

  const sourceValue = draft.sourceRef || draft.inspectionId;
  return (
    <div className="page-fill">
      <PageTitle
        id="Q-07"
        title="부적합 보고"
        subtitle="수입·공정·출하·고객에서 생긴 부적합을 기록하고 조치로 닫습니다"
        help="qms/q-07"
      />
      <p className="muted" role="note">
        <strong>
          연결한 시정·예방 조치를 모두 유효성 확인해야 종결됩니다.
        </strong>{" "}
        조치가 하나도 없으면 종결할 수 없습니다. 고객 발생 부적합은 클레임
        화면에서 만듭니다.
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
                  <option value="OPEN">미결</option>
                  <option value="CLOSED">종결</option>
                  <option value="">전체</option>
                </select>
              </label>
              <button
                type="button"
                onClick={() => guard.guard(() => openForm(null))}
              >
                부적합 보고
              </button>
            </div>
            <DataTable
              rows={rows}
              columns={columns}
              caption="부적합 보고 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="부적합 보고가 없습니다. 불합격 검사나 공정 불량에서 시작합니다."
                  action="부적합 보고"
                  onAction={() => guard.guard(() => openForm(null))}
                />
              }
            />
          </section>

          {panel?.kind === "detail" && detail && (
            <DetailPanel
              wide
              key={`detail-${detail.id}`}
              title={`${detail.ncrNo} · ${NCR_ORIGIN[detail.origin]} 부적합`}
              onClose={() => setPanel(null)}
              actions={
                detail.status === "OPEN" && (
                  <>
                    <button type="button" onClick={() => openForm(detail)}>
                      수정
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setCapa(CAPA_BLANK);
                        setSaveError(undefined);
                        setPanel({ kind: "capa", id: detail.id });
                      }}
                    >
                      조치 추가
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      disabled={pending}
                      onClick={() => void close()}
                    >
                      종결
                    </button>
                  </>
                )
              }
            >
              <ErrorNotice error={saveError} />
              <p>
                <NcrBadge status={detail.status} /> {detail.itemCode} ·{" "}
                {detail.lotNo ?? "LOT 없음"} · {num(detail.qty)} · 보고{" "}
                {detail.reportedOn}
                {detail.closedAt && ` · 종결 ${time(detail.closedAt)}`}
              </p>
              <p className="wrap">{detail.description}</p>
              {detail.immediateAction && (
                <p className="muted">즉시 조치: {detail.immediateAction}</p>
              )}
              <p className="muted">
                {detail.inspectionNo
                  ? `근거 검사 ${detail.inspectionNo}`
                  : detail.sourceRef
                    ? `원천 ${detail.sourceRef}`
                    : "근거 없음(직접 입력)"}
                {detail.defectCode &&
                  ` · 불량 유형 ${detail.defectCode} ${detail.defectName}`}
              </p>
              <div className="section-block">
                <DataTable
                  rows={detail.capas ?? []}
                  columns={[
                    { key: "capaNo", label: "조치" },
                    {
                      key: "kind",
                      label: "종류",
                      render: (c) => CAPA_KIND[c.kind],
                    },
                    { key: "ownerName", label: "담당" },
                    { key: "dueOn", label: "기한" },
                    {
                      key: "status",
                      label: "상태",
                      render: (c) => <CapaBadge status={c.status} />,
                    },
                    {
                      key: "id",
                      label: "관리",
                      render: (c) => (
                        <Link to={`/qms/capas?open=${c.id}`}>열기</Link>
                      ),
                    },
                  ]}
                  caption="연결한 시정·예방 조치"
                  offset={0}
                  total={detail.capas?.length ?? 0}
                  limit={detail.capas?.length || 1}
                  onPage={() => undefined}
                  empty={
                    <p className="muted">
                      조치가 없습니다. 조치를 추가하고 유효성을 확인해야 종결할
                      수 있습니다.
                    </p>
                  }
                />
              </div>
            </DetailPanel>
          )}

          {panel?.kind === "form" && (
            <FormPanel
              key={`form-${panel.id ?? "new"}`}
              title={panel.id ? "부적합 보고 수정" : "부적합 보고"}
              guard={guard}
              onClose={() =>
                panel.id ? void openDetail(panel.id) : setPanel(null)
              }
              onSubmit={(e) => void submitNcr(e)}
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
                <>
                  <div className="field">
                    <label htmlFor="ncr-origin">발생처</label>
                    <select
                      id="ncr-origin"
                      value={draft.origin}
                      onChange={(e) =>
                        setDraft({
                          ...BLANK,
                          origin: e.target.value as NcrOrigin,
                        })
                      }
                    >
                      {ORIGINS.map((o) => (
                        <option key={o} value={o}>
                          {NCR_ORIGIN[o]}
                        </option>
                      ))}
                    </select>
                    <small>
                      고객 발생 부적합은 클레임 화면에서 만듭니다. 등록 뒤에는
                      발생처를 바꾸지 않습니다.
                    </small>
                  </div>
                  {draft.origin === "PROCESS" && (
                    <div className="field">
                      <label htmlFor="ncr-month">공정 불량 조회 달</label>
                      <input
                        id="ncr-month"
                        type="month"
                        value={month}
                        onChange={(e) => setMonth(e.target.value)}
                      />
                    </div>
                  )}
                  <div className="field">
                    <label htmlFor="ncr-source">
                      근거{draft.origin === "PROCESS" ? " (선택)" : ""}
                    </label>
                    <select
                      id="ncr-source"
                      value={sourceValue}
                      aria-invalid={!!errors.inspectionId}
                      onChange={(e) => pickSource(e.target.value)}
                    >
                      <option value="">선택</option>
                      {(sources?.rows ?? []).map((r) =>
                        isDefect(r) ? (
                          <option key={r.sourceRef} value={r.sourceRef}>
                            {r.lotNo} · {r.processCode} · 불량{" "}
                            {num(r.defectQty)} {r.unit}
                          </option>
                        ) : (
                          <option key={r.id} value={r.id}>
                            {r.inspectionNo} · {r.lotNo} · {r.itemCode}
                          </option>
                        ),
                      )}
                    </select>
                    {sources?.mesEnabled === false ? (
                      <small>
                        {
                          "MES를 사용하지 않아 공정 불량을 읽을 수 없습니다. 품목·LOT·수량을 직접 적으세요."
                        }
                      </small>
                    ) : (
                      sources?.rows.length === 0 && (
                        <small>
                          {draft.origin === "PROCESS"
                            ? "그 달에 보고하지 않은 공정 불량이 없습니다."
                            : "보고하지 않은 불합격 검사가 없습니다."}
                        </small>
                      )
                    )}
                    {errors.inspectionId && (
                      <small>{errors.inspectionId}</small>
                    )}
                    {errors.sourceRef && <small>{errors.sourceRef}</small>}
                  </div>
                  <div className="field">
                    <label htmlFor="ncr-item">품목 코드</label>
                    <input
                      id="ncr-item"
                      required
                      maxLength={40}
                      value={draft.itemCode}
                      aria-invalid={!!errors.itemCode}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          itemCode: e.target.value.toUpperCase(),
                        })
                      }
                    />
                    {errors.itemCode && <small>{errors.itemCode}</small>}
                  </div>
                </>
              )}
              <div className="field">
                <label htmlFor="ncr-lot">LOT (선택)</label>
                <input
                  id="ncr-lot"
                  maxLength={50}
                  value={draft.lotNo}
                  onChange={(e) =>
                    setDraft({ ...draft, lotNo: e.target.value })
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="ncr-qty">부적합 수량</label>
                <input
                  id="ncr-qty"
                  required
                  inputMode="decimal"
                  value={draft.qty}
                  aria-invalid={!!errors.qty}
                  onChange={(e) => setDraft({ ...draft, qty: e.target.value })}
                />
                {errors.qty && <small>{errors.qty}</small>}
              </div>
              <div className="field">
                <label htmlFor="ncr-defect">불량 유형 (선택)</label>
                <select
                  id="ncr-defect"
                  value={draft.defectTypeId}
                  onChange={(e) =>
                    setDraft({ ...draft, defectTypeId: e.target.value })
                  }
                >
                  <option value="">없음</option>
                  {defectTypes.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.code} {d.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="ncr-description">내용</label>
                <textarea
                  id="ncr-description"
                  required
                  minLength={2}
                  maxLength={1000}
                  rows={4}
                  value={draft.description}
                  aria-invalid={!!errors.description}
                  onChange={(e) =>
                    setDraft({ ...draft, description: e.target.value })
                  }
                />
                {errors.description && <small>{errors.description}</small>}
              </div>
              <div className="field">
                <label htmlFor="ncr-action">즉시 조치 (선택)</label>
                <textarea
                  id="ncr-action"
                  maxLength={500}
                  rows={3}
                  value={draft.immediateAction}
                  onChange={(e) =>
                    setDraft({ ...draft, immediateAction: e.target.value })
                  }
                />
              </div>
            </FormPanel>
          )}

          {panel?.kind === "capa" && detail && (
            <FormPanel
              key={`capa-${detail.id}`}
              title={`${detail.ncrNo} 조치 추가`}
              guard={guard}
              onClose={() => void openDetail(detail.id)}
              onSubmit={(e) => void submitCapa(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    만들기
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      guard.guard(() => void openDetail(detail.id))
                    }
                  >
                    보고 상세로
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <div className="field">
                <label htmlFor="capa-kind">종류</label>
                <select
                  id="capa-kind"
                  value={capa.kind}
                  onChange={(e) =>
                    setCapa({
                      ...capa,
                      kind: e.target.value as CapaDraft["kind"],
                    })
                  }
                >
                  {(Object.keys(CAPA_KIND) as CapaDraft["kind"][]).map((k) => (
                    <option key={k} value={k}>
                      {CAPA_KIND[k]}
                    </option>
                  ))}
                </select>
                <small>시정은 이미 난 문제를, 예방은 날 문제를 막습니다.</small>
              </div>
              <div className="field">
                <label htmlFor="capa-cause">근본 원인</label>
                <textarea
                  id="capa-cause"
                  required
                  minLength={2}
                  maxLength={1000}
                  rows={3}
                  value={capa.rootCause}
                  aria-invalid={!!errors.rootCause}
                  onChange={(e) =>
                    setCapa({ ...capa, rootCause: e.target.value })
                  }
                />
                {errors.rootCause && <small>{errors.rootCause}</small>}
              </div>
              <div className="field">
                <label htmlFor="capa-action">대책</label>
                <textarea
                  id="capa-action"
                  required
                  minLength={2}
                  maxLength={1000}
                  rows={3}
                  value={capa.action}
                  aria-invalid={!!errors.action}
                  onChange={(e) => setCapa({ ...capa, action: e.target.value })}
                />
                {errors.action && <small>{errors.action}</small>}
              </div>
              <div className="field">
                <label htmlFor="capa-owner">담당</label>
                <input
                  id="capa-owner"
                  required
                  maxLength={60}
                  value={capa.ownerName}
                  aria-invalid={!!errors.ownerName}
                  onChange={(e) =>
                    setCapa({ ...capa, ownerName: e.target.value })
                  }
                />
                {errors.ownerName && <small>{errors.ownerName}</small>}
              </div>
              <div className="field">
                <label htmlFor="capa-due">기한</label>
                <input
                  id="capa-due"
                  type="date"
                  required
                  value={capa.dueOn}
                  aria-invalid={!!errors.dueOn}
                  onChange={(e) => setCapa({ ...capa, dueOn: e.target.value })}
                />
                {errors.dueOn && <small>{errors.dueOn}</small>}
              </div>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
