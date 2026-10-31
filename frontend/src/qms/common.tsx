// QMS 화면 공통 (FS-023): API 경로·타입·상태 배지. 공통 훅(shared/hooks)에 QMS 접두사를 붙인다.
import { Badge, EmptyState } from "../shared/components";
import { useApiLists, useApiSend } from "../shared/hooks";
export { fieldErrors, moduleOff } from "../shared/hooks";

export const QMS = "/api/v1/qms";

export type DefectType = {
  id: number;
  code: string;
  name: string;
  isActive: boolean;
  usedCount: number;
};
export type Method = "RANGE" | "PASS_FAIL";
export type SpecItem = {
  id?: number;
  seq?: number;
  name: string;
  method: Method;
  lowerLimit: string | null;
  upperLimit: string | null;
  unit: string | null;
  isRequired: boolean;
};
export type SpecStatus = "draft" | "published" | "retired";
export type SpecKind = "OUTGOING" | "INCOMING";
/** 기준에 적을 수 있는 AQL. 백엔드 sampling.AQLS와 같아야 한다. */
export const AQLS = ["0.65", "1.0", "1.5", "2.5", "4.0", "6.5"] as const;
export const SPEC_KIND: Record<SpecKind, string> = {
  OUTGOING: "출하 (반품·초품 포함)",
  INCOMING: "수입",
};
export type SamplingPlan = {
  letter: string;
  sampleSize: number;
  acceptNumber: number;
  rejectNumber: number;
  aql: string;
  isFullInspection: boolean;
};
/** 수입 검사 대기 한 줄 — WMS 격리 입고 줄에 검사 수준을 얹은 것. */
export type IncomingLot = {
  sourceRef: string;
  noticeNo: string;
  noticeKind: string;
  partnerCode: string | null;
  inspectedAt: string;
  lotNo: string | null;
  itemCode: string;
  itemName: string;
  qty: string;
  unit: string;
  level: InspectionLevel;
  hasSpec: boolean;
  isTarget: boolean;
};
export type Spec = {
  id: number;
  itemCode: string;
  itemName: string;
  versionNo: number;
  status: SpecStatus;
  publishedAt: string | null;
  note: string | null;
  inspectionKind: SpecKind;
  aql: string | null;
  itemCount: number;
  inspectionCount: number;
  items?: SpecItem[];
};
export type Judgement = "PASS" | "FAIL";
export type InspectionValue = {
  specItemId: number;
  seq: number;
  name: string;
  method: Method;
  lowerLimit: string | null;
  upperLimit: string | null;
  unit: string | null;
  isRequired: boolean;
  measuredValue: string | null;
  passValue: boolean | null;
  judgement: Judgement | null;
  defectTypeId: number | null;
  defectCode: string | null;
  defectName: string | null;
  gaugeId: number | null;
  gaugeCode: string | null;
  gaugeName: string | null;
};
export type Hold = {
  id: number;
  holdNo: string;
  lotNo: string;
  itemCode: string;
  inspectionId: number;
  inspectionNo: string;
  status: "held" | "released";
  heldAt: string;
  disposition: "REINSPECTED" | "CONCESSION" | "SCRAP" | null;
  releaseInspectionId: number | null;
  releaseInspectionNo: string | null;
  releaseReason: string | null;
  releasedAt: string | null;
};
export type Inspection = {
  id: number;
  inspectionNo: string;
  source: "MES" | "MANUAL" | "QMS" | "WMS";
  inspectionKind: "OUTGOING" | "INCOMING" | "RETURN" | "FIRST_ARTICLE";
  partnerCode: string | null;
  sourceRef: string | null;
  sampling: "AQL" | "MANUAL";
  acceptNumber: number | null;
  rejectNumber: number | null;
  defectCount: number | null;
  specAql: string | null;
  lotNo: string;
  itemCode: string;
  itemName: string;
  lotQty: string;
  unit: string;
  sampleQty: string;
  specId: number;
  specVersion: number;
  reinspectionOfId: number | null;
  status: "draft" | "confirmed";
  result: Judgement | null;
  inspectedOn: string;
  confirmedAt: string | null;
  note: string | null;
  values?: InspectionValue[];
  activeHold?: Hold | null;
  /** SPC 미조치 이상(FS-028 D44). null = SPC 꺼짐. 판정에는 영향이 없다. */
  spcSignal?: boolean | null;
};
export type MesLot = {
  lotNo: string;
  itemCode: string;
  itemName: string;
  finalGoodQty: string;
  unit: string;
  completedAt: string;
  status: "pending" | "drafting" | "inspected";
  draftInspectionId: number | null;
  latestResult: Judgement | null;
  hasSpec: boolean;
  spcSignal: boolean | null;
};

