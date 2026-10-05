"""DSN-24: PLM(신규) 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn23 다음).

근거: docs/modules/plm/PLM_설계_DSN-24.md 4장(plm 16테이블 + 모듈 키 'plm'), 결정 Q1~Q7.
배포(RELEASED)는 ECO로만, 품목당 현재 배포 리비전 1개, 배포 리비전·BOM 불변. 다른 솔루션은 가져오기(Q1).
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
L = "plm."
MODULE_TABLES = {"core.workspace_module", "core.app_review"}
REV = ("WORKING", "REVIEW", "RELEASED", "OBSOLETE")
VER = ("draft", "confirmed", "superseded")


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-24"}


PC, PA, PR, DO, DR, PD, BL, SU, ECR, ECO, EI, PJ, GA, GD, CR, CRL = (
    L + "part_class",
    L + "part",
    L + "part_revision",
    L + "document",
    L + "document_revision",
    L + "part_document",
    L + "bom_line",
    L + "substitute",
    L + "ecr",
    L + "eco",
    L + "eco_item",
    L + "project",
    L + "gate",
    L + "gate_deliverable",
    L + "cost_rollup",
    L + "cost_rollup_line",
)

TABLES = [
    table(
        PC,
        "부품 분류",
        "part",
        "DSN-24 F05. 대·중·소 분류(자기 참조)",
        [
            col("code", "분류 코드", "varchar(30)"),
            col("name", "분류명", "varchar(100)"),
            col("parent_id", "상위 분류", "bigint", nullable=True),
        ],
    ),
    table(
        PA,
        "설계 품목",
        "part",
        "DSN-24 F01. 부품 번호는 MES·ERP·WMS·QMS 품목 코드의 원천(가져오기 때 같은 코드)",
        [
            col("part_no", "부품 번호", "varchar(40)"),
            col("name", "품목명", "varchar(200)"),
            col("class_id", "분류", "bigint", nullable=True),
            col("unit", "단위", "varchar(10)"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        PR,
        "품목 리비전",
        "part",
        "DSN-24 F02·F03. 작업 중 → 검토 → 배포(ECO로만) → 폐기. 배포 후 불변, 품목당 현재 배포 1개",
        [
            col("part_id", "설계 품목", "bigint"),
            col("rev", "리비전", "varchar(4)", rule="A, B, … Z, AA …"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'WORKING'",
                rule=" / ".join(REV),
            ),
            col("material", "재질", "varchar(60)", nullable=True),
            col("unit_weight_kg", "단위 중량(kg)", "numeric(12,4)", nullable=True),
            col("dimensions", "치수", "varchar(100)", nullable=True),
            col("color", "색상", "varchar(30)", nullable=True),
            col("surface", "표면 처리", "varchar(60)", nullable=True),
            col("spec_note", "사양 메모", "varchar(500)", nullable=True),
            col("eco_id", "배포 ECO", "bigint", nullable=True),
            col("released_at", "배포 시각", "timestamptz", nullable=True),
            col("obsoleted_at", "폐기 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        DO,
        "도면·문서",
        "document",
        "DSN-24 F04(Q2). 메타데이터만 — 파일 첨부 없음",
        [
            col("doc_no", "문서 번호", "varchar(40)"),
            col("title", "제목", "varchar(200)"),
            col(
                "doc_kind",
                "종류",
                "varchar(10)",
                rule="DRAWING 도면 / SPEC 사양서 / STANDARD 표준 / OTHER",
            ),
        ],
    ),
    table(
        DR,
        "문서 리비전",
        "document",
        "DSN-24 F04. 품목 리비전과 같은 상태·불변 규칙",
        [
            col("document_id", "도면·문서", "bigint"),
            col("rev", "리비전", "varchar(4)"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'WORKING'",
                rule=" / ".join(REV),
            ),
            col("description", "변경 내용", "varchar(500)", nullable=True),
            col("eco_id", "배포 ECO", "bigint", nullable=True),
            col("released_at", "배포 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        PD,
        "품목 문서 연결",
        "document",
        "DSN-24 F04. 품목 리비전 ↔ 문서 리비전(여러 대 여러)",
        [
            col("part_revision_id", "품목 리비전", "bigint"),
            col("document_revision_id", "문서 리비전", "bigint"),
        ],
    ),
    table(
        BL,
        "E-BOM 구성",
        "bom",
        "DSN-24 F11. 상위 품목 리비전의 하위 품목·수량. 하위는 품목(전개 시 현재 배포 리비전). 상위 배포 후 불변",
        [
            col("parent_revision_id", "상위 품목 리비전", "bigint"),
            col("line_no", "행 번호", "integer"),
            col("child_part_id", "하위 품목", "bigint"),
            col("qty", "수량", "numeric(18,6)"),
            col("unit", "단위", "varchar(10)"),
            col("note", "메모", "varchar(300)", nullable=True),
        ],
    ),
    table(
        SU,
        "대체 부품",
        "bom",
        "DSN-24 F14. 설계 승인 대체품. MES 대체 자재(DSN-12 F16)의 원천",
        [
            col("bom_line_id", "E-BOM 구성", "bigint"),
            col("substitute_part_id", "대체 품목", "bigint"),
            col("priority", "우선순위", "integer", default="1"),
            col("note", "메모", "varchar(300)", nullable=True),
        ],
    ),
    table(
        ECR,
        "설계 변경 요청",
        "change",
        "DSN-24 F21. 사유·대상·제안 → 수락(ECO로)·반려",
        [
            col("ecr_no", "요청 번호", "varchar(40)"),
            col("title", "제목", "varchar(200)"),
            col("reason", "사유", "varchar(1000)"),
            col("requested_by", "요청자", "varchar(60)"),
            col("requested_on", "요청일", "date"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'OPEN'",
                rule="OPEN / ACCEPTED / REJECTED",
            ),
            col("decided_at", "결정 시각", "timestamptz", nullable=True),
            col("decision_note", "결정 의견", "varchar(500)", nullable=True),
        ],
    ),
    table(
        ECO,
        "설계 변경 지시",
        "change",
        "DSN-24 F22~F26(Q3). 대상 리비전 묶음 → 검토 → 승인 → 배포(대상 일괄 RELEASED, 이전 OBSOLETE). QMS가 배포를 읽어 4M 후보",
        [
            col("eco_no", "지시 번호", "varchar(40)"),
            col("ecr_id", "변경 요청", "bigint", nullable=True),
            col("title", "제목", "varchar(200)"),
            col("description", "변경 내용", "varchar(1000)"),
            col(
                "effective_on",
                "적용일",
                "date",
                nullable=True,
                rule="NULL이면 배포 즉시",
            ),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'DRAFT'",
                rule="DRAFT / REVIEW / APPROVED / RELEASED / CANCELLED",
            ),
            col("reviewer_name", "검토자", "varchar(60)", nullable=True),
            col("approved_at", "승인 시각", "timestamptz", nullable=True),
            col("released_at", "배포 시각", "timestamptz", nullable=True),
            col(
                "impact_note",
                "영향 분석",
                "varchar(1000)",
                nullable=True,
                rule="역전개 상위 품목·진행 작업지시 수 스냅샷",
            ),
            col("cancel_reason", "취소 사유", "varchar(300)", nullable=True),
        ],
    ),
    table(
        EI,
        "변경 대상",
        "change",
        "DSN-24 F22. ECO가 배포할 품목·문서 리비전(작업 중·검토 상태)",
        [
            col("eco_id", "설계 변경 지시", "bigint"),
            col("part_revision_id", "품목 리비전", "bigint", nullable=True),
            col("document_revision_id", "문서 리비전", "bigint", nullable=True),
            col("change_note", "변경 메모", "varchar(300)", nullable=True),
        ],
    ),
    table(
        PJ,
        "개발 프로젝트",
        "project",
        "DSN-24 F31(Q5). 신제품 개발 대상 품목·담당·일정",
        [
            col("project_no", "프로젝트 번호", "varchar(40)"),
            col("name", "프로젝트명", "varchar(200)"),
            col("target_part_id", "대상 품목", "bigint", nullable=True),
            col("owner_name", "담당", "varchar(60)"),
            col("start_on", "시작일", "date"),
            col("target_on", "양산 목표일", "date"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'ACTIVE'",
                rule="ACTIVE / ON_HOLD / DONE / CANCELLED",
            ),
        ],
    ),
    table(
        GA,
        "단계 게이트",
        "project",
        "DSN-24 F32(Q5). 기획 → 설계 → 시작 → 양산 승인. 앞 게이트 통과 후 다음",
        [
            col("project_id", "개발 프로젝트", "bigint"),
            col(
                "gate_kind", "게이트", "varchar(6)", rule="PLAN / DESIGN / PROTO / MASS"
            ),
            col("seq", "순서", "integer"),
            col("planned_on", "계획일", "date"),
            col(
                "status",
                "상태",
                "varchar(6)",
                default="'OPEN'",
                rule="OPEN / PASSED / FAILED",
            ),
            col("decided_at", "판정 시각", "timestamptz", nullable=True),
            col("note", "판정 의견", "varchar(500)", nullable=True),
        ],
    ),
    table(
        GD,
        "게이트 산출물",
        "project",
        "DSN-24 F32. 게이트 통과 = 필수 산출물 모두 완료",
        [
            col("gate_id", "단계 게이트", "bigint"),
            col("seq", "순서", "integer"),
            col("name", "산출물", "varchar(200)"),
            col("is_required", "필수", "boolean", default="true"),
            col("done_at", "완료 시각", "timestamptz", nullable=True),
            col("document_revision_id", "근거 문서", "bigint", nullable=True),
        ],
    ),
    table(
        CR,
        "설계 원가",
        "cost",
        "DSN-24 F43(Q6). 품목 리비전 E-BOM 전개 × ERP 표준 단가 스냅샷. 확정 1건 + 새 버전",
        [
            col("part_revision_id", "품목 리비전", "bigint"),
            col("version", "버전", "integer"),
            col(
                "status", "상태", "varchar(12)", default="'draft'", rule=" / ".join(VER)
            ),
            col("material_cost", "재료비 합", "numeric(18,2)"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col("missing_price_count", "단가 없는 부품 수", "integer", default="0"),
            col("calculated_at", "계산 시각", "timestamptz"),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        CRL,
        "설계 원가 명세",
        "cost",
        "DSN-24 F43. 전개 말단 부품별 누적 수량 × 단가",
        [
            col("cost_rollup_id", "설계 원가", "bigint"),
            col("part_id", "부품", "bigint"),
            col("level", "전개 단계", "integer"),
            col("extended_qty", "누적 수량", "numeric(18,6)"),
            col(
                "unit_cost",
                "단가",
                "numeric(18,4)",
                nullable=True,
                rule="ERP 표준 단가 스냅샷, 없으면 NULL",
            ),
            col("cost", "금액", "numeric(18,2)", nullable=True),
        ],
    ),
]

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t, field in [
    (PC, "code"),
    (PA, "part_no"),
    (DO, "doc_no"),
    (ECR, "ecr_no"),
    (ECO, "eco_no"),
    (PJ, "project_no"),
]:
    CONSTRAINTS += [
        c(t, "UK", S + [field], reason="세대 내 번호 유일"),
        c(t, "CHECK", [field], f"{field} {CODE}", "번호 형식"),
    ]
for t, parent in [(PR, "part_id"), (DR, "document_id")]:
    CONSTRAINTS += [
        c(t, "UK", S + [parent, "rev"], reason="리비전 유일"),
        c(t, "CHECK", ["rev"], "rev ~ '^[A-Z]{1,2}$'", "리비전 형식"),
        c(
            t,
            "CHECK",
            ["status", "eco_id", "released_at"],
            f"status IN ({q(REV)}) AND ((status IN ('RELEASED', 'OBSOLETE')) = (released_at IS NOT NULL AND eco_id IS NOT NULL))",
            "배포는 ECO로만",
        ),
        uk_partial(t, [parent], "status = 'RELEASED'", "현재 배포 리비전 1개"),
    ]
CONSTRAINTS += [
    c(
        PC,
        "CHECK",
        ["parent_id"],
        "parent_id IS NULL OR parent_id <> id",
        "자기 참조 금지",
    ),
    c(
        PR,
        "CHECK",
        ["status", "obsoleted_at"],
        "(status = 'OBSOLETE') = (obsoleted_at IS NOT NULL)",
        "폐기 시각",
    ),
    c(
        PR,
        "CHECK",
        ["unit_weight_kg"],
        "unit_weight_kg IS NULL OR unit_weight_kg >= 0",
        "중량 음수 금지",
    ),
    c(
        PR,
        "SERVICE/DB_POLICY",
        ["status"],
        "WORKING·REVIEW만 수정. ECO 배포 시 대상 리비전 RELEASED + 같은 품목의 이전 RELEASED → OBSOLETE(한 트랜잭션). 배포 리비전·그 E-BOM·문서 연결은 불변, 변경은 새 리비전",
        "리비전 불변(F02)",
    ),
    c(
        DO,
        "CHECK",
        ["doc_kind"],
        "doc_kind IN ('DRAWING', 'SPEC', 'STANDARD', 'OTHER')",
        "문서 종류",
    ),
    c(PD, "UK", S + ["part_revision_id", "document_revision_id"], reason="연결 1건"),
    c(BL, "UK", S + ["parent_revision_id", "line_no"], reason="행 번호 유일"),
    c(
        BL,
        "UK",
        S + ["parent_revision_id", "child_part_id"],
        reason="같은 하위 품목 1행",
    ),
    c(BL, "CHECK", ["line_no", "qty"], "line_no >= 1 AND qty > 0", "행 번호·수량"),
    c(
        BL,
        "SERVICE/DB_POLICY",
        ["child_part_id"],
        "하위 품목이 상위 품목(전개 경로 포함)과 같으면 거부(순환 금지). 전개·역전개·리비전 비교는 조회 계산",
        "순환 금지·전개",
    ),
    c(SU, "UK", S + ["bom_line_id", "substitute_part_id"], reason="구성·대체 1회"),
    c(SU, "CHECK", ["priority"], "priority >= 1", "우선순위"),
    c(
        ECR,
        "CHECK",
        ["status", "decided_at"],
        "status IN ('OPEN', 'ACCEPTED', 'REJECTED') AND ((status = 'OPEN') = (decided_at IS NULL))",
        "상태·결정 시각",
    ),
    c(
        ECO,
        "CHECK",
        ["status"],
        "status IN ('DRAFT', 'REVIEW', 'APPROVED', 'RELEASED', 'CANCELLED')",
        "상태 값",
    ),
    c(
        ECO,
        "CHECK",
        ["status", "approved_at", "released_at", "reviewer_name", "cancel_reason"],
        "((status IN ('APPROVED', 'RELEASED')) = (approved_at IS NOT NULL AND reviewer_name IS NOT NULL)) AND ((status = 'RELEASED') = (released_at IS NOT NULL)) AND (status <> 'CANCELLED' OR length(btrim(cancel_reason)) > 0) AND (released_at IS NULL OR released_at >= approved_at)",
        "상태별 승인·배포",
    ),
    c(
        ECO,
        "SERVICE/DB_POLICY",
        ["status"],
        "배포 = 대상 리비전 모두 RELEASED(이전 OBSOLETE). 배포 후 불변. QMS는 fs.plm.interface.eco_releases(since)로 읽어 4M 변경 신고 후보(PLM = 설계 변경, QMS = 현장 변경·초품, Q3). GW 결재 상태는 fs.gw.interface 배지만",
        "ECO 배포·연계(Q3)",
    ),
    c(
        EI,
        "CHECK",
        ["part_revision_id", "document_revision_id"],
        "(part_revision_id IS NULL) <> (document_revision_id IS NULL)",
        "대상 하나",
    ),
    uk_partial(
        EI,
        ["part_revision_id"],
        "part_revision_id IS NOT NULL",
        "품목 리비전은 ECO 1건에만",
    ),
    uk_partial(
        EI,
        ["document_revision_id"],
        "document_revision_id IS NOT NULL",
        "문서 리비전은 ECO 1건에만",
    ),
    c(
        PJ,
        "CHECK",
        ["status", "start_on", "target_on"],
        "status IN ('ACTIVE', 'ON_HOLD', 'DONE', 'CANCELLED') AND target_on >= start_on",
        "상태·일정",
    ),
    c(GA, "UK", S + ["project_id", "gate_kind"], reason="프로젝트·게이트 1건"),
    c(
        GA,
        "CHECK",
        ["gate_kind", "seq", "status", "decided_at"],
        "gate_kind IN ('PLAN', 'DESIGN', 'PROTO', 'MASS') AND seq BETWEEN 1 AND 4 AND status IN ('OPEN', 'PASSED', 'FAILED') AND ((status = 'OPEN') = (decided_at IS NULL))",
        "게이트·순서·판정",
    ),
    c(
        GA,
        "SERVICE/DB_POLICY",
        ["status"],
        "통과 = 필수 산출물 모두 완료 + 앞 게이트 PASSED. FAILED면 같은 게이트를 다시 OPEN(재판정)할 수 있다",
        "게이트 판정(Q5)",
    ),
    c(GD, "UK", S + ["gate_id", "seq"], reason="게이트·순서 유일"),
    c(CR, "UK", S + ["part_revision_id", "version"], reason="리비전·버전 유일"),
    c(
        CR,
        "CHECK",
        [
            "status",
            "version",
            "confirmed_at",
            "material_cost",
            "missing_price_count",
            "currency",
        ],
        "status IN ('draft', 'confirmed', 'superseded') AND version >= 1 AND ((status = 'draft') = (confirmed_at IS NULL)) AND material_cost >= 0 AND missing_price_count >= 0 AND currency = 'KRW'",
        "상태·값",
    ),
    uk_partial(
        CR, ["part_revision_id"], "status = 'confirmed'", "리비전당 확정 원가 1건"
    ),
    c(
        CR,
        "SERVICE/DB_POLICY",
        ["material_cost"],
        "E-BOM을 말단까지 전개(하위는 현재 배포 리비전), 누적 수량 × ERP 표준 단가(fs.erp.interface 조회). 단가 없는 부품은 개수만 세고 합에서 제외. 확정 후 불변",
        "설계 원가 롤업(Q6)",
    ),
    c(CRL, "UK", S + ["cost_rollup_id", "part_id"], reason="원가·부품 1행"),
    c(
        CRL,
        "CHECK",
        ["level", "extended_qty", "unit_cost", "cost"],
        "level >= 1 AND extended_qty > 0 AND (unit_cost IS NULL OR unit_cost >= 0) AND ((unit_cost IS NULL) = (cost IS NULL))",
        "전개 값",
    ),
]
for t, cols_ in [
    (PR, ["part_id"]),
    (BL, ["child_part_id"]),
    (EI, ["eco_id"]),
    (GA, ["project_id"]),
    (CRL, ["cost_rollup_id"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="FK·역전개 조회"))

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
    r(PC, ["parent_id"], PC, "상위 분류"),
    r(PA, ["class_id"], PC, "분류"),
    r(PR, ["part_id"], PA, "설계 품목"),
    r(PR, ["eco_id"], ECO, "배포 ECO"),
    r(DR, ["document_id"], DO, "도면·문서"),
    r(DR, ["eco_id"], ECO, "배포 ECO"),
    r(PD, ["part_revision_id"], PR, "품목 리비전"),
    r(PD, ["document_revision_id"], DR, "문서 리비전"),
    r(BL, ["parent_revision_id"], PR, "상위 품목 리비전"),
    r(BL, ["child_part_id"], PA, "하위 품목"),
    r(SU, ["bom_line_id"], BL, "E-BOM 구성"),
    r(SU, ["substitute_part_id"], PA, "대체 품목"),
    r(ECO, ["ecr_id"], ECR, "변경 요청"),
    r(EI, ["eco_id"], ECO, "설계 변경 지시"),
    r(EI, ["part_revision_id"], PR, "품목 리비전"),
    r(EI, ["document_revision_id"], DR, "문서 리비전"),
    r(PJ, ["target_part_id"], PA, "대상 품목"),
    r(GA, ["project_id"], PJ, "개발 프로젝트"),
    r(GD, ["gate_id"], GA, "단계 게이트"),
    r(GD, ["document_revision_id"], DR, "근거 문서"),
    r(CR, ["part_revision_id"], PR, "품목 리비전"),
    r(CRL, ["cost_rollup_id"], CR, "설계 원가"),
    r(CRL, ["part_id"], PA, "부품"),
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
        PR, REV, "WORKING", "WORKING→REVIEW→RELEASED(ECO 배포)→OBSOLETE(새 리비전 배포)"
    ),
    st(DR, REV, "WORKING", "WORKING→REVIEW→RELEASED(ECO 배포)→OBSOLETE"),
    st(
        ECR,
        ("OPEN", "ACCEPTED", "REJECTED"),
        "OPEN",
        "OPEN→ACCEPTED(ECO 생성)/REJECTED",
    ),
    st(
        ECO,
        ("DRAFT", "REVIEW", "APPROVED", "RELEASED", "CANCELLED"),
        "DRAFT",
        "DRAFT→REVIEW→APPROVED→RELEASED; 배포 전 CANCELLED",
    ),
    st(
        PJ,
        ("ACTIVE", "ON_HOLD", "DONE", "CANCELLED"),
        "ACTIVE",
        "ACTIVE↔ON_HOLD, →DONE(양산 승인)/CANCELLED",
    ),
    st(
        GA,
        ("OPEN", "PASSED", "FAILED"),
        "OPEN",
        "OPEN→PASSED/FAILED; FAILED→OPEN(재판정)",
    ),
    st(CR, VER, "draft", "draft→confirmed→superseded"),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn24는 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "tms.dispatch" not in names:
        raise SystemExit("apply_dsn23을 먼저 적용한다")
    if ECO in names:
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
        x["expression"] = x["expression"].rstrip(")") + ", 'plm')"
    for code in d["code_lists"]:
        if (
            code["target"] in MODULE_TABLES
            and code["column"] == "module_key"
            and "plm" not in code["values"]
        ):
            code["values"] = [*code["values"], "plm"]
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    d.update(version="target-0.12.0", task="DSN-24", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.12.0",
            task="DSN-24",
            date="2026-10-05",
            change="PLM 신규: plm 16테이블(분류·설계 품목·리비전·도면/문서·문서 리비전·연결·E-BOM·대체 부품·ECR·ECO·변경 대상·개발 프로젝트·게이트·산출물·설계 원가·명세), 모듈 키 plm. 업무 스키마 간 FK 0",
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
    plm = [t for t in d["tables"] if t["name"].startswith(L)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                plm_tables=len(plm),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
