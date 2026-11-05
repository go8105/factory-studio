// F-11 에너지원 — 공통 엔진(shared/master)에 선언만 넘기는 기준정보 화면의 기준 구현 (W0-5)
import { Badge, type Column } from "../shared/components";
import { MasterScreen, type MasterSpec } from "../shared/master";
export type EnergySource = {
  id: number;
  sourceCode: string;
  name: string;
  sourceKind: string;
  measureUnit: string;
  isBillable: boolean;
  isActive: boolean;
  createdAt: string;
};
type Draft = Omit<EnergySource, "id" | "createdAt">;
const KINDS = {
  ELECTRIC: "전기",
  FUEL: "연료",
  HEAT: "열",
  UTILITY: "유틸리티",
  GENERATION: "발전",
};
const UNITS = ["kWh", "Nm3", "m3", "ton"];
// 기준정보 공통: 등록 순서 안내 (FS-008a FEMS §2)
export function MasterOrder() {
  return (
    <ol className="master-order" aria-label="기준정보 등록 순서">
      <li>사업장 → 공간 → 설비</li>
      <li>에너지원</li>
      <li>계측기 → 채널 (설비·에너지원 필요)</li>
    </ol>
  );
}
const columns: Column<EnergySource>[] = [
  { key: "sourceCode", label: "코드" },
  { key: "name", label: "에너지원명" },
  {
    key: "sourceKind",
    label: "구분",
    render: (r) => KINDS[r.sourceKind as keyof typeof KINDS] ?? r.sourceKind,
  },
  { key: "measureUnit", label: "계측 단위" },
  {
    key: "isBillable",
    label: "요금 부과",
    render: (r) => (r.isBillable ? "부과" : "미부과"),
  },
  {
    key: "isActive",
    label: "사용",
    render: (r) => (
      <Badge tone={r.isActive ? "normal" : "warning"}>
        {r.isActive ? "사용" : "사용 안 함"}
      </Badge>
    ),
  },
];
const spec: MasterSpec<EnergySource, Draft> = {
  id: "F-11",
  title: "에너지원",
  subtitle: "전력·가스·용수를 같은 구조로 관리합니다",
  help: "fems/f-11",
  base: "/api/v1/fems/energy-sources",
  blank: {
    sourceCode: "",
    name: "",
    sourceKind: "ELECTRIC",
    measureUnit: "kWh",
    isBillable: true,
    isActive: true,
  },
  columns,
  intro: <MasterOrder />,
  filter: { label: "사용 중인 에너지원만", query: "active=true" },
  fields: [
    {
      kind: "text",
      key: "sourceCode",
      label: "에너지원 코드",
      required: true,
      maxLength: 20,
      pattern: "[A-Z][A-Z0-9_]{1,19}",
      title: "영문 대문자로 시작하는 2~20자 (대문자·숫자·_)",
      upper: true,
    },
    {
      kind: "text",
      key: "name",
      label: "에너지원명",
      required: true,
      maxLength: 50,
    },
    { kind: "select", key: "sourceKind", label: "에너지 구분", options: KINDS },
    {
      kind: "select",
      key: "measureUnit",
      label: "계측 단위",
      options: UNITS,
      note: "계측기·계수·요금제가 참조 중이면 단위를 바꿀 수 없습니다.",
    },
    { kind: "check", key: "isBillable", label: "요금 부과 대상" },
    {
      kind: "check",
      key: "isActive",
      label: "사용 (끄면 새 입력에서 제외, 기존 기록은 유지)",
    },
  ],
  labels: {
    create: "에너지원 등록",
    caption: "에너지원 목록",
    emptyReason:
      "등록된 에너지원이 없습니다. 계측기·계수·요금제는 에너지원이 있어야 등록할 수 있습니다.",
    editTitle: (row) => `${row.name} 수정`,
    deleted: (row) => `${row.name} 에너지원을 삭제했습니다.`,
    moduleOff:
      "FEMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};
export function EnergySources() {
  return <MasterScreen spec={spec} />;
}
