"""DSN-23: TMS(신규) 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn22 다음).

근거: docs/modules/tms/TMS_설계_DSN-23.md 4장(tms 10테이블 + 모듈 키 'tms'), 결정 Q1~Q7.
Q1: TMS는 ERP·WMS를 바꾸지 않는다 — ERP 출하지시·WMS 피킹 완료를 읽고, 상차·배송 결과를 ERP가 읽는다.
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
T = "tms."
MODULE_TABLES = {"core.workspace_module", "core.app_review"}


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-23"}


def money(name, label, nullable=False):
    return col(name, label, "numeric(18,2)", nullable=nullable)


DISPATCH_STATES = ("PLANNED", "LOADED", "DEPARTED", "COMPLETED", "CANCELLED")
STOP_STATES = (
    "PENDING",
    "LOADED",
    "ARRIVED",
    "DELIVERED",
    "PARTIAL",
    "FAILED",
    "CANCELLED",
)
CHARGE_KINDS = ("BASE", "EXTRA_STOP", "WAITING", "TOLL", "FUEL", "OTHER")

CA, VE, DR, ZO, DP, FR, DI, DS, DC, SE = (
    T + "carrier",
    T + "vehicle",
    T + "driver",
    T + "zone",
    T + "delivery_point",
    T + "freight_rate",
    T + "dispatch",
    T + "dispatch_stop",
    T + "dispatch_charge",
    T + "settlement",
)

TABLES = [
    table(
        CA,
        "운송사",
        "master",
        "DSN-23 F02(Q2). 용차 업체. ERP 거래처 코드 스냅샷(정산 → ERP 매입)",
        [
            col("code", "운송사 코드", "varchar(30)"),
            col("name", "운송사명", "varchar(200)"),
            col("erp_partner_code", "ERP 거래처 코드", "varchar(40)", nullable=True),
            col("phone", "연락처", "varchar(30)", nullable=True),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        VE,
        "차량",
        "master",
        "DSN-23 F01(Q2). 자차·용차(운송사 필수). 적재 한도는 적재율 경고 기준",
        [
            col("vehicle_no", "차량 번호", "varchar(20)", rule="합성 번호"),
            col("ownership", "구분", "varchar(5)", rule="OWN 자차 / HIRED 용차"),
            col("carrier_id", "운송사", "bigint", nullable=True),
            col("tonnage", "톤수", "numeric(5,1)"),
            col("max_weight_kg", "적재 중량(kg)", "numeric(10,1)"),
            col("max_volume_m3", "적재 용적(㎥)", "numeric(8,2)"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        DR,
        "기사",
        "master",
        "DSN-23 F03. 이름·연락처(합성)만. 기사 화면 식별 = 기사 코드",
        [
            col("code", "기사 코드", "varchar(30)"),
            col("name", "이름", "varchar(60)"),
            col("phone", "연락처", "varchar(30)", nullable=True),
            col(
                "carrier_id",
                "소속 운송사",
                "bigint",
                nullable=True,
                rule="NULL이면 자사 기사",
            ),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        ZO,
        "배송 권역",
        "master",
        "DSN-23 F05. 운임표의 단위",
        [
            col("code", "권역 코드", "varchar(30)"),
            col("name", "권역명", "varchar(100)"),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        DP,
        "배송지",
        "master",
        "DSN-23 F04. 납품처(ERP 거래처 코드·주소 스냅샷) + 하차 조건. 조달 운송의 상차지(공급처)도 같은 표",
        [
            col("code", "배송지 코드", "varchar(30)"),
            col("partner_code", "ERP 거래처 코드", "varchar(40)"),
            col("name", "배송지명", "varchar(200)"),
            col("address", "주소", "varchar(300)"),
            col("zone_id", "권역", "bigint"),
            col("unload_note", "하차 조건", "varchar(300)", nullable=True),
            col("is_active", "사용 여부", "boolean", default="true"),
        ],
    ),
    table(
        FR,
        "운임표",
        "freight",
        "DSN-23 F05·F31(Q5). 권역 × 톤수 기본 운임 + 경유지·대기 추가 요금. 적용일 이력",
        [
            col("zone_id", "권역", "bigint"),
            col("tonnage", "톤수", "numeric(5,1)"),
            money("base_rate", "기본 운임"),
            money("extra_stop_rate", "경유지 1곳 추가"),
            money("waiting_rate_per_hour", "대기 시간당"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col("valid_from", "적용일", "date"),
        ],
    ),
    table(
        DI,
        "배차",
        "dispatch",
        "DSN-23 F12~F14·F21·F22(Q1·Q3·Q6). 차량 1대의 하루 운행 1건. 출하(OUTBOUND)·조달(INBOUND). 적재 합계·운임은 확정 시 스냅샷",
        [
            col("dispatch_no", "배차 번호", "varchar(40)"),
            col("dispatch_on", "운행일", "date"),
            col("direction", "방향", "varchar(8)", rule="OUTBOUND 출하 / INBOUND 조달"),
            col("vehicle_id", "차량", "bigint"),
            col("driver_id", "기사", "bigint"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'PLANNED'",
                rule=" / ".join(DISPATCH_STATES),
            ),
            col("loaded_at", "상차 완료", "timestamptz", nullable=True),
            col("departed_at", "출발", "timestamptz", nullable=True),
            col("completed_at", "운행 완료", "timestamptz", nullable=True),
            col(
                "total_weight_kg",
                "적재 중량 합(kg)",
                "numeric(12,1)",
                nullable=True,
                rule="상차 완료 시 스냅샷",
            ),
            col("total_volume_m3", "적재 용적 합(㎥)", "numeric(10,2)", nullable=True),
            col("settlement_id", "운송사 정산", "bigint", nullable=True, rule="용차만"),
            col("cancel_reason", "취소 사유", "varchar(300)", nullable=True),
        ],
    ),
    table(
        DS,
        "배송지 방문",
        "dispatch",
        "DSN-23 F11·F21·F23·F24. 배차의 순서별 방문. 출하는 ERP 출하지시 번호, 조달은 ERP 발주·WMS 입고 예정 번호 스냅샷",
        [
            col("dispatch_id", "배차", "bigint"),
            col("seq", "방문 순서", "integer"),
            col("kind", "종류", "varchar(8)", rule="DELIVERY 납품 / PICKUP 조달 상차"),
            col("delivery_point_id", "배송지", "bigint"),
            col("shipment_order_no", "ERP 출하지시 번호", "varchar(40)", nullable=True),
            col("po_no", "ERP 발주 번호", "varchar(40)", nullable=True),
            col(
                "inbound_notice_no", "WMS 입고 예정 번호", "varchar(40)", nullable=True
            ),
            col(
                "weight_kg",
                "중량(kg)",
                "numeric(12,1)",
                rule="품목 단위 중량(MES 조회) × 수량 스냅샷",
            ),
            col("volume_m3", "용적(㎥)", "numeric(10,2)", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'PENDING'",
                rule=" / ".join(STOP_STATES),
            ),
            col("loaded_at", "상차 시각", "timestamptz", nullable=True),
            col("arrived_at", "도착 시각", "timestamptz", nullable=True),
            col("finished_at", "인수·실패 시각", "timestamptz", nullable=True),
            col("receiver_name", "인수자", "varchar(60)", nullable=True),
            col(
                "fail_reason",
                "실패 사유",
                "varchar(10)",
                nullable=True,
                rule="ABSENT 부재 / REFUSED 거부 / DAMAGED 파손 / OTHER",
            ),
            col("note", "메모", "varchar(300)", nullable=True),
        ],
    ),
    table(
        DC,
        "운행 비용",
        "freight",
        "DSN-23 F31·F33(Q5·Q7). 운임(기본·경유·대기)과 자차 운행비(유류·통행료). 운행 완료 시 운임 행 생성",
        [
            col("dispatch_id", "배차", "bigint"),
            col("kind", "종류", "varchar(10)", rule=" / ".join(CHARGE_KINDS)),
            money("amount", "금액"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col("note", "메모", "varchar(300)", nullable=True),
        ],
    ),
    table(
        SE,
        "운송사 정산",
        "freight",
        "DSN-23 F32(Q5). 용차 운송사 월 정산서. 확정 1건(취소 후 재작성). ERP가 읽어 직접 매입",
        [
            col("settlement_no", "정산 번호", "varchar(40)"),
            col("carrier_id", "운송사", "bigint"),
            col("settle_month", "정산 월", "varchar(7)", rule="'YYYY-MM'"),
            money("total_amount", "정산 금액"),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'draft'",
                rule="draft / confirmed / cancelled",
            ),
            col("confirmed_at", "확정 시각", "timestamptz", nullable=True),
            col("cancel_reason", "취소 사유", "varchar(300)", nullable=True),
        ],
    ),
]

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in (CA, DR, ZO, DP):
    CONSTRAINTS += [
        c(t, "UK", S + ["code"], reason="세대 내 코드 유일"),
        c(t, "CHECK", ["code"], f"code {CODE}", "코드 형식"),
    ]
for t, field in [(DI, "dispatch_no"), (SE, "settlement_no")]:
    CONSTRAINTS += [
        c(t, "UK", S + [field], reason="세대 내 번호 유일"),
        c(t, "CHECK", [field], f"length(btrim({field})) > 0", "번호 필수"),
    ]
for t in (FR, DC, SE):
    CONSTRAINTS.append(c(t, "CHECK", ["currency"], "currency = 'KRW'", "KRW 고정"))
CONSTRAINTS += [
    c(VE, "UK", S + ["vehicle_no"], reason="차량 번호 유일"),
    c(
        VE,
        "CHECK",
        ["ownership", "carrier_id"],
        "ownership IN ('OWN', 'HIRED') AND ((ownership = 'HIRED') = (carrier_id IS NOT NULL))",
        "용차는 운송사 필수",
    ),
    c(
        VE,
        "CHECK",
        ["tonnage", "max_weight_kg", "max_volume_m3"],
        "tonnage > 0 AND max_weight_kg > 0 AND max_volume_m3 > 0",
        "적재 한도 양수",
    ),
    c(
        FR,
        "UK",
        S + ["zone_id", "tonnage", "valid_from"],
        reason="권역·톤수·적용일 1건",
    ),
    c(
        FR,
        "CHECK",
        ["tonnage", "base_rate", "extra_stop_rate", "waiting_rate_per_hour"],
        "tonnage > 0 AND base_rate >= 0 AND extra_stop_rate >= 0 AND waiting_rate_per_hour >= 0",
        "운임 값",
    ),
    c(
        DI,
        "CHECK",
        ["direction", "status"],
        f"direction IN ('OUTBOUND', 'INBOUND') AND status IN ({q(DISPATCH_STATES)})",
        "방향·상태",
    ),
    c(
        DI,
        "CHECK",
        ["status", "loaded_at", "departed_at", "completed_at", "cancel_reason"],
        "(status = 'PLANNED' AND loaded_at IS NULL AND departed_at IS NULL) OR (status = 'LOADED' AND loaded_at IS NOT NULL AND departed_at IS NULL) OR "
        "(status = 'DEPARTED' AND departed_at >= loaded_at AND completed_at IS NULL) OR (status = 'COMPLETED' AND completed_at >= departed_at) OR "
        "(status = 'CANCELLED' AND departed_at IS NULL AND length(btrim(cancel_reason)) > 0)",
        "상태별 시각(출발 후 취소 불가)",
    ),
    c(
        DI,
        "SERVICE/DB_POLICY",
        ["total_weight_kg"],
        "적재 합계 = 방문 중량·용적 합. 차량 한도 초과면 경고(차단 아님, Q3). 상차 완료 = 모든 방문 LOADED. 출하 방문은 fs.wms.interface 피킹 완료 출하지시만 담을 수 있다(Q1)",
        "배차·적재 규칙(Q1·Q3)",
    ),
    c(
        DI,
        "SERVICE/DB_POLICY",
        ["status"],
        "TMS는 ERP·WMS를 바꾸지 않는다. ERP가 fs.tms.interface.loaded_shipments()를 읽어 출하 확정 대기로 보여 주고 사람이 ERP에서 확정, deliveries()로 납품 확인. WMS는 inbound_arrivals()로 입고 예정 차량·도착을 채운다(Q6)",
        "ERP·WMS 경계(Q1·Q6)",
    ),
    c(DS, "UK", S + ["dispatch_id", "seq"], reason="배차·순서 유일"),
    c(
        DS,
        "CHECK",
        ["kind", "shipment_order_no", "po_no", "inbound_notice_no"],
        "(kind = 'DELIVERY' AND shipment_order_no IS NOT NULL AND po_no IS NULL AND inbound_notice_no IS NULL) OR (kind = 'PICKUP' AND shipment_order_no IS NULL AND (po_no IS NOT NULL OR inbound_notice_no IS NOT NULL))",
        "종류별 원천 번호",
    ),
    c(
        DS,
        "CHECK",
        ["status", "weight_kg", "volume_m3"],
        f"status IN ({q(STOP_STATES)}) AND weight_kg >= 0 AND (volume_m3 IS NULL OR volume_m3 >= 0)",
        "상태·중량",
    ),
    c(
        DS,
        "CHECK",
        ["status", "receiver_name", "fail_reason", "finished_at"],
        "((status IN ('DELIVERED', 'PARTIAL')) = (receiver_name IS NOT NULL AND length(btrim(receiver_name)) > 0)) AND ((status = 'FAILED') = (fail_reason IS NOT NULL)) "
        "AND ((status IN ('DELIVERED', 'PARTIAL', 'FAILED')) = (finished_at IS NOT NULL)) AND (fail_reason IS NULL OR fail_reason IN ('ABSENT', 'REFUSED', 'DAMAGED', 'OTHER'))",
        "인수·실패 기록",
    ),
    uk_partial(
        DS,
        ["shipment_order_no"],
        "shipment_order_no IS NOT NULL AND status NOT IN ('FAILED', 'CANCELLED')",
        "출하지시당 살아 있는 배송 1건(실패 후 재배차 가능)",
    ),
    c(
        DS,
        "SERVICE/DB_POLICY",
        ["status"],
        "기사 화면(현장 단말 패턴 K, Q4)에서 도착·인수(인수자 이름)·부분 인수(메모)·실패(사유) 입력. 실패·부분 인수는 ERP 판매 반품 후보로 deliveries()에 표시",
        "배송 완료 입력(Q4)",
    ),
    c(
        DC,
        "CHECK",
        ["kind", "amount"],
        f"kind IN ({q(CHARGE_KINDS)}) AND amount >= 0",
        "종류·금액",
    ),
    c(
        DC,
        "SERVICE/DB_POLICY",
        ["kind"],
        "운행 완료 시 운임표(권역 = 마지막 배송지 권역, 톤수 = 차량, 적용일 최신)로 BASE + 경유지 수 × EXTRA_STOP 행 생성. 자차는 TOLL·FUEL 등 운행비를 기록(Q7). 정산 확정 후 불변",
        "운임 계산(Q5·Q7)",
    ),
    c(
        SE,
        "CHECK",
        ["settle_month"],
        "settle_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'",
        "'YYYY-MM' 형식",
    ),
    c(
        SE,
        "CHECK",
        ["status", "confirmed_at", "cancel_reason", "total_amount"],
        "total_amount >= 0 AND ((status = 'draft' AND confirmed_at IS NULL) OR (status = 'confirmed' AND confirmed_at IS NOT NULL) OR (status = 'cancelled' AND length(btrim(cancel_reason)) > 0))",
        "상태별 값",
    ),
    uk_partial(
        SE,
        ["carrier_id", "settle_month"],
        "status = 'confirmed'",
        "운송사·월당 확정 정산 1건",
    ),
    c(
        SE,
        "SERVICE/DB_POLICY",
        ["total_amount"],
        "정산 금액 = 그 달 완료된 그 운송사 차량 배차의 운행 비용 합. 확정분을 fs.tms.interface.carrier_settlements()로 ERP가 읽어 직접 매입(외주 운송비). 확정 후 불변, 정정은 취소 후 재작성",
        "용차 정산(Q5)",
    ),
]
for t, cols_ in [
    (VE, ["carrier_id"]),
    (DP, ["zone_id"]),
    (DI, ["dispatch_on", "status"]),
    (DS, ["dispatch_id"]),
    (DC, ["dispatch_id"]),
    (SE, ["carrier_id"]),
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
    r(VE, ["carrier_id"], CA, "운송사"),
    r(DR, ["carrier_id"], CA, "소속 운송사"),
    r(DP, ["zone_id"], ZO, "권역"),
    r(FR, ["zone_id"], ZO, "권역"),
    r(DI, ["vehicle_id"], VE, "차량"),
    r(DI, ["driver_id"], DR, "기사"),
    r(DI, ["settlement_id"], SE, "운송사 정산"),
    r(DS, ["dispatch_id"], DI, "배차"),
    r(DS, ["delivery_point_id"], DP, "배송지"),
    r(DC, ["dispatch_id"], DI, "배차"),
    r(SE, ["carrier_id"], CA, "운송사"),
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
        DI,
        DISPATCH_STATES,
        "PLANNED",
        "PLANNED→LOADED→DEPARTED→COMPLETED; 출발 전 CANCELLED",
    ),
    st(
        DS,
        STOP_STATES,
        "PENDING",
        "PENDING→LOADED→ARRIVED→DELIVERED/PARTIAL/FAILED; 배차 취소 시 CANCELLED",
    ),
    st(
        SE,
        ("draft", "confirmed", "cancelled"),
        "draft",
        "draft→confirmed→cancelled(재작성)",
    ),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn23은 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "pop.entry" not in names:
        raise SystemExit("apply_dsn22를 먼저 적용한다")
    if DI in names:
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
        x["expression"] = x["expression"].rstrip(")") + ", 'tms')"
    for code in d["code_lists"]:
        if (
            code["target"] in MODULE_TABLES
            and code["column"] == "module_key"
            and "tms" not in code["values"]
        ):
            code["values"] = [*code["values"], "tms"]
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    d["code_lists"].append(
        dict(
            target=DI,
            column="direction",
            values=["OUTBOUND", "INBOUND"],
            default=None,
            note="출하 / 조달",
        )
    )
    d.update(version="target-0.11.0", task="DSN-23", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.11.0",
            task="DSN-23",
            date="2026-10-05",
            change="TMS 신규: tms 10테이블(운송사·차량·기사·권역·배송지·운임표·배차·방문·운행 비용·운송사 정산), 모듈 키 tms. 업무 스키마 간 FK 0(ERP 출하지시·발주, WMS 입고 예정은 번호 스냅샷)",
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
    tms = [t for t in d["tables"] if t["name"].startswith(T)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                tms_tables=len(tms),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
