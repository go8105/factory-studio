"""DSN-29: RWS(신규) 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn28 다음).

근거: docs/modules/rws/RWS_설계_DSN-29.md 4장(rws 12테이블 + 모듈 키 'rws' + CMMS 출처 RWS_REQUEST), 결정 Q1~Q8.
Q1: 텍스트·단계 체크리스트 안내만(영상·AR·사진 없음). Q2: 출처 직접·CMMS 작업지시·QMS 부적합(POP 호출 제외).
Q3: 원격 해결 실패 → FIELD_VISIT, CMMS가 "RWS에서 가져오기"로 작업지시(source = RWS_REQUEST). RWS는 CMMS에 쓰지 않는다.
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
P = "rws."
MODULE_TABLES = {"core.workspace_module", "core.app_review"}
FIELDS = ("EQUIPMENT", "ELECTRIC", "PROCESS", "QUALITY", "IT", "SAFETY")
URGENCY = ("URGENT", "HIGH", "NORMAL")
REQ = ("OPEN", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "FIELD_VISIT", "CANCELLED")
DOC = ("draft", "published", "retired")


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-29"}


def field_col(nullable=False):
    return col(
        "field_code", "분야", "varchar(12)", nullable=nullable, rule=" / ".join(FIELDS)
    )


def check_cols():
    return [
        col(
            "check_kind",
            "확인 방식",
            "varchar(8)",
            rule="CONFIRM 확인 / OKNG 판정 / VALUE 측정값",
        ),
        col("unit", "단위", "varchar(20)", nullable=True),
        col("lower_limit", "하한", "numeric(20,4)", nullable=True),
        col("upper_limit", "상한", "numeric(20,4)", nullable=True),
    ]


EX, EF, SL, RQ, AS, MS, GD, GS, RS, RZ, FB, KN = (
    P + n
    for n in (
        "expert",
        "expert_field",
        "sla_policy",
        "request",
        "assignment",
        "message",
        "guide",
        "guide_step",
        "request_step",
        "resolution",
        "feedback",
        "knowledge",
    )
)

TABLES = [
    table(
        EX,
        "전문가",
        "expert",
        "DSN-29 F11. 내부 = HR 사원 코드, 외부 = 업체 코드 스냅샷(FK 없음). 단계 1~3은 상향 순서",
        [
            col("expert_kind", "구분", "varchar(8)", rule="INTERNAL / EXTERNAL"),
            col("hr_employee_code", "HR 사원 코드", "varchar(30)", nullable=True),
            col(
                "vendor_code",
                "업체 코드",
                "varchar(30)",
                nullable=True,
                rule="ERP 거래처 코드 스냅샷",
            ),
            col("name", "이름", "varchar(60)"),
            col(
                "tier",
                "단계",
                "integer",
                default="1",
                rule="1 일선 / 2 숙련 / 3 최상위",
            ),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        EF,
        "전문가 분야",
        "expert",
        "DSN-29 F11·F12. 배정 추천 기준(분야·숙련도)",
        [
            col("expert_id", "전문가", "bigint"),
            field_col(),
            col("skill", "숙련도", "integer", rule="1~3"),
        ],
    ),
    table(
        SL,
        "목표 시간",
        "expert",
        "DSN-29 F13(Q7). 긴급도별 응답·해결 목표(분). 요청 접수 시 기한을 요청에 스냅샷",
        [
            col("urgency", "긴급도", "varchar(8)", rule=" / ".join(URGENCY)),
            col("respond_minutes", "응답 목표(분)", "integer"),
            col("resolve_minutes", "해결 목표(분)", "integer"),
        ],
    ),
    table(
        RQ,
        "지원 요청",
        "request",
        "DSN-29 F01~F03(Q2·Q4). 대상은 코드 스냅샷. 출처 CMMS 작업지시·QMS 부적합은 조회로 채움(교차 쓰기 없음)",
        [
            col("request_no", "요청 번호", "varchar(30)"),
            col("source_kind", "출처", "varchar(8)", rule="DIRECT / CMMS_WO / QMS_NCR"),
            col(
                "source_ref",
                "출처 번호",
                "varchar(40)",
                nullable=True,
                rule="작업지시·NCR 번호 스냅샷",
            ),
            col(
                "site_kind",
                "현장 구분",
                "varchar(8)",
                rule="INTERNAL 사내 / CUSTOMER 고객 현장(Q4)",
            ),
            col(
                "customer_code",
                "고객사 코드",
                "varchar(30)",
                nullable=True,
                rule="CRM 고객사 스냅샷",
            ),
            col("customer_name", "고객사명", "varchar(100)", nullable=True),
            col("asset_code", "설비 코드", "varchar(40)", nullable=True),
            col("item_code", "품목 코드", "varchar(40)", nullable=True),
            col("lot_no", "LOT 번호", "varchar(40)", nullable=True),
            col(
                "work_order_no",
                "작업지시 번호",
                "varchar(40)",
                nullable=True,
                rule="MES 작업지시 스냅샷",
            ),
            field_col(),
            col("urgency", "긴급도", "varchar(8)", rule=" / ".join(URGENCY)),
            col(
                "symptom_code",
                "증상 코드",
                "varchar(30)",
                nullable=True,
                rule="CMMS 고장 코드 스냅샷 또는 직접",
            ),
            col("title", "제목", "varchar(200)"),
            col("description", "증상 설명", "varchar(2000)"),
            col(
                "requester_hr_code", "요청자 HR 사원 코드", "varchar(30)", nullable=True
            ),
            col("requester_name", "요청자", "varchar(60)"),
            col(
                "status", "상태", "varchar(12)", default="'OPEN'", rule=" / ".join(REQ)
            ),
            col("escalation_level", "상향 단계", "integer", default="1"),
            col("requested_at", "요청 시각", "timestamptz", default="now()"),
            col("respond_due_at", "응답 기한", "timestamptz"),
            col("resolve_due_at", "해결 기한", "timestamptz"),
            col("first_response_at", "첫 응답 시각", "timestamptz", nullable=True),
            col("closed_at", "종료 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        AS,
        "배정",
        "request",
        "DSN-29 F12·F14. 주 담당 1명 + 상향 전문가. 재배정은 해제 후 새 행(추가만)",
        [
            col("request_id", "지원 요청", "bigint"),
            col("expert_id", "전문가", "bigint"),
            col("role", "역할", "varchar(10)", rule="PRIMARY 주 담당 / ESCALATED 상향"),
            col("assigned_at", "배정 시각", "timestamptz", default="now()"),
            col("released_at", "해제 시각", "timestamptz", nullable=True),
            col("reason", "사유", "varchar(200)", nullable=True),
        ],
    ),
    table(
        MS,
        "안내 대화",
        "session",
        "DSN-29 F21. 텍스트 메시지(추가만, 수정·삭제 없음)",
        [
            col("request_id", "지원 요청", "bigint"),
            col("author_kind", "작성자 구분", "varchar(6)", rule="EXPERT / FIELD"),
            col("author_name", "작성자", "varchar(60)"),
            col("body", "내용", "varchar(2000)"),
        ],
    ),
    table(
        GD,
        "작업 가이드",
        "guide",
        "DSN-29 F31·F32(Q5). 코드별 버전, 게시 후 불변, 코드당 게시 1건",
        [
            col("code", "가이드 코드", "varchar(30)"),
            col("version_no", "버전", "integer", default="1"),
            col("title", "제목", "varchar(200)"),
            field_col(),
            col("asset_code", "대상 설비 코드", "varchar(40)", nullable=True),
            col("item_code", "대상 품목 코드", "varchar(40)", nullable=True),
            col(
                "status", "상태", "varchar(10)", default="'draft'", rule=" / ".join(DOC)
            ),
            col("approved_by", "승인자", "varchar(60)", nullable=True),
            col("published_at", "게시 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        GS,
        "가이드 단계",
        "guide",
        "DSN-29 F31. 단계별 지시·주의·확인 방식",
        [
            col("guide_id", "작업 가이드", "bigint"),
            col("step_no", "단계", "integer"),
            col("instruction", "지시", "varchar(1000)"),
            col("caution", "주의", "varchar(500)", nullable=True),
            *check_cols(),
        ],
    ),
    table(
        RS,
        "안내 단계",
        "session",
        "DSN-29 F22·F23. 가이드를 적용하면 단계를 복사(스냅샷), 전문가가 측정 요청을 추가하면 가이드 없이 1행. 현장이 결과 입력",
        [
            col("request_id", "지원 요청", "bigint"),
            col(
                "guide_id",
                "적용 가이드",
                "bigint",
                nullable=True,
                rule="NULL이면 전문가 개별 요청(F23)",
            ),
            col("step_no", "순서", "integer"),
            col("instruction", "지시", "varchar(1000)"),
            *check_cols(),
            col("result", "결과", "varchar(6)", nullable=True, rule="DONE / OK / NG"),
            col("measured_value", "측정값", "numeric(20,4)", nullable=True),
            col("entered_by", "입력자", "varchar(60)", nullable=True),
            col("entered_at", "입력 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        RZ,
        "완료 기록",
        "close",
        "DSN-29 F41·F42(Q3). 요청당 1건, 확정 후 불변. FIELD_VISIT이면 CMMS가 가져가 작업지시",
        [
            col("request_id", "지원 요청", "bigint"),
            col(
                "outcome",
                "결과",
                "varchar(12)",
                rule="REMOTE_FIXED 원격 해결 / FIELD_VISIT 현장 출동 필요",
            ),
            col("cause", "원인", "varchar(1000)"),
            col("action", "조치", "varchar(1000)"),
            col("symptom_code", "증상 코드", "varchar(30)", nullable=True),
            col("field_confirmed", "현장 확인", "boolean", default="false"),
            col("closed_by", "종료자", "varchar(60)"),
        ],
    ),
    table(
        FB,
        "만족도",
        "close",
        "DSN-29 F43(Q7). 종료 후 요청자 평가 1건",
        [
            col("request_id", "지원 요청", "bigint"),
            col("score", "점수", "integer", rule="1~5"),
            col("comment", "의견", "varchar(500)", nullable=True),
        ],
    ),
    table(
        KN,
        "지식 문서",
        "guide",
        "DSN-29 F33(Q6). 완료 요청에서 작성, 설비·증상으로 유사 사례 추천. 게시 후 불변",
        [
            col("request_id", "원 요청", "bigint", nullable=True),
            col("title", "제목", "varchar(200)"),
            field_col(),
            col("asset_code", "설비 코드", "varchar(40)", nullable=True),
            col("symptom_code", "증상 코드", "varchar(30)", nullable=True),
            col("summary", "원인·조치 요약", "varchar(2000)"),
            col("guide_id", "관련 가이드", "bigint", nullable=True),
            col(
                "status", "상태", "varchar(10)", default="'draft'", rule=" / ".join(DOC)
            ),
            col("published_at", "게시 시각", "timestamptz", nullable=True),
        ],
    ),
]

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in (EF, RQ, GD, KN):
    CONSTRAINTS.append(
        c(t, "CHECK", ["field_code"], f"field_code IN ({q(FIELDS)})", "분야")
    )
for t in (GS, RS):
    CONSTRAINTS.append(
        c(
            t,
            "CHECK",
            ["check_kind", "lower_limit", "upper_limit"],
            "check_kind IN ('CONFIRM', 'OKNG', 'VALUE') AND (check_kind = 'VALUE' OR (lower_limit IS NULL AND upper_limit IS NULL)) AND (lower_limit IS NULL OR upper_limit IS NULL OR lower_limit <= upper_limit)",
            "확인 방식·한계",
        )
    )
for t in (GD, KN):
    CONSTRAINTS.append(
        c(
            t,
            "CHECK",
            ["status", "published_at"],
            f"status IN ({q(DOC)}) AND ((status = 'draft') = (published_at IS NULL))",
            "상태·게시 시각",
        )
    )
CONSTRAINTS += [
    c(
        EX,
        "CHECK",
        ["expert_kind", "hr_employee_code", "vendor_code", "tier"],
        "expert_kind IN ('INTERNAL', 'EXTERNAL') AND ((expert_kind = 'INTERNAL') = (hr_employee_code IS NOT NULL)) AND ((expert_kind = 'EXTERNAL') = (vendor_code IS NOT NULL)) AND tier BETWEEN 1 AND 3",
        "내부는 HR 사원 코드, 외부는 업체 코드",
    ),
    uk_partial(
        EX, ["hr_employee_code"], "hr_employee_code IS NOT NULL", "사원당 전문가 1건"
    ),
    c(EF, "UK", S + ["expert_id", "field_code"], reason="전문가·분야 1행"),
    c(EF, "CHECK", ["skill"], "skill BETWEEN 1 AND 3", "숙련도"),
    c(SL, "UK", S + ["urgency"], reason="긴급도당 목표 1건"),
    c(
        SL,
        "CHECK",
        ["urgency", "respond_minutes", "resolve_minutes"],
        f"urgency IN ({q(URGENCY)}) AND respond_minutes > 0 AND resolve_minutes >= respond_minutes",
        "긴급도·목표",
    ),
    c(RQ, "UK", S + ["request_no"], reason="요청 번호 유일"),
    c(
        RQ,
        "CHECK",
        ["request_no", "source_kind", "source_ref"],
        f"request_no {CODE} AND source_kind IN ('DIRECT', 'CMMS_WO', 'QMS_NCR') AND ((source_kind = 'DIRECT') = (source_ref IS NULL))",
        "번호·출처(Q2 — POP 호출 없음)",
    ),
    c(
        RQ,
        "CHECK",
        ["site_kind", "customer_code"],
        "site_kind IN ('INTERNAL', 'CUSTOMER') AND ((site_kind = 'CUSTOMER') = (customer_code IS NOT NULL))",
        "고객 현장은 고객사 필수(Q4)",
    ),
    c(
        RQ,
        "CHECK",
        [
            "urgency",
            "status",
            "escalation_level",
            "closed_at",
            "respond_due_at",
            "resolve_due_at",
        ],
        f"urgency IN ({q(URGENCY)}) AND status IN ({q(REQ)}) AND escalation_level BETWEEN 1 AND 3 AND ((status IN ('RESOLVED', 'FIELD_VISIT', 'CANCELLED')) = (closed_at IS NOT NULL)) AND resolve_due_at >= respond_due_at",
        "상태·종료 시각·기한",
    ),
    uk_partial(
        RQ,
        ["source_kind", "source_ref"],
        "source_kind <> 'DIRECT' AND status <> 'CANCELLED'",
        "출처당 진행 요청 1건",
    ),
    c(
        RQ,
        "SERVICE/DB_POLICY",
        ["respond_due_at", "resolve_due_at"],
        "접수 시 rws.sla_policy(긴급도)로 기한을 계산해 스냅샷. 기한 초과는 조회 표시(저장 안 함). 해결 기한 초과·전문가 요청 시 상향 단계 +1 → 상위 단계 전문가 ESCALATED 배정",
        "목표 시간·상향(Q7)",
    ),
    c(
        RQ,
        "SERVICE/DB_POLICY",
        ["source_ref"],
        "CMMS_WO는 fs.cmms.interface.work_order(no), QMS_NCR는 fs.qms.interface.ncr(no)를 읽어 대상·증상을 채운다. 출처 솔루션에는 쓰지 않는다. POP 호출은 출처가 아니다(POP Q4)",
        "요청 가져오기(Q2)",
    ),
    c(
        AS,
        "CHECK",
        ["role"],
        "role IN ('PRIMARY', 'ESCALATED') AND (released_at IS NULL OR released_at >= assigned_at)",
        "역할·해제",
    ),
    uk_partial(
        AS,
        ["request_id"],
        "role = 'PRIMARY' AND released_at IS NULL",
        "요청당 주 담당 1명",
    ),
    uk_partial(
        AS,
        ["request_id", "expert_id"],
        "released_at IS NULL",
        "같은 전문가 중복 배정 금지",
    ),
    c(
        AS,
        "SERVICE/DB_POLICY",
        ["expert_id"],
        "추천 = 분야 일치 → 숙련도 높은 순 → 진행 건수 적은 순, 사람이 확정. 재배정은 기존 행 해제 + 새 행",
        "배정 추천(F12)",
    ),
    c(
        MS,
        "CHECK",
        ["author_kind", "body"],
        "author_kind IN ('EXPERT', 'FIELD') AND length(btrim(body)) > 0",
        "작성자·내용",
    ),
    c(
        MS,
        "SERVICE/DB_POLICY",
        ["id"],
        "추가만. 첫 EXPERT 메시지 시각 = 요청 first_response_at",
        "대화 불변",
    ),
    c(GD, "UK", S + ["code", "version_no"], reason="코드·버전 유일"),
    c(
        GD,
        "CHECK",
        ["code", "version_no"],
        f"code {CODE} AND version_no >= 1",
        "코드·버전",
    ),
    uk_partial(GD, ["code"], "status = 'published'", "코드당 게시 1건"),
    c(
        GD,
        "SERVICE/DB_POLICY",
        ["status"],
        "게시 후 가이드·단계 불변, 고치면 새 버전 draft → 게시 시 이전 버전 retired. 게시는 승인자 필수",
        "가이드 버전(Q5)",
    ),
    c(GS, "UK", S + ["guide_id", "step_no"], reason="가이드·단계 유일"),
    c(GS, "CHECK", ["step_no"], "step_no >= 1", "단계"),
    c(RS, "UK", S + ["request_id", "step_no"], reason="요청·순서 유일"),
    c(
        RS,
        "CHECK",
        ["step_no", "check_kind", "result", "measured_value", "entered_at"],
        "step_no >= 1 AND (result IS NULL OR result IN ('DONE', 'OK', 'NG')) AND ((result IS NULL) = (entered_at IS NULL)) AND (check_kind = 'VALUE' OR measured_value IS NULL)",
        "결과·측정값",
    ),
    c(
        RS,
        "SERVICE/DB_POLICY",
        ["guide_id"],
        "가이드 적용 = 게시 버전의 단계를 복사(이후 가이드가 바뀌어도 그대로). VALUE는 측정값 필수, 한계 밖이면 결과 NG. 요청 종료 후 입력 불가",
        "안내 단계(F22·F23)",
    ),
    c(RZ, "UK", S + ["request_id"], reason="요청당 완료 기록 1건"),
    c(RZ, "CHECK", ["outcome"], "outcome IN ('REMOTE_FIXED', 'FIELD_VISIT')", "결과"),
    c(
        RZ,
        "SERVICE/DB_POLICY",
        ["outcome"],
        "작성 = 요청 종료(REMOTE_FIXED → RESOLVED, FIELD_VISIT → FIELD_VISIT), 이후 불변. FIELD_VISIT은 fs.rws.interface.field_visit_requests()로 CMMS가 읽어 작업지시(source = RWS_REQUEST)를 만든다 — RWS는 CMMS에 쓰지 않는다",
        "완료·현장 출동(Q3)",
    ),
    c(FB, "UK", S + ["request_id"], reason="요청당 평가 1건"),
    c(FB, "CHECK", ["score"], "score BETWEEN 1 AND 5", "점수"),
    c(
        KN,
        "SERVICE/DB_POLICY",
        ["asset_code", "symptom_code"],
        "새 요청 접수 시 같은 설비 코드 또는 증상 코드의 게시 지식·완료 기록을 최근 순으로 추천(조회)",
        "유사 사례(Q6)",
    ),
]
for t, cols_ in [
    (EF, ["expert_id"]),
    (AS, ["request_id"]),
    (AS, ["expert_id"]),
    (MS, ["request_id"]),
    (GS, ["guide_id"]),
    (RS, ["guide_id"]),
    (FB, ["request_id"]),
    (KN, ["request_id"]),
    (KN, ["guide_id"]),
    (KN, ["asset_code", "symptom_code"]),
    (RQ, ["status", "resolve_due_at"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="조회"))

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
    r(EF, ["expert_id"], EX, "전문가"),
    r(AS, ["request_id"], RQ, "요청"),
    r(AS, ["expert_id"], EX, "전문가"),
    r(MS, ["request_id"], RQ, "요청"),
    r(GS, ["guide_id"], GD, "가이드"),
    r(RS, ["request_id"], RQ, "요청"),
    r(RS, ["guide_id"], GD, "적용 가이드"),
    r(RZ, ["request_id"], RQ, "요청"),
    r(FB, ["request_id"], RQ, "요청"),
    r(KN, ["request_id"], RQ, "원 요청"),
    r(KN, ["guide_id"], GD, "관련 가이드"),
]
STATES = [
    dict(
        table=RQ,
        column="status",
        values=list(REQ),
        default="OPEN",
        transition="OPEN→ASSIGNED→IN_PROGRESS→RESOLVED|FIELD_VISIT; OPEN|ASSIGNED|IN_PROGRESS→CANCELLED",
    ),
    dict(
        table=GD,
        column="status",
        values=list(DOC),
        default="draft",
        transition="draft→published→retired",
    ),
    dict(
        table=KN,
        column="status",
        values=list(DOC),
        default="draft",
        transition="draft→published→retired",
    ),
]

# CMMS 작업지시 출처에 RWS_REQUEST 추가(Q3) — 기존 제약 3개를 찾아 바꾼다
WO = "cmms.work_order"
WO_SRC_OLD = "source IN ('MANUAL', 'BEMS_ALARM', 'SPC_SIGNAL', 'PM_PLAN')"
WO_SRC_NEW = (
    "source IN ('MANUAL', 'BEMS_ALARM', 'SPC_SIGNAL', 'PM_PLAN', 'RWS_REQUEST')"
)
WO_SIG_OLD = "source IN ('BEMS_ALARM', 'SPC_SIGNAL')"
WO_SIG_NEW = "source IN ('BEMS_ALARM', 'SPC_SIGNAL', 'RWS_REQUEST')"


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn29은 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "eip.kpi" not in names:
        raise SystemExit("apply_dsn28을 먼저 적용한다")
    if RQ in names:
        return False
    modules = [
        x
        for x in d["constraints"]
        if x["table"] in MODULE_TABLES
        and x["kind"] == "CHECK"
        and "module_key IN" in x["expression"]
    ]
    wo = [
        x
        for x in d["constraints"]
        if x["table"] == WO
        and (WO_SRC_OLD in x["expression"] or WO_SIG_OLD in x["expression"])
    ]
    if len(modules) != 2 or len(wo) != 3:
        raise SystemExit(
            f"대상이 없다: 모듈 키 CHECK {len(modules)}개, CMMS 출처 제약 {len(wo)}개(3개여야 함)"
        )
    for x in modules:
        x["expression"] = x["expression"].rstrip(")") + ", 'rws')"
    for code in d["code_lists"]:
        if (
            code["target"] in MODULE_TABLES
            and code["column"] == "module_key"
            and "rws" not in code["values"]
        ):
            code["values"] = [*code["values"], "rws"]
    for x in wo:
        x["expression"] = (
            x["expression"]
            .replace(WO_SRC_OLD, WO_SRC_NEW)
            .replace(WO_SIG_OLD, WO_SIG_NEW)
        )
    for code in d["code_lists"]:
        if (
            code["target"] == WO
            and code["column"] == "source"
            and "RWS_REQUEST" not in code["values"]
        ):
            code["values"] = [*code["values"], "RWS_REQUEST"]
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    d.update(version="target-0.17.0", task="DSN-29", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.17.0",
            task="DSN-29",
            date="2026-10-05",
            change="RWS 신규: rws 12테이블(전문가·분야·목표 시간·지원 요청·배정·안내 대화·작업 가이드·가이드 단계·안내 단계·완료 기록·만족도·지식 문서), 모듈 키 rws. cmms.work_order 출처에 RWS_REQUEST(현장 출동 가져오기). 업무 스키마 간 FK 0",
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
    rws = [t for t in d["tables"] if t["name"].startswith(P)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                rws_tables=len(rws),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
