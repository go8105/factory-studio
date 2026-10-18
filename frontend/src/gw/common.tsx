import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, ApiError, MutationKeys } from "../shared/api";
import { useSession } from "../app/session";
import { Link, type LinkProps } from "react-router-dom";
export const CompanyContext = createContext<{
  companyId?: string;
  epoch?: number;
  invalidate?: (error: unknown) => void;
}>({});
export function companyPath(path: string, companyId?: string) {
  if (
    companyId === undefined ||
    (path.startsWith("/api/") && !path.startsWith("/api/v1/gw/"))
  )
    return path;
  const [base, query = ""] = path.split("?");
  if (base === "/companies" || base.endsWith("/gw/companies")) return path;
  const params = new URLSearchParams(query);
  params.delete("personId");
  params.set("companyId", companyId);
  return base + "?" + params;
}
export function GwLink(props: LinkProps) {
  const { companyId } = useContext(CompanyContext);
  const to =
    typeof props.to === "string" && props.to.startsWith("/gw")
      ? companyPath(props.to, companyId)
      : props.to;
  return <Link {...props} to={to} />;
}
export const GW = "/api/v1/gw";
export type Person = {
  id: string;
  code: string;
  name: string;
  jobRole: string;
  isActive: boolean;
  version: number;
};
export type HrEmployee = {
  employeeCode: string;
  name: string;
  status: string;
  departmentCode: string;
  departmentName: string;
  gradeName: string;
  dutyName: string | null;
  isHead: boolean;
};
export type Department = {
  code: string;
  name: string;
  parentCode: string | null;
  isActive: boolean;
  headEmployeeCode: string | null;
};
export type OrgSnapshot = {
  id: string;
  code: string;
  name: string;
  parentId: string | null;
  isActive: boolean;
  hrSyncedAt: string | null;
};
export type HrPreview = {
  available: boolean;
  digest: string | null;
  employees: HrEmployee[] | null;
  departments: Department[] | null;
  organizations: OrgSnapshot[];
  people: (Person & {
    hrEmployeeCode: string | null;
    organizationUnitId: string | null;
  })[];
};
export type ParticipantRole = "APPROVER" | "CONSENT" | "REFERENCE";
export const documentKinds = [
  "GENERAL",
  "ERP_PURCHASE",
  "ERP_PO",
  "ERP_EXPENSE",
  "PLM_ECO",
];
export function useDocumentKinds() {
  return useRole().companyId !== undefined ? ["GENERAL"] : documentKinds;
}
export const sourceKinds: Record<string, string> = {
  ERP_PURCHASE: "PURCHASE_INVOICE",
  ERP_PO: "PURCHASE_ORDER",
  ERP_EXPENSE: "EXPENSE_CLAIM",
  PLM_ECO: "ECO",
};
export type Route = {
  id: string;
  code: string;
  name: string;
  isActive: boolean;
  version: number;
  steps: {
    seq: number;
    participantRole: ParticipantRole;
    personId: string;
    name: string;
    jobRole: string;
    isActive: boolean;
  }[];
};
export type Page<T> = {
  rows: T[];
  total: number;
  offset: number;
  limit: number;
};
export type Event = {
  id: string;
  eventSeq: number;
  eventType: string;
  personName: string;
  actorKind: string;
  onBehalfOfPersonId?: string | null;
  details?: {
    participantRole?: ParticipantRole;
    originalPersonName?: string;
    cause?: string;
    personName?: string;
  };
  reason: string | null;
  createdAt: string;
};
export type Snapshot = {
  documentNo: string;
  partnerName: string;
  currency: string;
  totalAmount: string;
  supplyAmount: string;
  taxAmount: string;
  lines?: {
    lineNo: number;
    itemCode: string;
    quantity: string;
    unit: string;
    unitPrice: string;
    totalAmount: string;
  }[];
};
export type Document = {
  id: string;
  documentNo: string;
  title: string;
  body: string;
  kind: string;
  status: string;
  version: number;
  drafterName: string;
  drafterOrgName?: string | null;
  drafterId: string;
  routeId: string;
  routeName: string;
  currentStep: number | null;
  roundNo: number;
  policyVersion?: number;
  authoritySnapshot?: {
    code: string;
    finalSeq: number;
    amountFrom: string;
    amountTo: string | null;
    currency: string;
    effectiveFrom: string;
    effectiveTo: string | null;
  };
  actionSteps?: {
    stepId: string;
    participantRole: ParticipantRole;
    personName: string;
    delegationId: string | null;
  }[];
  amount: string | null;
  currency: string | null;
  sourceNo: string | null;
  sourceStatus: string | null;
  sourceSnapshot: Snapshot | null;
  sourceComparison: {
    availability: string;
    contentChanged: boolean | null;
    statusChanged: boolean | null;
    currentStatus: string | null;
  } | null;
  steps: {
    id: string;
    seq: number;
    participantRole?: ParticipantRole;
    personId: string;
    personName: string;
    originalPersonName?: string;
    originalPersonId?: string;
    organizationName?: string | null;
    status: string;
    decisionReason: string | null;
    decidedAt: string | null;
  }[];
  events: Event[];
  availableActions: string[];
  previousDocumentId: string | null;
  successor: { id: string; documentNo: string } | null;
  submittedAt: string | null;
};
export type Post = {
  visibility?: string;
  audienceOrgId?: string | null;
  id: string;
  postNo: string;
  boardKind: string;
  title: string;
  body: string;
  authorName: string;
  status: string;
  version: number;
  publishedAt: string | null;
  withdrawReason: string | null;
  events: Event[];
  availableActions: string[];
  previousPostId: string | null;
  successor: { id: string; postNo: string } | null;
};
export const labels: Record<string, string> = {
  STAFF: "담당자",
  MANAGER: "팀장",
  EXECUTIVE: "임원",
  BOARD_ADMIN: "게시판 운영",
  DRAFT: "초안",
  IN_REVIEW: "결재 진행",
  APPROVED: "승인",
  REJECTED: "반려",
  WITHDRAWN: "철회·회수",
  PUBLISHED: "게시",
  WAITING: "대기",
  SKIPPED: "건너뜀",
  GENERAL: "일반 기안",
  ERP_PURCHASE: "ERP 매입",
  ERP_PO: "ERP 구매발주",
  ERP_EXPENSE: "ERP 경비",
  PLM_ECO: "PLM 설계변경",
  APPROVER: "결재",
  CONSENT: "합의",
  REFERENCE: "참고",
  CONSENTED: "합의 완료",
  STEP_REASSIGNED: "결재 담당 재배정",
  READER_GRANTED: "읽기 권한 부여",
  READER_REVOKED: "읽기 권한 회수",
  OPPOSED: "합의 반대",
  consent: "합의",
  oppose: "합의 반대",
  reference: "참고 의견",
  NOTICE: "공지",
  FREE: "자유",
  CREATED: "초안 생성",
  DRAFT_SAVED: "초안 저장",
  SOURCE_REFRESHED: "원문 갱신",
  ROUTE_SELECTED: "결재선 변경",
  SUBMITTED: "상신",
  RESUBMISSION_CREATED: "재상신 초안",
  CORRECTION_CREATED: "정정 초안",
  edit: "편집",
  "select-route": "결재선 다시 선택",
  "refresh-source": "원문 갱신",
  submit: "상신",
  approve: "승인",
  reject: "반려",
  withdraw: "철회·회수",
  resubmit: "새 초안으로 재상신 준비",
  publish: "게시",
  correct: "정정 글 작성",
};
export const time = (v: string | null) =>
  v ? new Date(v).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" }) : "—";
