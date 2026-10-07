// H-06 발령 — 작성 → 확정. 확정해야 사원의 부서·직위·직책·재직 상태가 바뀐다(DSN-30 F03).
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { ApiError, MutationKeys, api } from "../shared/api";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import { fieldErrors, moduleOff, useApiLists } from "../shared/hooks";
import { KIND, type Employee } from "./Employees";

const BASE = "/api/v1/hr";
const LIMIT = 20;
type Lookup = { id: number; code: string; name: string; titleKind?: string };
type Appointment = {
  id: number;
  appointmentNo: string;
  employeeId: number;
  kind: string;
  effectiveDate: string;
  departmentId: number | null;
  gradeId: number | null;
  dutyId: number | null;
  reason: string | null;
  status: string;
  confirmedAt: string | null;
};
// 종류별로 반드시 채워야 하는 칸 (서버 규칙과 같다)
const REQUIRED: Record<string, string[]> = {
  HIRE: ["departmentId", "gradeId"],
  TRANSFER: ["departmentId"],
  PROMOTION: ["gradeId"],
  DUTY: [],
  LEAVE: [],
  RETURN: [],
  RETIRE: [],
};
const SELECTABLE = [
  "TRANSFER",
  "PROMOTION",
  "DUTY",
  "LEAVE",
  "RETURN",
  "RETIRE",
];
const EMPTY = {
  employeeId: "",
  kind: "TRANSFER",
  effectiveDate: "",
  departmentId: "",
  gradeId: "",
  dutyId: "",
  reason: "",
};

