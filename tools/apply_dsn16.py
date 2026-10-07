"""DSN-16: BEMS 보강 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn15 다음).

근거: docs/modules/bems/BEMS_보강설계_DSN-16.md 4장(새 테이블 core 1 + bems 11, 기존 테이블 변경 6), 결정 Q1~Q7.
Q1: 휴일 달력은 core 공통(core.holiday). 업무 솔루션은 날짜로 읽기만(FK 없음 — 업무 → core FK는 범위 앵커만, FS-013 §6).
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z][A-Z0-9-]{1,19}$'"
MONTH = "~ '^[0-9]{4}-(0[1-9]|1[0-2])$'"
B = "bems."


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-16"}


METRICS = (
    ("TEMP", "℃"),
    ("HUMIDITY", "%"),
    ("CO2", "ppm"),
    ("PM25", "㎍/㎥"),
    ("LUX", "lx"),
    ("OCCUPANCY", "명"),
)
VER = ("draft", "confirmed", "superseded")
HOL, BLD, LC, DP, DPS, CS, EAR, EA, ET, CR, CL, ER = (
    "core.holiday",
    B + "building",
    B + "lighting_circuit",
    B + "demand_plan",
    B + "demand_plan_step",
    B + "comfort_standard",
    B + "equipment_alarm_rule",
    B + "equipment_alarm",
    B + "energy_target",
    B + "cost_run",
    B + "cost_allocation_line",
    B + "energy_review",
)

TABLES = [
    table(
        HOL,
        "휴일",
        "calendar",
        "DSN-16 Q1. 회사 공통 휴일 달력(core 운영). BEMS 스케줄·FEMS TOU·MES 근무조·HR 근태가 날짜로 읽는다(FK 없음)",
        [
            col("holiday_on", "휴일", "date"),
            col("name", "이름", "varchar(60)"),
            col("kind", "구분", "varchar(8)", rule="PUBLIC 공휴일 / COMPANY 회사 휴무"),
        ],
    ),
    table(
        BLD,
        "건물",
        "space",
        "DSN-16 F04. 건물 > 층(구역의 층 표기) > 구역",
        [
            col("code", "건물 코드", "varchar(20)"),
            col("name", "건물명", "varchar(100)"),
            col("floors", "층수", "integer"),
            col("gross_area_m2", "연면적(㎡)", "numeric(12,2)"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        LC,
        "조명 회로",
        "control",
        "DSN-16 F06·F23(Q3). 구역별 조명 제어 단위. 상태는 마지막 적용 명령",
        [
            col("zone_id", "구역", "bigint"),
            col("code", "회로 코드", "varchar(20)"),
            col("name", "회로명", "varchar(100)"),
            col("meter_id", "조명 계측기", "bigint", nullable=True),
            col("rated_kw", "정격 전력(kW)", "numeric(10,2)"),
            col("state", "상태", "varchar(4)", default="'OFF'", rule="ON / OFF"),
            col(
                "control_source",
                "제어 출처",
                "varchar(10)",
                default="'SCHEDULE'",
                rule="SCHEDULE / MANUAL / PEAK",
            ),
            col("state_changed_at", "상태 변경 시각", "timestamptz", nullable=True),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        DP,
        "피크 감축안",
        "demand",
        "DSN-16 F24(Q2). FEMS 피크 경보 1건당 감축안 1건. 제안 → 승인 → 실행(제어 명령) → 경보 해제 후 복귀",
        [
            col("plan_no", "감축안 번호", "varchar(40)"),
            col(
                "fems_alarm_ref",
                "FEMS 경보",
                "varchar(60)",
                rule="fs.fems.interface.open_alarms() 경보 id 스냅샷",
            ),
            col("proposed_at", "제안 시각", "timestamptz"),
            col("target_reduction_kw", "목표 감축(kW)", "numeric(10,2)"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'PROPOSED'",
                rule="PROPOSED / APPROVED / EXECUTED / RESTORED / REJECTED",
            ),
            col("decided_at", "승인·반려 시각", "timestamptz", nullable=True),
            col("executed_at", "실행 시각", "timestamptz", nullable=True),
            col("restored_at", "복귀 시각", "timestamptz", nullable=True),
            col("decision_note", "의견", "varchar(300)", nullable=True),
        ],
    ),
    table(
        DPS,
        "감축 단계",
        "demand",
        "DSN-16 F24. 공조기 감축 우선순위대로 동작·예상 감축. 실행 시 제어 명령 연결",
        [
            col("demand_plan_id", "피크 감축안", "bigint"),
            col("seq", "순서", "integer"),
            col("hvac_unit_id", "공조기", "bigint", nullable=True),
            col("lighting_circuit_id", "조명 회로", "bigint", nullable=True),
            col(
                "action",
                "동작",
                "varchar(16)",
                rule="SET_FAN 송풍 전환 / RAISE_SETPOINT 설정 온도 상향 / POWER_OFF 끄기",
            ),
            col("delta_value", "상향 폭(℃)", "numeric(5,1)", nullable=True),
            col("expected_kw", "예상 감축(kW)", "numeric(10,2)"),
            col("command_id", "실행 명령", "bigint", nullable=True),
            col("restore_command_id", "복귀 명령", "bigint", nullable=True),
        ],
    ),
    table(
        CS,
        "쾌적 기준",
        "comfort",
        "DSN-16 F14(Q4). 구역 용도 × 지표의 쾌적 범위. 쾌적 시간 비율 = 범위 안 관측 시간 ÷ 관측 시간(조회 계산)",
        [
            col(
                "zone_kind",
                "구역 용도",
                "varchar(12)",
                rule="OFFICE / PRODUCTION / UTILITY",
            ),
            col("metric", "지표", "varchar(10)"),
            col("low", "하한", "numeric(10,2)", nullable=True),
            col("high", "상한", "numeric(10,2)", nullable=True),
            col("occupied_only", "근무 시간만", "boolean", default="true"),
        ],
    ),
    table(
        EAR,
        "설비 경보 규칙",
        "alarm",
        "DSN-16 F32. 공조기·조명 회로 이상(명령 거부 연속·장시간 연속 운전)",
        [
            col("code", "규칙 코드", "varchar(20)"),
            col(
                "condition",
                "조건",
                "varchar(16)",
                rule="COMMAND_REJECTED 명령 거부 / LONG_RUN 연속 운전",
            ),
            col(
                "hvac_unit_id",
                "공조기",
                "bigint",
                nullable=True,
                rule="NULL이면 모든 공조기",
            ),
            col(
                "threshold",
                "기준",
                "numeric(10,2)",
                rule="거부 횟수 또는 연속 운전 시간",
            ),
            col("severity", "등급", "varchar(8)", rule="WARNING / CRITICAL"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        EA,
        "설비 경보",
        "alarm",
        "DSN-16 F32·F33. 규칙·설비당 진행 1건. CMMS가 환경 경보와 함께 전환 대기 신호로 읽는다",
        [
            col("rule_id", "설비 경보 규칙", "bigint"),
            col("hvac_unit_id", "공조기", "bigint"),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'raised'",
                rule="raised / acknowledged / cleared(환경 경보와 같음)",
            ),
            col("raised_at", "발생 시각", "timestamptz"),
            col("acknowledged_at", "확인 시각", "timestamptz", nullable=True),
            col("cleared_at", "해제 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        ET,
        "건물 에너지 목표",
        "energy",
        "DSN-16 F42(Q6). 월·구역(NULL이면 건물 전체) kWh 목표",
        [
            col("target_month", "목표 월", "varchar(7)", rule="'YYYY-MM'"),
            col("zone_id", "구역", "bigint", nullable=True),
            col("target_kwh", "목표(kWh)", "numeric(14,2)"),
        ],
    ),
    table(
        CR,
        "공용 비용 배분 실행",
        "energy",
        "DSN-16 F43(Q6). 월 공용 전력 비용(FEMS TOU 요율 조회) → 부서 면적 비율. 확정 1건 + 새 버전",
        [
            col("cost_month", "배분 월", "varchar(7)", rule="'YYYY-MM'"),
            col("version", "버전", "integer"),
            col(
                "status", "상태", "varchar(12)", default="'draft'", rule=" / ".join(VER)
            ),
            col("total_kwh", "공용 사용량(kWh)", "numeric(14,2)"),
            col("total_cost", "공용 비용", "numeric(18,2)"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        CL,
        "공용 비용 배분",
        "energy",
        "DSN-16 F43. 부서별 면적·비율·비용",
        [
            col("cost_run_id", "배분 실행", "bigint"),
            col(
                "department_code",
                "부서 코드",
                "varchar(30)",
                rule="ERP 부서 코드 스냅샷(구역의 부서)",
            ),
            col("area_m2", "면적(㎡)", "numeric(12,2)"),
            col("share", "비율", "numeric(7,6)"),
            col("cost", "배분 비용", "numeric(18,2)"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
        ],
    ),
    table(
        ER,
        "월간 건물 에너지 보고서",
        "energy",
        "DSN-16 F41·F44(Q6). 공용 kWh·면적당 원단위(EUI)·목표 달성·비용·쾌적 시간 비율·이슈. 확정 스냅샷",
        [
            col("review_month", "보고 월", "varchar(7)", rule="'YYYY-MM'"),
            col("version", "버전", "integer"),
            col(
                "status", "상태", "varchar(12)", default="'draft'", rule=" / ".join(VER)
            ),
            col("total_kwh", "공용 사용량(kWh)", "numeric(14,2)"),
            col("eui_kwh_m2", "원단위(kWh/㎡)", "numeric(10,4)"),
            col("target_achievement", "목표 달성률", "numeric(7,4)", nullable=True),
            col("total_cost", "비용", "numeric(18,2)"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col("comfort_ratio", "쾌적 시간 비율", "numeric(5,4)", nullable=True),
            col("issues", "주요 이슈·조치", "varchar(2000)", nullable=True),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
]

NEW_COLUMNS = {
    B + "zone": [
        col("building_id", "건물", "bigint", nullable=True),
        col("floor_label", "층", "varchar(10)", nullable=True, rule="B1·1F·2F …"),
        col(
            "department_code",
            "사용 부서",
            "varchar(30)",
            nullable=True,
            rule="ERP 부서 코드 스냅샷(F43 면적 배분)",
        ),
    ],
    B + "hvac_unit": [
        col(
            "curtail_priority",
            "감축 우선순위",
            "integer",
            default="5",
            rule="1(먼저 감축)~9(마지막)",
        )
    ],
    B + "schedule_slot": [
        col("lighting_circuit_id", "조명 회로", "bigint", nullable=True)
    ],
    B + "control_command": [
        col("lighting_circuit_id", "조명 회로", "bigint", nullable=True),
        col("demand_plan_id", "피크 감축안", "bigint", nullable=True),
    ],
}

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in (BLD, LC, EAR):
    CONSTRAINTS += [
        c(t, "UK", S + ["code"], reason="세대 내 코드 유일"),
        c(t, "CHECK", ["code"], f"code {CODE}", "코드 형식"),
    ]
for t in (CR, CL, ER):
    CONSTRAINTS.append(c(t, "CHECK", ["currency"], "currency = 'KRW'", "KRW 고정"))
for t, period in [(CR, "cost_month"), (ER, "review_month")]:
    CONSTRAINTS += [
        c(t, "UK", S + [period, "version"], reason="기간·버전 유일"),
        c(t, "CHECK", [period], f"{period} {MONTH}", "'YYYY-MM' 형식"),
        c(
            t,
            "CHECK",
            ["status", "version", "confirmed_at"],
            "status IN ('draft', 'confirmed', 'superseded') AND version >= 1 AND ((status = 'draft') = (confirmed_at IS NULL))",
            "상태·버전",
        ),
        uk_partial(t, [period], "status = 'confirmed'", "기간당 확정 1건"),
    ]
CONSTRAINTS += [
    c(HOL, "UK", S + ["holiday_on"], reason="날짜당 1건"),
    c(
        HOL,
        "CHECK",
        ["kind", "name"],
        "kind IN ('PUBLIC', 'COMPANY') AND length(btrim(name)) > 0",
        "구분·이름",
    ),
    c(
        HOL,
        "SERVICE/DB_POLICY",
        ["holiday_on"],
        "업무 솔루션은 core 조회 함수(holidays(from, to))로 날짜만 읽는다. 업무 → core FK는 범위 앵커만 허용(FS-013 §6)이라 FK 없음. 요일 구분: 휴일 > 토·일(WEEKEND) > 평일",
        "공통 휴일 달력(Q1)",
    ),
    c(
        BLD,
        "CHECK",
        ["floors", "gross_area_m2"],
        "floors >= 1 AND gross_area_m2 > 0",
        "층수·면적",
    ),
    c(
        LC,
        "CHECK",
        ["state", "control_source", "rated_kw"],
        "state IN ('ON', 'OFF') AND control_source IN ('SCHEDULE', 'MANUAL', 'PEAK') AND rated_kw > 0",
        "상태·출처·전력",
    ),
    c(DP, "UK", S + ["plan_no"], reason="세대 내 번호 유일"),
    uk_partial(
        DP, ["fems_alarm_ref"], "status <> 'REJECTED'", "FEMS 경보 1건당 감축안 1건"
    ),
    c(
        DP,
        "CHECK",
        ["status", "target_reduction_kw"],
        "status IN ('PROPOSED', 'APPROVED', 'EXECUTED', 'RESTORED', 'REJECTED') AND target_reduction_kw > 0",
        "상태·목표",
    ),
    c(
        DP,
        "CHECK",
        ["status", "decided_at", "executed_at", "restored_at"],
        "((status = 'PROPOSED') = (decided_at IS NULL)) AND ((status IN ('EXECUTED', 'RESTORED')) = (executed_at IS NOT NULL)) AND ((status = 'RESTORED') = (restored_at IS NOT NULL))",
        "상태별 시각",
    ),
    c(
        DP,
        "SERVICE/DB_POLICY",
        ["status"],
        "자동 제어 없음(Q2). 승인 후 실행 = 단계마다 제어 명령(source PEAK). FEMS 경보가 해제되면 복귀 명령 제안 → 승인 시 RESTORED",
        "피크 감축 승인(Q2)",
    ),
    c(DPS, "UK", S + ["demand_plan_id", "seq"], reason="감축안 내 순서 유일"),
    c(
        DPS,
        "CHECK",
        ["hvac_unit_id", "lighting_circuit_id"],
        "(hvac_unit_id IS NULL) <> (lighting_circuit_id IS NULL)",
        "대상 하나",
    ),
    c(
        DPS,
        "CHECK",
        ["action", "delta_value", "expected_kw"],
        "action IN ('SET_FAN', 'RAISE_SETPOINT', 'POWER_OFF') AND ((action = 'RAISE_SETPOINT') = (delta_value IS NOT NULL)) AND (delta_value IS NULL OR delta_value BETWEEN 0.5 AND 5) AND expected_kw >= 0",
        "동작·폭·예상",
    ),
    c(CS, "UK", S + ["zone_kind", "metric"], reason="용도·지표당 기준 1건"),
    c(
        CS,
        "CHECK",
        ["zone_kind", "metric", "low", "high"],
        f"zone_kind IN ('OFFICE', 'PRODUCTION', 'UTILITY') AND metric IN ({q(m for m, _ in METRICS)}) AND (low IS NOT NULL OR high IS NOT NULL) AND (low IS NULL OR high IS NULL OR low < high)",
        "용도·지표·범위",
    ),
    c(
        EAR,
        "CHECK",
        ["condition", "threshold", "severity"],
        "condition IN ('COMMAND_REJECTED', 'LONG_RUN') AND threshold > 0 AND severity IN ('WARNING', 'CRITICAL')",
        "조건·기준·등급",
    ),
    c(
        EA,
        "CHECK",
        ["status", "acknowledged_at", "cleared_at", "raised_at"],
        "status IN ('raised', 'acknowledged', 'cleared') AND ((status = 'raised') = (acknowledged_at IS NULL AND cleared_at IS NULL)) AND ((status = 'cleared') = (cleared_at IS NOT NULL)) AND (cleared_at IS NULL OR cleared_at >= raised_at)",
        "상태별 시각",
    ),
    uk_partial(
        EA,
        ["rule_id", "hvac_unit_id"],
        "status <> 'cleared'",
        "규칙·설비당 진행 경보 1건",
    ),
    c(ET, "UK", S + ["target_month", "zone_id"], reason="월·구역 목표 1건"),
    uk_partial(ET, ["target_month"], "zone_id IS NULL", "월 건물 전체 목표 1건"),
    c(
        ET,
        "CHECK",
        ["target_month", "target_kwh"],
        f"target_month {MONTH} AND target_kwh > 0",
        "월·목표",
    ),
    c(
        CR,
        "CHECK",
        ["total_kwh", "total_cost"],
        "total_kwh >= 0 AND total_cost >= 0",
        "합계 음수 금지",
    ),
    c(
        CR,
        "SERVICE/DB_POLICY",
        ["total_cost"],
        "공용 비용 = 공용 사용량 시간별 × FEMS TOU 요율(fs.fems.interface 조회, FEMS 꺼지면 계산 거부). 부서 비율 = 부서 구역 면적 ÷ 부서 지정 구역 면적 합",
        "공용 비용 배분(Q6)",
    ),
    c(CL, "UK", S + ["cost_run_id", "department_code"], reason="실행·부서 1행"),
    c(
        CL,
        "CHECK",
        ["area_m2", "share", "cost"],
        "area_m2 > 0 AND share > 0 AND share <= 1 AND cost >= 0",
        "면적·비율·비용",
    ),
    c(
        ER,
        "CHECK",
        ["total_kwh", "eui_kwh_m2", "total_cost", "comfort_ratio"],
        "total_kwh >= 0 AND eui_kwh_m2 >= 0 AND total_cost >= 0 AND (comfort_ratio IS NULL OR comfort_ratio BETWEEN 0 AND 1)",
        "값 범위",
    ),
]
for t, cols_ in [
    (LC, ["zone_id"]),
    (DPS, ["demand_plan_id"]),
    (EA, ["hvac_unit_id", "raised_at"]),
    (CL, ["cost_run_id"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="FK·목록 조회"))

CHANGED_CONSTRAINTS = [
    c(
        B + "hvac_unit",
        "CHECK",
        ["curtail_priority"],
        "curtail_priority BETWEEN 1 AND 9",
        "감축 우선순위 범위",
    ),
    c(
        B + "schedule_slot",
        "CHECK",
        ["hvac_unit_id", "lighting_circuit_id", "mode"],
        "(hvac_unit_id IS NULL) <> (lighting_circuit_id IS NULL) AND ((lighting_circuit_id IS NOT NULL) = (mode = 'ON'))",
        "대상 하나, 조명은 ON",
    ),
    c(
        B + "control_command",
        "CHECK",
        ["hvac_unit_id", "lighting_circuit_id"],
        "NOT (hvac_unit_id IS NOT NULL AND lighting_circuit_id IS NOT NULL)",
        "대상 하나",
    ),
    c(
        B + "control_command",
        "CHECK",
        ["source", "demand_plan_id"],
        "(source = 'PEAK') = (demand_plan_id IS NOT NULL)",
        "피크 명령은 감축안 필수",
    ),
]
REPLACED = {
    (
        B + "sensor",
        "(metric = 'TEMP' AND unit = '℃') OR (metric = 'HUMIDITY' AND unit = '%') OR (metric = 'CO2' AND unit = 'ppm')",
    ): " OR ".join(f"(metric = '{m}' AND unit = '{u}')" for m, u in METRICS),
    (
        B + "schedule_slot",
        "day_kind IN ('WEEKDAY', 'WEEKEND')",
    ): "day_kind IN ('WEEKDAY', 'WEEKEND', 'HOLIDAY')",
    (
        B + "schedule_slot",
        "mode IN ('COOL', 'HEAT', 'FAN')",
    ): "mode IN ('COOL', 'HEAT', 'FAN', 'ON')",
    (
        B + "control_command",
        "command = 'SET_SETPOINT' OR hvac_unit_id IS NOT NULL",
    ): "command = 'SET_SETPOINT' OR hvac_unit_id IS NOT NULL OR lighting_circuit_id IS NOT NULL",
    (
        B + "control_command",
        "source IN ('MANUAL', 'SCHEDULE', 'SEED')",
    ): "source IN ('MANUAL', 'SCHEDULE', 'SEED', 'PEAK')",
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
    r(LC, ["zone_id"], B + "zone", "구역"),
    r(LC, ["meter_id"], B + "meter", "조명 계측기"),
    r(DPS, ["demand_plan_id"], DP, "감축안"),
    r(DPS, ["hvac_unit_id"], B + "hvac_unit", "공조기"),
    r(DPS, ["lighting_circuit_id"], LC, "조명 회로"),
    r(DPS, ["command_id"], B + "control_command", "실행 명령"),
    r(DPS, ["restore_command_id"], B + "control_command", "복귀 명령"),
    r(EAR, ["hvac_unit_id"], B + "hvac_unit", "공조기"),
    r(EA, ["rule_id"], EAR, "규칙"),
    r(EA, ["hvac_unit_id"], B + "hvac_unit", "공조기"),
    r(ET, ["zone_id"], B + "zone", "구역"),
    r(CL, ["cost_run_id"], CR, "배분 실행"),
    r(B + "zone", ["building_id"], BLD, "건물"),
    r(B + "schedule_slot", ["lighting_circuit_id"], LC, "조명 회로"),
    r(B + "control_command", ["lighting_circuit_id"], LC, "조명 회로"),
    r(B + "control_command", ["demand_plan_id"], DP, "피크 감축안"),
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
        DP,
        ("PROPOSED", "APPROVED", "EXECUTED", "RESTORED", "REJECTED"),
        "PROPOSED",
        "PROPOSED→APPROVED→EXECUTED→RESTORED; PROPOSED→REJECTED",
    ),
    st(
        EA,
        ("raised", "acknowledged", "cleared"),
        "raised",
        "raised→acknowledged→cleared; raised→cleared",
    ),
    st(CR, VER, "draft", "draft→confirmed→superseded"),
    st(ER, VER, "draft", "draft→confirmed→superseded"),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn16은 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "fems.alarm" not in names:
        raise SystemExit("apply_dsn15를 먼저 적용한다")
    if DP in names:
        return False
    hits = {(x["table"], x["expression"]) for x in d["constraints"]} & set(REPLACED)
    if len(hits) != len(REPLACED):
        raise SystemExit(f"바꿀 기존 제약을 찾지 못했다: {set(REPLACED) - hits}")
    tables = {t["name"]: t for t in d["tables"]}
    for name, columns in NEW_COLUMNS.items():
        cols = tables[name]["columns"]
        at = len(cols) - 1 if cols[-1]["name"] == "created_at" else len(cols)
        cols[at:at] = columns
    for x in tables[B + "schedule_slot"]["columns"]:
        if x["name"] == "hvac_unit_id":
            x.update(nullable=True, rule="DSN-16: 공조기 또는 조명 회로 중 하나")
    for x in d["constraints"]:
        new = REPLACED.get((x["table"], x["expression"]))
        if new:
            x["expression"] = new
    # 일괄 개발로 제품(schema.json)이 core.holiday를 먼저 가져가면 기준 복사본에 이미 있다.
    # 이 스크립트가 **새로 만드는 표** 중 이미 있는 것만 건너뛴다(기존 표에 더하는 제약·FK는 그대로).
    skip = {t["name"] for t in TABLES} & {t["name"] for t in d["tables"]}
    d["tables"].extend(t for t in TABLES if t["name"] not in skip)
    d["constraints"].extend(
        c for c in CONSTRAINTS + CHANGED_CONSTRAINTS if c["table"] not in skip
    )
    d["relations"].extend(r for r in RELATIONS if r["source"] not in skip)
    d["states"].extend(x for x in STATES if x["table"] not in skip)
    for code in d["code_lists"]:
        if code["target"] == B + "sensor" and code["column"] == "metric":
            code.update(
                values=[m for m, _ in METRICS], note=" / ".join(u for _, u in METRICS)
            )
    d.update(version="target-0.7.0", task="DSN-16", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.7.0",
            task="DSN-16",
            date="2026-10-05",
            change="BEMS 보강: core.holiday(공통 휴일) + bems 11(건물·조명 회로·피크 감축안 2·쾌적 기준·설비 경보 2·에너지 목표·공용 비용 배분 2·월간 보고서), 기존 6테이블 변경(구역 건물·층·부서, 공조기 감축 우선순위, 스케줄 조명·휴일, 제어 명령 조명·피크, 센서 지표 6종)",
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
    bems = [t for t in d["tables"] if t["name"].startswith(B)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                bems_tables=len(bems),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
