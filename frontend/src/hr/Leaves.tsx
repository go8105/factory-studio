// H-09 휴가 — 연차 발생을 등록하고, 신청을 부서장이 승인한다. 승인하면 그 날 근태가 휴가가 된다(DSN-30 F13).
import { useEffect, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { ApiError, api } from "../shared/api";
import {
  Badge,
  DataTable,
  DateRange,
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
type Title = {
  id: number;
  code: string;
  name: string;
  titleKind: string;
  isHead: boolean;
};
type Balance = {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  leaveYear: string;
  grantedDays: string;
  usedDays: string;
  remainingDays: string;
};
type Request = {
  id: number;
  requestNo: string;
  employeeId: number;
  leaveKind: string;
  fromDate: string;
  toDate: string;
  days: string;
  reason: string | null;
  status: string;
  approverCode: string | null;
  decidedAt: string | null;
};
const KIND: Record<string, string> = {
  ANNUAL: "연차",
  HALF_AM: "오전 반차",
  HALF_PM: "오후 반차",
  SICK: "병가",
  SPECIAL: "특별휴가",
  UNPAID: "무급휴가",
};
const STATE: Record<
  string,
  { label: string; tone: "normal" | "warning" | "issue" }
> = {
  REQUESTED: { label: "신청", tone: "warning" },
  APPROVED: { label: "승인", tone: "normal" },
  REJECTED: { label: "반려", tone: "issue" },
  CANCELLED: { label: "취소", tone: "issue" },
};
const DAYS: Record<string, string> = { HALF_AM: "0.5", HALF_PM: "0.5" };
const EMPTY = {
  employeeId: "",
  leaveKind: "ANNUAL",
  fromDate: "",
  toDate: "",
  days: "1",
  reason: "",
};
const thisYear = () => String(new Date().getFullYear());

export function Leaves() {
  const { fail } = useSession();
  const [year, setYear] = useState(thisYear());
  const [balances, setBalances] = useState<Balance[]>();
  const [requests, setRequests] = useState<Request[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [creating, setCreating] = useState<"request" | "balance">();
  const [draft, setDraft] = useState(EMPTY);
  const [grant, setGrant] = useState({ employeeId: "", grantedDays: "15" });
  const [approver, setApprover] = useState("");
  const [done, setDone] = useState("");
  const {
    send,
    pending,
    error: saveError,
  } = useApiSend(BASE, () => setReload((n) => n + 1));
  const lookups = useApiLists<[Employee[], Title[]]>(BASE, [
    "/employees?limit=200",
    "/titles?limit=200&titleKind=DUTY",
  ]);
  const [employees = [], duties = []] = lookups.data ?? [];
  const headDuties = new Set(duties.filter((d) => d.isHead).map((d) => d.id));
  const heads = employees.filter(
    (e) =>
      e.status === "ACTIVE" && e.dutyId !== null && headDuties.has(e.dutyId),
  );
  const dirty = creating === "request" && draft.fromDate !== "";
  const guard = useDiscardGuard(dirty);

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    Promise.all([
      api<Balance[]>(`${BASE}/leave-balances?year=${year}&limit=200`, {
        signal: controller.signal,
      }),
      api<Request[]>(`${BASE}/leave-requests?offset=${offset}&limit=${LIMIT}`, {
        signal: controller.signal,
      }),
    ])
      .then(([grants, list]) => {
        setBalances(grants.data);
        setRequests(list.data);
        setTotal(list.page?.total ?? 0);
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(error);
        if (error instanceof ApiError && [401, 410].includes(error.status))
          fail(error);
      });
    return () => controller.abort();
  }, [year, offset, reload]);

  async function submitRequest(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const made = await send<Request>("/leave-requests", "POST", {
      employeeId: Number(draft.employeeId),
      leaveKind: draft.leaveKind,
      fromDate: draft.fromDate,
      toDate: draft.toDate || draft.fromDate,
      days: draft.days,
      reason: draft.reason || null,
    });
    if (made) {
      setCreating(undefined);
      setDraft(EMPTY);
      setDone(
        `${made.requestNo} 휴가를 신청했습니다. 부서장이 승인해야 합니다.`,
      );
    }
  }

  async function submitGrant(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const made = await send("/leave-balances", "POST", {
      employeeId: Number(grant.employeeId),
      leaveYear: year,
      grantedDays: grant.grantedDays,
    });
    if (made) {
      setCreating(undefined);
      setGrant({ employeeId: "", grantedDays: "15" });
      setDone(`${year}년 연차 발생을 등록했습니다.`);
    }
  }

  async function decide(row: Request, action: "approve" | "reject") {
    setDone("");
    if (!approver) {
      setDone("승인할 부서장을 먼저 고르세요.");
      return;
    }
    const decided = await send<{ attendanceUpdated?: number }>(
      `/leave-requests/${row.id}/${action}`,
      "POST",
      { approverCode: approver },
    );
    if (decided)
      setDone(
        action === "approve"
          ? `${row.requestNo}을(를) 승인했습니다. 근태 ${decided.attendanceUpdated ?? 0}건이 휴가로 바뀌었습니다.`
          : `${row.requestNo}을(를) 반려했습니다.`,
      );
  }

  async function cancel(row: Request) {
    setDone("");
    const ok = await send(`/leave-requests/${row.id}/cancel`, "POST");
    if (ok) setDone(`${row.requestNo} 신청을 취소했습니다.`);
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
  const named = (id: number) => {
    const employee = employees.find((e) => e.id === id);
    return employee ? `${employee.employeeCode} ${employee.name}` : "—";
  };
  const balanceColumns: Column<Balance>[] = [
    { key: "employeeCode", label: "사원 코드" },
    { key: "employeeName", label: "이름" },
    { key: "grantedDays", label: "발생" },
    { key: "usedDays", label: "사용" },
    {
      key: "remainingDays",
      label: "잔여",
      render: (r) => (
        <Badge tone={Number(r.remainingDays) > 0 ? "normal" : "warning"}>
          {r.remainingDays}일
        </Badge>
      ),
    },
  ];
  const requestColumns: Column<Request>[] = [
    { key: "requestNo", label: "신청 번호" },
    { key: "employeeId", label: "사원", render: (r) => named(r.employeeId) },
    {
      key: "leaveKind",
      label: "종류",
      render: (r) => KIND[r.leaveKind] ?? r.leaveKind,
    },
    {
      key: "fromDate",
      label: "기간",
      render: (r) => <DateRange from={r.fromDate} to={r.toDate} />,
    },
    { key: "days", label: "일수" },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={STATE[r.status]?.tone ?? "normal"}>
          {STATE[r.status]?.label ?? r.status}
        </Badge>
      ),
    },
    {
      key: "approverCode",
      label: "결재자",
      render: (r) => r.approverCode ?? "—",
    },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        r.status === "REQUESTED" ? (
          <span className="row-actions">
            <button
              disabled={pending}
              onClick={() => void decide(r, "approve")}
            >
              승인
            </button>
            <button
              className="link-button"
              onClick={() => void decide(r, "reject")}
            >
              반려
            </button>
            <button className="link-button" onClick={() => void cancel(r)}>
              취소
            </button>
          </span>
        ) : (
          <span>—</span>
        ),
    },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="H-09"
        title="휴가"
        subtitle="부서장이 승인하면 그 날 근태가 휴가로 바뀝니다"
        help="hr/h-09"
        actions={
          <>
            <button
              type="button"
              disabled={!employees.length}
              onClick={() => guard.guard(() => setCreating("balance"))}
            >
              연차 발생 등록
            </button>
            <button
              type="button"
              disabled={!employees.length}
              onClick={() => guard.guard(() => setCreating("request"))}
            >
              휴가 신청
            </button>
          </>
        }
      />
      {done && <p role="status">{done}</p>}
      <ErrorNotice error={lookups.error} />
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <div className="filter-bar">
        <label htmlFor="leave-year">연도</label>
        <input
          id="leave-year"
          type="number"
          min={2000}
          max={2100}
          value={year}
          onChange={(event) => setYear(event.target.value)}
        />
        <label htmlFor="leave-approver">결재 부서장</label>
        <select
          id="leave-approver"
          value={approver}
          onChange={(event) => setApprover(event.target.value)}
        >
          <option value="">선택</option>
          {heads.map((head) => (
            <option key={head.id} value={head.employeeCode}>
              {head.employeeCode} {head.name}
            </option>
          ))}
        </select>
      </div>
      <ErrorNotice error={loadError} retry={() => setReload((n) => n + 1)} />
      <div className="split-view fill">
        <section className="fill">
          {!balances ? (
            !loadError && <Loading />
          ) : (
            <DataTable
              rows={balances}
              columns={balanceColumns}
              caption={`${year}년 연차 발생·잔여`}
              offset={0}
              total={balances.length}
              limit={balances.length || 1}
              onPage={() => {}}
              empty={
                <EmptyState
                  reason={`${year}년 연차 발생 기록이 없습니다. 등록해야 연차를 신청할 수 있습니다.`}
                  action="연차 발생 등록"
                  onAction={() => setCreating("balance")}
                />
              }
            />
          )}
          {requests && (
            <DataTable
              rows={requests}
              columns={requestColumns}
              caption="휴가 신청"
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason="휴가 신청이 없습니다."
                  action="휴가 신청"
                  onAction={() => setCreating("request")}
                />
              }
            />
          )}
        </section>
        {creating === "balance" && (
          <FormPanel
            title={`${year}년 연차 발생 등록`}
            guard={guard}
            onClose={() => setCreating(undefined)}
            onSubmit={(event) => void submitGrant(event)}
            actions={
              <>
                <button type="submit" disabled={pending} aria-busy={pending}>
                  등록
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
            <div className="field">
              <label htmlFor="grant-employee">사원</label>
              <select
                id="grant-employee"
                value={grant.employeeId}
                required
                onChange={(event) =>
                  setGrant({ ...grant, employeeId: event.target.value })
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
            <Field
              label="발생 일수"
              type="number"
              min={0}
              max={365}
              step={0.5}
              value={grant.grantedDays}
              required
              error={errors.grantedDays}
              onChange={(event) =>
                setGrant({ ...grant, grantedDays: event.target.value })
              }
            />
          </FormPanel>
        )}
        {creating === "request" && (
          <FormPanel
            title="휴가 신청"
            guard={guard}
            onClose={() => setCreating(undefined)}
            onSubmit={(event) => void submitRequest(event)}
            actions={
              <>
                <button type="submit" disabled={pending} aria-busy={pending}>
                  신청
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
              <label htmlFor="leave-employee">사원</label>
              <select
                id="leave-employee"
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
              <label htmlFor="leave-kind">휴가 종류</label>
              <select
                id="leave-kind"
                value={draft.leaveKind}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    leaveKind: event.target.value,
                    days: DAYS[event.target.value] ?? draft.days,
                  })
                }
              >
                {Object.entries(KIND).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <Field
              label="시작일"
              type="date"
              value={draft.fromDate}
              required
              error={errors.fromDate}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  fromDate: event.target.value,
                  toDate: draft.toDate || event.target.value,
                })
              }
            />
            <Field
              label="종료일"
              type="date"
              value={draft.toDate}
              min={draft.fromDate}
              error={errors.toDate}
              onChange={(event) =>
                setDraft({ ...draft, toDate: event.target.value })
              }
            />
            <Field
              label="일수"
              type="number"
              min={0.5}
              max={365}
              step={0.5}
              value={draft.days}
              required
              error={errors.days}
              onChange={(event) =>
                setDraft({ ...draft, days: event.target.value })
              }
            />
            <Field
              label="사유"
              value={draft.reason}
              maxLength={200}
              error={errors.reason}
              onChange={(event) =>
                setDraft({ ...draft, reason: event.target.value })
              }
            />
          </FormPanel>
        )}
      </div>
    </div>
  );
}
