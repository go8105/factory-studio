// H-05 사원 — 인사카드(발령 이력 포함). 부서·직위·직책은 발령으로만 바뀐다(DSN-30 F03).
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { ApiError, MutationKeys, api } from "../shared/api";
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
import { fieldErrors, moduleOff, useApiLists } from "../shared/hooks";
import { CODE_PATTERN } from "../shared/master";

const BASE = "/api/v1/hr";
const LIMIT = 20;
export const STATUS: Record<string, string> = {
  ACTIVE: "재직",
  LEAVE: "휴직",
  RETIRED: "퇴직",
};
export const KIND: Record<string, string> = {
  HIRE: "입사",
  TRANSFER: "부서 이동",
  PROMOTION: "승진",
  DUTY: "직책",
  LEAVE: "휴직",
  RETURN: "복직",
  RETIRE: "퇴직",
};
type Lookup = { id: number; code: string; name: string; titleKind?: string };
export type Employee = {
  id: number;
  employeeCode: string;
  name: string;
  hireDate: string;
  status: string;
  departmentId: number;
  gradeId: number;
  dutyId: number | null;
  workPatternId: number;
  retireDate: string | null;
};
type Appointment = {
  id: number;
  appointmentNo: string;
  kind: string;
  effectiveDate: string;
  status: string;
  reason: string | null;
};
const EMPTY = {
  employeeCode: "",
  name: "",
  hireDate: "",
  departmentId: "",
  gradeId: "",
  dutyId: "",
  workPatternId: "",
};