/** LOT 옆 "SPC 이상" 배지(FS-028 D44). 표시만 하고 판정·보류를 막지 않는다. */
export function SpcBadge({ signal }: { signal?: boolean | null }) {
  return signal ? (
    <Badge tone="warning">
      <span title="공정 중 관리도 이상이 조치되지 않았습니다. 판정에는 영향을 주지 않습니다.">
        SPC 이상
      </span>
    </Badge>
  ) : null;
}

/** 검사 출처. QMS는 4M 변경 신고에서 만든 초품 검사다(Q-12). */
export const SOURCE = {
  MES: "MES 조회",
  MANUAL: "직접 입력",
  QMS: "4M 초품",
  WMS: "WMS 입고",
} as const;
export const INSPECTION_KIND = {
  OUTGOING: "출하",
  INCOMING: "수입",
  RETURN: "반품",
  FIRST_ARTICLE: "초품",
} as const;

export const num = (v: string | number, digits = 3) =>
  Number(v).toLocaleString("ko-KR", { maximumFractionDigits: digits });
export const time = (v: string) =>
  new Date(v).toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });

export function ModuleOff() {
  return (
    <EmptyState
      reason="QMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
      to="/workspace"
      action="내 공간으로"
    />
  );
}

const SPEC: Record<SpecStatus, [string, "normal" | "warning" | "issue"]> = {
  draft: ["초안", "warning"],
  published: ["게시", "normal"],
  retired: ["폐기", "issue"],
};
export function SpecBadge({ status }: { status: SpecStatus }) {
  const [label, tone] = SPEC[status];
  return <Badge tone={tone}>{label}</Badge>;
}
export function ResultBadge({ result }: { result: Judgement | null }) {
  if (result === null) return <Badge tone="warning">작성 중</Badge>;
  return result === "PASS" ? (
    <Badge tone="normal">합격</Badge>
  ) : (
    <Badge tone="issue">불합격</Badge>
  );
}
export const DISPOSITION = {
  REINSPECTED: "재검사 합격",
  CONCESSION: "특채",
  SCRAP: "폐기 판정",
} as const;
export function HoldBadge({ hold }: { hold: Hold }) {
  return hold.status === "held" ? (
    <Badge tone="issue">보류 중</Badge>
  ) : (
    <Badge tone="normal">해제 · {DISPOSITION[hold.disposition!]}</Badge>
  );
}

/** 기준 한계를 한 줄로: 2.48~2.52 mm · ≥ 100 MΩ · 합·부 */
export function limitText(item: {
  method: Method;
  lowerLimit: string | null;
  upperLimit: string | null;
  unit: string | null;
}) {
  if (item.method === "PASS_FAIL") return "합·부";
  const lo = item.lowerLimit === null ? null : num(item.lowerLimit, 4);
  const hi = item.upperLimit === null ? null : num(item.upperLimit, 4);
  const range =
    lo !== null && hi !== null
      ? `${lo}~${hi}`
      : lo !== null
        ? `≥ ${lo}`
        : `≤ ${hi}`;
  return `${range} ${item.unit ?? ""}`.trim();
}

