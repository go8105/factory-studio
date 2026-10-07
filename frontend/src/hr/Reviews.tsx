// H-13 인사 평가 — 평가 기간을 열고, 목표 작성 → 제출 → 평가자 확정 (DSN-30 F31).
import { useEffect, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { ApiError, api } from "../shared/api";
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
  moduleOff,
  useApiLists,
  useApiSend,
} from "../shared/hooks";
import type { Employee } from "./Employees";

const BASE = "/api/v1/hr";
const LIMIT = 20;
type Cycle = { id: number; cycleYear: string; name: string; status: string };
type Review = {
  id: number;
  cycleId: number;
  cycleYear: string;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  goals: string;
  selfComment: string | null;
  reviewerCode: string;
  grade: string | null;
  reviewerComment: string | null;
  status: string;
  confirmedAt: string | null;
};
const STATE: Record<
  string,
  { label: string; tone: "normal" | "warning" | "issue" }
> = {
  draft: { label: "작성 중", tone: "warning" },
  submitted: { label: "제출", tone: "warning" },
  confirmed: { label: "확정", tone: "normal" },
};
const GRADES = ["S", "A", "B", "C", "D"];
const EMPTY = { employeeId: "", goals: "", reviewerCode: "" };

export function Reviews() {
  const { fail } = useSession();
  const [cycles, setCycles] = useState<Cycle[]>();
  const [cycleId, setCycleId] = useState("");
  const [rows, setRows] = useState<Review[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [creating, setCreating] = useState<"cycle" | "review">();
  const [draft, setDraft] = useState(EMPTY);
  const [cycleDraft, setCycleDraft] = useState({ cycleYear: "", name: "" });
  const [picked, setPicked] = useState<Review>();
  const [edit, setEdit] = useState({ goals: "", selfComment: "" });
  const [decision, setDecision] = useState({ grade: "A", reviewerComment: "" });
  const [done, setDone] = useState("");
  const {
    send,
    pending,
    error: saveError,
    deleteButtons,
  } = useApiSend(BASE, () => setReload((n) => n + 1));
  const lookups = useApiLists<[Employee[]]>(BASE, ["/employees?limit=200"]);
  const [employees = []] = lookups.data ?? [];
  const guard = useDiscardGuard(creating === "review" && draft.goals !== "");

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    api<Cycle[]>(`${BASE}/review-cycles?limit=50`, {
      signal: controller.signal,
    })
      .then((reply) => {
        setCycles(reply.data);
        setCycleId((current) => current || String(reply.data[0]?.id ?? ""));
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(error);
        if (error instanceof ApiError && [401, 410].includes(error.status))
          fail(error);
      });
    return () => controller.abort();
  }, [reload]);

  useEffect(() => {
    if (!cycleId) return setRows(undefined);
    const controller = new AbortController();
    api<Review[]>(
      `${BASE}/reviews?cycleId=${cycleId}&offset=${offset}&limit=${LIMIT}`,
      { signal: controller.signal },
    )
      .then((reply) => {
        setRows(reply.data);
        setTotal(reply.page?.total ?? 0);
        setPicked(
          (current) =>
            current && reply.data.find((row) => row.id === current.id),
        );
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(error);
      });
    return () => controller.abort();
  }, [cycleId, offset, reload]);

  const cycle = cycles?.find((item) => String(item.id) === cycleId);
  const open = cycle?.status === "OPEN";

  async function submitCycle(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const made = await send<Cycle>("/review-cycles", "POST", cycleDraft);
    if (made) {
      setCreating(undefined);
      setCycleDraft({ cycleYear: "", name: "" });
      setCycleId(String(made.id));
      setDone(`${made.cycleYear}년 평가 기간을 열었습니다.`);
    }
  }

  async function submitReview(event: FormEvent) {
    event.preventDefault();
    if (pending || !cycle) return;
    const made = await send("/reviews", "POST", {
      cycleId: cycle.id,
      employeeId: Number(draft.employeeId),
      goals: draft.goals,
      reviewerCode: draft.reviewerCode || null,
    });
    if (made) {
      setCreating(undefined);
      setDraft(EMPTY);
      setDone(
        "평가 대상을 추가했습니다. 평가자를 비우면 그 부서의 부서장이 됩니다.",
      );
    }
  }

  function openDetail(row: Review) {
    setDone("");
    setPicked(row);
    setEdit({ goals: row.goals, selfComment: row.selfComment ?? "" });
    setDecision({
      grade: row.grade ?? "A",
      reviewerComment: row.reviewerComment ?? "",
    });
  }

  async function saveSelf(event: FormEvent) {
    event.preventDefault();
    if (!picked || pending) return;
    const saved = await send(`/reviews/${picked.id}`, "PATCH", {
      goals: edit.goals,
      selfComment: edit.selfComment || null,
    });
    if (saved) setDone("자기 평가를 저장했습니다.");
  }

  async function submitSelf() {
    if (!picked) return;
    const ok = await send(`/reviews/${picked.id}/submit`, "POST");
    if (ok) setDone("제출했습니다. 이제 평가자가 등급을 매깁니다.");
  }

  async function confirm(event: FormEvent) {
    event.preventDefault();
    if (!picked || pending) return;
    const ok = await send(`/reviews/${picked.id}/confirm`, "POST", {
      reviewerCode: picked.reviewerCode,
      grade: decision.grade,
      reviewerComment: decision.reviewerComment || null,
    });
    if (ok)
      setDone(
        `${picked.employeeName} 평가를 확정했습니다. 이제 고칠 수 없습니다.`,
      );
  }

  async function closeCycle() {
    if (!cycle) return;
    const ok = await send(`/review-cycles/${cycle.id}/close`, "POST");
    if (ok) setDone(`${cycle.cycleYear}년 평가 기간을 닫았습니다.`);
  }

  if (moduleOff(loadError))
    return (
      <EmptyState
        reason="HR을 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const errors = fieldErrors(saveError);
  const columns: Column<Review>[] = [
    { key: "employeeCode", label: "사원 코드" },
    { key: "employeeName", label: "이름" },
    { key: "reviewerCode", label: "평가자" },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={STATE[r.status]?.tone ?? "normal"}>
          {STATE[r.status]?.label ?? r.status}
        </Badge>
      ),
    },
    { key: "grade", label: "등급", render: (r) => r.grade ?? "—" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button className="link-button" onClick={() => openDetail(r)}>
            열기
          </button>
          {open &&
            r.status !== "confirmed" &&
            deleteButtons(`review-${r.id}`, `/reviews/${r.id}`)}
        </span>
      ),
    },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="H-13"
        title="인사 평가"
        subtitle="목표 작성 → 제출 → 평가자 확정. 확정하면 바뀌지 않습니다"
        help="hr/h-13"
        actions={
          <>
            <button type="button" onClick={() => setCreating("cycle")}>
              평가 기간 열기
            </button>
            <button
              type="button"
              disabled={!open || !employees.length}
              onClick={() => guard.guard(() => setCreating("review"))}
            >
              평가 대상 추가
            </button>
          </>
        }
      />
      {done && <p role="status">{done}</p>}
      <ErrorNotice error={lookups.error} />
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <div className="filter-bar">
        <label htmlFor="review-cycle">평가 기간</label>
        <select
          id="review-cycle"
          value={cycleId}
          onChange={(event) => {
            setOffset(0);
            setPicked(undefined);
            setCycleId(event.target.value);
          }}
        >
          {(cycles ?? []).map((item) => (
            <option key={item.id} value={String(item.id)}>
              {item.cycleYear} {item.name}
            </option>
          ))}
        </select>
        {cycle && (
          <Badge tone={open ? "normal" : "issue"}>
            {open ? "진행 중" : "닫힘 — 더 고칠 수 없습니다"}
          </Badge>
        )}
        {open && (
          <button
            type="button"
            className="secondary"
            disabled={pending}
            onClick={() => void closeCycle()}
          >
            평가 기간 닫기
          </button>
        )}
      </div>
      <ErrorNotice error={loadError} retry={() => setReload((n) => n + 1)} />
      <div className="split-view fill">
        <section className="fill">
          {!cycles ? (
            !loadError && <Loading />
          ) : !cycles.length ? (
            <EmptyState
              reason="평가 기간이 없습니다. 연도별로 하나 열면 그 안에서 평가합니다."
              action="평가 기간 열기"
              onAction={() => setCreating("cycle")}
            />
          ) : !rows ? (
            <Loading />
          ) : (
            <DataTable
              rows={rows}
              columns={columns}
              caption={`${cycle?.cycleYear ?? ""}년 평가`}
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason="평가 대상이 없습니다. 사원을 추가하면 목표를 적을 수 있습니다."
                  action="평가 대상 추가"
                  onAction={() => open && setCreating("review")}
                />
              }
            />
          )}
        </section>
        {creating === "cycle" && (
          <FormPanel
            title="평가 기간 열기"
            guard={guard}
            onClose={() => setCreating(undefined)}
            onSubmit={(event) => void submitCycle(event)}
            actions={
              <>
                <button type="submit" disabled={pending} aria-busy={pending}>
                  열기
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setCreating(undefined)}
                >
                  취소
                </button>
              </>
            }
          >
            <ErrorNotice
              error={Object.keys(errors).length ? undefined : saveError}
            />
            <Field
              label="연도"
              type="number"
              min={2000}
              max={2100}
              value={cycleDraft.cycleYear}
              required
              error={errors.cycleYear}
              onChange={(event) =>
                setCycleDraft({ ...cycleDraft, cycleYear: event.target.value })
              }
            />
            <Field
              label="이름"
              value={cycleDraft.name}
              required
              maxLength={60}
              error={errors.name}
              onChange={(event) =>
                setCycleDraft({ ...cycleDraft, name: event.target.value })
              }
            />
          </FormPanel>
        )}
        {creating === "review" && (
          <FormPanel
            title="평가 대상 추가"
            guard={guard}
            onClose={() => setCreating(undefined)}
            onSubmit={(event) => void submitReview(event)}
            actions={
              <>
                <button type="submit" disabled={pending} aria-busy={pending}>
                  추가
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => guard.guard(() => setCreating(undefined))}
                >
                  취소
                </button>
              </>
            }
          >
            <ErrorNotice
              error={Object.keys(errors).length ? undefined : saveError}
            />
            <div className="field">
              <label htmlFor="review-employee">사원</label>
              <select
                id="review-employee"
                value={draft.employeeId}
                required
                onChange={(event) =>
                  setDraft({ ...draft, employeeId: event.target.value })
                }
              >
                <option value="">선택</option>
                {employees.map((employee) => (
                  <option key={employee.id} value={String(employee.id)}>
                    {employee.employeeCode} {employee.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="review-goals">목표</label>
              <textarea
                id="review-goals"
                value={draft.goals}
                required
                maxLength={2000}
                rows={4}
                onChange={(event) =>
                  setDraft({ ...draft, goals: event.target.value })
                }
              />
              {errors.goals && <small>{errors.goals}</small>}
            </div>
            <div className="field">
              <label htmlFor="review-reviewer">평가자 (선택)</label>
              <select
                id="review-reviewer"
                value={draft.reviewerCode}
                onChange={(event) =>
                  setDraft({ ...draft, reviewerCode: event.target.value })
                }
              >
                <option value="">그 부서의 부서장</option>
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.employeeCode}>
                    {employee.employeeCode} {employee.name}
                  </option>
                ))}
              </select>
              {errors.reviewerCode && <small>{errors.reviewerCode}</small>}
            </div>
          </FormPanel>
        )}
        {picked && (
          <DetailPanel
            wide
            title={`${picked.employeeName} ${picked.cycleYear}년 평가`}
            onClose={() => setPicked(undefined)}
          >
            <dl className="detail-grid">
              <dt>상태</dt>
              <dd>
                <Badge tone={STATE[picked.status]?.tone ?? "normal"}>
                  {STATE[picked.status]?.label ?? picked.status}
                </Badge>
              </dd>
              <dt>평가자</dt>
              <dd>{picked.reviewerCode}</dd>
              {picked.grade && (
                <>
                  <dt>등급</dt>
                  <dd>{picked.grade}</dd>
                  <dt>평가 의견</dt>
                  <dd>{picked.reviewerComment ?? "—"}</dd>
                </>
              )}
            </dl>
            {picked.status === "draft" && open ? (
              <form onSubmit={(event) => void saveSelf(event)}>
                <ErrorNotice
                  error={Object.keys(errors).length ? undefined : saveError}
                />
                <div className="field">
                  <label htmlFor="self-goals">목표</label>
                  <textarea
                    id="self-goals"
                    value={edit.goals}
                    required
                    maxLength={2000}
                    rows={4}
                    onChange={(event) =>
                      setEdit({ ...edit, goals: event.target.value })
                    }
                  />
                </div>
                <div className="field">
                  <label htmlFor="self-comment">자기 평가</label>
                  <textarea
                    id="self-comment"
                    value={edit.selfComment}
                    maxLength={2000}
                    rows={4}
                    onChange={(event) =>
                      setEdit({ ...edit, selfComment: event.target.value })
                    }
                  />
                </div>
                <div className="form-actions">
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    저장
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    disabled={pending}
                    onClick={() => void submitSelf()}
                  >
                    제출 (이후 본인은 못 고칩니다)
                  </button>
                </div>
              </form>
            ) : (
              <dl className="detail-grid">
                <dt>목표</dt>
                <dd>{picked.goals}</dd>
                <dt>자기 평가</dt>
                <dd>{picked.selfComment ?? "—"}</dd>
              </dl>
            )}
            {picked.status === "submitted" && open && (
              <form onSubmit={(event) => void confirm(event)}>
                <ErrorNotice
                  error={Object.keys(errors).length ? undefined : saveError}
                />
                <div className="field">
                  <label htmlFor="review-grade">등급</label>
                  <select
                    id="review-grade"
                    value={decision.grade}
                    onChange={(event) =>
                      setDecision({ ...decision, grade: event.target.value })
                    }
                  >
                    {GRADES.map((grade) => (
                      <option key={grade} value={grade}>
                        {grade}
                      </option>
                    ))}
                  </select>
                  <small>평가자 {picked.reviewerCode}로 확정합니다.</small>
                </div>
                <div className="field">
                  <label htmlFor="reviewer-comment">평가 의견</label>
                  <textarea
                    id="reviewer-comment"
                    value={decision.reviewerComment}
                    maxLength={2000}
                    rows={4}
                    onChange={(event) =>
                      setDecision({
                        ...decision,
                        reviewerComment: event.target.value,
                      })
                    }
                  />
                </div>
                <div className="form-actions">
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    확정
                  </button>
                </div>
              </form>
            )}
          </DetailPanel>
        )}
      </div>
    </div>
  );
}
