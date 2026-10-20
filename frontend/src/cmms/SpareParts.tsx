// C-06 예비품 — 보전에 쓰는 부품 목록과 WMS 재고 (UI-03 S 패턴, DSN-21 Q6).
// 재고 원장은 WMS만 갖는다(D50). CMMS는 수량을 저장하지 않고 볼 때마다 WMS에서 읽는다.
import { Badge, type Column } from "../shared/components";
import { CODE_PATTERN, MasterScreen, type MasterSpec } from "../shared/master";
import { CMMS, money, qty, type SparePart } from "./common";

type Draft = {
  code: string;
  name: string;
  unit: string;
  safetyStock: string;
  itemCode: string;
  unitCost: string;
  isActive: boolean;
};

const columns: Column<SparePart>[] = [
  { key: "code", label: "코드" },
  { key: "name", label: "예비품명" },
  { key: "unit", label: "단위" },
  {
    key: "itemCode",
    label: "WMS 품목",
    render: (r) => r.itemCode ?? <span className="muted">연결 안 됨</span>,
  },
  {
    key: "stock",
    label: "재고",
    render: (r) =>
      !r.stockKnown ? (
        <span className="muted">모름</span>
      ) : (
        <>
          {qty(r.stock!.qtyOnHand)} {r.stock!.unit}
          {r.stock!.isShort && (
            <>
              {" "}
              <Badge tone="issue">부족</Badge>
            </>
          )}
        </>
      ),
  },
  {
    key: "safetyStock",
    label: "안전 재고(참고)",
    render: (r) => qty(r.safetyStock),
  },
  { key: "unitCost", label: "표준 단가", render: (r) => money(r.unitCost) },
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

const spec: MasterSpec<SparePart, Draft> = {
  id: "C-06",
  title: "예비품",
  subtitle: "보전에 쓰는 부품과 WMS 재고입니다",
  help: "cmms/c-06",
  base: `${CMMS}/spare-parts`,
  blank: {
    code: "",
    name: "",
    unit: "EA",
    safetyStock: "0",
    itemCode: "",
    unitCost: "",
    isActive: true,
  },
  intro: (
    <p role="note" className="muted">
      <strong>재고는 WMS가 갖습니다.</strong> CMMS는 수량을 저장하지 않고 볼
      때마다 WMS에서 읽습니다. WMS 품목을 잇지 않았거나 WMS를 꺼 두면 재고가
      "모름"입니다 — 0이 아닙니다. 부족 여부는 WMS에 안전 재고가 설정된 품목만
      가립니다.
    </p>
  ),
  columns,
  fields: [
    {
      kind: "text",
      key: "code",
      label: "코드",
      required: true,
      maxLength: 20,
      pattern: CODE_PATTERN,
      title: "영문 대문자로 시작하는 2~20자",
      upper: true,
    },
    {
      kind: "text",
      key: "name",
      label: "예비품명",
      required: true,
      maxLength: 100,
    },
    { kind: "text", key: "unit", label: "단위", required: true, maxLength: 10 },
    {
      kind: "text",
      key: "itemCode",
      label: "WMS 품목 코드(선택)",
      maxLength: 40,
      title: "WMS 소모품(SUPPLY) 품목 코드를 적으면 재고가 보입니다.",
      upper: true,
    },
    {
      kind: "text",
      key: "safetyStock",
      label: "안전 재고(참고)",
      title: "부족 판정은 WMS 안전 재고로 합니다. 이 값은 참고용입니다.",
    },
    {
      kind: "text",
      key: "unitCost",
      label: "표준 단가(선택)",
      title: "부품을 쓸 때 이 단가가 스냅샷으로 기록됩니다.",
    },
    { kind: "check", key: "isActive", label: "사용" },
  ],
  labels: {
    create: "예비품 등록",
    caption: "예비품",
    emptyReason:
      "예비품이 없습니다. 작업지시에 부품을 적으려면 먼저 등록하세요.",
    editTitle: (row) => `${row.name} 수정`,
    deleted: (row) => `${row.name}을(를) 삭제했습니다.`,
    moduleOff:
      "CMMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};

export function SpareParts() {
  return <MasterScreen spec={spec} />;
}