/** 화면 미리보기 판정. 최종 판정은 서버 응답이다(모듈 설계 3장). */
export function previewJudgement(
  item: Pick<InspectionValue, "method" | "lowerLimit" | "upperLimit">,
  measured: string,
  passed: boolean | null,
): Judgement | null {
  if (item.method === "PASS_FAIL")
    return passed === null ? null : passed ? "PASS" : "FAIL";
  if (measured.trim() === "" || Number.isNaN(Number(measured))) return null;
  const value = Number(measured);
  if (item.lowerLimit !== null && value < Number(item.lowerLimit))
    return "FAIL";
  if (item.upperLimit !== null && value > Number(item.upperLimit))
    return "FAIL";
  return "PASS";
}

export const useLists = <T extends unknown[]>(paths: string[]) =>
  useApiLists<T>(QMS, paths);
export const useSend = (onDone: () => void) => useApiSend(QMS, onDone);

export type GaugeStatus = "ACTIVE" | "REPAIR" | "RETIRED";
export type DueState = "NONE" | "OK" | "SOON" | "OVERDUE";
export type Calibration = {
  id: number;
  gaugeId: number;
  calibratedOn: string;
  nextDueOn: string;
  result: Judgement;
  agency: string | null;
  certificateNo: string | null;
};
export type Gauge = {
  id: number;
  code: string;
  name: string;
  gaugeKind: string;
  measureRange: string | null;
  resolution: string | null;
  calibrationCycleDays: number;
  status: GaugeStatus;
  lastCalibratedOn: string | null;
  nextDueOn: string | null;
  lastResult: Judgement | null;
  dueState: DueState;
  dueInDays: number | null;
  calibrations?: Calibration[];
};
export type ChangeType = "MAN" | "MACHINE" | "MATERIAL" | "METHOD";
export type CnStatus = "REQUESTED" | "APPROVED" | "REJECTED" | "VERIFIED";
export type ChangeNotice = {
  id: number;
  cnNo: string;
  changeType: ChangeType;
  itemCode: string;
  description: string;
  requestedOn: string;
  effectiveOn: string;
  status: CnStatus;
  decidedAt: string | null;
  decisionNote: string | null;
  firstArticleInspectionId: number | null;
  firstArticleNo: string | null;
  firstArticleResult: Judgement | null;
  plmEcoNo: string | null;
  firstArticles?: Inspection[];
};

export const GAUGE_STATUS: Record<GaugeStatus, string> = {
  ACTIVE: "사용 중",
  REPAIR: "수리 중",
  RETIRED: "폐기",
};
export const CHANGE_TYPE: Record<ChangeType, string> = {
  MAN: "사람",
  MACHINE: "설비",
  MATERIAL: "자재",
  METHOD: "방법",
};
export const CN_STATUS: Record<CnStatus, string> = {
  REQUESTED: "신청",
  APPROVED: "승인",
  REJECTED: "반려",
  VERIFIED: "확인 완료",
};

export function GaugeStatusBadge({ status }: { status: GaugeStatus }) {
  const tone = status === "ACTIVE" ? "normal" : "warning";
  return <Badge tone={tone}>{GAUGE_STATUS[status]}</Badge>;
}

/** 교정 도래. 저장하지 않고 마지막 교정의 다음 기한에서 파생한 값이다. */
export function DueBadge({ gauge }: { gauge: Gauge }) {
  if (gauge.dueState === "NONE")
    return <span className="muted">기록 없음</span>;
  // 마지막 교정이 불합격이면 남은 날을 세어 줄 일이 아니다 — 다시 교정해야 한다.
  if (gauge.lastResult === "FAIL")
    return <Badge tone="issue">재교정 필요 · {gauge.lastCalibratedOn}</Badge>;
  if (gauge.dueState === "OVERDUE")
    return <Badge tone="issue">기한 경과 · {gauge.nextDueOn}</Badge>;
  if (gauge.dueState === "SOON")
    return (
      <Badge tone="warning">
        {gauge.dueInDays}일 남음 · {gauge.nextDueOn}
      </Badge>
    );
  return <span>{gauge.nextDueOn}</span>;
}

