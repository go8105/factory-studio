import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, ApiError, MutationKeys } from "../shared/api";
import { useSession } from "../app/session";
export const GW = "/api/v1/gw";
export type Person = {
  id: string;
  code: string;
  name: string;
  jobRole: string;
  isActive: boolean;
  version: number;
};
export type Route = {
  id: string;
  code: string;
  name: string;
  isActive: boolean;
  version: number;
  steps: {
    seq: number;
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
  lines: {
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
  drafterId: string;
  routeId: string;
  routeName: string;
  currentStep: number | null;
  roundNo: number;
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
    personId: string;
    personName: string;
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
}>({ person: "", setPerson: () => {}, people: [], reload: () => {} });
export const useRole = () => useContext(RoleContext);
export function useGet<T>(path: string | null) {
  const { session, fail } = useSession();
  const scope = `${session?.workspaceId}:${session?.generationId}`;
  const [state, setState] = useState<{
    key: string;
    data?: T;
    error?: unknown;
  }>({ key: "" });
  const [tick, setTick] = useState(0);
  const key = scope + path;
  useEffect(() => {
    if (!path) return;
    const ac = new AbortController();
    setState({ key });
    api<T>(path.startsWith("/api/") ? path : GW + path, { signal: ac.signal })
      .then((r) => {
        if (!ac.signal.aborted) setState({ key, data: r.data });
      })
      .catch((e) => {
        if (!ac.signal.aborted) {
          setState({ key, error: e });
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
  const { session, fail } = useSession();
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
    body: unknown,
  ): Promise<T | undefined> {
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    role.setBusy?.(true);
    setError(undefined);
    const op = `${session?.workspaceId}/${session?.generationId}/${method}/${path}/${JSON.stringify(body)}`;
    try {
      const r = await api<T>(GW + path, {
        method,
        body,
        csrf: session?.csrfToken,
        key: keys.current.get(op),
      });
      keys.current.complete(op);
      return r.data;
    } catch (e) {
      if (e instanceof ApiError && e.status > 0 && e.status < 500)
        keys.current.complete(op);
      setError(e);
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
