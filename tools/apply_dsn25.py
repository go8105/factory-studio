"""DSN-25: CRM(신규) 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn24 다음).

근거: docs/modules/crm/CRM_설계_DSN-25.md 4장(crm 13테이블 + 모듈 키 'crm'), 결정 Q1~Q6.
견적·수주는 ERP, 클레임은 QMS. 견적 요청의 "ERP가 가져감" 상태는 ERP 조회로 표시(CRM에 저장하지 않음).
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
C = "crm."
MODULE_TABLES = {"core.workspace_module", "core.app_review"}
STAGES = ("DISCOVERY", "QUALIFY", "PROPOSAL", "QUOTE", "NEGOTIATION", "WON", "LOST")
SOURCES = ("EXHIBITION", "SEMINAR", "WEB", "REFERRAL", "COLD", "OTHER")


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-25"}


RP, CA, LE, AC, CO, OP, OI, SH, QR, QL, AV, TK, IN = (
    C + "sales_rep",
    C + "campaign",
    C + "lead",
    C + "account",
    C + "contact",
    C + "opportunity",
    C + "opportunity_item",
    C + "stage_history",
    C + "quote_request",
    C + "quote_request_line",
    C + "activity",
    C + "task",
    C + "inquiry",
)

TABLES = [
    table(
        RP,
        "영업 담당자",
        "master",
        "DSN-25 F06. CRM 자체 담당자, ERP 담당자 코드 스냅샷",
        [
            col("code", "담당자 코드", "varchar(30)"),
            col("name", "이름", "varchar(60)"),
            col("erp_employee_code", "ERP 담당자 코드", "varchar(30)", nullable=True),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        CA,
        "캠페인",
        "marketing",
        "DSN-25 F41(Q5). 전시회·세미나 등. 리드·기회 출처 연결",
        [
            col("code", "캠페인 코드", "varchar(30)"),
            col("name", "캠페인명", "varchar(200)"),
            col("kind", "종류", "varchar(10)", rule=" / ".join(SOURCES)),
            col("start_on", "시작일", "date"),
            col("end_on", "종료일", "date", nullable=True),
            col("budget", "예산", "numeric(18,2)", nullable=True),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
        ],
    ),
    table(
        LE,
        "잠재 고객",
        "customer",
        "DSN-25 F01. 신규 → 접촉 → 자격 확인 → 전환(고객사) / 실격. 연락처는 합성",
        [
            col("lead_no", "리드 번호", "varchar(40)"),
            col("company_name", "회사명", "varchar(200)"),
            col("contact_name", "담당자", "varchar(60)"),
            col("phone", "연락처", "varchar(30)", nullable=True),
            col("email", "이메일", "varchar(120)", nullable=True),
            col("source", "출처", "varchar(10)", rule=" / ".join(SOURCES)),
            col("campaign_id", "캠페인", "bigint", nullable=True),
            col("interest", "관심 내용", "varchar(500)", nullable=True),
            col("rep_id", "담당", "bigint", nullable=True),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'NEW'",
                rule="NEW / CONTACTED / QUALIFIED / CONVERTED / DISQUALIFIED",
            ),
            col("converted_account_id", "전환 고객사", "bigint", nullable=True),
            col("closed_at", "전환·실격 시각", "timestamptz", nullable=True),
            col("disqualify_reason", "실격 사유", "varchar(300)", nullable=True),
        ],
    ),
    table(
        AC,
        "고객사",
        "customer",
        "DSN-25 F02·F04·F05(Q1). CRM 소유. 거래 시작 시 ERP가 가져가 거래처 생성, ERP 거래처 코드를 연결. 등급은 ERP 매출 조회 계산",
        [
            col("code", "고객사 코드", "varchar(30)"),
            col("name", "고객사명", "varchar(200)"),
            col("industry", "업종", "varchar(60)", nullable=True),
            col(
                "business_no",
                "사업자번호",
                "varchar(12)",
                nullable=True,
                rule="합성 값",
            ),
            col("address", "주소", "varchar(300)", nullable=True),
            col(
                "tags",
                "분류·관심 품목 태그",
                "varchar(300)",
                nullable=True,
                rule="쉼표 구분",
            ),
            col("erp_partner_code", "ERP 거래처 코드", "varchar(40)", nullable=True),
            col("rep_id", "담당", "bigint", nullable=True),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        CO,
        "고객 담당자",
        "customer",
        "DSN-25 F03. 이름·직위·연락처(합성)",
        [
            col("account_id", "고객사", "bigint"),
            col("name", "이름", "varchar(60)"),
            col("title", "직위", "varchar(60)", nullable=True),
            col("phone", "연락처", "varchar(30)", nullable=True),
            col("email", "이메일", "varchar(120)", nullable=True),
            col("is_primary", "주 담당", "boolean", default="false"),
        ],
    ),
    table(
        OP,
        "영업 기회",
        "opportunity",
        "DSN-25 F11~F16(Q2·Q3). 6단계 + 수주/실주. 확률 기본값은 단계별, 조정 가능. 수주는 ERP 수주 확인 후 사람이",
        [
            col("opp_no", "기회 번호", "varchar(40)"),
            col("account_id", "고객사", "bigint"),
            col("title", "제목", "varchar(200)"),
            col("rep_id", "담당", "bigint"),
            col(
                "stage",
                "단계",
                "varchar(12)",
                default="'DISCOVERY'",
                rule=" / ".join(STAGES),
            ),
            col(
                "probability",
                "확률(%)",
                "integer",
                rule="단계 기본 10·20·40·60·80·100·0",
            ),
            col("amount", "예상 금액", "numeric(18,2)"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col("expected_close_on", "예상 마감일", "date"),
            col("campaign_id", "캠페인", "bigint", nullable=True),
            col("competitor", "경쟁사", "varchar(100)", nullable=True),
            col(
                "lost_reason",
                "실주 사유",
                "varchar(10)",
                nullable=True,
                rule="PRICE / SPEC / DELIVERY / COMPETITOR / CANCELLED / OTHER",
            ),
            col(
                "erp_order_no",
                "ERP 수주 번호",
                "varchar(40)",
                nullable=True,
                rule="수주 확인 시 스냅샷",
            ),
            col("closed_at", "종료 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        OI,
        "기회 품목",
        "opportunity",
        "DSN-25 F11. 관심 품목·수량·희망가(ERP 품목 코드 스냅샷)",
        [
            col("opportunity_id", "영업 기회", "bigint"),
            col("line_no", "행 번호", "integer"),
            col("item_code", "품목 코드", "varchar(40)"),
            col("item_name", "품목명", "varchar(200)"),
            col("qty", "수량", "numeric(18,3)"),
            col("target_price", "희망 단가", "numeric(18,4)", nullable=True),
        ],
    ),
    table(
        SH,
        "단계 이력",
        "opportunity",
        "DSN-25 F12·F53. 단계 변경 기록(정체 기간·전환율 계산). 추가만",
        [
            col("opportunity_id", "영업 기회", "bigint"),
            col("from_stage", "이전 단계", "varchar(12)", nullable=True),
            col("to_stage", "새 단계", "varchar(12)"),
            col("changed_at", "변경 시각", "timestamptz"),
        ],
    ),
    table(
        QR,
        "견적 요청",
        "opportunity",
        "DSN-25 F13(Q2). 견적 단계 기회 → ERP가 가져가 견적 초안. ERP 처리 여부는 ERP 조회(저장 안 함)",
        [
            col("request_no", "요청 번호", "varchar(40)"),
            col("opportunity_id", "영업 기회", "bigint"),
            col("requested_at", "요청 시각", "timestamptz"),
            col("note", "요청 메모", "varchar(500)", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'OPEN'",
                rule="OPEN / CANCELLED",
            ),
            col("cancelled_at", "취소 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        QL,
        "견적 요청 품목",
        "opportunity",
        "DSN-25 F13. 요청 시점 기회 품목 스냅샷(불변)",
        [
            col("quote_request_id", "견적 요청", "bigint"),
            col("line_no", "행 번호", "integer"),
            col("item_code", "품목 코드", "varchar(40)"),
            col("item_name", "품목명", "varchar(200)"),
            col("qty", "수량", "numeric(18,3)"),
            col("target_price", "희망 단가", "numeric(18,4)", nullable=True),
        ],
    ),
    table(
        AV,
        "영업 활동",
        "activity",
        "DSN-25 F21. 방문·전화·메일·회의 기록(발송 없음). 고객사·기회·리드 중 하나 이상에 연결",
        [
            col("kind", "종류", "varchar(8)", rule="VISIT / CALL / MAIL / MEETING"),
            col("subject", "제목", "varchar(200)"),
            col("note", "내용", "varchar(2000)", nullable=True),
            col("result", "결과", "varchar(300)", nullable=True),
            col("rep_id", "담당", "bigint"),
            col("account_id", "고객사", "bigint", nullable=True),
            col("opportunity_id", "영업 기회", "bigint", nullable=True),
            col("lead_id", "잠재 고객", "bigint", nullable=True),
            col("occurred_at", "일시", "timestamptz"),
        ],
    ),
    table(
        TK,
        "할 일",
        "activity",
        "DSN-25 F22. 다음 활동 예정·완료",
        [
            col("title", "할 일", "varchar(200)"),
            col("due_on", "예정일", "date"),
            col("rep_id", "담당", "bigint"),
            col("account_id", "고객사", "bigint", nullable=True),
            col("opportunity_id", "영업 기회", "bigint", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'OPEN'",
                rule="OPEN / DONE / CANCELLED",
            ),
            col("done_at", "완료 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        IN,
        "고객 문의",
        "inquiry",
        "DSN-25 F31·F32(Q4). 일반 문의는 답변·종결, 품질 문의는 QMS 클레임으로 전환(QMS가 가져감, 클레임은 QMS 소유)",
        [
            col("inquiry_no", "문의 번호", "varchar(40)"),
            col("account_id", "고객사", "bigint"),
            col("contact_id", "고객 담당자", "bigint", nullable=True),
            col(
                "kind",
                "종류",
                "varchar(10)",
                rule="DELIVERY 납기 / QUOTE 견적 / TECH 기술 / QUALITY 품질 / OTHER",
            ),
            col("subject", "제목", "varchar(200)"),
            col("content", "내용", "varchar(2000)"),
            col("item_code", "품목 코드", "varchar(40)", nullable=True),
            col("lot_no", "LOT 번호", "varchar(50)", nullable=True),
            col("received_at", "접수 시각", "timestamptz"),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'OPEN'",
                rule="OPEN / ANSWERED / CLOSED / TRANSFERRED",
            ),
            col("answer", "답변", "varchar(2000)", nullable=True),
            col("answered_at", "답변 시각", "timestamptz", nullable=True),
            col("closed_at", "종결 시각", "timestamptz", nullable=True),
        ],
    ),
]

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in (RP, CA, AC):
    CONSTRAINTS += [
        c(t, "UK", S + ["code"], reason="세대 내 코드 유일"),
        c(t, "CHECK", ["code"], f"code {CODE}", "코드 형식"),
    ]
for t, field in [
    (LE, "lead_no"),
    (OP, "opp_no"),
    (QR, "request_no"),
    (IN, "inquiry_no"),
]:
    CONSTRAINTS += [
        c(t, "UK", S + [field], reason="세대 내 번호 유일"),
        c(t, "CHECK", [field], f"length(btrim({field})) > 0", "번호 필수"),
    ]
for t in (CA, OP):
    CONSTRAINTS.append(c(t, "CHECK", ["currency"], "currency = 'KRW'", "KRW 고정"))
for t, parent in [(OI, "opportunity_id"), (QL, "quote_request_id")]:
    CONSTRAINTS += [
        c(t, "UK", S + [parent, "line_no"], reason="행 번호 유일"),
        c(
            t,
            "CHECK",
            ["line_no", "qty", "target_price"],
            "line_no >= 1 AND qty > 0 AND (target_price IS NULL OR target_price >= 0)",
            "행 값",
        ),
    ]
CONSTRAINTS += [
    c(
        CA,
        "CHECK",
        ["kind", "start_on", "end_on", "budget"],
        f"kind IN ({q(SOURCES)}) AND (end_on IS NULL OR end_on >= start_on) AND (budget IS NULL OR budget >= 0)",
        "종류·기간·예산",
    ),
    c(
        LE,
        "CHECK",
        ["source", "status"],
        f"source IN ({q(SOURCES)}) AND status IN ('NEW', 'CONTACTED', 'QUALIFIED', 'CONVERTED', 'DISQUALIFIED')",
        "출처·상태",
    ),
    c(
        LE,
        "CHECK",
        ["status", "converted_account_id", "closed_at", "disqualify_reason"],
        "((status = 'CONVERTED') = (converted_account_id IS NOT NULL)) AND ((status IN ('CONVERTED', 'DISQUALIFIED')) = (closed_at IS NOT NULL)) AND ((status = 'DISQUALIFIED') = (disqualify_reason IS NOT NULL))",
        "전환·실격 값",
    ),
    c(
        AC,
        "SERVICE/DB_POLICY",
        ["erp_partner_code"],
        'ERP가 fs.crm.interface.accounts(ready_for_erp=True)로 읽어 "CRM에서 가져오기"로 거래처 생성 후, CRM은 ERP 조회(erp.interface.crm_imports)로 거래처 코드를 연결(자동 동기화 없음, Q1). 등급 = 최근 12개월 ERP 매출(조회 계산)',
        "고객 마스터 연결(Q1)",
    ),
    uk_partial(
        AC,
        ["erp_partner_code"],
        "erp_partner_code IS NOT NULL",
        "ERP 거래처 1건에 고객사 1건",
    ),
    uk_partial(CO, ["account_id"], "is_primary", "고객사당 주 담당 1명"),
    c(
        OP,
        "CHECK",
        ["stage", "probability", "amount"],
        f"stage IN ({q(STAGES)}) AND probability BETWEEN 0 AND 100 AND amount >= 0",
        "단계·확률·금액",
    ),
    c(
        OP,
        "CHECK",
        ["stage", "probability", "closed_at", "lost_reason", "erp_order_no"],
        "((stage IN ('WON', 'LOST')) = (closed_at IS NOT NULL)) AND ((stage = 'LOST') = (lost_reason IS NOT NULL)) AND (stage <> 'WON' OR (probability = 100 AND erp_order_no IS NOT NULL)) AND (stage <> 'LOST' OR probability = 0)",
        "수주·실주 값",
    ),
    c(
        OP,
        "CHECK",
        ["lost_reason"],
        "lost_reason IS NULL OR lost_reason IN ('PRICE', 'SPEC', 'DELIVERY', 'COMPETITOR', 'CANCELLED', 'OTHER')",
        "실주 사유 값",
    ),
    c(
        OP,
        "SERVICE/DB_POLICY",
        ["stage"],
        "단계 이동마다 단계 이력 1행. 확률 기본값 10·20·40·60·80(조정 가능). 수주 = ERP 수주(erp.interface.sales_orders_for_crm)에서 해당 견적 요청의 수주를 확인해 사람이 처리(ERP 수주 번호 스냅샷). 종료 후 단계 변경은 재개(새 이력)만",
        "기회 단계·수주(Q2·Q3)",
    ),
    uk_partial(
        OP, ["erp_order_no"], "erp_order_no IS NOT NULL", "ERP 수주 1건에 기회 1건"
    ),
    c(
        SH,
        "CHECK",
        ["from_stage", "to_stage"],
        f"to_stage IN ({q(STAGES)}) AND (from_stage IS NULL OR from_stage IN ({q(STAGES)})) AND from_stage IS DISTINCT FROM to_stage",
        "단계 값",
    ),
    c(
        QR,
        "CHECK",
        ["status", "cancelled_at"],
        "status IN ('OPEN', 'CANCELLED') AND ((status = 'CANCELLED') = (cancelled_at IS NOT NULL))",
        "상태·취소",
    ),
    uk_partial(QR, ["opportunity_id"], "status = 'OPEN'", "기회당 열린 견적 요청 1건"),
    c(
        QR,
        "SERVICE/DB_POLICY",
        ["status"],
        "기회가 QUOTE 단계 이상일 때만 생성. 품목은 요청 시점 스냅샷(불변). ERP가 fs.crm.interface.quote_requests(since)로 가져가 견적 초안, 처리 여부는 ERP 조회로 표시(CRM에 저장 안 함). ERP가 가져간 뒤 취소는 거부",
        "견적 요청(Q2)",
    ),
    c(
        AV,
        "CHECK",
        ["kind", "account_id", "opportunity_id", "lead_id"],
        "kind IN ('VISIT', 'CALL', 'MAIL', 'MEETING') AND (account_id IS NOT NULL OR opportunity_id IS NOT NULL OR lead_id IS NOT NULL)",
        "종류·연결 대상",
    ),
    c(
        TK,
        "CHECK",
        ["status", "done_at"],
        "status IN ('OPEN', 'DONE', 'CANCELLED') AND ((status = 'DONE') = (done_at IS NOT NULL))",
        "상태·완료",
    ),
    c(
        IN,
        "CHECK",
        ["kind", "status"],
        "kind IN ('DELIVERY', 'QUOTE', 'TECH', 'QUALITY', 'OTHER') AND status IN ('OPEN', 'ANSWERED', 'CLOSED', 'TRANSFERRED')",
        "종류·상태",
    ),
    c(
        IN,
        "CHECK",
        ["kind", "status"],
        "status <> 'TRANSFERRED' OR kind = 'QUALITY'",
        "QMS 전환은 품질 문의만",
    ),
    c(
        IN,
        "CHECK",
        ["status", "answer", "answered_at", "closed_at"],
        "((status IN ('ANSWERED', 'CLOSED')) = (answered_at IS NOT NULL AND answer IS NOT NULL)) AND ((status IN ('CLOSED', 'TRANSFERRED')) = (closed_at IS NOT NULL))",
        "답변·종결",
    ),
    c(
        IN,
        "SERVICE/DB_POLICY",
        ["status"],
        '품질 문의 "QMS 클레임으로 전환" = TRANSFERRED. QMS가 fs.crm.interface.quality_inquiries(since)로 가져가 클레임 접수(클레임은 QMS 소유, DSN-14 Q4). CRM은 qms.interface.claims(customer)로 진행을 읽어 표시',
        "품질 문의 → QMS(Q4)",
    ),
]
for t, cols_ in [
    (LE, ["status"]),
    (CO, ["account_id"]),
    (OP, ["stage", "expected_close_on"]),
    (OP, ["account_id"]),
    (SH, ["opportunity_id", "changed_at"]),
    (AV, ["account_id", "occurred_at"]),
    (TK, ["rep_id", "status", "due_on"]),
    (IN, ["account_id", "status"]),
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
    r(LE, ["campaign_id"], CA, "캠페인"),
    r(LE, ["rep_id"], RP, "담당"),
    r(LE, ["converted_account_id"], AC, "전환 고객사"),
    r(AC, ["rep_id"], RP, "담당"),
    r(CO, ["account_id"], AC, "고객사"),
    r(OP, ["account_id"], AC, "고객사"),
    r(OP, ["rep_id"], RP, "담당"),
    r(OP, ["campaign_id"], CA, "캠페인"),
    r(OI, ["opportunity_id"], OP, "영업 기회"),
    r(SH, ["opportunity_id"], OP, "영업 기회"),
    r(QR, ["opportunity_id"], OP, "영업 기회"),
    r(QL, ["quote_request_id"], QR, "견적 요청"),
    r(AV, ["rep_id"], RP, "담당"),
    r(AV, ["account_id"], AC, "고객사"),
    r(AV, ["opportunity_id"], OP, "영업 기회"),
    r(AV, ["lead_id"], LE, "잠재 고객"),
    r(TK, ["rep_id"], RP, "담당"),
    r(TK, ["account_id"], AC, "고객사"),
    r(TK, ["opportunity_id"], OP, "영업 기회"),
    r(IN, ["account_id"], AC, "고객사"),
    r(IN, ["contact_id"], CO, "고객 담당자"),
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
        LE,
        ("NEW", "CONTACTED", "QUALIFIED", "CONVERTED", "DISQUALIFIED"),
        "NEW",
        "NEW→CONTACTED→QUALIFIED→CONVERTED; 어느 단계에서나 DISQUALIFIED",
    ),
    st(
        OP,
        STAGES,
        "DISCOVERY",
        "DISCOVERY→QUALIFY→PROPOSAL→QUOTE→NEGOTIATION→WON(ERP 수주 확인)/LOST; 재개는 새 이력",
        column="stage",
    ),
    st(QR, ("OPEN", "CANCELLED"), "OPEN", "OPEN→CANCELLED(ERP가 가져가기 전만)"),
    st(TK, ("OPEN", "DONE", "CANCELLED"), "OPEN", "OPEN→DONE/CANCELLED"),
    st(
        IN,
        ("OPEN", "ANSWERED", "CLOSED", "TRANSFERRED"),
        "OPEN",
        "OPEN→ANSWERED→CLOSED; 품질 OPEN→TRANSFERRED(QMS)",
    ),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn25는 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "plm.eco" not in names:
        raise SystemExit("apply_dsn24를 먼저 적용한다")
    if OP in names:
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
        x["expression"] = x["expression"].rstrip(")") + ", 'crm')"
    for code in d["code_lists"]:
        if (
            code["target"] in MODULE_TABLES
            and code["column"] == "module_key"
            and "crm" not in code["values"]
        ):
            code["values"] = [*code["values"], "crm"]
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    d["code_lists"].append(
        dict(
            target=OP,
            column="stage",
            values=list(STAGES),
            default="DISCOVERY",
            note="발굴 10 · 자격 20 · 제안 40 · 견적 60 · 협상 80 · 수주 100 · 실주 0(%)",
        )
    )
    d.update(version="target-0.13.0", task="DSN-25", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.13.0",
            task="DSN-25",
            date="2026-10-05",
            change="CRM 신규: crm 13테이블(영업 담당자·캠페인·잠재 고객·고객사·고객 담당자·영업 기회·기회 품목·단계 이력·견적 요청·요청 품목·활동·할 일·고객 문의), 모듈 키 crm. 업무 스키마 간 FK 0",
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
    crm = [t for t in d["tables"] if t["name"].startswith(C)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                crm_tables=len(crm),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
