"""DSN-21: CMMS 재점검·보강 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn17 다음).

근거: docs/modules/cmms/CMMS_보강설계_DSN-21.md 4장(새 테이블 6·기존 테이블 변경 6), 결정 Q1~Q7.
Q4(FEMS 에너지 경보·BEMS 설비 경보 신호 전환)는 제외 — 작업지시 출처는 FS-029 그대로.
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z][A-Z0-9-]{1,19}$'"
M = "cmms."


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-21"}


ASSET_TYPES = (
    "INJECTION",
    "ASSEMBLY",
    "INSPECTION",
    "HVAC",
    "UTILITY",
    "OTHER",
    "MOLD",
    "LINE",
    "COMPONENT",
    "FACILITY",
)
SOURCES = ("MES", "BEMS", "CMMS", "MES_MOLD")
TRIGGERS = ("CALENDAR", "RUN_HOURS", "SHOTS")

CI, CRS, TE, VE, FC, AP = (
    M + "checklist_item",
    M + "checklist_result",
    M + "technician",
    M + "vendor",
    M + "failure_code",
    M + "asset_part",
)

TABLES = [
    table(
        CI,
        "점검 항목",
        "pm",
        "DSN-21 F13·F14(Q3). PM 계획의 점검표. 시설 일상 점검은 일 주기 계획의 점검표",
        [
            col("pm_plan_id", "예방보전 계획", "bigint"),
            col("seq", "순서", "integer"),
            col("name", "항목", "varchar(100)"),
            col("method", "판정 방식", "varchar(8)", rule="OK_NG / RANGE"),
            col("standard_text", "기준", "varchar(200)", nullable=True),
            col("lower_limit", "하한", "numeric(15,4)", nullable=True),
            col("upper_limit", "상한", "numeric(15,4)", nullable=True),
            col("unit", "단위", "varchar(10)", nullable=True),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        CRS,
        "점검 결과",
        "pm",
        "DSN-21 F13. PM 작업지시 완료 전 항목별 결과. NG가 있으면 고장 작업지시 제안",
        [
            col("work_order_id", "작업지시", "bigint"),
            col("checklist_item_id", "점검 항목", "bigint"),
            col("result", "결과", "varchar(2)", rule="OK / NG"),
            col("measured_value", "측정값", "numeric(15,4)", nullable=True),
            col("note", "메모", "varchar(300)", nullable=True),
            col("checked_at", "점검 시각", "timestamptz"),
        ],
    ),
    table(
        TE,
        "정비원",
        "people",
        "DSN-21 F25(Q5). 인사 정보는 HR(D79), 사원 코드는 스냅샷. 시간당 인건비는 비용 집계용 합성 값",
        [
            col("code", "정비원 코드", "varchar(20)"),
            col("name", "이름", "varchar(100)"),
            col(
                "skill",
                "기술 분야",
                "varchar(12)",
                rule="MECHANICAL / ELECTRICAL / UTILITY / GENERAL",
            ),
            col("hourly_rate", "시간당 인건비", "numeric(12,2)"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col("hr_employee_code", "HR 사원 코드", "varchar(30)", nullable=True),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        VE,
        "외주 업체",
        "people",
        "DSN-21 F26(Q5). ERP 거래처 코드 스냅샷. 비용 회계는 ERP 직접 매입",
        [
            col("code", "업체 코드", "varchar(20)"),
            col("name", "업체명", "varchar(200)"),
            col("erp_partner_code", "ERP 거래처 코드", "varchar(40)", nullable=True),
            col("phone", "연락처", "varchar(30)", nullable=True),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        FC,
        "고장 코드",
        "failure",
        "DSN-21 F24. 증상·조치 코드(원인은 기존 6분류 + 상세 코드)",
        [
            col(
                "kind",
                "구분",
                "varchar(8)",
                rule="SYMPTOM 증상 / CAUSE 원인 / ACTION 조치",
            ),
            col("code", "코드", "varchar(20)"),
            col("name", "이름", "varchar(100)"),
            col(
                "cause_category",
                "원인 분류",
                "varchar(12)",
                nullable=True,
                rule="CAUSE면 FS-029 6분류 중 하나",
            ),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        AP,
        "설비별 예비품",
        "parts",
        "DSN-21 F34. 적용 설비·표준 수량. 작업지시 부품 선택에서 먼저 보여 준다",
        [
            col("asset_id", "설비", "bigint"),
            col("spare_part_id", "예비품", "bigint"),
            col("qty_per", "표준 수량", "numeric(12,3)"),
        ],
    ),
]

NEW_COLUMNS = {
    M + "asset": [
        col(
            "parent_asset_id",
            "상위 설비",
            "bigint",
            nullable=True,
            rule="F04 라인 > 설비 > 구성품",
        ),
        col("manufacturer", "제조사", "varchar(100)", nullable=True),
        col("model", "모델", "varchar(100)", nullable=True),
        col("serial_no", "일련번호", "varchar(60)", nullable=True),
        col("installed_on", "설치일", "date", nullable=True),
        col("acquisition_cost", "취득가", "numeric(18,2)", nullable=True),
        col("criticality", "중요도", "varchar(1)", nullable=True, rule="A / B / C"),
    ],
    M + "pm_plan": [
        col(
            "trigger_kind",
            "기준",
            "varchar(10)",
            default="'CALENDAR'",
            rule=" / ".join(TRIGGERS) + "(Q2)",
        ),
        col(
            "interval_usage",
            "사용량 주기",
            "numeric(14,2)",
            nullable=True,
            rule="RUN_HOURS: 시간, SHOTS: 타수",
        ),
        col(
            "last_done_usage",
            "마지막 수행 시 사용량",
            "numeric(14,2)",
            nullable=True,
            rule="PM 완료로만 바뀐다",
        ),
    ],
    M + "work_order": [
        col("technician_id", "담당 정비원", "bigint", nullable=True, rule="Q5"),
        col("vendor_id", "외주 업체", "bigint", nullable=True, rule="Q5 외주 수리"),
        col("external_cost", "외주 비용", "numeric(18,2)", nullable=True),
        col("symptom_code_id", "증상 코드", "bigint", nullable=True),
        col("action_code_id", "조치 코드", "bigint", nullable=True),
        col(
            "usage_at_due",
            "생성 시 사용량",
            "numeric(14,2)",
            nullable=True,
            rule="사용량 기준 PM 스냅샷",
        ),
    ],
    M + "work_log": [
        col("technician_id", "정비원", "bigint", nullable=True, rule="Q5 정비원별 시간")
    ],
    M + "spare_part": [
        col(
            "item_code",
            "WMS 품목 코드",
            "varchar(40)",
            nullable=True,
            rule="Q6 WMS SUPPLY 품목 스냅샷(재고 조회 키)",
        ),
        col(
            "unit_cost", "표준 단가", "numeric(18,4)", nullable=True, rule="비용 집계용"
        ),
    ],
    M + "part_usage": [
        col(
            "unit_cost",
            "사용 단가",
            "numeric(18,4)",
            nullable=True,
            rule="사용 시점 표준 단가 스냅샷",
        )
    ],
}
NULLABLE = {(M + "pm_plan", "interval_days")}

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in (TE, VE):
    CONSTRAINTS += [
        c(t, "UK", S + ["code"], reason="세대 내 코드 유일"),
        c(t, "CHECK", ["code"], f"code {CODE}", "코드 형식"),
    ]
CONSTRAINTS += [
    c(CI, "UK", S + ["pm_plan_id", "seq"], reason="계획·순서 유일"),
    c(
        CI,
        "CHECK",
        ["method", "lower_limit", "upper_limit", "unit"],
        "method IN ('OK_NG', 'RANGE') AND (method = 'OK_NG' OR (COALESCE(lower_limit, upper_limit) IS NOT NULL AND unit IS NOT NULL)) AND (lower_limit IS NULL OR upper_limit IS NULL OR lower_limit <= upper_limit)",
        "판정 방식별 기준",
    ),
    c(
        CRS,
        "UK",
        S + ["work_order_id", "checklist_item_id"],
        reason="작업지시·항목당 결과 1건",
    ),
    c(
        CRS,
        "CHECK",
        ["result", "note"],
        "result IN ('OK', 'NG') AND (result = 'OK' OR length(btrim(note)) >= 2)",
        "결과·NG 메모",
    ),
    c(
        CRS,
        "SERVICE/DB_POLICY",
        ["result"],
        "PM 작업지시는 계획의 사용 항목 결과를 모두 기록해야 완료. RANGE는 값으로 판정(서버). NG가 있으면 같은 설비 고장(BM) 작업지시 생성을 제안. 완료 후 불변",
        "점검표 완료 조건(Q3)",
    ),
    c(
        TE,
        "CHECK",
        ["skill", "hourly_rate", "currency"],
        "skill IN ('MECHANICAL', 'ELECTRICAL', 'UTILITY', 'GENERAL') AND hourly_rate >= 0 AND currency = 'KRW'",
        "분야·단가·통화",
    ),
    c(FC, "UK", S + ["kind", "code"], reason="구분·코드 유일"),
    c(
        FC,
        "CHECK",
        ["kind", "code", "cause_category"],
        f"kind IN ('SYMPTOM', 'CAUSE', 'ACTION') AND code {CODE} AND ((kind = 'CAUSE') = (cause_category IS NOT NULL)) AND (cause_category IS NULL OR cause_category IN ('WEAR', 'LUBRICATION', 'ELECTRICAL', 'SETTING', 'EXTERNAL', 'OTHER'))",
        "구분·코드·원인 분류",
    ),
    c(AP, "UK", S + ["asset_id", "spare_part_id"], reason="설비·예비품 1행"),
    c(AP, "CHECK", ["qty_per"], "qty_per > 0", "표준 수량 양수"),
]
for t, cols_ in [
    (CI, ["pm_plan_id"]),
    (CRS, ["work_order_id"]),
    (AP, ["spare_part_id"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="FK·목록 조회"))

CHANGED_CONSTRAINTS = [
    c(
        M + "asset",
        "CHECK",
        ["criticality", "acquisition_cost", "parent_asset_id"],
        "(criticality IS NULL OR criticality IN ('A', 'B', 'C')) AND (acquisition_cost IS NULL OR acquisition_cost >= 0) AND (parent_asset_id IS NULL OR parent_asset_id <> id)",
        "중요도·취득가·자기 참조",
    ),
    c(
        M + "asset",
        "CHECK",
        ["source", "asset_type"],
        "(source = 'MES_MOLD') = (asset_type = 'MOLD')",
        "금형은 MES 금형 출처(Q1)",
    ),
    c(
        M + "pm_plan",
        "CHECK",
        ["trigger_kind", "interval_days", "interval_usage"],
        f"trigger_kind IN ({q(TRIGGERS)}) AND ((trigger_kind = 'CALENDAR') = (interval_days IS NOT NULL)) AND ((trigger_kind = 'CALENDAR') = (interval_usage IS NULL)) AND (interval_usage IS NULL OR interval_usage > 0)",
        "기준별 주기(Q2)",
    ),
    c(
        M + "pm_plan",
        "SERVICE/DB_POLICY",
        ["interval_usage"],
        "RUN_HOURS: MES 공정 실행 시간 합(fs.mes.interface.operation_runs, 설비 코드), SHOTS: MES 금형 누적 타수(molds). 도래 = 현재 사용량 − 마지막 수행 사용량 ≥ 주기 → 사람이 작업지시 생성(D49와 같음, 자동 생성 없음). MES 꺼짐이면 도래 판정 불가 표시",
        "사용량 기준 PM(Q2)",
    ),
    c(
        M + "work_order",
        "CHECK",
        ["external_cost", "vendor_id"],
        "(external_cost IS NULL OR external_cost >= 0) AND (external_cost IS NULL OR vendor_id IS NOT NULL)",
        "외주 비용은 업체 필수",
    ),
    c(
        M + "work_order",
        "SERVICE/DB_POLICY",
        ["technician_id", "external_cost"],
        "보전 비용 = 부품(Σ사용 수량 × 사용 단가) + 인건비(Σ작업 기록 분 ÷ 60 × 정비원 시간당 인건비) + 외주 비용. 조회 계산(저장 안 함). 외주 수리의 회계 처리는 ERP 직접 매입",
        "보전 비용(Q5)",
    ),
    c(
        M + "spare_part",
        "CHECK",
        ["unit_cost"],
        "unit_cost IS NULL OR unit_cost >= 0",
        "단가 음수 금지",
    ),
    c(
        M + "spare_part",
        "SERVICE/DB_POLICY",
        ["item_code"],
        "재고 = fs.wms.interface.stock_on_hand(item_code)(CMMS 재고 원장 없음, D50 유지). 재고 < 안전 재고 → 부족, fs.cmms.interface.part_requests()로 ERP 구매 요청 원천(출처 CMMS). 부품 사용은 fs.cmms.interface.part_usages()로 WMS가 읽어 출고",
        "예비품 재고·구매 연계(Q6)",
    ),
]
REPLACED = {
    (
        M + "asset",
        "asset_type IN ('INJECTION', 'ASSEMBLY', 'INSPECTION', 'HVAC', 'UTILITY', 'OTHER')",
    ): f"asset_type IN ({q(ASSET_TYPES)})",
    (M + "asset", "source IN ('MES', 'BEMS', 'CMMS')"): f"source IN ({q(SOURCES)})",
    (
        M + "pm_plan",
        "interval_days BETWEEN 1 AND 365",
    ): "interval_days IS NULL OR interval_days BETWEEN 1 AND 365",
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
    r(CI, ["pm_plan_id"], M + "pm_plan", "예방보전 계획"),
    r(CRS, ["work_order_id"], M + "work_order", "작업지시"),
    r(CRS, ["checklist_item_id"], CI, "점검 항목"),
    r(AP, ["asset_id"], M + "asset", "설비"),
    r(AP, ["spare_part_id"], M + "spare_part", "예비품"),
    r(M + "asset", ["parent_asset_id"], M + "asset", "상위 설비"),
    r(M + "work_order", ["technician_id"], TE, "담당 정비원"),
    r(M + "work_order", ["vendor_id"], VE, "외주 업체"),
    r(M + "work_order", ["symptom_code_id"], FC, "증상 코드"),
    r(M + "work_order", ["action_code_id"], FC, "조치 코드"),
    r(M + "work_log", ["technician_id"], TE, "정비원"),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn21은 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "spc.spec_violation" not in names:
        raise SystemExit("apply_dsn17을 먼저 적용한다")
    if TE in names:
        return False
    hits = {(x["table"], x["expression"]) for x in d["constraints"]} & set(REPLACED)
    if len(hits) != len(REPLACED):
        raise SystemExit(f"바꿀 기존 제약을 찾지 못했다: {set(REPLACED) - hits}")
    tables = {t["name"]: t for t in d["tables"]}
    for name, columns in NEW_COLUMNS.items():
        cols = tables[name]["columns"]
        at = len(cols) - 1 if cols[-1]["name"] == "created_at" else len(cols)
        cols[at:at] = columns
    for name, column in NULLABLE:
        for x in tables[name]["columns"]:
            if x["name"] == column:
                x.update(nullable=True, rule="DSN-21: CALENDAR 기준일 때만")
    for x in d["constraints"]:
        new = REPLACED.get((x["table"], x["expression"]))
        if new:
            x["expression"] = new
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS + CHANGED_CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    for code in d["code_lists"]:
        if code["target"] == M + "asset" and code["column"] == "asset_type":
            code["values"] = list(ASSET_TYPES)
        if code["target"] == M + "asset" and code["column"] == "source":
            code["values"] = list(SOURCES)
    d["code_lists"].append(
        dict(
            target=M + "pm_plan",
            column="trigger_kind",
            values=list(TRIGGERS),
            default="CALENDAR",
            note="일 주기 / 운전 시간 / 금형 타수",
        )
    )
    d.update(version="target-0.9.0", task="DSN-21", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.9.0",
            task="DSN-21",
            date="2026-10-05",
            change="CMMS 보강: 새 테이블 6(점검 항목·결과·정비원·외주 업체·고장 코드·설비별 예비품), 기존 6테이블 변경(설비 상세·계층·금형 출처, PM 사용량 기준, 작업지시 정비원·외주·코드, 작업 기록 정비원, 예비품 WMS 품목·단가, 부품 사용 단가)",
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
    cmms = [t for t in d["tables"] if t["name"].startswith(M)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                cmms_tables=len(cmms),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
