import { Master, type InputField } from "./Master";
const fields: InputField[] = [
  {
    key: "partnerId",
    label: "거래처",
    lookup: {
      path: "/api/v1/erp/partners",
      code: "partnerCode",
      name: "partnerName",
    },
  },
  {
    key: "itemId",
    label: "품목",
    lookup: { path: "/api/v1/erp/items", code: "itemCode", name: "name" },
  },
  { key: "priceKind", label: "단가 구분", initial: "SALE", maxLength: 20 },
  { key: "unitPrice", label: "단가", initial: "0" },
  { key: "currency", label: "통화", initial: "KRW", maxLength: 3 },
  { key: "effectiveFrom", label: "시작월", type: "month" },
  { key: "effectiveTo", label: "종료월", type: "month", nullable: true },
  { key: "isActive", label: "사용 여부", type: "checkbox" },
];
const groups: InputField[] = [
  { key: "code", label: "그룹 코드", maxLength: 30 },
  { key: "name", label: "그룹명", maxLength: 100 },
  {
    key: "priceKind",
    label: "단가 구분",
    options: [
      ["SALE", "판매"],
      ["PURCHASE", "구매"],
    ],
    initial: "SALE",
  },
  { key: "isActive", label: "사용 여부", type: "checkbox" },
];
const groupPrices: InputField[] = [
  {
    key: "priceGroupId",
    label: "단가 그룹",
    lookup: { path: "/api/v1/erp/price-groups", code: "code", name: "name" },
  },
  {
    key: "itemId",
    label: "품목",
    lookup: { path: "/api/v1/erp/items", code: "itemCode", name: "name" },
  },
  { key: "unitPrice", label: "단가", initial: "0" },
  { key: "currency", label: "통화", initial: "KRW", maxLength: 3 },
  { key: "validFrom", label: "적용 시작일", type: "date" },
];
export function Prices() {
  return (
    <Master
      id="E-17"
      title="거래처별 단가"
      path="/api/v1/erp/partner-prices"
      fields={fields}
      note="단가는 거래처별 단가 → 거래처가 속한 단가 그룹(적용 시작일이 가장 늦은 것) → 품목 표준 판매가 순서로 정해집니다. 시작월과 종료월을 포함하고, 종료월이 없으면 계속 적용됩니다. 같은 거래처·품목의 구간은 사용 여부와 관계없이 겹칠 수 없습니다."
    >
      <Master
        embedded
        id="E-17"
        title="단가 그룹"
        path="/api/v1/erp/price-groups"
        fields={groups}
      />
      <Master
        embedded
        id="E-17"
        title="단가 그룹 단가"
        path="/api/v1/erp/group-prices"
        fields={groupPrices}
      />
    </Master>
  );
}
