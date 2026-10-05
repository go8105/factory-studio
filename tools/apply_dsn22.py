"""DSN-22: POP(신규) 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn21 다음).

근거: docs/modules/pop/POP_설계_DSN-22.md 4장(pop 7테이블 + 모듈 키 'pop' + MES·WMS 가져오기 종류 확장), 결정 Q1~Q6.
Q1: 지연 가져오기 — MES·WMS가 자기 API가 불릴 때 미반영 POP 확정 입력을 가져감. POP는 다른 스키마에 쓰지 않는다.
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
P = "pop."
MODULE_TABLES = {"core.workspace_module", "core.app_review"}


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-22"}


MES_KINDS = (
    "ARRIVE",
    "START",
    "COMPLETE",
    "ISSUE",
    "PACK",
    "RECEIVE",
    "DOWNTIME",
    "INSPECT",
    "CANCEL",
)
WMS_KINDS = ("RECEIVE", "PUTAWAY", "PICK", "ISSUE", "COUNT", "MOVE", "CANCEL")
TARGET_KINDS = (
    "LOT",
    "BOX",
    "PALLET",
    "WORK_ORDER",
    "WORKER",
    "EQUIPMENT",
    "LOCATION",
    "MATERIAL_LOT",
    "UNKNOWN",
)
CALL_KINDS = ("MATERIAL", "QUALITY", "MAINTENANCE", "SUPERVISOR")

TE, OP, SE, SC, EN, EL, CA = (
    P + "terminal",
    P + "operator",
    P + "session",
    P + "scan",
    P + "entry",
    P + "entry_line",
    P + "call",
)

TABLES = [
    table(
        TE,
        "단말",
        "device",
        "DSN-22 F01. 키오스크·태블릿·핸디. 설치 위치는 MES 공정 코드 또는 WMS 위치/구역 코드 스냅샷",
        [
            col("code", "단말 코드", "varchar(30)"),
            col("name", "단말명", "varchar(100)"),
            col("kind", "종류", "varchar(8)", rule="KIOSK / TABLET / HANDY"),
            col(
                "mode",
                "화면 모드",
                "varchar(10)",
                rule="PRODUCTION 생산 / WAREHOUSE 창고",
            ),
            col(
                "location_code",
                "설치 위치 코드",
                "varchar(40)",
                rule="생산: MES 공정 코드, 창고: WMS 위치·구역 코드(스냅샷)",
            ),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        OP,
        "현장 작업자",
        "device",
        "DSN-22 F02(Q2). POP 자체 단말 사용자. 작업자 바코드 = 코드. MES는 같은 코드의 MES 작업자로 연결(없으면 거부)",
        [
            col("code", "작업자 코드", "varchar(30)"),
            col("name", "이름", "varchar(100)"),
            col("role", "역할", "varchar(10)", rule="PRODUCTION / WAREHOUSE / BOTH"),
            col("hr_employee_code", "HR 사원 코드", "varchar(30)", nullable=True),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        SE,
        "단말 세션",
        "device",
        "DSN-22 F02. 작업자 바코드 스캔으로 시작, 교대·종료로 끝. 단말당 열린 세션 1개",
        [
            col("terminal_id", "단말", "bigint"),
            col("operator_id", "작업자", "bigint"),
            col("started_at", "시작", "timestamptz"),
            col("ended_at", "종료", "timestamptz", nullable=True),
        ],
    ),
    table(
        SC,
        "스캔 원장",
        "ledger",
        "DSN-22 F41·F31. 모든 스캔 시도. 대상 판별·결과는 MES·WMS pop_context 조회 결과 스냅샷. 보존 90일(세대 정리와 별개)",
        [
            col("session_id", "세션", "bigint"),
            col("scanned_at", "스캔 시각", "timestamptz"),
            col("barcode_value", "스캔 값", "varchar(80)"),
            col(
                "target_kind", "대상 종류", "varchar(12)", rule=" / ".join(TARGET_KINDS)
            ),
            col(
                "result",
                "결과",
                "varchar(6)",
                rule="OK / WARN(경고 후 진행 가능) / REJECT",
            ),
            col(
                "message",
                "안내",
                "varchar(300)",
                nullable=True,
                rule="보류 LOT·SPC 이상·순서 위반·오투입 등",
            ),
        ],
    ),
    table(
        EN,
        "확정 입력",
        "ledger",
        "DSN-22 F42~F44. MES·WMS가 가져갈 단위(entry_no = pop_entry_ref). 확정 후 불변, 정정은 CANCEL 입력·재제출은 새 입력",
        [
            col(
                "entry_no",
                "입력 번호",
                "varchar(40)",
                rule="MES·WMS pop_import의 pop_entry_ref",
            ),
            col("session_id", "세션", "bigint"),
            col("operator_code", "작업자 코드", "varchar(30)", rule="스냅샷"),
            col("terminal_code", "단말 코드", "varchar(30)", rule="스냅샷"),
            col("target_solution", "반영 솔루션", "varchar(3)", rule="MES / WMS"),
            col(
                "entry_kind",
                "입력 종류",
                "varchar(10)",
                rule="MES: " + "·".join(MES_KINDS) + " / WMS: " + "·".join(WMS_KINDS),
            ),
            col("confirmed_at", "확정 시각", "timestamptz"),
            col("barcode_value", "주 스캔 값", "varchar(80)", nullable=True),
            col("lot_no", "LOT 번호", "varchar(50)", nullable=True),
            col("work_order_no", "작업지시 번호", "varchar(40)", nullable=True),
            col("equipment_code", "설비 코드", "varchar(40)", nullable=True),
            col("item_code", "품목 코드", "varchar(40)", nullable=True),
            col("location_code", "위치 코드", "varchar(40)", nullable=True),
            col("to_location_code", "도착 위치 코드", "varchar(40)", nullable=True),
            col("packing_no", "패킹 번호", "varchar(40)", nullable=True),
            col(
                "doc_no",
                "WMS 지시 번호",
                "varchar(40)",
                nullable=True,
                rule="입고 예정·적치·피킹·불출·실사 번호",
            ),
            col("qty", "수량", "numeric(18,3)", nullable=True),
            col("good_qty", "양품", "numeric(18,3)", nullable=True),
            col("defect_qty", "불량", "numeric(18,3)", nullable=True),
            col("unit", "단위", "varchar(10)", nullable=True),
            col(
                "reason_code",
                "사유 코드",
                "varchar(30)",
                nullable=True,
                rule="비가동·조정 사유(MES 사유 코드 스냅샷)",
            ),
            col("note", "메모", "varchar(300)", nullable=True),
            col("cancels_entry_id", "취소 대상 입력", "bigint", nullable=True),
            col("resubmit_of_id", "재제출 원 입력", "bigint", nullable=True),
        ],
    ),
    table(
        EL,
        "확정 입력 명세",
        "ledger",
        "DSN-22 F13·F18·F25. 불량 코드별 수량·공정 검사 값·실사 행 등 여러 줄 입력",
        [
            col("entry_id", "확정 입력", "bigint"),
            col("line_no", "행 번호", "integer"),
            col("line_kind", "행 종류", "varchar(8)", rule="DEFECT / INSPECT / COUNT"),
            col(
                "code",
                "코드",
                "varchar(50)",
                rule="불량 코드 · 검사 항목 순서 · LOT/위치",
            ),
            col("value", "값", "numeric(18,4)", nullable=True),
            col("pass_value", "합·부", "boolean", nullable=True),
        ],
    ),
    table(
        CA,
        "호출",
        "call",
        "DSN-22 F34(Q4). 자재·품질·보전·관리자 호출 → 확인 → 완료. POP 안에서만(CMMS 신호 아님)",
        [
            col("call_no", "호출 번호", "varchar(40)"),
            col("terminal_id", "단말", "bigint"),
            col("operator_id", "호출자", "bigint"),
            col("call_kind", "종류", "varchar(12)", rule=" / ".join(CALL_KINDS)),
            col("raised_at", "호출 시각", "timestamptz"),
            col(
                "status",
                "상태",
                "varchar(6)",
                default="'OPEN'",
                rule="OPEN / ACK / DONE",
            ),
            col("acked_at", "확인 시각", "timestamptz", nullable=True),
            col("done_at", "완료 시각", "timestamptz", nullable=True),
            col("responder_name", "응답자", "varchar(60)", nullable=True),
            col("note", "메모", "varchar(300)", nullable=True),
        ],
    ),
]

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in (TE, OP):
    CONSTRAINTS += [
        c(t, "UK", S + ["code"], reason="세대 내 코드 유일"),
        c(t, "CHECK", ["code"], f"code {CODE}", "코드 형식"),
    ]
for t, field in [(EN, "entry_no"), (CA, "call_no")]:
    CONSTRAINTS += [
        c(t, "UK", S + [field], reason="세대 내 번호 유일"),
        c(t, "CHECK", [field], f"length(btrim({field})) > 0", "번호 필수"),
    ]
CONSTRAINTS += [
    c(
        TE,
        "CHECK",
        ["kind", "mode"],
        "kind IN ('KIOSK', 'TABLET', 'HANDY') AND mode IN ('PRODUCTION', 'WAREHOUSE')",
        "종류·모드",
    ),
    c(OP, "CHECK", ["role"], "role IN ('PRODUCTION', 'WAREHOUSE', 'BOTH')", "역할 값"),
    c(
        SE,
        "CHECK",
        ["started_at", "ended_at"],
        "ended_at IS NULL OR ended_at >= started_at",
        "시각 순서",
    ),
    uk_partial(SE, ["terminal_id"], "ended_at IS NULL", "단말당 열린 세션 1개"),
    c(
        SE,
        "SERVICE/DB_POLICY",
        ["operator_id"],
        "작업자 역할이 단말 모드와 맞아야 시작(BOTH는 둘 다). 새 작업자 스캔 = 이전 세션 종료 + 새 세션(교대)",
        "세션 시작·교대(Q2)",
    ),
    c(
        SC,
        "CHECK",
        ["target_kind", "result"],
        f"target_kind IN ({q(TARGET_KINDS)}) AND result IN ('OK', 'WARN', 'REJECT')",
        "대상·결과",
    ),
    c(
        SC,
        "CHECK",
        ["result", "message"],
        "result = 'OK' OR message IS NOT NULL",
        "경고·거부는 안내 필수",
    ),
    c(
        SC,
        "SERVICE/DB_POLICY",
        ["target_kind"],
        "스캔 값의 대상·허용 동작은 fs.mes.interface.pop_context / fs.wms.interface.pop_context 읽기로 판별(모드에 따라). 꺼져 있으면 REJECT '반영 솔루션 꺼짐'. 보존 90일 후 정리",
        "스캔 즉시 확인(F31)",
    ),
    c(
        EN,
        "CHECK",
        ["target_solution", "entry_kind"],
        f"(target_solution = 'MES' AND entry_kind IN ({q(MES_KINDS)})) OR (target_solution = 'WMS' AND entry_kind IN ({q(WMS_KINDS)}))",
        "반영 솔루션별 입력 종류",
    ),
    c(
        EN,
        "CHECK",
        ["entry_kind", "cancels_entry_id"],
        "(entry_kind = 'CANCEL') = (cancels_entry_id IS NOT NULL)",
        "취소 입력은 대상 필수",
    ),
    c(
        EN,
        "CHECK",
        ["qty", "good_qty", "defect_qty"],
        "(qty IS NULL OR qty >= 0) AND (good_qty IS NULL OR good_qty >= 0) AND (defect_qty IS NULL OR defect_qty >= 0)",
        "수량 음수 금지",
    ),
    c(
        EN,
        "CHECK",
        ["cancels_entry_id", "resubmit_of_id"],
        "NOT (cancels_entry_id IS NOT NULL AND resubmit_of_id IS NOT NULL)",
        "취소·재제출 동시 금지",
    ),
    uk_partial(
        EN, ["cancels_entry_id"], "cancels_entry_id IS NOT NULL", "입력당 취소 1건"
    ),
    c(
        EN,
        "SERVICE/DB_POLICY",
        ["entry_no"],
        "확정 = pop_context로 다시 확인 후 저장, 이후 불변. MES·WMS가 자기 API가 불릴 때 fs.pop.interface.confirmed_entries(since)로 미반영분을 가져가 재검증·반영(Q1 지연 가져오기, 배경 작업 없음). 결과는 MES·WMS pop_results(entry_nos) 조회로 표시",
        "확정·지연 가져오기(Q1)",
    ),
    c(
        EN,
        "SERVICE/DB_POLICY",
        ["cancels_entry_id"],
        "CANCEL: 원 입력이 아직 가져가지 않았으면 MES·WMS가 둘 다 건너뜀(REJECTED '취소됨'), 이미 반영됐으면 CANCEL을 거부('반영됨 — MES/WMS에서 정정'). POP는 다른 스키마에 쓰지 않는다",
        "취소 입력 처리",
    ),
    c(EL, "UK", S + ["entry_id", "line_no"], reason="입력 내 행 번호 유일"),
    c(
        EL,
        "CHECK",
        ["line_no", "line_kind", "value", "pass_value"],
        "line_no >= 1 AND line_kind IN ('DEFECT', 'INSPECT', 'COUNT') AND (value IS NOT NULL OR pass_value IS NOT NULL)",
        "행 종류·값",
    ),
    c(
        CA,
        "CHECK",
        ["call_kind", "status"],
        f"call_kind IN ({q(CALL_KINDS)}) AND status IN ('OPEN', 'ACK', 'DONE')",
        "종류·상태",
    ),
    c(
        CA,
        "CHECK",
        ["status", "acked_at", "done_at", "raised_at"],
        "((status = 'OPEN') = (acked_at IS NULL)) AND ((status = 'DONE') = (done_at IS NOT NULL)) AND (acked_at IS NULL OR acked_at >= raised_at) AND (done_at IS NULL OR done_at >= acked_at)",
        "상태별 시각",
    ),
    uk_partial(
        CA,
        ["terminal_id", "call_kind"],
        "status <> 'DONE'",
        "단말·종류당 진행 호출 1건",
    ),
]
for t, cols_ in [
    (SC, ["session_id", "scanned_at"]),
    (EN, ["target_solution", "confirmed_at"]),
    (EN, ["session_id"]),
    (EL, ["entry_id"]),
    (CA, ["status", "raised_at"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="가져오기·목록 조회"))

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
    r(SE, ["terminal_id"], TE, "단말"),
    r(SE, ["operator_id"], OP, "작업자"),
    r(SC, ["session_id"], SE, "세션"),
    r(EN, ["session_id"], SE, "세션"),
    r(EN, ["cancels_entry_id"], EN, "취소 대상 입력"),
    r(EN, ["resubmit_of_id"], EN, "재제출 원 입력"),
    r(EL, ["entry_id"], EN, "확정 입력"),
    r(CA, ["terminal_id"], TE, "단말"),
    r(CA, ["operator_id"], OP, "호출자"),
]
STATES = [
    dict(
        table=CA,
        column="status",
        values=["OPEN", "ACK", "DONE"],
        default="OPEN",
        transition="OPEN→ACK→DONE; OPEN→DONE",
    )
]

# MES·WMS 가져오기 종류 확장(공정 검사·비가동·취소)
REPLACED = {
    (
        "mes.pop_import",
        "entry_kind IN ('ARRIVE', 'START', 'COMPLETE', 'ISSUE', 'PACK', 'RECEIVE') AND result IN ('APPLIED', 'REJECTED')",
    ): f"entry_kind IN ({q(MES_KINDS)}) AND result IN ('APPLIED', 'REJECTED')",
    (
        "wms.pop_import",
        "entry_kind IN ('RECEIVE', 'PUTAWAY', 'PICK', 'ISSUE', 'COUNT', 'MOVE') AND result IN ('APPLIED', 'REJECTED')",
    ): f"entry_kind IN ({q(WMS_KINDS)}) AND result IN ('APPLIED', 'REJECTED')",
}


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn22는 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "cmms.technician" not in names:
        raise SystemExit("apply_dsn21을 먼저 적용한다")
    if EN in names:
        return False
    hits = {(x["table"], x["expression"]) for x in d["constraints"]} & set(REPLACED)
    modules = [
        x
        for x in d["constraints"]
        if x["table"] in MODULE_TABLES
        and x["kind"] == "CHECK"
        and "module_key IN" in x["expression"]
    ]
    if len(hits) != len(REPLACED) or len(modules) != 2:
        raise SystemExit(
            f"바꿀 기존 제약을 찾지 못했다: {set(REPLACED) - hits}, 모듈 키 CHECK {len(modules)}개"
        )
    for x in d["constraints"]:
        new = REPLACED.get((x["table"], x["expression"]))
        if new:
            x["expression"] = new
    for x in modules:
        x["expression"] = x["expression"].rstrip(")") + ", 'pop')"
    for code in d["code_lists"]:
        if (
            code["target"] in MODULE_TABLES
            and code["column"] == "module_key"
            and "pop" not in code["values"]
        ):
            code["values"] = [*code["values"], "pop"]
        if code["target"] == "mes.pop_import" and code["column"] == "entry_kind":
            code["values"] = list(MES_KINDS)
        if code["target"] == "wms.pop_import" and code["column"] == "entry_kind":
            code["values"] = list(WMS_KINDS)
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    d["code_lists"].append(
        dict(
            target=EN,
            column="target_solution",
            values=["MES", "WMS"],
            default=None,
            note="생산 입력 → MES, 창고 입력 → WMS",
        )
    )
    d.update(version="target-0.10.0", task="DSN-22", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.10.0",
            task="DSN-22",
            date="2026-10-05",
            change="POP 신규: pop 7테이블(단말·현장 작업자·세션·스캔 원장·확정 입력·명세·호출), 모듈 키 pop(workspace_module·app_review), MES·WMS pop_import 종류 확장(공정 검사·비가동·취소). 업무 스키마 간 FK 0",
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
    pop = [t for t in d["tables"] if t["name"].startswith(P)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                pop_tables=len(pop),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
