// M-19 라벨 양식 — LOT·박스·팔레트·자재·지시서 라벨의 크기와 바코드 종류 (DSN-12 F18).
// 팔레트만 QR, 나머지는 Code128. 종류마다 기본 양식은 하나다. 출력은 M-20에서 한다.
import { Badge } from "../shared/components";
import { CODE_PATTERN, MasterScreen, type MasterSpec } from "../shared/master";

export const LABEL_KINDS = {
  LOT: "LOT",
  BOX: "박스",
  PALLET: "팔레트",
  MATERIAL: "자재",
  WORK_ORDER: "작업지시서",
};
const BARCODES = { CODE128: "Code128", QR: "QR" };
type LabelTemplate = {
  id: number;
  code: string;
  labelKind: string;
  barcodeType: string;
  widthMm: number;
  heightMm: number;
  fields: string;
  isDefault: boolean;
  isActive: boolean;
};
type Draft = Omit<LabelTemplate, "id">;

const spec: MasterSpec<LabelTemplate, Draft> = {
  id: "M-19",
  title: "라벨 양식",
  subtitle: "브라우저에서 인쇄할 라벨의 크기와 바코드 종류입니다",
  help: "mes/m-19",
  base: "/api/v1/mes/label-templates",
  blank: {
    code: "",
    labelKind: "LOT",
    barcodeType: "CODE128",
    widthMm: 60,
    heightMm: 40,
    fields: "lotNo,itemCode,qty",
    isDefault: false,
    isActive: true,
  },
  intro: (
    <p>
      <b>팔레트는 QR</b>, 나머지는 Code128을 씁니다. 바코드 값은 대상 번호
      그대로입니다. 종류마다 <b>기본 양식은 하나</b>만 둘 수 있습니다.
    </p>
  ),
  columns: [
    { key: "code", label: "코드" },
    {
      key: "labelKind",
      label: "종류",
      render: (r) =>
        LABEL_KINDS[r.labelKind as keyof typeof LABEL_KINDS] ?? r.labelKind,
    },
    {
      key: "barcodeType",
      label: "바코드",
      render: (r) =>
        BARCODES[r.barcodeType as keyof typeof BARCODES] ?? r.barcodeType,
    },
    {
      key: "widthMm",
      label: "크기",
      render: (r) => `${r.widthMm} × ${r.heightMm} mm`,
    },
    { key: "fields", label: "인쇄 항목", wrap: true },
    {
      key: "isDefault",
      label: "기본",
      render: (r) => (r.isDefault ? <Badge>기본</Badge> : "—"),
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
    {
      kind: "select",
      key: "labelKind",
      label: "종류",
      options: LABEL_KINDS,
      note: "등록 후에는 종류를 바꿀 수 없습니다.",
    },
    {
      kind: "select",
      key: "barcodeType",
      label: "바코드",
      options: BARCODES,
      note: "팔레트는 QR, 나머지는 Code128입니다.",
    },
    {
      kind: "number",
      key: "widthMm",
      label: "가로(mm)",
      required: true,
      min: 20,
      max: 210,
    },
    {
      kind: "number",
      key: "heightMm",
      label: "세로(mm)",
      required: true,
      min: 10,
      max: 297,
    },
    {
      kind: "text",
      key: "fields",
      label: "인쇄 항목",
      required: true,
      maxLength: 300,
      title: "쉼표로 나눕니다. 예: lotNo,itemCode,qty",
    },
    { kind: "check", key: "isDefault", label: "이 종류의 기본 양식" },
    { kind: "check", key: "isActive", label: "사용" },
  ],
  labels: {
    create: "라벨 양식 등록",
    caption: "라벨 양식",
    emptyReason:
      "라벨 양식이 없습니다. 패킹에서 라벨을 뽑으려면 먼저 만듭니다.",
    editTitle: (row) => `${row.code} 수정`,
    deleted: (row) => `${row.code}을(를) 삭제했습니다.`,
    moduleOff:
      "MES를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};

export function Labels() {
  return <MasterScreen spec={spec} />;
}
