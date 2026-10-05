"""DSN-26: SCM(신규) 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn25 다음).

근거: docs/modules/scm/SCM_설계_DSN-26.md 4장(scm 9테이블 + 모듈 키 'scm'), 결정 Q1~Q7.
Q1: SCM은 계획·분석만 — 판매계획·생산계획·발주·재고 값은 ERP·MES·WMS가 가져가 반영. 결품 위험·정확도는 조회 계산.
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
MONTH = "~ '^[0-9]{4}-(0[1-9]|1[0-2])$'"
P = "scm."
MODULE_TABLES = {"core.workspace_module", "core.app_review"}
VER = ("draft", "confirmed", "superseded")
METHODS = ("MA", "SES", "SEASONAL")


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-26"}


PI, SI, DH, FR, FL, SP, SL, IP, SS = (
    P + "plan_item",
    P + "supplier_item",
    P + "demand_history",
    P + "forecast_run",
    P + "forecast_line",
    P + "sop_plan",
    P + "sop_line",
    P + "inventory_policy",
    P + "supplier_score",
)

TABLES = [
    table(
        PI,
        "계획 품목",
        "master",
        "DSN-26 F01·F02. 계획 대상·예측 방법·서비스 수준·조달 리드타임·최소 주문량(품목 코드는 ERP·MES 스냅샷)",
        [
            col("item_code", "품목 코드", "varchar(40)"),
            col("item_name", "품목명", "varchar(200)"),
            col("unit", "단위", "varchar(10)"),
            col("is_planned", "계획 대상", "boolean", default="true"),
            col(
                "method_pref",
                "예측 방법",
                "varchar(10)",
                default="'AUTO'",
                rule="AUTO(오차 최소 추천) / " + " / ".join(METHODS),
            ),
            col(
                "service_level",
                "서비스 수준",
                "numeric(4,3)",
                default="0.95",
                rule="0.80~0.995",
            ),
            col("lead_time_days", "조달·생산 리드타임(일)", "integer"),
            col("moq", "최소 주문량", "numeric(18,3)", nullable=True),
            col("order_multiple", "주문 단위", "numeric(18,3)", nullable=True),
        ],
    ),
    table(
        SI,
        "공급처 품목",
        "master",
        "DSN-26 F03. 우선 공급처·할당 비율·계약 리드타임, 적용일 이력(ERP 거래처 코드 스냅샷)",
        [
            col("item_code", "품목 코드", "varchar(40)"),
            col("partner_code", "공급처 코드", "varchar(40)"),
            col("priority", "우선순위", "integer", default="1"),
            col("share_pct", "할당 비율(%)", "numeric(5,2)"),
            col("contract_lead_time_days", "계약 리드타임(일)", "integer"),
            col("valid_from", "적용일", "date"),
        ],
    ),
    table(
        DH,
        "수요 이력",
        "demand",
        "DSN-26 F11. ERP 출하 실적 월 집계 스냅샷(다시 가져오면 갱신 — 확정 데이터가 아님)",
        [
            col("item_code", "품목 코드", "varchar(40)"),
            col("history_month", "실적 월", "varchar(7)", rule="'YYYY-MM'"),
            col("qty", "출하 수량", "numeric(18,3)"),
            col("captured_at", "가져온 시각", "timestamptz"),
        ],
    ),
    table(
        FR,
        "수요 예측",
        "demand",
        "DSN-26 F12~F14(Q2·Q3). 기준 월 예측 버전. 확정 후 불변, 기준 월당 확정 1건. ERP가 가져가 판매계획 초안",
        [
            col("run_no", "예측 번호", "varchar(40)"),
            col(
                "base_month",
                "기준 월",
                "varchar(7)",
                rule="'YYYY-MM' — 이 달까지 실적으로 다음 달부터 예측",
            ),
            col("horizon_months", "예측 기간(개월)", "integer", default="12"),
            col("version", "버전", "integer"),
            col(
                "status", "상태", "varchar(12)", default="'draft'", rule=" / ".join(VER)
            ),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        FL,
        "예측 명세",
        "demand",
        "DSN-26 F12·F13·F15. 품목·월별 통계 예측(방법별 오차로 추천)과 조정값",
        [
            col("forecast_run_id", "수요 예측", "bigint"),
            col("item_code", "품목 코드", "varchar(40)"),
            col("target_month", "예측 월", "varchar(7)", rule="'YYYY-MM'"),
            col("method", "적용 방법", "varchar(10)", rule=" / ".join(METHODS)),
            col("stat_qty", "통계 예측", "numeric(18,3)"),
            col("adjusted_qty", "조정 예측", "numeric(18,3)"),
            col("adjust_reason", "조정 사유", "varchar(300)", nullable=True),
            col(
                "method_mape",
                "적용 방법 MAPE",
                "numeric(7,4)",
                nullable=True,
                rule="예측 시점 과거 오차 스냅샷",
            ),
        ],
    ),
    table(
        SP,
        "S&OP 계획",
        "sop",
        "DSN-26 F21~F23(Q4). 월 수급 균형 버전. 기준 월당 확정 1건",
        [
            col("sop_month", "기준 월", "varchar(7)", rule="'YYYY-MM'"),
            col("forecast_run_id", "근거 예측", "bigint"),
            col("version", "버전", "integer"),
            col(
                "status", "상태", "varchar(12)", default="'draft'", rule=" / ".join(VER)
            ),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
            col("note", "회의 결론", "varchar(1000)", nullable=True),
        ],
    ),
    table(
        SL,
        "S&OP 명세",
        "sop",
        "DSN-26 F21·F22. 품목·월: 수요 · 생산 능력(MES 스냅샷) · 계획 생산 · 재고 목표 일수 · 예상 재고",
        [
            col("sop_plan_id", "S&OP 계획", "bigint"),
            col("item_code", "품목 코드", "varchar(40)"),
            col("target_month", "계획 월", "varchar(7)", rule="'YYYY-MM'"),
            col("demand_qty", "수요", "numeric(18,3)"),
            col(
                "capacity_qty",
                "생산 능력",
                "numeric(18,3)",
                rule="MES 설비 × 근무 시간 ÷ 표준 사이클(스냅샷)",
            ),
            col("production_qty", "계획 생산", "numeric(18,3)"),
            col("target_days", "재고 목표 일수", "numeric(6,1)"),
            col("projected_inventory", "예상 기말 재고", "numeric(18,3)"),
        ],
    ),
    table(
        IP,
        "재고 정책",
        "policy",
        "DSN-26 F31·F32(Q5). 안전재고·재주문점 산정 스냅샷. 품목당 제안 1건(새 산정 시 이전 superseded). WMS가 가져가 반영",
        [
            col("item_code", "품목 코드", "varchar(40)"),
            col("calc_month", "산정 월", "varchar(7)", rule="'YYYY-MM'"),
            col("avg_monthly_demand", "월평균 수요", "numeric(18,3)"),
            col("demand_std", "수요 표준편차", "numeric(18,3)"),
            col("lead_time_days", "리드타임(일)", "integer"),
            col("service_level", "서비스 수준", "numeric(4,3)"),
            col("z_value", "z", "numeric(5,3)"),
            col("safety_stock", "안전재고", "numeric(18,3)"),
            col("reorder_point", "재주문점", "numeric(18,3)"),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'proposed'",
                rule="proposed / superseded",
            ),
        ],
    ),
    table(
        SS,
        "공급처 성과",
        "supplier",
        "DSN-26 F33(Q6). 월 납기 준수·리드타임 실적(ERP 발주 vs WMS 입고) + QMS 품질 등급 → 종합 점수",
        [
            col("score_month", "평가 월", "varchar(7)", rule="'YYYY-MM'"),
            col("partner_code", "공급처 코드", "varchar(40)"),
            col("po_line_count", "발주 행 수", "integer"),
            col("on_time_rate", "납기 준수율", "numeric(5,4)"),
            col("avg_lead_time_days", "평균 리드타임(일)", "numeric(6,1)"),
            col(
                "quality_grade",
                "QMS 품질 등급",
                "varchar(1)",
                nullable=True,
                rule="QMS 조회 스냅샷",
            ),
            col("score", "종합 점수", "numeric(5,1)", rule="0~100"),
            col("grade", "종합 등급", "varchar(1)", rule="A / B / C / D"),
        ],
    ),
]

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t, period in [
    (DH, "history_month"),
    (FR, "base_month"),
    (FL, "target_month"),
    (SP, "sop_month"),
    (SL, "target_month"),
    (IP, "calc_month"),
    (SS, "score_month"),
]:
    CONSTRAINTS.append(c(t, "CHECK", [period], f"{period} {MONTH}", "'YYYY-MM' 형식"))
for t, period in [(FR, "base_month"), (SP, "sop_month")]:
    CONSTRAINTS += [
        c(t, "UK", S + [period, "version"], reason="기준 월·버전 유일"),
        c(
            t,
            "CHECK",
            ["status", "version", "confirmed_at"],
            "status IN ('draft', 'confirmed', 'superseded') AND version >= 1 AND ((status = 'draft') = (confirmed_at IS NULL))",
            "상태·버전",
        ),
        uk_partial(t, [period], "status = 'confirmed'", "기준 월당 확정 1건"),
    ]
CONSTRAINTS += [
    c(PI, "UK", S + ["item_code"], reason="품목 1건"),
    c(
        PI,
        "CHECK",
        ["method_pref", "service_level", "lead_time_days", "moq", "order_multiple"],
        f"method_pref IN ('AUTO', {q(METHODS)}) AND service_level BETWEEN 0.8 AND 0.995 AND lead_time_days BETWEEN 0 AND 365 AND (moq IS NULL OR moq > 0) AND (order_multiple IS NULL OR order_multiple > 0)",
        "방법·서비스 수준·리드타임·주문 단위",
    ),
    c(
        SI,
        "UK",
        S + ["item_code", "partner_code", "valid_from"],
        reason="품목·공급처·적용일 1건",
    ),
    c(
        SI,
        "CHECK",
        ["priority", "share_pct", "contract_lead_time_days"],
        "priority >= 1 AND share_pct > 0 AND share_pct <= 100 AND contract_lead_time_days BETWEEN 0 AND 365",
        "우선순위·비율·리드타임",
    ),
    c(
        SI,
        "SERVICE/DB_POLICY",
        ["share_pct"],
        "같은 품목·적용일의 할당 비율 합 = 100(저장 시 검사)",
        "할당 비율 합",
    ),
    c(DH, "UK", S + ["item_code", "history_month"], reason="품목·월 1건"),
    c(DH, "CHECK", ["qty"], "qty >= 0", "수량 음수 금지"),
    c(
        DH,
        "SERVICE/DB_POLICY",
        ["qty"],
        "fs.erp.interface 출하 실적(확정 출하, 반품 차감)을 월로 집계해 덮어쓴다 — 실행 데이터의 파생 스냅샷이라 갱신 허용. 예측 확정 때 쓴 값은 예측 명세 오차 스냅샷으로 남는다",
        "수요 이력 갱신",
    ),
    c(FR, "UK", S + ["run_no"], reason="예측 번호 유일"),
    c(FR, "CHECK", ["horizon_months"], "horizon_months BETWEEN 1 AND 24", "예측 기간"),
    c(
        FR,
        "SERVICE/DB_POLICY",
        ["status"],
        '확정 후 불변. 확정분을 fs.scm.interface.demand_forecast(month)로 ERP가 "SCM에서 가져오기" → 판매계획 초안(Q3). CRM pipeline_summary는 조정 화면 참고만(합산 안 함)',
        "예측 확정 → ERP(Q3)",
    ),
    c(
        FL,
        "UK",
        S + ["forecast_run_id", "item_code", "target_month"],
        reason="예측·품목·월 1행",
    ),
    c(
        FL,
        "CHECK",
        ["method", "stat_qty", "adjusted_qty", "method_mape"],
        f"method IN ({q(METHODS)}) AND stat_qty >= 0 AND adjusted_qty >= 0 AND (method_mape IS NULL OR method_mape >= 0)",
        "방법·값",
    ),
    c(
        FL,
        "CHECK",
        ["stat_qty", "adjusted_qty", "adjust_reason"],
        "adjusted_qty = stat_qty OR length(btrim(adjust_reason)) >= 2",
        "조정하면 사유 필수",
    ),
    c(
        FL,
        "SERVICE/DB_POLICY",
        ["method"],
        "이동평균(3개월)·단순 지수평활(α 0.3)·계절 지수(12개월 이상 이력)를 모두 계산해 최근 6개월 MAPE가 가장 작은 방법 추천(AUTO), 사람이 변경 가능. 정확도(MAPE·편향)는 확정 예측 vs 이후 실적으로 조회 계산",
        "예측 방법(Q2)",
    ),
    c(
        SL,
        "UK",
        S + ["sop_plan_id", "item_code", "target_month"],
        reason="계획·품목·월 1행",
    ),
    c(
        SL,
        "CHECK",
        ["demand_qty", "capacity_qty", "production_qty", "target_days"],
        "demand_qty >= 0 AND capacity_qty >= 0 AND production_qty >= 0 AND target_days >= 0",
        "값 음수 금지",
    ),
    c(
        SP,
        "SERVICE/DB_POLICY",
        ["status"],
        "능력 = MES 설비·표준 사이클·근무조 시간(fs.mes.interface, 휴일은 core 달력) 월 가능량 스냅샷. 계획 생산 > 능력이면 부족, 예상 재고 > 목표 × 1.5면 과잉 경고. MES는 확정 S&OP를 생산계획 참고로 읽는다",
        "S&OP 능력·경고(Q4)",
    ),
    c(
        IP,
        "CHECK",
        [
            "service_level",
            "z_value",
            "safety_stock",
            "reorder_point",
            "status",
            "demand_std",
            "avg_monthly_demand",
        ],
        "service_level BETWEEN 0.8 AND 0.995 AND z_value > 0 AND safety_stock >= 0 AND reorder_point >= safety_stock AND demand_std >= 0 AND avg_monthly_demand >= 0 AND status IN ('proposed', 'superseded')",
        "산정 값",
    ),
    uk_partial(IP, ["item_code"], "status = 'proposed'", "품목당 제안 1건"),
    c(
        IP,
        "SERVICE/DB_POLICY",
        ["safety_stock"],
        "안전재고 = z × 월 수요 표준편차 × √(리드타임 ÷ 30), 재주문점 = 월평균 수요 × 리드타임 ÷ 30 + 안전재고. WMS가 fs.scm.interface.inventory_policies()로 가져가 품목 안전재고에 반영(Q5)",
        "재고 정책 산정(Q5)",
    ),
    c(SS, "UK", S + ["score_month", "partner_code"], reason="월·공급처 1건"),
    c(
        SS,
        "CHECK",
        [
            "po_line_count",
            "on_time_rate",
            "avg_lead_time_days",
            "score",
            "grade",
            "quality_grade",
        ],
        "po_line_count >= 0 AND on_time_rate BETWEEN 0 AND 1 AND avg_lead_time_days >= 0 AND score BETWEEN 0 AND 100 AND grade IN ('A', 'B', 'C', 'D') AND (quality_grade IS NULL OR quality_grade IN ('A', 'B', 'C', 'D'))",
        "성과 값",
    ),
    c(
        SS,
        "SERVICE/DB_POLICY",
        ["score"],
        "납기 준수 = WMS 입고 확정일 ≤ ERP 발주 납기인 행 비율. 종합 = 납기 50 + 리드타임 20 + QMS 품질 등급 30(A30·B20·C10·D0). QMS 꺼짐이면 품질 제외 후 비례 환산",
        "공급처 종합 점수(Q6)",
    ),
]
for t, cols_ in [
    (FL, ["forecast_run_id"]),
    (SL, ["sop_plan_id"]),
    (DH, ["history_month"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="FK·목록 조회"))

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
    r(FL, ["forecast_run_id"], FR, "수요 예측"),
    r(SP, ["forecast_run_id"], FR, "근거 예측"),
    r(SL, ["sop_plan_id"], SP, "S&OP 계획"),
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
    st(FR, VER, "draft", "draft→confirmed→superseded"),
    st(SP, VER, "draft", "draft→confirmed→superseded"),
    st(IP, ("proposed", "superseded"), "proposed", "proposed→superseded(새 산정)"),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn26은 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "crm.opportunity" not in names:
        raise SystemExit("apply_dsn25를 먼저 적용한다")
    if FR in names:
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
        x["expression"] = x["expression"].rstrip(")") + ", 'scm')"
    for code in d["code_lists"]:
        if (
            code["target"] in MODULE_TABLES
            and code["column"] == "module_key"
            and "scm" not in code["values"]
        ):
            code["values"] = [*code["values"], "scm"]
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    d["code_lists"].append(
        dict(
            target=FL,
            column="method",
            values=list(METHODS),
            default=None,
            note="이동평균 / 단순 지수평활 / 계절 지수",
        )
    )
    d.update(version="target-0.14.0", task="DSN-26", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.14.0",
            task="DSN-26",
            date="2026-10-05",
            change="SCM 신규: scm 9테이블(계획 품목·공급처 품목·수요 이력·수요 예측·예측 명세·S&OP 계획·명세·재고 정책·공급처 성과), 모듈 키 scm. 업무 스키마 간 FK 0",
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
    scm = [t for t in d["tables"] if t["name"].startswith(P)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                scm_tables=len(scm),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
