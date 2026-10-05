"""DSN-28: EIP(신규) 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn27 다음).

근거: docs/modules/eip/EIP_설계_DSN-28.md 4장(eip 8테이블 + 사람 연결 칸), 결정 Q1~Q8. 모듈 키 'eip'는 두지 않는다(Q8: 포털 첫 화면 = EIP, 끌 수 없음).
Q3·Q3-1: "내 할 일"은 HR 사원 코드 기준 — HR 코드가 없던 사람 마스터(GW 담당자·CRM 담당자·ELB 신청자/승인자·QMS CAPA 담당)에 칸 추가.
Q5: 위젯 배치는 eip 스키마(core에는 대시보드 배치를 두지 않는다 — FS-008b).
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
P = "eip."
VER = ("draft", "confirmed", "superseded")
HR = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-28"}


def actor():
    return [
        col(
            "actor_kind", "사용자 구분", "varchar(6)", rule="MEMBER 회원 / GUEST 게스트"
        ),
        col(
            "actor_key",
            "사용자 키",
            "varchar(80)",
            rule="회원: core 사용자 id, 게스트: 게스트 행위자 키(FK 없음)",
        ),
    ]


KP, KT, PL, WL, FV, MR, RL, RC = (
    P + "kpi",
    P + "kpi_target",
    P + "person_link",
    P + "widget_layout",
    P + "favorite",
    P + "management_report",
    P + "report_line",
    P + "report_comment",
)

TABLES = [
    table(
        KP,
        "KPI",
        "kpi",
        "DSN-28 F11(Q2). 출처 솔루션 월 요약의 지표 키를 가리키는 정의. 실적은 조회(저장 안 함)",
        [
            col("code", "KPI 코드", "varchar(30)"),
            col("name", "KPI명", "varchar(100)"),
            col(
                "source_module", "출처 솔루션", "varchar(10)", rule="모듈 키(mes·erp·…)"
            ),
            col(
                "metric_key",
                "지표 키",
                "varchar(60)",
                rule="그 솔루션 monthly_summary의 키",
            ),
            col("unit", "단위", "varchar(20)"),
            col("better", "좋은 방향", "varchar(6)", rule="HIGHER / LOWER"),
            col("display_order", "표시 순서", "integer"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        KT,
        "KPI 월 목표",
        "kpi",
        "DSN-28 F12(Q2). KPI·월당 목표 1건",
        [
            col("kpi_id", "KPI", "bigint"),
            col("target_month", "목표 월", "varchar(7)", rule="'YYYY-MM'"),
            col("target_value", "목표값", "numeric(20,4)"),
        ],
    ),
    table(
        PL,
        "사람 연결",
        "person",
        "DSN-28 F21(Q3·Q3-1). 로그인 사용자(회원) 또는 게스트가 고른 체험 사람 ↔ HR 사원 코드. 각 솔루션은 이 코드로 할 일을 돌려준다",
        [
            *actor(),
            col("hr_employee_code", "HR 사원 코드", "varchar(30)"),
            col("display_name", "표시 이름", "varchar(60)"),
        ],
    ),
    table(
        WL,
        "위젯 배치",
        "personal",
        "DSN-28 F04(Q5). 사용자별 대시보드 카드 선택·순서. 없으면 기본 배치. core에는 두지 않는다(FS-008b)",
        [
            *actor(),
            col(
                "widget_code",
                "위젯 코드",
                "varchar(40)",
                rule="코드 상수 목록(요약 카드·KPI·할 일·공지·추이)",
            ),
            col("seq", "순서", "integer"),
            col("is_visible", "표시", "boolean", default="true"),
        ],
    ),
    table(
        FV,
        "즐겨찾는 화면",
        "personal",
        "DSN-28 F42. 솔루션·화면 경로 바로가기",
        [
            *actor(),
            col("module_key", "솔루션", "varchar(10)"),
            col("path", "화면 경로", "varchar(200)"),
            col("label", "표시 이름", "varchar(60)"),
            col("seq", "순서", "integer"),
        ],
    ),
    table(
        MR,
        "월간 경영 보고서",
        "report",
        "DSN-28 F31(Q4). 모든 솔루션 요약 + KPI 달성 확정 스냅샷. 재작성은 새 버전",
        [
            col("report_month", "보고 월", "varchar(7)", rule="'YYYY-MM'"),
            col("version", "버전", "integer"),
            col(
                "status", "상태", "varchar(12)", default="'draft'", rule=" / ".join(VER)
            ),
            col("headline", "총평", "varchar(1000)", nullable=True),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        RL,
        "보고서 지표",
        "report",
        "DSN-28 F31. 지표별 값·목표·달성률 스냅샷(KPI 또는 솔루션 요약 지표). 꺼진 솔루션은 값 없음",
        [
            col("report_id", "월간 경영 보고서", "bigint"),
            col("line_no", "순서", "integer"),
            col("module_key", "솔루션", "varchar(10)"),
            col("metric_key", "지표 키", "varchar(60)"),
            col("label", "지표명", "varchar(100)"),
            col(
                "value",
                "값",
                "numeric(20,4)",
                nullable=True,
                rule="NULL이면 솔루션 꺼짐·조회 실패",
            ),
            col("target_value", "목표", "numeric(20,4)", nullable=True),
            col("unit", "단위", "varchar(20)"),
            col("kpi_id", "KPI", "bigint", nullable=True),
        ],
    ),
    table(
        RC,
        "경영 의견",
        "report",
        "DSN-28 F32(Q4). 보고서 지표별 의견·조치. 확정 전까지 수정",
        [
            col("report_id", "월간 경영 보고서", "bigint"),
            col(
                "report_line_id",
                "보고서 지표",
                "bigint",
                nullable=True,
                rule="NULL이면 보고서 전체 의견",
            ),
            col("author_name", "작성자", "varchar(60)"),
            col("comment", "의견", "varchar(1000)"),
            col("action", "조치", "varchar(500)", nullable=True),
            col("due_on", "조치 기한", "date", nullable=True),
        ],
    ),
]

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in (PL, WL, FV):
    CONSTRAINTS.append(
        c(
            t,
            "CHECK",
            ["actor_kind", "actor_key"],
            "actor_kind IN ('MEMBER', 'GUEST') AND length(btrim(actor_key)) > 0",
            "사용자 구분·키",
        )
    )
CONSTRAINTS += [
    c(KP, "UK", S + ["code"], reason="KPI 코드 유일"),
    c(
        KP,
        "CHECK",
        ["code", "better", "display_order"],
        f"code {CODE} AND better IN ('HIGHER', 'LOWER') AND display_order >= 1",
        "코드·방향·순서",
    ),
    c(KP, "UK", S + ["source_module", "metric_key"], reason="같은 지표 KPI 1개"),
    c(KT, "UK", S + ["kpi_id", "target_month"], reason="KPI·월 목표 1건"),
    c(
        KT,
        "CHECK",
        ["target_month"],
        "target_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'",
        "'YYYY-MM' 형식",
    ),
    c(
        KP,
        "SERVICE/DB_POLICY",
        ["metric_key"],
        "실적 = fs.<source_module>.interface.monthly_summary(month)[metric_key](조회, 저장 안 함). 달성률 = 실적 ÷ 목표(LOWER면 목표 ÷ 실적). 솔루션 꺼짐이면 '꺼짐'",
        "KPI 실적 조회(Q2)",
    ),
    c(PL, "UK", S + ["actor_kind", "actor_key"], reason="사용자당 사람 연결 1건"),
    c(PL, "CHECK", ["hr_employee_code"], f"hr_employee_code {HR}", "HR 사원 코드 형식"),
    c(
        PL,
        "SERVICE/DB_POLICY",
        ["hr_employee_code"],
        "회원은 관리자가 연결, 게스트는 체험 사람(HR 사원)을 골라 연결. 할 일 = 각 솔루션 pending_tasks(hr_employee_code)(건수·바로가기). 사람 원천은 HR(D79), 각 솔루션 사람 마스터는 HR 사원 코드 스냅샷(DSN-28 Q3-1)",
        "사람별 할 일(Q3)",
    ),
    c(
        WL,
        "UK",
        S + ["actor_kind", "actor_key", "widget_code"],
        reason="사용자·위젯 1행",
    ),
    c(WL, "CHECK", ["seq"], "seq >= 1", "순서"),
    c(
        FV,
        "UK",
        S + ["actor_kind", "actor_key", "module_key", "path"],
        reason="사용자·화면 1건",
    ),
    c(FV, "CHECK", ["seq", "path"], "seq >= 1 AND path ~ '^/'", "순서·경로"),
    c(MR, "UK", S + ["report_month", "version"], reason="월·버전 유일"),
    c(
        MR,
        "CHECK",
        ["report_month"],
        "report_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'",
        "'YYYY-MM' 형식",
    ),
    c(
        MR,
        "CHECK",
        ["status", "version", "confirmed_at"],
        "status IN ('draft', 'confirmed', 'superseded') AND version >= 1 AND ((status = 'draft') = (confirmed_at IS NULL))",
        "상태·버전",
    ),
    uk_partial(MR, ["report_month"], "status = 'confirmed'", "월당 확정 보고서 1건"),
    c(
        MR,
        "SERVICE/DB_POLICY",
        ["status"],
        "작성 시 모든 켜진 솔루션 monthly_summary + KPI 실적을 지표 행으로 스냅샷. 확정 후 지표·의견 불변, 재작성은 새 버전",
        "경영 보고서 확정(Q4)",
    ),
    c(RL, "UK", S + ["report_id", "line_no"], reason="보고서·순서 유일"),
    c(
        RL,
        "UK",
        S + ["report_id", "module_key", "metric_key"],
        reason="보고서·지표 1행",
    ),
    c(RC, "CHECK", ["comment"], "length(btrim(comment)) >= 2", "의견 필수"),
]
for t, cols_ in [(KT, ["kpi_id"]), (RL, ["report_id"]), (RC, ["report_id"])]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="FK 조회"))

# 다른 스키마: 사람 연결 칸(Q3-1) — HR 사원 코드 스냅샷, FK 없음
EXT_COLUMNS = {
    "gw.person": [
        col(
            "hr_employee_code",
            "HR 사원 코드",
            "varchar(30)",
            nullable=True,
            rule="DSN-28 Q3-1 사람 연결(스냅샷)",
        )
    ],
    "crm.sales_rep": [
        col(
            "hr_employee_code",
            "HR 사원 코드",
            "varchar(30)",
            nullable=True,
            rule="DSN-28 Q3-1",
        )
    ],
    "elb.request": [
        col(
            "requester_hr_code",
            "신청자 HR 사원 코드",
            "varchar(30)",
            nullable=True,
            rule="DSN-28 Q3-1",
        )
    ],
    "elb.approval": [
        col(
            "approver_hr_code",
            "승인자 HR 사원 코드",
            "varchar(30)",
            nullable=True,
            rule="DSN-28 Q3-1",
        )
    ],
    "qms.capa": [
        col(
            "owner_hr_code",
            "담당 HR 사원 코드",
            "varchar(30)",
            nullable=True,
            rule="DSN-28 Q3-1",
        )
    ],
}
EA = "elb.approver"
EXT_TABLES = [
    {
        **_table(
            EA,
            "승인자 지정",
            "approval",
            "DSN-28 Q3-1. 승인 역할(부서장·관리부서)을 맡는 사람. 부서 코드 NULL이면 전사(관리부서). 승인 대기 할 일의 근거",
            [
                col(
                    "approver_role",
                    "승인 역할",
                    "varchar(12)",
                    rule="DEPT_HEAD / ADMIN_DEPT",
                ),
                col("department_code", "부서 코드", "varchar(30)", nullable=True),
                col("hr_employee_code", "HR 사원 코드", "varchar(30)"),
                col("name", "이름", "varchar(60)"),
                col("is_active", "사용 여부", "boolean", default="true"),
            ],
        ),
        "phase": "DSN-28",
    },
]
EXT_CONSTRAINTS = [
    c(EA, "PK", ["id"], reason="기본키"),
    c(EA, "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    c(
        EA,
        "CHECK",
        ["approver_role", "department_code"],
        "approver_role IN ('DEPT_HEAD', 'ADMIN_DEPT') AND ((approver_role = 'DEPT_HEAD') = (department_code IS NOT NULL))",
        "부서장은 부서 필수",
    ),
    uk_partial(
        EA,
        ["approver_role", "department_code"],
        "is_active AND department_code IS NOT NULL",
        "부서당 활성 부서장 1명",
    ),
    uk_partial(
        EA,
        ["approver_role"],
        "is_active AND department_code IS NULL",
        "활성 관리부서 승인자 1명",
    ),
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
    for t in TABLES + EXT_TABLES
]
RELATIONS += [
    r(KT, ["kpi_id"], KP, "KPI"),
    r(RL, ["report_id"], MR, "보고서"),
    r(RL, ["kpi_id"], KP, "KPI"),
    r(RC, ["report_id"], MR, "보고서"),
    r(RC, ["report_line_id"], RL, "보고서 지표"),
]
STATES = [
    dict(
        table=MR,
        column="status",
        values=list(VER),
        default="draft",
        transition="draft→confirmed→superseded",
    )
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn28은 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "elb.request" not in names:
        raise SystemExit("apply_dsn27을 먼저 적용한다")
    if KP in names:
        return False
    missing = set(EXT_COLUMNS) - names
    if missing:
        raise SystemExit(f"대상이 없다: {missing}")
    tables = {t["name"]: t for t in d["tables"]}
    for name, columns in EXT_COLUMNS.items():
        cols = tables[name]["columns"]
        at = len(cols) - 1 if cols[-1]["name"] == "created_at" else len(cols)
        cols[at:at] = columns
    d["tables"].extend(TABLES + EXT_TABLES)
    d["constraints"].extend(CONSTRAINTS + EXT_CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    d.update(version="target-0.16.0", task="DSN-28", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.16.0",
            task="DSN-28",
            date="2026-10-05",
            change="EIP 신규: eip 8테이블(KPI·월 목표·사람 연결·위젯 배치·즐겨찾기·경영 보고서·지표·의견). 모듈 키 없음(Q8 포털 첫 화면 = EIP). 사람 연결(HR 사원 코드) 칸: gw.person·crm.sales_rep·elb.request·elb.approval·qms.capa + elb.approver(승인자 지정). 업무 스키마 간 FK 0",
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
    eip = [t for t in d["tables"] if t["name"].startswith(P)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                eip_tables=len(eip),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
