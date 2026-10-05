"""DSN-17: SPC 보강 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn16 다음).

근거: docs/modules/spc/SPC_보강설계_DSN-17.md 4장(새 테이블 5·기존 테이블 변경 5), 결정 Q1~Q7.
관리도 계수(A2·D3·D4·d2·E2, n=1~10)는 FS-028과 같이 코드 상수. I-MR은 X̄·R 칸을 I·MR로 쓰고, 계수형은 중심값(p̄·c̄·ū·np̄)만 저장(한계는 부분군 크기마다 계산).
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
P = "spc."


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-17"}


CHART_TYPES = ("XBAR_R", "I_MR", "P", "NP", "C", "U")
ATTRIBUTE = ("P", "NP", "C", "U")
CHARTS = ("XBAR", "R", "I", "MR", "P", "NP", "C", "U")
LOCATION_CHARTS = ("XBAR", "I", "P", "NP", "C", "U")
VER = ("draft", "confirmed", "superseded")

CR, SV, OI, OC, RP = (
    P + "characteristic_rule",
    P + "spec_violation",
    P + "ocap_item",
    P + "ocap_check",
    P + "capability_report",
)

TABLES = [
    table(
        CR,
        "특성별 판정 규칙",
        "rule",
        "DSN-17 F22·F23(Q3). 특성이 쓰는 Nelson 규칙(1~8). 행이 없으면 기본 1~3(FS-028 D41)",
        [
            col("characteristic_id", "관리 특성", "bigint"),
            col(
                "rule_no",
                "규칙 번호",
                "integer",
                rule="1 한계 밖 · 2 한쪽 9점 · 3 6점 증감 · 4 14점 교대 · 5 3점 중 2점 2σ 밖 · 6 5점 중 4점 1σ 밖 · 7 15점 1σ 안 · 8 8점 1σ 밖 양쪽",
            ),
        ],
    ),
    table(
        SV,
        "규격 이탈",
        "signal",
        "DSN-17 F24·F33(Q4). 개별 측정값이 LSL·USL 밖. 관리 이탈(이상 기록)과 별개. QMS가 읽어 부적합 보고(발생처 공정) 후보로",
        [
            col("subgroup_id", "부분군", "bigint"),
            col("characteristic_id", "관리 특성", "bigint"),
            col("seq", "측정 순번", "integer"),
            col("lot_no", "LOT 번호", "varchar(50)", rule="부분군 스냅샷"),
            col("value", "측정값", "numeric(18,6)"),
            col("side", "이탈 방향", "varchar(4)", rule="LOW / HIGH"),
            col(
                "limit_value",
                "규격 한계",
                "numeric(18,6)",
                rule="그때 LSL 또는 USL 스냅샷",
            ),
            col("detected_at", "탐지 시각", "timestamptz"),
            col(
                "voided_at",
                "무효 시각",
                "timestamptz",
                nullable=True,
                rule="부분군 무효화와 함께",
            ),
        ],
    ),
    table(
        OI,
        "이상 대응 점검 항목",
        "ocap",
        "DSN-17 F32(Q5). 특성(NULL = 공통)·규칙(NULL = 모든 규칙)별 표준 점검 순서",
        [
            col("characteristic_id", "관리 특성", "bigint", nullable=True),
            col("rule_no", "규칙 번호", "integer", nullable=True),
            col("seq", "순서", "integer"),
            col("check_text", "점검 내용", "varchar(300)"),
            col(
                "cause_category",
                "해당 원인",
                "varchar(12)",
                nullable=True,
                rule="MACHINE / MATERIAL / MAN / METHOD / MEASUREMENT / ENVIRONMENT",
            ),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        OC,
        "이상 대응 점검 결과",
        "ocap",
        "DSN-17 F32. 이상 1건 × 점검 항목. 조치 완료 전에 해당 항목 모두 기록",
        [
            col("signal_id", "이상 기록", "bigint"),
            col("ocap_item_id", "점검 항목", "bigint"),
            col("result", "결과", "varchar(3)", rule="OK / NG / NA"),
            col("note", "메모", "varchar(300)", nullable=True),
            col("checked_at", "점검 시각", "timestamptz"),
        ],
    ),
    table(
        RP,
        "공정능력 보고서",
        "report",
        "DSN-17 F41~F46(Q6). 특성·기간의 능력 지표 확정 스냅샷. 재작성은 새 버전",
        [
            col("characteristic_id", "관리 특성", "bigint"),
            col("report_start_on", "기간 시작", "date"),
            col("report_end_on", "기간 끝", "date"),
            col("version", "버전", "integer"),
            col(
                "status", "상태", "varchar(12)", default="'draft'", rule=" / ".join(VER)
            ),
            col("subgroup_count", "부분군 수", "integer"),
            col("mean", "평균", "numeric(18,6)"),
            col("sigma_within", "군내 σ(R̄/d2)", "numeric(18,6)"),
            col("sigma_overall", "전체 σ", "numeric(18,6)"),
            col("cp", "Cp", "numeric(8,3)", nullable=True),
            col("cpk", "Cpk", "numeric(8,3)", nullable=True),
            col("pp", "Pp", "numeric(8,3)", nullable=True),
            col("ppk", "Ppk", "numeric(8,3)", nullable=True),
            col("skewness", "왜도", "numeric(8,4)", nullable=True),
            col("kurtosis", "첨도", "numeric(8,4)", nullable=True),
            col("comment", "의견", "varchar(1000)", nullable=True),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
        ],
    ),
]

NEW_COLUMNS = {
    P + "characteristic": [
        col(
            "chart_type",
            "관리도 종류",
            "varchar(8)",
            default="'XBAR_R'",
            rule=" / ".join(CHART_TYPES) + "(Q1·Q2)",
        ),
        col(
            "defect_source",
            "불량 수 출처",
            "varchar(6)",
            nullable=True,
            rule="계수형: MES(확정 실적 조회) / MANUAL",
        ),
    ],
    P + "control_limit": [
        col(
            "attr_center",
            "계수형 중심값",
            "numeric(18,6)",
            nullable=True,
            rule="p̄·np̄·c̄·ū. 한계는 부분군 크기마다 계산",
        )
    ],
    P + "subgroup": [
        col(
            "inspected_qty",
            "검사 수(n)",
            "numeric(18,3)",
            nullable=True,
            rule="계수형 부분군",
        ),
        col(
            "defect_count",
            "불량·결점 수",
            "numeric(18,3)",
            nullable=True,
            rule="계수형 부분군",
        ),
        col(
            "gauge_code",
            "계측기 번호",
            "varchar(30)",
            nullable=True,
            rule="F07 QMS 계측기 코드 스냅샷",
        ),
    ],
}
NULLABLE = {
    (P + "control_limit", n)
    for n in ("xbar_cl", "xbar_ucl", "xbar_lcl", "r_cl", "r_ucl", "r_lcl")
} | {(P + "subgroup", "xbar"), (P + "subgroup", "r")}

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
CONSTRAINTS += [
    c(CR, "UK", S + ["characteristic_id", "rule_no"], reason="특성·규칙 1회"),
    c(CR, "CHECK", ["rule_no"], "rule_no BETWEEN 1 AND 8", "Nelson 규칙 1~8"),
    c(
        CR,
        "SERVICE/DB_POLICY",
        ["rule_no"],
        "규칙 2~8은 위치 관리도(X̄·I·p·np·c·u)에만. 계수형은 규칙 1~4만 쓴다. 행이 없으면 1~3",
        "판정 규칙 선택(Q3)",
    ),
    c(SV, "UK", S + ["subgroup_id", "seq"], reason="측정값당 이탈 1건"),
    c(
        SV,
        "CHECK",
        ["side", "value", "limit_value"],
        "(side = 'LOW' AND value < limit_value) OR (side = 'HIGH' AND value > limit_value)",
        "방향·값",
    ),
    c(
        SV,
        "SERVICE/DB_POLICY",
        ["detected_at"],
        "부분군 기록 때 측정값별로 규격과 비교해 생성(관리 이탈 판정과 같은 트랜잭션). QMS가 fs.spc.interface.spec_violations(since)로 읽어 부적합 보고 후보(Q4). SPC는 QMS 결과를 저장하지 않는다",
        "규격 이탈 → QMS(Q4)",
    ),
    c(
        OI,
        "UK",
        S + ["characteristic_id", "rule_no", "seq"],
        reason="특성·규칙·순서 유일",
    ),
    uk_partial(
        OI,
        ["seq"],
        "characteristic_id IS NULL AND rule_no IS NULL",
        "공통 항목 순서 유일",
    ),
    c(
        OI,
        "CHECK",
        ["rule_no", "seq", "check_text", "cause_category"],
        "(rule_no IS NULL OR rule_no BETWEEN 1 AND 8) AND seq >= 1 AND length(btrim(check_text)) >= 2 AND (cause_category IS NULL OR cause_category IN ('MACHINE', 'MATERIAL', 'MAN', 'METHOD', 'MEASUREMENT', 'ENVIRONMENT'))",
        "규칙·순서·내용·원인",
    ),
    c(OC, "UK", S + ["signal_id", "ocap_item_id"], reason="이상·항목당 결과 1건"),
    c(
        OC,
        "CHECK",
        ["result", "note"],
        "result IN ('OK', 'NG', 'NA') AND (result <> 'NG' OR length(btrim(note)) >= 2)",
        "결과·NG 메모",
    ),
    c(
        OC,
        "SERVICE/DB_POLICY",
        ["signal_id"],
        "조치 완료 전에 그 이상에 해당하는 사용 항목(특성·규칙 일치 + 공통)을 모두 기록. NG 항목의 원인 분류를 조치 원인 기본값으로 제안. 조치 완료 후 불변",
        "OCAP 기록(Q5)",
    ),
    c(
        RP,
        "UK",
        S + ["characteristic_id", "report_start_on", "report_end_on", "version"],
        reason="특성·기간·버전 유일",
    ),
    uk_partial(
        RP,
        ["characteristic_id", "report_start_on", "report_end_on"],
        "status = 'confirmed'",
        "특성·기간당 확정 1건",
    ),
    c(
        RP,
        "CHECK",
        ["status", "version", "confirmed_at"],
        "status IN ('draft', 'confirmed', 'superseded') AND version >= 1 AND ((status = 'draft') = (confirmed_at IS NULL))",
        "상태·버전",
    ),
    c(
        RP,
        "CHECK",
        [
            "report_start_on",
            "report_end_on",
            "subgroup_count",
            "sigma_within",
            "sigma_overall",
        ],
        "report_end_on >= report_start_on AND subgroup_count >= 20 AND sigma_within >= 0 AND sigma_overall >= 0",
        "기간·부분군 수·σ",
    ),
    c(
        RP,
        "SERVICE/DB_POLICY",
        ["cp", "pp"],
        "Cp·Cpk는 군내 σ(R̄/d2 또는 MR̄/1.128), Pp·Ppk는 전체 σ(표본 표준편차). 한쪽 규격이면 해당 쪽만. 유효 부분군만. 확정 후 불변",
        "능력 지표 계산(Q6)",
    ),
]
for t, cols_ in [
    (SV, ["characteristic_id", "detected_at"]),
    (OC, ["signal_id"]),
    (RP, ["characteristic_id"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="FK·목록 조회"))

CHANGED_CONSTRAINTS = [
    c(
        P + "characteristic",
        "CHECK",
        ["chart_type", "subgroup_size", "defect_source"],
        f"chart_type IN ({q(CHART_TYPES)}) AND ((chart_type = 'I_MR') = (subgroup_size = 1)) AND ((chart_type IN ({q(ATTRIBUTE)})) = (defect_source IS NOT NULL)) AND (defect_source IS NULL OR defect_source IN ('MES', 'MANUAL'))",
        "관리도 종류·부분군 크기·불량 출처(Q1·Q2)",
    ),
    c(
        P + "subgroup",
        "CHECK",
        ["xbar", "r", "inspected_qty", "defect_count"],
        "(xbar IS NOT NULL AND inspected_qty IS NULL AND defect_count IS NULL) OR (xbar IS NULL AND r IS NULL AND inspected_qty > 0 AND defect_count >= 0)",
        "계량형(X̄·R) 또는 계수형(검사 수·불량 수) 하나",
    ),
    c(
        P + "subgroup",
        "SERVICE/DB_POLICY",
        ["defect_count"],
        "계수형 부분군 = MES 확정 실적(fs.mes.interface 조회: 투입 = 검사 수, 불량 수)을 LOT·일별로 읽어 생성(원천 1건당 1건) 또는 수동. p·np는 불량 수 ≤ 검사 수",
        "계수형 부분군(Q2)",
    ),
    c(
        P + "control_limit",
        "SERVICE/DB_POLICY",
        ["attr_center"],
        "계량형은 xbar_*·r_*(I-MR이면 I·MR), 계수형은 attr_center만 저장하고 한계는 부분군 검사 수마다 계산. 계수(A2·D3·D4·d2·E2, n=1~10)는 코드 상수",
        "관리도별 한계(Q1·Q2)",
    ),
]
REPLACED = {
    (P + "characteristic", "subgroup_size = 5"): "subgroup_size BETWEEN 1 AND 10",
    (
        P + "characteristic",
        "(lsl IS NOT NULL OR usl IS NOT NULL) AND (lsl IS NULL OR usl IS NULL OR lsl < usl)",
    ): "(chart_type IN ('P', 'NP', 'C', 'U') OR lsl IS NOT NULL OR usl IS NOT NULL) AND (lsl IS NULL OR usl IS NULL OR lsl < usl)",
    (P + "measurement", "seq BETWEEN 1 AND 5"): "seq BETWEEN 1 AND 10",
    (P + "signal", "chart IN ('XBAR', 'R')"): f"chart IN ({q(CHARTS)})",
    (P + "signal", "rule BETWEEN 1 AND 3"): "rule BETWEEN 1 AND 8",
    (
        P + "signal",
        "rule = 1 OR chart = 'XBAR'",
    ): f"rule = 1 OR chart IN ({q(LOCATION_CHARTS)})",
    (
        P + "subgroup",
        "source IN ('SEED', 'MANUAL')",
    ): "source IN ('SEED', 'MANUAL', 'MES', 'FILE')",
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
    r(CR, ["characteristic_id"], P + "characteristic", "관리 특성"),
    r(SV, ["subgroup_id"], P + "subgroup", "부분군"),
    r(SV, ["characteristic_id"], P + "characteristic", "관리 특성"),
    r(OI, ["characteristic_id"], P + "characteristic", "관리 특성"),
    r(OC, ["signal_id"], P + "signal", "이상 기록"),
    r(OC, ["ocap_item_id"], OI, "점검 항목"),
    r(RP, ["characteristic_id"], P + "characteristic", "관리 특성"),
]
STATES = [
    dict(
        table=RP,
        column="status",
        values=list(VER),
        default="draft",
        transition="draft→confirmed→superseded",
    )
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn17은 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "bems.demand_plan" not in names:
        raise SystemExit("apply_dsn16을 먼저 적용한다")
    if SV in names:
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
                x["nullable"] = True
    for x in d["constraints"]:
        new = REPLACED.get((x["table"], x["expression"]))
        if new:
            x["expression"] = new
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS + CHANGED_CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    d["code_lists"].append(
        dict(
            target=P + "characteristic",
            column="chart_type",
            values=list(CHART_TYPES),
            default="XBAR_R",
            note="X̄-R / I-MR / p / np / c / u",
        )
    )
    d.update(version="target-0.8.0", task="DSN-17", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.8.0",
            task="DSN-17",
            date="2026-10-05",
            change="SPC 보강: 새 테이블 5(특성별 판정 규칙·규격 이탈·OCAP 항목/결과·공정능력 보고서), 기존 5테이블 변경(특성 관리도 종류·n=1~10, 한계 계수형 중심값·X̄/R 칸 NULL 허용, 부분군 계수형·계측기·출처, 측정 순번 1~10, 이상 관리도 8종·규칙 1~8)",
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
    spc = [t for t in d["tables"] if t["name"].startswith(P)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                spc_tables=len(spc),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