export function Appointments() {
  const { session, fail } = useSession();
  const keys = useRef(new MutationKeys());
  const [rows, setRows] = useState<Appointment[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [draftsOnly, setDraftsOnly] = useState(false);
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState(EMPTY);
  const [saveError, setSaveError] = useState<unknown>();
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState("");
  const lookups = useApiLists<[Employee[], Lookup[], Lookup[]]>(BASE, [
    "/employees?limit=200",
    "/departments?limit=200&active=true",
    "/titles?limit=200",
  ]);
  const [employees = [], departments = [], titles = []] = lookups.data ?? [];
  const grades = titles.filter((t) => t.titleKind === "GRADE");
  const duties = titles.filter((t) => t.titleKind === "DUTY");
  const dirty =
    creating &&
    Object.values(draft).some((value) => value !== "" && value !== "TRANSFER");
  const guard = useDiscardGuard(dirty);

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    api<Appointment[]>(
      `${BASE}/appointments?offset=${offset}&limit=${LIMIT}${draftsOnly ? "&status=draft" : ""}`,
      { signal: controller.signal },
    )
      .then((reply) => {
        setRows(reply.data);
        setTotal(reply.page?.total ?? 0);
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(error);
        if (error instanceof ApiError && [401, 410].includes(error.status))
          fail(error);
      });
    return () => controller.abort();
  }, [offset, draftsOnly, reload]);

  async function send(
    operation: string,
    path: string,
    method: string,
    body?: unknown,
  ) {
    setPending(true);
    setSaveError(undefined);
    try {
      await api(`${BASE}${path}`, {
        method,
        body,
        csrf: session?.csrfToken,
        key: keys.current.get(operation),
      });
      keys.current.complete(operation);
      setReload((n) => n + 1);
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.status > 0 && error.status < 500)
        keys.current.complete(operation);
      setSaveError(error);
      if (error instanceof ApiError && [401, 410].includes(error.status))
        fail(error);
      return false;
    } finally {
      setPending(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const body: Record<string, unknown> = {
      employeeId: Number(draft.employeeId),
      kind: draft.kind,
      effectiveDate: draft.effectiveDate,
    };
    for (const field of ["departmentId", "gradeId", "dutyId"] as const)
      if (draft[field]) body[field] = Number(draft[field]);
    if (draft.reason) body.reason = draft.reason;
    const ok = await send(
      `create:${JSON.stringify(body)}`,
      "/appointments",
      "POST",
      body,
    );
    if (ok) {
      setCreating(false);
      setDraft(EMPTY);
      setDone("발령을 작성했습니다. 확정해야 사원 정보가 바뀝니다.");
    }
  }

  async function confirm(row: Appointment) {
    setDone("");
    const ok = await send(
      `confirm:${row.id}`,
      `/appointments/${row.id}/confirm`,
      "POST",
    );
    if (ok) setDone(`${row.appointmentNo} 발령을 확정했습니다.`);
  }

  async function remove(row: Appointment) {
    setDone("");
    const ok = await send(
      `delete:${row.id}`,
      `/appointments/${row.id}`,
      "DELETE",
    );
    if (ok) setDone(`${row.appointmentNo} 발령을 지웠습니다.`);
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
  const label = (list: { id: number; name: string }[], id: number | null) =>
    list.find((x) => x.id === id)?.name ?? "—";
  const columns: Column<Appointment>[] = [
    { key: "appointmentNo", label: "발령 번호" },
    {
      key: "employeeId",
      label: "사원",
      render: (r) => label(employees, r.employeeId),
    },
    { key: "kind", label: "종류", render: (r) => KIND[r.kind] ?? r.kind },
    { key: "effectiveDate", label: "발령일" },
    {
      key: "departmentId",
      label: "부서",
      render: (r) => label(departments, r.departmentId),
    },
    { key: "gradeId", label: "직위", render: (r) => label(grades, r.gradeId) },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={r.status === "confirmed" ? "normal" : "warning"}>
          {r.status === "confirmed" ? "확정" : "작성 중"}
        </Badge>
      ),
    },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        r.status === "draft" ? (
          <span className="row-actions">
            <button disabled={pending} onClick={() => void confirm(r)}>
              확정
            </button>
            <button className="link-button" onClick={() => void remove(r)}>
              삭제
            </button>
          </span>
        ) : (
          <span>—</span>
        ),
    },
  ];
  const required = REQUIRED[draft.kind] ?? [];
  return (
    <div className="page-fill">
      <PageTitle
        id="H-06"
        title="발령"
        subtitle="확정해야 사원의 부서·직위·재직 상태가 바뀝니다"
        help="hr/h-06"
        actions={
          <button
            type="button"
            aria-pressed={creating}
            disabled={!employees.length}
            onClick={() => guard.guard(() => setCreating(true))}
          >
            발령 작성
          </button>
        }
      />
      {done && <p role="status">{done}</p>}
      <ErrorNotice error={lookups.error} />
      {!creating && (
        <ErrorNotice
          error={Object.keys(errors).length ? undefined : saveError}
        />
      )}
      <div className="split-view fill">
        <section className="fill">
          <div className="filter-bar">
            <label className="inline-check">
              <input
                type="checkbox"
                checked={draftsOnly}
                onChange={(event) => {
                  setOffset(0);
                  setDraftsOnly(event.target.checked);
                }}
              />
              작성 중인 발령만
            </label>
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
              caption="발령 목록"
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason="발령이 없습니다. 사원을 등록하면 입사 발령이 함께 기록됩니다."
                  action="발령 작성"
                  onAction={() => guard.guard(() => setCreating(true))}
                />
              }
            />
          )}
        </section>
        {creating && (
          <FormPanel
            title="발령 작성"
            guard={guard}
            onClose={() => setCreating(false)}
            onSubmit={(event) => void submit(event)}
            actions={
              <>
                <button type="submit" disabled={pending} aria-busy={pending}>
                  작성
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => guard.guard(() => setCreating(false))}
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
              <label htmlFor="appointment-employee">사원</label>
              <select
                id="appointment-employee"
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
              <label htmlFor="appointment-kind">발령 종류</label>
              <select
                id="appointment-kind"
                value={draft.kind}
                onChange={(event) =>
                  setDraft({ ...draft, kind: event.target.value })
                }
              >
                {SELECTABLE.map((kind) => (
                  <option key={kind} value={kind}>
                    {KIND[kind]}
                  </option>
                ))}
              </select>
              <small>입사 발령은 사원을 등록할 때 함께 만들어집니다.</small>
            </div>
            <Field
              label="발령일"
              type="date"
              value={draft.effectiveDate}
              required
              error={errors.effectiveDate}
              onChange={(event) =>
                setDraft({ ...draft, effectiveDate: event.target.value })
              }
            />
            <div className="field">
              <label htmlFor="appointment-department">
                부서{required.includes("departmentId") ? "" : " (선택)"}
              </label>
              <select
                id="appointment-department"
                value={draft.departmentId}
                required={required.includes("departmentId")}
                aria-invalid={!!errors.departmentId}
                onChange={(event) =>
                  setDraft({ ...draft, departmentId: event.target.value })
                }
              >
                <option value="">바꾸지 않음</option>
                {departments.map((option) => (
                  <option key={option.id} value={String(option.id)}>
                    {option.name}
                  </option>
                ))}
              </select>
              {errors.departmentId && <small>{errors.departmentId}</small>}
            </div>
            <div className="field">
              <label htmlFor="appointment-grade">
                직위{required.includes("gradeId") ? "" : " (선택)"}
              </label>
              <select
                id="appointment-grade"
                value={draft.gradeId}
                required={required.includes("gradeId")}
                aria-invalid={!!errors.gradeId}
                onChange={(event) =>
                  setDraft({ ...draft, gradeId: event.target.value })
                }
              >
                <option value="">바꾸지 않음</option>
                {grades.map((option) => (
                  <option key={option.id} value={String(option.id)}>
                    {option.name}
                  </option>
                ))}
              </select>
              {errors.gradeId && <small>{errors.gradeId}</small>}
            </div>
            <div className="field">
              <label htmlFor="appointment-duty">직책 (선택)</label>
              <select
                id="appointment-duty"
                value={draft.dutyId}
                onChange={(event) =>
                  setDraft({ ...draft, dutyId: event.target.value })
                }
              >
                <option value="">바꾸지 않음</option>
                {duties.map((option) => (
                  <option key={option.id} value={String(option.id)}>
                    {option.name}
                  </option>
                ))}
              </select>
            </div>
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