export function CnStatusBadge({ status }: { status: CnStatus }) {
  const tone =
    status === "VERIFIED"
      ? "normal"
      : status === "REJECTED"
        ? "issue"
        : "warning";
  return <Badge tone={tone}>{CN_STATUS[status]}</Badge>;
}

export type NcrOrigin = "INCOMING" | "PROCESS" | "OUTGOING" | "CUSTOMER";
export type NcrStatus = "OPEN" | "CLOSED";
export type Ncr = {
  id: number;
  ncrNo: string;
  origin: NcrOrigin;
  itemCode: string;
  lotNo: string | null;
  qty: string;
  defectTypeId: number | null;
  defectCode: string | null;
  defectName: string | null;
  description: string;
  immediateAction: string | null;
  inspectionId: number | null;
  inspectionNo: string | null;
  claimId: number | null;
  sourceRef: string | null;
  reportedOn: string;
  status: NcrStatus;
  closedAt: string | null;
  capaCount: number;
  verifiedCount: number;
  capas?: Capa[];
};
export type CapaKind = "CORRECTIVE" | "PREVENTIVE";
export type CapaStatus = "OPEN" | "DONE" | "VERIFIED" | "INEFFECTIVE";
export type Capa = {
  id: number;
  capaNo: string;
  ncrId: number;
  ncrNo: string;
  itemCode: string;
  kind: CapaKind;
  rootCause: string;
  action: string;
  ownerName: string;
  dueOn: string;
  status: CapaStatus;
  doneAt: string | null;
  verifiedAt: string | null;
  verificationNote: string | null;
  ownerHrCode: string | null;
};
/** 공정 부적합의 근거 후보 = MES 공정 불량 1건(1b `defects`). */
export type MesDefect = {
  sourceRef: string;
  lotNo: string;
  itemCode: string;
  itemName: string;
  processCode: string;
  defectQty: string;
  unit: string;
  reason: string | null;
  confirmedAt: string;
};

export const NCR_ORIGIN: Record<NcrOrigin, string> = {
  INCOMING: "수입",
  PROCESS: "공정",
  OUTGOING: "출하",
  CUSTOMER: "고객",
};
export const NCR_STATUS: Record<NcrStatus, string> = {
  OPEN: "미결",
  CLOSED: "종결",
};
export const CAPA_KIND: Record<CapaKind, string> = {
  CORRECTIVE: "시정",
  PREVENTIVE: "예방",
};
export const CAPA_STATUS: Record<CapaStatus, string> = {
  OPEN: "진행",
  DONE: "완료",
  VERIFIED: "유효 확인",
  INEFFECTIVE: "무효",
};

export function NcrBadge({ status }: { status: NcrStatus }) {
  return status === "CLOSED" ? (
    <Badge tone="normal">종결</Badge>
  ) : (
    <Badge tone="warning">미결</Badge>
  );
}
export function CapaBadge({ status }: { status: CapaStatus }) {
  const tone =
    status === "VERIFIED"
      ? "normal"
      : status === "INEFFECTIVE"
        ? "issue"
        : "warning";
  return <Badge tone={tone}>{CAPA_STATUS[status]}</Badge>;
}

