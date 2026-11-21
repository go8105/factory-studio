import { Master, type InputField } from "./Master";
const priceGroup = {
  path: "/api/v1/erp/price-groups",
  code: "code",
  name: "name",
};
const fields: InputField[] = [
  { key: "partnerCode", label: "거래처 코드", maxLength: 40 },
  { key: "partnerName", label: "거래처명", maxLength: 200 },
  {
    key: "partnerKind",
    label: "거래처 구분",
    options: [
      ["CUSTOMER", "매출처"],
      ["SUPPLIER", "매입처"],
      ["BOTH", "매출·매입"],
    ],
    initial: "CUSTOMER",
  },
  {
    key: "paymentTermDays",
    label: "결제조건 일수",
    type: "number",
    nullable: true,
  },
  { key: "isActive", label: "사용 여부", type: "checkbox" },
  { key: "businessNo", label: "사업자등록번호", nullable: true, maxLength: 12 },
  { key: "representative", label: "대표자", nullable: true, maxLength: 60 },
  { key: "businessType", label: "업태", nullable: true, maxLength: 60 },
  { key: "businessItem", label: "종목", nullable: true, maxLength: 60 },
  { key: "address", label: "주소", nullable: true, maxLength: 300 },
  { key: "phone", label: "전화", nullable: true, maxLength: 30 },
  { key: "contactName", label: "담당자", nullable: true, maxLength: 60 },
  { key: "partnerGroup", label: "거래처 그룹", nullable: true, maxLength: 40 },
  { key: "creditLimit", label: "여신 한도", nullable: true },
  { key: "creditDays", label: "여신 기간(일)", type: "number", nullable: true },
  {
    key: "salePriceGroupId",
    label: "판매 단가 그룹",
    nullable: true,
    lookup: priceGroup,
  },
  {
    key: "purchasePriceGroupId",
    label: "구매 단가 그룹",
    nullable: true,
    lookup: priceGroup,
  },
];
export function Partners() {
  return (
    <Master
      id="E-15"
      title="거래처"
      path="/api/v1/erp/partners"
      fields={fields}
      columns={[
        "partnerCode",
        "partnerName",
        "partnerKind",
        "paymentTermDays",
        "partnerGroup",
        "creditLimit",
        "salePriceGroupId",
        "purchasePriceGroupId",
        "isActive",
      ]}
      note="매출·매입을 함께 하는 거래처는 구분을 '매출·매입'으로 둡니다. 여신 한도는 수주·출하지시에서 경고로만 쓰고 막지 않습니다. 단가 그룹은 종류가 맞아야 저장됩니다(판매 자리에 구매 그룹을 넣을 수 없습니다). 결제조건을 비워 두면 만기 미설정입니다. 참조 중인 거래처는 삭제 대신 사용 여부를 변경할 수 있습니다."
    />
  );
}
