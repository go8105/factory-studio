// Q-12 4M 변경 — 신고 → 승인·반려 → 초품 검사 합격 → 확인 완료 (DSN-14 F06).
// PLM ECO 가져오기는 PLM 솔루션이 아직 없어 넣지 않았다. 직접 신고로 전 과정이 돈다.
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
  CHANGE_TYPE,
  CN_STATUS,
  CnStatusBadge,
  fieldErrors,
  ModuleOff,
  moduleOff,
  QMS,
  ResultBadge,
  time,
  useSend,
  type ChangeNotice,
  type ChangeType,
  type CnStatus,
} from "./common";

type Draft = {
  changeType: ChangeType;
  itemCode: string;
  description: string;
  effectiveOn: string;
};
const BLANK: Draft = {
  changeType: "MATERIAL",
  itemCode: "",
  description: "",
  effectiveOn: "",
};
type Decide = { approve: boolean; note: string };
type FirstArticle = {
  lotNo: string;
  lotQty: string;
  unit: string;
  sampleQty: string;
};
const FA_BLANK: FirstArticle = {
  lotNo: "",
  lotQty: "",
  unit: "EA",
  sampleQty: "",
};
type Panel = {
  kind: "detail" | "form" | "decide" | "first-article";
  id: number | null;
};

