"""DSN-27: ELB/MRO(신규) 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn26 다음).

근거: docs/modules/elb/ELB_설계_DSN-27.md 4장(elb 11테이블 + 모듈 키 'elb'), 결정 Q1~Q7.
Q1: ELB 자체 발주 없음 — 승인 신청을 ERP가 구매 요청(출처 ELB)으로 가져감. 긴급 구매는 ERP 카드 내역에 연결(구매 요청 아님).
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
E = "elb."
MODULE_TABLES = {"core.workspace_module", "core.app_review"}
REQ_STATES = ("DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "WITHDRAWN")


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-27"}


CA, CI, CP, SS, SSI, AR, RQ, RL, AP, RC, RCL = (
    E + "category",
    E + "catalog_item",
    E + "contract_price",
    E + "standard_set",
    E + "standard_set_item",
    E + "approval_rule",
    E + "request",
    E + "request_line",
    E + "approval",
    E + "receipt",
    E + "receipt_line",
)

TABLES = [
    table(
        CA,
        "분류",
        "catalog",
        "DSN-27 F02. 사무·소모품·공구·안전·청소·IT 등",
        [
            col("code", "분류 코드", "varchar(30)"),
            col("name", "분류명", "varchar(100)"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        CI,
        "카탈로그 품목",
        "catalog",
        "DSN-27 F01. 재고 품목은 WMS 품목 코드 연결(입고는 WMS), 비재고는 비용 계정 코드(ERP 스냅샷)",
        [
            col("code", "품목 코드", "varchar(30)"),
            col("name", "품목명", "varchar(200)"),
            col("spec", "규격", "varchar(200)", nullable=True),
            col("category_id", "분류", "bigint"),
            col("unit", "단위", "varchar(10)"),
            col("is_stock", "재고 품목", "boolean", default="false"),
            col("wms_item_code", "WMS 품목 코드", "varchar(40)", nullable=True),
            col(
                "expense_account_code",
                "비용 계정 코드",
                "varchar(30)",
                nullable=True,
                rule="ERP 계정 코드 스냅샷(비재고)",
            ),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        CP,
        "계약 단가",
        "catalog",
        "DSN-27 F03(Q5). 공급처·단가·최소 수량·유효기간(ERP 거래처 코드 스냅샷)",
        [
            col("catalog_item_id", "카탈로그 품목", "bigint"),
            col("partner_code", "공급처 코드", "varchar(40)"),
            col("unit_price", "계약 단가", "numeric(18,4)"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col("min_qty", "최소 수량", "numeric(18,3)", default="1"),
            col("valid_from", "시작일", "date"),
            col("valid_until", "종료일", "date", nullable=True),
        ],
    ),
    table(
        SS,
        "표준 세트",
        "catalog",
        "DSN-27 F04(Q5). 부서 정기 소모품 묶음 — 한 번에 장바구니로",
        [
            col("code", "세트 코드", "varchar(30)"),
            col("name", "세트명", "varchar(100)"),
            col(
                "department_code",
                "부서 코드",
                "varchar(30)",
                nullable=True,
                rule="ERP 부서 코드 스냅샷, NULL이면 공용",
            ),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        SSI,
        "표준 세트 품목",
        "catalog",
        "DSN-27 F04",
        [
            col("standard_set_id", "표준 세트", "bigint"),
            col("catalog_item_id", "카탈로그 품목", "bigint"),
            col("qty", "수량", "numeric(18,3)"),
        ],
    ),
    table(
        AR,
        "승인 규칙",
        "approval",
        "DSN-27 F12(Q2). 단계·기준 금액·승인 역할. 신청 금액 ≥ 기준이면 그 단계 필요",
        [
            col("step", "단계", "integer"),
            col("min_amount", "기준 금액", "numeric(18,2)", rule="1단계는 0"),
            col(
                "approver_role",
                "승인 역할",
                "varchar(12)",
                rule="DEPT_HEAD 부서장 / ADMIN_DEPT 관리부서",
            ),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        RQ,
        "신청서",
        "request",
        "DSN-27 F11~F15·F23(Q2·Q3·Q6). 일반(승인 → ERP 구매 요청) / 긴급(카드 사후 등록 → ERP 카드 내역 연결)",
        [
            col("request_no", "신청 번호", "varchar(40)"),
            col(
                "kind",
                "구분",
                "varchar(10)",
                default="'NORMAL'",
                rule="NORMAL / EMERGENCY",
            ),
            col(
                "department_code",
                "부서 코드",
                "varchar(30)",
                rule="ERP 부서 코드 스냅샷",
            ),
            col("requester_name", "신청자", "varchar(60)"),
            col("reason", "사유", "varchar(500)"),
            col("needed_on", "희망일", "date", nullable=True),
            col("total_amount", "합계", "numeric(18,2)"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'DRAFT'",
                rule=" / ".join(REQ_STATES),
            ),
            col("submitted_at", "제출 시각", "timestamptz", nullable=True),
            col("decided_at", "최종 결정 시각", "timestamptz", nullable=True),
            col("reject_reason", "반려 사유", "varchar(300)", nullable=True),
            col(
                "card_txn_ref",
                "ERP 카드 내역",
                "varchar(40)",
                nullable=True,
                rule="긴급 구매만, ERP 카드 사용 내역 id 스냅샷",
            ),
            col(
                "budget_note",
                "예산 확인 결과",
                "varchar(300)",
                nullable=True,
                rule="제출 시 ERP 예산 대비 스냅샷(경고만)",
            ),
        ],
    ),
    table(
        RL,
        "신청 품목",
        "request",
        "DSN-27 F11·F22. 단가는 계약 단가 스냅샷, 공급처별로 ERP 구매 요청을 묶는다",
        [
            col("request_id", "신청서", "bigint"),
            col("line_no", "행 번호", "integer"),
            col("catalog_item_id", "카탈로그 품목", "bigint"),
            col("qty", "수량", "numeric(18,3)"),
            col("unit_price", "단가", "numeric(18,4)"),
            col("amount", "금액", "numeric(18,2)"),
            col("partner_code", "공급처 코드", "varchar(40)", nullable=True),
        ],
    ),
    table(
        AP,
        "승인",
        "approval",
        "DSN-27 F12·F13. 신청서·단계당 1건(승인/반려). 반려되면 재신청은 새 신청서",
        [
            col("request_id", "신청서", "bigint"),
            col("step", "단계", "integer"),
            col("approver_name", "승인자", "varchar(60)"),
            col("decision", "결정", "varchar(8)", rule="APPROVED / REJECTED"),
            col("decided_at", "결정 시각", "timestamptz"),
            col("comment", "의견", "varchar(300)", nullable=True),
        ],
    ),
    table(
        RC,
        "수령",
        "receipt",
        "DSN-27 F31·F33(Q4). 비재고 품목 부서 수령 확인. ERP가 읽어 매입 근거(재고 품목은 WMS 입고)",
        [
            col("receipt_no", "수령 번호", "varchar(40)"),
            col("request_id", "신청서", "bigint"),
            col("received_on", "수령일", "date"),
            col("received_by", "수령자", "varchar(60)"),
            col("note", "메모", "varchar(300)", nullable=True),
        ],
    ),
    table(
        RCL,
        "수령 품목",
        "receipt",
        "DSN-27 F31·F33. 수량·이상(파손·오배송) → 반품 요청(처리는 ERP 구매 반품)",
        [
            col("receipt_id", "수령", "bigint"),
            col("request_line_id", "신청 품목", "bigint"),
            col("qty", "수령 수량", "numeric(18,3)"),
            col(
                "issue",
                "이상",
                "varchar(8)",
                default="'OK'",
                rule="OK / DAMAGED / WRONG / SHORT",
            ),
            col("return_requested", "반품 요청", "boolean", default="false"),
        ],
    ),
]

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in (CA, CI, SS):
    CONSTRAINTS += [
        c(t, "UK", S + ["code"], reason="세대 내 코드 유일"),
        c(t, "CHECK", ["code"], f"code {CODE}", "코드 형식"),
    ]
for t, field in [(RQ, "request_no"), (RC, "receipt_no")]:
    CONSTRAINTS += [
        c(t, "UK", S + [field], reason="세대 내 번호 유일"),
        c(t, "CHECK", [field], f"length(btrim({field})) > 0", "번호 필수"),
    ]
for t in (CP, RQ):
    CONSTRAINTS.append(c(t, "CHECK", ["currency"], "currency = 'KRW'", "KRW 고정"))
CONSTRAINTS += [
    c(
        CI,
        "CHECK",
        ["is_stock", "wms_item_code", "expense_account_code"],
        "(is_stock = (wms_item_code IS NOT NULL)) AND (is_stock OR expense_account_code IS NOT NULL)",
        "재고 품목은 WMS 코드, 비재고는 비용 계정",
    ),
    c(
        CP,
        "UK",
        S + ["catalog_item_id", "partner_code", "valid_from"],
        reason="품목·공급처·시작일 1건",
    ),
    c(
        CP,
        "CHECK",
        ["unit_price", "min_qty", "valid_from", "valid_until"],
        "unit_price >= 0 AND min_qty > 0 AND (valid_until IS NULL OR valid_until >= valid_from)",
        "단가·최소 수량·기간",
    ),
    c(SSI, "UK", S + ["standard_set_id", "catalog_item_id"], reason="세트·품목 1행"),
    c(SSI, "CHECK", ["qty"], "qty > 0", "수량 양수"),
    c(
        AR,
        "CHECK",
        ["step", "min_amount", "approver_role"],
        "step BETWEEN 1 AND 3 AND min_amount >= 0 AND approver_role IN ('DEPT_HEAD', 'ADMIN_DEPT')",
        "단계·금액·역할",
    ),
    uk_partial(AR, ["step"], "is_active", "단계당 사용 규칙 1개"),
    c(
        RQ,
        "CHECK",
        ["kind", "status", "total_amount"],
        f"kind IN ('NORMAL', 'EMERGENCY') AND status IN ({q(REQ_STATES)}) AND total_amount >= 0",
        "구분·상태·합계",
    ),
    c(
        RQ,
        "CHECK",
        ["status", "submitted_at", "decided_at", "reject_reason"],
        "((status = 'DRAFT') = (submitted_at IS NULL)) AND ((status IN ('APPROVED', 'REJECTED')) = (decided_at IS NOT NULL)) AND ((status = 'REJECTED') = (reject_reason IS NOT NULL))",
        "상태별 시각·사유",
    ),
    c(
        RQ,
        "CHECK",
        ["kind", "card_txn_ref"],
        "(kind = 'EMERGENCY') = (card_txn_ref IS NOT NULL)",
        "긴급 구매는 카드 내역 필수",
    ),
    uk_partial(
        RQ,
        ["card_txn_ref"],
        "card_txn_ref IS NOT NULL AND status <> 'WITHDRAWN'",
        "카드 내역 1건에 신청 1건",
    ),
    c(
        RQ,
        "SERVICE/DB_POLICY",
        ["status"],
        "제출 시 필요한 단계 = 사용 규칙 중 기준 금액 ≤ 합계. 모든 단계 승인 → APPROVED, 한 단계라도 반려 → REJECTED(재신청은 새 신청서). 제출 후 명세 불변, 승인 전 회수(WITHDRAWN) 가능",
        "승인 단계(Q2)",
    ),
    c(
        RQ,
        "SERVICE/DB_POLICY",
        ["budget_note"],
        "제출·승인 화면에 ERP 부서·비용 계정 월 예산 대비 실적 + 이번 합계를 표시(erp.interface.budget_status), 초과면 경고만(차단 아님, Q3). 제출 시 결과 스냅샷",
        "예산 확인(Q3)",
    ),
    c(
        RQ,
        "SERVICE/DB_POLICY",
        ["kind"],
        "NORMAL 승인분은 ERP가 fs.elb.interface.approved_requests(since)로 가져가 공급처별 구매 요청(출처 ELB) — ELB 자체 발주 없음(Q1). EMERGENCY는 구매 요청을 만들지 않고 ERP 카드 내역(card_transaction)과 연결해 비용 근거로(Q6)",
        "구매 연계(Q1·Q6)",
    ),
    c(RL, "UK", S + ["request_id", "line_no"], reason="행 번호 유일"),
    c(
        RL,
        "CHECK",
        ["line_no", "qty", "unit_price", "amount"],
        "line_no >= 1 AND qty > 0 AND unit_price >= 0 AND amount >= 0",
        "행 값",
    ),
    c(AP, "UK", S + ["request_id", "step"], reason="신청·단계 결정 1건"),
    c(
        AP,
        "CHECK",
        ["step", "decision", "comment"],
        "step BETWEEN 1 AND 3 AND decision IN ('APPROVED', 'REJECTED') AND (decision = 'APPROVED' OR length(btrim(comment)) >= 2)",
        "단계·결정·반려 의견",
    ),
    c(RCL, "UK", S + ["receipt_id", "request_line_id"], reason="수령·신청 품목 1행"),
    c(
        RCL,
        "CHECK",
        ["qty", "issue", "return_requested"],
        "qty >= 0 AND issue IN ('OK', 'DAMAGED', 'WRONG', 'SHORT') AND (NOT return_requested OR issue <> 'OK')",
        "수량·이상·반품 요청",
    ),
    c(
        RC,
        "SERVICE/DB_POLICY",
        ["request_id"],
        "비재고 품목만, 승인 신청에 대해. 누적 수령 ≤ 신청 수량(부분 수령 여러 번). ERP가 fs.elb.interface.receipts(since)로 읽어 매입 근거, 반품 요청은 ERP 구매 반품으로(Q4). 재고 품목은 WMS 입고 상태만 표시",
        "수령 확인(Q4)",
    ),
]
for t, cols_ in [
    (CI, ["category_id"]),
    (CP, ["catalog_item_id"]),
    (RQ, ["department_code", "status"]),
    (RL, ["request_id"]),
    (AP, ["request_id"]),
    (RCL, ["receipt_id"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="FK·목록 조회"))

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
    r(CI, ["category_id"], CA, "분류"),
    r(CP, ["catalog_item_id"], CI, "카탈로그 품목"),
    r(SSI, ["standard_set_id"], SS, "표준 세트"),
    r(SSI, ["catalog_item_id"], CI, "카탈로그 품목"),
    r(RL, ["request_id"], RQ, "신청서"),
    r(RL, ["catalog_item_id"], CI, "카탈로그 품목"),
    r(AP, ["request_id"], RQ, "신청서"),
    r(RC, ["request_id"], RQ, "신청서"),
    r(RCL, ["receipt_id"], RC, "수령"),
    r(RCL, ["request_line_id"], RL, "신청 품목"),
]
STATES = [
    dict(
        table=RQ,
        column="status",
        values=list(REQ_STATES),
        default="DRAFT",
        transition="DRAFT→SUBMITTED→APPROVED/REJECTED; 승인 전 SUBMITTED→WITHDRAWN",
    )
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn27은 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "scm.forecast_run" not in names:
        raise SystemExit("apply_dsn26을 먼저 적용한다")
    if RQ in names:
        return False
    modules = [
        x
        for x in d["constraints"]
        if x["table"] in MODULE_TABLES
        and x["kind"] == "CHECK"
        and "module_key IN" in x["expression"]
    ]
    if len(modules) != 2:
        raise SystemExit(f"모듈 키 CHECK를 찾지 못했다: {len(modules)}개")
    for x in modules:
        x["expression"] = x["expression"].rstrip(")") + ", 'elb')"
    for code in d["code_lists"]:
        if (
            code["target"] in MODULE_TABLES
            and code["column"] == "module_key"
            and "elb" not in code["values"]
        ):
            code["values"] = [*code["values"], "elb"]
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    d.update(version="target-0.15.0", task="DSN-27", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.15.0",
            task="DSN-27",
            date="2026-10-05",
            change="ELB/MRO 신규: elb 11테이블(분류·카탈로그 품목·계약 단가·표준 세트·세트 품목·승인 규칙·신청서·신청 품목·승인·수령·수령 품목), 모듈 키 elb. 업무 스키마 간 FK 0",
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
    elb = [t for t in d["tables"] if t["name"].startswith(E)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                elb_tables=len(elb),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
