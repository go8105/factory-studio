// H-07 근태 — 근무 형태와 휴일 달력으로 한 달치를 만들고, 예외만 고친다(DSN-30 F12).
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../shared/api";
import {
  Badge,
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  fieldErrors,
  moduleOff,
  useApiLists,
  useApiSend,
} from "../shared/hooks";
import { useSession } from "../app/session";
import type { Employee } from "./Employees";

const BASE = "/api/v1/hr";
const LIMIT = 100;
export const DAY_KIND: Record<string, string> = {
  WORKDAY: "근무일",
  OFFDAY: "휴무일",
  HOLIDAY: "휴일",
};
export const STATUS: Record<string, string> = {
  NORMAL: "정상",
  LATE: "지각",
  EARLY: "조퇴",
  ABSENT: "결근",
  LEAVE: "휴가",
  HALF_LEAVE: "반차",
  OFF: "쉼",
};
const EDITABLE = ["NORMAL", "LATE", "EARLY", "ABSENT", "OFF"];
export type Attendance = {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  workDate: string;
  dayKind: string;
  status: string;
  clockIn: string | null;
  clockOut: string | null;
  overtimeMinutes: number;
  nightMinutes: number;
  holidayMinutes: number;
  source: string;
  note: string | null;
};
/** 오늘이 속한 달. 서버의 FS_TODAY와 달라도 조회 기준일 뿐이라 문제가 없다. */
export const thisMonth = () => new Date().toISOString().slice(0, 7);

