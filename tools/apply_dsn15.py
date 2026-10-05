"""DSN-15: FEMS 보강 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn14 다음).

근거: docs/modules/fems/FEMS_보강설계_DSN-15.md 4장(새 테이블 12·기존 테이블 변경 6), 결정 Q1~Q7.
계절 월 구분(여름 6~8·봄가을 3~5·9~10·겨울 11~2)은 코드 상수. 1시간 계측 유지(Q2), 피크는 시간 최대값 근사.
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
MONTH = "~ '^[0-9]{4}-(0[1-9]|1[0-2])$'"
F = "fems."


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-15"}


def money(name, label, nullable=False, rule=""):
    return col(name, label, "numeric(18,2)", nullable=nullable, rule=rule)


SEASONS = ("SUMMER", "SPRING_FALL", "WINTER")
BANDS = ("OFF_PEAK", "MID", "PEAK")
DAY_KINDS = ("WEEKDAY", "SATURDAY", "HOLIDAY")
ALARM_KINDS = ("THRESHOLD", "PEAK", "IDLE_USAGE")
VER = ("draft", "confirmed", "superseded")

TB, RU, RC, AR, AL, SP, ER, GI, GL, CR, CL, UB = (
    F + "tariff_band",
    F + "reading_upload",
    F + "reading_correction",
    F + "alarm_rule",
    F + "alarm",
    F + "saving_project",
    F + "energy_review",
    F + "ghg_inventory",
    F + "ghg_inventory_line",
    F + "cost_run",
    F + "cost_allocation_line",
    F + "utility_bill",
)

TABLES = [
    table(
        TB,
        "시간대별 요율",
        "tariff",
        "DSN-15 F05(Q1). 요금제 버전의 계절 × 요일 × 시간 구간 → 부하 구분·요율. 계절 월 구분은 코드 상수",
        [
            col("tariff_id", "요금제", "bigint"),
            col("season", "계절", "varchar(12)", rule=" / ".join(SEASONS)),
            col("day_kind", "요일 구분", "varchar(8)", rule=" / ".join(DAY_KINDS)),
            col("hour_from", "시작 시(포함)", "integer", rule="0~23"),
            col("hour_to", "끝 시(제외)", "integer", rule="1~24"),
            col("load_band", "부하 구분", "varchar(8)", rule=" / ".join(BANDS)),
            col("rate", "사용 요율(원/kWh)", "numeric(12,4)"),
        ],
    ),
    table(
        RU,
        "계측 파일 올리기",
        "reading",
        "DSN-15 F13. CSV 한 번 = 1행. 행별 검증 결과 합계만 저장, 반영 행은 계측(입력 방법 FILE)",
        [
            col("upload_no", "올리기 번호", "varchar(40)"),
            col("file_name", "파일 이름", "varchar(200)"),
            col("row_count", "행 수", "integer"),
            col("accepted_count", "반영", "integer"),
            col("rejected_count", "거부", "integer"),
            col("uploaded_at", "올린 시각", "timestamptz"),
            col("error_summary", "거부 사유 요약", "varchar(1000)", nullable=True),
        ],
    ),
    table(
        RC,
        "계측 보정",
        "reading",
        "DSN-15 F14. 결측·이상값 보정 이력. 보정은 새 입력 수정 버전으로 계측에 반영(원 값 보존)",
        [
            col("meter_channel_id", "계측 채널", "bigint"),
            col("period_start", "구간 시작", "timestamptz"),
            col(
                "original_value",
                "원 값",
                "numeric(20,6)",
                nullable=True,
                rule="결측이면 NULL",
            ),
            col("corrected_value", "보정 값", "numeric(20,6)"),
            col(
                "method",
                "보정 방법",
                "varchar(12)",
                rule="INTERPOLATE 보간 / PREVIOUS 직전값 / MANUAL 수동",
            ),
            col("reason", "사유", "varchar(300)"),
            col("corrected_at", "보정 시각", "timestamptz"),
        ],
    ),
    table(
        AR,
        "에너지 경보 규칙",
        "alarm",
        "DSN-15 F31. 임계 초과·피크 임박(계약전력 비율)·비가동 시간 사용",
        [
            col("code", "규칙 코드", "varchar(30)"),
            col("name", "규칙명", "varchar(100)"),
            col("alarm_kind", "종류", "varchar(10)", rule=" / ".join(ALARM_KINDS)),
            col("meter_channel_id", "계측 채널", "bigint", nullable=True),
            col("equipment_id", "설비", "bigint", nullable=True),
            col(
                "threshold",
                "임계값",
                "numeric(20,6)",
                rule="THRESHOLD: 시간 사용량, PEAK: 계약전력 대비 비율(0~1), IDLE_USAGE: 비가동 시간 사용량",
            ),
            col("unit", "단위", "varchar(10)"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        AL,
        "에너지 경보",
        "alarm",
        "DSN-15 F31·F34. 규칙당 진행 경보 1건. CMMS가 진행 경보를 전환 대기 신호로 읽는다",
        [
            col("alarm_rule_id", "경보 규칙", "bigint"),
            col("raised_at", "발생 시각", "timestamptz"),
            col("peak_value", "최대값", "numeric(20,6)"),
            col(
                "status",
                "상태",
                "varchar(8)",
                default="'OPEN'",
                rule="OPEN / ACK / CLEARED",
            ),
            col("acknowledged_at", "확인 시각", "timestamptz", nullable=True),
            col("cleared_at", "해제 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        SP,
        "절감 활동",
        "management",
        "DSN-15 F32(Q5). 예상 절감 → 시행 → 시행 전·후 같은 길이 기간 비교(생산량 보정)로 실제 절감 검증",
        [
            col("code", "활동 코드", "varchar(30)"),
            col("title", "제목", "varchar(200)"),
            col("equipment_id", "대상 설비", "bigint", nullable=True),
            col("energy_source_id", "에너지원", "bigint"),
            col("expected_saving", "예상 절감(연, 기본 단위)", "numeric(20,6)"),
            money("investment", "투자비"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col("start_on", "시행일", "date"),
            col("baseline_start_on", "비교 전 시작", "date"),
            col("baseline_end_on", "비교 전 끝", "date"),
            col("review_end_on", "비교 후 끝", "date", nullable=True),
            col(
                "measured_saving",
                "검증 절감(연 환산)",
                "numeric(20,6)",
                nullable=True,
                rule="검증 시점 스냅샷",
            ),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'PLANNED'",
                rule="PLANNED / ACTIVE / VERIFIED / CANCELLED",
            ),
            col("verified_at", "검증 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        ER,
        "월간 에너지 검토",
        "management",
        "DSN-15 F33(Q5). 월 마감 후 확정 스냅샷(사용·비용·원단위·목표·주요 이슈). 재작성은 새 버전",
        [
            col("review_month", "검토 월", "varchar(7)", rule="'YYYY-MM'"),
            col("version", "버전", "integer"),
            col(
                "status", "상태", "varchar(12)", default="'draft'", rule=" / ".join(VER)
            ),
            col(
                "primary_energy_toe",
                "1차에너지(toe)",
                "numeric(18,4)",
                rule="PRIMARY 계수 환산 후 합산",
            ),
            money("energy_cost", "에너지 비용"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col(
                "emission_tco2e", "배출량(tCO2e)", "numeric(18,4)", rule="EMISSION 계수"
            ),
            col("target_achievement", "목표 달성률", "numeric(7,4)", nullable=True),
            col("issues", "주요 이슈·조치", "varchar(2000)", nullable=True),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        GI,
        "온실가스 명세서",
        "ghg",
        "DSN-15 F35(Q6). 연간 Scope 1·2. 확정 후 불변, 재산정은 새 버전",
        [
            col("inventory_year", "보고 연도", "varchar(4)", rule="'YYYY'"),
            col("version", "버전", "integer"),
            col(
                "status", "상태", "varchar(12)", default="'draft'", rule=" / ".join(VER)
            ),
            col("scope1_tco2e", "Scope 1", "numeric(18,4)"),
            col("scope2_tco2e", "Scope 2", "numeric(18,4)"),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        GL,
        "명세서 배출 시설",
        "ghg",
        "DSN-15 F35. 설비(시설)·에너지원별 활동량 × 배출 계수(EMISSION, 해당 연도) 스냅샷",
        [
            col("ghg_inventory_id", "온실가스 명세서", "bigint"),
            col(
                "equipment_id",
                "배출 시설",
                "bigint",
                nullable=True,
                rule="NULL이면 사업장 공용",
            ),
            col("energy_source_id", "에너지원", "bigint"),
            col("scope", "범위", "integer", rule="1 연료 직접 / 2 전력·열 간접"),
            col("activity_qty", "활동량", "numeric(20,6)"),
            col("unit", "단위", "varchar(10)"),
            col("factor_value", "배출 계수", "numeric(20,10)", rule="스냅샷"),
            col("emission_tco2e", "배출량", "numeric(18,4)"),
        ],
    ),
    table(
        CR,
        "에너지 비용 배분 실행",
        "cost",
        "DSN-15 F43(Q4). 월 설비·부서·품목 배분. 확정 1건 + 새 버전. ERP가 참고로 읽음",
        [
            col("cost_month", "배분 월", "varchar(7)", rule="'YYYY-MM'"),
            col("version", "버전", "integer"),
            col(
                "status", "상태", "varchar(12)", default="'draft'", rule=" / ".join(VER)
            ),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        CL,
        "에너지 비용 배분",
        "cost",
        "DSN-15 F43. 설비 배분량 × 시간대별 요율 산정 비용. 부서·품목은 스냅샷",
        [
            col("cost_run_id", "배분 실행", "bigint"),
            col("equipment_id", "설비", "bigint"),
            col("energy_source_id", "에너지원", "bigint"),
            col(
                "department_code",
                "부서 코드",
                "varchar(30)",
                nullable=True,
                rule="ERP 부서 코드 스냅샷",
            ),
            col(
                "item_code",
                "주 생산 품목",
                "varchar(40)",
                nullable=True,
                rule="그 달 생산량 최다 품목",
            ),
            col("quantity", "사용량", "numeric(20,6)"),
            col("unit", "단위", "varchar(10)"),
            money("cost", "비용"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
        ],
    ),
    table(
        UB,
        "고지서 대조",
        "cost",
        "DSN-15 F42. 실제 청구 금액 입력 vs 산정(스냅샷). 회계 처리는 ERP 매입",
        [
            col("energy_source_id", "에너지원", "bigint"),
            col("bill_month", "청구 월", "varchar(7)", rule="'YYYY-MM'"),
            col("billed_qty", "청구 사용량", "numeric(20,6)"),
            money("billed_amount", "청구 금액"),
            money("calculated_amount", "산정 금액", rule="입력 시점 스냅샷"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col("note", "차이 사유", "varchar(300)", nullable=True),
        ],
    ),
]

NEW_COLUMNS = {
    F + "tariff": [
        col(
            "tariff_kind",
            "요금 구분",
            "varchar(4)",
            default="'FLAT'",
            rule="FLAT 단일 / TOU 시간대별(Q1)",
        ),
        col(
            "contract_kw",
            "계약전력(kW)",
            "numeric(12,2)",
            nullable=True,
            rule="TOU면 필수. 기본요금 = 계약전력 × basic_charge",
        ),
    ],
    F + "energy_reading": [
        col(
            "entry_method",
            "입력 방법",
            "varchar(6)",
            default="'METER'",
            rule="METER / MANUAL(검침) / FILE(F12·F13)",
        )
    ],
    F + "equipment": [
        col(
            "department_code",
            "부서 코드",
            "varchar(30)",
            nullable=True,
            rule="F06 ERP 부서 코드 스냅샷",
        )
    ],
    F + "production_record": [
        col(
            "source",
            "출처",
            "varchar(6)",
            default="'MANUAL'",
            rule="MES(조회 가져오기) / MANUAL(Q3)",
        )
    ],
}

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in (SP, ER, CL, UB):
    CONSTRAINTS.append(c(t, "CHECK", ["currency"], "currency = 'KRW'", "KRW 고정"))
for t in (AR, SP):
    CONSTRAINTS += [
        c(t, "UK", S + ["code"], reason="세대 내 코드 유일"),
        c(t, "CHECK", ["code"], f"code {CODE}", "코드 형식"),
    ]
for t, period, fmt in [
    (ER, "review_month", MONTH),
    (CR, "cost_month", MONTH),
    (GI, "inventory_year", "~ '^[0-9]{4}$'"),
]:
    CONSTRAINTS += [
        c(t, "UK", S + [period, "version"], reason="기간·버전 유일"),
        c(t, "CHECK", [period], f"{period} {fmt}", "기간 형식"),
        c(
            t,
            "CHECK",
            ["status", "version", "confirmed_at"],
            "status IN ('draft', 'confirmed', 'superseded') AND version >= 1 AND ((status = 'draft') = (confirmed_at IS NULL))",
            "상태·버전",
        ),
        uk_partial(
            t, [period], "status = 'confirmed'", "기간당 확정 1건(재작성은 새 버전)"
        ),
    ]
CONSTRAINTS += [
    c(
        TB,
        "CHECK",
        ["season", "day_kind", "load_band"],
        f"season IN ({q(SEASONS)}) AND day_kind IN ({q(DAY_KINDS)}) AND load_band IN ({q(BANDS)})",
        "계절·요일·부하 값",
    ),
    c(
        TB,
        "CHECK",
        ["hour_from", "hour_to", "rate"],
        "hour_from BETWEEN 0 AND 23 AND hour_to BETWEEN 1 AND 24 AND hour_to > hour_from AND rate >= 0",
        "시간 구간·요율",
    ),
    c(
        TB,
        "UK",
        S + ["tariff_id", "season", "day_kind", "hour_from"],
        reason="요금제·계절·요일·시작 시 1구간",
    ),
    c(
        TB,
        "SERVICE/DB_POLICY",
        ["hour_from", "hour_to"],
        "같은 요금제·계절·요일의 구간은 0~24시를 겹침 없이 빈틈없이 덮는다(저장 시 검사). TOU 요금제는 3계절 × 3요일이 모두 있어야 게시",
        "구간 완전성(Q1)",
    ),
    c(RU, "UK", S + ["upload_no"], reason="세대 내 번호 유일"),
    c(
        RU,
        "CHECK",
        ["row_count", "accepted_count", "rejected_count"],
        "row_count >= 0 AND accepted_count >= 0 AND rejected_count >= 0 AND accepted_count + rejected_count = row_count",
        "행 합계",
    ),
    c(
        RC,
        "CHECK",
        ["method", "reason"],
        "method IN ('INTERPOLATE', 'PREVIOUS', 'MANUAL') AND length(btrim(reason)) >= 2",
        "방법·사유",
    ),
    c(
        RC,
        "SERVICE/DB_POLICY",
        ["corrected_value"],
        "보정은 같은 채널·구간 계측의 새 input_revision(quality estimated)으로 반영, 원 계측은 남긴다. 배분·원단위는 최신 revision 기준",
        "보정 = 새 버전",
    ),
    c(
        AR,
        "CHECK",
        ["alarm_kind", "threshold", "meter_channel_id", "equipment_id"],
        f"alarm_kind IN ({q(ALARM_KINDS)}) AND threshold > 0 AND (meter_channel_id IS NOT NULL OR equipment_id IS NOT NULL) AND (alarm_kind <> 'PEAK' OR threshold <= 1)",
        "종류·임계·대상",
    ),
    c(
        AL,
        "CHECK",
        ["status", "acknowledged_at", "cleared_at", "raised_at"],
        "status IN ('OPEN', 'ACK', 'CLEARED') AND ((status = 'OPEN') = (acknowledged_at IS NULL AND cleared_at IS NULL)) AND ((status = 'CLEARED') = (cleared_at IS NOT NULL)) AND (cleared_at IS NULL OR cleared_at >= raised_at)",
        "상태별 시각",
    ),
    uk_partial(AL, ["alarm_rule_id"], "status <> 'CLEARED'", "규칙당 진행 경보 1건"),
    c(
        SP,
        "CHECK",
        ["status", "expected_saving", "investment"],
        "status IN ('PLANNED', 'ACTIVE', 'VERIFIED', 'CANCELLED') AND expected_saving > 0 AND investment >= 0",
        "상태·예상·투자",
    ),
    c(
        SP,
        "CHECK",
        ["baseline_start_on", "baseline_end_on", "start_on", "review_end_on"],
        "baseline_end_on > baseline_start_on AND baseline_end_on <= start_on AND (review_end_on IS NULL OR review_end_on > start_on)",
        "비교 기간 순서",
    ),
    c(
        SP,
        "CHECK",
        ["status", "measured_saving", "verified_at"],
        "(status = 'VERIFIED') = (verified_at IS NOT NULL AND measured_saving IS NOT NULL)",
        "검증 값",
    ),
    c(
        SP,
        "SERVICE/DB_POLICY",
        ["measured_saving"],
        "실제 절감 = (비교 전 원단위 − 비교 후 원단위) × 비교 후 생산량, 연 환산. 비교 후 기간은 비교 전과 같은 길이. 검증 후 불변",
        "절감 측정·검증(Q5)",
    ),
    c(
        ER,
        "CHECK",
        ["primary_energy_toe", "energy_cost", "emission_tco2e"],
        "primary_energy_toe >= 0 AND energy_cost >= 0 AND emission_tco2e >= 0",
        "값 음수 금지",
    ),
    c(
        ER,
        "SERVICE/DB_POLICY",
        ["primary_energy_toe", "emission_tco2e"],
        "1차에너지는 PRIMARY 계수로 환산 후 합산, 배출은 EMISSION 계수 — 섞지 않는다(AGENTS §3). 확정 = 그 달 스냅샷",
        "환산·배출 계수 분리",
    ),
    c(
        GI,
        "CHECK",
        ["scope1_tco2e", "scope2_tco2e"],
        "scope1_tco2e >= 0 AND scope2_tco2e >= 0",
        "배출 음수 금지",
    ),
    c(
        GL,
        "CHECK",
        ["scope", "activity_qty", "factor_value", "emission_tco2e"],
        "scope IN (1, 2) AND activity_qty >= 0 AND factor_value >= 0 AND emission_tco2e >= 0",
        "범위·값",
    ),
    c(
        GL,
        "UK",
        S + ["ghg_inventory_id", "equipment_id", "energy_source_id"],
        reason="명세서·시설·에너지원 1행",
    ),
    uk_partial(
        GL,
        ["ghg_inventory_id", "energy_source_id"],
        "equipment_id IS NULL",
        "사업장 공용 행 에너지원당 1행",
    ),
    c(
        GI,
        "SERVICE/DB_POLICY",
        ["scope1_tco2e", "scope2_tco2e"],
        "Scope 1 = 연료(FUEL), Scope 2 = 전력(ELECTRIC)·열(HEAT), 계수는 그 연도 EMISSION. 합계 = 배출 시설 합. 확정 후 불변(Q6)",
        "온실가스 명세서(Q6)",
    ),
    c(
        CL,
        "UK",
        S + ["cost_run_id", "equipment_id", "energy_source_id"],
        reason="실행·설비·에너지원 1행",
    ),
    c(CL, "CHECK", ["quantity", "cost"], "quantity >= 0 AND cost >= 0", "값 음수 금지"),
    c(
        CR,
        "SERVICE/DB_POLICY",
        ["status"],
        "비용 = 설비 배분량 × 시간대별 요율(TOU) + 기본요금 사용량 비율 배분. 확정분을 fs.fems.interface.energy_costs(month)로 ERP가 참고로 읽음(원가 배부 기준은 ERP 생산량 그대로, Q4)",
        "비용 배분 제공(Q4)",
    ),
    c(
        UB,
        "UK",
        S + ["energy_source_id", "bill_month"],
        reason="에너지원·월 고지서 1건",
    ),
    c(UB, "CHECK", ["bill_month"], f"bill_month {MONTH}", "'YYYY-MM' 형식"),
    c(
        UB,
        "CHECK",
        ["billed_qty", "billed_amount", "calculated_amount"],
        "billed_qty >= 0 AND billed_amount >= 0 AND calculated_amount >= 0",
        "값 음수 금지",
    ),
]
for t, cols_ in [
    (TB, ["tariff_id"]),
    (RC, ["meter_channel_id", "period_start"]),
    (AL, ["alarm_rule_id", "raised_at"]),
    (GL, ["ghg_inventory_id"]),
    (CL, ["cost_run_id"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="FK·목록 조회"))

CHANGED_CONSTRAINTS = [
    c(
        F + "tariff",
        "CHECK",
        ["tariff_kind", "contract_kw"],
        "tariff_kind IN ('FLAT', 'TOU') AND (tariff_kind = 'FLAT' OR contract_kw > 0)",
        "TOU는 계약전력 필수(Q1)",
    ),
    c(
        F + "energy_reading",
        "CHECK",
        ["entry_method"],
        "entry_method IN ('METER', 'MANUAL', 'FILE')",
        "입력 방법 값",
    ),
    c(
        F + "production_record",
        "CHECK",
        ["source"],
        "source IN ('MES', 'MANUAL')",
        "출처 값",
    ),
    c(
        F + "production_record",
        "SERVICE/DB_POLICY",
        ["source"],
        "MES 출처는 fs.mes.interface.production_results(month)를 읽어 새 version_no로 확정(원 행 불변). MES 꺼짐이면 수동만",
        "MES 생산량 가져오기(Q3)",
    ),
]
REPLACED = {
    (
        F + "energy_source",
        "source_kind IN ('ELECTRIC','FUEL','HEAT','UTILITY')",
    ): "source_kind IN ('ELECTRIC','FUEL','HEAT','UTILITY','GENERATION')",
    (
        F + "meter",
        "scope_kind IN ('factory','site_total')",
    ): "scope_kind IN ('factory','site_total','generation')",
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
    r(TB, ["tariff_id"], F + "tariff", "요금제"),
    r(RC, ["meter_channel_id"], F + "meter_channel", "계측 채널"),
    r(AR, ["meter_channel_id"], F + "meter_channel", "계측 채널"),
    r(AR, ["equipment_id"], F + "equipment", "설비"),
    r(AL, ["alarm_rule_id"], AR, "경보 규칙"),
    r(SP, ["equipment_id"], F + "equipment", "대상 설비"),
    r(SP, ["energy_source_id"], F + "energy_source", "에너지원"),
    r(GL, ["ghg_inventory_id"], GI, "명세서"),
    r(GL, ["equipment_id"], F + "equipment", "배출 시설"),
    r(GL, ["energy_source_id"], F + "energy_source", "에너지원"),
    r(CL, ["cost_run_id"], CR, "배분 실행"),
    r(CL, ["equipment_id"], F + "equipment", "설비"),
    r(CL, ["energy_source_id"], F + "energy_source", "에너지원"),
    r(UB, ["energy_source_id"], F + "energy_source", "에너지원"),
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
        AL,
        ("OPEN", "ACK", "CLEARED"),
        "OPEN",
        "OPEN→ACK(확인)→CLEARED(조건 해소); OPEN→CLEARED",
    ),
    st(
        SP,
        ("PLANNED", "ACTIVE", "VERIFIED", "CANCELLED"),
        "PLANNED",
        "PLANNED→ACTIVE(시행)→VERIFIED(절감 검증); 검증 전 CANCELLED",
    ),
    st(ER, VER, "draft", "draft→confirmed→superseded"),
    st(GI, VER, "draft", "draft→confirmed→superseded"),
    st(CR, VER, "draft", "draft→confirmed→superseded"),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn15는 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "qms.ncr" not in names:
        raise SystemExit("apply_dsn14를 먼저 적용한다")
    if AL in names:
        return False
    hits = {(x["table"], x["expression"]) for x in d["constraints"]} & set(REPLACED)
    if len(hits) != len(REPLACED):
        raise SystemExit(f"바꿀 기존 제약을 찾지 못했다: {set(REPLACED) - hits}")
    tables = {t["name"]: t for t in d["tables"]}
    for name, columns in NEW_COLUMNS.items():
        cols = tables[name]["columns"]
        at = len(cols) - 1 if cols[-1]["name"] == "created_at" else len(cols)
        cols[at:at] = columns
    for x in d["constraints"]:
        new = REPLACED.get((x["table"], x["expression"]))
        if new:
            x["expression"] = new
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS + CHANGED_CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    for code in d["code_lists"]:
        if (
            code["target"] == F + "energy_source"
            and code["column"] == "source_kind"
            and "GENERATION" not in code["values"]
        ):
            code["values"] = [*code["values"], "GENERATION"]
    d["code_lists"].append(
        dict(
            target=TB,
            column="load_band",
            values=list(BANDS),
            default=None,
            note="경부하 / 중간부하 / 최대부하",
        )
    )
    d.update(version="target-0.6.0", task="DSN-15", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.6.0",
            task="DSN-15",
            date="2026-10-05",
            change="FEMS 보강: 새 테이블 12(시간대별 요율·계측 파일·계측 보정·경보 규칙/경보·절감 활동·월간 검토·온실가스 명세서 2·비용 배분 2·고지서 대조), 기존 6테이블 변경(요금제 TOU·계약전력, 계측 입력 방법, 설비 부서, 생산량 출처, 에너지원 GENERATION, 계측기 generation)",
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
    fems = [t for t in d["tables"] if t["name"].startswith(F)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                fems_tables=len(fems),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
