// H-10 급여 기준 — 급여 항목·사원 기준(기본급·고정 수당)·상여 규칙 (DSN-30 F21·F22·F27).
// 한 화면에 셋을 묶고 탭으로 나눈다. 항목은 공통 엔진, 나머지 둘은 자식 줄·참조가 있어 직접 만든다.
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
import { CODE_PATTERN, MasterScreen, type MasterSpec } from "../shared/master";
import type { Employee } from "./Employees";

const BASE = "/api/v1/hr";
const LIMIT = 20;
const ITEM_KINDS = { EARNING: "지급", DEDUCTION: "공제" };
const CALC_KINDS = {
  BASE: "기본급",
  FIXED: "고정 수당",
  OVERTIME: "연장(배수)",
  NIGHT: "야간(배수)",
  HOLIDAY: "휴일(배수)",
  BONUS: "상여(지급률)",
  RATE: "공제 비율(%)",
};
export type PayItem = {
  id: number;
  code: string;
  name: string;
  itemKind: string;
  calcKind: string;
  rate: string | null;
  isTaxable: boolean;
  displayOrder: number;
  isActive: boolean;
};
type PayBase = {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  effectiveFrom: string;
  baseSalary: string;
  ordinaryHours: number;
  fixedTotal: string;
};
type BaseLine = {
  id: number;
  payItemId: number;
  itemCode: string;
  itemName: string;
  amount: string;
};
type BonusRule = {
  id: number;
  payableMm: string;
  ratePercent: string;
  payItemId: number;
  isActive: boolean;
};
/** 금액은 원 단위 정수다. 자릿점을 찍어 읽기 쉽게만 바꾼다. */
export const won = (value: string | number) =>
  Number(value).toLocaleString("ko-KR");

const itemSpec: MasterSpec<PayItem, Omit<PayItem, "id">> = {
  id: "H-10",
  title: "급여 기준",
  subtitle: "지급·공제 항목과 계산 방식을 정합니다",
  help: "hr/h-10",
  base: `${BASE}/pay-items`,
  blank: {
    code: "",
    name: "",
    itemKind: "EARNING",
    calcKind: "BASE",
    rate: "",
    isTaxable: true,
    displayOrder: 1,
    isActive: true,
  },
  intro: (
    <p>
      공제는 <b>비율(%)</b>로만 만들고 과세 지급 합계에 걸립니다.
      연장·야간·휴일은 통상시급에 곱할 <b>배수</b>를 적습니다.
    </p>
  ),
  columns: [
    { key: "code", label: "코드" },
    { key: "name", label: "이름" },
    {
      key: "itemKind",
      label: "구분",
      render: (r) =>
        ITEM_KINDS[r.itemKind as keyof typeof ITEM_KINDS] ?? r.itemKind,
    },
    {
      key: "calcKind",
      label: "계산 방식",
      render: (r) =>
        CALC_KINDS[r.calcKind as keyof typeof CALC_KINDS] ?? r.calcKind,
    },
    { key: "rate", label: "배수·비율", render: (r) => r.rate ?? "—" },
    {
      key: "isTaxable",
      label: "과세",
      render: (r) =>
        r.isTaxable ? "과세" : <Badge tone="warning">비과세</Badge>,
    },
    { key: "displayOrder", label: "순서" },
  ],
  fields: [
    {
      kind: "text",
      key: "code",
      label: "코드",
      required: true,
      maxLength: 30,
      pattern: CODE_PATTERN,
      title: "영문 대문자·숫자로 시작하는 1~30자",
      upper: true,
    },
    { kind: "text", key: "name", label: "이름", required: true, maxLength: 60 },
    { kind: "select", key: "itemKind", label: "구분", options: ITEM_KINDS },
    {
      kind: "select",
      key: "calcKind",
      label: "계산 방식",
      options: CALC_KINDS,
      note: "공제는 비율(%)만, 지급은 비율이 아닌 방식만 고를 수 있습니다.",
    },
    {
      kind: "text",
      key: "rate",
      label: "배수·비율",
      maxLength: 9,
      title: "연장 1.5 같은 배수, 공제 4.5 같은 퍼센트",
    },
    {
      kind: "check",
      key: "isTaxable",
      label: "과세 대상 (공제 계산에 들어갑니다)",
    },
    {
      kind: "number",
      key: "displayOrder",
      label: "순서",
      required: true,
      min: 1,
    },
    { kind: "check", key: "isActive", label: "사용" },
  ],
  labels: {
    create: "급여 항목 등록",
    caption: "급여 항목",
    emptyReason:
      "급여 항목이 없습니다. 기본급(BASE) 항목이 있어야 계산할 수 있습니다.",
    editTitle: (row) => `${row.name} 수정`,
    deleted: (row) => `${row.name}을(를) 삭제했습니다.`,
    moduleOff:
      "HR을 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};

const TABS = {
  items: "급여 항목",
  bases: "사원 급여 기준",
  bonus: "상여 규칙",
};

export function PayStandards() {
  const [tab, setTab] = useState<keyof typeof TABS>("items");
  return (
    <div className="page-fill">
      <nav className="filter-bar" aria-label="급여 기준 구분">
        {Object.entries(TABS).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={tab === key ? "" : "secondary"}
            aria-pressed={tab === key}
            onClick={() => setTab(key as keyof typeof TABS)}
          >
            {label}
          </button>
        ))}
      </nav>
      {tab === "items" ? (
        <MasterScreen spec={itemSpec} />
      ) : tab === "bases" ? (
        <PayBases />
      ) : (
        <BonusRules />
      )}
    </div>
  );
}

