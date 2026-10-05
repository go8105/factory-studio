"""DSN-11: ERP 보강 설계를 목표 DB(schema-target.json)에 반영한다(멱등). 실제 DB 기준인 schema.json은 건드리지 않는다.

근거: docs/modules/erp/ERP_보강설계_DSN-11.md 4장(새 테이블 36·기존 테이블 변경 10), 결정 Q1~Q7.
이미 반영돼 있으면 아무것도 바꾸지 않는다. 새 제약·관계는 목록 끝에 붙인다.
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
KRW = "currency = 'KRW'"
MONTH = "~ '^[0-9]{4}-(0[1-9]|1[0-2])$'"
YEAR = "~ '^[0-9]{4}$'"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
DOC = ("draft", "confirmed", "cancelled")


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-11"}


def money(name, label, nullable=False, rule=""):
    return col(name, label, "numeric(18,2)", nullable=nullable, rule=rule)


def cur():
    return col("currency", "통화", "varchar(3)", default="'KRW'")


def doc_status(default="draft", values=DOC):
    return col(
        "status", "상태", "varchar(20)", default=f"'{default}'", rule=" / ".join(values)
    )


def confirm_cols():
    return [
        col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        col("cancelled_at", "취소 시각", "timestamptz", nullable=True),
        col("cancel_reason", "취소 사유", "varchar(300)", nullable=True),
    ]


def doc_check(t):
    """draft/confirmed/cancelled 시각·사유 정합(기존 erp.purchase_invoice와 같은 식)."""
    return c(
        t,
        "CHECK",
        ["status", "confirmed_at", "cancelled_at", "cancel_reason"],
        "(status = 'draft' AND confirmed_at IS NULL AND cancelled_at IS NULL AND cancel_reason IS NULL) OR "
        "(status = 'confirmed' AND confirmed_at IS NOT NULL AND cancelled_at IS NULL AND cancel_reason IS NULL) OR "
        "(status = 'cancelled' AND cancelled_at IS NOT NULL AND cancel_reason IS NOT NULL AND length(btrim(cancel_reason)) > 0)",
        "상태별 시각·사유",
    )


def amounts_check(t):
    return c(
        t,
        "CHECK",
        ["supply_amount", "tax_amount", "total_amount"],
        "supply_amount >= 0 AND tax_amount >= 0 AND total_amount = supply_amount + tax_amount",
        "공급가·세액·합계",
    )


def line_cols(parent, parent_label):
    return [
        col(parent, parent_label, "bigint"),
        col("line_no", "행 번호", "integer"),
        col("item_id", "품목", "bigint"),
        col("quantity", "수량", "numeric(18,3)"),
        col("unit", "단위", "varchar(10)"),
        col("unit_price", "단가", "numeric(18,4)"),
        money("supply_amount", "공급가"),
        money("tax_amount", "세액"),
        money("total_amount", "합계"),
    ]


def line_checks(t, parent):
    return [
        c(t, "UK", S + [parent, "line_no"], reason="문서 내 행 번호 유일"),
        c(
            t,
            "CHECK",
            [
                "line_no",
                "quantity",
                "unit_price",
                "supply_amount",
                "tax_amount",
                "total_amount",
            ],
            "line_no >= 1 AND quantity > 0 AND unit_price >= 0 AND supply_amount >= 0 AND tax_amount >= 0 AND total_amount = supply_amount + tax_amount",
            "행 수량·금액",
        ),
    ]


E = "erp."
DEPT, EMP, PROJ, PG, PGP = (
    E + "department",
    E + "employee",
    E + "project",
    E + "price_group",
    E + "price_group_price",
)
SR, SRL = E + "sales_return", E + "sales_return_line"
PRQ, PRQL, PO, POL, PRT, PRTL = (
    E + "purchase_request",
    E + "purchase_request_line",
    E + "purchase_order",
    E + "purchase_order_line",
    E + "purchase_return",
    E + "purchase_return_line",
)
RA, PA = E + "receivable_adjust", E + "payable_adjust"
JE, JL, EC, ECL, FP, OB = (
    E + "journal_entry",
    E + "journal_line",
    E + "expense_claim",
    E + "expense_claim_line",
    E + "fiscal_period",
    E + "opening_balance",
)
CR, CIR, CA = E + "cost_run", E + "cost_item_result", E + "cost_allocation"
PTI, VR, VRL = E + "purchase_tax_invoice", E + "vat_return", E + "vat_return_line"
BA, BT, CC, CT, CPI, BU, BUL, FA, DEP = (
    E + "bank_account",
    E + "bank_transaction",
    E + "corporate_card",
    E + "card_transaction",
    E + "cash_plan_item",
    E + "budget",
    E + "budget_line",
    E + "fixed_asset",
    E + "depreciation",
)

ENTRY_KINDS = (
    "GENERAL",
    "SALE",
    "SALES_RETURN",
    "PURCHASE",
    "PURCHASE_RETURN",
    "SUBCONTRACT",
    "RECEIPT",
    "PAYMENT",
    "ADJUST",
    "EXPENSE_CLAIM",
    "CARD",
    "PAYROLL",
    "DEPRECIATION",
    "COGS",
    "CLOSING",
    "REVERSAL",
)
ACCOUNT_CLASSES = (
    "ASSET",
    "LIABILITY",
    "EQUITY",
    "REVENUE",
    "COGS",
    "EXPENSE",
    "MFG_COST",
    "NON_OPERATING",
)
ADJUST_KINDS_AR = ("RETURN_CREDIT", "OFFSET", "BAD_DEBT")
ADJUST_KINDS_AP = ("RETURN_CREDIT", "OFFSET")
TAX_STATES = ("pending", "issued", "transmitting", "transmitted", "failed", "cancelled")
POSTING_KINDS = (
    "SALE",
    "RECEIPT",
    "PURCHASE",
    "PAYMENT",
    "SALES_RETURN",
    "PURCHASE_RETURN",
    "SUBCONTRACT",
    "EXPENSE_CLAIM",
    "CARD",
    "PAYROLL",
    "DEPRECIATION",
    "BAD_DEBT",
    "OFFSET",
    "COGS",
)
AMOUNT_BASES = ("TOTAL", "SUPPLY", "TAX", "APPLY", "AMOUNT")

TABLES = [
    # 01 기초등록
    table(
        DEPT,
        "부서",
        "master",
        "DSN-11 F07. ERP 자체 부서 코드(HR 조직과 별개, FS-013 D1 중복 정상)",
        [
            col("code", "부서 코드", "varchar(30)"),
            col("name", "부서명", "varchar(100)"),
            col(
                "cost_center_kind",
                "원가 구분",
                "varchar(12)",
                rule="MFG 제조 / SALES 판매 / ADMIN 관리",
            ),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        EMP,
        "담당자",
        "master",
        "DSN-11 F07. 전표·문서 담당자 코드. 인사 정보(주민번호·계좌)는 두지 않는다 — 인사는 HR(D79)",
        [
            col("code", "담당자 코드", "varchar(30)"),
            col("name", "이름", "varchar(100)"),
            col("department_id", "부서", "bigint"),
            col(
                "hr_employee_code",
                "HR 사원 코드",
                "varchar(30)",
                nullable=True,
                rule="HR 조회 스냅샷, FK 없음",
            ),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        PROJ,
        "프로젝트",
        "master",
        "DSN-11 F08. 매출·전표 관리항목",
        [
            col("code", "프로젝트 코드", "varchar(30)"),
            col("name", "프로젝트명", "varchar(200)"),
            col("start_on", "시작일", "date", nullable=True),
            col("end_on", "종료일", "date", nullable=True),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        PG,
        "단가 그룹",
        "master",
        "DSN-11 F06. 거래처가 속하는 판매·구매 단가 그룹",
        [
            col("code", "그룹 코드", "varchar(30)"),
            col("name", "그룹명", "varchar(100)"),
            col("price_kind", "구분", "varchar(10)", rule="SALE / PURCHASE"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        PGP,
        "단가 그룹 단가",
        "master",
        "DSN-11 F06. 거래처별 단가(partner_item_price)가 우선, 없으면 그룹 단가",
        [
            col("price_group_id", "단가 그룹", "bigint"),
            col("item_id", "품목", "bigint"),
            col("unit_price", "단가", "numeric(18,4)"),
            cur(),
            col("valid_from", "적용 시작일", "date"),
        ],
    ),
    # 11 영업
    table(
        SR,
        "판매 반품",
        "sales",
        "DSN-11 F16. 확정 시 매출 차감 전표 + 채권 조정(RETURN_CREDIT). 실물 반입은 WMS",
        [
            col("return_no", "반품 번호", "varchar(40)"),
            col("partner_id", "거래처", "bigint"),
            col("sales_record_id", "원 매출", "bigint"),
            col("returned_on", "반품일", "date"),
            col("reason", "사유", "varchar(300)"),
            cur(),
            money("supply_amount", "공급가"),
            money("tax_amount", "세액"),
            money("total_amount", "합계"),
            doc_status(),
            *confirm_cols(),
        ],
    ),
    table(
        SRL,
        "판매 반품 명세",
        "sales",
        "DSN-11 F16",
        line_cols("sales_return_id", "판매 반품"),
    ),
    # 21 구매
    table(
        PRQ,
        "구매 요청",
        "purchase",
        "DSN-11 F21. 수동·CMMS 예비품·ELB/MRO 요청을 받는 자리(원천은 코드 스냅샷)",
        [
            col("request_no", "요청 번호", "varchar(40)"),
            col("requested_on", "요청일", "date"),
            col("department_id", "요청 부서", "bigint", nullable=True),
            col("employee_id", "요청자", "bigint", nullable=True),
            col(
                "source",
                "출처",
                "varchar(10)",
                default="'MANUAL'",
                rule="MANUAL / CMMS / ELB",
            ),
            col("source_ref", "원천 코드", "varchar(60)", nullable=True),
            col(
                "status",
                "상태",
                "varchar(20)",
                default="'draft'",
                rule="draft / confirmed / ordered / cancelled",
            ),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
            col("cancelled_at", "취소 시각", "timestamptz", nullable=True),
            col("cancel_reason", "취소 사유", "varchar(300)", nullable=True),
        ],
    ),
    table(
        PRQL,
        "구매 요청 명세",
        "purchase",
        "DSN-11 F21",
        [
            col("purchase_request_id", "구매 요청", "bigint"),
            col("line_no", "행 번호", "integer"),
            col("item_id", "품목", "bigint"),
            col("quantity", "수량", "numeric(18,3)"),
            col("unit", "단위", "varchar(10)"),
            col("needed_on", "필요일", "date", nullable=True),
        ],
    ),
    table(
        PO,
        "발주서",
        "purchase",
        "DSN-11 F22. 입고 진행(부분·완료)은 WMS 입고를 읽어 파생, 저장하지 않는다",
        [
            col("po_no", "발주 번호", "varchar(40)"),
            col("partner_id", "공급처", "bigint"),
            col("ordered_on", "발주일", "date"),
            col("due_on", "납기", "date", nullable=True),
            col("department_id", "부서", "bigint", nullable=True),
            col("project_id", "프로젝트", "bigint", nullable=True),
            cur(),
            money("supply_amount", "공급가"),
            money("tax_amount", "세액"),
            money("total_amount", "합계"),
            col(
                "status",
                "상태",
                "varchar(20)",
                default="'draft'",
                rule="draft / confirmed / closed / cancelled",
            ),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
            col("closed_at", "종결 시각", "timestamptz", nullable=True),
            col("cancelled_at", "취소 시각", "timestamptz", nullable=True),
            col("cancel_reason", "취소 사유", "varchar(300)", nullable=True),
        ],
    ),
    table(
        POL,
        "발주 명세",
        "purchase",
        "DSN-11 F22",
        [
            *line_cols("purchase_order_id", "발주서"),
            col("purchase_request_line_id", "구매 요청 명세", "bigint", nullable=True),
            col("due_on", "행 납기", "date", nullable=True),
        ],
    ),
    table(
        PRT,
        "구매 반품",
        "purchase",
        "DSN-11 F25. 확정 시 매입 차감 전표 + 채무 조정(RETURN_CREDIT). 실물 반출은 WMS",
        [
            col("return_no", "반품 번호", "varchar(40)"),
            col("partner_id", "공급처", "bigint"),
            col("purchase_invoice_id", "원 매입", "bigint"),
            col("returned_on", "반품일", "date"),
            col("reason", "사유", "varchar(300)"),
            cur(),
            money("supply_amount", "공급가"),
            money("tax_amount", "세액"),
            money("total_amount", "합계"),
            doc_status(),
            *confirm_cols(),
        ],
    ),
    table(
        PRTL,
        "구매 반품 명세",
        "purchase",
        "DSN-11 F25",
        line_cols("purchase_return_id", "구매 반품"),
    ),
    # 71 채권·채무 조정
    table(
        RA,
        "채권 조정",
        "ledger",
        "DSN-11 F16·F76. 반품 대변·상계·대손. 채권 잔액 = 원금 − 수금 소명 − 조정(조회 파생)",
        [
            col("receivable_id", "채권", "bigint"),
            col("partner_id", "거래처", "bigint"),
            cur(),
            col(
                "adjust_kind",
                "조정 종류",
                "varchar(16)",
                rule=" / ".join(ADJUST_KINDS_AR),
            ),
            money("amount", "조정 금액"),
            col("adjusted_on", "조정일", "date"),
            col(
                "source_id",
                "원천 문서",
                "bigint",
                nullable=True,
                rule="판매 반품 id(RETURN_CREDIT)",
            ),
            col(
                "offset_no",
                "상계 번호",
                "varchar(40)",
                nullable=True,
                rule="OFFSET이면 채무 조정과 같은 번호",
            ),
            col("reason", "사유", "varchar(300)", nullable=True),
            col("apply_key", "멱등 키", "varchar(80)"),
        ],
    ),
    table(
        PA,
        "채무 조정",
        "ledger",
        "DSN-11 F25·F76. 반품 대변·상계. 채무 잔액 = 원금 − 지급 소명 − 조정(조회 파생)",
        [
            col("payable_id", "채무", "bigint"),
            col("partner_id", "거래처", "bigint"),
            cur(),
            col(
                "adjust_kind",
                "조정 종류",
                "varchar(16)",
                rule=" / ".join(ADJUST_KINDS_AP),
            ),
            money("amount", "조정 금액"),
            col("adjusted_on", "조정일", "date"),
            col(
                "source_id",
                "원천 문서",
                "bigint",
                nullable=True,
                rule="구매 반품 id(RETURN_CREDIT)",
            ),
            col("offset_no", "상계 번호", "varchar(40)", nullable=True),
            col("reason", "사유", "varchar(300)", nullable=True),
            col("apply_key", "멱등 키", "varchar(80)"),
        ],
    ),
    # 41·51 회계
    table(
        JE,
        "전표",
        "journal",
        "DSN-11 F42~F45·F57. 확정 후 불변, 정정은 역분개(REVERSAL) 새 전표. 차대 일치는 SERVICE",
        [
            col("entry_no", "전표 번호", "varchar(40)"),
            col("entry_date", "전표일", "date"),
            col("entry_kind", "전표 종류", "varchar(16)", rule=" / ".join(ENTRY_KINDS)),
            col(
                "source_kind",
                "원천 종류",
                "varchar(30)",
                nullable=True,
                rule="자동 전표의 원천 테이블 이름(erp.sales_record 등)",
            ),
            col(
                "source_id",
                "원천 id",
                "bigint",
                nullable=True,
                rule="ERP 안 원천 문서 id",
            ),
            col(
                "source_ref",
                "외부 원천 코드",
                "varchar(60)",
                nullable=True,
                rule="HR 급여·MES 외주 코드 스냅샷",
            ),
            col("description", "적요", "varchar(300)", nullable=True),
            col("department_id", "부서", "bigint", nullable=True),
            col("employee_id", "작성 담당자", "bigint", nullable=True),
            cur(),
            col(
                "status",
                "상태",
                "varchar(20)",
                default="'draft'",
                rule="draft / confirmed / reversed",
            ),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
            col("reversal_of_id", "역분개 대상", "bigint", nullable=True),
        ],
    ),
    table(
        JL,
        "전표 라인",
        "journal",
        "DSN-11 F42·F47. 금액은 양수, 차변/대변 구분",
        [
            col("journal_entry_id", "전표", "bigint"),
            col("line_no", "행 번호", "integer"),
            col("account_id", "계정", "bigint"),
            col("side", "차대", "varchar(6)", rule="DEBIT / CREDIT"),
            money("amount", "금액"),
            col("partner_id", "거래처", "bigint", nullable=True),
            col("department_id", "부서", "bigint", nullable=True),
            col("project_id", "프로젝트", "bigint", nullable=True),
            col("memo", "적요", "varchar(300)", nullable=True),
        ],
    ),
    table(
        EC,
        "지출결의서",
        "journal",
        "DSN-11 F46. GW 결재 상태는 읽기 전용 배지(확정 통제 없음). 확정 시 비용 전표",
        [
            col("claim_no", "결의 번호", "varchar(40)"),
            col("claimed_on", "결의일", "date"),
            col("employee_id", "청구자", "bigint"),
            col("department_id", "부서", "bigint"),
            col("pay_method", "지급 방법", "varchar(10)", rule="BANK / CARD / CASH"),
            cur(),
            money("total_amount", "합계"),
            doc_status(),
            *confirm_cols(),
        ],
    ),
    table(
        ECL,
        "지출결의 명세",
        "journal",
        "DSN-11 F46",
        [
            col("expense_claim_id", "지출결의서", "bigint"),
            col("line_no", "행 번호", "integer"),
            col("account_id", "비용 계정", "bigint"),
            money("amount", "금액"),
            col("project_id", "프로젝트", "bigint", nullable=True),
            col("memo", "적요", "varchar(300)", nullable=True),
        ],
    ),
    table(
        FP,
        "회계 기간",
        "closing",
        "DSN-11 F57. 마감 월 전표는 입력·확정·역분개 금지(SERVICE)",
        [
            col("period_month", "회계 월", "varchar(7)", rule="'YYYY-MM'"),
            col(
                "status", "상태", "varchar(10)", default="'open'", rule="open / closed"
            ),
            col("closed_at", "마감 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        OB,
        "기초 잔액",
        "closing",
        "DSN-11 F58. 연도 시작 잔액. 이월은 전년 마감 결과로 새 행 생성",
        [
            col("fiscal_year", "회계 연도", "varchar(4)", rule="'YYYY'"),
            col("account_id", "계정", "bigint"),
            col("partner_id", "거래처", "bigint", nullable=True),
            col("side", "차대", "varchar(6)", rule="DEBIT / CREDIT"),
            money("amount", "금액"),
            cur(),
        ],
    ),
    # 31 원가
    table(
        CR,
        "원가 계산 실행",
        "cost",
        "DSN-11 F35·F36(Q5). 월 이동평균 + 생산량 배부. 확정 후 불변, 재계산은 새 버전",
        [
            col("cost_month", "원가 월", "varchar(7)", rule="'YYYY-MM'"),
            col("version", "버전", "integer"),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'draft'",
                rule="draft / confirmed / superseded",
            ),
            col(
                "labor_cost",
                "노무비 합계",
                "numeric(18,2)",
                rule="MFG_COST 노무 계정 월 합계 스냅샷",
            ),
            col(
                "overhead_cost",
                "경비 합계",
                "numeric(18,2)",
                rule="MFG_COST 경비 계정 월 합계 스냅샷",
            ),
            cur(),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        CIR,
        "재고자산 평가",
        "cost",
        "DSN-11 F35. WMS 수불을 읽은 월 이동평균 결과 스냅샷",
        [
            col("cost_run_id", "원가 계산 실행", "bigint"),
            col("item_id", "품목", "bigint"),
            col("opening_qty", "기초 수량", "numeric(18,3)"),
            money("opening_amount", "기초 금액"),
            col("in_qty", "입고 수량", "numeric(18,3)"),
            money("in_amount", "입고 금액"),
            col("out_qty", "출고 수량", "numeric(18,3)"),
            money("out_amount", "출고 금액"),
            col("unit_cost", "평균 단가", "numeric(18,4)"),
        ],
    ),
    table(
        CA,
        "제조원가 배부",
        "cost",
        "DSN-11 F36. 제품별 재료비 + 노무·경비(생산 수량 비율). 생산 수량은 MES 조회 스냅샷",
        [
            col("cost_run_id", "원가 계산 실행", "bigint"),
            col("item_id", "제품", "bigint"),
            col("produced_qty", "생산 수량", "numeric(18,3)"),
            money("material_cost", "재료비"),
            money("labor_cost", "노무비"),
            money("overhead_cost", "경비"),
            col("unit_cost", "제품 단위원가", "numeric(18,4)"),
        ],
    ),
    # 61 세무
    table(
        PTI,
        "매입 세금계산서",
        "tax",
        "DSN-11 F62(Q6). 수취 기록 + 국세청 조회 상태 흉내. 매입 전표 1건당 1건",
        [
            col("purchase_invoice_id", "매입 전표", "bigint"),
            col("partner_id", "공급처", "bigint"),
            col("approval_no", "승인번호", "varchar(60)"),
            col("issued_on", "작성일", "date"),
            cur(),
            money("supply_amount", "공급가"),
            money("tax_amount", "세액"),
            money("total_amount", "합계"),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'received'",
                rule="received / verified / mismatch / cancelled",
            ),
            col(
                "verified_at",
                "조회 확인 시각",
                "timestamptz",
                nullable=True,
                rule="합성 국세청 조회",
            ),
        ],
    ),
    table(
        VR,
        "부가세 신고 집계",
        "tax",
        "DSN-11 F63. 분기 집계, 확정 후 불변, 재집계는 새 버전. 신고 전송 없음",
        [
            col("vat_period", "신고 기간", "varchar(7)", rule="'YYYY-Qn'"),
            col("version", "버전", "integer"),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'draft'",
                rule="draft / confirmed / superseded",
            ),
            cur(),
            money("sales_supply", "매출 공급가"),
            money("sales_tax", "매출 세액"),
            money("purchase_supply", "매입 공급가"),
            money("purchase_tax", "매입 세액"),
            money(
                "payable_tax",
                "납부(환급) 세액",
                rule="매출 세액 − 매입 세액, 음수면 환급",
            ),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        VRL,
        "거래처별 합계",
        "tax",
        "DSN-11 F63. 매출·매입처별 세금계산서 합계표",
        [
            col("vat_return_id", "부가세 신고 집계", "bigint"),
            col("side", "구분", "varchar(8)", rule="SALES / PURCHASE"),
            col("partner_id", "거래처", "bigint"),
            col("business_no", "사업자번호", "varchar(12)", rule="집계 시점 스냅샷"),
            col("invoice_count", "매수", "integer"),
            money("supply_amount", "공급가"),
            money("tax_amount", "세액"),
        ],
    ),
    # 81 자금·자산
    table(
        BA,
        "계좌",
        "treasury",
        "DSN-11 F81. 계좌번호는 합성 마스킹 값만(뒤 4자리)",
        [
            col("code", "계좌 코드", "varchar(30)"),
            col("bank_name", "은행", "varchar(60)"),
            col("alias", "계좌 별칭", "varchar(100)"),
            col("masked_no", "마스킹 번호", "varchar(20)", rule="예: ***-***-1234"),
            col("account_id", "연결 계정", "bigint", rule="보통예금 등"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        BT,
        "계좌 입출금",
        "treasury",
        "DSN-11 F81. 수동 입력(은행 수집 없음). 수금·지급·전표와 연결",
        [
            col("bank_account_id", "계좌", "bigint"),
            col("txn_on", "거래일", "date"),
            col("direction", "구분", "varchar(4)", rule="IN / OUT"),
            money("amount", "금액"),
            cur(),
            col("counterparty", "거래 상대", "varchar(200)", nullable=True),
            col("memo", "적요", "varchar(300)", nullable=True),
            col("receipt_id", "수금", "bigint", nullable=True),
            col("payment_id", "지급", "bigint", nullable=True),
            col("journal_entry_id", "전표", "bigint", nullable=True),
        ],
    ),
    table(
        CC,
        "법인카드",
        "treasury",
        "DSN-11 F82. 카드번호는 뒤 4자리만",
        [
            col("code", "카드 코드", "varchar(30)"),
            col("alias", "카드 별칭", "varchar(100)"),
            col("last4", "뒤 4자리", "varchar(4)"),
            col("account_id", "미지급 계정", "bigint"),
            col("employee_id", "사용자", "bigint", nullable=True),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        CT,
        "카드 사용 내역",
        "treasury",
        "DSN-11 F82. 수동 입력 → 비용 전표(posted) 또는 제외",
        [
            col("corporate_card_id", "법인카드", "bigint"),
            col("used_on", "사용일", "date"),
            col("merchant", "가맹점", "varchar(200)"),
            cur(),
            money("supply_amount", "공급가"),
            money("tax_amount", "세액"),
            money("total_amount", "합계"),
            col("expense_account_id", "비용 계정", "bigint", nullable=True),
            col("department_id", "부서", "bigint", nullable=True),
            col("project_id", "프로젝트", "bigint", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'draft'",
                rule="draft / posted / excluded",
            ),
            col("journal_entry_id", "전표", "bigint", nullable=True),
        ],
    ),
    table(
        CPI,
        "자금 계획 항목",
        "treasury",
        "DSN-11 F83. 수동 예정 입출금. 채권·채무 만기 예정액은 조회 때 합친다",
        [
            col("expected_on", "예정일", "date"),
            col("direction", "구분", "varchar(4)", rule="IN / OUT"),
            money("amount", "금액"),
            cur(),
            col("memo", "내용", "varchar(300)"),
            col("bank_account_id", "계좌", "bigint", nullable=True),
        ],
    ),
    table(
        BU,
        "예산",
        "budget",
        "DSN-11 F84. 연 예산, 확정 후 불변, 수정 예산은 새 버전",
        [
            col("budget_year", "예산 연도", "varchar(4)", rule="'YYYY'"),
            col("version", "버전", "integer"),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'draft'",
                rule="draft / confirmed / superseded",
            ),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        BUL,
        "예산 명세",
        "budget",
        "DSN-11 F84. 부서·계정·월 단위",
        [
            col("budget_id", "예산", "bigint"),
            col("budget_month", "예산 월", "varchar(7)", rule="'YYYY-MM'"),
            col("department_id", "부서", "bigint"),
            col("account_id", "계정", "bigint"),
            money("amount", "금액"),
            cur(),
        ],
    ),
    table(
        FA,
        "고정자산",
        "asset",
        "DSN-11 F85. 정액·정률, 월 상각",
        [
            col("asset_no", "자산 번호", "varchar(40)"),
            col("name", "자산명", "varchar(200)"),
            col("acquired_on", "취득일", "date"),
            money("acquisition_cost", "취득가"),
            money("salvage_amount", "잔존가"),
            col("useful_life_months", "내용연수(월)", "integer"),
            col(
                "method",
                "상각 방법",
                "varchar(10)",
                rule="STRAIGHT 정액 / DECLINING 정률",
            ),
            col(
                "declining_rate",
                "정률",
                "numeric(7,4)",
                nullable=True,
                rule="DECLINING이면 필수",
            ),
            cur(),
            col("asset_account_id", "자산 계정", "bigint"),
            col("expense_account_id", "상각비 계정", "bigint"),
            col("accumulated_account_id", "감가상각누계액 계정", "bigint"),
            col("department_id", "사용 부서", "bigint", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'active'",
                rule="active / disposed",
            ),
            col("disposed_on", "처분일", "date", nullable=True),
        ],
    ),
    table(
        DEP,
        "감가상각",
        "asset",
        "DSN-11 F85·F57. 월 결산에서 자산·월당 1건, 전표 연결",
        [
            col("fixed_asset_id", "고정자산", "bigint"),
            col("depreciation_month", "상각 월", "varchar(7)", rule="'YYYY-MM'"),
            money("amount", "상각액"),
            cur(),
            col("journal_entry_id", "전표", "bigint", nullable=True),
        ],
    ),
]

NEW_COLUMNS = {
    E + "partner": [
        col(
            "business_no",
            "사업자번호",
            "varchar(12)",
            nullable=True,
            rule="'NNN-NN-NNNNN' 합성 값",
        ),
        col("representative", "대표자", "varchar(60)", nullable=True),
        col("business_type", "업태", "varchar(60)", nullable=True),
        col("business_item", "종목", "varchar(60)", nullable=True),
        col("address", "주소", "varchar(300)", nullable=True),
        col("phone", "연락처", "varchar(30)", nullable=True),
        col("contact_name", "담당자", "varchar(60)", nullable=True),
        col("partner_group", "거래처 그룹", "varchar(40)", nullable=True),
        col(
            "credit_limit",
            "여신 한도",
            "numeric(18,2)",
            nullable=True,
            rule="F03·F17. NULL이면 확인 안 함",
        ),
        col("credit_days", "여신 기간(일)", "integer", nullable=True),
        col("sale_price_group_id", "판매 단가 그룹", "bigint", nullable=True),
        col("purchase_price_group_id", "구매 단가 그룹", "bigint", nullable=True),
    ],
    E + "item": [
        col("spec", "규격", "varchar(100)", nullable=True),
        col(
            "standard_cost",
            "표준 원가",
            "numeric(18,4)",
            nullable=True,
            rule="원가 계산 전 참고값",
        ),
        col("standard_price", "표준 판매가", "numeric(18,4)", nullable=True),
        col(
            "track_stock",
            "재고 관리",
            "boolean",
            default="true",
            rule="false면 서비스·무형(WMS 조회 대상 아님)",
        ),
    ],
    E + "sales_order_line": [
        col("discount_amount", "할인 금액", "numeric(18,2)", default="0", rule="F18"),
    ],
    E + "purchase_invoice": [
        col(
            "invoice_kind",
            "매입 종류",
            "varchar(12)",
            default="'DIRECT'",
            rule="PO_RECEIPT 발주 입고 / DIRECT 직접 매입 / SUBCONTRACT 외주비(Q4·F34)",
        ),
        col("purchase_order_id", "발주서", "bigint", nullable=True),
        col(
            "source_ref",
            "원천 코드",
            "varchar(60)",
            nullable=True,
            rule="WMS 입고 번호·MES 외주 코드 스냅샷",
        ),
        col("department_id", "부서", "bigint", nullable=True),
        col("project_id", "프로젝트", "bigint", nullable=True),
    ],
    E + "purchase_invoice_line": [
        col("purchase_order_line_id", "발주 명세", "bigint", nullable=True),
        col(
            "expense_account_id",
            "비용 계정",
            "bigint",
            nullable=True,
            rule="직접 매입(서비스·소모품)이면 계정 지정",
        ),
    ],
    E + "receipt": [
        col("bank_account_id", "입금 계좌", "bigint", nullable=True, rule="F81")
    ],
    E + "payment": [
        col("bank_account_id", "출금 계좌", "bigint", nullable=True, rule="F81")
    ],
    E + "account": [
        col(
            "account_class",
            "계정 분류",
            "varchar(16)",
            default="'ASSET'",
            rule=" / ".join(ACCOUNT_CLASSES),
        ),
        col(
            "normal_side",
            "정상 잔액",
            "varchar(6)",
            default="'DEBIT'",
            rule="DEBIT / CREDIT",
        ),
        col("statement_group", "재무제표 표시 그룹", "varchar(40)", nullable=True),
        col("requires_partner", "거래처 필수", "boolean", default="false"),
        col("requires_department", "부서 필수", "boolean", default="false"),
        col("is_active", "사용 여부", "boolean", default="true"),
    ],
    E + "tax_invoice": [
        col(
            "transmitted_at",
            "전송 시각",
            "timestamptz",
            nullable=True,
            rule="Q6 합성 전송",
        ),
        col("transmit_message", "전송 결과", "varchar(300)", nullable=True),
        col("cancelled_at", "취소 시각", "timestamptz", nullable=True),
    ],
}

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in TABLES:
    names = {x["name"] for x in t["columns"]}
    if "currency" in names:
        CONSTRAINTS.append(c(t["name"], "CHECK", ["currency"], KRW, "KRW 고정"))
for t, field in [
    (DEPT, "code"),
    (EMP, "code"),
    (PROJ, "code"),
    (PG, "code"),
    (BA, "code"),
    (CC, "code"),
]:
    CONSTRAINTS += [
        c(t, "UK", S + [field], reason="세대 내 코드 유일"),
        c(t, "CHECK", [field], f"{field} {CODE}", "코드 형식"),
    ]
for t, field in [
    (SR, "return_no"),
    (PRQ, "request_no"),
    (PO, "po_no"),
    (PRT, "return_no"),
    (JE, "entry_no"),
    (EC, "claim_no"),
    (FA, "asset_no"),
]:
    CONSTRAINTS += [
        c(t, "UK", S + [field], reason="세대 내 번호 유일"),
        c(t, "CHECK", [field], f"length(btrim({field})) > 0", "번호 필수"),
    ]
for t in (SR, PRT, EC):
    CONSTRAINTS.append(doc_check(t))
for t in (SR, PO, PRT, PTI, CT):
    CONSTRAINTS.append(amounts_check(t))
for t, parent in [
    (SRL, "sales_return_id"),
    (POL, "purchase_order_id"),
    (PRTL, "purchase_return_id"),
]:
    CONSTRAINTS += line_checks(t, parent)
CONSTRAINTS += [
    c(
        DEPT,
        "CHECK",
        ["cost_center_kind"],
        "cost_center_kind IN ('MFG', 'SALES', 'ADMIN')",
        "원가 구분 값",
    ),
    c(
        PROJ,
        "CHECK",
        ["start_on", "end_on"],
        "end_on IS NULL OR start_on IS NULL OR end_on >= start_on",
        "기간 순서",
    ),
    c(
        PG,
        "CHECK",
        ["price_kind"],
        "price_kind IN ('SALE', 'PURCHASE')",
        "단가 구분 값",
    ),
    c(
        PGP,
        "UK",
        S + ["price_group_id", "item_id", "valid_from"],
        reason="그룹·품목·적용일당 단가 1건",
    ),
    c(PGP, "CHECK", ["unit_price"], "unit_price >= 0", "단가 음수 금지"),
    c(SR, "CHECK", ["reason"], "length(btrim(reason)) >= 2", "반품 사유"),
    c(PRT, "CHECK", ["reason"], "length(btrim(reason)) >= 2", "반품 사유"),
    c(
        PRQ,
        "CHECK",
        ["source", "source_ref"],
        "source IN ('MANUAL', 'CMMS', 'ELB') AND ((source = 'MANUAL') = (source_ref IS NULL))",
        "출처·원천 코드",
    ),
    c(
        PRQ,
        "CHECK",
        ["status"],
        "status IN ('draft', 'confirmed', 'ordered', 'cancelled')",
        "상태 값",
    ),
    c(
        PRQ,
        "CHECK",
        ["status", "cancelled_at", "cancel_reason"],
        "(status = 'cancelled') = (cancelled_at IS NOT NULL) AND (cancelled_at IS NULL OR length(btrim(cancel_reason)) > 0)",
        "취소 시각·사유",
    ),
    uk_partial(
        PRQ,
        ["source", "source_ref"],
        "source <> 'MANUAL' AND status <> 'cancelled'",
        "원천 요청 1건당 구매 요청 1건",
    ),
    c(
        PRQL,
        "UK",
        S + ["purchase_request_id", "line_no"],
        reason="문서 내 행 번호 유일",
    ),
    c(
        PRQL,
        "CHECK",
        ["line_no", "quantity"],
        "line_no >= 1 AND quantity > 0",
        "행 수량",
    ),
    c(
        PO,
        "CHECK",
        ["status"],
        "status IN ('draft', 'confirmed', 'closed', 'cancelled')",
        "상태 값",
    ),
    c(
        PO,
        "CHECK",
        ["status", "confirmed_at", "closed_at", "cancelled_at", "cancel_reason"],
        "(status = 'draft' AND confirmed_at IS NULL AND closed_at IS NULL AND cancelled_at IS NULL) OR "
        "(status = 'confirmed' AND confirmed_at IS NOT NULL AND closed_at IS NULL AND cancelled_at IS NULL) OR "
        "(status = 'closed' AND confirmed_at IS NOT NULL AND closed_at IS NOT NULL AND cancelled_at IS NULL) OR "
        "(status = 'cancelled' AND cancelled_at IS NOT NULL AND length(btrim(cancel_reason)) > 0)",
        "상태별 시각",
    ),
    c(
        PO,
        "CHECK",
        ["ordered_on", "due_on"],
        "due_on IS NULL OR due_on >= ordered_on",
        "납기 순서",
    ),
    c(
        PO,
        "SERVICE/DB_POLICY",
        ["status"],
        "입고 진행(미입고·부분·완료)은 fs.wms.interface 입고 수량을 읽어 파생. 확정 후 명세 불변, 변경은 취소 후 재발주",
        "발주 진행 파생",
    ),
    c(
        RA,
        "CHECK",
        ["adjust_kind"],
        f"adjust_kind IN ({q(ADJUST_KINDS_AR)})",
        "조정 종류 값",
    ),
    c(
        PA,
        "CHECK",
        ["adjust_kind"],
        f"adjust_kind IN ({q(ADJUST_KINDS_AP)})",
        "조정 종류 값",
    ),
    c(RA, "UK", S + ["apply_key"], reason="조정 재요청 중복 차단"),
    c(PA, "UK", S + ["apply_key"], reason="조정 재요청 중복 차단"),
    c(RA, "CHECK", ["amount"], "amount > 0", "조정 금액 양수"),
    c(PA, "CHECK", ["amount"], "amount > 0", "조정 금액 양수"),
    c(
        RA,
        "CHECK",
        ["adjust_kind", "offset_no", "source_id"],
        "(adjust_kind = 'OFFSET') = (offset_no IS NOT NULL) AND (adjust_kind = 'RETURN_CREDIT') = (source_id IS NOT NULL)",
        "종류별 연결",
    ),
    c(
        PA,
        "CHECK",
        ["adjust_kind", "offset_no", "source_id"],
        "(adjust_kind = 'OFFSET') = (offset_no IS NOT NULL) AND (adjust_kind = 'RETURN_CREDIT') = (source_id IS NOT NULL)",
        "종류별 연결",
    ),
    c(
        RA,
        "SERVICE/DB_POLICY",
        ["amount"],
        "조정 합 + 수금 소명 합 ≤ 채권 원금(잠금 순서: 채권 → 조정). 조정은 확정 전표와 같은 트랜잭션. 정정은 반대 조정이 아니라 원천 문서 취소로",
        "채권 조정 한도",
    ),
    c(
        PA,
        "SERVICE/DB_POLICY",
        ["amount"],
        "조정 합 + 지급 소명 합 ≤ 채무 원금. 상계는 같은 offset_no로 채권 조정과 한 트랜잭션, 같은 거래처·같은 금액",
        "채무 조정 한도·상계 쌍",
    ),
    c(JE, "CHECK", ["entry_kind"], f"entry_kind IN ({q(ENTRY_KINDS)})", "전표 종류 값"),
    c(
        JE,
        "CHECK",
        ["status"],
        "status IN ('draft', 'confirmed', 'reversed')",
        "상태 값",
    ),
    c(
        JE,
        "CHECK",
        ["status", "confirmed_at"],
        "(status = 'draft') = (confirmed_at IS NULL)",
        "확정 시각",
    ),
    c(
        JE,
        "CHECK",
        ["entry_kind", "reversal_of_id"],
        "(entry_kind = 'REVERSAL') = (reversal_of_id IS NOT NULL)",
        "역분개 대상",
    ),
    c(
        JE,
        "CHECK",
        ["source_kind", "source_id"],
        "(source_kind IS NULL) = (source_id IS NULL)",
        "원천 종류·id 짝",
    ),
    uk_partial(
        JE,
        ["source_kind", "source_id"],
        "source_id IS NOT NULL AND status <> 'reversed' AND entry_kind <> 'REVERSAL'",
        "원천 문서 1건당 살아 있는 자동 전표 1건(Q3)",
    ),
    uk_partial(
        JE,
        ["entry_kind", "source_ref"],
        "source_ref IS NOT NULL AND status <> 'reversed' AND entry_kind <> 'REVERSAL'",
        "외부 원천(급여·외주) 1건당 전표 1건",
    ),
    uk_partial(
        JE, ["reversal_of_id"], "reversal_of_id IS NOT NULL", "원 전표당 역분개 1건"
    ),
    c(
        JE,
        "SERVICE/DB_POLICY",
        ["status"],
        "확정 시 차변 합 = 대변 합 > 0, 라인 2개 이상, 계정의 거래처·부서 필수 충족, 회계 월 open. 확정 후 전표·라인 불변. 정정은 REVERSAL 새 전표(원 전표 status=reversed)",
        "전표 확정·불변(F45)",
    ),
    c(
        JE,
        "SERVICE/DB_POLICY",
        ["source_kind", "source_id"],
        "업무 확정과 같은 트랜잭션에서 posting_rule로 자동 생성(즉시). 규칙 누락·회계 월 마감이면 업무는 확정되고 전표만 미생성 → 회계 미반영 현황(F44)에서 일괄 반영",
        "자동 전표 즉시 + 일괄(Q3)",
    ),
    c(JL, "UK", S + ["journal_entry_id", "line_no"], reason="전표 내 행 번호 유일"),
    c(JL, "CHECK", ["side"], "side IN ('DEBIT', 'CREDIT')", "차대 값"),
    c(
        JL,
        "CHECK",
        ["line_no", "amount"],
        "line_no >= 1 AND amount > 0",
        "행 금액 양수",
    ),
    c(
        EC,
        "CHECK",
        ["pay_method"],
        "pay_method IN ('BANK', 'CARD', 'CASH')",
        "지급 방법 값",
    ),
    c(EC, "CHECK", ["total_amount"], "total_amount > 0", "합계 양수"),
    c(
        EC,
        "SERVICE/DB_POLICY",
        ["status"],
        "확정 시 합계 = 명세 합, 비용 전표(EXPENSE_CLAIM) 생성. GW 결재 상태는 fs.gw.interface로 읽어 배지만 표시",
        "지출결의 확정",
    ),
    c(ECL, "UK", S + ["expense_claim_id", "line_no"], reason="문서 내 행 번호 유일"),
    c(
        ECL,
        "CHECK",
        ["line_no", "amount"],
        "line_no >= 1 AND amount > 0",
        "행 금액 양수",
    ),
    c(FP, "UK", S + ["period_month"], reason="회계 월 1건"),
    c(FP, "CHECK", ["period_month"], f"period_month {MONTH}", "'YYYY-MM' 형식"),
    c(
        FP,
        "CHECK",
        ["status", "closed_at"],
        "status IN ('open', 'closed') AND ((status = 'closed') = (closed_at IS NOT NULL))",
        "마감 상태",
    ),
    c(
        FP,
        "SERVICE/DB_POLICY",
        ["status"],
        "마감 순서: 감가상각 → 원가 계산 확정 → 매출원가(COGS) 전표 → 마감. 마감 월 전표 입력·확정·역분개 금지. 마감 해제는 다음 월이 open일 때만",
        "월 마감(F57)",
    ),
    c(
        OB,
        "UK",
        S + ["fiscal_year", "account_id", "partner_id"],
        reason="연도·계정·거래처당 1건(거래처 없는 행은 SERVICE)",
    ),
    c(OB, "CHECK", ["fiscal_year"], f"fiscal_year {YEAR}", "'YYYY' 형식"),
    c(
        OB,
        "CHECK",
        ["side", "amount"],
        "side IN ('DEBIT', 'CREDIT') AND amount >= 0",
        "차대·금액",
    ),
    uk_partial(
        OB,
        ["fiscal_year", "account_id"],
        "partner_id IS NULL",
        "거래처 없는 기초 잔액 1건",
    ),
    c(CR, "UK", S + ["cost_month", "version"], reason="월·버전 유일"),
    c(CR, "CHECK", ["cost_month"], f"cost_month {MONTH}", "'YYYY-MM' 형식"),
    c(
        CR,
        "CHECK",
        ["status", "version"],
        "status IN ('draft', 'confirmed', 'superseded') AND version >= 1",
        "상태·버전",
    ),
    c(
        CR,
        "CHECK",
        ["labor_cost", "overhead_cost"],
        "labor_cost >= 0 AND overhead_cost >= 0",
        "배부 원가 음수 금지",
    ),
    uk_partial(CR, ["cost_month"], "status = 'confirmed'", "월당 확정 원가 1건"),
    c(
        CR,
        "SERVICE/DB_POLICY",
        ["status"],
        "확정 후 불변. 재계산은 새 버전 확정 시 이전 confirmed→superseded. 재료비는 fs.wms.interface 수불, 생산 수량은 fs.mes.interface 실적을 읽어 스냅샷(꺼져 있으면 계산 거부)",
        "원가 확정·재계산(Q5)",
    ),
    c(CIR, "UK", S + ["cost_run_id", "item_id"], reason="실행·품목당 1건"),
    c(
        CIR,
        "CHECK",
        ["opening_qty", "in_qty", "out_qty", "unit_cost"],
        "opening_qty >= 0 AND in_qty >= 0 AND out_qty >= 0 AND unit_cost >= 0",
        "수량·단가 음수 금지",
    ),
    c(CA, "UK", S + ["cost_run_id", "item_id"], reason="실행·제품당 1건"),
    c(
        CA,
        "CHECK",
        ["produced_qty", "material_cost", "labor_cost", "overhead_cost", "unit_cost"],
        "produced_qty > 0 AND material_cost >= 0 AND labor_cost >= 0 AND overhead_cost >= 0 AND unit_cost >= 0",
        "배부 값",
    ),
    c(PTI, "UK", S + ["purchase_invoice_id"], reason="매입 전표당 세금계산서 1건"),
    c(PTI, "UK", S + ["approval_no"], reason="승인번호 유일"),
    c(
        PTI,
        "CHECK",
        ["status", "verified_at"],
        "status IN ('received', 'verified', 'mismatch', 'cancelled') AND ((status IN ('verified', 'mismatch')) = (verified_at IS NOT NULL))",
        "조회 상태",
    ),
    c(VR, "UK", S + ["vat_period", "version"], reason="기간·버전 유일"),
    c(
        VR,
        "CHECK",
        ["vat_period"],
        "vat_period ~ '^[0-9]{4}-Q[1-4]$'",
        "'YYYY-Qn' 형식",
    ),
    c(
        VR,
        "CHECK",
        ["status", "version"],
        "status IN ('draft', 'confirmed', 'superseded') AND version >= 1",
        "상태·버전",
    ),
    c(
        VR,
        "CHECK",
        ["payable_tax", "sales_tax", "purchase_tax"],
        "payable_tax = sales_tax - purchase_tax",
        "납부 세액",
    ),
    uk_partial(VR, ["vat_period"], "status = 'confirmed'", "기간당 확정 집계 1건"),
    c(
        VRL,
        "UK",
        S + ["vat_return_id", "side", "partner_id"],
        reason="집계·구분·거래처당 1행",
    ),
    c(
        VRL,
        "CHECK",
        ["side", "invoice_count"],
        "side IN ('SALES', 'PURCHASE') AND invoice_count >= 1",
        "구분·매수",
    ),
    c(
        BT,
        "CHECK",
        ["direction", "amount"],
        "direction IN ('IN', 'OUT') AND amount > 0",
        "방향·금액",
    ),
    c(
        BT,
        "CHECK",
        ["direction", "receipt_id", "payment_id"],
        "NOT (receipt_id IS NOT NULL AND payment_id IS NOT NULL) AND (receipt_id IS NULL OR direction = 'IN') AND (payment_id IS NULL OR direction = 'OUT')",
        "수금은 입금·지급은 출금",
    ),
    c(CC, "CHECK", ["last4"], "last4 ~ '^[0-9]{4}$'", "뒤 4자리"),
    c(
        CT,
        "CHECK",
        ["status", "journal_entry_id"],
        "status IN ('draft', 'posted', 'excluded') AND ((status = 'posted') = (journal_entry_id IS NOT NULL))",
        "전표 반영 상태",
    ),
    c(
        CPI,
        "CHECK",
        ["direction", "amount"],
        "direction IN ('IN', 'OUT') AND amount > 0",
        "방향·금액",
    ),
    c(BU, "UK", S + ["budget_year", "version"], reason="연도·버전 유일"),
    c(BU, "CHECK", ["budget_year"], f"budget_year {YEAR}", "'YYYY' 형식"),
    c(
        BU,
        "CHECK",
        ["status", "version"],
        "status IN ('draft', 'confirmed', 'superseded') AND version >= 1",
        "상태·버전",
    ),
    uk_partial(BU, ["budget_year"], "status = 'confirmed'", "연도당 확정 예산 1건"),
    c(
        BUL,
        "UK",
        S + ["budget_id", "budget_month", "department_id", "account_id"],
        reason="예산·월·부서·계정당 1행",
    ),
    c(BUL, "CHECK", ["budget_month"], f"budget_month {MONTH}", "'YYYY-MM' 형식"),
    c(BUL, "CHECK", ["amount"], "amount >= 0", "금액 음수 금지"),
    c(
        FA,
        "CHECK",
        ["method", "declining_rate"],
        "method IN ('STRAIGHT', 'DECLINING') AND ((method = 'DECLINING') = (declining_rate IS NOT NULL)) AND (declining_rate IS NULL OR declining_rate > 0 AND declining_rate < 1)",
        "상각 방법·정률",
    ),
    c(
        FA,
        "CHECK",
        ["acquisition_cost", "salvage_amount", "useful_life_months"],
        "acquisition_cost > 0 AND salvage_amount >= 0 AND salvage_amount < acquisition_cost AND useful_life_months BETWEEN 1 AND 600",
        "취득가·잔존가·내용연수",
    ),
    c(
        FA,
        "CHECK",
        ["status", "disposed_on", "acquired_on"],
        "status IN ('active', 'disposed') AND ((status = 'disposed') = (disposed_on IS NOT NULL)) AND (disposed_on IS NULL OR disposed_on >= acquired_on)",
        "처분 상태",
    ),
    c(
        DEP,
        "UK",
        S + ["fixed_asset_id", "depreciation_month"],
        reason="자산·월당 상각 1건",
    ),
    c(
        DEP,
        "CHECK",
        ["depreciation_month"],
        f"depreciation_month {MONTH}",
        "'YYYY-MM' 형식",
    ),
    c(DEP, "CHECK", ["amount"], "amount >= 0", "상각액 음수 금지"),
    c(
        DEP,
        "SERVICE/DB_POLICY",
        ["amount"],
        "누계 상각 ≤ 취득가 − 잔존가. 마지막 달에 끝수 조정. 월 마감에서 DEPRECIATION 전표와 함께 생성",
        "상각 한도",
    ),
]
for t, cols_ in [
    (SRL, ["sales_return_id"]),
    (POL, ["purchase_order_id"]),
    (PRTL, ["purchase_return_id"]),
    (JL, ["journal_entry_id"]),
    (JL, ["account_id"]),
    (JE, ["entry_date"]),
    (JE, ["status", "entry_date"]),
    (PO, ["partner_id", "status"]),
    (RA, ["receivable_id"]),
    (PA, ["payable_id"]),
    (BT, ["bank_account_id", "txn_on"]),
    (CT, ["corporate_card_id", "used_on"]),
    (CIR, ["cost_run_id"]),
    (CA, ["cost_run_id"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="FK·목록 조회"))

# 기존 테이블 변경 — 제약
CHANGED_CONSTRAINTS = [
    c(
        E + "partner",
        "CHECK",
        ["credit_limit", "credit_days"],
        "(credit_limit IS NULL OR credit_limit >= 0) AND (credit_days IS NULL OR credit_days >= 0)",
        "여신 음수 금지",
    ),
    c(
        E + "partner",
        "CHECK",
        ["business_no"],
        "business_no IS NULL OR business_no ~ '^[0-9]{3}-[0-9]{2}-[0-9]{5}$'",
        "사업자번호 형식",
    ),
    c(
        E + "item",
        "CHECK",
        ["standard_cost", "standard_price"],
        "(standard_cost IS NULL OR standard_cost >= 0) AND (standard_price IS NULL OR standard_price >= 0)",
        "표준 단가 음수 금지",
    ),
    c(
        E + "sales_order_line",
        "CHECK",
        ["discount_amount"],
        "discount_amount >= 0",
        "할인 음수 금지",
    ),
    c(
        E + "purchase_invoice",
        "CHECK",
        ["invoice_kind"],
        "invoice_kind IN ('PO_RECEIPT', 'DIRECT', 'SUBCONTRACT')",
        "매입 종류 값",
    ),
    c(
        E + "purchase_invoice",
        "CHECK",
        ["invoice_kind", "purchase_order_id", "source_ref"],
        "((invoice_kind = 'PO_RECEIPT') = (purchase_order_id IS NOT NULL)) AND (invoice_kind = 'DIRECT' OR source_ref IS NOT NULL)",
        "종류별 발주·원천",
    ),
    uk_partial(
        E + "purchase_invoice",
        ["invoice_kind", "source_ref"],
        "source_ref IS NOT NULL AND status <> 'cancelled'",
        "입고·외주 원천 1건당 매입 1건(Q4)",
    ),
    c(
        E + "purchase_invoice",
        "SERVICE/DB_POLICY",
        ["invoice_kind"],
        "PO_RECEIPT는 fs.wms.interface 입고 확정분을 읽어 생성(발주 단가). DIRECT는 지금처럼 직접 입력. SUBCONTRACT는 fs.mes.interface 외주 실적 코드",
        "매입 경로 둘 다 허용(Q4)",
    ),
    c(
        E + "account",
        "CHECK",
        ["account_code"],
        f"account_code {CODE}",
        "계정 코드 형식(DSN-11: 고정 7개 해제)",
    ),
    c(
        E + "account",
        "CHECK",
        ["account_class", "normal_side"],
        f"account_class IN ({q(ACCOUNT_CLASSES)}) AND normal_side IN ('DEBIT', 'CREDIT')",
        "계정 분류·정상 잔액",
    ),
    c(
        E + "posting_rule",
        "CHECK",
        ["transaction_kind"],
        f"transaction_kind IN ({q(POSTING_KINDS)})",
        "자동 전표 종류(DSN-11)",
    ),
    c(
        E + "posting_rule",
        "CHECK",
        ["entry_side", "amount_basis", "line_no"],
        f"entry_side IN ('DEBIT', 'CREDIT') AND amount_basis IN ({q(AMOUNT_BASES)}) AND line_no >= 1",
        "규칙 값",
    ),
    c(
        E + "tax_invoice",
        "CHECK",
        ["status", "approval_no", "issued_on", "transmitted_at", "cancelled_at"],
        "(status = 'pending' AND approval_no IS NULL AND issued_on IS NULL AND transmitted_at IS NULL AND cancelled_at IS NULL) OR "
        "(status IN ('issued', 'transmitting', 'failed') AND approval_no IS NOT NULL AND issued_on IS NOT NULL AND transmitted_at IS NULL AND cancelled_at IS NULL) OR "
        "(status = 'transmitted' AND approval_no IS NOT NULL AND issued_on IS NOT NULL AND transmitted_at IS NOT NULL AND cancelled_at IS NULL) OR "
        "(status = 'cancelled' AND approval_no IS NOT NULL AND cancelled_at IS NOT NULL)",
        "진행 단계별 값(Q6)",
    ),
]
REMOVED_CHECK_PREFIXES = {
    E + "account": "(account_code = 'AR'",
    E + "posting_rule": "(transaction_kind = 'SALE'",
    E + "tax_invoice": "(status = 'pending'",
}

RELATIONS = [
    dict(
        source=t["name"],
        columns=S,
        target="core.data_generation",
        target_columns=["workspace_id", "id"],
        on_delete="RESTRICT",
        on_update="RESTRICT",
        note="같은 참조 범위 유지",
    )
    for t in TABLES
]
RELATIONS += [
    r(EMP, ["department_id"], DEPT, "담당자 부서"),
    r(PGP, ["price_group_id"], PG, "단가 그룹"),
    r(PGP, ["item_id"], E + "item", "단가 품목"),
    r(SR, ["partner_id"], E + "partner", "반품 거래처"),
    r(SR, ["sales_record_id"], E + "sales_record", "원 매출"),
    r(SRL, ["sales_return_id"], SR, "반품 소속"),
    r(SRL, ["item_id"], E + "item", "반품 품목"),
    r(PRQ, ["department_id"], DEPT, "요청 부서"),
    r(PRQ, ["employee_id"], EMP, "요청자"),
    r(PRQL, ["purchase_request_id"], PRQ, "요청 소속"),
    r(PRQL, ["item_id"], E + "item", "요청 품목"),
    r(PO, ["partner_id"], E + "partner", "공급처"),
    r(PO, ["department_id"], DEPT, "발주 부서"),
    r(PO, ["project_id"], PROJ, "발주 프로젝트"),
    r(POL, ["purchase_order_id"], PO, "발주 소속"),
    r(POL, ["item_id"], E + "item", "발주 품목"),
    r(POL, ["purchase_request_line_id"], PRQL, "원 구매 요청 명세"),
    r(PRT, ["partner_id"], E + "partner", "반품 공급처"),
    r(PRT, ["purchase_invoice_id"], E + "purchase_invoice", "원 매입"),
    r(PRTL, ["purchase_return_id"], PRT, "반품 소속"),
    r(PRTL, ["item_id"], E + "item", "반품 품목"),
    r(RA, ["receivable_id"], E + "receivable", "조정 대상 채권"),
    r(RA, ["partner_id"], E + "partner", "조정 거래처"),
    r(PA, ["payable_id"], E + "payable", "조정 대상 채무"),
    r(PA, ["partner_id"], E + "partner", "조정 거래처"),
    r(JE, ["department_id"], DEPT, "전표 부서"),
    r(JE, ["employee_id"], EMP, "작성 담당자"),
    r(JE, ["reversal_of_id"], JE, "역분개 원 전표"),
    r(JL, ["journal_entry_id"], JE, "전표 소속"),
    r(JL, ["account_id"], E + "account", "라인 계정"),
    r(JL, ["partner_id"], E + "partner", "라인 거래처"),
    r(JL, ["department_id"], DEPT, "라인 부서"),
    r(JL, ["project_id"], PROJ, "라인 프로젝트"),
    r(EC, ["employee_id"], EMP, "청구자"),
    r(EC, ["department_id"], DEPT, "결의 부서"),
    r(ECL, ["expense_claim_id"], EC, "결의 소속"),
    r(ECL, ["account_id"], E + "account", "비용 계정"),
    r(ECL, ["project_id"], PROJ, "프로젝트"),
    r(OB, ["account_id"], E + "account", "기초 계정"),
    r(OB, ["partner_id"], E + "partner", "기초 거래처"),
    r(CIR, ["cost_run_id"], CR, "평가 소속"),
    r(CIR, ["item_id"], E + "item", "평가 품목"),
    r(CA, ["cost_run_id"], CR, "배부 소속"),
    r(CA, ["item_id"], E + "item", "배부 제품"),
    r(PTI, ["purchase_invoice_id"], E + "purchase_invoice", "매입 전표"),
    r(PTI, ["partner_id"], E + "partner", "공급처"),
    r(VRL, ["vat_return_id"], VR, "집계 소속"),
    r(VRL, ["partner_id"], E + "partner", "거래처"),
    r(BA, ["account_id"], E + "account", "계좌 계정"),
    r(BT, ["bank_account_id"], BA, "계좌"),
    r(BT, ["receipt_id"], E + "receipt", "연결 수금"),
    r(BT, ["payment_id"], E + "payment", "연결 지급"),
    r(BT, ["journal_entry_id"], JE, "연결 전표"),
    r(CC, ["account_id"], E + "account", "카드 미지급 계정"),
    r(CC, ["employee_id"], EMP, "카드 사용자"),
    r(CT, ["corporate_card_id"], CC, "카드"),
    r(CT, ["expense_account_id"], E + "account", "비용 계정"),
    r(CT, ["department_id"], DEPT, "부서"),
    r(CT, ["project_id"], PROJ, "프로젝트"),
    r(CT, ["journal_entry_id"], JE, "전표"),
    r(CPI, ["bank_account_id"], BA, "계좌"),
    r(BUL, ["budget_id"], BU, "예산 소속"),
    r(BUL, ["department_id"], DEPT, "부서"),
    r(BUL, ["account_id"], E + "account", "계정"),
    r(FA, ["asset_account_id"], E + "account", "자산 계정"),
    r(FA, ["expense_account_id"], E + "account", "상각비 계정"),
    r(FA, ["accumulated_account_id"], E + "account", "누계액 계정"),
    r(FA, ["department_id"], DEPT, "사용 부서"),
    r(DEP, ["fixed_asset_id"], FA, "자산"),
    r(DEP, ["journal_entry_id"], JE, "상각 전표"),
    # 기존 테이블의 새 컬럼
    r(E + "partner", ["sale_price_group_id"], PG, "판매 단가 그룹"),
    r(E + "partner", ["purchase_price_group_id"], PG, "구매 단가 그룹"),
    r(E + "purchase_invoice", ["purchase_order_id"], PO, "발주 입고 매입의 발주"),
    r(E + "purchase_invoice", ["department_id"], DEPT, "매입 부서"),
    r(E + "purchase_invoice", ["project_id"], PROJ, "매입 프로젝트"),
    r(E + "purchase_invoice_line", ["purchase_order_line_id"], POL, "발주 명세"),
    r(
        E + "purchase_invoice_line",
        ["expense_account_id"],
        E + "account",
        "직접 매입 비용 계정",
    ),
    r(E + "receipt", ["bank_account_id"], BA, "입금 계좌"),
    r(E + "payment", ["bank_account_id"], BA, "출금 계좌"),
]


def st(t, values, default, transition, column="status"):
    return dict(
        table=t,
        column=column,
        values=list(values),
        default=default,
        transition=transition,
    )


STATES = [
    st(
        SR,
        DOC,
        "draft",
        "draft→confirmed(매출 차감 전표·채권 조정)→cancelled(역분개); draft→cancelled",
    ),
    st(
        PRT, DOC, "draft", "draft→confirmed(매입 차감 전표·채무 조정)→cancelled(역분개)"
    ),
    st(
        PRQ,
        ("draft", "confirmed", "ordered", "cancelled"),
        "draft",
        "draft→confirmed→ordered(발주 생성 시); 발주 전 cancelled",
    ),
    st(
        PO,
        ("draft", "confirmed", "closed", "cancelled"),
        "draft",
        "draft→confirmed→closed(입고 완료·수동 종결); 입고 전 cancelled",
    ),
    st(
        JE,
        ("draft", "confirmed", "reversed"),
        "draft",
        "draft→confirmed→reversed(역분개 생성 시); 확정 후 불변",
    ),
    st(EC, DOC, "draft", "draft→confirmed(비용 전표)→cancelled(역분개)"),
    st(
        FP,
        ("open", "closed"),
        "open",
        "open→closed(마감 순서 SERVICE)→open(다음 월 open일 때만)",
    ),
    st(
        CR,
        ("draft", "confirmed", "superseded"),
        "draft",
        "draft→confirmed→superseded(새 버전 확정 시)",
    ),
    st(VR, ("draft", "confirmed", "superseded"), "draft", "draft→confirmed→superseded"),
    st(BU, ("draft", "confirmed", "superseded"), "draft", "draft→confirmed→superseded"),
    st(
        PTI,
        ("received", "verified", "mismatch", "cancelled"),
        "received",
        "received→verified/mismatch(합성 국세청 조회)→cancelled",
    ),
    st(
        CT, ("draft", "posted", "excluded"), "draft", "draft→posted(비용 전표)/excluded"
    ),
    st(FA, ("active", "disposed"), "active", "active→disposed"),
]
TAX_STATE = st(
    E + "tax_invoice",
    TAX_STATES,
    "pending",
    "pending→issued→transmitting→transmitted/failed(합성 전송, Q6); failed→transmitting 재시도; issued·transmitted→cancelled(수정 세금계산서는 새 발급)",
)

CODE_LISTS = [
    dict(
        target=JE,
        column="entry_kind",
        values=list(ENTRY_KINDS),
        default=None,
        note="일반·자동(매출·반품·매입·외주·수금·지급·조정·지출결의·카드·급여·상각·매출원가)·결산·역분개",
    ),
    dict(
        target=RA,
        column="adjust_kind",
        values=list(ADJUST_KINDS_AR),
        default=None,
        note="반품 대변 / 상계 / 대손",
    ),
    dict(
        target=PA,
        column="adjust_kind",
        values=list(ADJUST_KINDS_AP),
        default=None,
        note="반품 대변 / 상계",
    ),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn11은 schema-target.json에만 적용한다")
    if JE in {t["name"] for t in d["tables"]}:
        return False
    tables = {t["name"]: t for t in d["tables"]}
    for name, columns in NEW_COLUMNS.items():
        cols = tables[name]["columns"]
        at = len(cols) - 1 if cols[-1]["name"] == "created_at" else len(cols)
        cols[at:at] = columns
    d["constraints"] = [
        x
        for x in d["constraints"]
        if not (
            x["kind"] == "CHECK"
            and x["table"] in REMOVED_CHECK_PREFIXES
            and x["expression"].startswith(REMOVED_CHECK_PREFIXES[x["table"]])
        )
    ]
    for x in d["constraints"]:
        if (
            x["table"] == E + "partner"
            and x["kind"] == "CHECK"
            and x["expression"] == "partner_kind IN ('CUSTOMER','SUPPLIER')"
        ):
            x["expression"] = "partner_kind IN ('CUSTOMER','SUPPLIER','BOTH')"
        if (
            x["table"] == E + "item"
            and x["kind"] == "CHECK"
            and x["expression"]
            == "item_type IN ('finished','semi_finished','raw','auxiliary')"
        ):
            x["expression"] = (
                "item_type IN ('finished','semi_finished','raw','auxiliary','merchandise','intangible')"
            )
        if x["table"] == E + "account" and x["kind"] == "SERVICE/DB_POLICY":
            x["expression"] = (
                "DSN-11: 계정은 사용자가 추가·사용중단(삭제 없음). 시드는 표준 계정표(분류별)로 공급. 전표에 쓰인 계정의 분류·정상 잔액은 바꾸지 않는다"
            )
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS + CHANGED_CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"] = (
        [s for s in d["states"] if s["table"] != E + "tax_invoice"]
        + STATES
        + [TAX_STATE]
    )
    for code in d["code_lists"]:
        if code["target"] == E + "account" and code["column"] == "account_code":
            code.update(
                values=[
                    "AR",
                    "PRODUCT_SALES",
                    "VAT_PAYABLE",
                    "BANK",
                    "RAW_MATERIAL",
                    "VAT_RECEIVABLE",
                    "AP",
                ],
                note="DSN-11: 기존 7개는 시드 표준 계정표에 그대로 포함. 계정은 고정 목록이 아니다",
            )
        if (
            code["target"] == E + "posting_rule"
            and code["column"] == "transaction_kind"
        ):
            code["values"] = list(POSTING_KINDS)
    d["code_lists"].extend(CODE_LISTS)
    d.update(version="target-0.2.0", task="DSN-11", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.2.0",
            task="DSN-11",
            date="2026-10-05",
            change="ERP 보강: 새 테이블 36(기초 5·영업 반품 2·구매 6·채권채무 조정 2·회계 6·원가 3·세무 3·자금/예산/자산 9), 기존 10테이블 변경(거래처·품목·수주 명세·매입·매입 명세·수금·지급·계정·분개 규칙·세금계산서). 계정 7개·분개 10조합 고정 해제",
            status="설계 전용",
        )
    )
    return True


def main():
    d = json.loads(TARGET.read_text(encoding="utf-8"))
    changed = apply(d)
    if changed:
        TARGET.write_text(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    erp = [t for t in d["tables"] if t["name"].startswith(E)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                erp_tables=len(erp),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
