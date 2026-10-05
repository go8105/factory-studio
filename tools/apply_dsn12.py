"""DSN-12: MES 보강 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn11 다음).

근거: docs/modules/mes/MES_보강설계_DSN-12.md 4장(새 테이블 24·기존 테이블 변경 9 + ERP 구매 요청 출처 MES), 결정 Q1~Q7.
Q1: 바코드 스캔 화면은 POP 소관 — MES는 라벨·검증 규칙과 POP 확정 결과 가져오기(pop_import)만 가진다.
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
M = "mes."


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-12"}


def active():
    return col("is_active", "사용 여부", "boolean", default="true")


DC, PDC, RC, SH, WK = (
    M + "defect_code",
    M + "process_defect_code",
    M + "reason_code",
    M + "shift",
    M + "worker",
)
MO, MU, MC, BS = M + "mold", M + "mold_usage", M + "mold_change", M + "bom_substitute"
LT, LP, MRR, MR = (
    M + "label_template",
    M + "label_print",
    M + "material_requirement_run",
    M + "material_requirement",
)
PI, PA, LG, EW = (
    M + "pop_import",
    M + "process_arrival",
    M + "lot_genealogy",
    M + "execution_worker",
)
MA, II, PIN, PIV = (
    M + "material_adjustment",
    M + "inspection_item",
    M + "process_inspection",
    M + "process_inspection_value",
)
OD, DT, SC = M + "operation_defect", M + "downtime", M + "subcontract_order"

LABEL_KINDS = ("LOT", "BOX", "PALLET", "MATERIAL", "WORK_ORDER")
REASON_CATEGORIES = ("ADJUST", "DOWNTIME", "SCRAP", "REWORK")
ADJUST_KINDS = ("UNPLANNED_ISSUE", "RETURN", "RECOVERY", "SCRAP")
POP_KINDS = ("ARRIVE", "START", "COMPLETE", "ISSUE", "PACK", "RECEIVE")
DISPOSITIONS = ("PENDING", "REWORK", "SCRAP", "CONCESSION")

TABLES = [
    table(
        DC,
        "불량 코드",
        "master",
        "DSN-12 F06. 공정 실적의 불량은 코드로 기록(자유 입력 대체)",
        [
            col("code", "불량 코드", "varchar(30)"),
            col("name", "불량명", "varchar(100)"),
            col(
                "category",
                "분류",
                "varchar(12)",
                rule="APPEARANCE 외관 / DIMENSION 치수 / FUNCTION 기능 / OTHER",
            ),
            active(),
        ],
    ),
    table(
        PDC,
        "공정별 불량 코드",
        "master",
        "DSN-12 F06. 공정에서 고를 수 있는 불량 코드",
        [
            col("process_id", "공정", "bigint"),
            col("defect_code_id", "불량 코드", "bigint"),
        ],
    ),
    table(
        RC,
        "사유 코드",
        "master",
        "DSN-12 F07·F43~F45·F38. 비가동·비계획 입출고·폐기·재작업 사유",
        [
            col("category", "분류", "varchar(10)", rule=" / ".join(REASON_CATEGORIES)),
            col("code", "사유 코드", "varchar(30)"),
            col("name", "사유명", "varchar(100)"),
            col(
                "planned",
                "계획 정지 여부",
                "boolean",
                default="false",
                rule="DOWNTIME에서 OEE 가동률 제외 여부",
            ),
            active(),
        ],
    ),
    table(
        SH,
        "근무조",
        "master",
        "DSN-12 F08",
        [
            col("code", "근무조 코드", "varchar(30)"),
            col("name", "근무조명", "varchar(60)"),
            col("start_time", "시작 시각", "time"),
            col("end_time", "종료 시각", "time", rule="시작보다 작으면 다음 날"),
            active(),
        ],
    ),
    table(
        WK,
        "작업자",
        "master",
        "DSN-12 F08·F39. 작업자 바코드 = 코드. 인사 정보는 HR(D79), 사원 코드는 스냅샷",
        [
            col("code", "작업자 코드", "varchar(30)"),
            col("name", "이름", "varchar(100)"),
            col("shift_id", "기본 근무조", "bigint", nullable=True),
            col("hr_employee_code", "HR 사원 코드", "varchar(30)", nullable=True),
            active(),
        ],
    ),
    table(
        MO,
        "금형",
        "mold",
        "DSN-12 F09·F74(Q6). 누적 타수는 사용 기록 합(저장 안 함). 보전은 CMMS가 가져가 관리",
        [
            col("code", "금형 코드", "varchar(30)"),
            col("name", "금형명", "varchar(100)"),
            col("item_id", "생산 품목", "bigint", nullable=True),
            col("cavity", "캐비티 수", "integer"),
            col("life_shots", "수명 타수", "integer"),
            col(
                "warn_ratio",
                "경고 비율",
                "numeric(5,4)",
                default="0.9",
                rule="누적/수명 ≥ 비율이면 경고",
            ),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'ACTIVE'",
                rule="ACTIVE / REPAIR / RETIRED",
            ),
        ],
    ),
    table(
        MU,
        "금형 사용",
        "mold",
        "DSN-12 F74. 공정 실행 1건당 금형 1개 타수",
        [
            col("mold_id", "금형", "bigint"),
            col("execution_id", "공정 실행", "bigint"),
            col("shots", "타수", "integer"),
            col("recorded_at", "기록 시각", "timestamptz"),
        ],
    ),
    table(
        MC,
        "금형 교체",
        "mold",
        "DSN-12 F74. 설비 장착·탈착 이력",
        [
            col("mold_id", "금형", "bigint"),
            col("equipment_id", "설비", "bigint"),
            col("mounted_at", "장착 시각", "timestamptz"),
            col("unmounted_at", "탈착 시각", "timestamptz", nullable=True),
            col("note", "메모", "varchar(300)", nullable=True),
        ],
    ),
    table(
        BS,
        "BOM 대체 자재",
        "bom",
        "DSN-12 F16. 오투입 검사(F42)의 허용 목록",
        [
            col("bom_line_id", "BOM 구성", "bigint"),
            col("substitute_item_id", "대체 자재", "bigint"),
            col("priority", "우선순위", "integer", default="1"),
            col(
                "ratio",
                "환산 비율",
                "numeric(12,6)",
                default="1",
                rule="대체 자재 수량 = 원 자재 수량 × 비율",
            ),
        ],
    ),
    table(
        LT,
        "라벨 양식",
        "label",
        "DSN-12 F18(Q3). Code128(LOT·박스·지시서·자재) / QR(팔레트), 브라우저 인쇄",
        [
            col("code", "양식 코드", "varchar(30)"),
            col("label_kind", "라벨 종류", "varchar(12)", rule=" / ".join(LABEL_KINDS)),
            col("barcode_type", "바코드", "varchar(8)", rule="CODE128 / QR"),
            col("width_mm", "가로(mm)", "integer"),
            col("height_mm", "세로(mm)", "integer"),
            col(
                "fields",
                "표시 항목",
                "varchar(300)",
                rule="쉼표 구분: item_code,item_name,qty,lot_no,date …",
            ),
            col("is_default", "종류별 기본", "boolean", default="false"),
            active(),
        ],
    ),
    table(
        LP,
        "라벨 출력",
        "label",
        "DSN-12 F25·F62·F63·F67. 바코드 값 = 대상 번호. 재발행은 이전 라벨 무효(VOID) + 사유",
        [
            col("label_kind", "라벨 종류", "varchar(12)", rule=" / ".join(LABEL_KINDS)),
            col(
                "barcode_value",
                "바코드 값",
                "varchar(80)",
                rule="LOT 번호·패킹 번호·지시 번호·WMS 자재 LOT",
            ),
            col("template_id", "라벨 양식", "bigint"),
            col("copies", "매수", "integer", default="1"),
            col("printed_at", "출력 시각", "timestamptz"),
            col("status", "상태", "varchar(6)", default="'VALID'", rule="VALID / VOID"),
            col("reprint_of_id", "재발행 원본", "bigint", nullable=True),
            col("reprint_reason", "재발행 사유", "varchar(300)", nullable=True),
        ],
    ),
    table(
        MRR,
        "자재 소요 계산",
        "plan",
        "DSN-12 F23. BOM 전개 − WMS 가용 재고(스냅샷). 확정 결과를 ERP 구매 요청 원천으로 제공",
        [
            col("run_no", "계산 번호", "varchar(40)"),
            col("production_plan_id", "생산계획", "bigint", nullable=True),
            col("calculated_at", "계산 시각", "timestamptz"),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'draft'",
                rule="draft / confirmed / superseded",
            ),
            col(
                "stock_source",
                "재고 출처",
                "varchar(10)",
                rule="WMS / NONE(WMS 꺼짐: 재고 0으로 계산)",
            ),
        ],
    ),
    table(
        MR,
        "자재 소요",
        "plan",
        "DSN-12 F23",
        [
            col("run_id", "자재 소요 계산", "bigint"),
            col("item_id", "자재", "bigint"),
            col("required_qty", "소요량", "numeric(18,3)"),
            col("available_qty", "가용 재고", "numeric(18,3)", rule="WMS 조회 스냅샷"),
            col("shortage_qty", "부족량", "numeric(18,3)", rule="max(소요 − 가용, 0)"),
            col("unit", "단위", "varchar(10)"),
            col("need_by", "필요일", "date"),
        ],
    ),
    table(
        PI,
        "POP 가져오기",
        "pop",
        "DSN-12 Q1. POP 확정 입력 1건당 1행(멱등). 적용 대상은 kind별 MES 행, 거부는 사유",
        [
            col(
                "pop_entry_ref",
                "POP 입력 코드",
                "varchar(60)",
                rule="pop.interface 확정 입력 키 스냅샷",
            ),
            col("entry_kind", "입력 종류", "varchar(10)", rule=" / ".join(POP_KINDS)),
            col("barcode_value", "스캔 값", "varchar(80)"),
            col("imported_at", "가져온 시각", "timestamptz"),
            col("result", "결과", "varchar(8)", rule="APPLIED / REJECTED"),
            col(
                "reject_reason",
                "거부 사유",
                "varchar(300)",
                nullable=True,
                rule="경로 순서·보류 LOT·BOM 외 자재·입수 초과 등",
            ),
            col(
                "target_id",
                "적용 대상 id",
                "bigint",
                nullable=True,
                rule="entry_kind에 따른 MES 행",
            ),
        ],
    ),
    table(
        PA,
        "공정 입고",
        "execution",
        "DSN-12 F34. LOT이 공정 앞에 도착(대기). 출처 POP 스캔 또는 MES 수동. 재공 현황(F94)의 근거",
        [
            col("lot_id", "LOT", "bigint"),
            col("route_step_id", "경로 단계", "bigint"),
            col("arrived_at", "도착 시각", "timestamptz"),
            col("source", "출처", "varchar(6)", rule="POP / MANUAL"),
            col("pop_entry_ref", "POP 입력 코드", "varchar(60)", nullable=True),
        ],
    ),
    table(
        LG,
        "LOT 계보",
        "execution",
        "DSN-12 F37·F38·F93. 분할·병합·재작업으로 생긴 LOT 관계와 수량",
        [
            col("parent_lot_id", "원 LOT", "bigint"),
            col("child_lot_id", "새 LOT", "bigint"),
            col("relation", "관계", "varchar(8)", rule="SPLIT / MERGE / REWORK"),
            col("qty", "수량", "numeric(18,3)"),
            col("unit", "단위", "varchar(10)"),
            col("related_at", "처리 시각", "timestamptz"),
        ],
    ),
    table(
        EW,
        "실행 작업자",
        "execution",
        "DSN-12 F39. 실행 1건에 작업자 여러 명",
        [
            col("execution_id", "공정 실행", "bigint"),
            col("worker_id", "작업자", "bigint"),
            col("started_at", "시작", "timestamptz"),
            col("ended_at", "종료", "timestamptz", nullable=True),
        ],
    ),
    table(
        MA,
        "비계획 입출고",
        "material",
        "DSN-12 F43~F45(Q2). MES가 현장 사건을 기록, WMS가 확정분을 읽어 재고 반영",
        [
            col("adjust_no", "번호", "varchar(40)"),
            col(
                "adjust_kind",
                "종류",
                "varchar(16)",
                rule="UNPLANNED_ISSUE 비계획 출고 / RETURN 반납 / RECOVERY 재생 회수 / SCRAP 폐기",
            ),
            col("item_id", "품목", "bigint"),
            col(
                "lot_no",
                "LOT 번호",
                "varchar(50)",
                nullable=True,
                rule="WMS 자재 LOT 또는 MES LOT 스냅샷",
            ),
            col("qty", "수량", "numeric(18,3)"),
            col("unit", "단위", "varchar(10)"),
            col("reason_code_id", "사유", "bigint"),
            col("work_order_id", "관련 작업지시", "bigint", nullable=True),
            col(
                "location_code",
                "현장 로케이션",
                "varchar(40)",
                nullable=True,
                rule="WMS 라인 로케이션 코드 스냅샷",
            ),
            col("occurred_on", "발생일", "date"),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'draft'",
                rule="draft / confirmed / cancelled",
            ),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
            col("cancel_reason", "취소 사유", "varchar(300)", nullable=True),
        ],
    ),
    table(
        II,
        "공정 검사 항목",
        "inspection",
        "DSN-12 F52(Q5). 공정(·품목)별 초·중·종물 점검 항목. 버전 대신 사용중단",
        [
            col("process_id", "공정", "bigint"),
            col("item_id", "품목", "bigint", nullable=True, rule="NULL이면 공정 공통"),
            col("seq", "순서", "integer"),
            col("name", "항목명", "varchar(100)"),
            col("method", "판정 방식", "varchar(10)", rule="RANGE / PASS_FAIL"),
            col("lower_limit", "하한", "numeric(15,4)", nullable=True),
            col("upper_limit", "상한", "numeric(15,4)", nullable=True),
            col("unit", "단위", "varchar(10)", nullable=True),
            active(),
        ],
    ),
    table(
        PIN,
        "공정 검사",
        "inspection",
        "DSN-12 F52. 실행 1건의 초물·중물·종물 각 1회. 확정 후 불변",
        [
            col("execution_id", "공정 실행", "bigint"),
            col(
                "timing",
                "시점",
                "varchar(6)",
                rule="FIRST 초물 / MIDDLE 중물 / LAST 종물",
            ),
            col("worker_id", "검사자", "bigint", nullable=True),
            col("inspected_at", "검사 시각", "timestamptz"),
            col(
                "result",
                "판정",
                "varchar(4)",
                nullable=True,
                rule="PASS / FAIL(확정 시 서버 계산)",
            ),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'draft'",
                rule="draft / confirmed",
            ),
        ],
    ),
    table(
        PIV,
        "공정 검사 값",
        "inspection",
        "DSN-12 F52. SPC 측정값과 별개(관리도용 측정은 SPC 소유, D38)",
        [
            col("process_inspection_id", "공정 검사", "bigint"),
            col("inspection_item_id", "검사 항목", "bigint"),
            col("measured_value", "측정값", "numeric(15,4)", nullable=True),
            col("pass_value", "합·부", "boolean", nullable=True),
            col("judgement", "항목 판정", "varchar(4)", nullable=True),
        ],
    ),
    table(
        OD,
        "불량 명세",
        "quality",
        "DSN-12 F51·F53. 확정 실적의 불량을 코드별로. 처리 판정(재작업·폐기·특채)",
        [
            col("operation_result_id", "확정 공정 실적", "bigint"),
            col("defect_code_id", "불량 코드", "bigint"),
            col("qty", "수량", "numeric(18,3)"),
            col(
                "disposition",
                "처리",
                "varchar(10)",
                default="'PENDING'",
                rule=" / ".join(DISPOSITIONS),
            ),
            col("decided_at", "판정 시각", "timestamptz", nullable=True),
            col("rework_work_order_id", "재작업 지시", "bigint", nullable=True),
        ],
    ),
    table(
        DT,
        "비가동",
        "equipment",
        "DSN-12 F72(Q6). 설비 정지 구간·사유. 고장 작업지시는 CMMS",
        [
            col("equipment_id", "설비", "bigint"),
            col("reason_code_id", "사유", "bigint"),
            col("started_at", "정지 시작", "timestamptz"),
            col("ended_at", "정지 종료", "timestamptz", nullable=True),
            col(
                "source", "출처", "varchar(6)", default="'MANUAL'", rule="MANUAL / POP"
            ),
            col("note", "메모", "varchar(300)", nullable=True),
        ],
    ),
    table(
        SC,
        "외주 지시",
        "subcontract",
        "DSN-12 F81~F83. 경로의 외주 단계. 외주처는 ERP 거래처 코드 스냅샷, 외주비는 ERP",
        [
            col("sc_no", "외주 번호", "varchar(40)"),
            col("lot_id", "LOT", "bigint"),
            col("route_step_id", "외주 단계", "bigint"),
            col("subcontractor_code", "외주처 코드", "varchar(40)"),
            col("qty", "지시 수량", "numeric(18,3)"),
            col("unit", "단위", "varchar(10)"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'draft'",
                rule="draft / shipped / received / cancelled",
            ),
            col("shipped_at", "출고 시각", "timestamptz", nullable=True),
            col("received_at", "입고 시각", "timestamptz", nullable=True),
            col("good_qty", "양품", "numeric(18,3)", nullable=True),
            col("defect_qty", "불량", "numeric(18,3)", nullable=True),
            col("cancel_reason", "취소 사유", "varchar(300)", nullable=True),
        ],
    ),
]

NEW_COLUMNS = {
    M + "item": [
        col("spec", "규격", "varchar(100)", nullable=True),
        col("drawing_no", "도번", "varchar(40)", nullable=True),
        col("revision", "리비전", "varchar(10)", nullable=True),
        col("item_group", "품목군", "varchar(40)", nullable=True),
        col("material", "재질", "varchar(60)", nullable=True),
        col("color", "색상", "varchar(30)", nullable=True),
        col("unit_weight_kg", "단위 중량(kg)", "numeric(12,4)", nullable=True),
        col("customer_part_no", "고객 품번", "varchar(40)", nullable=True),
        col("lot_tracked", "LOT 관리", "boolean", default="true"),
        col("shelf_life_days", "유효기간(일)", "integer", nullable=True),
        col("inspection_required", "출하 검사 필요(QMS)", "boolean", default="false"),
        col(
            "default_warehouse_code",
            "기본 입고 창고",
            "varchar(30)",
            nullable=True,
            rule="WMS 창고 코드 스냅샷",
        ),
        col("barcode_enabled", "바코드 사용", "boolean", default="true"),
        col(
            "box_qty", "박스 입수", "numeric(18,3)", nullable=True, rule="F17 포장 기준"
        ),
        col("boxes_per_pallet", "팔레트당 박스 수", "integer", nullable=True),
    ],
    M + "route_step": [
        col(
            "standard_cycle_sec",
            "표준 사이클(초/개)",
            "numeric(10,2)",
            nullable=True,
            rule="F05 OEE 성능 기준",
        ),
        col("setup_minutes", "준비 시간(분)", "integer", nullable=True),
        col("is_subcontract", "외주 단계", "boolean", default="false"),
        col(
            "subcontractor_code",
            "기본 외주처",
            "varchar(40)",
            nullable=True,
            rule="ERP 거래처 코드 스냅샷",
        ),
    ],
    M + "bom_line": [
        col(
            "issue_process_id",
            "투입 공정",
            "bigint",
            nullable=True,
            rule="F16 NULL이면 첫 공정",
        )
    ],
    M + "work_order": [
        col("equipment_id", "배정 설비", "bigint", nullable=True, rule="F24"),
        col("priority", "우선순위", "integer", default="5", rule="1(높음)~9"),
        col("split_from_id", "분할 원 지시", "bigint", nullable=True),
        col(
            "rework_of_lot_id",
            "재작업 대상 LOT",
            "bigint",
            nullable=True,
            rule="order_type=REWORK",
        ),
    ],
    M + "lot": [
        col(
            "origin_lot_id",
            "분할 원 LOT",
            "bigint",
            nullable=True,
            rule="F37 분할로 생긴 LOT",
        )
    ],
    M + "operation_execution": [
        col(
            "source", "출처", "varchar(6)", default="'MANUAL'", rule="MANUAL / POP(Q1)"
        ),
        col("pop_entry_ref", "POP 입력 코드", "varchar(60)", nullable=True),
    ],
    M + "material_issue": [
        col(
            "material_lot_no",
            "자재 LOT 번호",
            "varchar(50)",
            nullable=True,
            rule="Q4 WMS 자재 LOT 스냅샷(FK 없음)",
        ),
        col("source", "출처", "varchar(6)", default="'MANUAL'", rule="MANUAL / POP"),
    ],
    M + "packing_unit": [
        col(
            "voided_at",
            "해체 시각",
            "timestamptz",
            nullable=True,
            rule="F65 입고 전 해체",
        )
    ],
    M + "finished_goods_receipt": [
        col("source", "출처", "varchar(6)", default="'MANUAL'", rule="MANUAL / POP"),
        col("pop_entry_ref", "POP 입력 코드", "varchar(60)", nullable=True),
    ],
}

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in (DC, SH, WK, MO, LT):
    CONSTRAINTS += [
        c(t, "UK", S + ["code"], reason="세대 내 코드 유일"),
        c(t, "CHECK", ["code"], f"code {CODE}", "코드 형식"),
    ]
for t, field in [(MRR, "run_no"), (MA, "adjust_no"), (SC, "sc_no")]:
    CONSTRAINTS += [
        c(t, "UK", S + [field], reason="세대 내 번호 유일"),
        c(t, "CHECK", [field], f"length(btrim({field})) > 0", "번호 필수"),
    ]
CONSTRAINTS += [
    c(
        DC,
        "CHECK",
        ["category"],
        "category IN ('APPEARANCE', 'DIMENSION', 'FUNCTION', 'OTHER')",
        "분류 값",
    ),
    c(PDC, "UK", S + ["process_id", "defect_code_id"], reason="공정·불량 코드 1회"),
    c(RC, "UK", S + ["category", "code"], reason="분류 내 사유 코드 유일"),
    c(
        RC,
        "CHECK",
        ["category", "code"],
        f"category IN ({q(REASON_CATEGORIES)}) AND code {CODE}",
        "분류·코드 형식",
    ),
    c(
        RC,
        "CHECK",
        ["category", "planned"],
        "category = 'DOWNTIME' OR planned = false",
        "계획 정지는 비가동만",
    ),
    c(
        MO,
        "CHECK",
        ["cavity", "life_shots", "warn_ratio"],
        "cavity >= 1 AND life_shots > 0 AND warn_ratio > 0 AND warn_ratio <= 1",
        "캐비티·수명·경고 비율",
    ),
    c(MO, "CHECK", ["status"], "status IN ('ACTIVE', 'REPAIR', 'RETIRED')", "상태 값"),
    c(
        MO,
        "SERVICE/DB_POLICY",
        ["life_shots"],
        "누적 타수 = Σ금형 사용.shots(조회 파생, 저장 안 함). 누적 ≥ 수명 × 경고 비율이면 경고, ≥ 수명이면 실행 시작 경고(차단 아님). 보전은 CMMS가 fs.mes.interface.molds()로 가져가 관리",
        "금형 타수 파생(Q6)",
    ),
    c(MU, "UK", S + ["execution_id", "mold_id"], reason="실행·금형당 1건"),
    c(MU, "CHECK", ["shots"], "shots > 0", "타수 양수"),
    c(
        MC,
        "CHECK",
        ["mounted_at", "unmounted_at"],
        "unmounted_at IS NULL OR unmounted_at >= mounted_at",
        "시각 순서",
    ),
    uk_partial(MC, ["mold_id"], "unmounted_at IS NULL", "금형은 한 설비에만 장착"),
    uk_partial(MC, ["equipment_id"], "unmounted_at IS NULL", "설비당 장착 금형 1개"),
    c(BS, "UK", S + ["bom_line_id", "substitute_item_id"], reason="구성·대체 자재 1회"),
    c(
        BS,
        "CHECK",
        ["priority", "ratio"],
        "priority >= 1 AND ratio > 0",
        "우선순위·비율",
    ),
    c(
        LT,
        "CHECK",
        ["label_kind", "barcode_type"],
        f"label_kind IN ({q(LABEL_KINDS)}) AND barcode_type IN ('CODE128', 'QR')",
        "종류·바코드 값",
    ),
    c(
        LT,
        "CHECK",
        ["width_mm", "height_mm"],
        "width_mm BETWEEN 20 AND 210 AND height_mm BETWEEN 10 AND 297",
        "라벨 크기",
    ),
    uk_partial(LT, ["label_kind"], "is_default AND is_active", "종류별 기본 양식 1개"),
    c(
        LP,
        "CHECK",
        ["label_kind", "status", "copies"],
        f"label_kind IN ({q(LABEL_KINDS)}) AND status IN ('VALID', 'VOID') AND copies BETWEEN 1 AND 99",
        "종류·상태·매수",
    ),
    c(
        LP,
        "CHECK",
        ["reprint_of_id", "reprint_reason"],
        "(reprint_of_id IS NULL) = (reprint_reason IS NULL) AND (reprint_reason IS NULL OR length(btrim(reprint_reason)) >= 2)",
        "재발행 사유 필수",
    ),
    uk_partial(
        LP,
        ["label_kind", "barcode_value"],
        "status = 'VALID'",
        "대상당 유효 라벨 1건(재발행 시 이전 VOID)",
    ),
    c(
        LP,
        "SERVICE/DB_POLICY",
        ["status"],
        "재발행은 같은 트랜잭션에서 이전 VALID→VOID 후 새 VALID. 출력 내용은 출력 시점 스냅샷(브라우저 인쇄, Q3). 박스·팔레트는 패킹 닫을 때 자동 출력",
        "라벨 재발행(F63)",
    ),
    c(
        MRR,
        "CHECK",
        ["status", "stock_source"],
        "status IN ('draft', 'confirmed', 'superseded') AND stock_source IN ('WMS', 'NONE')",
        "상태·재고 출처",
    ),
    uk_partial(
        MRR,
        ["production_plan_id"],
        "status = 'confirmed' AND production_plan_id IS NOT NULL",
        "계획당 확정 소요 1건",
    ),
    c(MR, "UK", S + ["run_id", "item_id", "need_by"], reason="실행·자재·필요일 1행"),
    c(
        MR,
        "CHECK",
        ["required_qty", "available_qty", "shortage_qty"],
        "required_qty > 0 AND available_qty >= 0 AND shortage_qty = GREATEST(required_qty - available_qty, 0)",
        "부족량 계산",
    ),
    c(PI, "UK", S + ["pop_entry_ref"], reason="POP 입력 1건당 가져오기 1회(멱등)"),
    c(
        PI,
        "CHECK",
        ["entry_kind", "result"],
        f"entry_kind IN ({q(POP_KINDS)}) AND result IN ('APPLIED', 'REJECTED')",
        "종류·결과 값",
    ),
    c(
        PI,
        "CHECK",
        ["result", "reject_reason", "target_id"],
        "(result = 'REJECTED') = (reject_reason IS NOT NULL) AND (result = 'APPLIED') = (target_id IS NOT NULL)",
        "결과별 사유·대상",
    ),
    c(
        PI,
        "SERVICE/DB_POLICY",
        ["pop_entry_ref"],
        "fs.pop.interface.confirmed_entries()를 읽어 가져올 때 MES 규칙(경로 순서·이전 공정 완료·QMS 보류·BOM/대체 자재·입수)으로 다시 검증. 통과하면 해당 MES 행 생성 + APPLIED, 아니면 REJECTED. POP 행은 바꾸지 않는다(교차 쓰기 금지)",
        "POP 가져오기 재검증(Q1)",
    ),
    c(PA, "UK", S + ["lot_id", "route_step_id"], reason="LOT·단계당 공정 입고 1건"),
    c(
        PA,
        "CHECK",
        ["source", "pop_entry_ref"],
        "source IN ('POP', 'MANUAL') AND ((source = 'POP') = (pop_entry_ref IS NOT NULL))",
        "출처·POP 코드",
    ),
    c(
        LG,
        "CHECK",
        ["relation", "qty", "parent_lot_id", "child_lot_id"],
        "relation IN ('SPLIT', 'MERGE', 'REWORK') AND qty > 0 AND parent_lot_id <> child_lot_id",
        "관계·수량",
    ),
    c(LG, "UK", S + ["parent_lot_id", "child_lot_id"], reason="LOT 쌍 1건"),
    c(
        EW,
        "CHECK",
        ["started_at", "ended_at"],
        "ended_at IS NULL OR ended_at >= started_at",
        "시각 순서",
    ),
    c(
        MA,
        "CHECK",
        ["adjust_kind", "qty"],
        f"adjust_kind IN ({q(ADJUST_KINDS)}) AND qty > 0",
        "종류·수량",
    ),
    c(
        MA,
        "CHECK",
        ["status", "confirmed_at", "cancel_reason"],
        "(status = 'draft' AND confirmed_at IS NULL AND cancel_reason IS NULL) OR (status = 'confirmed' AND confirmed_at IS NOT NULL) OR (status = 'cancelled' AND length(btrim(cancel_reason)) > 0)",
        "상태별 값",
    ),
    c(
        MA,
        "SERVICE/DB_POLICY",
        ["status"],
        "확정 후 불변. WMS는 fs.mes.interface.material_adjustments()로 확정분을 읽어 재고 이동(MES는 재고를 바꾸지 않는다). 사유 코드 분류는 SCRAP이면 SCRAP, 그 외 ADJUST",
        "비계획 입출고 경계(Q2)",
    ),
    c(II, "UK", S + ["process_id", "item_id", "seq"], reason="공정·품목·순서 유일"),
    c(
        II,
        "CHECK",
        ["method", "lower_limit", "upper_limit", "unit"],
        "method IN ('RANGE', 'PASS_FAIL') AND (method = 'PASS_FAIL' OR (COALESCE(lower_limit, upper_limit) IS NOT NULL AND unit IS NOT NULL)) AND (lower_limit IS NULL OR upper_limit IS NULL OR lower_limit <= upper_limit)",
        "판정 방식별 한계",
    ),
    c(PIN, "UK", S + ["execution_id", "timing"], reason="실행·시점당 1회"),
    c(
        PIN,
        "CHECK",
        ["timing", "status", "result"],
        "timing IN ('FIRST', 'MIDDLE', 'LAST') AND status IN ('draft', 'confirmed') AND ((status = 'confirmed') = (result IS NOT NULL)) AND (result IS NULL OR result IN ('PASS', 'FAIL'))",
        "시점·상태·판정",
    ),
    c(
        PIN,
        "SERVICE/DB_POLICY",
        ["result"],
        "초물 PASS 전에는 실적 확정 경고. FAIL이면 실행 중 알림(차단 아님). 확정 후 불변",
        "공정 검사(Q5)",
    ),
    c(
        PIV,
        "UK",
        S + ["process_inspection_id", "inspection_item_id"],
        reason="검사·항목당 1값",
    ),
    c(
        PIV,
        "CHECK",
        ["judgement"],
        "judgement IS NULL OR judgement IN ('PASS', 'FAIL')",
        "판정 값",
    ),
    c(
        OD,
        "UK",
        S + ["operation_result_id", "defect_code_id"],
        reason="실적·불량 코드당 1행",
    ),
    c(
        OD,
        "CHECK",
        ["qty", "disposition"],
        f"qty > 0 AND disposition IN ({q(DISPOSITIONS)})",
        "수량·처리 값",
    ),
    c(
        OD,
        "CHECK",
        ["disposition", "decided_at", "rework_work_order_id"],
        "((disposition = 'PENDING') = (decided_at IS NULL)) AND (rework_work_order_id IS NULL OR disposition = 'REWORK')",
        "판정 시각·재작업 지시",
    ),
    c(
        OD,
        "SERVICE/DB_POLICY",
        ["qty"],
        "Σ불량 명세 qty = 확정 실적 defect_qty. 판정은 1회(PENDING→결정), 재작업이면 REWORK 작업지시 생성",
        "불량 명세 합계·판정",
    ),
    c(
        DT,
        "CHECK",
        ["started_at", "ended_at", "source"],
        "(ended_at IS NULL OR ended_at > started_at) AND source IN ('MANUAL', 'POP')",
        "구간·출처",
    ),
    uk_partial(DT, ["equipment_id"], "ended_at IS NULL", "설비당 진행 중 비가동 1건"),
    c(
        SC,
        "CHECK",
        ["status", "qty"],
        "status IN ('draft', 'shipped', 'received', 'cancelled') AND qty > 0",
        "상태·수량",
    ),
    c(
        SC,
        "CHECK",
        [
            "status",
            "shipped_at",
            "received_at",
            "good_qty",
            "defect_qty",
            "cancel_reason",
        ],
        "(status = 'draft' AND shipped_at IS NULL AND received_at IS NULL) OR (status = 'shipped' AND shipped_at IS NOT NULL AND received_at IS NULL) OR "
        "(status = 'received' AND received_at >= shipped_at AND good_qty >= 0 AND defect_qty >= 0) OR (status = 'cancelled' AND received_at IS NULL AND length(btrim(cancel_reason)) > 0)",
        "상태별 시각·수량",
    ),
    c(
        SC,
        "SERVICE/DB_POLICY",
        ["status"],
        "입고 수량(양품+불량) ≤ 지시 수량. 입고 확정분을 fs.mes.interface.subcontract_results()로 ERP(외주비 F34)·WMS(실물)가 읽는다",
        "외주 실적 제공",
    ),
]
for t, cols_ in [
    (PDC, ["process_id"]),
    (WK, ["shift_id"]),
    (MU, ["mold_id"]),
    (MC, ["equipment_id"]),
    (LP, ["template_id"]),
    (MR, ["run_id"]),
    (PA, ["route_step_id", "arrived_at"]),
    (LG, ["child_lot_id"]),
    (EW, ["worker_id", "started_at"]),
    (MA, ["item_id", "occurred_on"]),
    (PIN, ["execution_id"]),
    (OD, ["defect_code_id"]),
    (DT, ["equipment_id", "started_at"]),
    (SC, ["lot_id"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="FK·목록 조회"))

CHANGED_CONSTRAINTS = [
    c(
        M + "item",
        "CHECK",
        ["shelf_life_days", "unit_weight_kg", "box_qty", "boxes_per_pallet"],
        "(shelf_life_days IS NULL OR shelf_life_days > 0) AND (unit_weight_kg IS NULL OR unit_weight_kg >= 0) AND (box_qty IS NULL OR box_qty > 0) AND (boxes_per_pallet IS NULL OR boxes_per_pallet > 0)",
        "관리 속성·포장 기준 범위",
    ),
    c(
        M + "item",
        "SERVICE/DB_POLICY",
        ["box_qty", "boxes_per_pallet"],
        "패킹(POP 가져오기 포함)은 박스 수량 ≤ 박스 입수, 팔레트 박스 수 ≤ 팔레트당 박스 수일 때만 닫는다. 기준이 없으면 검사 생략",
        "포장 기준(F17·F64)",
    ),
    c(
        M + "route_step",
        "CHECK",
        ["standard_cycle_sec", "setup_minutes", "is_subcontract", "subcontractor_code"],
        "(standard_cycle_sec IS NULL OR standard_cycle_sec > 0) AND (setup_minutes IS NULL OR setup_minutes >= 0) AND (subcontractor_code IS NULL OR is_subcontract)",
        "표준 시간·외주 단계",
    ),
    c(
        M + "work_order",
        "CHECK",
        ["priority"],
        "priority BETWEEN 1 AND 9",
        "우선순위 범위",
    ),
    c(
        M + "work_order",
        "CHECK",
        ["order_type", "rework_of_lot_id"],
        "(order_type = 'REWORK') = (rework_of_lot_id IS NOT NULL)",
        "재작업 지시는 대상 LOT 필수",
    ),
    uk_partial(
        M + "lot",
        ["work_order_id"],
        "origin_lot_id IS NULL",
        "작업지시당 원 LOT 1개(분할 LOT은 예외, DSN-12 F37)",
    ),
    c(
        M + "operation_execution",
        "CHECK",
        ["source", "pop_entry_ref"],
        "source IN ('MANUAL', 'POP') AND ((source = 'POP') = (pop_entry_ref IS NOT NULL))",
        "출처·POP 코드",
    ),
    c(
        M + "material_issue",
        "CHECK",
        ["source", "material_lot_id", "material_lot_no"],
        "source IN ('MANUAL', 'POP') AND (material_lot_id IS NULL OR material_lot_no IS NULL)",
        "출처·LOT 한쪽만",
    ),
    uk_partial(
        M + "material_issue",
        ["execution_id", "material_item_id", "material_lot_no"],
        "material_lot_no IS NOT NULL",
        "실행·자재·WMS LOT별 1건",
    ),
    c(
        M + "finished_goods_receipt",
        "CHECK",
        ["source", "pop_entry_ref"],
        "source IN ('MANUAL', 'POP') AND ((source = 'POP') = (pop_entry_ref IS NOT NULL))",
        "출처·POP 코드",
    ),
    c(
        M + "packing_unit",
        "CHECK",
        ["status", "voided_at"],
        "(status = 'void') = (voided_at IS NOT NULL)",
        "해체 시각",
    ),
]
REPLACED = {
    (M + "work_order", "order_type = 'STOCK'"): "order_type IN ('STOCK', 'REWORK')",
    (
        M + "packing_unit",
        "status IN ('open', 'closed', 'received', 'shipped')",
    ): "status IN ('open', 'closed', 'received', 'shipped', 'void')",
    (
        "erp.purchase_request",
        "source IN ('MANUAL', 'CMMS', 'ELB') AND ((source = 'MANUAL') = (source_ref IS NULL))",
    ): "source IN ('MANUAL', 'CMMS', 'ELB', 'MES') AND ((source = 'MANUAL') = (source_ref IS NULL))",
}
REMOVED_UK = (M + "lot", S + ["work_order_id"])

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
    r(PDC, ["process_id"], M + "process", "공정"),
    r(PDC, ["defect_code_id"], DC, "불량 코드"),
    r(WK, ["shift_id"], SH, "기본 근무조"),
    r(MO, ["item_id"], M + "item", "생산 품목"),
    r(MU, ["mold_id"], MO, "금형"),
    r(MU, ["execution_id"], M + "operation_execution", "공정 실행"),
    r(MC, ["mold_id"], MO, "금형"),
    r(MC, ["equipment_id"], M + "equipment", "장착 설비"),
    r(BS, ["bom_line_id"], M + "bom_line", "BOM 구성"),
    r(BS, ["substitute_item_id"], M + "item", "대체 자재"),
    r(LP, ["template_id"], LT, "라벨 양식"),
    r(LP, ["reprint_of_id"], LP, "재발행 원본"),
    r(MRR, ["production_plan_id"], M + "production_plan", "생산계획"),
    r(MR, ["run_id"], MRR, "계산 소속"),
    r(MR, ["item_id"], M + "item", "자재"),
    r(PA, ["lot_id"], M + "lot", "LOT"),
    r(PA, ["route_step_id"], M + "route_step", "경로 단계"),
    r(LG, ["parent_lot_id"], M + "lot", "원 LOT"),
    r(LG, ["child_lot_id"], M + "lot", "새 LOT"),
    r(EW, ["execution_id"], M + "operation_execution", "공정 실행"),
    r(EW, ["worker_id"], WK, "작업자"),
    r(MA, ["item_id"], M + "item", "품목"),
    r(MA, ["reason_code_id"], RC, "사유"),
    r(MA, ["work_order_id"], M + "work_order", "관련 작업지시"),
    r(II, ["process_id"], M + "process", "공정"),
    r(II, ["item_id"], M + "item", "품목"),
    r(PIN, ["execution_id"], M + "operation_execution", "공정 실행"),
    r(PIN, ["worker_id"], WK, "검사자"),
    r(PIV, ["process_inspection_id"], PIN, "공정 검사"),
    r(PIV, ["inspection_item_id"], II, "검사 항목"),
    r(OD, ["operation_result_id"], M + "operation_result", "확정 실적"),
    r(OD, ["defect_code_id"], DC, "불량 코드"),
    r(OD, ["rework_work_order_id"], M + "work_order", "재작업 지시"),
    r(DT, ["equipment_id"], M + "equipment", "설비"),
    r(DT, ["reason_code_id"], RC, "비가동 사유"),
    r(SC, ["lot_id"], M + "lot", "LOT"),
    r(SC, ["route_step_id"], M + "route_step", "외주 단계"),
    r(M + "bom_line", ["issue_process_id"], M + "process", "투입 공정"),
    r(M + "work_order", ["equipment_id"], M + "equipment", "배정 설비"),
    r(M + "work_order", ["split_from_id"], M + "work_order", "분할 원 지시"),
    r(M + "work_order", ["rework_of_lot_id"], M + "lot", "재작업 대상 LOT"),
    r(M + "lot", ["origin_lot_id"], M + "lot", "분할 원 LOT"),
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
        MO,
        ("ACTIVE", "REPAIR", "RETIRED"),
        "ACTIVE",
        "ACTIVE↔REPAIR(CMMS 보전), →RETIRED",
    ),
    st(LP, ("VALID", "VOID"), "VALID", "VALID→VOID(재발행)"),
    st(
        MRR, ("draft", "confirmed", "superseded"), "draft", "draft→confirmed→superseded"
    ),
    st(
        MA,
        ("draft", "confirmed", "cancelled"),
        "draft",
        "draft→confirmed(WMS가 읽음); draft→cancelled",
    ),
    st(PIN, ("draft", "confirmed"), "draft", "draft→confirmed(판정 계산)"),
    st(
        SC,
        ("draft", "shipped", "received", "cancelled"),
        "draft",
        "draft→shipped→received; 출고 전 cancelled",
    ),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn12는 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "erp.journal_entry" not in names:
        raise SystemExit("apply_dsn11을 먼저 적용한다")
    if PI in names:
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
            x["table"] == REMOVED_UK[0]
            and x["kind"] == "UK"
            and x["columns"] == REMOVED_UK[1]
        )
    ]
    for x in d["constraints"]:
        new = REPLACED.get((x["table"], x["expression"]))
        if new:
            x["expression"] = new
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS + CHANGED_CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    for s in d["states"]:
        if s["table"] == M + "packing_unit" and "void" not in s["values"]:
            s["values"] = [*s["values"], "void"]
            s["transition"] += "; open/closed(입고 전)→void(해체, F65)"
    d["states"].extend(STATES)
    d["code_lists"].extend(
        [
            dict(
                target=RC,
                column="category",
                values=list(REASON_CATEGORIES),
                default=None,
                note="비계획 입출고 / 비가동 / 폐기 / 재작업",
            ),
            dict(
                target=MA,
                column="adjust_kind",
                values=list(ADJUST_KINDS),
                default=None,
                note="비계획 출고 / 반납 / 재생 회수 / 폐기",
            ),
            dict(
                target=LT,
                column="label_kind",
                values=list(LABEL_KINDS),
                default=None,
                note="LOT 이동 카드 / 박스 / 팔레트 / 자재 / 작업지시서",
            ),
            dict(
                target=PI,
                column="entry_kind",
                values=list(POP_KINDS),
                default=None,
                note="공정 입고 / 작업 시작 / 완료 / 투입 / 패킹 / 완제품 입고",
            ),
        ]
    )
    d.update(version="target-0.3.0", task="DSN-12", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.3.0",
            task="DSN-12",
            date="2026-10-05",
            change="MES 보강: 새 테이블 24(기준 5·금형 3·BOM 대체 1·라벨 2·자재 소요 2·POP 가져오기·공정 입고·LOT 계보·실행 작업자·비계획 입출고·공정 검사 3·불량 명세·비가동·외주), 기존 9테이블 변경(품목·경로 단계·BOM 구성·작업지시·LOT·공정 실행·자재 투입·패킹·완제품 입고), ERP 구매 요청 출처에 MES",
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
    mes = [t for t in d["tables"] if t["name"].startswith(M)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                mes_tables=len(mes),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