export type Severity = "MINOR" | "MAJOR" | "CRITICAL";
export type ClaimStatus = "RECEIVED" | "INVESTIGATING" | "RESPONDED" | "CLOSED";
export type LotTrace = {
  lotNo: string;
  itemCode: string;
  itemName: string;
  orderNo: string;
  status: string;
  materials: {
    itemCode: string;
    itemName: string;
    lotNo: string | null;
    qty: string;
    unit: string;
    processCode: string;
    issuedAt: string;
  }[];
  parents: { lotNo: string; itemCode: string; relation: string }[];
  children: { lotNo: string; itemCode: string; relation: string }[];
  usedIn: { lotNo: string; itemCode: string; qty: string; unit: string }[];
};
export type Claim = {
  id: number;
  claimNo: string;
  customerCode: string;
  receivedOn: string;
  itemCode: string;
  lotNo: string | null;
  qty: string;
  severity: Severity;
  description: string;
  returnRef: string | null;
  status: ClaimStatus;
  response: string | null;
  respondedOn: string | null;
  closedAt: string | null;
  crmInquiryNo: string | null;
  ncrCount: number;
  ncrs?: Ncr[];
  trace?: LotTrace | null;
  mesEnabled?: boolean;
};
export type Partner = {
  partnerCode: string;
  partnerName: string;
  partnerKind: string;
};
export type InspectionLevel = "EXEMPT" | "NORMAL" | "TIGHTENED";
export type SupplierLevel = {
  id: number;
  partnerCode: string;
  itemCode: string | null;
  level: InspectionLevel;
  validFrom: string;
  reason: string;
  ratingId: number | null;
  ratingMonth: string | null;
  grade: string | null;
  isCurrent: boolean;
};
export type SupplierRating = {
  id: number;
  ratingMonth: string;
  partnerCode: string;
  lotCount: number;
  failedLotCount: number;
  defectPpm: string;
  scarCount: number;
  grade: "A" | "B" | "C" | "D";
  suggestedLevel: InspectionLevel | null;
};
export type ScarStatus = "OPEN" | "RESPONDED" | "CLOSED";
export type Scar = {
  id: number;
  scarNo: string;
  partnerCode: string;
  inspectionId: number | null;
  inspectionNo: string | null;
  ncrId: number | null;
  ncrNo: string | null;
  issuedOn: string;
  dueOn: string;
  response: string | null;
  respondedOn: string | null;
  status: ScarStatus;
  closedAt: string | null;
};

export const SEVERITY: Record<Severity, string> = {
  MINOR: "경미",
  MAJOR: "중대",
  CRITICAL: "치명",
};
export const CLAIM_STATUS: Record<ClaimStatus, string> = {
  RECEIVED: "접수",
  INVESTIGATING: "조사 중",
  RESPONDED: "회신",
  CLOSED: "종결",
};
export const LEVEL: Record<InspectionLevel, string> = {
  EXEMPT: "면제",
  NORMAL: "보통",
  TIGHTENED: "강화",
};
export const SCAR_STATUS: Record<ScarStatus, string> = {
  OPEN: "발행",
  RESPONDED: "회신",
  CLOSED: "종결",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const tone =
    severity === "CRITICAL"
      ? "issue"
      : severity === "MAJOR"
        ? "warning"
        : "normal";
  return <Badge tone={tone}>{SEVERITY[severity]}</Badge>;
}
export function ClaimBadge({ status }: { status: ClaimStatus }) {
  const tone = status === "CLOSED" ? "normal" : "warning";
  return <Badge tone={tone}>{CLAIM_STATUS[status]}</Badge>;
}
export function LevelBadge({ level }: { level: InspectionLevel }) {
  const tone =
    level === "TIGHTENED" ? "issue" : level === "EXEMPT" ? "normal" : "warning";
  return <Badge tone={tone}>{LEVEL[level]}</Badge>;
}
export function GradeBadge({ grade }: { grade: string }) {
  const tone = grade === "A" ? "normal" : grade === "D" ? "issue" : "warning";
  return <Badge tone={tone}>{grade}</Badge>;
}
export function ScarBadge({ status }: { status: ScarStatus }) {
  const tone = status === "CLOSED" ? "normal" : "warning";
  return <Badge tone={tone}>{SCAR_STATUS[status]}</Badge>;
}
