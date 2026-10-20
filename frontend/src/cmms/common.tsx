// CMMS 화면 공통 (FS-029 · DSN-21): API 경로·타입·문구.
export const CMMS = "/api/v1/cmms";

export type AssetType =
  | "INJECTION"
  | "ASSEMBLY"
  | "INSPECTION"
  | "HVAC"
  | "UTILITY"
  | "OTHER"
  | "MOLD"
  | "LINE"
  | "COMPONENT"
  | "FACILITY";
export type AssetSource = "CMMS" | "MES" | "MES_MOLD" | "BEMS";
export type Criticality = "A" | "B" | "C";
/** 보전 원인 6분류. SPC의 4M1E와 다르다 — 설비가 왜 섰는지를 본다. */
export type Cause =
  "WEAR" | "LUBRICATION" | "ELECTRICAL" | "SETTING" | "EXTERNAL" | "OTHER";
export type CodeKind = "SYMPTOM" | "CAUSE" | "ACTION";

export type Asset = {
  id: number;
  code: string;
  name: string;
  assetType: AssetType;
  location: string | null;
  source: AssetSource;
  sourceCode: string | null;
  parentAssetId: number | null;
  manufacturer: string | null;
  model: string | null;
  serialNo: string | null;
  installedOn: string | null;
  acquisitionCost: string | null;
  criticality: Criticality | null;
  isActive: boolean;
};
export type AssetNode = Pick<
  Asset,
  | "id"
  | "code"
  | "name"
  | "assetType"
  | "location"
  | "source"
  | "sourceCode"
  | "parentAssetId"
  | "criticality"
  | "isActive"
> & { depth: number };
export type ImportCandidate = {
  sourceCode: string;
  name: string;
  assetType: AssetType;
  location: string | null;
  note?: string;
};
export type FailureCode = {
  id: number;
  kind: CodeKind;
  code: string;
  name: string;
  causeCategory: Cause | null;
  isActive: boolean;
};

export const ASSET_TYPE_LABEL: Record<AssetType, string> = {
  INJECTION: "사출기",
  ASSEMBLY: "조립기",
  INSPECTION: "검사기",
  HVAC: "공조기",
  UTILITY: "유틸리티",
  OTHER: "기타",
  MOLD: "금형",
  LINE: "라인",
  COMPONENT: "구성품",
  FACILITY: "시설",
};
export const SOURCE_LABEL: Record<AssetSource, string> = {
  CMMS: "직접 등록",
  MES: "MES 설비",
  MES_MOLD: "MES 금형",
  BEMS: "BEMS 공조기",
};
/** 가져오기에서 고르는 원천. 직접 등록(CMMS)은 가져오기 대상이 아니다. */
export const IMPORT_LABEL = {
  MES: "MES 설비",
  MES_MOLD: "MES 금형",
  BEMS: "BEMS 공조기",
} as const;
export type ImportSource = keyof typeof IMPORT_LABEL;
export const CRITICALITY_LABEL: Record<Criticality, string> = {
  A: "A · 멈추면 라인이 선다",
  B: "B · 대체 수단이 있다",
  C: "C · 여유가 있다",
};
export const CODE_KIND_LABEL: Record<CodeKind, string> = {
  SYMPTOM: "증상",
  CAUSE: "원인",
  ACTION: "조치",
};
export const CAUSE_LABEL: Record<Cause, string> = {
  WEAR: "마모",
  LUBRICATION: "윤활",
  ELECTRICAL: "전기",
  SETTING: "설정",
  EXTERNAL: "외부 요인",
  OTHER: "기타",
};

export type WoKind = "BM" | "PM";
export type WoStatus = "REQUESTED" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED";
export type WoSource =
  "MANUAL" | "BEMS_ALARM" | "SPC_SIGNAL" | "PM_PLAN" | "RWS_REQUEST";
export type Skill = "MECHANICAL" | "ELECTRICAL" | "UTILITY" | "GENERAL";

export type WorkLog = {
  id: number;
  loggedAt: string;
  minutes: number;
  note: string | null;
  technicianId: number | null;
  technicianName: string | null;
};
export type WorkOrder = {
  id: number;
  woNo: string;
  assetId: number;
  assetCode: string;
  assetName: string;
  assetType: AssetType;
  kind: WoKind;
  source: WoSource;
  sourceRef: string | null;
  sourceSummary: string | null;
  dueOn: string | null;
  title: string;
  description: string | null;
  status: WoStatus;
  requestedAt: string;
  failureAt: string | null;
  startedAt: string | null;
  completedAt: string | null;
  restoredAt: string | null;
  causeCategory: Cause | null;
  action: string | null;
  cancelledAt: string | null;
  cancelReason: string | null;
  technicianId: number | null;
  technicianName: string | null;
  vendorId: number | null;
  vendorName: string | null;
  externalCost: string | null;
  symptomCodeId: number | null;
  symptomCode: string | null;
  symptomName: string | null;
  actionCodeId: number | null;
  actionCode: string | null;
  actionName: string | null;
  logs?: WorkLog[];
};
export type PendingSignal = {
  id: string;
  source: "BEMS_ALARM" | "SPC_SIGNAL";
  sourceRef: string;
  summary: string;
  severity: string | null;
  detectedAt: string;
  suggestedAssetId: number | null;
  suggestedAssetCode: string | null;
};
export type SignalBoard = {
  sources: { bems: boolean; spc: boolean };
  signals: PendingSignal[];
};
export type Technician = {
  id: number;
  code: string;
  name: string;
  skill: Skill;
  hourlyRate: string;
  currency: string;
  hrEmployeeCode: string | null;
  isActive: boolean;
};
export type Vendor = {
  id: number;
  code: string;
  name: string;
  erpPartnerCode: string | null;
  phone: string | null;
  isActive: boolean;
};

export const WO_STATUS_LABEL: Record<WoStatus, string> = {
  REQUESTED: "접수",
  IN_PROGRESS: "진행",
  COMPLETED: "완료",
  CANCELLED: "취소",
};
export const WO_STATUS_TONE: Record<WoStatus, "normal" | "warning" | "issue"> =
  {
    REQUESTED: "issue",
    IN_PROGRESS: "warning",
    COMPLETED: "normal",
    CANCELLED: "normal",
  };
export const WO_KIND_LABEL: Record<WoKind, string> = {
  BM: "고장",
  PM: "예방",
};
export const WO_SOURCE_LABEL: Record<WoSource, string> = {
  MANUAL: "직접 접수",
  BEMS_ALARM: "BEMS 경보",
  SPC_SIGNAL: "SPC 이상",
  PM_PLAN: "보전 계획",
  RWS_REQUEST: "RWS 요청",
};
export const SKILL_LABEL: Record<Skill, string> = {
  MECHANICAL: "기계",
  ELECTRICAL: "전기",
  UTILITY: "유틸리티",
  GENERAL: "일반",
};

export const time = (value: string) =>
  new Date(value).toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
export const money = (value: string | null) =>
  value == null ? "—" : `${Number(value).toLocaleString("ko-KR")}원`;
/** 작업 기록 분 합계를 "1시간 20분"으로. 인건비의 근거가 되는 값이다. */
export const duration = (minutes: number) =>
  minutes >= 60
    ? `${Math.floor(minutes / 60)}시간${minutes % 60 ? ` ${minutes % 60}분` : ""}`
    : `${minutes}분`;