export const RoleContext = createContext<{
  person: string;
  setPerson: (p: string) => void;
  people: Person[];
  reload: () => void;
  error?: unknown;
  busy?: boolean;
  setBusy?: (busy: boolean) => void;
  companyId?: string;
  personName?: string;
  roles?: string[];
  organizationUnitId?: string | null;
  uncertain?: boolean;
  setUncertain?: (value: boolean) => void;
  peopleSearch?: string;
  setPeopleSearch?: (value: string) => void;
}>({ person: "", setPerson: () => {}, people: [], reload: () => {} });
export const useRole = () => useContext(RoleContext);
export function useGet<T>(
  path: string | null,
  retainDuringReload = false,
  reportScopeFailure = true,
) {
  const { session, fail } = useSession();
  const company = useContext(CompanyContext);
  const scope = `${session?.workspaceId}:${session?.generationId}:${company.companyId ?? "personal"}:${company.epoch ?? 0}`;
  const scopedPath =
    path === null ? null : companyPath(path, company.companyId);
  const [state, setState] = useState<{
    key: string;
    data?: T;
    error?: unknown;
  }>({ key: "" });
  const [tick, setTick] = useState(0);
  const key = scope + scopedPath;
  useEffect(() => {
    if (!scopedPath) return;
    const ac = new AbortController();
    setState((previous) =>
      retainDuringReload && previous.key === key ? previous : { key },
    );
    api<T>(scopedPath.startsWith("/api/") ? scopedPath : GW + scopedPath, {
      signal: ac.signal,
    })
      .then((r) => {
        if (!ac.signal.aborted) setState({ key, data: r.data });
      })
      .catch((e) => {
        if (!ac.signal.aborted) {
          setState({ key, error: e });
          if (
            e instanceof ApiError &&
            [403, 404].includes(e.status) &&
            path !== "/me" &&
            reportScopeFailure
          )
            company.invalidate?.(e);
          if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
        }
      });
    return () => ac.abort();
  }, [key, tick]);
  return {
    data: state.key === key ? state.data : undefined,
    error: state.key === key ? state.error : undefined,
    reload: () => setTick((t) => t + 1),
    setData: (data: T) => setState({ key, data }),
  };
}
export function useSend() {
  const role = useRole();
  const company = useContext(CompanyContext);
  const { session, fail } = useSession();
  const currentScope = `${session?.workspaceId}:${session?.generationId}:${company.companyId ?? "personal"}:${company.epoch ?? 0}`;
  const liveScope = useRef(currentScope);
  liveScope.current = currentScope;
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const uncertainOperation = useRef<string | undefined>(undefined);
  const keys = useRef(new MutationKeys());
  const busy = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    if (!pending) return;
    const block = (event: MouseEvent) => {
      if ((event.target as Element | null)?.closest?.("a[href]")) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    document.addEventListener("click", block, true);
    return () => document.removeEventListener("click", block, true);
  }, [pending]);
  async function send<T>(
    path: string,
    method: string,
    body?: unknown,
  ): Promise<T | undefined> {
    if (busy.current || !mounted.current) return;
    busy.current = true;
    setPending(true);
    role.setBusy?.(true);
    setError(undefined);
    const scopedPath = companyPath(path, company.companyId);
    const outgoing =
      company.companyId !== undefined && body && typeof body === "object"
        ? Object.fromEntries(
            Object.entries(body).filter(([k]) => k !== "actingPersonId"),
          )
        : body;
    const op = `${session?.workspaceId}/${session?.generationId}/${company.companyId ?? "personal"}/${company.epoch ?? 0}/${method}/${scopedPath}/${JSON.stringify(outgoing)}`;
    if (uncertainOperation.current && uncertainOperation.current !== op) {
      busy.current = false;
      setPending(false);
      role.setBusy?.(false);
      setError(
        new ApiError(0, {
          code: "NETWORK_UNCERTAIN",
          message: "응답이 불명확한 이전 요청을 같은 입력으로 다시 확인하세요.",
        }),
      );
      return;
    }
    try {
      const r = await api<T>(GW + scopedPath, {
        method,
        body: outgoing,
        csrf: session?.csrfToken,
        key: keys.current.get(op),
      });
      keys.current.complete(op);
      uncertainOperation.current = undefined;
      role.setUncertain?.(false);
      return mounted.current && liveScope.current === currentScope
        ? r.data
        : undefined;
    } catch (e) {
      if (e instanceof ApiError && e.status > 0 && e.status < 500)
        keys.current.complete(op);
      if (!mounted.current || liveScope.current !== currentScope)
        return undefined;
      if (e instanceof ApiError && (e.status === 0 || e.status >= 500)) {
        uncertainOperation.current = op;
        role.setUncertain?.(true);
      } else {
        uncertainOperation.current = undefined;
        role.setUncertain?.(false);
      }
      setError(e);
      if (
        e instanceof ApiError &&
        [403, 404].includes(e.status) &&
        e.error.code !== "STEP_UP_REQUIRED"
      )
        company.invalidate?.(e);
      if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      return undefined;
    } finally {
      busy.current = false;
      setPending(false);
      role.setBusy?.(false);
    }
  }
  return { send, pending, error, setError };
}

// 검색 페이지 밖의 선택 ID는 허용된 최소 표시만 개별 조회한다.
export function SelectedPeople({
  ids,
  onRemove,
}: {
  ids: string[];
  onRemove?: (id: string) => void;
}) {
  const role = useRole();
  if (role.companyId === undefined) return null;
  return (
    <>
      {ids
        .filter((id) => id && !role.people.some((p) => p.id === id))
        .map((id) => (
          <SelectedPeer key={id} id={id} onRemove={onRemove} />
        ))}
    </>
  );
}
function SelectedPeer({
  id,
  onRemove,
}: {
  id: string;
  onRemove?: (id: string) => void;
}) {
  const person = useGet<Person>(`/people/${id}`, false, false);
  const name =
    person.data?.name ??
    `직원 ${id}${person.error ? " (비활성·미연결 또는 조회 불가)" : ""}`;
  return onRemove ? (
    <label className="inline-check">
      <input type="checkbox" checked onChange={() => onRemove(id)} />
      {name}
    </label>
  ) : (
    <option value={id}>{name}</option>
  );
}
