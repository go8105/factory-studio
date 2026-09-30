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
export type Spec = {
  id: number;
  itemCode: string;
  itemName: string;
  versionNo: number;
  status: SpecStatus;
  publishedAt: string | null;
  note: string | null;
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
  source: "MES" | "MANUAL";
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
