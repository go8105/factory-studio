import { DocumentReaders } from "./Company";
import { Comments } from "./Collaboration";
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { GwLink as Link } from "./common";
import {
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
} from "../shared/components";
import { fieldErrors } from "../shared/hooks";
import {
  labels,
  useDocumentKinds,
  sourceKinds,
  time,
  useGet,
  useRole,
  useSend,
  type Document,
  type Page,
  type Route,
  type Snapshot,
} from "./common";
import { Events, NoRole, RoleBar, SnapshotView, Status } from "./ui";
export function Documents({ box }: { box: "drafts" | "pending" | "archive" }) {
  const role = useRole();
  return <DocumentsSpace key={role.person} box={box} />;
}
function DocumentsSpace({ box }: { box: "drafts" | "pending" | "archive" }) {
  const kinds = useDocumentKinds();
  const { person, busy } = useRole();
  const [q, setQ] = useSearchParams();
  const [create, setCreate] = useState(false);
  const search = q.get("search") ?? "";
  const offset = Math.max(0, Number(q.get("offset")) || 0);
  const chosen =
    box === "archive" ? (q.get("box") === "all" ? "all" : "archive") : box;
  const query = new URLSearchParams({
    box: chosen,
    search,
    offset: String(offset),
    limit: "20",
    ...(person ? { personId: person } : {}),
  });
  if (q.get("status")) query.set("status", q.get("status")!);
  if (q.get("kind")) query.set("kind", q.get("kind")!);
  const list = useGet<Page<Document>>(
    !person && box !== "archive" ? null : "/documents?" + query,
  );
  const open = q.get("open");
  const change = (k: string, v: string) => {
    const n = new URLSearchParams(q);
    if (v) n.set(k, v);
    else n.delete(k);
    if (k !== "offset") n.delete("offset");
    setQ(n);
  };
  const id = box === "drafts" ? "G-02" : box === "pending" ? "G-03" : "G-04";
  const title =
    box === "drafts" ? "기안함" : box === "pending" ? "결재함" : "결재 기록";
  return (
    <div className="page-fill">
      <PageTitle
        id={id}
        title={title}
        help={"gw/" + id.toLowerCase()}
        actions={
          box === "drafts" && (
            <button disabled={!person || busy} onClick={() => setCreate(true)}>
              새 기안
            </button>
          )
        }
      />
      <div className="split-view fill">
        <section className="fill" inert={!!busy}>
          {!create && !open && <RoleBar />}
          {!person && box !== "archive" ? (
            <NoRole />
          ) : (
            <>
              <div className="gw-filters">
                <Field
                  label="문서 검색"
                  value={search}
                  onChange={(e) => change("search", e.target.value)}
                />
                {box === "archive" && (
                  <label>
                    범위
                    <select
                      aria-label="범위"
                      value={chosen}
                      onChange={(e) => change("box", e.target.value)}
                    >
                      <option value="archive">종결 기록</option>
                      <option value="all">전체 기록</option>
                    </select>
                  </label>
                )}
                <label>
                  상태
                  <select
                    aria-label="상태"
                    value={q.get("status") ?? ""}
                    onChange={(e) => change("status", e.target.value)}
                  >
                    <option value="">전체 상태</option>
                    {[
                      "DRAFT",
                      "IN_REVIEW",
                      "APPROVED",
                      "REJECTED",
                      "WITHDRAWN",
                    ].map((s) => (
                      <option key={s} value={s}>
                        {labels[s]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  종류
                  <select
                    aria-label="종류"
                    value={q.get("kind") ?? ""}
                    onChange={(e) => change("kind", e.target.value)}
                  >
                    <option value="">전체 종류</option>
                    {kinds.map((k) => (
                      <option key={k} value={k}>
                        {labels[k]}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <ErrorNotice error={list.error} />
              {list.data ? (
                <DataTable
                  rows={list.data.rows}
                  columns={[
                    { key: "documentNo", label: "문서번호" },
                    {
                      key: "title",
                      label: "제목",
                      render: (d) => (
                        <button
                          className="link-button"
                          onClick={() => change("open", d.id)}
                        >
                          {d.title}
                        </button>
                      ),
                    },
                    {
                      key: "kind",
                      label: "종류",
                      render: (d) => labels[d.kind],
                    },
                    {
                      key: "status",
                      label: "상태",
                      render: (d) => <Status value={d.status} />,
                    },
                    { key: "drafterName", label: "기안자" },
                    { key: "currentStep", label: "현재 단계" },
                    {
                      key: "submittedAt",
                      label: "상신 시각",
                      render: (d) => time(d.submittedAt),
                    },
                  ]}
                  caption={title}
                  offset={offset}
                  limit={20}
                  total={list.data.total}
                  onPage={(n) => change("offset", String(n))}
                  empty={
                    <EmptyState
                      reason="표시할 문서가 없습니다. 담당자와 결재선을 등록한 뒤 기안을 만들어 보세요."
                      to="/gw/routes"
                      action="결재선 관리"
                    />
                  }
                />
              ) : (
                !list.error && <Loading />
              )}
            </>
          )}
        </section>
        {create && (
          <DocumentEditor
            close={() => setCreate(false)}
            done={(d) => {
              setCreate(false);
              change("open", d.id);
              list.reload();
            }}
          />
        )}
        {open && !create && (
          <DocumentDetail
            key={open + person}
            id={open}
            close={() => change("open", "")}
            changed={(d) => {
              change("open", d.id);
              list.reload();
            }}
          />
        )}
      </div>
    </div>
  );
}
function DocumentEditor({
  value,
  close,
  done,
}: {
  value?: Document;
  close: () => void;
  done: (d: Document) => void;
}) {
  const kinds = useDocumentKinds();
  const { person } = useRole();
  const [title, setTitle] = useState(value?.title ?? "");
  const [body, setBody] = useState(value?.body ?? "");
  const [kind, setKind] = useState(value?.kind ?? "GENERAL");
  const [routeId, setRoute] = useState(value?.routeId ?? "");
  const [amount, setAmount] = useState(value?.amount ?? "");
  const [currency, setCurrency] = useState(value?.currency ?? "KRW");
  const [sourceNo, setSource] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const routes = useGet<Page<Route>>("/routes?limit=100");
  const sources = useGet<
    { enabled: boolean; availability?: string; manualEntry?: boolean } & Page<
      Snapshot & { status: string }
    >
  >(
    kind !== "GENERAL" && !value
      ? "/sources?kind=" +
          sourceKinds[kind] +
          "&search=" +
          encodeURIComponent(search) +
          "&offset=" +
          page +
          "&limit=20"
      : null,
  );
  const preview = useGet<{ snapshot: Snapshot }>(
    sourceNo
      ? "/sources/" + sourceKinds[kind] + "/" + encodeURIComponent(sourceNo)
      : null,
  );
  const request = useSend();
  const errors = fieldErrors(request.error);
  const guard = useDiscardGuard(true);
  const selected = routes.data?.rows.find((r) => r.id === routeId);
  const self = selected?.steps.some(
    (s) => s.personId === person || !s.isActive,
  );
  async function submit(e: FormEvent) {
    e.preventDefault();
    const fields = {
      actingPersonId: person,
      title,
      body,
      ...(kind === "GENERAL"
        ? { amount: amount || null, currency: amount ? currency : null }
        : {}),
    };
    const payload = value
      ? { ...fields, expectedVersion: value.version }
      : {
          ...fields,
          routeId,
          kind,
          ...(kind !== "GENERAL" ? { sourceNo } : {}),
        };
    const d = await request.send<Document>(
      "/documents" + (value ? "/" + value.id : ""),
      value ? "PATCH" : "POST",
      payload,
    );
    if (d) done(d);
  }
  return (
    <FormPanel
      title={value ? "초안 편집" : "새 기안"}
      wide
      guard={guard}
      onClose={() => {
        if (!request.pending) close();
      }}
      onSubmit={(e) => void submit(e)}
      actions={
        <button
          disabled={
            request.pending ||
            (!value &&
              (!routeId ||
                !!self ||
                (kind !== "GENERAL" &&
                  (!sourceNo || !sources.data?.enabled || !preview.data))))
          }
        >
          초안 저장
        </button>
      }
    >
      <RoleBar guard={guard} pending={request.pending} />
      <fieldset disabled={request.pending}>
        <ErrorNotice error={request.error} />
        <ErrorNotice error={routes.error} />
        {!value && (
          <label>
            문서 종류
            <select
              aria-label="문서 종류"
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
                setSource("");
                setPage(0);
              }}
            >
              {kinds.map((k) => (
                <option key={k} value={k}>
                  {labels[k]}
                </option>
              ))}
            </select>
          </label>
        )}
        {kind !== "GENERAL" && !value && (
          <>
            <Field
              label="원문 검색"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
            />
            <ErrorNotice error={sources.error} />
            {sources.data?.manualEntry && (
              <Field
                label="PLM ECO 번호"
                required
                value={sourceNo}
                onChange={(e) => setSource(e.target.value)}
              />
            )}
            {sources.data && !sources.data.enabled ? (
              <p role="status">
                {sources.data.availability === "UNIMPLEMENTED"
                  ? "이 종류의 원문 제공 기능은 아직 구현되지 않았습니다. 제공 솔루션 구현 후 이용할 수 있습니다."
                  : "원문 솔루션이 꺼져 있거나 아직 열지 않아 조회할 수 없습니다."}
              </p>
            ) : (
              sources.data && (
                <DataTable
                  rows={sources.data.rows.map((s) => ({
                    ...s,
                    id: s.documentNo,
                  }))}
                  columns={[
                    { key: "documentNo", label: "번호" },
                    { key: "partnerName", label: "거래처" },
                    { key: "totalAmount", label: "합계" },
                    {
                      key: "status",
                      label: "상태",
                      render: (s) =>
                        s.status === "confirmed" ? "확정 · 사후 검토" : "초안",
                    },
                    {
                      key: "id",
                      label: "선택",
                      render: (s) => (
                        <button
                          type="button"
                          aria-pressed={sourceNo === s.documentNo}
                          onClick={() => setSource(s.documentNo)}
                        >
                          선택 {s.documentNo}
                        </button>
                      ),
                    },
                  ]}
                  caption="ERP 매입 후보"
                  offset={page}
                  limit={20}
                  total={sources.data.total}
                  onPage={setPage}
                />
              )
            )}
            <ErrorNotice error={preview.error} />
            {preview.data && <SnapshotView value={preview.data.snapshot} />}
            {kind === "ERP_PURCHASE" && (
              <p>
                확정 매입의 결재는 사후 검토이며 ERP 처리 상태를 바꾸지
                않습니다.
              </p>
            )}
          </>
        )}
        <Field
          label="제목"
          required
          maxLength={200}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          error={errors["body.title"] ?? errors.title}
        />
        <label>
          본문
          <textarea
            required
            maxLength={10000}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </label>
        {kind === "GENERAL" && (
          <div className="gw-filters">
            <Field
              label="금액 (선택)"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              error={errors.amount ?? errors["body.amount"]}
            />
            <Field
              label="통화"
              maxLength={3}
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
            />
          </div>
        )}
        {!value && (
          <>
            <label>
              결재선
              <select
                required
                aria-label="결재선"
                value={routeId}
                onChange={(e) => setRoute(e.target.value)}
              >
                <option value="">결재선 선택</option>
                {routes.data?.rows
                  .filter((r) => r.isActive)
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
              </select>
            </label>
            <ol>
              {selected?.steps.map((s) => (
                <li key={s.personId}>
                  {s.seq}단계 · {s.name} ·{" "}
                  {labels[s.participantRole ?? "APPROVER"]}
                </li>
              ))}
            </ol>
            {self && (
              <p role="alert">
                기안자를 포함하거나 비활성 담당자가 있는 결재선입니다.
              </p>
            )}
          </>
        )}
        <p className="muted">
          저장은 초안만 만듭니다. 상세에서 검토 후 상신하세요.
        </p>
      </fieldset>
    </FormPanel>
  );
}
function DocumentDetail({
  id,
  close,
  changed,
}: {
  id: string;
  close: () => void;
  changed: (d: Document) => void;
}) {
  const role = useRole();
  const { person } = role;
  const query = useGet<Document>(
    `/documents/${id}${person ? "?personId=" + person : ""}`,
  );
  const request = useSend();
  const [editing, setEditing] = useState(false);
  const [action, setAction] = useState("");
  const [reason, setReason] = useState("");
  const [route, setRoute] = useState("");
  const [stepId, setStepId] = useState("");
  const [commentDirty, setCommentDirty] = useState(false);
  const [readerDirty, setReaderDirty] = useState(false);
  const guard = useDiscardGuard(
    !!action || !!reason || commentDirty || readerDirty,
  );
  const routes = useGet<Page<Route>>(
    action === "select-route" ? "/routes?limit=100" : null,
  );
  const d = query.data;
  async function commit(e: FormEvent) {
    e.preventDefault();
    if (!d) return;
    const payload = {
      actingPersonId: person,
      expectedVersion: d.version,
      ...([
        "approve",
        "reject",
        "withdraw",
        "consent",
        "oppose",
        "reference",
      ].includes(action)
        ? { reason }
        : {}),
      ...(stepId ? { stepId } : {}),
      ...(action === "select-route" ? { routeId: route } : {}),
    };
    const saved = await request.send<Document>(
      `/documents/${id}/${action}`,
      "POST",
      payload,
    );
    if (saved) {
      query.setData(saved);
      setAction("");
      setReason("");
      changed(saved);
    }
  }
  if (editing && d)
    return (
      <DocumentEditor
        value={d}
        close={() => setEditing(false)}
        done={(saved) => {
          query.setData(saved);
          setEditing(false);
          changed(saved);
        }}
      />
    );
  return (
    <DetailPanel
      title={d?.documentNo ?? "결재 상세"}
      wide
      guard={guard}
      onClose={() => {
        if (!request.pending) close();
      }}
    >
      <RoleBar guard={guard} pending={request.pending} />
      <ErrorNotice error={query.error} />
      <ErrorNotice error={request.error} />
      <button
        disabled={request.pending}
        onClick={() =>
          guard.guard(() => {
            setAction("");
            setReason("");
            query.reload();
          })
        }
      >
        서버 상태 다시 확인
      </button>
      {!d && !query.error ? (
        <Loading />
      ) : (
        d && (
          <section className="gw-print-content">
            <h2>
              {d.title} <Status value={d.status} />
            </h2>
            <p>
              {d.documentNo} · {d.drafterName} · {d.roundNo}회차 · {d.routeName}
              {d.drafterOrgName && ` · 기안 조직: ${d.drafterOrgName}`}
            </p>
            <p className="muted">
              상신 당시 문서의 검토 기록이며 ERP 확정을 제어하지 않습니다.
            </p>
            <p>상신 시각: {time(d.submittedAt)}</p>
            <p className="gw-body">{d.body}</p>
            {d.amount && (
              <p>
                금액 {d.amount} {d.currency}
              </p>
            )}
            {d.sourceSnapshot && <SnapshotView value={d.sourceSnapshot} />}{" "}
            {d.sourceComparison && (
              <div className="gw-comparison" role="status">
                <strong>현재 원문 비교</strong>
                <p>
                  {d.sourceComparison.availability === "DISABLED"
                    ? "원문 솔루션 꺼짐 · 저장된 상신본은 열람·결재할 수 있습니다."
                    : d.sourceComparison.availability === "UNIMPLEMENTED"
                      ? "원문 제공 기능 미구현 · 현재 원문을 비교할 수 없습니다."
                      : d.sourceComparison.availability === "MISSING"
                        ? "원문 없음 · 저장된 상신본은 열람·결재할 수 있습니다."
                        : d.sourceComparison.contentChanged
                          ? `${d.status === "APPROVED" ? "과거 상신본 승인 · " : ""}원문 내용 변경 · 아래 고정된 상신본을 검토합니다.`
                          : "상신본 의미 값과 동일합니다."}
                </p>
                {d.sourceComparison.statusChanged && (
                  <p>
                    원문 상태 변경 ·{" "}
                    {d.sourceComparison.currentStatus === "cancelled"
                      ? "ERP 원문 취소"
                      : "ERP 확정"}{" "}
                    (결재와 별도)
                  </p>
                )}
              </div>
            )}
            <DataTable
              rows={d.steps}
              columns={[
                { key: "seq", label: "단계" },
                {
                  key: "personName",
                  label: "담당자",
                  render: (s) => (
                    <span>
                      {s.personName}
                      {s.originalPersonId &&
                        s.originalPersonId !== s.personId && (
                          <small> · 상신 담당: {s.originalPersonName}</small>
                        )}
                    </span>
                  ),
                },
                {
                  key: "organizationName",
                  label: "상신 조직",
                  render: (s) => s.organizationName ?? "미연결",
                },
                {
                  key: "participantRole",
                  label: "역할",
                  render: (s) => labels[s.participantRole ?? "APPROVER"],
                },
                {
                  key: "status",
                  label: "처리",
                  render: (s) => (
                    <>
                      {s.seq === d.currentStep ? "현재 · " : ""}
                      <Status value={s.status} />
                    </>
                  ),
                },
                { key: "decisionReason", label: "의견" },
                {
                  key: "decidedAt",
                  label: "처리 시각",
                  render: (s) => time(s.decidedAt),
                },
              ]}
              caption="결재 단계"
              offset={0}
              limit={30}
              total={d.steps.length}
              onPage={() => {}}
            />
            <div className="gw-actions">
              {d.availableActions.map((a) => (
                <button
                  disabled={request.pending}
                  key={a}
                  onClick={() => {
                    if (a === "edit") setEditing(true);
                    else {
                      setAction(a);
                      setStepId("");
                      setReason("");
                    }
                  }}
                >
                  {labels[a]}
                </button>
              ))}
            </div>
            {action && (
              <form onSubmit={(e) => void commit(e)}>
                <h3>{labels[action]} 확인</h3>
                <p>
                  {d.documentNo} · {d.title} · {d.drafterName} ·{" "}
                  {d.amount ?? "금액 없음"} {d.currency}
                </p>
                <p>
                  {action === "approve"
                    ? `${d.currentStep}단계를 승인합니다. 필수 결재·합의가 모두 끝나면 다음 단계로 넘어갑니다.`
                    : action === "submit"
                      ? "저장된 본문·원문·결재선을 검토한 뒤 상신합니다."
                      : action === "refresh-source"
                        ? "현재 ERP 원문으로 초안을 갱신합니다. 자동 상신되지 않습니다."
                        : "처리 후 기존 기록은 이력으로 보존됩니다."}
                </p>
                {[
                  "approve",
                  "reject",
                  "withdraw",
                  "consent",
                  "oppose",
                  "reference",
                ].includes(action) && (
                  <Field
                    label="처리 사유"
                    required={[
                      "reject",
                      "withdraw",
                      "oppose",
                      "reference",
                    ].includes(action)}
                    minLength={
                      ["reject", "withdraw", "oppose", "reference"].includes(
                        action,
                      )
                        ? 2
                        : undefined
                    }
                    maxLength={500}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                )}{" "}
                {action === "select-route" && (
                  <label>
                    새 결재선
                    <select
                      required
                      aria-label="새 결재선"
                      value={route}
                      onChange={(e) => setRoute(e.target.value)}
                    >
                      <option value="">선택</option>
                      {routes.data?.rows
                        .filter((r) => r.isActive)
                        .map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name}
                          </option>
                        ))}
                    </select>
                  </label>
                )}
                {[
                  "approve",
                  "reject",
                  "consent",
                  "oppose",
                  "reference",
                ].includes(action) &&
                  !!d.actionSteps?.length && (
                    <label>
                      처리할 참여자
                      <select
                        aria-label="처리할 참여자"
                        value={stepId}
                        required={
                          d.actionSteps.filter(
                            (s) =>
                              s.participantRole ===
                              (["approve", "reject"].includes(action)
                                ? "APPROVER"
                                : action === "reference"
                                  ? "REFERENCE"
                                  : "CONSENT"),
                          ).length > 1
                        }
                        onChange={(e) => setStepId(e.target.value)}
                      >
                        <option value="">자동 선택 (한 명인 경우)</option>
                        {d.actionSteps
                          .filter(
                            (s) =>
                              s.participantRole ===
                              (["approve", "reject"].includes(action)
                                ? "APPROVER"
                                : action === "reference"
                                  ? "REFERENCE"
                                  : "CONSENT"),
                          )
                          .map((s) => (
                            <option key={s.stepId} value={s.stepId}>
                              {s.personName} · {labels[s.participantRole]}
                              {s.delegationId ? " · 위임" : ""}
                            </option>
                          ))}
                      </select>
                    </label>
                  )}
                <button disabled={request.pending}>확정</button>{" "}
                <button
                  type="button"
                  disabled={request.pending}
                  onClick={() => {
                    setAction("");
                    setReason("");
                  }}
                >
                  취소
                </button>
              </form>
            )}
            <div className="gw-actions">
              {d.previousDocumentId && (
                <Link to={"/gw/documents?open=" + d.previousDocumentId}>
                  이전 회차
                </Link>
              )}
              {d.successor && (
                <Link to={"/gw/documents?open=" + d.successor.id}>
                  후속 {d.successor.documentNo}
                </Link>
              )}
            </div>
            <p>
              {role.companyId !== undefined ? (
                "회사 로그인 계정의 처리 기록 (전자서명 아님)"
              ) : (
                <>
                  결재 정책 v{d.policyVersion ?? 1} · 합성 담당자 체험 기록
                  (전자서명 아님)
                </>
              )}
            </p>
            {d.authoritySnapshot && (
              <p>
                상신 시 전결: {d.authoritySnapshot.code} · 최종{" "}
                {d.authoritySnapshot.finalSeq}단계 ·{" "}
                {d.authoritySnapshot.amountFrom} 이상 /{" "}
                {d.authoritySnapshot.amountTo ?? "상한 없음"} 미만{" "}
                {d.authoritySnapshot.currency}
              </p>
            )}
            <button className="gw-no-print" onClick={() => window.print()}>
              기록 인쇄 / PDF 저장
            </button>
            {role.companyId !== undefined &&
              d.drafterId === person &&
              d.status !== "DRAFT" && (
                <DocumentReaders
                  documentId={d.id}
                  version={d.version}
                  onDirty={setReaderDirty}
                  onChanged={query.reload}
                />
              )}
            <Events rows={d.events} />
            {d.status !== "DRAFT" && (
              <Comments kind="DOCUMENT" id={d.id} onDirty={setCommentDirty} />
            )}
          </section>
        )
      )}
    </DetailPanel>
  );
}
