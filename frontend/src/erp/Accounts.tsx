import { PageTitle } from "../shared/components";
import { Master, type InputField } from "./Master";
const accounts: InputField[] = [
  { key: "accountCode", label: "계정 코드", maxLength: 30 },
  { key: "accountName", label: "계정과목", maxLength: 100 },
  {
    key: "accountClass",
    label: "분류",
    options: [
      ["ASSET", "자산"],
      ["LIABILITY", "부채"],
      ["EQUITY", "자본"],
      ["REVENUE", "수익"],
      ["COGS", "매출원가"],
      ["EXPENSE", "판매비와관리비"],
      ["MFG_COST", "제조원가"],
      ["NON_OPERATING", "영업외"],
    ],
    initial: "ASSET",
  },
  {
    key: "normalSide",
    label: "정상 잔액",
    options: [
      ["DEBIT", "차변"],
      ["CREDIT", "대변"],
    ],
    initial: "DEBIT",
  },
  {
    key: "statementGroup",
    label: "재무제표 묶음",
    nullable: true,
    maxLength: 40,
  },
  { key: "requiresPartner", label: "거래처 필수", type: "checkbox" },
  { key: "requiresDepartment", label: "부서 필수", type: "checkbox" },
  { key: "isActive", label: "사용 여부", type: "checkbox" },
];
const rules: InputField[] = [
  { key: "transactionKind", label: "거래 유형" },
  { key: "lineNo", label: "순서" },
  { key: "entrySide", label: "차변·대변" },
  { key: "accountCode", label: "계정 코드" },
  { key: "amountBasis", label: "금액 기준" },
];
export function Accounts() {
  return (
    <>
      <PageTitle id="E-18" title="계정과목·분개규칙" help="erp/e-18" />
      <p className="notice">
        계정은 더하고 사용 여부를 끌 수 있지만 지우지는 못합니다 — 지난 전표가
        계정을 잃기 때문입니다. 이미 쓰이고 있는 계정의 분류와 정상 잔액도 바꿀
        수 없습니다. 분개규칙은 읽기 전용입니다.
      </p>
      <Master
        embedded
        deletable={false}
        id="E-18"
        title="계정과목"
        path="/api/v1/erp/accounts"
        fields={accounts}
      />
      <Master
        embedded
        readOnly
        id="E-18"
        title="분개규칙"
        path="/api/v1/erp/posting-rules"
        fields={rules}
      />
      <section className="panel">
        <h2>매핑 이유</h2>
        <p>
          매출은 외상매출금(총액)을 차변, 제품매출(공급가액)과
          부가세예수금(세액)을 대변에 둡니다. 매입은 원재료·부가세대급금을 차변,
          외상매입금을 대변에 둡니다. 반품은 각각의 반대편입니다.
        </p>
        <p>
          수금은 소명액만큼 보통예금 차변·외상매출금 대변, 지급은 외상매입금
          차변·보통예금 대변입니다. 미소명 잔여는 분개에 포함하지 않습니다.
        </p>
        <p>
          지출결의·카드 규칙의 비용 계정은 기본값이고, 실제 전표는 명세가 고른
          비용 계정을 씁니다. 상계는 같은 거래처의 채무와 채권을 맞물립니다.
        </p>
        <p>
          DEBIT = 차변, CREDIT = 대변. TOTAL = 총액, SUPPLY = 공급가액, TAX =
          세액, APPLY = 소명액, AMOUNT = 그 건의 금액.
        </p>
      </section>
    </>
  );
}