export function Employees() {
  const { session, fail } = useSession();
  const keys = useRef(new MutationKeys());
  const [rows, setRows] = useState<Employee[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [activeOnly, setActiveOnly] = useState(false);
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [draft, setDraft] = useState(EMPTY);
  const [creating, setCreating] = useState(false);
  const [card, setCard] = useState<
    (Employee & { appointments: Appointment[] }) | null
  >(null);
  const [saveError, setSaveError] = useState<unknown>();
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState("");
  const lookups = useApiLists<[Lookup[], Lookup[], Lookup[]]>(BASE, [
    "/departments?limit=200&active=true",
    "/titles?limit=200",
    "/work-patterns?limit=200",
  ]);
  const [departments = [], titles = [], patterns = []] = lookups.data ?? [];
  const grades = titles.filter((t) => t.titleKind === "GRADE");
  const duties = titles.filter((t) => t.titleKind === "DUTY");
  const dirty = creating && Object.values(draft).some((value) => value !== "");
  const guard = useDiscardGuard(dirty);

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    api<Employee[]>(
      `${BASE}/employees?offset=${offset}&limit=${LIMIT}${activeOnly ? "&status=ACTIVE" : ""}`,
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
  }, [offset, activeOnly, reload]);

  async function openCard(row: Employee) {
    setDone("");
    try {
      const reply = await api<Employee & { appointments: Appointment[] }>(
        `${BASE}/employees/${row.id}`,
      );
      setCard(reply.data);
    } catch (error) {
      setLoadError(error);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const body = {
      employeeCode: draft.employeeCode,
      name: draft.name,
      hireDate: draft.hireDate,
      departmentId: Number(draft.departmentId),
      gradeId: Number(draft.gradeId),
      dutyId: draft.dutyId ? Number(draft.dutyId) : undefined,
      workPatternId: Number(draft.workPatternId),
    };
    const operation = `create:${JSON.stringify(body)}`;
    setPending(true);
    setSaveError(undefined);
    try {
      await api(`${BASE}/employees`, {
        method: "POST",
        body,
        csrf: session?.csrfToken,
        key: keys.current.get(operation),
      });
      keys.current.complete(operation);
      setCreating(false);
      setDraft(EMPTY);
      setReload((n) => n + 1);
      setDone("사원을 등록하고 입사 발령을 확정했습니다.");
    } catch (error) {
      if (error instanceof ApiError && error.status > 0 && error.status < 500)
        keys.current.complete(operation);
      setSaveError(error);
      if (error instanceof ApiError && [401, 410].includes(error.status))
        fail(error);
    } finally {
      setPending(false);
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
  const name = (list: Lookup[], id: number | null) =>
    list.find((x) => x.id === id)?.name ?? "—";
  const columns: Column<Employee>[] = [
    { key: "employeeCode", label: "사원 코드" },
    { key: "name", label: "이름" },
    {
      key: "departmentId",
      label: "부서",
      render: (r) => name(departments, r.departmentId),
    },
    { key: "gradeId", label: "직위", render: (r) => name(grades, r.gradeId) },
    { key: "dutyId", label: "직책", render: (r) => name(duties, r.dutyId) },
    { key: "hireDate", label: "입사일" },
    {
      key: "status",
      label: "재직",
      render: (r) => (
        <Badge tone={r.status === "ACTIVE" ? "normal" : "warning"}>
          {STATUS[r.status] ?? r.status}
        </Badge>
      ),
    },
    {
      key: "id",
      label: "인사카드",
      render: (r) => (
        <button className="link-button" onClick={() => void openCard(r)}>
          열기
        </button>
      ),
    },
  ];
  const ready =
    departments.length > 0 && grades.length > 0 && patterns.length > 0;
  return (
    <div className="page-fill">
      <PageTitle
        id="H-05"
        title="사원"
        subtitle="사원 코드는 모든 솔루션이 가져다 쓰는 사람의 원천입니다"
        help="hr/h-05"
        actions={
          <button
            type="button"
            aria-pressed={creating}
            disabled={!ready}
            onClick={() => guard.guard(() => setCreating(true))}
          >
            사원 등록
          </button>
        }
      />
      {!ready && !lookups.error && (
        <p role="status">
          부서·직위·근무 형태를 먼저 등록하면 사원을 등록할 수 있습니다.
        </p>
      )}
      {done && <p role="status">{done}</p>}
      <ErrorNotice error={lookups.error} />
      <div className="split-view fill">
        <section className="fill">
          <div className="filter-bar">
            <label className="inline-check">
              <input
                type="checkbox"
                checked={activeOnly}
                onChange={(event) => {
                  setOffset(0);
                  setActiveOnly(event.target.checked);
                }}
              />
              재직 중인 사원만
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
              caption="사원 목록"
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason="등록된 사원이 없습니다. 부서·직위·근무 형태를 먼저 등록하세요."
                  action="사원 등록"
                  onAction={() => guard.guard(() => setCreating(true))}
                />
              }
            />
          )}
        </section>
        {creating && (
          <FormPanel
            title="사원 등록"
            guard={guard}
            onClose={() => setCreating(false)}
            onSubmit={(event) => void submit(event)}
            actions={
              <>
                <button type="submit" disabled={pending} aria-busy={pending}>
                  등록
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
            <Field
              label="사원 코드"
              value={draft.employeeCode}
              required
              maxLength={30}
              pattern={CODE_PATTERN}
              title="영문 대문자·숫자로 시작하는 1~30자"
              error={errors.employeeCode}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  employeeCode: event.target.value.toUpperCase(),
                })
              }
            />
            <Field
              label="이름"
              value={draft.name}
              required
              maxLength={60}
              error={errors.name}
              onChange={(event) =>
                setDraft({ ...draft, name: event.target.value })
              }
            />
            <Field
              label="입사일"
              type="date"
              value={draft.hireDate}
              required
              error={errors.hireDate}
              onChange={(event) =>
                setDraft({ ...draft, hireDate: event.target.value })
              }
            />
            <Select
              label="부서"
              value={draft.departmentId}
              options={departments}
              error={errors.departmentId}
              onChange={(value) => setDraft({ ...draft, departmentId: value })}
            />
            <Select
              label="직위"
              value={draft.gradeId}
              options={grades}
              error={errors.gradeId}
              onChange={(value) => setDraft({ ...draft, gradeId: value })}
            />
            <Select
              label="직책"
              value={draft.dutyId}
              options={duties}
              optional
              error={errors.dutyId}
              onChange={(value) => setDraft({ ...draft, dutyId: value })}
            />
            <Select
              label="근무 형태"
              value={draft.workPatternId}
              options={patterns}
              error={errors.workPatternId}
              onChange={(value) => setDraft({ ...draft, workPatternId: value })}
            />
            <small>
              최초 부서·직위는 입사 발령으로 함께 확정됩니다. 이후 변경은 발령
              화면에서 합니다.
            </small>
          </FormPanel>
        )}
        {card && (
          <DetailPanel
            title={`${card.name} 인사카드`}
            onClose={() => setCard(null)}
            wide
          >
            <dl className="detail-grid">
              <dt>사원 코드</dt>
              <dd>{card.employeeCode}</dd>
              <dt>재직</dt>
              <dd>{STATUS[card.status] ?? card.status}</dd>
              <dt>부서</dt>
              <dd>{name(departments, card.departmentId)}</dd>
              <dt>직위·직책</dt>
              <dd>
                {name(grades, card.gradeId)} · {name(duties, card.dutyId)}
              </dd>
              <dt>입사일</dt>
              <dd>{card.hireDate}</dd>
              {card.retireDate && (
                <>
                  <dt>퇴직일</dt>
                  <dd>{card.retireDate}</dd>
                </>
              )}
            </dl>
            <h3>발령 이력</h3>
            <DataTable
              rows={card.appointments}
              columns={[
                { key: "appointmentNo", label: "발령 번호" },
                {
                  key: "kind",
                  label: "종류",
                  render: (r) => KIND[r.kind] ?? r.kind,
                },
                { key: "effectiveDate", label: "발령일" },
                {
                  key: "status",
                  label: "상태",
                  render: (r) => (
                    <Badge
                      tone={r.status === "confirmed" ? "normal" : "warning"}
                    >
                      {r.status === "confirmed" ? "확정" : "작성 중"}
                    </Badge>
                  ),
                },
                { key: "reason", label: "사유", wrap: true },
              ]}
              caption="발령 이력"
              offset={0}
              total={card.appointments.length}
              limit={card.appointments.length || 1}
              onPage={() => {}}
            />
          </DetailPanel>
        )}
      </div>
    </div>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
  optional,
  error,
}: {
  label: string;
  value: string;
  options: Lookup[];
  onChange: (value: string) => void;
  optional?: boolean;
  error?: string;
}) {
  return (
    <div className="field">
      <label htmlFor={`select-${label}`}>{label}</label>
      <select
        id={`select-${label}`}
        value={value}
        required={!optional}
        aria-invalid={!!error}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{optional ? "없음" : "선택"}</option>
        {options.map((option) => (
          <option key={option.id} value={String(option.id)}>
            {option.name}
          </option>
        ))}
      </select>
      {error && <small>{error}</small>}
    </div>
  );
}