const EMPTY_BASE = {
  employeeId: "",
  effectiveFrom: "",
  baseSalary: "",
  ordinaryHours: "209",
};

function PayBases() {
  const { fail } = useSession();
  const [rows, setRows] = useState<PayBase[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState(EMPTY_BASE);
  const [picked, setPicked] = useState<PayBase>();
  const [lines, setLines] = useState<BaseLine[]>();
  const [adding, setAdding] = useState({ payItemId: "", amount: "" });
  const [done, setDone] = useState("");
  const {
    send,
    pending,
    error: saveError,
    deleteButtons,
  } = useApiSend(BASE, () => setReload((n) => n + 1));
  const lookups = useApiLists<[Employee[], PayItem[]]>(BASE, [
    "/employees?limit=200",
    "/pay-items?limit=200&isActive=true",
  ]);
  const [employees = [], items = []] = lookups.data ?? [];
  const fixedItems = items.filter((item) => item.calcKind === "FIXED");
  const guard = useDiscardGuard(creating && draft.employeeId !== "");

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    api<PayBase[]>(`${BASE}/pay-bases?offset=${offset}&limit=${LIMIT}`, {
      signal: controller.signal,
    })
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
  }, [offset, reload]);

  // 고른 기준의 고정 수당 줄은 목록을 다시 불러올 때마다 함께 새로 읽는다.
  useEffect(() => {
    if (!picked) return setLines(undefined);
    const controller = new AbortController();
    api<PayBase & { items: BaseLine[] }>(`${BASE}/pay-bases/${picked.id}`, {
      signal: controller.signal,
    })
      .then((reply) => setLines(reply.data.items))
      .catch(() => controller.signal.aborted || setLines([]));
    return () => controller.abort();
  }, [picked?.id, reload]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const made = await send<PayBase>("/pay-bases", "POST", {
      employeeId: Number(draft.employeeId),
      effectiveFrom: draft.effectiveFrom,
      baseSalary: draft.baseSalary,
      ordinaryHours: Number(draft.ordinaryHours),
    });
    if (made) {
      setCreating(false);
      setDraft(EMPTY_BASE);
      setDone("급여 기준을 등록했습니다. 고정 수당은 상세에서 넣습니다.");
    }
  }

  async function addLine(event: FormEvent) {
    event.preventDefault();
    if (!picked || pending) return;
    const made = await send(`/pay-bases/${picked.id}/items`, "POST", {
      payItemId: Number(adding.payItemId),
      amount: adding.amount,
    });
    if (made) setAdding({ payItemId: "", amount: "" });
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
  const columns: Column<PayBase>[] = [
    { key: "employeeCode", label: "사원 코드" },
    { key: "employeeName", label: "이름" },
    { key: "effectiveFrom", label: "적용 시작 월" },
    { key: "baseSalary", label: "기본급", render: (r) => won(r.baseSalary) },
    { key: "ordinaryHours", label: "통상 시간" },
    { key: "fixedTotal", label: "고정 수당", render: (r) => won(r.fixedTotal) },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button className="link-button" onClick={() => setPicked(r)}>
            고정 수당
          </button>
          {deleteButtons(`base-${r.id}`, `/pay-bases/${r.id}`)}
        </span>
      ),
    },
  ];
  return (
    <>
      <PageTitle
        id="H-10"
        title="사원 급여 기준"
        subtitle="적용 시작 월마다 쌓이고, 계산은 가장 최근 기준을 씁니다"
        help="hr/h-10"
        actions={
          <button
            type="button"
            disabled={!employees.length}
            onClick={() => guard.guard(() => setCreating(true))}
          >
            급여 기준 등록
          </button>
        }
      />
      {done && <p role="status">{done}</p>}
      <ErrorNotice error={lookups.error} />
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <div className="split-view fill">
        <section className="fill">
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
              caption="사원 급여 기준"
              offset={offset}
              total={total}
              limit={LIMIT}
              onPage={setOffset}
              empty={
                <EmptyState
                  reason="급여 기준이 없습니다. 기본급이 있어야 급여를 계산할 수 있습니다."
                  action="급여 기준 등록"
                  onAction={() => setCreating(true)}
                />
              }
            />
          )}
        </section>
        {creating && (
          <FormPanel
            title="급여 기준 등록"
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
            <div className="field">
              <label htmlFor="pay-base-employee">사원</label>
              <select
                id="pay-base-employee"
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
            <Field
              label="적용 시작 월"
              type="month"
              value={draft.effectiveFrom}
              required
              error={errors.effectiveFrom}
              onChange={(event) =>
                setDraft({ ...draft, effectiveFrom: event.target.value })
              }
            />
            <Field
              label="기본급 (원)"
              type="number"
              min={0}
              step={1000}
              value={draft.baseSalary}
              required
              error={errors.baseSalary}
              onChange={(event) =>
                setDraft({ ...draft, baseSalary: event.target.value })
              }
            />
            <Field
              label="월 통상 시간"
              type="number"
              min={1}
              max={400}
              value={draft.ordinaryHours}
              required
              error={errors.ordinaryHours}
              onChange={(event) =>
                setDraft({ ...draft, ordinaryHours: event.target.value })
              }
            />
            <small>
              통상시급 = 기본급 ÷ 월 통상 시간. 연장·야간 수당의 근거입니다.
            </small>
          </FormPanel>
        )}
        {picked && (
          <DetailPanel
            title={`${picked.employeeName} ${picked.effectiveFrom} 고정 수당`}
            onClose={() => setPicked(undefined)}
          >
            {!lines ? (
              <Loading />
            ) : lines.length ? (
              <table>
                <caption>고정 수당</caption>
                <thead>
                  <tr>
                    <th>항목</th>
                    <th>금액</th>
                    <th>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line) => (
                    <tr key={line.id}>
                      <td>{line.itemName}</td>
                      <td>{won(line.amount)}</td>
                      <td>
                        {deleteButtons(
                          `line-${line.id}`,
                          `/pay-base-items/${line.id}`,
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p>고정 수당이 없습니다.</p>
            )}
            <form onSubmit={(event) => void addLine(event)}>
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <div className="field">
                <label htmlFor="base-line-item">고정 수당 항목</label>
                <select
                  id="base-line-item"
                  value={adding.payItemId}
                  required
                  onChange={(event) =>
                    setAdding({ ...adding, payItemId: event.target.value })
                  }
                >
                  <option value="">선택</option>
                  {fixedItems.map((item) => (
                    <option key={item.id} value={String(item.id)}>
                      {item.name}
                    </option>
                  ))}
                </select>
                {!fixedItems.length && (
                  <small>
                    계산 방식이 '고정 수당'인 급여 항목을 먼저 만드세요.
                  </small>
                )}
              </div>
              <Field
                label="금액 (원)"
                type="number"
                min={0}
                step={1000}
                value={adding.amount}
                required
                error={errors.amount}
                onChange={(event) =>
                  setAdding({ ...adding, amount: event.target.value })
                }
              />
              <div className="form-actions">
                <button type="submit" disabled={pending} aria-busy={pending}>
                  수당 추가
                </button>
              </div>
            </form>
          </DetailPanel>
        )}
      </div>
    </>
  );
}

