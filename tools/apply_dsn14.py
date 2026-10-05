"""DSN-14: QMS 보강 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn13 다음).

근거: docs/modules/qms/QMS_보강설계_DSN-14.md 4장(새 테이블 9·기존 테이블 변경 4), 결정 Q1~Q7.
AQL 샘플링 표(KS Q ISO 2859-1)는 표준 참조 데이터라 DB가 아니라 코드 상수로 둔다(FS-013 D6 — 정적 기준은 리포지토리).
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
Q = "qms."


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-14"}


KINDS = ("OUTGOING", "INCOMING", "RETURN", "FIRST_ARTICLE")
SOURCES = ("MES", "WMS", "ERP", "QMS", "MANUAL")
LEVELS = ("EXEMPT", "NORMAL", "TIGHTENED")
ORIGINS = ("INCOMING", "PROCESS", "OUTGOING", "CUSTOMER")

SL, SR, SC, NCR, CAPA, CL, GA, CA, CN = (
    Q + "supplier_level",
    Q + "supplier_rating",
    Q + "scar",
    Q + "ncr",
    Q + "capa",
    Q + "claim",
    Q + "gauge",
    Q + "calibration",
    Q + "change_notice",
)

TABLES = [
    table(
        SL,
        "공급처 검사 수준",
        "supplier",
        "DSN-14 F05(Q1·Q5). 공급처(·품목)별 면제·보통·강화, 적용일 이력. 현재 = 적용일 최신",
        [
            col(
                "partner_code",
                "공급처 코드",
                "varchar(40)",
                rule="ERP 거래처 코드 스냅샷",
            ),
            col(
                "item_code",
                "품목 코드",
                "varchar(40)",
                nullable=True,
                rule="NULL이면 공급처 전체",
            ),
            col("level", "검사 수준", "varchar(10)", rule=" / ".join(LEVELS)),
            col("valid_from", "적용일", "date"),
            col("reason", "사유", "varchar(300)", rule="등급 제안 근거 또는 수동 사유"),
            col("rating_id", "근거 평가", "bigint", nullable=True),
        ],
    ),
    table(
        SR,
        "공급처 품질 평가",
        "supplier",
        "DSN-14 F51(Q5). 월 계산 스냅샷 → 등급·전환 제안. 확정은 사람이 검사 수준 행으로",
        [
            col("rating_month", "평가 월", "varchar(7)", rule="'YYYY-MM'"),
            col("partner_code", "공급처 코드", "varchar(40)"),
            col("lot_count", "검사 LOT 수", "integer"),
            col("failed_lot_count", "불합격 LOT 수", "integer"),
            col("defect_ppm", "불량 PPM", "numeric(12,1)"),
            col("scar_count", "시정 요구 건수", "integer"),
            col("grade", "등급", "varchar(1)", rule="A / B / C / D"),
            col(
                "suggested_level",
                "전환 제안",
                "varchar(10)",
                nullable=True,
                rule="연속 합격 → EXEMPT, 연속 불합격 → TIGHTENED",
            ),
        ],
    ),
    table(
        SC,
        "공급처 시정 요구",
        "supplier",
        "DSN-14 F14. 수입 불합격 → 공급처 통보·회신·종결(통보는 기록만, 발송 없음)",
        [
            col("scar_no", "요구 번호", "varchar(40)"),
            col("partner_code", "공급처 코드", "varchar(40)"),
            col("inspection_id", "근거 검사", "bigint", nullable=True),
            col("ncr_id", "근거 부적합", "bigint", nullable=True),
            col("issued_on", "발행일", "date"),
            col("due_on", "회신 기한", "date"),
            col("response", "공급처 회신", "varchar(1000)", nullable=True),
            col("responded_on", "회신일", "date", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'OPEN'",
                rule="OPEN / RESPONDED / CLOSED",
            ),
            col("closed_at", "종결 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        NCR,
        "부적합 보고",
        "ncr",
        "DSN-14 F31(Q3). 발생처 4종. 불합격 검사·클레임·MES 공정 불량에서 생성. CAPA로 이어짐",
        [
            col("ncr_no", "보고 번호", "varchar(40)"),
            col("origin", "발생처", "varchar(10)", rule=" / ".join(ORIGINS)),
            col("item_code", "품목 코드", "varchar(40)"),
            col("lot_no", "LOT 번호", "varchar(50)", nullable=True, rule="스냅샷"),
            col("qty", "부적합 수량", "numeric(18,3)"),
            col("defect_type_id", "불량 유형", "bigint", nullable=True),
            col("description", "내용", "varchar(1000)"),
            col("immediate_action", "즉시 조치", "varchar(500)", nullable=True),
            col("inspection_id", "근거 검사", "bigint", nullable=True),
            col("claim_id", "근거 클레임", "bigint", nullable=True),
            col(
                "source_ref",
                "외부 원천",
                "varchar(60)",
                nullable=True,
                rule="MES 불량 명세 등 코드 스냅샷",
            ),
            col("reported_on", "보고일", "date"),
            col(
                "status", "상태", "varchar(10)", default="'OPEN'", rule="OPEN / CLOSED"
            ),
            col("closed_at", "종결 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        CAPA,
        "시정·예방 조치",
        "ncr",
        "DSN-14 F32(Q3). 원인·대책·담당·기한 → 완료 → 유효성 확인. 무효면 새 CAPA",
        [
            col("capa_no", "조치 번호", "varchar(40)"),
            col("ncr_id", "부적합 보고", "bigint"),
            col(
                "kind", "종류", "varchar(12)", rule="CORRECTIVE 시정 / PREVENTIVE 예방"
            ),
            col("root_cause", "근본 원인", "varchar(1000)"),
            col("action", "대책", "varchar(1000)"),
            col("owner_name", "담당", "varchar(60)"),
            col("due_on", "기한", "date"),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'OPEN'",
                rule="OPEN / DONE / VERIFIED / INEFFECTIVE",
            ),
            col("done_at", "완료 시각", "timestamptz", nullable=True),
            col("verified_at", "확인 시각", "timestamptz", nullable=True),
            col("verification_note", "유효성 확인", "varchar(500)", nullable=True),
        ],
    ),
    table(
        CL,
        "고객 클레임",
        "claim",
        "DSN-14 F41(Q4). QMS 소유. 접수 → 조사 → 회신 → 종결. CRM은 읽기",
        [
            col("claim_no", "클레임 번호", "varchar(40)"),
            col(
                "customer_code",
                "고객 코드",
                "varchar(40)",
                rule="ERP 거래처 코드 스냅샷",
            ),
            col("received_on", "접수일", "date"),
            col("item_code", "품목 코드", "varchar(40)"),
            col("lot_no", "LOT 번호", "varchar(50)", nullable=True),
            col("qty", "수량", "numeric(18,3)"),
            col("severity", "심각도", "varchar(8)", rule="MINOR / MAJOR / CRITICAL"),
            col("description", "내용", "varchar(1000)"),
            col(
                "return_ref",
                "판매 반품 번호",
                "varchar(40)",
                nullable=True,
                rule="ERP 반품 코드 스냅샷",
            ),
            col(
                "status",
                "상태",
                "varchar(14)",
                default="'RECEIVED'",
                rule="RECEIVED / INVESTIGATING / RESPONDED / CLOSED",
            ),
            col("response", "회신 내용", "varchar(1000)", nullable=True),
            col("responded_on", "회신일", "date", nullable=True),
            col("closed_at", "종결 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        GA,
        "계측기",
        "gauge",
        "DSN-14 F61(Q6). 교정 도래 = 마지막 교정 다음 기한(조회 파생)",
        [
            col("code", "계측기 번호", "varchar(30)"),
            col("name", "계측기명", "varchar(100)"),
            col(
                "gauge_kind",
                "종류",
                "varchar(40)",
                rule="버니어 캘리퍼스·마이크로미터·하이트 게이지 등",
            ),
            col("measure_range", "측정 범위", "varchar(60)", nullable=True),
            col("resolution", "분해능", "varchar(30)", nullable=True),
            col("calibration_cycle_days", "교정 주기(일)", "integer"),
            col(
                "status",
                "상태",
                "varchar(8)",
                default="'ACTIVE'",
                rule="ACTIVE / REPAIR / RETIRED",
            ),
        ],
    ),
    table(
        CA,
        "교정 이력",
        "gauge",
        "DSN-14 F62. 교정 결과·다음 기한. 불합격이면 계측기 REPAIR",
        [
            col("gauge_id", "계측기", "bigint"),
            col("calibrated_on", "교정일", "date"),
            col("next_due_on", "다음 기한", "date"),
            col("result", "결과", "varchar(4)", rule="PASS / FAIL"),
            col("agency", "교정 기관", "varchar(100)", nullable=True),
            col("certificate_no", "성적서 번호", "varchar(60)", nullable=True),
        ],
    ),
    table(
        CN,
        "4M 변경 신고",
        "change",
        "DSN-14 F06(Q7). 사람·설비·자재·방법 변경 → 승인 → 초품 검사 합격 → 확인",
        [
            col("cn_no", "신고 번호", "varchar(40)"),
            col(
                "change_type",
                "변경 구분",
                "varchar(8)",
                rule="MAN / MACHINE / MATERIAL / METHOD",
            ),
            col("item_code", "품목 코드", "varchar(40)"),
            col("description", "변경 내용", "varchar(1000)"),
            col("requested_on", "신청일", "date"),
            col("effective_on", "적용 예정일", "date"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'REQUESTED'",
                rule="REQUESTED / APPROVED / REJECTED / VERIFIED",
            ),
            col("decided_at", "승인·반려 시각", "timestamptz", nullable=True),
            col("decision_note", "승인 의견", "varchar(500)", nullable=True),
            col("first_article_inspection_id", "초품 검사", "bigint", nullable=True),
        ],
    ),
]

NEW_COLUMNS = {
    Q + "inspection_spec": [
        col(
            "inspection_kind",
            "검사 종류",
            "varchar(14)",
            default="'OUTGOING'",
            rule="OUTGOING 출하 / INCOMING 수입. RETURN·FIRST_ARTICLE은 출하 기준 사용",
        ),
        col(
            "aql",
            "AQL",
            "numeric(5,3)",
            nullable=True,
            rule="Q2. NULL이면 시료 수 직접 입력",
        ),
    ],
    Q + "inspection": [
        col(
            "inspection_kind",
            "검사 종류",
            "varchar(14)",
            default="'OUTGOING'",
            rule=" / ".join(KINDS),
        ),
        col(
            "partner_code",
            "공급처·고객 코드",
            "varchar(40)",
            nullable=True,
            rule="수입: 공급처, 반품: 고객(ERP 코드 스냅샷)",
        ),
        col(
            "source_ref",
            "원천 번호",
            "varchar(60)",
            nullable=True,
            rule="WMS 입고 번호·ERP 반품 번호·4M 신고 번호",
        ),
        col(
            "sampling", "샘플링", "varchar(6)", default="'MANUAL'", rule="AQL / MANUAL"
        ),
        col("accept_number", "합격 판정 개수(Ac)", "integer", nullable=True),
        col("reject_number", "불합격 판정 개수(Re)", "integer", nullable=True),
        col(
            "defect_count",
            "시료 불량 개수",
            "integer",
            nullable=True,
            rule="AQL 판정 입력",
        ),
    ],
    Q + "inspection_value": [
        col("gauge_id", "사용 계측기", "bigint", nullable=True, rule="F27")
    ],
}

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t, field in [
    (SC, "scar_no"),
    (NCR, "ncr_no"),
    (CAPA, "capa_no"),
    (CL, "claim_no"),
    (CN, "cn_no"),
]:
    CONSTRAINTS += [
        c(t, "UK", S + [field], reason="세대 내 번호 유일"),
        c(t, "CHECK", [field], f"length(btrim({field})) > 0", "번호 필수"),
    ]
CONSTRAINTS += [
    c(
        SL,
        "UK",
        S + ["partner_code", "item_code", "valid_from"],
        reason="공급처·품목·적용일 1건",
    ),
    uk_partial(
        SL,
        ["partner_code", "valid_from"],
        "item_code IS NULL",
        "공급처 전체 수준·적용일 1건",
    ),
    c(
        SL,
        "CHECK",
        ["level", "reason"],
        f"level IN ({q(LEVELS)}) AND length(btrim(reason)) >= 2",
        "수준·사유",
    ),
    c(
        SL,
        "SERVICE/DB_POLICY",
        ["level"],
        "수입 검사 대상 = 품목 출하 검사 필요(MES·WMS 품목 속성) AND 현재 수준 <> EXEMPT. TIGHTENED는 AQL 표 강화 검사. 전환은 평가 제안을 담당자가 확정할 때만 새 행",
        "검사 대상·수준 전환(Q1·Q5)",
    ),
    c(SR, "UK", S + ["rating_month", "partner_code"], reason="월·공급처 1건"),
    c(
        SR,
        "CHECK",
        ["rating_month"],
        "rating_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'",
        "'YYYY-MM' 형식",
    ),
    c(
        SR,
        "CHECK",
        [
            "lot_count",
            "failed_lot_count",
            "defect_ppm",
            "scar_count",
            "grade",
            "suggested_level",
        ],
        f"lot_count >= 0 AND failed_lot_count BETWEEN 0 AND lot_count AND defect_ppm >= 0 AND scar_count >= 0 AND grade IN ('A', 'B', 'C', 'D') AND (suggested_level IS NULL OR suggested_level IN ({q(LEVELS)}))",
        "평가 값",
    ),
    c(
        SC,
        "CHECK",
        ["status", "responded_on", "closed_at"],
        "status IN ('OPEN', 'RESPONDED', 'CLOSED') AND ((status = 'OPEN') = (responded_on IS NULL)) AND ((status = 'CLOSED') = (closed_at IS NOT NULL))",
        "상태별 값",
    ),
    c(SC, "CHECK", ["issued_on", "due_on"], "due_on >= issued_on", "기한 순서"),
    c(
        NCR,
        "CHECK",
        ["origin", "qty", "description"],
        f"origin IN ({q(ORIGINS)}) AND qty > 0 AND length(btrim(description)) >= 2",
        "발생처·수량·내용",
    ),
    c(
        NCR,
        "CHECK",
        ["status", "closed_at"],
        "status IN ('OPEN', 'CLOSED') AND ((status = 'CLOSED') = (closed_at IS NOT NULL))",
        "종결 시각",
    ),
    c(
        NCR,
        "CHECK",
        ["origin", "inspection_id", "claim_id"],
        "(origin <> 'CUSTOMER' OR claim_id IS NOT NULL) AND (origin NOT IN ('INCOMING', 'OUTGOING') OR inspection_id IS NOT NULL)",
        "발생처별 근거",
    ),
    c(
        NCR,
        "SERVICE/DB_POLICY",
        ["status"],
        "종결 조건: 연결 CAPA가 모두 VERIFIED(또는 CAPA 불필요 사유 기록). 종결 후 불변",
        "부적합 종결(Q3)",
    ),
    c(
        CAPA,
        "CHECK",
        ["kind", "status"],
        "kind IN ('CORRECTIVE', 'PREVENTIVE') AND status IN ('OPEN', 'DONE', 'VERIFIED', 'INEFFECTIVE')",
        "종류·상태",
    ),
    c(
        CAPA,
        "CHECK",
        ["status", "done_at", "verified_at", "verification_note"],
        "(status = 'OPEN' AND done_at IS NULL AND verified_at IS NULL) OR (status = 'DONE' AND done_at IS NOT NULL AND verified_at IS NULL) OR "
        "(status IN ('VERIFIED', 'INEFFECTIVE') AND done_at IS NOT NULL AND verified_at >= done_at AND length(btrim(verification_note)) >= 2)",
        "상태별 시각·확인",
    ),
    c(
        CAPA,
        "CHECK",
        ["root_cause", "action"],
        "length(btrim(root_cause)) >= 2 AND length(btrim(action)) >= 2",
        "원인·대책",
    ),
    c(
        CL,
        "CHECK",
        ["severity", "status", "qty"],
        "severity IN ('MINOR', 'MAJOR', 'CRITICAL') AND status IN ('RECEIVED', 'INVESTIGATING', 'RESPONDED', 'CLOSED') AND qty > 0",
        "심각도·상태·수량",
    ),
    c(
        CL,
        "CHECK",
        ["status", "response", "responded_on", "closed_at"],
        "((status IN ('RECEIVED', 'INVESTIGATING') AND responded_on IS NULL) OR (status IN ('RESPONDED', 'CLOSED') AND responded_on IS NOT NULL AND length(btrim(response)) >= 2)) AND ((status = 'CLOSED') = (closed_at IS NOT NULL))",
        "회신·종결",
    ),
    c(
        CL,
        "SERVICE/DB_POLICY",
        ["status"],
        "조사 시작 시 부적합 보고(origin CUSTOMER) 생성. LOT 역추적은 MES·WMS 조회. CRM은 fs.qms.interface.claims()로 읽기만",
        "클레임 흐름(Q4)",
    ),
    c(GA, "UK", S + ["code"], reason="세대 내 계측기 번호 유일"),
    c(
        GA,
        "CHECK",
        ["code", "calibration_cycle_days", "status"],
        f"code {CODE} AND calibration_cycle_days BETWEEN 1 AND 1825 AND status IN ('ACTIVE', 'REPAIR', 'RETIRED')",
        "번호·주기·상태",
    ),
    c(
        GA,
        "SERVICE/DB_POLICY",
        ["calibration_cycle_days"],
        "교정 도래 = 최신 교정의 next_due_on. 30일 이내 경고, 기한 경과·REPAIR 계측기를 검사 값에 쓰면 경고(차단 아님)",
        "교정 도래·사용 경고(Q6)",
    ),
    c(CA, "UK", S + ["gauge_id", "calibrated_on"], reason="계측기·교정일 1건"),
    c(
        CA,
        "CHECK",
        ["calibrated_on", "next_due_on", "result"],
        "next_due_on > calibrated_on AND result IN ('PASS', 'FAIL')",
        "기한·결과",
    ),
    c(
        CN,
        "CHECK",
        ["change_type", "status"],
        "change_type IN ('MAN', 'MACHINE', 'MATERIAL', 'METHOD') AND status IN ('REQUESTED', 'APPROVED', 'REJECTED', 'VERIFIED')",
        "구분·상태",
    ),
    c(
        CN,
        "CHECK",
        ["status", "decided_at", "first_article_inspection_id"],
        "((status = 'REQUESTED') = (decided_at IS NULL)) AND (status <> 'VERIFIED' OR first_article_inspection_id IS NOT NULL)",
        "승인·초품 검사",
    ),
    c(
        CN,
        "CHECK",
        ["requested_on", "effective_on"],
        "effective_on >= requested_on",
        "적용일 순서",
    ),
    c(
        CN,
        "SERVICE/DB_POLICY",
        ["status"],
        "APPROVED 후 초품 검사(inspection_kind FIRST_ARTICLE, source_ref = 신고 번호) 합격 확정 시 VERIFIED. 불합격이면 APPROVED 유지·부적합 보고",
        "4M 변경 검증(Q7)",
    ),
]
for t, cols_ in [
    (SC, ["partner_code"]),
    (NCR, ["status", "reported_on"]),
    (CAPA, ["ncr_id"]),
    (CL, ["customer_code", "received_on"]),
    (CA, ["gauge_id"]),
    (SL, ["partner_code"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="FK·목록 조회"))

CHANGED_CONSTRAINTS = [
    c(
        Q + "inspection_spec",
        "CHECK",
        ["inspection_kind", "aql"],
        "inspection_kind IN ('OUTGOING', 'INCOMING') AND (aql IS NULL OR aql > 0)",
        "검사 종류·AQL",
    ),
    uk_partial(
        Q + "inspection_spec",
        ["item_code", "inspection_kind"],
        "status = 'published'",
        "품목·검사 종류당 게시 기준 1개(DSN-14)",
    ),
    c(
        Q + "inspection",
        "CHECK",
        ["inspection_kind", "sampling"],
        f"inspection_kind IN ({q(KINDS)}) AND sampling IN ('AQL', 'MANUAL')",
        "검사 종류·샘플링",
    ),
    c(
        Q + "inspection",
        "CHECK",
        ["sampling", "accept_number", "reject_number"],
        "(sampling = 'MANUAL' AND accept_number IS NULL AND reject_number IS NULL) OR (sampling = 'AQL' AND accept_number >= 0 AND reject_number = accept_number + 1)",
        "AQL Ac/Re",
    ),
    c(
        Q + "inspection",
        "CHECK",
        ["inspection_kind", "partner_code", "source_ref"],
        "(inspection_kind = 'OUTGOING') OR (source_ref IS NOT NULL AND (inspection_kind = 'FIRST_ARTICLE' OR partner_code IS NOT NULL))",
        "종류별 원천·거래처",
    ),
    c(
        Q + "inspection",
        "SERVICE/DB_POLICY",
        ["sampling"],
        "AQL: 로트 크기 → 시료 문자 → 시료 수·Ac/Re를 KS Q ISO 2859-1(일반 수준 II, 보통/강화 1회) 코드 상수 표로 계산. 판정 = 시료 불량 개수 ≤ Ac이면 합격(항목 판정과 함께). 표는 DB가 아니라 코드",
        "AQL 샘플링(Q2)",
    ),
    c(
        Q + "inspection",
        "SERVICE/DB_POLICY",
        ["inspection_kind"],
        "INCOMING 판정 확정 → fs.qms.interface.incoming_results()로 WMS가 읽어 합격 정상 위치·불합격 불량 위치(또는 반품). 불합격이면 보류 + 부적합 보고 + 시정 요구 제안",
        "수입 검사 → WMS(Q1)",
    ),
]
REPLACED = {
    (Q + "inspection", "source IN ('MES', 'MANUAL')"): f"source IN ({q(SOURCES)})",
    (
        Q + "quality_hold",
        "(status = 'held' AND disposition IS NULL AND released_at IS NULL AND release_inspection_id IS NULL AND release_reason IS NULL) OR (status = 'released' AND disposition IN ('REINSPECTED', 'CONCESSION', 'SCRAP') AND released_at IS NOT NULL)",
    ): "(status = 'held' AND disposition IS NULL AND released_at IS NULL AND release_inspection_id IS NULL AND release_reason IS NULL) OR (status = 'released' AND disposition IN ('REINSPECTED', 'CONCESSION', 'SCRAP', 'RETURN') AND released_at IS NOT NULL)",
    (
        Q + "quality_hold",
        "(disposition IS NULL) OR (disposition = 'REINSPECTED' AND release_inspection_id IS NOT NULL) OR (disposition IN ('CONCESSION', 'SCRAP') AND release_inspection_id IS NULL AND release_reason IS NOT NULL AND length(btrim(release_reason)) > 0)",
    ): "(disposition IS NULL) OR (disposition = 'REINSPECTED' AND release_inspection_id IS NOT NULL) OR (disposition IN ('CONCESSION', 'SCRAP', 'RETURN') AND release_inspection_id IS NULL AND release_reason IS NOT NULL AND length(btrim(release_reason)) > 0)",
}
REMOVED = [
    (
        Q + "inspection_spec",
        "UK_PARTIAL",
        "UNIQUE (workspace_id, generation_id, item_code) WHERE status = 'published'",
    )
]

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
    r(SL, ["rating_id"], SR, "근거 평가"),
    r(SC, ["inspection_id"], Q + "inspection", "근거 검사"),
    r(SC, ["ncr_id"], NCR, "근거 부적합"),
    r(NCR, ["defect_type_id"], Q + "defect_type", "불량 유형"),
    r(NCR, ["inspection_id"], Q + "inspection", "근거 검사"),
    r(NCR, ["claim_id"], CL, "근거 클레임"),
    r(CAPA, ["ncr_id"], NCR, "부적합 보고"),
    r(CA, ["gauge_id"], GA, "계측기"),
    r(CN, ["first_article_inspection_id"], Q + "inspection", "초품 검사"),
    r(Q + "inspection_value", ["gauge_id"], GA, "사용 계측기"),
]


def st(t, values, default, transition):
    return dict(
        table=t,
        column="status",
        values=list(values),
        default=default,
        transition=transition,
    )


STATES = [
    st(
        SC,
        ("OPEN", "RESPONDED", "CLOSED"),
        "OPEN",
        "OPEN→RESPONDED(공급처 회신)→CLOSED",
    ),
    st(NCR, ("OPEN", "CLOSED"), "OPEN", "OPEN→CLOSED(CAPA 확인 후)"),
    st(
        CAPA,
        ("OPEN", "DONE", "VERIFIED", "INEFFECTIVE"),
        "OPEN",
        "OPEN→DONE→VERIFIED/INEFFECTIVE(무효면 새 CAPA)",
    ),
    st(
        CL,
        ("RECEIVED", "INVESTIGATING", "RESPONDED", "CLOSED"),
        "RECEIVED",
        "RECEIVED→INVESTIGATING(NCR 생성)→RESPONDED→CLOSED",
    ),
    st(
        GA,
        ("ACTIVE", "REPAIR", "RETIRED"),
        "ACTIVE",
        "ACTIVE↔REPAIR(교정 불합격), →RETIRED",
    ),
    st(
        CN,
        ("REQUESTED", "APPROVED", "REJECTED", "VERIFIED"),
        "REQUESTED",
        "REQUESTED→APPROVED→VERIFIED(초품 합격) / REJECTED",
    ),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn14는 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "wms.pop_import" not in names:
        raise SystemExit("apply_dsn13을 먼저 적용한다")
    if NCR in names:
        return False
    # 아무것도 바꾸기 전에 확인한다(반쯤 적용된 목표 파일을 남기지 않게).
    found = {(x["table"], x["kind"], x["expression"]) for x in d["constraints"]} & set(
        REMOVED
    )
    hits = {(x["table"], x["expression"]) for x in d["constraints"]} & set(REPLACED)
    if len(found) != len(REMOVED) or len(hits) != len(REPLACED):
        raise SystemExit(
            f"바꿀 기존 제약을 찾지 못했다: {set(REMOVED) - found} {set(REPLACED) - hits}"
        )
    tables = {t["name"]: t for t in d["tables"]}
    for name, columns in NEW_COLUMNS.items():
        cols = tables[name]["columns"]
        at = len(cols) - 1 if cols[-1]["name"] == "created_at" else len(cols)
        cols[at:at] = columns
    d["constraints"] = [
        x
        for x in d["constraints"]
        if (x["table"], x["kind"], x["expression"]) not in REMOVED
    ]
    for x in d["constraints"]:
        new = REPLACED.get((x["table"], x["expression"]))
        if new:
            x["expression"] = new
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS + CHANGED_CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    for code in d["code_lists"]:
        if code["target"] == Q + "inspection" and code["column"] == "source":
            code["values"] = list(SOURCES)
        if code["target"] == Q + "quality_hold" and code["column"] == "disposition":
            code["values"] = ["REINSPECTED", "CONCESSION", "SCRAP", "RETURN"]
    d["code_lists"].append(
        dict(
            target=Q + "inspection",
            column="inspection_kind",
            values=list(KINDS),
            default="OUTGOING",
            note="출하 / 수입 / 반품 / 초품",
        )
    )
    d.update(version="target-0.5.0", task="DSN-14", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.5.0",
            task="DSN-14",
            date="2026-10-05",
            change="QMS 보강: 새 테이블 9(공급처 검사 수준·평가·시정 요구, 부적합 보고·CAPA, 고객 클레임, 계측기·교정, 4M 변경), 기존 4테이블 변경(검사 기준 종류·AQL, 검사 종류·샘플링·원천, 검사 값 계측기, 보류 처분에 반품). AQL 표는 코드 상수",
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
    qms = [t for t in d["tables"] if t["name"].startswith(Q)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                qms_tables=len(qms),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
