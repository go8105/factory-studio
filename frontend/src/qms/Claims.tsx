// Q-09 고객 클레임 — 접수 → 조사 → 회신 → 종결 + LOT 역추적 (DSN-14 F41~F43).
// 클레임은 QMS가 소유한다(Q4). 조사 시작이 곧 고객 발생 부적합 보고 생성이다.
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
  CLAIM_STATUS,
  ClaimBadge,
  fieldErrors,
  ModuleOff,
  moduleOff,
  NCR_ORIGIN,
  NcrBadge,
  num,
  QMS,
  SEVERITY,
  SeverityBadge,
  time,
  useSend,
  type Claim,
  type ClaimStatus,
  type Partner,
  type Severity,
} from "./common";

type Draft = {
  customerCode: string;
  itemCode: string;
  lotNo: string;
  qty: string;
  severity: Severity;
  description: string;
  returnRef: string;
};
const BLANK: Draft = {
  customerCode: "",
  itemCode: "",
  lotNo: "",
  qty: "",
  severity: "MAJOR",
  description: "",
  returnRef: "",
};
type Panel = {
  kind: "detail" | "form" | "investigate" | "respond";
  id: number | null;
};

export function Claims() {
  const { fail } = useSession();
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState<Claim[]>();
  const [customers, setCustomers] = useState<Partner[]>([]);
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [detail, setDetail] = useState<Claim>();
  const [draft, setDraft] = useState<Draft>(BLANK);
  const [initial, setInitial] = useState<Draft>(BLANK);
  const [finding, setFinding] = useState("");
  const [response, setResponse] = useState("");
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
      : panel?.kind === "investigate"
        ? finding !== ""
        : panel?.kind === "respond"
          ? response !== ""
          : false;
  const guard = useDiscardGuard(dirty);

  useEffect(() => {
    const controller = new AbortController();
    api<Claim[]>(`${QMS}/claims${status ? `?status=${status}` : ""}`, {
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
    api<Partner[]>(`${QMS}/claims/customers`)
      .then((r) => setCustomers(r.data))
      .catch(() => setCustomers([]));
  }, []);

  if (moduleOff(error)) return <ModuleOff />;
  const errors = fieldErrors(saveError);

  async function openDetail(id: number) {
    setSaveError(undefined);
    const r = await api<Claim>(`${QMS}/claims/${id}`);
    setDetail(r.data);
    setPanel({ kind: "detail", id });
  }
  function openForm(row: Claim | null) {
    const values: Draft = row
      ? {
          customerCode: row.customerCode,
          itemCode: row.itemCode,
          lotNo: row.lotNo ?? "",
          qty: row.qty,
          severity: row.severity,
          description: row.description,
          returnRef: row.returnRef ?? "",
        }
      : BLANK;
    setDraft(values);
    setInitial(values);
    setSaveError(undefined);
    setPanel({ kind: "form", id: row?.id ?? null });
  }

  async function submitClaim(event: FormEvent) {
    event.preventDefault();
    const common = {
      lotNo: draft.lotNo.trim() || null,
      qty: draft.qty,
      severity: draft.severity,
      description: draft.description,
      returnRef: draft.returnRef.trim() || null,
    };
    const saved = panel?.id
      ? await send<Claim>(`/claims/${panel.id}`, "PATCH", common)
      : await send<Claim>("/claims", "POST", {
          ...common,
          customerCode: draft.customerCode,
          itemCode: draft.itemCode,
        });
    if (saved) {
      setDone(`${saved.claimNo} 저장했습니다.`);
      await openDetail(saved.id);
    }
  }
  async function submitInvestigation(event: FormEvent) {
    event.preventDefault();
    if (!detail) return;
    const saved = await send<Claim>(
      `/claims/${detail.id}/investigation`,
      "POST",
      { description: finding },
    );
    if (saved) {
      setDone(
        `${saved.claimNo} 조사 시작 · 고객 발생 부적합 보고를 만들었습니다.`,
      );
      await openDetail(detail.id);
    }
  }
  async function submitResponse(event: FormEvent) {
    event.preventDefault();
    if (!detail) return;
    const saved = await send<Claim>(`/claims/${detail.id}/response`, "POST", {
      response,
    });
    if (saved) {
      setDone(`${saved.claimNo} 회신`);
      await openDetail(detail.id);
    }
  }
  async function close() {
    if (!detail) return;
    const saved = await send<Claim>(`/claims/${detail.id}/closure`, "POST");
    if (saved) {
      setDone(`${saved.claimNo} 종결`);
      await openDetail(detail.id);
    }
  }

  const columns: Column<Claim>[] = [
    { key: "claimNo", label: "클레임" },
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
    { key: "customerCode", label: "고객" },
    { key: "itemCode", label: "품목" },
    { key: "lotNo", label: "LOT", render: (r) => r.lotNo ?? "—" },
    { key: "qty", label: "수량", render: (r) => num(r.qty) },
    {
      key: "severity",
      label: "심각도",
      render: (r) => <SeverityBadge severity={r.severity} />,
    },
    { key: "receivedOn", label: "접수일" },
    {
      key: "status",
      label: "상태",
      render: (r) => <ClaimBadge status={r.status} />,
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="Q-09"
        title="고객 클레임"
        subtitle="고객 불만을 접수해 조사·회신하고 LOT을 거슬러 봅니다"
        help="qms/q-09"
      />
      <p className="muted" role="note">
        <strong>
          조사를 시작하면 고객 발생 부적합 보고가 함께 만들어집니다.
        </strong>{" "}
        확인 없이 회신하지 않도록 조사 → 회신 순서로만 갑니다. 연결한 부적합이
        모두 종결되어야 클레임이 닫힙니다.
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
                  {(Object.keys(CLAIM_STATUS) as ClaimStatus[]).map((s) => (
                    <option key={s} value={s}>
                      {CLAIM_STATUS[s]}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={() => guard.guard(() => openForm(null))}
              >
                클레임 접수
              </button>
            </div>
            <DataTable
              rows={rows}
              columns={columns}
              caption="고객 클레임 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="클레임이 없습니다. 고객 불만이 들어오면 접수합니다."
                  action="클레임 접수"
                  onAction={() => guard.guard(() => openForm(null))}
                />
              }
            />
          </section>

          {panel?.kind === "detail" && detail && (
            <DetailPanel
              wide
              key={`detail-${detail.id}`}
              title={`${detail.claimNo} · ${detail.customerCode}`}
              onClose={() => setPanel(null)}
              actions={
                <>
                  {detail.status === "RECEIVED" && (
                    <>
                      <button type="button" onClick={() => openForm(detail)}>
                        수정
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setFinding("");
                          setSaveError(undefined);
                          setPanel({ kind: "investigate", id: detail.id });
                        }}
                      >
                        조사 시작
                      </button>
                    </>
                  )}
                  {detail.status === "INVESTIGATING" && (
                    <button
                      type="button"
                      onClick={() => {
                        setResponse("");
                        setSaveError(undefined);
                        setPanel({ kind: "respond", id: detail.id });
                      }}
                    >
                      회신
                    </button>
                  )}
                  {detail.status === "RESPONDED" && (
                    <button
                      type="button"
                      className="secondary"
                      disabled={pending}
                      onClick={() => void close()}
                    >
                      종결
                    </button>
                  )}
                </>
              }
            >
              <ErrorNotice error={saveError} />
              <p>
                <ClaimBadge status={detail.status} />{" "}
                <SeverityBadge severity={detail.severity} /> {detail.itemCode} ·{" "}
                {detail.lotNo ?? "LOT 없음"} · {num(detail.qty)} · 접수{" "}
                {detail.receivedOn}
                {detail.closedAt && ` · 종결 ${time(detail.closedAt)}`}
              </p>
              <p className="wrap">{detail.description}</p>
              {detail.returnRef && (
                <p className="muted">판매 반품 번호: {detail.returnRef}</p>
              )}
              {detail.response && (
                <>
                  <h3>회신 ({detail.respondedOn})</h3>
                  <p className="wrap">{detail.response}</p>
                </>
              )}
              <div className="section-block">
                <DataTable
                  rows={detail.ncrs ?? []}
                  columns={[
                    { key: "ncrNo", label: "부적합" },
                    {
                      key: "origin",
                      label: "발생처",
                      render: (n) => NCR_ORIGIN[n.origin],
                    },
                    { key: "qty", label: "수량", render: (n) => num(n.qty) },
                    {
                      key: "capaCount",
                      label: "조치",
                      render: (n) =>
                        n.capaCount === 0
                          ? "없음"
                          : `${n.verifiedCount}/${n.capaCount} 확인`,
                    },
                    {
                      key: "status",
                      label: "상태",
                      render: (n) => <NcrBadge status={n.status} />,
                    },
                  ]}
                  caption="이 클레임에서 만든 부적합 보고"
                  offset={0}
                  total={detail.ncrs?.length ?? 0}
                  limit={detail.ncrs?.length || 1}
                  onPage={() => undefined}
                  empty={
                    <p className="muted">
                      아직 조사를 시작하지 않았습니다. 조사를 시작하면 부적합
                      보고가 만들어집니다.
                    </p>
                  }
                />
                {(detail.ncrs?.length ?? 0) > 0 && (
                  <p className="muted">
                    조치는 <Link to="/qms/ncrs">부적합 보고</Link>에서 답니다.
                  </p>
                )}
              </div>
              <div className="section-block">
                <h3>LOT 역추적</h3>
                {!detail.lotNo ? (
                  <p className="muted">
                    LOT을 적지 않은 클레임입니다. 거슬러 볼 대상이 없습니다.
                  </p>
                ) : detail.mesEnabled === false ? (
                  <p className="muted">
                    MES를 사용하지 않아 LOT 계보를 읽을 수 없습니다.
                  </p>
                ) : !detail.trace ? (
                  <p className="muted">
                    MES에 {detail.lotNo} LOT이 없습니다. 직접 적은 LOT이거나
                    다른 공장의 번호입니다.
                  </p>
                ) : (
                  <>
                    <p>
                      {detail.trace.itemCode} {detail.trace.itemName} · 작업지시{" "}
                      {detail.trace.orderNo}
                    </p>
                    <div className="table-scroll">
                      <table>
                        <caption>이 LOT에 들어간 자재</caption>
                        <thead>
                          <tr>
                            <th scope="col">투입 자재</th>
                            <th scope="col">자재 LOT</th>
                            <th scope="col">공정</th>
                            <th scope="col" className="num">
                              수량
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {detail.trace.materials.map((m, index) => (
                            <tr key={`${m.itemCode}-${m.processCode}-${index}`}>
                              <td>
                                {m.itemCode} {m.itemName}
                              </td>
                              <td>{m.lotNo ?? "—"}</td>
                              <td>{m.processCode}</td>
                              <td className="num">
                                {num(m.qty)} {m.unit}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {detail.trace.materials.length === 0 && (
                      <p className="muted">투입 자재 기록이 없습니다.</p>
                    )}
                  </>
                )}
              </div>
            </DetailPanel>
          )}

          {panel?.kind === "form" && (
            <FormPanel
              key={`form-${panel.id ?? "new"}`}
              title={panel.id ? "클레임 수정" : "클레임 접수"}
              guard={guard}
              onClose={() =>
                panel.id ? void openDetail(panel.id) : setPanel(null)
              }
              onSubmit={(e) => void submitClaim(e)}
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
                    <label htmlFor="claim-customer">고객</label>
                    {customers.length ? (
                      <select
                        id="claim-customer"
                        required
                        value={draft.customerCode}
                        aria-invalid={!!errors.customerCode}
                        onChange={(e) =>
                          setDraft({ ...draft, customerCode: e.target.value })
                        }
                      >
                        <option value="">선택</option>
                        {customers.map((p) => (
                          <option key={p.partnerCode} value={p.partnerCode}>
                            {p.partnerCode} {p.partnerName}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <>
                        <input
                          id="claim-customer"
                          required
                          maxLength={40}
                          value={draft.customerCode}
                          aria-invalid={!!errors.customerCode}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              customerCode: e.target.value.toUpperCase(),
                            })
                          }
                        />
                        <small>
                          ERP를 사용하지 않아 고객 코드를 직접 적습니다.
                        </small>
                      </>
                    )}
                    {errors.customerCode && (
                      <small>{errors.customerCode}</small>
                    )}
                  </div>
                  <div className="field">
                    <label htmlFor="claim-item">품목 코드</label>
                    <input
                      id="claim-item"
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
                <label htmlFor="claim-lot">LOT (선택)</label>
                <input
                  id="claim-lot"
                  maxLength={50}
                  value={draft.lotNo}
                  onChange={(e) =>
                    setDraft({ ...draft, lotNo: e.target.value })
                  }
                />
                <small>LOT을 적으면 자재·공정을 거슬러 볼 수 있습니다.</small>
              </div>
              <div className="field">
                <label htmlFor="claim-qty">수량</label>
                <input
                  id="claim-qty"
                  required
                  inputMode="decimal"
                  value={draft.qty}
                  aria-invalid={!!errors.qty}
                  onChange={(e) => setDraft({ ...draft, qty: e.target.value })}
                />
                {errors.qty && <small>{errors.qty}</small>}
              </div>
              <div className="field">
                <label htmlFor="claim-severity">심각도</label>
                <select
                  id="claim-severity"
                  value={draft.severity}
                  onChange={(e) =>
                    setDraft({ ...draft, severity: e.target.value as Severity })
                  }
                >
                  {(Object.keys(SEVERITY) as Severity[]).map((s) => (
                    <option key={s} value={s}>
                      {SEVERITY[s]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="claim-description">내용</label>
                <textarea
                  id="claim-description"
                  required
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
                <label htmlFor="claim-return">판매 반품 번호 (선택)</label>
                <input
                  id="claim-return"
                  maxLength={40}
                  value={draft.returnRef}
                  onChange={(e) =>
                    setDraft({ ...draft, returnRef: e.target.value })
                  }
                />
                <small>
                  ERP 반품 조회는 아직 없습니다. 번호를 알면 적어 둡니다.
                </small>
              </div>
            </FormPanel>
          )}

          {panel?.kind === "investigate" && detail && (
            <FormPanel
              key={`inv-${detail.id}`}
              title={`${detail.claimNo} 조사 시작`}
              guard={guard}
              onClose={() => void openDetail(detail.id)}
              onSubmit={(e) => void submitInvestigation(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    조사 시작
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      guard.guard(() => void openDetail(detail.id))
                    }
                  >
                    클레임 상세로
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <p className="muted">
                <strong>고객 발생 부적합 보고가 함께 만들어집니다.</strong>{" "}
                품목·LOT·수량은 클레임에서 가져갑니다. 조치는 부적합 보고에서
                답니다.
              </p>
              <div className="field">
                <label htmlFor="inv-finding">확인한 내용</label>
                <textarea
                  id="inv-finding"
                  required
                  minLength={2}
                  maxLength={1000}
                  rows={4}
                  value={finding}
                  aria-invalid={!!errors.description}
                  onChange={(e) => setFinding(e.target.value)}
                />
                <small>
                  고객이 말한 것이 아니라 우리가 확인한 것을 적습니다.
                </small>
                {errors.description && <small>{errors.description}</small>}
              </div>
            </FormPanel>
          )}

          {panel?.kind === "respond" && detail && (
            <FormPanel
              key={`res-${detail.id}`}
              title={`${detail.claimNo} 회신`}
              guard={guard}
              onClose={() => void openDetail(detail.id)}
              onSubmit={(e) => void submitResponse(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    회신
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      guard.guard(() => void openDetail(detail.id))
                    }
                  >
                    클레임 상세로
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <p className="muted">
                회신한 뒤에는 클레임 내용을 고치지 않습니다. 기록으로 남습니다.
              </p>
              <div className="field">
                <label htmlFor="res-text">회신 내용</label>
                <textarea
                  id="res-text"
                  required
                  minLength={2}
                  maxLength={1000}
                  rows={4}
                  value={response}
                  aria-invalid={!!errors.response}
                  onChange={(e) => setResponse(e.target.value)}
                />
                {errors.response && <small>{errors.response}</small>}
              </div>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