export function Attendance() {
  const { fail } = useSession();
  const [month, setMonth] = useState(thisMonth());
  const [employeeId, setEmployeeId] = useState("");
  const [rows, setRows] = useState<Attendance[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [closed, setClosed] = useState(false);
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [picked, setPicked] = useState<Attendance>();
  const [edit, setEdit] = useState({
    status: "",
    overtimeMinutes: "",
    note: "",
  });
  const [done, setDone] = useState("");
  const {
    send,
    pending,
    error: saveError,
  } = useApiSend(BASE, () => setReload((n) => n + 1));
  const lookups = useApiLists<[Employee[]]>(BASE, ["/employees?limit=200"]);
  const [employees = []] = lookups.data ?? [];

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    api<Attendance[]>(
      `${BASE}/attendance?month=${month}&offset=${offset}&limit=${LIMIT}` +
        (employeeId ? `&employeeId=${employeeId}` : ""),
      { signal: controller.signal },
    )
      .then((reply) => {
        setRows(reply.data);
        setTotal(reply.page?.total ?? 0);
        setClosed(Boolean((reply as { closed?: boolean }).closed));
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(error);
        if (error instanceof ApiError && [401, 410].includes(error.status))
          fail(error);
      });
    return () => controller.abort();
  }, [month, employeeId, offset, reload]);

  async function generate() {
    setDone("");
    const made = await send<{ created: number; employees: number }>(
      "/attendance/generate",
      "POST",
      { month },
    );
    if (made)
      setDone(
        made.created
          ? `${month} 근태 ${made.created}건을 만들었습니다(사원 ${made.employees}명).`
          : "새로 만들 근태가 없습니다. 이미 모두 있습니다.",
      );
  }

  function open(row: Attendance) {
    setDone("");
    setPicked(row);
    setEdit({
      status: row.status,
      overtimeMinutes: String(row.overtimeMinutes),
      note: row.note ?? "",
    });
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!picked || pending) return;
    const saved = await send<Attendance>(`/attendance/${picked.id}`, "PATCH", {
      status: edit.status,
      overtimeMinutes: Number(edit.overtimeMinutes || 0),
      note: edit.note || null,
    });
    if (saved) {
      setPicked(undefined);
      setDone(`${picked.employeeName} ${picked.workDate} 근태를 고쳤습니다.`);
    }
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
  const minutes = (value: number) => (value ? `${value}분` : "—");
  const columns: Column<Attendance>[] = [
    { key: "workDate", label: "일자" },
    { key: "employeeCode", label: "사원 코드" },
    { key: "employeeName", label: "이름" },
    {
      key: "dayKind",
      label: "날",
      render: (r) => DAY_KIND[r.dayKind] ?? r.dayKind,
    },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge
          tone={
            ["ABSENT", "LATE", "EARLY"].includes(r.status)
              ? "warning"
              : "normal"
          }
        >
          {STATUS[r.status] ?? r.status}
        </Badge>
      ),
    },
    {
      key: "overtimeMinutes",
      label: "연장",
      render: (r) => minutes(r.overtimeMinutes),
    },
    {
      key: "nightMinutes",
      label: "야간",
      render: (r) => minutes(r.nightMinutes),
    },
    {
      key: "source",
      label: "출처",
      render: (r) => (r.source === "MANUAL" ? "직접 고침" : "자동"),
    },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        closed ? (
          <span>—</span>
        ) : (
          <button className="link-button" onClick={() => open(r)}>
            고치기
          </button>
        ),
    },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="H-07"
        title="근태"
        subtitle="한 달치를 자동으로 만들고 예외만 고칩니다"
        help="hr/h-07"
        actions={
          <button
            type="button"
            disabled={pending || closed}
            onClick={() => void generate()}
          >
            {month} 근태 만들기
          </button>
        }
      />
      {done && <p role="status">{done}</p>}
      <ErrorNotice error={lookups.error} />
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <div className="split-view fill">
        <section className="fill">
          <div className="filter-bar">
            <label htmlFor="attendance-month">조회 월</label>
            <input
              id="attendance-month"
              type="month"
              value={month}
              onChange={(event) => {
                setOffset(0);
                setPicked(undefined);
                setMonth(event.target.value);
              }}
            />
            <label htmlFor="attendance-employee">사원</label>
            <select
              id="attendance-employee"
              value={employeeId}
              onChange={(event) => {
                setOffset(0);
                setEmployeeId(event.target.value);
              }}
            >
              <option value="">전체</option>
              {employees.map((employee) => (
                <option key={employee.id} value={String(employee.id)}>
                  {employee.employeeCode} {employee.name}
                </option>
              ))}
            </select>
            {closed && <Badge tone="issue">마감됨 — 고칠 수 없습니다</Badge>}
          </div>
          <ErrorNotice
            error={loadError}
            retry={() => setReload((n) => n + 1)}
          />
          {!rows ? (
            !loadError && <Loading />
          ) : (
            <DataTable
              rows={rows}
              columns={columns}
              caption={`${month} 근태`}
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason={`${month} 근태가 없습니다. 근태를 만들면 사원별로 한 달치가 채워집니다.`}
                  action={`${month} 근태 만들기`}
                  onAction={() => void generate()}
                />
              }
            />
          )}
        </section>
        {picked && (
          <DetailPanel
            title={`${picked.employeeName} ${picked.workDate}`}
            onClose={() => setPicked(undefined)}
          >
            <form onSubmit={(event) => void save(event)}>
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <div className="field">
                <label htmlFor="attendance-status">상태</label>
                <select
                  id="attendance-status"
                  value={edit.status}
                  onChange={(event) =>
                    setEdit({ ...edit, status: event.target.value })
                  }
                >
                  {EDITABLE.map((status) => (
                    <option key={status} value={status}>
                      {STATUS[status]}
                    </option>
                  ))}
                </select>
                <small>휴가는 휴가 신청을 승인하면 자동으로 바뀝니다.</small>
              </div>
              <Field
                label="연장 근무(분)"
                type="number"
                min={0}
                max={960}
                value={edit.overtimeMinutes}
                error={errors.overtimeMinutes}
                onChange={(event) =>
                  setEdit({ ...edit, overtimeMinutes: event.target.value })
                }
              />
              <Field
                label="메모"
                value={edit.note}
                maxLength={200}
                error={errors.note}
                onChange={(event) =>
                  setEdit({ ...edit, note: event.target.value })
                }
              />
              <div className="form-actions">
                <button type="submit" disabled={pending} aria-busy={pending}>
                  저장
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setPicked(undefined)}
                >
                  취소
                </button>
              </div>
            </form>
          </DetailPanel>
        )}
      </div>
    </div>
  );
}
