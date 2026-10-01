"""FS-029a: CMMS 6테이블과 모듈 키 'cmms'(workspace_module·app_review)를 schema.json에 반영한다(멱등).

근거: docs/modules/cmms/CMMS_모듈설계_FS-029.md 4장, docs/plan/CMMS도입_설비보전_결정_FS-029.md(D45~D52).
이미 반영돼 있으면 아무것도 바꾸지 않는다. 새 제약·관계는 목록 끝에 붙여 기존 C·R 번호를 유지한다.
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "docs/db/schema-metadata/schema.json"
MODULE_TABLES = {"core.workspace_module", "core.app_review"}
CODE_FORMAT = "code ~ '^[A-Z][A-Z0-9-]{1,19}$'"
ASSET_TYPES = ("INJECTION", "ASSEMBLY", "INSPECTION", "HVAC", "UTILITY", "OTHER")
SOURCES = ("MANUAL", "BEMS_ALARM", "SPC_SIGNAL", "PM_PLAN")
STATUSES = ("REQUESTED", "IN_PROGRESS", "COMPLETED", "CANCELLED")
CAUSES = ("WEAR", "LUBRICATION", "ELECTRICAL", "SETTING", "EXTERNAL", "OTHER")


def quoted(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "C1"}


def active():
    return col("is_active", "사용 여부", "boolean", default="true")


TABLES = [
    table(
        "cmms.asset",
        "설비 대장",
        "asset",
        "FS-029 4.1·D46. CMMS 소유. MES 설비·BEMS 공조기는 원천 코드 스냅샷(FK 없음)",
        [
            col("code", "설비 코드", "varchar(20)"),
            col("name", "설비명", "varchar(100)"),
            col("asset_type", "설비 종류", "varchar(12)", rule=" / ".join(ASSET_TYPES)),
            col("location", "위치", "varchar(100)", nullable=True),
            col("source", "출처", "varchar(6)", rule="MES / BEMS / CMMS(직접 등록)"),
            col(
                "source_code",
                "원천 코드",
                "varchar(40)",
                nullable=True,
                rule="MES 설비 코드 / BEMS 공조기 코드 스냅샷. CMMS 출처면 비움",
            ),
            active(),
        ],
    ),
    table(
        "cmms.pm_plan",
        "예방보전 계획",
        "plan",
        "FS-029 4.1·D49. 다음 예정일 = (마지막 수행일 ?? 시작일) + 주기, 저장하지 않는다",
        [
            col("asset_id", "설비", "bigint"),
            col("code", "계획 코드", "varchar(20)"),
            col("title", "제목", "varchar(200)"),
            col("checklist", "점검 항목", "varchar(500)"),
            col("interval_days", "주기(일)", "integer", rule="1~365"),
            col("start_on", "시작일", "date"),
            col(
                "last_done_on",
                "마지막 수행일",
                "date",
                nullable=True,
                rule="PM 작업지시 완료로만 바뀐다",
            ),
            active(),
        ],
    ),
    table(
        "cmms.work_order",
        "보전 작업지시",
        "work",
        "FS-029 4.2·D47·D48. 접수 → 진행 → 완료/취소, 완료·취소 후 불변. 신호 출처는 원천 id 스냅샷",
        [
            col(
                "wo_no",
                "작업지시 번호",
                "varchar(30)",
                rule="서버 발번 WO-YYYYMMDD-NNN(업무 기준일)",
            ),
            col("asset_id", "설비", "bigint"),
            col("kind", "종류", "varchar(2)", rule="BM 고장(사후) / PM 예방"),
            col("source", "출처", "varchar(12)", rule=" / ".join(SOURCES)),
            col(
                "source_ref",
                "원천 id",
                "varchar(60)",
                nullable=True,
                rule="BEMS 경보 id · SPC 이상 id",
            ),
            col(
                "source_summary",
                "원천 요약",
                "varchar(300)",
                nullable=True,
                rule="전환 때 스냅샷",
            ),
            col("pm_plan_id", "예방보전 계획", "bigint", nullable=True),
            col("due_on", "PM 예정일", "date", nullable=True),
            col("title", "제목", "varchar(200)"),
            col("description", "설명", "varchar(1000)", nullable=True),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'REQUESTED'",
                rule=" / ".join(STATUSES),
            ),
            col("requested_at", "접수 시각", "timestamptz"),
            col(
                "failure_at",
                "정지 시작",
                "timestamptz",
                nullable=True,
                rule="BM 필수(고장 시각)",
            ),
            col("started_at", "작업 시작", "timestamptz", nullable=True),
            col("completed_at", "완료 시각", "timestamptz", nullable=True),
            col(
                "restored_at",
                "복구 시각",
                "timestamptz",
                nullable=True,
                rule="BM 완료 시 필수, 정지 시작 이후",
            ),
            col(
                "cause_category",
                "원인 분류",
                "varchar(12)",
                nullable=True,
                rule=" / ".join(CAUSES),
            ),
            col("action", "조치 내용", "varchar(500)", nullable=True),
            col("cancelled_at", "취소 시각", "timestamptz", nullable=True),
            col("cancel_reason", "취소 사유", "varchar(300)", nullable=True),
        ],
    ),
    table(
        "cmms.work_log",
        "작업 기록",
        "work",
        "FS-029 4.2. 진행 중에만 추가, 수정·삭제 없음",
        [
            col("work_order_id", "작업지시", "bigint"),
            col("logged_at", "기록 시각", "timestamptz"),
            col("minutes", "작업 시간(분)", "integer", rule="1~1440"),
            col("note", "내용", "varchar(300)"),
        ],
    ),
    table(
        "cmms.spare_part",
        "예비품",
        "parts",
        "FS-029 4.3·D50. 재고 원장 없음(WMS 영역)",
        [
            col("code", "예비품 코드", "varchar(20)"),
            col("name", "예비품명", "varchar(100)"),
            col("unit", "단위", "varchar(10)"),
            col("safety_stock", "안전 재고(참고)", "numeric(12,3)", default="0"),
            active(),
        ],
    ),
    table(
        "cmms.part_usage",
        "부품 사용",
        "parts",
        "FS-029 4.3. 진행 중에만 추가, 수정·삭제 없음",
        [
            col("work_order_id", "작업지시", "bigint"),
            col("spare_part_id", "예비품", "bigint"),
            col("qty", "수량", "numeric(12,3)"),
            col("used_at", "사용 시각", "timestamptz"),
        ],
    ),
]
AS, PM, WO, WL, SP, PU = (t["name"] for t in TABLES)

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
SIGNAL_SOURCES = "('BEMS_ALARM', 'SPC_SIGNAL')"
CONSTRAINTS += [
    c(AS, "UK", S + ["code"], reason="세대 내 설비 코드 유일"),
    c(AS, "CHECK", ["code"], CODE_FORMAT, "코드 형식"),
    c(
        AS,
        "CHECK",
        ["asset_type"],
        f"asset_type IN ({quoted(ASSET_TYPES)})",
        "설비 종류 값",
    ),
    c(AS, "CHECK", ["source"], "source IN ('MES', 'BEMS', 'CMMS')", "출처 값"),
    c(
        AS,
        "CHECK",
        ["source", "source_code"],
        "(source = 'CMMS') = (source_code IS NULL)",
        "가져온 설비만 원천 코드",
    ),
    uk_partial(
        AS,
        ["source", "source_code"],
        "source <> 'CMMS'",
        "같은 원천 설비는 1건(가져오기 멱등, D46)",
    ),
    c(
        AS,
        "SERVICE/DB_POLICY",
        ["source_code"],
        "가져오기는 원천 코드가 이미 있으면 건너뛴다. 원천이 바뀌어도 대장은 그대로(스냅샷). 작업지시가 있는 설비는 삭제 대신 사용 안 함",
        "설비 대장 스냅샷",
    ),
    c(PM, "UK", S + ["code"], reason="세대 내 계획 코드 유일"),
    c(PM, "CHECK", ["code"], CODE_FORMAT, "코드 형식"),
    c(PM, "CHECK", ["interval_days"], "interval_days BETWEEN 1 AND 365", "주기 범위"),
    c(
        PM,
        "CHECK",
        ["start_on", "last_done_on"],
        "last_done_on IS NULL OR last_done_on >= start_on",
        "마지막 수행일은 시작일 이후",
    ),
    c(
        PM,
        "SERVICE/DB_POLICY",
        ["last_done_on"],
        "마지막 수행일은 PM 작업지시 완료(TX-C4)로만 바뀐다 = 완료 시각의 날짜(KST). 다음 예정일 = (마지막 수행일 ?? 시작일) + 주기",
        "PM 주기(D49, 13장 5)",
    ),
    c(WO, "UK", S + ["wo_no"], reason="세대 내 작업지시 번호 유일"),
    c(WO, "CHECK", ["kind"], "kind IN ('BM', 'PM')", "종류 값"),
    c(WO, "CHECK", ["source"], f"source IN ({quoted(SOURCES)})", "출처 값"),
    c(
        WO,
        "CHECK",
        ["kind", "source"],
        "(kind = 'PM') = (source = 'PM_PLAN')",
        "PM은 계획 출처만",
    ),
    c(
        WO,
        "CHECK",
        ["kind", "pm_plan_id", "due_on"],
        "(kind = 'PM' AND pm_plan_id IS NOT NULL AND due_on IS NOT NULL) OR (kind = 'BM' AND pm_plan_id IS NULL AND due_on IS NULL)",
        "PM만 계획·예정일",
    ),
    c(
        WO,
        "CHECK",
        ["source", "source_ref"],
        f"(source IN {SIGNAL_SOURCES}) = (source_ref IS NOT NULL)",
        "신호 출처만 원천 id",
    ),
    c(
        WO,
        "CHECK",
        ["kind", "failure_at"],
        "(kind = 'BM') = (failure_at IS NOT NULL)",
        "BM만 정지 시작",
    ),
    c(WO, "CHECK", ["status"], f"status IN ({quoted(STATUSES)})", "상태 값"),
    c(
        WO,
        "CHECK",
        ["cause_category"],
        f"cause_category IS NULL OR cause_category IN ({quoted(CAUSES)})",
        "원인 분류 값",
    ),
    c(
        WO,
        "CHECK",
        [
            "status",
            "started_at",
            "completed_at",
            "cancelled_at",
            "cause_category",
            "action",
            "cancel_reason",
        ],
        "(status = 'REQUESTED' AND started_at IS NULL AND completed_at IS NULL AND cancelled_at IS NULL) OR "
        "(status = 'IN_PROGRESS' AND started_at IS NOT NULL AND completed_at IS NULL AND cancelled_at IS NULL) OR "
        "(status = 'COMPLETED' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND cause_category IS NOT NULL AND action IS NOT NULL AND cancelled_at IS NULL) OR "
        "(status = 'CANCELLED' AND completed_at IS NULL AND cancelled_at IS NOT NULL AND cancel_reason IS NOT NULL)",
        "상태와 시각·필수 칸 일치",
    ),
    c(
        WO,
        "CHECK",
        ["restored_at", "failure_at"],
        "restored_at IS NULL OR restored_at >= failure_at",
        "복구는 정지 시작 이후",
    ),
    c(
        WO,
        "CHECK",
        ["kind", "status", "restored_at"],
        "NOT (kind = 'BM' AND status = 'COMPLETED' AND restored_at IS NULL) AND (restored_at IS NULL OR kind = 'BM')",
        "BM 완료는 복구 시각 필수, PM은 복구 없음",
    ),
    c(
        WO,
        "CHECK",
        ["requested_at", "started_at", "completed_at"],
        "(started_at IS NULL OR started_at >= requested_at) AND (completed_at IS NULL OR completed_at >= started_at)",
        "시각 순서",
    ),
    c(
        WO,
        "CHECK",
        ["action", "cancel_reason"],
        "(action IS NULL OR char_length(btrim(action)) >= 2) AND (cancel_reason IS NULL OR char_length(btrim(cancel_reason)) >= 2)",
        "조치·사유 2자 이상",
    ),
    uk_partial(
        WO,
        ["source", "source_ref"],
        f"source IN {SIGNAL_SOURCES} AND status <> 'CANCELLED'",
        "신호 1건당 취소되지 않은 작업지시 1건(D48)",
    ),
    uk_partial(
        WO,
        ["pm_plan_id", "due_on"],
        "kind = 'PM' AND status <> 'CANCELLED'",
        "계획·예정일당 PM 작업지시 1건",
    ),
    c(
        WO,
        "SERVICE/DB_POLICY",
        ["status"],
        "REQUESTED → IN_PROGRESS(TX-C2) → COMPLETED(TX-C4) · REQUESTED/IN_PROGRESS → CANCELLED(TX-C5). 완료·취소 후 수정·삭제하지 않는다(세대 정리 제외)",
        "작업지시 수명(D47)",
    ),
    c(
        WO,
        "SERVICE/DB_POLICY",
        ["source_ref"],
        "전환은 원천 조회(fs.bems.interface·fs.spc.interface)로 신호가 있고 아직 전환되지 않았을 때만. 원천 상태는 바꾸지 않는다. PM 생성은 업무 기준일 ≥ 다음 예정일일 때만",
        "신호 전환·PM 생성(D48·D49)",
    ),
    c(WL, "CHECK", ["minutes"], "minutes BETWEEN 1 AND 1440", "작업 시간 범위"),
    c(
        WL,
        "SERVICE/DB_POLICY",
        ["work_order_id"],
        "작업지시가 IN_PROGRESS일 때만 추가(TX-C3). 수정·삭제 없음",
        "작업 기록 추가만(13장 3)",
    ),
    c(SP, "UK", S + ["code"], reason="세대 내 예비품 코드 유일"),
    c(SP, "CHECK", ["code"], CODE_FORMAT, "코드 형식"),
    c(SP, "CHECK", ["safety_stock"], "safety_stock >= 0", "안전 재고 음수 금지"),
    c(PU, "CHECK", ["qty"], "qty > 0", "수량 양수"),
    c(
        PU,
        "SERVICE/DB_POLICY",
        ["work_order_id"],
        "작업지시가 IN_PROGRESS일 때만 추가(TX-C3). 수정·삭제 없음. 재고를 움직이지 않는다(D50)",
        "부품 사용 추가만",
    ),
    c(PM, "INDEX", S + ["asset_id"], reason="FK 조회"),
    c(WO, "INDEX", S + ["asset_id", "status"], reason="설비별 진행 작업지시(MES 배지)"),
    c(WO, "INDEX", S + ["pm_plan_id"], reason="FK 조회"),
    c(WO, "INDEX", S + ["status", "requested_at"], reason="목록"),
    c(WL, "INDEX", S + ["work_order_id"], reason="FK 조회"),
    c(PU, "INDEX", S + ["work_order_id"], reason="FK 조회"),
    c(PU, "INDEX", S + ["spare_part_id", "used_at"], reason="예비품 사용 집계"),
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
    r(PM, ["asset_id"], AS, "계획의 설비"),
    r(WO, ["asset_id"], AS, "작업지시의 설비"),
    r(WO, ["pm_plan_id"], PM, "PM 작업지시의 계획"),
    r(WL, ["work_order_id"], WO, "작업 기록의 작업지시"),
    r(PU, ["work_order_id"], WO, "부품 사용의 작업지시"),
    r(PU, ["spare_part_id"], SP, "사용한 예비품"),
]

STATES = [
    dict(
        table=WO,
        column="status",
        values=list(STATUSES),
        default="REQUESTED",
        transition="REQUESTED→IN_PROGRESS→COMPLETED, REQUESTED/IN_PROGRESS→CANCELLED; 완료·취소 후 불변",
    ),
]


def apply(d):
    """schema dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if AS in {t["name"] for t in d["tables"]}:
        return False
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    for cst in d["constraints"]:
        if (
            cst["table"] in MODULE_TABLES
            and cst["kind"] == "CHECK"
            and "module_key IN" in cst["expression"]
            and "'cmms'" not in cst["expression"]
        ):
            cst["expression"] = cst["expression"].rstrip(")") + ", 'cmms')"
    for code in d["code_lists"]:
        if (
            code["target"] in MODULE_TABLES
            and code["column"] == "module_key"
            and "cmms" not in code["values"]
        ):
            code["values"] = [*code["values"], "cmms"]
    d["code_lists"].extend(
        [
            dict(
                target=AS,
                column="asset_type",
                values=list(ASSET_TYPES),
                default=None,
                note="사출·조립·검사·공조·유틸리티·기타",
            ),
            dict(
                target=AS,
                column="source",
                values=["MES", "BEMS", "CMMS"],
                default=None,
                note="가져오기 원천 / 직접 등록",
            ),
            dict(
                target=WO,
                column="source",
                values=list(SOURCES),
                default=None,
                note="수동 / BEMS 경보 / SPC 이상 / PM 계획",
            ),
            dict(
                target=WO,
                column="cause_category",
                values=list(CAUSES),
                default=None,
                note="마모·윤활·전기·설정·외부·기타",
            ),
        ]
    )
    d.update(
        version="0.17.0",
        task="FS-029a",
        date="2026-10-01",
        migration_revision="fs029b_cmms_module",
    )
    d["change_log"].append(
        dict(
            version="0.17.0",
            task="FS-029a",
            date="2026-10-01",
            change="cmms 스키마 6테이블(설비 대장·예방보전 계획·작업지시·작업 기록·예비품·부품 사용), 모듈 키 cmms(workspace_module·app_review). 스키마 간 FK 0건",
            status="마이그레이션 fs029a_cmms·fs029b_cmms_module 적용 대상",
        )
    )
    return True


def main():
    d = json.loads(SCHEMA.read_text(encoding="utf-8"))
    changed = apply(d)
    if changed:
        SCHEMA.write_text(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