export function ChangeNotices() {
  const { fail } = useSession();
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState<ChangeNotice[]>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [detail, setDetail] = useState<ChangeNotice>();
  const [draft, setDraft] = useState<Draft>(BLANK);
  const [initial, setInitial] = useState<Draft>(BLANK);
  const [decide, setDecide] = useState<Decide>({ approve: true, note: "" });
  const [article, setArticle] = useState<FirstArticle>(FA_BLANK);
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
      : panel?.kind === "first-article"
        ? JSON.stringify(article) !== JSON.stringify(FA_BLANK)
        : panel?.kind === "decide"
          ? decide.note !== ""
          : false;
  const guard = useDiscardGuard(dirty);

  useEffect(() => {
    const controller = new AbortController();
    api<ChangeNotice[]>(
      `${QMS}/change-notices${status ? `?status=${status}` : ""}`,
      { signal: controller.signal },
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
    const r = await api<ChangeNotice>(`${QMS}/change-notices/${id}`);
    setDetail(r.data);
    setPanel({ kind: "detail", id });
  }
  function openForm(row: ChangeNotice | null) {
    const values: Draft = row
      ? {
          changeType: row.changeType,
          itemCode: row.itemCode,
          description: row.description,
          effectiveOn: row.effectiveOn,
        }
      : BLANK;
    setDraft(values);
    setInitial(values);
    setSaveError(undefined);
    setPanel({ kind: "form", id: row?.id ?? null });
  }

  async function submitNotice(event: FormEvent) {
    event.preventDefault();
    const body = {
      changeType: draft.changeType,
      itemCode: draft.itemCode,
      description: draft.description,
      effectiveOn: draft.effectiveOn,
    };
    const saved = panel?.id
      ? await send<ChangeNotice>(`/change-notices/${panel.id}`, "PATCH", body)
      : await send<ChangeNotice>("/change-notices", "POST", body);
    if (saved) {
      setDone(`${saved.cnNo} 저장했습니다.`);
      await openDetail(saved.id);
    }
  }
  async function submitDecision(event: FormEvent) {
    event.preventDefault();
    if (!detail) return;
    const saved = await send<ChangeNotice>(
      `/change-notices/${detail.id}/decision`,
      "POST",
      { approve: decide.approve, note: decide.note.trim() || null },
    );
    if (saved) {
      setDone(`${saved.cnNo} ${CN_STATUS[saved.status]}`);
      await openDetail(detail.id);
    }
  }
  async function submitFirstArticle(event: FormEvent) {
    event.preventDefault();
    if (!detail) return;
    const saved = await send<{ inspectionNo: string }>(
      `/change-notices/${detail.id}/first-article`,
      "POST",
      article,
    );
    if (saved) {
      setDone(
        `초품 검사 ${saved.inspectionNo}을(를) 만들었습니다. 검사 화면에서 값을 적고 확정하세요.`,
      );
      await openDetail(detail.id);
    }
  }
  async function verify(inspectionId: number) {
    if (!detail) return;
    const saved = await send<ChangeNotice>(
      `/change-notices/${detail.id}/verification`,
      "POST",
      { firstArticleInspectionId: inspectionId },
    );
    if (saved) {
      setDone(`${saved.cnNo} 확인 완료`);
      await openDetail(detail.id);
    }
  }

  const passedArticles =
    detail?.firstArticles?.filter(
      (i) => i.status === "confirmed" && i.result === "PASS",
    ) ?? [];
  const columns: Column<ChangeNotice>[] = [
    { key: "cnNo", label: "신고 번호" },
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
    {
      key: "changeType",
      label: "구분",
      render: (r) => CHANGE_TYPE[r.changeType],
    },
    { key: "itemCode", label: "품목" },
    { key: "requestedOn", label: "신청일" },
    { key: "effectiveOn", label: "적용 예정" },
    {
      key: "status",
      label: "상태",
      render: (r) => <CnStatusBadge status={r.status} />,
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="Q-12"
        title="4M 변경"
        subtitle="사람·설비·자재·방법 변경을 신고하고 초품 검사로 확인합니다"
        help="qms/q-12"
      />
      <p className="muted" role="note">
        <strong>신고 → 승인 → 초품 검사 합격 → 확인 완료</strong> 순서로만
        닫힙니다. 승인·반려한 뒤에는 신고 내용을 고치지 않습니다. 초품 검사가
        불합격이면 승인 상태 그대로 두고 다시 검사합니다.
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
                  {(Object.keys(CN_STATUS) as CnStatus[]).map((s) => (
                    <option key={s} value={s}>
                      {CN_STATUS[s]}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={() => guard.guard(() => openForm(null))}
              >
                변경 신고
              </button>
            </div>
            <DataTable
              rows={rows}
              columns={columns}
              caption="4M 변경 신고 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="4M 변경 신고가 없습니다. 현장 변경이 생기면 신고하고 초품 검사로 확인합니다."
                  action="변경 신고"
                  onAction={() => guard.guard(() => openForm(null))}
                />
              }
            />
          </section>

          {panel?.kind === "detail" && detail && (
            <DetailPanel
              wide
              key={`detail-${detail.id}`}
              title={`${detail.cnNo} · ${CHANGE_TYPE[detail.changeType]} 변경`}
              onClose={() => setPanel(null)}
              actions={
                <>
                  {detail.status === "REQUESTED" && (
                    <>
                      <button type="button" onClick={() => openForm(detail)}>
                        수정
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setDecide({ approve: true, note: "" });
                          setSaveError(undefined);
                          setPanel({ kind: "decide", id: detail.id });
                        }}
                      >
                        승인·반려
                      </button>
                    </>
                  )}
                  {detail.status === "APPROVED" && (
                    <button
                      type="button"
                      onClick={() => {
                        setArticle(FA_BLANK);
                        setSaveError(undefined);
                        setPanel({ kind: "first-article", id: detail.id });
                      }}
                    >
                      초품 검사 만들기
                    </button>
                  )}
                </>
              }
            >
              <ErrorNotice error={saveError} />
              <p>
                <CnStatusBadge status={detail.status} /> {detail.itemCode} ·
                신청 {detail.requestedOn} · 적용 예정 {detail.effectiveOn}
                {detail.decidedAt && ` · 결정 ${time(detail.decidedAt)}`}
              </p>
              <p className="wrap">{detail.description}</p>
              {detail.decisionNote && (
                <p className="muted">결정 의견: {detail.decisionNote}</p>
              )}
              {detail.firstArticleNo && (
                <p>
                  확인 초품 검사: {detail.firstArticleNo}{" "}
                  <ResultBadge result={detail.firstArticleResult} />
                </p>
              )}
              <div className="section-block">
                <DataTable
                  rows={detail.firstArticles ?? []}
                  columns={[
                    { key: "inspectionNo", label: "초품 검사" },
                    { key: "lotNo", label: "LOT" },
                    {
                      key: "result",
                      label: "판정",
                      render: (i) => <ResultBadge result={i.result} />,
                    },
                    { key: "inspectedOn", label: "검사일" },
                    {
                      key: "id",
                      label: "확인",
                      render: (i) =>
                        detail.status === "APPROVED" &&
                        i.status === "confirmed" &&
                        i.result === "PASS" ? (
                          <button
                            type="button"
                            className="link-button"
                            disabled={pending}
                            onClick={() => void verify(i.id)}
                          >
                            확인 완료
                          </button>
                        ) : (
                          <span className="muted">—</span>
                        ),
                    },
                  ]}
                  caption="이 신고를 원천으로 만든 초품 검사"
                  offset={0}
                  total={detail.firstArticles?.length ?? 0}
                  limit={detail.firstArticles?.length || 1}
                  onPage={() => undefined}
                  empty={
                    <p className="muted">
                      초품 검사가 없습니다.{" "}
                      {detail.status === "APPROVED"
                        ? "초품 검사 만들기로 시작하세요."
                        : "승인한 뒤에 만들 수 있습니다."}
                    </p>
                  }
                />
              </div>
              {detail.status === "APPROVED" && passedArticles.length === 0 && (
                <p className="muted">
                  합격한 초품 검사가 없어 확인 완료할 수 없습니다. 초품 검사를
                  만든 뒤 <Link to="/qms/inspections">검사</Link>에서 값을 적고
                  확정하세요.
                </p>
              )}
            </DetailPanel>
          )}

          {panel?.kind === "form" && (
            <FormPanel
              key={`form-${panel.id ?? "new"}`}
              title={panel.id ? "변경 신고 수정" : "4M 변경 신고"}
              guard={guard}
              onClose={() =>
                panel.id ? void openDetail(panel.id) : setPanel(null)
              }
              onSubmit={(e) => void submitNotice(e)}
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
                <label htmlFor="cn-type">변경 구분</label>
                <select
                  id="cn-type"
                  value={draft.changeType}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      changeType: e.target.value as ChangeType,
                    })
                  }
                >
                  {(Object.keys(CHANGE_TYPE) as ChangeType[]).map((t) => (
                    <option key={t} value={t}>
                      {CHANGE_TYPE[t]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="cn-item">품목 코드</label>
                <input
                  id="cn-item"
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
                <small>
                  초품 검사는 이 품목의 게시한 검사 기준으로 만듭니다.
                </small>
                {errors.itemCode && <small>{errors.itemCode}</small>}
              </div>
              <div className="field">
                <label htmlFor="cn-effective">적용 예정일</label>
                <input
                  id="cn-effective"
                  type="date"
                  required
                  value={draft.effectiveOn}
                  aria-invalid={!!errors.effectiveOn}
                  onChange={(e) =>
                    setDraft({ ...draft, effectiveOn: e.target.value })
                  }
                />
                {errors.effectiveOn && <small>{errors.effectiveOn}</small>}
              </div>
              <div className="field">
                <label htmlFor="cn-description">변경 내용</label>
                <textarea
                  id="cn-description"
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
            </FormPanel>
          )}

          {panel?.kind === "decide" && detail && (
            <FormPanel
              key={`decide-${detail.id}`}
              title={`${detail.cnNo} 승인·반려`}
              guard={guard}
              onClose={() => void openDetail(detail.id)}
              onSubmit={(e) => void submitDecision(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    결정
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      guard.guard(() => void openDetail(detail.id))
                    }
                  >
                    신고 상세로
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <p className="muted">결정한 뒤에는 되돌릴 수 없습니다.</p>
              <fieldset className="field">
                <legend>결정</legend>
                {[true, false].map((approve) => (
                  <label key={String(approve)} className="inline-check">
                    <input
                      type="radio"
                      name="cn-decision"
                      checked={decide.approve === approve}
                      onChange={() => setDecide({ ...decide, approve })}
                    />
                    {approve ? "승인" : "반려"}
                  </label>
                ))}
              </fieldset>
              <div className="field">
                <label htmlFor="cn-note">
                  의견{decide.approve ? " (선택)" : ""}
                </label>
                <textarea
                  id="cn-note"
                  maxLength={500}
                  rows={3}
                  value={decide.note}
                  aria-invalid={!!errors.note}
                  onChange={(e) =>
                    setDecide({ ...decide, note: e.target.value })
                  }
                />
                {!decide.approve && <small>반려에는 의견이 필요합니다.</small>}
                {errors.note && <small>{errors.note}</small>}
              </div>
            </FormPanel>
          )}

          {panel?.kind === "first-article" && detail && (
            <FormPanel
              key={`fa-${detail.id}`}
              title={`${detail.cnNo} 초품 검사 만들기`}
              guard={guard}
              onClose={() => void openDetail(detail.id)}
              onSubmit={(e) => void submitFirstArticle(e)}
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
                    신고 상세로
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <p className="muted">
                {detail.itemCode}의 게시한 검사 기준으로 초안을 만듭니다. 값은{" "}
                <Link to="/qms/inspections">검사</Link> 화면에서 적고
                확정합니다.
              </p>
              <div className="field">
                <label htmlFor="fa-lot">초품 LOT·샘플 번호</label>
                <input
                  id="fa-lot"
                  required
                  maxLength={50}
                  value={article.lotNo}
                  aria-invalid={!!errors.lotNo}
                  onChange={(e) =>
                    setArticle({ ...article, lotNo: e.target.value })
                  }
                />
                {errors.lotNo && <small>{errors.lotNo}</small>}
              </div>
              <div className="field">
                <label htmlFor="fa-qty">초품 수량</label>
                <input
                  id="fa-qty"
                  required
                  inputMode="decimal"
                  value={article.lotQty}
                  aria-invalid={!!errors.lotQty}
                  onChange={(e) =>
                    setArticle({ ...article, lotQty: e.target.value })
                  }
                />
                {errors.lotQty && <small>{errors.lotQty}</small>}
              </div>
              <div className="field">
                <label htmlFor="fa-unit">단위</label>
                <input
                  id="fa-unit"
                  required
                  maxLength={10}
                  value={article.unit}
                  aria-invalid={!!errors.unit}
                  onChange={(e) =>
                    setArticle({ ...article, unit: e.target.value })
                  }
                />
                {errors.unit && <small>{errors.unit}</small>}
              </div>
              <div className="field">
                <label htmlFor="fa-sample">표본 수량</label>
                <input
                  id="fa-sample"
                  required
                  inputMode="decimal"
                  value={article.sampleQty}
                  aria-invalid={!!errors.sampleQty}
                  onChange={(e) =>
                    setArticle({ ...article, sampleQty: e.target.value })
                  }
                />
                {errors.sampleQty && <small>{errors.sampleQty}</small>}
              </div>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
