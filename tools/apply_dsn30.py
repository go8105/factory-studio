"""DSN-30: HR(신규) 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn29 다음).

근거: docs/modules/hr/HR_설계_DSN-30.md 4장(hr 19테이블 + 모듈 키 'hr'), 결정 Q1~Q8. ROADMAP-02 D79.
Q1: HR이 사원·부서 코드 원천 — 각 솔루션은 "HR에서 가져오기"(스냅샷, FK 없음). 민감 정보(주민번호·계좌·주소·가족) 칸 없음.
Q2: 일 근태는 근무 형태·core 휴일로 자동 생성 + 예외 수정. Q3: 휴가는 HR 자체 부서장 승인.
Q4: 월급제, 공제는 합성 고정 비율, 확정 후 불변(재계산은 새 버전). Q5 상여·퇴직금 추계(조회). Q6 자격·교육·인사 평가.
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
MONTH = "~ '^[0-9]{4}-(0[1-9]|1[0-2])$'"
YEAR = "~ '^[0-9]{4}$'"
P = "hr."
MODULE_TABLES = {"core.workspace_module", "core.app_review"}
VER = ("draft", "confirmed", "superseded")


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-30"}


def ver_cols():
    return [
        col("version", "버전", "integer", default="1"),
        col("status", "상태", "varchar(12)", default="'draft'", rule=" / ".join(VER)),
        col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
    ]


def money(name, label, nullable=False):
    return col(name, label, "numeric(18,0)", nullable=nullable, rule="원")


(DP, TT, WP, EM, AP, QL, AT, AC, LB, LR, PI, PB, PBI, BR, PR, PS, PSL, RC, RV) = (
    P + n
    for n in (
        "department",
        "title",
        "work_pattern",
        "employee",
        "appointment",
        "qualification",
        "attendance",
        "attendance_close",
        "leave_balance",
        "leave_request",
        "pay_item",
        "pay_base",
        "pay_base_item",
        "bonus_rule",
        "payroll_run",
        "payslip",
        "payslip_line",
        "review_cycle",
        "review",
    )
)

TABLES = [
    table(
        DP,
        "부서",
        "org",
        "DSN-30 F01(Q1). 부서 코드 원천. 상위 부서로 계층. ERP·ELB 등은 코드를 가져가 맞춘다(FK 없음)",
        [
            col("code", "부서 코드", "varchar(30)"),
            col("name", "부서명", "varchar(100)"),
            col("parent_id", "상위 부서", "bigint", nullable=True),
            col("display_order", "표시 순서", "integer", default="1"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        TT,
        "직위·직책",
        "org",
        "DSN-30 F01. GRADE 직위(사원·대리·과장…) / DUTY 직책(팀장·부서장). 부서장 직책이 휴가 승인자(Q3)",
        [
            col("title_kind", "구분", "varchar(6)", rule="GRADE / DUTY"),
            col("code", "코드", "varchar(30)"),
            col("name", "이름", "varchar(60)"),
            col("rank_order", "서열", "integer"),
            col(
                "is_head",
                "부서장 여부",
                "boolean",
                default="false",
                rule="DUTY만. 휴가 승인 권한",
            ),
        ],
    ),
    table(
        WP,
        "근무 형태",
        "attendance",
        "DSN-30 F11. 일근·교대. 정상 근태 자동 생성의 기준(Q2). MES 근무조와 별개(FS-013 D1)",
        [
            col("code", "코드", "varchar(30)"),
            col("name", "이름", "varchar(60)"),
            col(
                "pattern_kind",
                "유형",
                "varchar(12)",
                rule="DAY / TWO_SHIFT / THREE_SHIFT",
            ),
            col("start_time", "시작 시각", "time"),
            col("scheduled_minutes", "소정 근로(분)", "integer"),
            col("break_minutes", "휴게(분)", "integer", default="60"),
            col("works_weekend", "주말 근무", "boolean", default="false"),
        ],
    ),
    table(
        EM,
        "사원",
        "org",
        "DSN-30 F02·F04(Q1). 사원 코드 원천. 현재 부서·직위·직책은 확정 발령으로만 바뀐다. 민감 정보 칸 없음(D79)",
        [
            col("employee_code", "사원 코드", "varchar(30)"),
            col("name", "이름", "varchar(60)"),
            col("hire_date", "입사일", "date"),
            col(
                "status",
                "재직 상태",
                "varchar(8)",
                default="'ACTIVE'",
                rule="ACTIVE 재직 / LEAVE 휴직 / RETIRED 퇴직",
            ),
            col("department_id", "현재 부서", "bigint"),
            col("grade_id", "현재 직위", "bigint"),
            col("duty_id", "현재 직책", "bigint", nullable=True),
            col("work_pattern_id", "근무 형태", "bigint"),
            col("retire_date", "퇴직일", "date", nullable=True),
            col("retire_reason", "퇴직 사유", "varchar(200)", nullable=True),
        ],
    ),
    table(
        AP,
        "발령",
        "org",
        "DSN-30 F03·F04. 입사·이동·승진·직책·휴직·복직·퇴직. 확정 시 사원 현재값 갱신, 이후 불변",
        [
            col("appointment_no", "발령 번호", "varchar(30)"),
            col("employee_id", "사원", "bigint"),
            col(
                "kind",
                "발령 종류",
                "varchar(10)",
                rule="HIRE / TRANSFER / PROMOTION / DUTY / LEAVE / RETURN / RETIRE",
            ),
            col("effective_date", "발령일", "date"),
            col("department_id", "부서", "bigint", nullable=True),
            col("grade_id", "직위", "bigint", nullable=True),
            col("duty_id", "직책", "bigint", nullable=True),
            col("reason", "사유", "varchar(200)", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'draft'",
                rule="draft / confirmed",
            ),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        QL,
        "자격·교육",
        "org",
        "DSN-30 F06(Q6). 설비 운전 자격·안전 교육 등. 만료 30일 전 경고(조회)",
        [
            col("employee_id", "사원", "bigint"),
            col("qual_kind", "구분", "varchar(8)", rule="CERT 자격 / TRAINING 교육"),
            col("name", "자격·과정명", "varchar(100)"),
            col("issuer", "발급·주관", "varchar(100)", nullable=True),
            col("acquired_on", "취득·이수일", "date"),
            col("expires_on", "만료일", "date", nullable=True),
        ],
    ),
    table(
        AT,
        "일 근태",
        "attendance",
        "DSN-30 F12·F14(Q2). 근무 형태·core 휴일로 자동 생성(AUTO) 후 예외만 수정(MANUAL). 월 마감 확정 후 수정 불가",
        [
            col("employee_id", "사원", "bigint"),
            col("work_date", "근무일", "date"),
            col(
                "day_kind",
                "일 구분",
                "varchar(8)",
                rule="WORKDAY / OFFDAY / HOLIDAY(core 휴일)",
            ),
            col(
                "status",
                "근태",
                "varchar(10)",
                rule="NORMAL / LATE / EARLY / ABSENT / LEAVE / HALF_LEAVE / OFF",
            ),
            col("clock_in", "출근", "timestamptz", nullable=True),
            col("clock_out", "퇴근", "timestamptz", nullable=True),
            col("overtime_minutes", "연장(분)", "integer", default="0"),
            col("night_minutes", "야간(분)", "integer", default="0", rule="22~06시"),
            col("holiday_minutes", "휴일 근로(분)", "integer", default="0"),
            col("source", "출처", "varchar(6)", default="'AUTO'", rule="AUTO / MANUAL"),
            col("note", "비고", "varchar(200)", nullable=True),
        ],
    ),
    table(
        AC,
        "월 근태 마감",
        "attendance",
        "DSN-30 F15. 월당 확정 1건. 확정 시 사원별 합계를 급여 입력으로 고정. 재마감은 새 버전",
        [col("close_month", "마감 월", "varchar(7)", rule="'YYYY-MM'"), *ver_cols()],
    ),
    table(
        LB,
        "연차 발생",
        "leave",
        "DSN-30 F13. 사원·연도별 발생 일수. 사용·잔여는 승인 휴가에서 조회 계산",
        [
            col("employee_id", "사원", "bigint"),
            col("leave_year", "연도", "varchar(4)", rule="'YYYY'"),
            col("granted_days", "발생 일수", "numeric(5,1)"),
        ],
    ),
    table(
        LR,
        "휴가 신청",
        "leave",
        "DSN-30 F13(Q3). 부서장(HR 조직의 부서장 직책) 승인. 승인 시 일 근태를 LEAVE로",
        [
            col("request_no", "신청 번호", "varchar(30)"),
            col("employee_id", "사원", "bigint"),
            col(
                "leave_kind",
                "휴가 종류",
                "varchar(8)",
                rule="ANNUAL / HALF_AM / HALF_PM / SICK / SPECIAL",
            ),
            col("from_date", "시작일", "date"),
            col("to_date", "종료일", "date"),
            col("days", "일수", "numeric(4,1)"),
            col("reason", "사유", "varchar(200)", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'REQUESTED'",
                rule="REQUESTED / APPROVED / REJECTED / CANCELLED",
            ),
            col("approver_code", "승인자 사원 코드", "varchar(30)", nullable=True),
            col("decided_at", "처리 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        PI,
        "급여 항목",
        "payroll",
        "DSN-30 F21(Q4). 지급·공제. 계산 방식별 비율(연장 1.5배·공제 %)은 합성 고정값",
        [
            col("code", "항목 코드", "varchar(30)"),
            col("name", "항목명", "varchar(60)"),
            col(
                "item_kind", "구분", "varchar(10)", rule="EARNING 지급 / DEDUCTION 공제"
            ),
            col(
                "calc_kind",
                "계산 방식",
                "varchar(10)",
                rule="BASE 기본급 / FIXED 고정 / OVERTIME / NIGHT / HOLIDAY(통상시급 × rate) / BONUS / RATE(과세 지급 합계 × rate%)",
            ),
            col("rate", "배율·비율", "numeric(8,4)", nullable=True),
            col("is_taxable", "과세", "boolean", default="true"),
            col("display_order", "순서", "integer"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        PB,
        "급여 기준",
        "payroll",
        "DSN-30 F22. 사원별 기본급, 적용 시작 월 이력(가장 최근 시작 월 적용)",
        [
            col("employee_id", "사원", "bigint"),
            col("effective_from", "적용 시작 월", "varchar(7)", rule="'YYYY-MM'"),
            money("base_salary", "월 기본급"),
            col("ordinary_hours", "월 통상 근로시간", "integer", default="209"),
        ],
    ),
    table(
        PBI,
        "급여 기준 고정 수당",
        "payroll",
        "DSN-30 F22. 급여 기준별 FIXED 항목 금액",
        [
            col("pay_base_id", "급여 기준", "bigint"),
            col("pay_item_id", "급여 항목", "bigint"),
            money("amount", "금액"),
        ],
    ),
    table(
        BR,
        "상여 규칙",
        "payroll",
        "DSN-30 F27(Q5). 지정 월에 기본급 × 지급률을 BONUS 항목으로 계산",
        [
            col("payable_mm", "지급 월", "varchar(2)", rule="'01'~'12'"),
            col("rate_percent", "지급률(%)", "numeric(6,2)"),
            col("pay_item_id", "상여 항목", "bigint"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        PR,
        "급여 실행",
        "payroll",
        "DSN-30 F23·F24(Q4). 월당 확정 1건. 확정 근태 마감을 입력으로 계산, 확정 후 불변, 재계산은 새 버전. ERP F94가 확정 결과를 읽음",
        [
            col("pay_month", "급여 월", "varchar(7)", rule="'YYYY-MM'"),
            col("attendance_close_id", "근태 마감", "bigint"),
            col("pay_date", "지급일", "date"),
            *ver_cols(),
        ],
    ),
    table(
        PS,
        "급여명세서",
        "payroll",
        "DSN-30 F25. 사원별 합계와 부서·직위 스냅샷(ERP 부서별 합계의 기준)",
        [
            col("run_id", "급여 실행", "bigint"),
            col("employee_id", "사원", "bigint"),
            col("department_code", "부서 코드", "varchar(30)", rule="계산 시점 스냅샷"),
            col("grade_name", "직위", "varchar(60)"),
            money("gross_pay", "지급 합계"),
            money("deduction_total", "공제 합계"),
            money("net_pay", "실지급액"),
        ],
    ),
    table(
        PSL,
        "급여명세 항목",
        "payroll",
        "DSN-30 F23·F25. 항목별 금액과 근거 수량(분·일)",
        [
            col("payslip_id", "급여명세서", "bigint"),
            col("pay_item_id", "급여 항목", "bigint"),
            col("item_code", "항목 코드", "varchar(30)", rule="스냅샷"),
            money("amount", "금액"),
            col("basis_quantity", "근거 수량", "numeric(10,2)", nullable=True),
        ],
    ),
    table(
        RC,
        "평가 기간",
        "review",
        "DSN-30 F31(Q6). 연도별 평가 기간",
        [
            col("cycle_year", "평가 연도", "varchar(4)", rule="'YYYY'"),
            col("name", "이름", "varchar(60)"),
            col("status", "상태", "varchar(8)", default="'OPEN'", rule="OPEN / CLOSED"),
        ],
    ),
    table(
        RV,
        "인사 평가",
        "review",
        "DSN-30 F31(Q6). 목표·자기 평가·평가자 등급. 확정 후 불변",
        [
            col("cycle_id", "평가 기간", "bigint"),
            col("employee_id", "사원", "bigint"),
            col("goals", "목표", "varchar(2000)"),
            col("self_comment", "자기 평가", "varchar(2000)", nullable=True),
            col("reviewer_code", "평가자 사원 코드", "varchar(30)"),
            col("grade", "등급", "varchar(1)", nullable=True, rule="S / A / B / C / D"),
            col("reviewer_comment", "평가 의견", "varchar(2000)", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'draft'",
                rule="draft / submitted / confirmed",
            ),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
]

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in (AC, PR):
    CONSTRAINTS.append(
        c(
            t,
            "CHECK",
            ["status", "version", "confirmed_at"],
            f"status IN ({q(VER)}) AND version >= 1 AND ((status = 'draft') = (confirmed_at IS NULL))",
            "상태·버전",
        )
    )
CONSTRAINTS += [
    c(DP, "UK", S + ["code"], reason="부서 코드 유일"),
    c(DP, "CHECK", ["code"], f"code {CODE}", "코드 형식"),
    c(TT, "UK", S + ["title_kind", "code"], reason="구분·코드 유일"),
    c(
        TT,
        "CHECK",
        ["title_kind", "code", "rank_order", "is_head"],
        f"title_kind IN ('GRADE', 'DUTY') AND code {CODE} AND rank_order >= 1 AND (title_kind = 'DUTY' OR NOT is_head)",
        "구분·부서장은 직책만",
    ),
    c(WP, "UK", S + ["code"], reason="근무 형태 코드 유일"),
    c(
        WP,
        "CHECK",
        ["pattern_kind", "scheduled_minutes", "break_minutes"],
        "pattern_kind IN ('DAY', 'TWO_SHIFT', 'THREE_SHIFT') AND scheduled_minutes BETWEEN 1 AND 720 AND break_minutes >= 0",
        "유형·시간",
    ),
    c(EM, "UK", S + ["employee_code"], reason="사원 코드 유일"),
    c(
        EM,
        "CHECK",
        ["employee_code", "status", "retire_date"],
        f"employee_code {CODE} AND status IN ('ACTIVE', 'LEAVE', 'RETIRED') AND ((status = 'RETIRED') = (retire_date IS NOT NULL)) AND (retire_date IS NULL OR retire_date >= hire_date)",
        "코드·상태·퇴직일",
    ),
    c(
        EM,
        "SERVICE/DB_POLICY",
        ["employee_code"],
        "사람 원천(Q1): fs.hr.interface.employees()·departments()가 코드·이름·부서·재직 상태를 돌려준다. 각 솔루션은 'HR에서 가져오기'로 자기 사람 마스터를 만들고 hr_employee_code를 스냅샷(자동 동기화 없음, 퇴직은 조회 때 표시). 현재 부서·직위·직책은 확정 발령으로만 바뀐다",
        "사람 원천(Q1)",
    ),
    c(AP, "UK", S + ["appointment_no"], reason="발령 번호 유일"),
    c(
        AP,
        "CHECK",
        ["appointment_no", "kind", "status", "confirmed_at"],
        f"appointment_no {CODE} AND kind IN ('HIRE', 'TRANSFER', 'PROMOTION', 'DUTY', 'LEAVE', 'RETURN', 'RETIRE') AND status IN ('draft', 'confirmed') AND ((status = 'confirmed') = (confirmed_at IS NOT NULL))",
        "종류·상태",
    ),
    c(
        AP,
        "CHECK",
        ["kind", "department_id", "grade_id"],
        "(kind NOT IN ('HIRE', 'TRANSFER') OR department_id IS NOT NULL) AND (kind NOT IN ('HIRE', 'PROMOTION') OR grade_id IS NOT NULL)",
        "입사·이동은 부서, 입사·승진은 직위 필수",
    ),
    c(
        AP,
        "SERVICE/DB_POLICY",
        ["status"],
        "확정 시 사원 현재값(부서·직위·직책·상태·퇴직일)을 갱신하고 이후 불변. 정정은 새 발령",
        "발령 확정",
    ),
    c(
        QL,
        "CHECK",
        ["qual_kind", "expires_on"],
        "qual_kind IN ('CERT', 'TRAINING') AND (expires_on IS NULL OR expires_on >= acquired_on)",
        "구분·만료일",
    ),
    c(AT, "UK", S + ["employee_id", "work_date"], reason="사원·일 1건"),
    c(
        AT,
        "CHECK",
        [
            "day_kind",
            "status",
            "source",
            "overtime_minutes",
            "night_minutes",
            "holiday_minutes",
        ],
        "day_kind IN ('WORKDAY', 'OFFDAY', 'HOLIDAY') AND status IN ('NORMAL', 'LATE', 'EARLY', 'ABSENT', 'LEAVE', 'HALF_LEAVE', 'OFF') AND source IN ('AUTO', 'MANUAL') AND overtime_minutes >= 0 AND night_minutes >= 0 AND holiday_minutes >= 0 AND (clock_out IS NULL OR clock_in IS NULL OR clock_out > clock_in)",
        "구분·근태·시간",
    ),
    c(
        AT,
        "SERVICE/DB_POLICY",
        ["source"],
        "월 단위 자동 생성: 근무 형태 + core.holiday(날짜) → 정상 근태(AUTO). 승인 휴가는 LEAVE. 예외 수정은 MANUAL. 그 달 근태 마감이 확정이면 수정 거부",
        "근태 자동 생성(Q2)",
    ),
    c(AC, "UK", S + ["close_month", "version"], reason="월·버전 유일"),
    c(AC, "CHECK", ["close_month"], f"close_month {MONTH}", "'YYYY-MM' 형식"),
    uk_partial(AC, ["close_month"], "status = 'confirmed'", "월당 확정 마감 1건"),
    c(LB, "UK", S + ["employee_id", "leave_year"], reason="사원·연도 1건"),
    c(
        LB,
        "CHECK",
        ["leave_year", "granted_days"],
        f"leave_year {YEAR} AND granted_days >= 0",
        "연도·일수",
    ),
    c(LR, "UK", S + ["request_no"], reason="신청 번호 유일"),
    c(
        LR,
        "CHECK",
        ["leave_kind", "status", "from_date", "to_date", "days", "decided_at"],
        "leave_kind IN ('ANNUAL', 'HALF_AM', 'HALF_PM', 'SICK', 'SPECIAL') AND status IN ('REQUESTED', 'APPROVED', 'REJECTED', 'CANCELLED') AND to_date >= from_date AND days > 0 AND ((leave_kind IN ('HALF_AM', 'HALF_PM')) = (days = 0.5)) AND ((status IN ('APPROVED', 'REJECTED')) = (decided_at IS NOT NULL AND approver_code IS NOT NULL))",
        "종류·상태·일수·처리",
    ),
    c(
        LR,
        "SERVICE/DB_POLICY",
        ["approver_code"],
        "승인자 = 신청자 부서의 부서장 직책(is_head) 사원(부서장 본인은 상위 부서장). 연차 잔여 = 발생 − 승인 ANNUAL·HALF 합(조회), 초과 신청 거부",
        "휴가 승인(Q3)",
    ),
    c(PI, "UK", S + ["code"], reason="항목 코드 유일"),
    c(
        PI,
        "CHECK",
        ["code", "item_kind", "calc_kind", "rate"],
        f"code {CODE} AND item_kind IN ('EARNING', 'DEDUCTION') AND calc_kind IN ('BASE', 'FIXED', 'OVERTIME', 'NIGHT', 'HOLIDAY', 'BONUS', 'RATE') AND ((calc_kind IN ('OVERTIME', 'NIGHT', 'HOLIDAY', 'RATE')) = (rate IS NOT NULL)) AND ((item_kind = 'DEDUCTION') = (calc_kind = 'RATE'))",
        "구분·계산 방식·비율",
    ),
    c(PB, "UK", S + ["employee_id", "effective_from"], reason="사원·시작 월 1건"),
    c(
        PB,
        "CHECK",
        ["effective_from", "base_salary", "ordinary_hours"],
        f"effective_from {MONTH} AND base_salary >= 0 AND ordinary_hours > 0",
        "형식·금액",
    ),
    c(PBI, "UK", S + ["pay_base_id", "pay_item_id"], reason="기준·항목 1행"),
    c(PBI, "CHECK", ["amount"], "amount >= 0", "금액"),
    c(
        BR,
        "CHECK",
        ["payable_mm", "rate_percent"],
        "payable_mm ~ '^(0[1-9]|1[0-2])$' AND rate_percent > 0",
        "지급 월·지급률",
    ),
    uk_partial(BR, ["payable_mm"], "is_active", "지급 월당 활성 규칙 1건"),
    c(PR, "UK", S + ["pay_month", "version"], reason="월·버전 유일"),
    c(PR, "CHECK", ["pay_month"], f"pay_month {MONTH}", "'YYYY-MM' 형식"),
    uk_partial(PR, ["pay_month"], "status = 'confirmed'", "월당 확정 급여 1건"),
    c(
        PR,
        "SERVICE/DB_POLICY",
        ["status"],
        "계산 = 기본급 + 고정 수당 + 근태 수당(통상시급 = (기본급 + 고정 수당) ÷ 통상 근로시간, × 분/60 × rate) + 상여(지급 월이면 기본급 × 지급률) − 공제(과세 지급 합계 × rate%, 합성 고정 비율). 근태 마감은 같은 월 확정본만. 확정 후 명세 불변, 재계산은 새 버전 → 이전 superseded",
        "급여 계산·확정(Q4·Q5)",
    ),
    c(
        PR,
        "SERVICE/DB_POLICY",
        ["pay_month"],
        "fs.hr.interface.payroll_runs(month) = 확정 실행의 부서 코드·항목별 합계(개인별 금액 없음) → ERP F94 급여 전표. 퇴직금 추계 = 최근 3개월 평균 임금 × 30일 × 근속 연수(조회 계산, 저장 안 함)",
        "ERP 제공·퇴직금 추계(Q5)",
    ),
    c(PS, "UK", S + ["run_id", "employee_id"], reason="실행·사원 1건"),
    c(
        PS,
        "CHECK",
        ["gross_pay", "deduction_total", "net_pay"],
        "gross_pay >= 0 AND deduction_total >= 0 AND net_pay = gross_pay - deduction_total",
        "합계",
    ),
    c(
        PS,
        "SERVICE/DB_POLICY",
        ["employee_id"],
        "급여 화면은 HR 관리자만. 본인 조회(Q7)는 EIP 사람 연결(fs.eip.interface.my_employee_code)의 사원 코드와 같은 명세서·잔여 연차·근태만",
        "급여 열람 범위(Q7)",
    ),
    c(PSL, "UK", S + ["payslip_id", "pay_item_id"], reason="명세서·항목 1행"),
    c(PSL, "CHECK", ["amount"], "amount >= 0", "금액"),
    c(RC, "UK", S + ["cycle_year"], reason="연도당 평가 기간 1건"),
    c(
        RC,
        "CHECK",
        ["cycle_year", "status"],
        f"cycle_year {YEAR} AND status IN ('OPEN', 'CLOSED')",
        "연도·상태",
    ),
    c(RV, "UK", S + ["cycle_id", "employee_id"], reason="기간·사원 1건"),
    c(
        RV,
        "CHECK",
        ["grade", "status", "confirmed_at"],
        "(grade IS NULL OR grade IN ('S', 'A', 'B', 'C', 'D')) AND status IN ('draft', 'submitted', 'confirmed') AND ((status = 'confirmed') = (confirmed_at IS NOT NULL AND grade IS NOT NULL))",
        "등급·상태",
    ),
    c(
        RV,
        "SERVICE/DB_POLICY",
        ["reviewer_code"],
        "평가자 기본값 = 부서장. 본인은 목표·자기 평가만, 등급·의견은 평가자. 확정 후 불변, 기간 CLOSED면 입력 불가",
        "인사 평가(Q6)",
    ),
]
for t, cols_ in [
    (DP, ["parent_id"]),
    (EM, ["department_id"]),
    (AP, ["employee_id"]),
    (QL, ["employee_id"]),
    (QL, ["expires_on"]),
    (LR, ["employee_id"]),
    (PBI, ["pay_item_id"]),
    (PR, ["attendance_close_id"]),
    (PS, ["employee_id"]),
    (PSL, ["pay_item_id"]),
    (RV, ["employee_id"]),
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
    r(DP, ["parent_id"], DP, "상위 부서"),
    r(EM, ["department_id"], DP, "현재 부서"),
    r(EM, ["grade_id"], TT, "현재 직위"),
    r(EM, ["duty_id"], TT, "현재 직책"),
    r(EM, ["work_pattern_id"], WP, "근무 형태"),
    r(AP, ["employee_id"], EM, "사원"),
    r(AP, ["department_id"], DP, "부서"),
    r(AP, ["grade_id"], TT, "직위"),
    r(AP, ["duty_id"], TT, "직책"),
    r(QL, ["employee_id"], EM, "사원"),
    r(AT, ["employee_id"], EM, "사원"),
    r(LB, ["employee_id"], EM, "사원"),
    r(LR, ["employee_id"], EM, "사원"),
    r(PB, ["employee_id"], EM, "사원"),
    r(PBI, ["pay_base_id"], PB, "급여 기준"),
    r(PBI, ["pay_item_id"], PI, "급여 항목"),
    r(BR, ["pay_item_id"], PI, "상여 항목"),
    r(PR, ["attendance_close_id"], AC, "근태 마감"),
    r(PS, ["run_id"], PR, "급여 실행"),
    r(PS, ["employee_id"], EM, "사원"),
    r(PSL, ["payslip_id"], PS, "급여명세서"),
    r(PSL, ["pay_item_id"], PI, "급여 항목"),
    r(RV, ["cycle_id"], RC, "평가 기간"),
    r(RV, ["employee_id"], EM, "사원"),
]
STATES = [
    dict(
        table=AC,
        column="status",
        values=list(VER),
        default="draft",
        transition="draft→confirmed→superseded",
    ),
    dict(
        table=PR,
        column="status",
        values=list(VER),
        default="draft",
        transition="draft→confirmed→superseded",
    ),
    dict(
        table=AP,
        column="status",
        values=["draft", "confirmed"],
        default="draft",
        transition="draft→confirmed",
    ),
    dict(
        table=LR,
        column="status",
        values=["REQUESTED", "APPROVED", "REJECTED", "CANCELLED"],
        default="REQUESTED",
        transition="REQUESTED→APPROVED|REJECTED|CANCELLED; APPROVED→CANCELLED(근태 마감 전)",
    ),
    dict(
        table=RV,
        column="status",
        values=["draft", "submitted", "confirmed"],
        default="draft",
        transition="draft→submitted→confirmed",
    ),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn30은 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "rws.request" not in names:
        raise SystemExit("apply_dsn29를 먼저 적용한다")
    if EM in names:
        return False
    modules = [
        x
        for x in d["constraints"]
        if x["table"] in MODULE_TABLES
        and x["kind"] == "CHECK"
        and "module_key IN" in x["expression"]
    ]
    if len(modules) != 2:
        raise SystemExit(f"대상이 없다: 모듈 키 CHECK {len(modules)}개")
    for x in modules:
        x["expression"] = x["expression"].rstrip(")") + ", 'hr')"
    for code in d["code_lists"]:
        if (
            code["target"] in MODULE_TABLES
            and code["column"] == "module_key"
            and "hr" not in code["values"]
        ):
            code["values"] = [*code["values"], "hr"]
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    d.update(version="target-0.18.0", task="DSN-30", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.18.0",
            task="DSN-30",
            date="2026-10-05",
            change="HR 신규: hr 19테이블(부서·직위/직책·근무 형태·사원·발령·자격/교육·일 근태·월 근태 마감·연차 발생·휴가 신청·급여 항목·급여 기준·고정 수당·상여 규칙·급여 실행·급여명세서·명세 항목·평가 기간·인사 평가), 모듈 키 hr. 민감 정보 칸 없음. 업무 스키마 간 FK 0",
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
    hr = [t for t in d["tables"] if t["name"].startswith(P)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                hr_tables=len(hr),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