const MONTHS = Array.from({ length: 12 }, (_, index) =>
  String(index + 1).padStart(2, "0"),
);
const EMPTY_BONUS = { payableMm: "01", ratePercent: "100", payItemId: "" };

function BonusRules() {
  const { fail } = useSession();
  const [rows, setRows] = useState<BonusRule[]>();
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState(EMPTY_BONUS);
  const [done, setDone] = useState("");
  const {
    send,
    pending,
    error: saveError,
    deleteButtons,
  } = useApiSend(BASE, () => setReload((n) => n + 1));
  const lookups = useApiLists<[PayItem[]]>(BASE, ["/pay-items?limit=200"]);
  const [items = []] = lookups.data ?? [];
  const bonusItems = items.filter((item) => item.calcKind === "BONUS");
  const guard = useDiscardGuard(creating && draft.payItemId !== "");

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    api<BonusRule[]>(`${BASE}/bonus-rules?limit=50`, {
      signal: controller.signal,
    })
      .then((reply) => setRows(reply.data))
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(error);
        if (error instanceof ApiError && [401, 410].includes(error.status))
          fail(error);
      });
    return () => controller.abort();
  }, [reload]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const made = await send("/bonus-rules", "POST", {
      payableMm: draft.payableMm,
      ratePercent: draft.ratePercent,
      payItemId: Number(draft.payItemId),
    });
    if (made) {
      setCreating(false);
      setDraft(EMPTY_BONUS);
      setDone(`${draft.payableMm}월 상여 규칙을 등록했습니다.`);
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
  const columns: Column<BonusRule>[] = [
    {
      key: "payableMm",
      label: "지급 월",
      render: (r) => `${Number(r.payableMm)}월`,
    },
    { key: "ratePercent", label: "지급률", render: (r) => `${r.ratePercent}%` },
    {
      key: "payItemId",
      label: "급여 항목",
      render: (r) => items.find((item) => item.id === r.payItemId)?.name ?? "—",
    },
    {
      key: "isActive",
      label: "사용",
      render: (r) =>
        r.isActive ? <Badge>사용</Badge> : <Badge tone="issue">중지</Badge>,
    },
    {
      key: "id",
      label: "관리",
      render: (r) => deleteButtons(`bonus-${r.id}`, `/bonus-rules/${r.id}`),
    },
  ];
  return (
    <>
      <PageTitle
        id="H-10"
        title="상여 규칙"
        subtitle="지정한 달에 기본급 × 지급률을 상여 항목으로 넣습니다"
        help="hr/h-10"
        actions={
          <button
            type="button"
            disabled={!bonusItems.length}
            onClick={() => guard.guard(() => setCreating(true))}
          >
            상여 규칙 등록
          </button>
        }
      />
      {done && <p role="status">{done}</p>}
      <ErrorNotice error={lookups.error} />
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <div className="split-view fill">
        <section className="fill">
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
              caption="상여 규칙"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => {}}
              empty={
                <EmptyState
                  reason={
                    bonusItems.length
                      ? "상여 규칙이 없습니다. 지급 월을 정하면 그 달 급여에 상여가 들어갑니다."
                      : "계산 방식이 '상여'인 급여 항목을 먼저 만드세요."
                  }
                  action="상여 규칙 등록"
                  onAction={() => bonusItems.length && setCreating(true)}
                />
              }
            />
          )}
        </section>
        {creating && (
          <FormPanel
            title="상여 규칙 등록"
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
                  onClick={() => setCreating(false)}
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
              <label htmlFor="bonus-month">지급 월</label>
              <select
                id="bonus-month"
                value={draft.payableMm}
                onChange={(event) =>
                  setDraft({ ...draft, payableMm: event.target.value })
                }
              >
                {MONTHS.map((month) => (
                  <option key={month} value={month}>
                    {Number(month)}월
                  </option>
                ))}
              </select>
            </div>
            <Field
              label="지급률 (%)"
              type="number"
              min={0}
              max={1000}
              step={5}
              value={draft.ratePercent}
              required
              error={errors.ratePercent}
              onChange={(event) =>
                setDraft({ ...draft, ratePercent: event.target.value })
              }
            />
            <div className="field">
              <label htmlFor="bonus-item">급여 항목</label>
              <select
                id="bonus-item"
                value={draft.payItemId}
                required
                onChange={(event) =>
                  setDraft({ ...draft, payItemId: event.target.value })
                }
              >
                <option value="">선택</option>
                {bonusItems.map((item) => (
                  <option key={item.id} value={String(item.id)}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>
          </FormPanel>
        )}
      </div>
    </>
  );
}
