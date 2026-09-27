import { PageTitle } from "../shared/components";
import { Master, type InputField } from "./Master";
const accounts: InputField[] = [
  { key: "accountCode", label: "계정 코드" },
  { key: "accountName", label: "계정과목" },
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
    <div className="page-fill">
      <PageTitle id="E-18" title="계정과목·분개규칙" help="/help/erp/e-18" />
      <p className="notice">
        읽기 전용 — 7개 계정과목과 10개 분개규칙을 조회합니다. 전표
        확정·총계정원장·결산은 범위 밖입니다.
      </p>
      <div className="split-view fill">
        <section className="fill">
          <Master
            embedded
            readOnly
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
        </section>
        <aside className="panel detail-panel" aria-label="매핑 이유">
          <h2>매핑 이유</h2>
          <p>
            매출은 외상매출금(총액)을 차변, 제품매출(공급가액)과
            부가세예수금(세액)을 대변에 둡니다. 매입은 원재료·부가세대급금을
            차변, 외상매입금을 대변에 둡니다.
          </p>
          <p>
            수금은 소명액만큼 보통예금 차변·외상매출금 대변, 지급은 외상매입금
            차변·보통예금 대변입니다. 미소명 잔여는 분개에 포함하지 않습니다.
          </p>
          <p>
            DEBIT = 차변, CREDIT = 대변. TOTAL = 총액, SUPPLY = 공급가액, TAX =
            세액, APPLY = 소명액.
          </p>
        </aside>
      </div>
    </div>
  );
}
